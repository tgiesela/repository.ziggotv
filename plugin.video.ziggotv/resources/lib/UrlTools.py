from collections import namedtuple
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode, unquote

import xbmc
import xbmcaddon


class UrlTools:
    def __init__(self, addon: xbmcaddon.Addon):
        self.base_url = None
        self.redirected_url = None
        self.proxy_url = None
        self.addon = addon

    def build_url(self, streaming_token, locator) -> str:
        use_proxy = self.addon.getSettingBool('use-proxy')
        if use_proxy:
            xbmc.log('Using proxy server', xbmc.LOGINFO)
            o = urlparse(locator)
            Components = namedtuple(
                typename='Components',
                field_names=['scheme', 'netloc', 'path', 'url', 'query', 'fragment']
            )

            query_params = {
                'path': o.path,
                'token': streaming_token,
                'hostname': o.hostname,
            }
            orig_params = parse_qs(o.query)
            for param in orig_params:
                query_params.update({param: orig_params[param][0]})

            port = self.addon.getSetting('proxy-port')
            ip = self.addon.getSetting('proxy-ip')
            url = urlunparse(
                Components(
                    scheme='http',
                    netloc='{0}:{1}'.format(ip, port),
                    query=urlencode(query_params),
                    path='manifest',
                    url='',
                    fragment=''
                )
            )
            xbmc.log('BUILD URL: {0}'.format(url), xbmc.LOGDEBUG)
            return url
        else:
            if '/dash' in locator:
                return locator.replace("/dash", "/dash,vxttoken=" + streaming_token).replace("http://", "https://")
            elif 'sdash' in locator:
                return locator.replace("/sdash", "/sdash,vxttoken=" + streaming_token).replace("http://", "https://")
            elif '/live' in locator:
                return locator.replace("/live", "/live,vxttoken=" + streaming_token).replace("http://", "https://")
            else:
                return locator

    @staticmethod
    def __insert_token(url, streaming_token: str):
        if '/dash' in url:
            return url.replace("/dash", "/dash,vxttoken=" + streaming_token)
        elif '/sdash' in url:
            return url.replace("/sdash", "/sdash,vxttoken=" + streaming_token)
        elif '/live' in url:
            return url.replace("/live", "/live,vxttoken=" + streaming_token)
        else:
            xbmc.log('token not inserted in url: {0}'.format(url))
            return url

    def update_redirection(self, proxy_url: str, actual_url: str, baseURL: str = None):
        """
        Results in setting:
            self.redirected_url to be used for manifests
            self.base_url to be used for video/audio requests

        @param proxy_url:  URL send to the proxy
        @param actual_url: URL after redirection
        @param baseURL: extracted from the manifest.mpd file
        @return:
        """
        if self.proxy_url != proxy_url:
            self.proxy_url = proxy_url
            self.base_url = None

        s = actual_url.find(',vxttoken=')
        e = actual_url.find('/', s)
        actual_url = actual_url[0:s] + actual_url[e:]

        o = urlparse(actual_url)
        if baseURL is not None:
            if baseURL.startswith('../'):  # it is a baseURL which strips some levels of the original url
                levels = o.path.split('/')
                levels.pop(len(levels)-1)  # Always remove last level, because it contains a filename (manifest.mpd)
                cntToRemove = baseURL.count('../')
                for i in range(cntToRemove):
                    levels.pop(len(levels)-1)
                # Reconstruct the actual_url to be used as baseUrl
                path = '/'.join(levels)
                Components = namedtuple(
                    typename='Components',
                    field_names=['scheme', 'netloc', 'path', 'url', 'query', 'fragment']
                )
                updated_url = urlunparse(
                    Components(
                        scheme=o.scheme,
                        netloc=o.netloc,
                        path=path + '/',
                        url='',
                        query='',
                        fragment=''
                    )
                )
                self.base_url = updated_url
            else:
                self.base_url = baseURL
        else:
            self.base_url = actual_url

        self.redirected_url = actual_url

    def get_manifest_url(self, proxy_url: str, streaming_token: str):
        """
        Function to create the manifest URL to the real host

        :param proxy_url: URL received by the proxy to obtain the manifest
        :param streaming_token: token to be inserted into the manifest request URL
        :return: URL to the real host to be used to obtain the manifest
        """
        if proxy_url != self.proxy_url:
            self.proxy_url = proxy_url
            self.redirected_url = None
        parsed_url = urlparse(proxy_url)
        orig_path = unquote(parse_qs(parsed_url.query)['path'][0])
        orig_hostname = unquote(parse_qs(parsed_url.query)['hostname'][0])
        initial_token = unquote(parse_qs(parsed_url.query)['token'][0])
        if streaming_token is not None:
            initial_token = streaming_token

        if self.redirected_url is not None:
            #  We can simply use the redirected URL, because it remains unchanged
            return self.__insert_token(self.redirected_url, initial_token)
        else:
            Components = namedtuple(
                typename='Components',
                field_names=['scheme', 'netloc', 'path', 'url', 'query', 'fragment']
            )
            query_params = {}
            skip_params = ['hostname', 'path', 'token']
            orig_params = parse_qs(parsed_url.query)
            for param in orig_params:
                if param not in skip_params:
                    query_params.update({param: orig_params[param][0]})

            url = urlunparse(
                Components(
                    scheme='https',
                    netloc=orig_hostname,
                    query=urlencode(query_params),
                    path=orig_path,
                    url='',
                    fragment=''
                )
            )
            return self.__insert_token(url, initial_token)

    def replace_baseurl(self, url, streaming_token):
        """
        The url is updated with the name of the redirected host, if a token is still present, it will be
        removed.
        @param url:
        @param streaming_token:
        @return:
        """
        xbmc.log('REPLACE BASEURL {0}'.format(url), xbmc.LOGDEBUG)
        o = urlparse(url)
        redir = urlparse(self.base_url)
        actual_path = redir.path
        s = actual_path.find(',vxttoken=')
        e = actual_path.find('/', s)
        if s > 0 and e > 0:
            actual_path = actual_path[0:s] + actual_path[e:]
        path_dir = actual_path.rsplit('/', 1)[0]
        host_and_path = redir.hostname + path_dir + o.path
        xbmc.log('REPLACE BASEURL RESULT {0}'.format(redir.scheme + '://' + self.__insert_token(host_and_path, streaming_token)), xbmc.LOGDEBUG)
        return redir.scheme + '://' + self.__insert_token(host_and_path, streaming_token)
