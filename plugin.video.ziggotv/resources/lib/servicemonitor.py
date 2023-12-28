from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import os
import json
import threading
from resources.lib.proxyserver import ProxyServer
from resources.lib.utils import Timer, SharedProperties, ServiceStatus
from resources.lib.webcalls import LoginSession


class HttpProxyService:
    def __init__(self, svc_lock):
        self.lock = svc_lock
        self.profileFolder = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
        self.address = ''
        self.port = 80
        self.isShutDown = True
        self.HTTPServerThread = None
        self.ProxyServer = None  # started by me
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
            self.ProxyServer = None
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
    def __init__(self, service: HttpProxyService, svc_lock):
        super(ServiceMonitor, self).__init__()
        self.addon = xbmcaddon.Addon()
        self.home = SharedProperties(addon=self.addon)
        self.home.setServiceStatus(ServiceStatus.STARTING)
        self.lock = svc_lock
        self.service: HttpProxyService = service
        self.timer = None
        self.refreshTimer = None
        self.session = LoginSession(self.addon)
        self.__initialize_session(self.session)
        xbmc.log("SERVICEMONITOR initialized: {0}".format(service), xbmc.LOGINFO)
        self.home.setServiceStatus(ServiceStatus.STARTED)

    def __initialize_session(self, session: LoginSession):
        addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        Path(addon_path).mkdir(parents=True, exist_ok=True)
        self.__refresh_session()
        self.refreshTimer = Timer(60, self.__refresh_session)
        self.refreshTimer.start()

    def __refresh_session(self):
        if self.addon.getSetting('username') == '':
            xbmcaddon.Addon().openSettings()
        if self.addon.getSetting('username') == '':
            xbmcgui.Dialog().ok('Error', 'Login credentials not set, exiting')
            raise RuntimeError('Login credentials not set')
        else:
            username = self.addon.getSetting('username')
            password = self.addon.getSetting('password')

        self.session.load_cookies()
        session_info = self.session.login(username, password)
        if len(session_info) == 0:
            raise RuntimeError("Login failed, check your credentials")
        self.session.load_cookies()
        self.session.refresh_widevine_license()
        self.session.refresh_entitlements()
        self.session.refresh_channels()

    def update_token(self):
        if self.service.ProxyServer is None:
            xbmc.log('SERVICEMONITOR ProxyServer not started yet', xbmc.LOGDEBUG)
            return
        # session = LoginSession(self.addon)
        # session.load_cookies()
        proxy: ProxyServer = self.service.ProxyServer
        xbmc.log("Refresh token interval expired", xbmc.LOGDEBUG)
        token = proxy.get_streaming_token()
        if token is None or token == '':
            return
        streaming_token = self.session.update_token(proxy.get_streaming_token())
        proxy.set_streaming_token(streaming_token)

    def onNotification(self, sender: str, method: str, data: str) -> None:
        if self.service.ProxyServer is None:
            xbmc.log('SERVICEMONITOR ProxyServer not started yet', xbmc.LOGERROR)
            return
        proxy: ProxyServer = self.service.ProxyServer
        xbmc.log("SERVICEMONITOR Notification: {0},{1},{2}".format(sender, method, data), xbmc.LOGINFO)
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
                self.session.delete_token(proxy.get_streaming_token())
                proxy.session.streaming_token = None
                proxy.set_streaming_token(None)

        # xbmc,Playlist.OnAdd,{"item":{"title":"1. NPO 1","type":"video"},"playlistid":1,"position":0})
        # xbmc, Info.OnChanged, null ????
        # xbmc, Player.OnPlay, {"item": {"title": "", "type": "video"}, "player": {"playerid": 1, "speed": 1}}
        # xbmc,Player.OnAVChange,{"item":{"title":"","type":"video"},"player":{"playerid":1,"speed":1}}
        # xbmc,Player.OnAVChange,{"item":{"title":"","type":"video"},"player":{"playerid":1,"speed":1}}
        # xbmc,Player.OnAVStart,{"item":{"title":"","type":"video"},"player":{"playerid":1,"speed":1}}
        # xbmc,Playlist.OnClear,{"playlistid":1}
        # xbmc,Player.OnStop,{"end":false,"item":{"title":"1. NPO 1","type":"video"}}
        # xbmc,Player.OnPause,{"item":{"title":"2. NPO 2","type":"video"},"player":{"playerid":1,"speed":0}}
        # xbmc,Player.OnResume,{"item":{"title":"2. NPO 2","type":"video"},"player":{"playerid":1,"speed":1}}
        # xbmc,Player.OnSpeedChanged,{"item":{"title":"2. NPO 2","type":"video"},"player":{"playerid":1,"speed":2}}

    def shutdown(self):
        self.home.setServiceStatus(ServiceStatus.STOPPING)
        if self.timer is not None:
            self.timer.stop()
        if self.refreshTimer is not None:
            self.refreshTimer.stop()
        xbmc.log("SERVICE-MONITOR Timers stopped", xbmc.LOGDEBUG)
        self.home.setServiceStatus(ServiceStatus.STOPPED)

