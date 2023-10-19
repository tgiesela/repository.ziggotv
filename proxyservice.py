import base64
import json
import os
import socketserver
import sys
import threading
import http.server
import time
import typing
from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer
from urllib.parse import urlparse, parse_qs, unquote

import requests

from resources.lib.globals import G
from resources.lib.utils import Timer
from resources.lib.webcalls import LoginSession

import xbmc
import xbmcaddon
import xbmcvfs


class HTTPRequestHandler(BaseHTTPRequestHandler):

    def __init__(self, request: bytes, client_address: typing.Tuple[str, int], server: socketserver.BaseServer):
        super().__init__(request, client_address, server)
        print("HTTPRequestHandler created")

    def do_GET(self):
        """Handle http get requests, used for manifest and all streaming calls"""
        # if REMOTE_DEBUG:
        #     pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
        path = self.path  # Path with parameters received from request e.g. "/manifest?id=234324"
        print('HTTP GET Request received: {0}'.format(unquote(path)))
        proxy: ProxyServer = self.server
        print("ORIG: {0}, REDIR: {1}".format(proxy.originalhost, proxy.redirectedhost))
        try:
            received_data_length = int(self.headers.get('content-length', 0))
            received_data = self.rfile.read(received_data_length)
            streaming_token = proxy.get_streaming_token()
            parsed_url = urlparse(self.path)
            qs = parse_qs(parsed_url.query)
            if 'path' in qs:
                orig_path = qs['path'][0]
                orig_hostname = qs['hostname'][0]
                orig_token = qs['token'][0]
                if streaming_token is None:
                    # This can occur at the first call. The notification with the token is not
                    # sent immediately
                    print("Using original token")
                    proxy.set_streaming_token(orig_token)
                    streaming_token = orig_token
                manifest_url = proxy.get_manifest_url(orig_hostname, orig_path, streaming_token)
                print("ManifestURL: {0}".format(manifest_url))
                with proxy.lock:
                    response = proxy.session.get_manifest(manifest_url)
                proxy.update_redirection(response.url)
            else:
                # baseurl = proxy.get_baseurl(response.url, streaming_token)
                baseurl = proxy.get_baseurl(proxy.locator, streaming_token)
                print("BaseURL: {0}".format(baseurl))
                response = requests.get(baseurl + parsed_url.path)

            self.send_response(response.status_code)
            self.end_headers()
            self.wfile.write(response.content)
            print('HTTP GET Request processed: {0}'.format(unquote(path)))
        except Exception as exc:
            xbmc.log('Exception in do_get(): {0}'.format(exc), xbmc.LOGERROR)
            self.send_response(500)
            self.end_headers()

    def do_GET_partial(self):
        """Handle http get requests, used for manifest only. Currently not used due to kodi crashes """
        # if REMOTE_DEBUG:
        #     pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
        path = self.path  # Path with parameters received from request e.g. "/manifest?id=234324"
        print('HTTP GET Request received: {0}'.format(unquote(path)))
        proxy: ProxyServer = self.server
        print("ORIG: {0}, REDIR: {1}".format(proxy.originalhost, proxy.redirectedhost))
        if '/manifest' not in path:
            self.send_response(404)
            self.end_headers()
            return
        try:
            # IMPORTANT NOTE!!!
            # The x-streaming-token needs to be refreshed/updated every 60 seconds.
            # If the vxttoken needs to be updated also, we have to use the proxy to update the
            # manifest.mpd with the BaseURL. This is attempted in this function.
            # However, ISA does niet seem to update the BaseURL after the first manifest.mpd, so this does
            # not work.
            # A bit of research showed that ISA sets up a new connection. Redirection gives a different url and
            # the streaming-token contains a session-id, which is probably not the same for the new connection.
            # My assumption is that this is why the streaming only works for the first few seconds before kodi
            # stops or crashes.
            received_data_length = int(self.headers.get('content-length', 0))
            received_data = self.rfile.read(received_data_length)
            streaming_token = proxy.get_streaming_token()
            parsed_url = urlparse(self.path)
            orig_path = parse_qs(parsed_url.query)['path'][0]
            orig_hostname = parse_qs(parsed_url.query)['hostname'][0]
            orig_token = parse_qs(parsed_url.query)['token'][0]
            if streaming_token is None:
                # This can occur at the first call. The notification with the token is not
                # sent immediately
                print("Using original token")
                proxy.set_streaming_token(orig_token)
                streaming_token = orig_token

            manifest_url = proxy.get_manifest_url(orig_hostname, orig_path, streaming_token)
            print("ManifestURL: {0}".format(manifest_url))
            with proxy.lock:
                response = proxy.session.get_manifest(manifest_url)
            proxy.update_redirection(response.url)
            baseurl = proxy.get_baseurl_orig(manifest_url, streaming_token)
            print("BaseURL: {0}".format(baseurl))
            mpd = str(response.content, 'utf-8')
            mpd = mpd.replace('><Period', '>' + '<BaseURL>' + baseurl + '</BaseURL><Period')

            self.send_response(response.status_code)
            for key in response.headers:
                if key.lower() == 'content-length':
                    self.send_header('content-length', str(len(mpd)))
                self.send_header(key, response.headers[key])
            self.end_headers()
            self.wfile.write(bytes(mpd, 'utf-8'))
            print('HTTP GET Request processed: {0}'.format(unquote(path)))
        except Exception as exc:
            xbmc.log('Exception in do_get(): {0}'.format(exc), xbmc.LOGERROR)
            self.send_response(500)
            self.end_headers()

    def do_POST(self):
        """Handle http post requests, used for license"""
        path = self.path  # Path with parameters received from request e.g. "/license?id=234324"
        print('HTTP POST request received: {0}'.format(unquote(path)))
        if '/license' not in path:
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get('content-length', 0))
            received_data = self.rfile.read(length)

            parsed_url = urlparse(self.path)
            content_id = parse_qs(parsed_url.query)['ContentId'][0]

            proxy: ProxyServer = self.server
            with proxy.lock:
                proxy.session.load_cookies()
            hdrs = {}
            for key in self.headers:
                hdrs[key] = self.headers[key]
            with proxy.lock:
                response = proxy.session.get_license(content_id, received_data, hdrs)
            for key in response.headers:
                self.headers.add_header(key, response.headers[key])
                if key.lower() == 'x-streaming-token':
                    proxy.set_streaming_token(response.headers[key])
            self.send_response(response.status_code)
            self.end_headers()
            self.wfile.write(response.content)
            print('HTTP POST request processed: {0}'.format(unquote(path)))
        except Exception as exc:
            xbmc.log('Exception in do_post(): {0}'.format(exc), xbmc.LOGERROR)
            self.send_response(500)
            self.end_headers()


