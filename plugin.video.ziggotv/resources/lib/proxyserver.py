from urllib.parse import urlparse, parse_qs, unquote

import typing
import xbmc
import xbmcaddon

from resources.lib.UrlTools import UrlTools
from resources.lib.webcalls import LoginSession

from http.server import BaseHTTPRequestHandler
from http.client import HTTPConnection
from http.client import HTTPSConnection
import http.server
import socketserver


class HTTPRequestHandler(BaseHTTPRequestHandler):

    def __init__(self, request: bytes, client_address: typing.Tuple[str, int], server: socketserver.BaseServer):
        super().__init__(request, client_address, server)

    def log_request(self, code='-', size='-'):
        if code == 200:
            pass
        else:
            xbmc.log('HTTPRequestHandler log_request({0},{1})'.format(code, size), xbmc.LOGERROR)

    def do_GET(self):
        """Handle http get requests, used for manifest and all streaming calls"""
        proxy: ProxyServer = self.server
        proxy.handle_get(self)

    def do_POST(self):
        """Handle http post requests, used for license"""
        proxy: ProxyServer = self.server
        proxy.handle_post(self)


class ProxyServer(http.server.HTTPServer):
    """
        Proxyserver for processing license and manifest request.
        Contains some functions to maintain state because HttpRequestHandler is instantiated
        for every new call
    """

    def __init__(self, addon, server_address, lock):
        http.server.HTTPServer.__init__(self, server_address, HTTPRequestHandler)
        self.lock = lock
        self.addon = addon
        self.session = LoginSession(xbmcaddon.Addon())
        self.urlTools = UrlTools(addon)
        xbmc.log("ProxyServer created", xbmc.LOGINFO)

    def set_streaming_token(self, token):
        with self.lock:
            self.session.streaming_token = token
            xbmc.log('Setting streaming token to: {0}'.format(token), xbmc.LOGDEBUG)

    def get_streaming_token(self):
        with self.lock:
            return self.session.streaming_token

    def get_manifest_url(self, url: str, streaming_token: str):
        return self.urlTools.get_manifest_url(proxy_url=url, streaming_token=streaming_token)

    def update_redirection(self, proxy_url, actual_url):
        self.urlTools.update_redirection(proxy_url, actual_url)

    def replace_baseurl(self, url, streaming_token):
        return self.urlTools.replace_baseurl(url, streaming_token)

    def handle_manifest(self, request):
        parsed_url = urlparse(request.path)
        qs = parse_qs(parsed_url.query)
        if 'path' in qs and 'hostname' in qs and 'token' in qs:
            orig_token = qs['token'][0]
            streaming_token = self.get_streaming_token()
            if streaming_token is None:
                # This can occur at the first call. The notification with the token is not
                # sent immediately
                xbmc.log("Using original token", xbmc.LOGDEBUG)
                self.set_streaming_token(orig_token)
                streaming_token = orig_token
            manifest_url = self.get_manifest_url(request.path, streaming_token)
            with self.lock:
                response = self.session.get_manifest(manifest_url)
            self.update_redirection(request.path, response.url)
            request.send_response(response.status_code)
            request.end_headers()
            request.wfile.write(response.content)

        else:
            request.send_response(404)
            request.end_headers()

    def handle_default(self, request):
        url = self.replace_baseurl(request.path, self.get_streaming_token())
        parsed_dest_url = urlparse(url)
        if parsed_dest_url.scheme == 'https':
            connection = HTTPConnection(parsed_dest_url.hostname, timeout=10)
        else:
            connection = HTTPSConnection(parsed_dest_url.hostname, timeout=10)
        connection.request("GET", parsed_dest_url.path)
        response = connection.getresponse()
        request.send_response(response.status)
        chunked = False
        for header in response.headers:
            if header.lower() == 'transfer-encoding':
                if response.headers[header].lower() == 'chunked':
                    #  We don't know the length upfront
                    chunked = True
            request.send_header(header, response.headers[header])
        request.end_headers()
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
                request.wfile.write(block_to_write)
                response.readline()
                block_length = response.readline()
                length = int(block_length, 16)
            block_to_write = bytearray(block_length)
            block_to_write.extend(b'\r\n')
            request.wfile.write(block_to_write)
        else:
            expected_length = int(response.headers['Content-Length'])
            block = response.read(8192)
            while length_processed < expected_length:
                length_processed += len(block)
                written = request.wfile.write(block)
                if written != len(block):
                    xbmc.log('count-written ({0})<>len(block)({1})'.format(written, len(block)))
                    return
                block = response.read(8192)

    def handle_get(self, request):
        path = request.path  # Path with parameters received from request e.g. "/manifest?id=234324"
        xbmc.log('HTTP GET Request received: {0}'.format(unquote(path)), xbmc.LOGDEBUG)
        try:
            if '/manifest' in path:
                self.handle_manifest(request)
            else:
                self.handle_default(request)

            xbmc.log('HTTP GET Request processed: {0}'.format(unquote(path)), xbmc.LOGDEBUG)
        except ConnectionResetError as exc:
            xbmc.log('Connection reset during processing: {0}'.format(exc), xbmc.LOGERROR)
        except Exception as exc:
            xbmc.log('Exception in do_get(): {0}'.format(exc), xbmc.LOGERROR)
            request.send_response(500)
            request.end_headers()

    def handle_post(self, request):
        path = request.path  # Path with parameters received from request e.g. "/license?id=234324"
        xbmc.log('HTTP POST request received: {0}'.format(unquote(path)), xbmc.LOGDEBUG)
        if '/license' not in path:
            request.send_response(404)
            request.end_headers()
            return
        try:
            length = int(request.headers.get('content-length', 0))
            received_data = request.rfile.read(length)

            parsed_url = urlparse(request.path)
            content_id = parse_qs(parsed_url.query)['ContentId'][0]

            with self.lock:
                self.session.load_cookies()
            hdrs = {}
            for key in request.headers:
                hdrs[key] = request.headers[key]
            with self.lock:
                response = self.session.get_license(content_id, received_data, hdrs)
            for key in response.headers:
                request.headers.add_header(key, response.headers[key])
                if key.lower() == 'x-streaming-token':
                    self.set_streaming_token(response.headers[key])
            request.send_response(response.status_code)
            request.end_headers()
            request.wfile.write(response.content)
            xbmc.log('HTTP POST request processed: {0}'.format(unquote(path)), xbmc.LOGDEBUG)
        except ConnectionResetError as exc:
            xbmc.log('Connection reset during processing: {0}'.format(exc), xbmc.LOGERROR)
        except Exception as exc:
            xbmc.log('Exception in do_post(): {0}'.format(exc), xbmc.LOGERROR)
            request.send_response(500)
            request.end_headers()
