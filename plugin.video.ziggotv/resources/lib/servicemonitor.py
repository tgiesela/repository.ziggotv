import datetime
import http.server
import json
import os
import threading
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib.channel import ChannelGuide
from resources.lib.proxyserver import ProxyServer
from resources.lib.utils import Timer, SharedProperties, ServiceStatus, ProxyHelper
from resources.lib.webcalls import LoginSession


class HttpProxyService:
    def __init__(self, svc_lock):
        self.lock = svc_lock
        self.profileFolder = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
        self.address = ''
        self.port = 80
        self.isShutDown = True
        self.HTTPServerThread = None
        self.ProxyServer: http.server.HTTPServer = None  # started by me
        self.settingsChangeLock = threading.Lock()
        xbmc.log("Proxy service initialized", xbmc.LOGDEBUG)

    def set_address(self, address_and_port):
        """
        funtion to set ip address and port
        :param address_and_port: tuple containing address:str and port:int
        :return:
        """
        with self.lock:
            self.address, self.port = address_and_port

    def restartHttpServer(self):
        with self.settingsChangeLock:
            self.stopHttpServer()
            self.startHttpServer()

    def startHttpServer(self):
        self.isShutDown = False
        self.stopHttpServer()
        try:
            self.ProxyServer = ProxyServer(self, (self.address, self.port), self.lock)
        except IOError as e:
            pass

        thread = threading.Thread(target=self.ProxyServer.serve_forever)
        thread.start()
        self.HTTPServerThread = thread
        xbmc.log("ProxyService started listening on {0}-{1}".format(self.address,
                                                                    self.port), xbmc.LOGINFO)

    def stopHttpServer(self):
        if self.ProxyServer is not None:
            self.ProxyServer.shutdown()
            xbmc.log("PROXY SERVER STOPPPED", xbmc.LOGDEBUG)
        if self.HTTPServerThread is not None:
            self.HTTPServerThread.join()
            self.HTTPServerThread = None
            xbmc.log("HTTP SERVER THREAD STOPPPED", xbmc.LOGDEBUG)
        self.isShutDown = True

    def clearBrowserLock(self):
        """Clears the pidfile in case the last shutdown was not clean"""
        browserLockPath = os.path.join(self.profileFolder, 'browser.pid')
        try:
            os.remove(browserLockPath)
        except OSError:
            pass


