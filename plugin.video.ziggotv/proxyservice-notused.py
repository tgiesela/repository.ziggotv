import json
import os
import socketserver
import threading
import http.server
import typing
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

import http.client

from resources.lib.UrlTools import UrlTools
from resources.lib.utils import Timer
from resources.lib.webcalls import LoginSession

import xbmc
import xbmcaddon
import xbmcvfs


class HTTPRequestHandler(BaseHTTPRequestHandler):

    def __init__(self, request: bytes, client_address: typing.Tuple[str, int], server: socketserver.BaseServer):
        super().__init__(request, client_address, server)

    def handle_manifest(self):
        proxy: ProxyServer = self.server
        parsed_url = urlparse(self.path)
        qs = parse_qs(parsed_url.query)
        if 'path' in qs and 'hostname' in qs and 'token' in qs:
            orig_token = qs['token'][0]
            streaming_token = proxy.get_streaming_token()
            if streaming_token is None:
                # This can occur at the first call. The notification with the token is not
                # sent immediately
                xbmc.log("Using original token", xbmc.LOGDEBUG)
                proxy.set_streaming_token(orig_token)
                streaming_token = orig_token
            manifest_url = proxy.get_manifest_url(self.path, streaming_token)
            with proxy.lock:
                response = proxy.session.get_manifest(manifest_url)
            proxy.update_redirection(self.path, response.url)
            self.send_response(response.status_code)
            self.end_headers()
            self.wfile.write(response.content)

        else:
            self.send_response(404)
            self.end_headers()

    def handle_default(self):
        proxy: ProxyServer = self.server
        url = proxy.replace_baseurl(self.path, proxy.get_streaming_token())
        parsed_dest_url = urlparse(url)
        if parsed_dest_url.scheme == 'https':
            connection = http.client.HTTPConnection(parsed_dest_url.hostname, timeout=10)
        else:
            connection = http.client.HTTPSConnection(parsed_dest_url.hostname, timeout=10)
        connection.request("GET", parsed_dest_url.path)
        response = connection.getresponse()
        self.send_response(response.status)
        chunked = False
        for header in response.headers:
            if header.lower() == 'transfer-encoding':
                if response.headers[header].lower() == 'chunked':
                    #  We don't know the length upfront
                    chunked = True
            self.send_header(header, response.headers[header])
        self.end_headers()
        length_processed = 0
        if chunked:  # process the same chunks as received
            response.chunked = False
            block_length = response.readline()
            length = int(block_length, 16)
            while length > 0:
                length_processed += length
                block = response.read(length)
                block_to_write = bytearray(block_length)
                block_to_write.extend(block + b'\r\n')
                self.wfile.write(block_to_write)
                response.readline()
                block_length = response.readline()
                length = int(block_length, 16)
            block_to_write = bytearray(block_length)
            block_to_write.extend(b'\r\n')
            self.wfile.write(block_to_write)
        else:
            expected_length = int(response.headers['Content-Length'])
            block = response.read(8192)
            while length_processed < expected_length:
                length_processed += len(block)
                written = self.wfile.write(block)
                if written != len(block):
                    xbmc.log('count-written ({0})<>len(block)({1})'.format(written, len(block)))
                    return
                block = response.read(8192)

    def do_GET(self):
        """Handle http get requests, used for manifest and all streaming calls"""
        # if REMOTE_DEBUG:
        #     pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
        path = self.path  # Path with parameters received from request e.g. "/manifest?id=234324"
        xbmc.log('HTTP GET Request received: {0}'.format(unquote(path)), xbmc.LOGDEBUG)
        try:
            if '/manifest' in path:
                self.handle_manifest()
            else:
                self.handle_default()

            xbmc.log('HTTP GET Request processed: {0}'.format(unquote(path)), xbmc.LOGDEBUG)
        except Exception as exc:
            xbmc.log('Exception in do_get(): {0}'.format(exc), xbmc.LOGERROR)
            self.send_response(500)
            self.end_headers()

    def do_POST(self):
        """Handle http post requests, used for license"""
        path = self.path  # Path with parameters received from request e.g. "/license?id=234324"
        xbmc.log('HTTP POST request received: {0}'.format(unquote(path)), xbmc.LOGDEBUG)
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
            xbmc.log('HTTP POST request processed: {0}'.format(unquote(path)), xbmc.LOGDEBUG)
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
        self.locator = None
        self.lock = lock
        self.addon = addon
        self.session = LoginSession(xbmcaddon.Addon())
        self.urlTools = UrlTools(addon)
        xbmc.log("ProxyServer created", xbmc.LOGINFO)

    def set_streaming_token(self, token):
        with lock:
            self.session.streaming_token = token
            xbmc.log('Setting streaming token to: {0}'.format(token), xbmc.LOGDEBUG)

    def get_streaming_token(self):
        with lock:
            return self.session.streaming_token

    def get_manifest_url(self, url: str, streaming_token: str):
        return self.urlTools.get_manifest_url(proxy_url=url, streaming_token=streaming_token)

    def update_redirection(self, proxy_url, actual_url):
        self.urlTools.update_redirection(proxy_url, actual_url)

    def replace_baseurl(self, url, streaming_token):
        return self.urlTools.replace_baseurl(url, streaming_token)

    def set_locator(self, locator):
        self.locator = locator


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
        self.locator = None
        self.lock = svc_lock
        self.service: HttpProxyService = service
        self.addon = xbmcaddon.Addon()
        self.channelid = ''
        self.timer = None
        xbmc.log("SERVICEMONITOR initialized: {0}".format(service), xbmc.LOGINFO)

    def update_token(self):
        if self.service.ProxyServer is None:
            xbmc.log('SERVICEMONITOR ProxyServer not started yet', xbmc.LOGDEBUG)
            return
        session = LoginSession(self.addon)
        session.load_cookies()
        proxy: ProxyServer = self.service.ProxyServer
        xbmc.log("Refresh token interval expired", xbmc.LOGDEBUG)
        token = proxy.get_streaming_token()
        if token is None or token == '':
            return
        streaming_token = session.update_token(proxy.get_streaming_token())
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
                self.channelid = params['command_params']['uniqueId']
                self.locator = params['command_params']['locator']
                streaming_token = params['command_params']['streamingToken']
                proxy.set_streaming_token(streaming_token)
                proxy.set_locator(self.locator)
                self.timer = Timer(60, self.update_token)
                self.timer.start()
        elif sender == 'xbmc':
            if method == 'Player.OnStop':
                if self.timer is not None:
                    self.timer.stop()
                session = LoginSession(self.addon)
                xbmc.log("Delete token after OnStop", xbmc.LOGDEBUG)
                session.load_cookies()
                session.delete_token(proxy.get_streaming_token())
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

    def cleanup(self):
        pass


