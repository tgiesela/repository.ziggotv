"""
Module with a collection of url functions
"""
from collections import namedtuple
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode, unquote

import xbmc
import xbmcaddon


class UrlTools:
    """
    class implementing all kind of functions to manipulate the urls
    """
    def __init__(self, addon: xbmcaddon.Addon):
        self.baseUrl = None
        self.redirectedUrl = None
        self.proxyUrl = None
        self.addon = addon

    def build_url(self, streamingToken, locator) -> str:
        """
        function to build an url to pass to ISA
        @param streamingToken:
        @param locator:
        @return:
        """
        useProxy = self.addon.getSettingBool('use-proxy')
        if useProxy:
            xbmc.log('Using proxy server', xbmc.LOGINFO)
            o = urlparse(locator)
            Components = namedtuple(
                typename='Components',
                field_names=['scheme', 'netloc', 'path', 'url', 'query', 'fragment']
            )

            queryParams = {
                'path': o.path,
                'token': streamingToken,
                'hostname': o.hostname,
            }
            origParams = parse_qs(o.query)
            for param, value in origParams.items():
                queryParams.update({param: value[0]})
            port = self.addon.getSetting('proxy-port')
            ip = self.addon.getSetting('proxy-ip')
            url = urlunparse(
                Components(
                    scheme='http',
                    netloc='{0}:{1}'.format(ip, port),
                    query=urlencode(queryParams),
                    path='manifest',
                    url='',
                    fragment=''
                )
            )
            xbmc.log('BUILD URL: {0}'.format(url), xbmc.LOGDEBUG)
            return url
        if '/dash' in locator:
            return locator.replace("/dash", "/dash,vxttoken=" + streamingToken).replace("http://", "https://")
        if '/sdash' in locator:
            return locator.replace("/sdash", "/sdash,vxttoken=" + streamingToken).replace("http://", "https://")
        if '/live' in locator:
            return locator.replace("/live", "/live,vxttoken=" + streamingToken).replace("http://", "https://")
        return locator

    @staticmethod
    def __insert_token(url, streamingToken: str):
        if '/dash' in url:
            return url.replace("/dash", "/dash,vxttoken=" + streamingToken)
        if '/sdash' in url:
            return url.replace("/sdash", "/sdash,vxttoken=" + streamingToken)
        if '/live' in url:
            return url.replace("/live", "/live,vxttoken=" + streamingToken)
        xbmc.log('token not inserted in url: {0}'.format(url))
        return url

    def update_redirection(self, proxyUrl: str, actualUrl: str, baseURL: str = None):
        """
        Results in setting:
            self.redirected_url to be used for manifests
            self.base_url to be used for video/audio requests

        @param proxyUrl:  URL send to the proxy
        @param actualUrl: URL after redirection
        @param baseURL: extracted from the manifest.mpd file
        @return:
        """
        if self.proxyUrl != proxyUrl:
            self.proxyUrl = proxyUrl
            self.baseUrl = None

        s = actualUrl.find(',vxttoken=')
        e = actualUrl.find('/', s)
        actualUrl = actualUrl[0:s] + actualUrl[e:]

        o = urlparse(actualUrl)
        if baseURL is not None:
            if baseURL.startswith('../'):  # it is a baseURL which strips some levels of the original url
                levels = o.path.split('/')
                levels.pop(len(levels)-1)  # Always remove last level, because it contains a filename (manifest.mpd)
                cntToRemove = baseURL.count('../')
                for _ in range(cntToRemove):
                    levels.pop(len(levels)-1)
                # Reconstruct the actual_url to be used as baseUrl
                path = '/'.join(levels)
                Components = namedtuple(
                    typename='Components',
                    field_names=['scheme', 'netloc', 'path', 'url', 'query', 'fragment']
                )
                updatedUrl = urlunparse(
                    Components(
                        scheme=o.scheme,
                        netloc=o.netloc,
                        path=path + '/',
                        url='',
                        query='',
                        fragment=''
                    )
                )
                self.baseUrl = updatedUrl
            else:
                self.baseUrl = baseURL
        else:
            self.baseUrl = actualUrl

        self.redirectedUrl = actualUrl

    def get_manifest_url(self, proxyUrl: str, streamingToken: str):
        """
        Function to create the manifest URL to the real host

        :param proxyUrl: URL received by the proxy to obtain the manifest
        :param streamingToken: token to be inserted into the manifest request URL
        :return: URL to the real host to be used to obtain the manifest
        """
        if proxyUrl != self.proxyUrl:
            self.proxyUrl = proxyUrl
            self.redirectedUrl = None
        parsedUrl = urlparse(proxyUrl)
        origPath = unquote(parse_qs(parsedUrl.query)['path'][0])
        origHostname = unquote(parse_qs(parsedUrl.query)['hostname'][0])
        initialToken = unquote(parse_qs(parsedUrl.query)['token'][0])
        if streamingToken is not None:
            initialToken = streamingToken

        if self.redirectedUrl is not None:
            #  We can simply use the redirected URL, because it remains unchanged
            return self.__insert_token(self.redirectedUrl, initialToken)
        Components = namedtuple(
            typename='Components',
            field_names=['scheme', 'netloc', 'path', 'url', 'query', 'fragment']
        )
        queryParams = {}
        skipParams = ['hostname', 'path', 'token']
        origParams = parse_qs(parsedUrl.query)
        for param, value in origParams.items():
            if param not in skipParams:
                queryParams.update({param: value[0]})

        url = urlunparse(
            Components(
                scheme='https',
                netloc=origHostname,
                query=urlencode(queryParams),
                path=origPath,
                url='',
                fragment=''
            )
        )
        return self.__insert_token(url, initialToken)

    def replace_baseurl(self, url, streamingToken):
        """
        The url is updated with the name of the redirected host, if a token is still present, it will be
        removed.
        @param url:
        @param streamingToken:
        @return:
        """
        o = urlparse(url)
        redir = urlparse(self.baseUrl)
        actualPath = redir.path
        s = actualPath.find(',vxttoken=')
        e = actualPath.find('/', s)
        if s > 0 and e > 0:
            actualPath = actualPath[0:s] + actualPath[e:]
        pathDir = actualPath.rsplit('/', 1)[0]
        hostAndPath = redir.hostname + pathDir + o.path
        return redir.scheme + '://' + self.__insert_token(hostAndPath, streamingToken)
