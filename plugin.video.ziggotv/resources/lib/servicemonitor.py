import asyncio
import json
import threading

import xbmc
import xbmcaddon
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
        xbmc.log("SERVICE-MONITOR initialized", xbmc.LOGDEBUG)

    def update_token(self):
        if self.ProxyServer is None:
            xbmc.log('SERVICE-MONITOR ProxyServer not started yet', xbmc.LOGDEBUG)
            return
        session = LoginSession(self.addon)
        session.load_cookies()
        xbmc.log("Refresh token interval expired", xbmc.LOGDEBUG)
        token = self.ProxyServer.get_streaming_token()
        if token is None or token == '':
            return
        streaming_token = session.update_token(self.ProxyServer.get_streaming_token())
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
                session = LoginSession(self.addon)
                session.load_cookies()
                xbmc.log("Delete token after OnStop", xbmc.LOGDEBUG)
                session.delete_token(self.ProxyServer.get_streaming_token())
                session.streaming_token = None
                self.ProxyServer.set_streaming_token(session.streaming_token)

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

    async def cleanup(self):
        await self.webapp.cleanup()
        await self.webapp.shutdown()

    async def start_proxy(self):
        await self.stop_proxy()
        self.isShutDown = False
        lock = threading.Lock()
        self.ProxyServer = ProxyServer(lock)

        self.webapp.add_routes([web.get('/manifest', self.ProxyServer.manifest_handler),
                                web.get('/ {tail:. *}', self.ProxyServer.default_handler),
                                web.post('/license', self.ProxyServer.license_handler)])
        self.apprunner = web.AppRunner(self.webapp)
        await self.apprunner.setup()
        self.site = web.TCPSite(self.apprunner, port=6969, host='127.0.0.1')
        await self.site.start()

    async def stop_proxy(self):
        self.isShutDown = True
        if self.ProxyServer is not None:
            await self.apprunner.cleanup()
            # await self.webapp.shutdown()
            # await self.webapp.cleanup()
            print("PROXY SERVER SHUTDOWN")
            self.ProxyServer = None
        self.isShutDown = True


async def main():
    monitor_service = ServiceMonitor(loop)
    try:
        while not monitor_service.abortRequested():
            # Sleep/wait for abort for 10 seconds
            await asyncio.sleep(10)
            # if monitor_service.waitForAbort(10):
            # Abort was requested while waiting. We should exit
        print("MONITOR PROXY SERVICE WAITFORABORT timeout")
        await monitor_service.cleanup()

    except Exception as exc:
        print("UNEXPECTED EXCEPTION IN SERVICE: ", exc)
    #    await asyncio.sleep(600)
    await monitor_service.stop_proxy()
    print("STOPPING PROXY SERVICE")


if __name__ == '__main__':
    # Note : normally not called, only in tests
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