class ProxyServer(http.server.HTTPServer):
    """
        Proxyserver for processing license and manifest request.
        Contains some functions to maintain state because HttpRequestHandler is instantiated
        for every new call
    """

    def __init__(self, addon, server_address, lock):
        http.server.HTTPServer.__init__(self, server_address, HTTPRequestHandler)
        self.locator_path_file = None
        self.locator_path_dir = None
        self.locator = None
        self.lock = lock
        self.redirectedhost = None
        self.originalhost = None
        self.addon = addon
        self.session = LoginSession(xbmcaddon.Addon())
        print("ProxyServer created")

    def set_streaming_token(self, token):
        with lock:
            self.session.streaming_token = token
            print('Setting streaming token to: ', token)

    def get_streaming_token(self):
        with lock:
            return self.session.streaming_token

    def get_manifest_url(self, hostname: str, orig_path: str, streaming_token: str):
        self.locator_path_dir = orig_path.rsplit('/', 1)[0]
        self.locator_path_file = orig_path.rsplit('/', 1)[1]
        if hostname == self.originalhost:     # we received a request for this host before
            if self.redirectedhost is None:   # we did not yet detect a redirect
                self.originalhost = hostname  # continue with the host from the params
                hostname_to_use = hostname
            else:
                hostname_to_use = self.redirectedhost  # we detected a redirect before and use the redirected host
        else:
            self.originalhost = hostname
            self.redirectedhost = None  # Different original host, reset redirect host
            hostname_to_use = hostname
        url = 'https://' + hostname_to_use + self.locator_path_dir + '/' + self.locator_path_file
        return self.insert_token(url, streaming_token)

    def update_redirection(self, url):
        o = urlparse(url)
        host_and_path = o.hostname + o.path[0:o.path.find('/dash,vxttoken=')]
        self.redirectedhost = host_and_path

    def get_baseurl_orig(self, url, streaming_token):
        #  Here we build the url which has to be set in the manifest as <BaseURL>
        #  We use the original locator and replace the part before /dash with
        #  the new host_and_path
        #  Finally we insert the vxttoken
        path_dir = url.rsplit('/', 1)[0]
        path_file = url.rsplit('/', 1)[1]
        o = urlparse(url)
        host_and_path = path_dir
        new_url = host_and_path
        return o.scheme + '://' + self.insert_token(new_url, streaming_token) + '/'

    def get_baseurl(self, url, streaming_token):
        #  Here we build the url which has to be set in the manifest as <BaseURL>
        #  We use the original locator and replace the part before /dash with
        #  the new host_and_path
        #  Finally we insert the vxttoken
        o = urlparse(url)
        host_and_path = self.redirectedhost + self.locator_path_dir
        new_url = host_and_path
        return o.scheme + '://' + self.insert_token(new_url, streaming_token) + '/'

    def set_locator(self, locator):
        self.locator = locator

    def insert_token(self, url, streaming_token:str):
        return url.replace("/dash", "/dash,vxttoken=" + streaming_token)


