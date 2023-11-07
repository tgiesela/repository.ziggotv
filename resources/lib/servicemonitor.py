import asyncio
import json
import threading
import time
from asyncio import AbstractEventLoop

import xbmc
import xbmcaddon
from aiohttp import web

from resources.lib.proxy import ProxyServer
from resources.lib.webcalls import LoginSession
from resources.lib.utils import Timer


class ServiceMonitor(xbmc.Monitor):
    def __init__(self, loop: AbstractEventLoop):
        super(ServiceMonitor, self).__init__()
        self.site = None
        self.apprunner = None
        self.webapp: web.Application = web.Application()
        self.ProxyServerThread: threading.Thread = None
        self.ProxyServer = None
        self.isShutDown = None
        self.locator = None
        self.addon = xbmcaddon.Addon()
        self.channelid = ''
        self.timer = None
        self.loop: AbstractEventLoop = loop
        xbmc.log("SERVICE-MONITOR initialized", xbmc.LOGDEBUG)

    def update_token(self):
        if self.ProxyServer is None:
            xbmc.log('SERVICE-MONITOR ProxyServer not started yet', xbmc.LOGDEBUG)
            return
        session = LoginSession(self.addon)
        session.load_cookies()
        print("Refresh token for channel: {0}".format(self.channelid))
        streaming_token = session.update_token(self.ProxyServer.get_streaming_token())
        self.ProxyServer.set_streaming_token(streaming_token)

    def onNotification(self, sender: str, method: str, data: str) -> None:
        if self.ProxyServer is None:
            print('SERVICE-MONITOR ProxyServer not started yet')
            return
        print("SERVICE-MONITOR Notification: {0},{1},{2}".format(sender, method, data))
        if sender == self.addon.getAddonInfo("id"):
            params = json.loads(data)
            print("SERVICE-MONITOR command and params: {0},{1}".format(params['command'], params['command_params']))
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
                self.timer.stop()
                session = LoginSession(self.addon)
                session.load_cookies()
                session.delete_token(self.ProxyServer.get_streaming_token())

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

    def cleanup(self):
        pass

    async def start_proxy(self):
        await self.stop_proxy()
        self.isShutDown = False
        self.ProxyServer = ProxyServer()

        self.webapp.add_routes([web.get('/manifest', self.ProxyServer.manifest_handler),
                                web.get('/ {tail:. *}', self.ProxyServer.default_handler),
                                web.post('/license', self.ProxyServer.license_handler)])
        # thread = threading.Thread(target=web.run_app, kwargs=({'app': self.webapp, 'host': '127.0.0.1', 'port': 6969}))
        # thread.start()
        # self.ProxyServerThread = thread
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
        if self.ProxyServerThread is not None:
            self.ProxyServerThread.join(1)
            self.ProxyServerThread = None
            print("HTTP SERVER THREAD STOPPED")
        self.isShutDown = True

    async def run(self, host: str = 'localhost', port: int = 1081):
        xbmc.log(f'AIOHTTP getting event-loop, http://{host}:{port}', xbmc.LOGDEBUG)
        # self.loop.create_task(self.start_proxy())
        await self.start_proxy()
        while not self.abortRequested():
            await asyncio.sleep(10)
        await self.stop_proxy()


async def main():
    monitor_service = ServiceMonitor(loop)
    await monitor_service.start_proxy()
    try:
        while not monitor_service.abortRequested():
            # Sleep/wait for abort for 10 seconds
            await asyncio.sleep(10)
            # if monitor_service.waitForAbort(10):
            # Abort was requested while waiting. We should exit
        print("MONITOR PROXY SERVICE WAITFORABORT timeout")
        monitor_service.cleanup()

    except Exception as exc:
        print("UNEXPECTED EXCEPTION IN SERVICE: ", exc)
    #    await asyncio.sleep(600)
    await monitor_service.stop_proxy()
    print("STOPPING PROXY SERVICE")


if __name__ == '__main__':
    # Note : normally not called, only in tests
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
