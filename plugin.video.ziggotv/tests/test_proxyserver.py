import threading
import unittest
from time import sleep

import requests
import xbmc

from resources.lib.proxyserver import HTTPRequestHandler, ProxyServer
from resources.lib.utils import ProxyHelper
from resources.lib.webcalls import WebException, LoginSession
from tests.test_base import TestBase
from http.server import BaseHTTPRequestHandler
import http.server


class TestProxyServer(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = threading.Lock()
        self.port = 8888
        self.address = '127.0.0.1'

    def test_startProxy(self):
        thread = None
        try:
            self.ProxyServer = ProxyServer(self, (self.address, self.port), self.lock)
            thread = threading.Thread(target=self.ProxyServer.serve_forever)
            thread.start()
            self.HTTPServerThread = thread
            sleep(1)
            helper = ProxyHelper(self.addon)
            rslt = helper.dynamicCall(LoginSession.login, username='bad', password='bad')
#            response = requests.get('http://127.0.0.1:8888/function}')
#            if response.status_code != 200:
#                raise WebException(response)
            sleep(1)
            self.ProxyServer.shutdown()
            thread.join()
            print('ProxyServer stopped')

        except IOError as e:
            print('Exception during ProxyServer test: {0}'.format(e))
        except WebException as e:
            print('Web Exception during ProxyServer test: {0}'.format(e))
            print('Message: {0}'.format(e.getResponse()))
            print('Status: {0}'.format(e.getStatus()))
            self.ProxyServer.shutdown()
            if thread is not None:
                thread.join()
            print('ProxyServer stopped')


if __name__ == '__main__':
    unittest.main()