REMOTE_DEBUG = False
if __name__ == '__main__':
    # if REMOTE_DEBUG:
    #     try:
    #         sys.path.append('E:\Eclipse IDE\eclipse\plugins\org.python.pydev.core_10.2.1.202307021217\pysrc')
    #         import pydevd
    #         pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
    #     except:
    #         sys.stderr.write("Error: " + "You must add org.python.pydev.debug.pysrc to your PYTHONPATH")
    #         sys.stderr.write("Error: " + "Debug not available")
    # else:
    #     import web_pdb
    #     web_pdb.set_trace()
    lock = threading.Lock()
    proxy_service = HttpProxyService(lock)
    port = xbmcaddon.Addon().getSettingNumber('proxy-port')
    ip = xbmcaddon.Addon().getSetting('proxy-ip')
    proxy_service.set_address((ip, port))
    proxy_service.clearBrowserLock()
    monitor_service = ServiceMonitor(proxy_service, lock)
    proxy_service.startHttpServer()
    try:
        while not monitor_service.abortRequested():
            # Sleep/wait for abort for 10 seconds
            if monitor_service.waitForAbort(10):
                # Abort was requested while waiting. We should exit
                xbmc.log("MONITOR PROXYSERVICE WAITFORABORT timeout", xbmc.LOGINFO)
                break

    except:
        pass
    xbmc.log("STOPPING PROXYSERVICE", xbmc.LOGINFO)
    proxy_service.stopHttpServer()
