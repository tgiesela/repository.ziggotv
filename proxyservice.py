import base64
import json
import os
import threading
import http.server
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer
from urllib.parse import urlparse, parse_qs, unquote
from resources.lib.sharedcache import SharedCache
from resources.lib.globals import G
from resources.lib.webcalls import LoginSession

import requests
import xbmc
import xbmcaddon
import xbmcvfs


class HTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Handle http get requests, used for manifest"""
        path = self.path  # Path with parameters received from request e.g. "/manifest?id=234324"
        print('HTTP GET Request received to {}'.format(path))
        if '/manifest' not in path:
            self.send_response(404)
            self.end_headers()
            return
        try:
            # To obtain the DRM Challenge and the DRM Session ID data to make a licensed manifest request,
            # you must set the ISA property: inputstream.adaptive.pre_init_data, see Integration Wiki page
            challenge_base64 = unquote(self.headers['challengeB64'])
            sid = self.headers['sessionId']

            # Call your method to do the magic to generate DASH manifest data
            print(self.headers)
            length = int(self.headers.get('content-length', 0))
            received_data = self.rfile.read(length)
            print("HEX: " + received_data.hex())
            print("B64: ", base64.b64encode(received_data))

            parts = received_data.split(b'!')
            print("# Parts =", len(parts))
            for part in parts:
                print("part HEX: " + part.hex())

            manifest_data = (
                b'0ac502080312101dc8b0e73f05ea9a9e786dbf6540fd01189389ada405228e023082010a0282010100c192abe'
                b'baa94fed6a476cb5b6f5f23b77d1650f9d39ed6e1580d984ecfb5793c0b0a88ba51cf477f3fae42747d834cb3'
                b'8fc0acbe7feb08661c0cfd8c0d193f4a5a6e3f2485961b8da3f21e7c5c9c89663979fd9e5d6e94bf718ef4872'
                b'1744a141d0e0abf07d706997769acf8ce31227559b9b3e9ecf7bc44f4992559a2ed3ff0b9eb95c301f2af4602'
                b'fb7de3fe2cf4b8ce1deaf9e1bb85baf79f13809a00d285a5f8ebffb4c60a1873b3e9d1940165c8bf4cfd315da'
                b'646b95c78da33f3093a33345104676edbda8a2aaa314be04e6c5a83f7b3131170029567754dbbe2aea269fd3c'
                b'909316135d73f6a0fd7e8949f6b0fc4586d989a2717cca0eed17f7aefc5f02030100013a18616c63617472617'
                b'a5f746573745f64726d5f73657276657212800325134ee22264a7f39d9a623c93637c2bd9b4776ce10c2d1382'
                b'83937260e03e2fc9e1c901f0824063c4cb0d1e2992911fabbb0f6fde3ca6ed0297162ede589c3726442fb45ca'
                b'b91806977d9a57148118b4d2706d4ae0bd3056619f62525cb3d2dd0a9db60ebe184595e0669081b2b88cd409c'
                b'237dd82dd503c80620e06f1635fb1769b920d9cca3f0d02f6ff61805d764a171334292c0fab3444e9b84152e3'
                b'e34bb45ea15cc4a1faac900a72a2a6795eba07373a7998054b52f4ce3c562f25dcc6f682ca04ca64fc16b3b1e'
                b'c853a5322f1b4697a16af00bdd76234e03b33c125cc9113a068b4b3f1868be3aea64d2ba01025bf26bc0caed5'
                b'0e814fe538e1238a4df89cfe45454c47e30d92eb690ec892af3e8930e3e3f8794c0a506bc585c4483725609b6'
                b'4802ac63eb61da63b98f8248327f69c098236c5b57f0dc9d352a2fe1ad01be310b56b3060de196a63ee0c3f4e'
                b'e9ec89bb1fda102d2021b4ab8911bc7ab883ce75e67e3b3af53d74f402524e6bfd62ba3c7d983ad8b79722de9'
                b'838136')
            self.send_response(200)
            self.send_header('content-type', 'application/dash+xml')
            self.end_headers()
            self.wfile.write(manifest_data)
        except Exception:
            self.send_response(500)
            self.end_headers()

    def do_POST(self):
        """Handle http post requests, used for license"""
        path = self.path  # Path with parameters received from request e.g. "/license?id=234324"
        print('HTTP POST Request received to {}'.format(path))
        if '/license' not in path:
            self.send_response(404)
            self.end_headers()
            return
        # InputStream Adaptive can send some data depending on license_key settings
        # The data is split by "!" char
        # This example split 'challenge' and 'session id' data
        length = int(self.headers.get('content-length', 0))
        received_data = self.rfile.read(length)
        print("HEX: " + received_data.hex())
        print("B64: ", base64.b64encode(received_data))

        # response = session.do_post(url=license_URL, data=received_data, extra_headers=self.headers)
        parsed_url = urlparse(self.path)
        addon_name = parse_qs(parsed_url.query)['addon'][0]
        content_id = parse_qs(parsed_url.query)['ContentId'][0]
        print('ADDON-name:' + addon_name)
        current_addon = xbmcaddon.Addon(id=addon_name)
        url = G.license_URL
        new_session = LoginSession(current_addon)
        new_headers = {}
        for key in self.headers:
            if key in G.ALLOWED_LICENSE_HEADERS:
                new_headers[key] = self.headers[key]
            else:
                print("HEADER DROPPPED: {0}:{1}".format(key, self.headers[key]))

        new_session.load_cookies()
        # request_data = bytes.fromhex('0804')
        response = new_session.post(url,
                                    params={'ContentId': content_id},
                                    data=received_data,
                                    headers=new_headers)
        # response = requests.post(url,
        #                          params={'contentId': content_id},
        #                          data=received_data,
        #                          headers=new_headers)
        #   if not self.__status_code_ok(response):
        #       raise RuntimeError("status code <> 200 during obtain of widevine_license")
        new_session.print_dialog(response)
        # isa_data = self.rfile.read(length).decode('utf-8').split('!')
        # print("HEX: " + b2ah(response.received_data))
        # print("B64: ", base64.b64encode(received_data))

        # challenge = isa_data[0]
        # session_id = isa_data[1]
        # Call your method to do the magic to generate license data
        # The format type of data must be correct in according to your VOD service
        # license_data = b'my license data'
        for key in response.headers:
            self.headers.add_header(key, response.headers[key])
        self.send_response(response.status_code)
        self.end_headers()
        b64response = base64.b64encode(bytes(response.content))
        self.wfile.write(response.content)


class ServerThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super(ServerThread, self).__init__(*args, **kwargs)
        self._stop = threading.Event()
        self.server_inst = None
        self.port = 80
        self.address = '127.0.0.1'
        print("SERVERTHREAD initialized")

    def set_address(self, address_and_port):
        """
        funtion to set ip address and port
        :param address_and_port: tuple containing address:str and port:int
        :return:
        """
        self.address, self.port = address_and_port

    def run(self):
        print("SERVERTHREAD run called")
        self.server_inst = TCPServer((self.address, self.port), HTTPRequestHandler)
        self.server_inst.serve_forever()

    def stopped(self):
        return self._stop.is_set()

    def stop(self):
        print("SERVERTHREAD stopping")
        self._stop.set()
        if self.server_inst is not None:
            self.server_inst.shutdown()
        print("SERVERTHREAD stopped")


class ProxyServer(http.server.HTTPServer):
    def __init__(self, addon, server_address):
        http.server.HTTPServer.__init__(self, server_address, HTTPRequestHandler)
        self.addon = addon


class HttpProxyService(xbmcaddon.Addon):
    def __init__(self):
        print("Proxy service initializing")
        super().__init__()
        self.profileFolder = xbmcvfs.translatePath(self.getAddonInfo('profile'))
        self.address = ''
        self.port = 80
        self.isShutDown = True
        self.HTTPServerThread = None
        self.ProxyServer = None
        self.settingsChangeLock = threading.Lock()
        print("Proxy service initialized")

    def set_address(self, address_and_port):
        """
        funtion to set ip address and port
        :param address_and_port: tuple containing address:str and port:int
        :return:
        """
        self.address, self.port = address_and_port

    def restartHttpServer(self):
        with self.settingsChangeLock:
            self.stopHttpServer()
            self.startHttpServer()

    def startHttpServer(self):
        # self.HTTPServerThread.start()
        self.isShutDown = False
        self.stopHttpServer()
        try:
            self.ProxyServer = ProxyServer(self, (self.address, self.port))
        except IOError as e:
            pass

        thread = threading.Thread(target=self.ProxyServer.serve_forever)
        thread.start()
        self.HTTPServerThread = thread
        print("SERVERTHREAD started listening on {0}-{1}".format(self.address,
                                                                 self.port))

    def stopHttpServer(self):
        if self.ProxyServer is not None:
            self.ProxyServer.shutdown()
            self.ProxyServer = None
            print("PROXY SERVER STOPPPED")
        if self.HTTPServerThread is not None:
            self.HTTPServerThread.join()
            self.HTTPServerThread = None
            print("HTTP SERVER THREAD STOPPPED")
        self.isShutDown = True

    def clearBrowserLock(self):
        """Clears the pidfile in case the last shutdown was not clean"""
        browserLockPath = os.path.join(self.profileFolder, 'browser.pid')
        try:
            os.remove(browserLockPath)
        except OSError:
            pass


class ServiceMonitor(xbmc.Monitor):
    def __init__(self, service):
        super(ServiceMonitor, self).__init__()
        self.streamingToken = None
        self.service = service
        self.sharedCache = SharedCache()
        self.addon = xbmcaddon.Addon()
        self.channelid = ''
        self.timer = None
        self.session: LoginSession = LoginSession(self.addon)
        self.channels = self.session.get_channels()
        print("SERVICEMONITOR initialized: {0}".format(service))

    def update_token(self):
        print("Refresh token for channel: {0}".format(self.channelid))
        self.session.load_cookies()
        streamingToken = self.session.update_token(self.streamingToken)
        print("UPDATE TOKEN streamtoken:", streamingToken)
        self.streamingToken = streamingToken


    def onNotification(self, sender: str, method: str, data: str) -> None:
        print("SERVICEMONITOR Notification: {0},{1},{2}".format(sender, method, data))
        if sender == self.addon.getAddonInfo("id"):
            params = json.loads(data)
            print("SERVICEMONITOR command and params: {0},{1}".format(params['command'],params['command_params']))
            if params['command'] == 'play_video':
                self.channelid = params['command_params']['uniqueId']
                self.streamingToken = params['command_params']['streamingToken']
                self.timer = threading.Timer(60, self.update_token)
                self.timer.start()
        elif sender == 'xbmc':
            if method == 'Player.OnStop':
                self.timer.cancel()
                self.session.delete_token(self.streamingToken)

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
        self.sharedCache.clear()

if __name__ == '__main__':
    global now_playing
    proxy_service = HttpProxyService()
    proxy_service.set_address(('127.0.0.1', 6969))
    proxy_service.clearBrowserLock()
    monitor_service = ServiceMonitor(proxy_service)
    proxy_service.startHttpServer()
    try:
        while not monitor_service.abortRequested():
            # Sleep/wait for abort for 10 seconds
            if monitor_service.waitForAbort(10):
                # Abort was requested while waiting. We should exit
                print("MONITOR PROXYSERVICE WAITFORABORT timeout")
                monitor_service.cleanup()
                if monitor_service.sharedCache.getprop(G.VIDEO_PLAYING) == 'true':
                    xbmc.Player().stop()
                break
            else:
                if monitor_service.sharedCache.getprop(G.VIDEO_PLAYING) == 'true':
                    print('PROXYSERVICE VIDEO_PLAYING = true')
                    if xbmc.Player().isPlaying():
                        pass
                    else:
                        monitor_service.sharedCache.setprop(G.VIDEO_PLAYING, 'false')
                        print('PROXYSERVICE VIDEO_PLAYING set to false')

    except:
        pass
    print("STOPPING PROXYSERVICE")
    proxy_service.stopHttpServer()