class HttpProxyService:
    def __init__(self, svc_lock):
        print("Proxy service initializing")
        self.lock = svc_lock
        self.profileFolder = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
        self.address = ''
        self.port = 80
        self.isShutDown = True
        self.HTTPServerThread = None
        self.ProxyServer = None  # started by me
        self.settingsChangeLock = threading.Lock()
        print("Proxy service initialized")

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
        # self.HTTPServerThread.start()
        self.isShutDown = False
        self.stopHttpServer()
        try:
            self.ProxyServer = ProxyServer(self, (self.address, self.port), self.lock)
        except IOError as e:
            pass

        thread = threading.Thread(target=self.ProxyServer.serve_forever)
        thread.start()
        self.HTTPServerThread = thread
        print("ProxyService started listening on {0}-{1}".format(self.address,
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
    def __init__(self, service: HttpProxyService, svc_lock):
        super(ServiceMonitor, self).__init__()
        self.locator = None
        self.lock = svc_lock
        self.service: HttpProxyService = service
        self.addon = xbmcaddon.Addon()
        self.channelid = ''
        self.timer = None
        print("SERVICEMONITOR initialized: {0}".format(service))

    def update_token(self):
        if self.service.ProxyServer is None:
            print('SERVICEMONITOR ProxyServer not started yet')
            return
        session = LoginSession(self.addon)
        session.load_cookies()
        proxy: ProxyServer = self.service.ProxyServer
        print("Refresh token for channel: {0}".format(self.channelid))
        streaming_token = session.update_token(proxy.get_streaming_token())
        proxy.set_streaming_token(streaming_token)

    def onNotification(self, sender: str, method: str, data: str) -> None:
        if self.service.ProxyServer is None:
            print('SERVICEMONITOR ProxyServer not started yet')
            return
        # session = self.service.ProxyServer.session
        proxy: ProxyServer = self.service.ProxyServer
        print("SERVICEMONITOR Notification: {0},{1},{2}".format(sender, method, data))
        if sender == self.addon.getAddonInfo("id"):
            params = json.loads(data)
            print("SERVICEMONITOR command and params: {0},{1}".format(params['command'], params['command_params']))
            if params['command'] == 'play_video':
                self.channelid = params['command_params']['uniqueId']
                self.locator = params['command_params']['locator']
                streaming_token = params['command_params']['streamingToken']
                proxy.set_streaming_token(streaming_token)
                proxy.set_locator(self.locator)
                self.timer = Timer(60, self.update_token)
                self.timer.start()
        elif sender == 'xbmc':
            if method == 'Player.OnStop':
                self.timer.stop()
                session = LoginSession(self.addon)
                session.load_cookies()
                session.delete_token(proxy.get_streaming_token())

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


REMOTE_DEBUG = False
if __name__ == '__main__':
    # if REMOTE_DEBUG:
    #     try:
    #         sys.path.append('E:\Eclipse IDE\eclipse\plugins\org.python.pydev.core_10.2.1.202307021217\pysrc')
    #         import pydevd
    #     except:
    #         sys.stderr.write("Error: " + "You must add org.python.pydev.debug.pysrc to your PYTHONPATH")
    #         sys.stderr.write("Error: " + "Debug not available")
    # else:
    #     import web_pdb
    #     web_pdb.set_trace()
    lock = threading.Lock()
    proxy_service = HttpProxyService(lock)
    proxy_service.set_address(('127.0.0.1', 6969))
    proxy_service.clearBrowserLock()
    monitor_service = ServiceMonitor(proxy_service, lock)
    proxy_service.startHttpServer()
    try:
        while not monitor_service.abortRequested():
            # Sleep/wait for abort for 10 seconds
            if monitor_service.waitForAbort(10):
                # Abort was requested while waiting. We should exit
                print("MONITOR PROXYSERVICE WAITFORABORT timeout")
                monitor_service.cleanup()
                break

    except:
        pass
    print("STOPPING PROXYSERVICE")
    proxy_service.stopHttpServer()
