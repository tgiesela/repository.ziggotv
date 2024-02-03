import asyncio
import json
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from aiohttp import web

from resources.lib.proxy import ProxyServer
from resources.lib.webcalls import LoginSession
from resources.lib.utils import Timer


class ServiceMonitor(xbmc.Monitor):
    def __init__(self, service: ProxyServer):
        super(ServiceMonitor, self).__init__()
        self.addon = xbmcaddon.Addon()
        self.site = None
        self.apprunner = None
        self.webapp: web.Application = web.Application()
        self.ProxyServer = service
        self.isShutDown = None
        self.locator = None
        self.addon = xbmcaddon.Addon()
        self.channelid = ''
        self.timer = None
        self.refreshTimer = None
        self.session = LoginSession(self.addon)
        self.__initialize_session(self.session)
        xbmc.log("SERVICE-MONITOR initialized", xbmc.LOGDEBUG)

    def __initialize_session(self, session: LoginSession):
        addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        Path(addon_path).mkdir(parents=True, exist_ok=True)
        self.__refresh_session()
        self.refreshTimer = Timer(600, self.__refresh_session)
        self.refreshTimer.start()

    def __refresh_session(self):
        if self.addon.getSetting('username') == '':
            xbmcaddon.Addon().openSettings()
        if self.addon.getSetting('username') == '':
            xbmcgui.Dialog().ok('Error', 'Login credentials not set, exiting')
            raise Exception('Login credentials not set')
        else:
            username = self.addon.getSetting('username')
            password = self.addon.getSetting('password')

        self.session.load_cookies()
        session_info = self.session.login(username, password)
        if len(session_info) == 0:
            raise RuntimeError("Login failed, check your credentials")
        xbmc.log("ADDON: {0}, authenticated with: {1}".format(self.addon.getAddonInfo('name'),
                                                              username), 0)
        self.session.refresh_widevine_license()
        self.session.refresh_entitlements()
        self.session.refresh_channels()
        self.session.load_cookies()

    def update_token(self):
        if self.ProxyServer is None:
            xbmc.log('SERVICE-MONITOR ProxyServer not started yet', xbmc.LOGDEBUG)
            return
        # session = LoginSession(self.addon)
        # self.session.load_cookies()
        xbmc.log("Refresh token interval expired", xbmc.LOGDEBUG)
        token = self.ProxyServer.get_streaming_token()
        if token is None or token == '':
            return
        streaming_token = self.session.update_token(self.ProxyServer.get_streaming_token())
        self.ProxyServer.set_streaming_token(streaming_token)

    def onNotification(self, sender: str, method: str, data: str) -> None:
        if self.ProxyServer is None:
            xbmc.log('SERVICE-MONITOR ProxyServer not started yet', xbmc.LOGERROR)
            return
        xbmc.log("SERVICE-MONITOR Notification: {0},{1},{2}".format(sender, method, data), xbmc.LOGINFO)
        if sender == self.addon.getAddonInfo("id"):
            params = json.loads(data)
            xbmc.log("SERVICE-MONITOR command and params: {0},{1}".format(params['command'],
                                                                          params['command_params']), xbmc.LOGDEBUG)
            if params['command'] == 'play_video':
                self.channelid = params['command_params']['uniqueId']
                self.locator = params['command_params']['locator']
                streaming_token = params['command_params']['streamingToken']
                self.ProxyServer.set_streaming_token(streaming_token)
                self.ProxyServer.set_locator(self.locator)
                self.timer = Timer(60, self.update_token)
                self.timer.start()
        elif sender == 'xbmc':
            if method == 'Player.OnStop':
                if self.timer is not None:
                    self.timer.stop()
                # session = LoginSession(self.addon)
                # self.session.load_cookies()
                xbmc.log("Delete token after OnStop", xbmc.LOGDEBUG)
                self.session.delete_token(self.ProxyServer.get_streaming_token())
                self.session.streamingToken = None
                self.ProxyServer.set_streaming_token(self.session.streamingToken)

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
        if self.timer is not None:
            self.timer.stop()
        if self.refreshTimer is not None:
            self.refreshTimer.stop()
        xbmc.log("SERVICE-MONITOR Timers stopped", xbmc.LOGDEBUG)

async def main():
    monitor_service = ServiceMonitor(loop)
    try:
        while not monitor_service.abortRequested():
            # Sleep/wait for abort for 10 seconds
            await asyncio.sleep(10)
            # if monitor_service.waitForAbort(10):
            # Abort was requested while waiting. We should exit
        xbmc.log("MONITOR PROXY SERVICE WAITFORABORT timeout", xbmc.LOGDEBUG)

    except Exception as exc:
        xbmc.log("UNEXPECTED EXCEPTION IN SERVICE: {0}".format(exc), xbmc.LOGDEBUG)
    #    await asyncio.sleep(600)
    xbmc.log("STOPPING PROXY SERVICE", xbmc.LOGDEBUG)


if __name__ == '__main__':
    # Note : normally not called, only in tests
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