class ServiceMonitor(xbmc.Monitor):
    """
        Servicemonitor keeps data up to date.
        Starts the HTTP Proxy which is the central process to maintain session data.
        All methods of LoginSession are called via the dynamic procedure calls.

    """
    def __init__(self):
        super(ServiceMonitor, self).__init__()
        self.lock = threading.Lock()

        #  Start the HTTP Proxy server
        port = xbmcaddon.Addon().getSettingNumber('proxy-port')
        ip = xbmcaddon.Addon().getSetting('proxy-ip')
        self.proxy_service = HttpProxyService(self.lock)
        self.proxy_service.set_address((ip, int(port)))
        self.proxy_service.startHttpServer()

        #  Set the status of this service to STARTING
        self.addon = xbmcaddon.Addon()
        self.home = SharedProperties(addon=self.addon)
        self.home.setUUID()
        self.home.setServiceStatus(ServiceStatus.STARTING)

        self.helper = ProxyHelper(self.addon)
        self.timer = None
        self.refreshTimer = None
        self.licenseRefreshed = datetime.datetime.now() - datetime.timedelta(days=2)
        self.epg = None
        self.__initialize_session()

        #  Set the status of this service to STARTED
        self.home.setServiceStatus(ServiceStatus.STARTED)
        xbmc.log('SERVICEMONITOR initialized: ', xbmc.LOGDEBUG)

    def __initialize_session(self):
        addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        Path(addon_path).mkdir(parents=True, exist_ok=True)
        self.__refresh_session()
        self.refreshTimer = Timer(600, self.__refresh_session)
        self.refreshTimer.start()
        self.helper.dynamicCall(LoginSession.close)

    def __refresh_session(self):
        if self.addon.getSetting('username') == '':
            xbmcaddon.Addon().openSettings()
        if self.addon.getSetting('username') == '':
            xbmcgui.Dialog().ok('Error', 'Login credentials not set, exiting')
            raise RuntimeError('Login credentials not set')
        else:
            username = self.addon.getSetting('username')
            password = self.addon.getSetting('password')

        try:
            session_info = self.helper.dynamicCall(LoginSession.login, username=username, password=password)
            if len(session_info) == 0:
                raise RuntimeError("Login failed, check your credentials")
            # The Widevine license and entitlements will only be refreshed once per day, because they do not change
            # If entitlements change or the license becomes invalid, a restart is required.
            if (self.licenseRefreshed + datetime.timedelta(days=1)) <= datetime.datetime.now():
                self.licenseRefreshed = datetime.datetime.now()
                self.helper.dynamicCall(LoginSession.refresh_widevine_license)
                self.helper.dynamicCall(LoginSession.refresh_entitlements)
            self.helper.dynamicCall(LoginSession.refresh_channels)
            if self.epg is None:
                self.epg = ChannelGuide(self.addon)
            self.epg.loadStoredEvents()
            self.epg.obtainEvents()
            self.epg.storeEvents()
            self.helper.dynamicCall(LoginSession.close)
        except ConnectionResetError as exc:
            xbmc.log('Connection reset in __refresh_session, will retry later: {0}'.format(exc), xbmc.LOGERROR)
        except Exception as exc:
            xbmc.log('Unexpected exception in __refresh_session: {0}'.format(exc), xbmc.LOGERROR)

    def update_token(self):
        if self.proxy_service.ProxyServer is None:
            xbmc.log('SERVICEMONITOR ProxyServer not started yet', xbmc.LOGDEBUG)
            return
        # session = LoginSession(self.addon)
        # session.load_cookies()
        proxy: ProxyServer = self.proxy_service.ProxyServer
        xbmc.log("Refresh token interval expired", xbmc.LOGDEBUG)
        token = proxy.get_streaming_token()
        if token is None or token == '':
            return
        streaming_token = self.helper.dynamicCall(LoginSession.update_token, streaming_token=token)
        proxy.set_streaming_token(streaming_token)

    def onNotification(self, sender: str, method: str, data: str) -> None:
        if self.proxy_service.ProxyServer is None:
            xbmc.log('SERVICEMONITOR ProxyServer not started yet', xbmc.LOGERROR)
            return
        proxy: ProxyServer = self.proxy_service.ProxyServer
        xbmc.log("SERVICEMONITOR Notification: {0},{1},{2}".format(sender, method, data), xbmc.LOGDEBUG)
        if sender == self.addon.getAddonInfo("id"):
            params = json.loads(data)
            xbmc.log("SERVICEMONITOR command and params: {0},{1}".format(params['command'],
                                                                         params['command_params']), xbmc.LOGDEBUG)
            if params['command'] == 'play_video':
                streaming_token = params['command_params']['streamingToken']
                proxy.set_streaming_token(streaming_token)
                self.timer = Timer(60, self.update_token)
                self.timer.start()

        elif sender == 'xbmc':
            if method == 'Player.OnStop':
                if self.timer is not None:
                    self.timer.stop()
                # session = LoginSession(self.addon)
                # session.load_cookies()
                xbmc.log("Delete token after OnStop", xbmc.LOGDEBUG)
                self.helper.dynamicCall(LoginSession.delete_token, streaming_id=proxy.get_streaming_token())
                proxy.session.streaming_token = None
                proxy.set_streaming_token(None)

    def shutdown(self):
        self.proxy_service.stopHttpServer()
        self.home.setServiceStatus(ServiceStatus.STOPPING)
        if self.timer is not None:
            self.timer.stop()
        if self.refreshTimer is not None:
            self.refreshTimer.stop()
        xbmc.log("SERVICE-MONITOR Timers stopped", xbmc.LOGDEBUG)
        self.home.setServiceStatus(ServiceStatus.STOPPED)
