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
    def __init__(self, svcLock):
        self.lock = svcLock
        self.profileFolder = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
        self.address = ''
        self.port = 80
        self.isShutDown = True
        self.httpServerThread = None
        self.proxyServer: http.server.HTTPServer = None  # started by me
        self.settingsChangeLock = threading.Lock()
        xbmc.log("Proxy service initialized", xbmc.LOGDEBUG)

    def set_address(self, addressAndPort):
        """
        funtion to set ip address and port
        :param addressAndPort: tuple containing address:str and port:int
        :return:
        """
        with self.lock:
            self.address, self.port = addressAndPort

    def restart_http_server(self):
        with self.settingsChangeLock:
            self.stop_http_server()
            self.start_http_server()

    def start_http_server(self):
        self.isShutDown = False
        self.stop_http_server()
        try:
            self.proxyServer = ProxyServer(self, (self.address, self.port), self.lock)
        except IOError:
            pass

        thread = threading.Thread(target=self.proxyServer.serve_forever)
        thread.start()
        self.httpServerThread = thread
        xbmc.log("ProxyService started listening on {0}-{1}".format(self.address,
                                                                    self.port), xbmc.LOGINFO)

    def stop_http_server(self):
        if self.proxyServer is not None:
            self.proxyServer.shutdown()
            xbmc.log("PROXY SERVER STOPPPED", xbmc.LOGDEBUG)
        if self.httpServerThread is not None:
            self.httpServerThread.join()
            self.httpServerThread = None
            xbmc.log("HTTP SERVER THREAD STOPPPED", xbmc.LOGDEBUG)
        self.isShutDown = True

    def clear_browser_lock(self):
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
        super().__init__()
        self.lock = threading.Lock()

        #  Start the HTTP Proxy server
        port = xbmcaddon.Addon().getSettingNumber('proxy-port')
        ip = xbmcaddon.Addon().getSetting('proxy-ip')
        self.proxyService = HttpProxyService(self.lock)
        self.proxyService.set_address((ip, int(port)))
        self.proxyService.start_http_server()

        #  Set the status of this service to STARTING
        self.addon = xbmcaddon.Addon()
        self.home = SharedProperties(addon=self.addon)
        self.home.set_uuid()
        self.home.set_service_status(ServiceStatus.STARTING)

        self.helper = ProxyHelper(self.addon)
        self.timer = None
        self.refreshTimer = None
        self.licenseRefreshed = datetime.datetime.now() - datetime.timedelta(days=2)
        self.epg = None
        self.__initialize_session()

        #  Set the status of this service to STARTED
        self.home.set_service_status(ServiceStatus.STARTED)
        xbmc.log('SERVICEMONITOR initialized: ', xbmc.LOGDEBUG)

    def __initialize_session(self):
        addonPath = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        Path(addonPath).mkdir(parents=True, exist_ok=True)
        self.__refresh_session()
        self.refreshTimer = Timer(600, self.__refresh_session)
        self.refreshTimer.start()
        self.helper.dynamic_call(LoginSession.close)

    def __refresh_session(self):
        if self.addon.getSetting('username') == '':
            xbmcaddon.Addon().openSettings()
        if self.addon.getSetting('username') == '':
            xbmcgui.Dialog().ok('Error', 'Login credentials not set, exiting')
            raise RuntimeError('Login credentials not set')
        username = self.addon.getSetting('username')
        password = self.addon.getSetting('password')

        try:
            sessionInfo = self.helper.dynamic_call(LoginSession.login, username=username, password=password)
            if len(sessionInfo) == 0:
                raise RuntimeError("Login failed, check your credentials")
            # The Widevine license and entitlements will only be refreshed once per day, because they do not change
            # If entitlements change or the license becomes invalid, a restart is required.
            if (self.licenseRefreshed + datetime.timedelta(days=1)) <= datetime.datetime.now():
                self.licenseRefreshed = datetime.datetime.now()
                self.helper.dynamic_call(LoginSession.refresh_widevine_license)
                self.helper.dynamic_call(LoginSession.refresh_entitlements)
            self.helper.dynamic_call(LoginSession.refresh_channels)
            channels = self.helper.dynamic_call(LoginSession.get_channels)
            if self.epg is None:
                self.epg = ChannelGuide(self.addon, channels)
            self.epg.load_stored_events()
            self.epg.obtain_events()
            self.epg.store_events()
            self.helper.dynamic_call(LoginSession.close)
        except ConnectionResetError as exc:
            xbmc.log('Connection reset in __refresh_session, will retry later: {0}'.format(exc), xbmc.LOGERROR)
        except Exception as exc:
            xbmc.log('Unexpected exception in __refresh_session: {0}'.format(exc), xbmc.LOGERROR)

    def update_token(self):
        if self.proxyService.proxyServer is None:
            xbmc.log('SERVICEMONITOR ProxyServer not started yet', xbmc.LOGDEBUG)
            return
        # session = LoginSession(self.addon)
        # session.load_cookies()
        proxy: ProxyServer = self.proxyService.proxyServer
        xbmc.log("Refresh token interval expired", xbmc.LOGDEBUG)
        token = proxy.get_streaming_token()
        if token is None or token == '':
            return
        streamingToken = self.helper.dynamic_call(LoginSession.update_token, streaming_token=token)
        proxy.set_streaming_token(streamingToken)

    def onNotification(self, sender: str, method: str, data: str) -> None:
        if self.proxyService.proxyServer is None:
            xbmc.log('SERVICEMONITOR ProxyServer not started yet', xbmc.LOGERROR)
            return
        proxy: ProxyServer = self.proxyService.proxyServer
        xbmc.log("SERVICEMONITOR Notification: {0},{1},{2}".format(sender, method, data), xbmc.LOGDEBUG)
        if sender == self.addon.getAddonInfo("id"):
            params = json.loads(data)
            xbmc.log("SERVICEMONITOR command and params: {0},{1}".format(params['command'],
                                                                         params['command_params']), xbmc.LOGDEBUG)
            if params['command'] == 'play_video':
                streamingToken = params['command_params']['streamingToken']
                proxy.set_streaming_token(streamingToken)
                self.timer = Timer(60, self.update_token)
                self.timer.start()

        elif sender == 'xbmc':
            if method == 'Player.OnStop':
                if self.timer is not None:
                    self.timer.stop()
                # session = LoginSession(self.addon)
                # session.load_cookies()
                xbmc.log("Delete token after OnStop", xbmc.LOGDEBUG)
                self.helper.dynamic_call(LoginSession.delete_token, streaming_id=proxy.get_streaming_token())
                proxy.session.streamingToken = None
                proxy.set_streaming_token(None)

    def shutdown(self):
        self.proxyService.stop_http_server()
        self.home.set_service_status(ServiceStatus.STOPPING)
        if self.timer is not None:
            self.timer.stop()
        if self.refreshTimer is not None:
            self.refreshTimer.stop()
        xbmc.log("SERVICE-MONITOR Timers stopped", xbmc.LOGDEBUG)
        self.home.set_service_status(ServiceStatus.STOPPED)
