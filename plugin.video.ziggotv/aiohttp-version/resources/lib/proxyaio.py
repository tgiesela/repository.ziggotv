import threading

import xbmc
import xbmcaddon
from aiohttp import web, ClientSession

from resources.lib.urltools import UrlTools
from resources.lib.webcalls import LoginSession


class ProxyServer:
    def __init__(self, lock):
        self.apprunner = None
        self.lock = lock
        self.thread = None
        self.app: web.Application = None
        self.locator = None
        self.redirected_host = None
        self.original_host = None
        self.locator_path_file = None
        self.locator_path_dir = None
        self.streaming_token = None
        self.addon = xbmcaddon.Addon()
        self.urlTools = UrlTools(self.addon)
        self.session: LoginSession = LoginSession(self.addon)

    async def manifest_handler(self, request: web.Request):
        if 'path' not in request.query or 'hostname' not in request.query or 'token' not in request.query:
            xbmc.log('Unexpected manifest request. Url: {0}'.format(request.url), xbmc.LOGINFO)
            return

        orig_token = request.query['token']
        streaming_token = self.get_streaming_token()
        if streaming_token is None:
            # This can occur at the first call. The notification with the token is not
            # sent immediately
            xbmc.log("Using original token", xbmc.LOGDEBUG)
            self.set_streaming_token(orig_token)
            streaming_token = orig_token

        xbmc.log('manifest_handler(): url: {0}'.format(request.url.human_repr()))
        manifest_url = self.get_manifest_url(request.url.human_repr(), streaming_token)
        xbmc.log('manifest_handler(): manifest_url: {0}'.format(manifest_url))

        async with ClientSession(auto_decompress=False) as session:
            async with session.get(manifest_url, allow_redirects=True) as server_response:
                resp: web.StreamResponse = web.StreamResponse(headers=server_response.headers)
                self.update_redirection(request.url.human_repr(), server_response.url.human_repr())
                await resp.prepare(request)
                proxy_response = web.Response()
                for key in resp.headers:
                    proxy_response.headers[key.upper()] = resp.headers[key]
                resp.set_status(server_response.status)
                while not server_response.content.at_eof():
                    data = await server_response.content.read(8192)
                    await resp.write(data)
            return resp

    async def default_handler(self, request: web.Request):
        url = self.replace_baseurl(request.url.human_repr(), self.streaming_token)
        async with ClientSession() as session:
            async with session.get(url, allow_redirects=True) as server_response:
                resp: web.StreamResponse = web.StreamResponse(headers=server_response.headers)
                await resp.prepare(request)
                resp.set_status(server_response.status)
                try:
                    while not server_response.content.at_eof():
                        data = await server_response.content.read(8192)
                        await resp.write(data)
                    return resp
                except ConnectionResetError:
                    xbmc.log('Connection lost', xbmc.LOGDEBUG)
                    return None

    async def license_handler(self, request: web.Request):
        length = int(request.headers['content-length'])
        received_data = await request.content.read(length)

        content_id = request.query['ContentId']
        with self.lock:
            self.session.load_cookies()
            hdrs = {}
            for key in request.headers:
                hdrs[key] = request.headers[key]
            response = self.session.get_license(content_id, received_data, hdrs)

        proxy_response = web.Response()
        for key in response.headers:
            proxy_response.headers[key.upper()] = response.headers[key]
            if key.lower() == 'x-streaming-token':
                self.streaming_token = response.headers[key]
        await proxy_response.prepare(request)

        proxy_response.set_status(response.status_code)
        xbmc.log("LICENSE RESPONSE RECEIVED: {0}".format(response.content), xbmc.LOGDEBUG)
        await proxy_response.write(response.content)
        return proxy_response

    @staticmethod
    async def shutdown_handler(request: web.Request):
        from aiohttp.web_runner import GracefulExit
        print('SHUTTING DOWN')

        raise GracefulExit()

    def get_manifest_url(self, url: str, streaming_token: str):
        return self.urlTools.get_manifest_url(proxyUrl=url, streamingToken=streaming_token)

    def update_redirection(self, proxy_url, actual_url):
        self.urlTools.update_redirection(proxy_url, actual_url)

    @staticmethod
    def insert_token(url, streaming_token: str):
        return url.replace("/dash", "/dash,vxttoken=" + streaming_token)

    def get_streaming_token(self):
        return self.streaming_token

    def set_streaming_token(self, token):
        with self.lock:
            self.session.streamingToken = token
            self.streaming_token = token
            xbmc.log('Setting streaming token to: {0}'.format(token), xbmc.LOGDEBUG)

    def replace_baseurl(self, url, streaming_token):
        return self.urlTools.replace_baseurl(url, streaming_token)

    def set_locator(self, locator):
        self.locator = locator

    def __start_webserver(self):
        xbmc.log("WEBSERVER STARTED", xbmc.LOGDEBUG)
        self.app = web.Application()
        self.app.add_routes([web.get('/manifest', self.manifest_handler),
                             web.get('/{tail:.*}', self.default_handler),
                             web.post('/license', self.license_handler),
                             web.delete('/shutdown', self.shutdown_handler)])
        port = xbmcaddon.Addon().getSettingNumber('proxy-port')
        ip = xbmcaddon.Addon().getSetting('proxy-ip')
        web.run_app(app=self.app, host=ip, port=int(port))
        xbmc.log("WEBSERVER STOPPED", xbmc.LOGDEBUG)

    def serve_forever(self):
        self.thread = threading.Thread(target=self.__start_webserver)
        self.thread.start()
        print('PROXYSERVER Thread started')

    def shutdown(self):
        self.thread.join()
        xbmc.log("SHUTDOWN COMPLETE", xbmc.LOGDEBUG)


def main():
    #  Not normally called, only during tests
    app = web.Application()
    lock = threading.Lock()
    proxy = ProxyServer(lock)
    proxy.serve_forever()


if __name__ == '__main__':
    main()
