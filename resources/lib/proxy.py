import socket
import threading

import xbmc
import xbmcaddon
from aiohttp import web, ClientSession
from urllib.parse import urlparse
from resources.lib.webcalls import LoginSession


class TCPServer:
    def __init__(self, host='127.0.0.1', port=8888):
        self.host = host
        self.port = port

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(5)

        print("Listening at", s.getsockname())

        while True:
            conn, addr = s.accept()
            print("Connected by", addr)
            data = conn.recv(1024)

            response = self.handle_request(data)
            conn.sendall(response)
            conn.close()

    def handle_request(self, data):
        """Handles incoming data and returns a response.
        Override this in subclass.
        """
        return data


class ProxyServer:
    def __init__(self):
        self.thread = None
        self.app = None
        self.locator = None
        self.redirected_host = None
        self.original_host = None
        self.locator_path_file = None
        self.locator_path_dir = None
        self.streaming_token = None
        self.session: LoginSession = LoginSession(xbmcaddon.Addon())

    async def manifest_handler(self, request: web.Request):
        print('MANIFESTHANDLER')
        streaming_token = self.streaming_token
        if 'path' not in request.query:
            xbmc.log('Unexpected manifest request. Url: {0}'.format(request.url), xbmc.LOGINFO)
            return

        orig_path = request.query['path']
        orig_hostname = request.query['hostname']
        orig_token = request.query['token']
        if streaming_token is None:
            # This can occur at the first call. The notification with the token is not
            # sent immediately
            xbmc.log("Using original token", xbmc.LOGDEBUG)
            self.streaming_token = orig_token
            self.session.streaming_token = orig_token
            streaming_token = orig_token

        url = self.get_manifest_url(orig_hostname, orig_path, streaming_token)
        print("ManifestURL {0}".format(url))
        async with ClientSession() as session:
            async with session.get(url, allow_redirects=True) as server_response:
                resp: web.StreamResponse = web.StreamResponse(headers=server_response.headers)
                self.update_redirection(server_response.url.human_repr())
                await resp.prepare(request)
                while not server_response.content.at_eof():
                    data = await server_response.content.read(8192)
                    await resp.write(data)
            return resp

    async def default_handler(self, request: web.Request):
        print('DEFAULTHANDLER')
        # baseurl = proxy.get_baseurl(response.url, streaming_token)
        baseurl = self.get_baseurl(request.url.scheme, self.streaming_token)
        xbmc.log("BaseURL: {0}".format(baseurl), xbmc.LOGDEBUG)

        url = baseurl + request.path
        async with ClientSession() as session:
            async with session.get(url, allow_redirects=True) as server_response:
                resp: web.StreamResponse = web.StreamResponse(headers=server_response.headers)
                self.update_redirection(server_response.url.human_repr())
                await resp.prepare(request)
                while not server_response.content.at_eof():
                    data = await server_response.content.read(8192)
                    await resp.write(data)
            return resp

    def get_baseurl(self, scheme: str, streaming_token: str) -> str:
        """
        This method replaces the proxy-url with the (redirected) host url
        :param scheme: from the proxy url
        :param streaming_token: token to be inserted in the resulting url
        :return:
        """
        host_and_path = self.redirected_host + self.locator_path_dir
        new_url = host_and_path
        return scheme + '://' + self.insert_token(new_url, streaming_token) + '/'

    async def license_handler(self, request: web.Request):
        length = int(request.headers['content-length'])
        received_data = await request.content.read(length)

        content_id = request.query['ContentId']
        self.session.load_cookies()
        headers = {}
        for key in request.headers:
            headers[key] = request.headers[key]
        response = self.session.get_license(content_id, received_data, headers)

        proxy_response = web.Response()
        for key in response.headers:
            proxy_response.headers[key.upper()] = response.headers[key]
            if key.lower() == 'x-streaming-token':
                self.streaming_token = response.headers[key]
        await proxy_response.prepare(request)

        proxy_response.set_status(response.status_code)
        print("LICENSE RESPONSE RECEIVED: ", response.content)
        await proxy_response.write(response.content)
        xbmc.log('HTTP POST request processed: {0}'.format(request.url), xbmc.LOGDEBUG)
        return proxy_response

    def get_manifest_url(self, hostname: str, orig_path: str, streaming_token: str):
        self.locator_path_dir = orig_path.rsplit('/', 1)[0]
        self.locator_path_file = orig_path.rsplit('/', 1)[1]
        if hostname == self.original_host:  # we received a request for this host before
            if self.redirected_host is None:  # we did not yet detect a redirect
                self.original_host = hostname  # continue with the host from the params
                hostname_to_use = hostname
            else:
                hostname_to_use = self.redirected_host  # we detected a redirect before and use the redirected host
        else:
            self.original_host = hostname
            self.redirected_host = None  # Different original host, reset redirect host
            hostname_to_use = hostname
        url = 'https://' + hostname_to_use + self.locator_path_dir + '/' + self.locator_path_file
        return self.insert_token(url, streaming_token)

    def update_redirection(self, url):
        """
        Extract the hostname and path from the url before '/dash, vxttoken'. This part will
        change during the redirection. The result is stored in self.redirected_host.
        :param url:
        :return: nothing
        """
        o = urlparse(url)
        host_and_path = o.hostname + o.path[0:o.path.find('/dash,vxttoken=')]
        self.redirected_host = host_and_path

    @staticmethod
    def insert_token(url, streaming_token: str):
        return url.replace("/dash", "/dash,vxttoken=" + streaming_token)

    def get_streaming_token(self):
        return self.streaming_token

    def set_streaming_token(self, streaming_token):
        self.streaming_token = streaming_token
        self.session.streaming_token = streaming_token

    def set_locator(self, locator):
        self.locator = locator

    def __start_webserver(self):
        self.app = web.Application()
        self.app.add_routes([web.get('/manifest', self.manifest_handler),
                             web.get('/{tail:.*}', self.default_handler),
                             web.post('/license', self.license_handler)])
        web.run_app(app=self.app, host='127.0.0.1', port=6969)
        xbmc.log("WEBSERVER STARTED", xbmc.LOGDEBUG)

    def serve_forever(self):
        self.thread = threading.Thread(target=self.__start_webserver)
        self.thread.start()

    def shutdown(self):
        self.thread.join()
        xbmc.log("SHUTDOWN COMPLETE", xbmc.LOGDEBUG)


def main():
    #  Not normally called, only during tests
    app = web.Application()
    proxy = ProxyServer()
    proxy.serve_forever()


if __name__ == '__main__':
    main()
