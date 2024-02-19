# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring

import threading
import unittest
import json
from time import sleep

from resources.lib.proxyserver import ProxyServer
from resources.lib.utils import ProxyHelper, WebException
from resources.lib.webcalls import LoginSession
from tests.test_base import TestBase


class TestProxyServer(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = threading.Lock()
        self.port = 6868
        self.address = '127.0.0.1'
        self.session.printNetworkTraffic = True
        self.helper = ProxyHelper(self.addon)

    def do_login(self):
        with open('c:/temp/credentials.json', 'r', encoding='utf-8') as credfile:
            credentials = json.loads(credfile.read())
        self.helper.dynamic_call(LoginSession.login,
                                 username=credentials['username'],
                                 password=credentials['password'])

    def test_start_proxy(self):
        self.do_login()
        thread = None
        proxyServer = None
        try:
            proxyServer = ProxyServer(self, (self.address, self.port), self.lock)
            thread = threading.Thread(target=proxyServer.serve_forever)
            thread.start()
            sleep(1)
            rslt = self.helper.dynamic_call(LoginSession.login, username='bad', password='bad')
            print(rslt)
            sleep(1)
            proxyServer.shutdown()
            thread.join()
            print('ProxyServer stopped')

        except IOError as e:
            print('Exception during ProxyServer test: {0}'.format(e))
        except WebException as e:
            print('Web Exception during ProxyServer test: {0}'.format(e))
            print('Message: {0}'.format(e.response))
            print('Status: {0}'.format(e.status))
            if proxyServer is not None:
                proxyServer.shutdown()
            if thread is not None:
                thread.join()
            print('ProxyServer stopped')

    def test_dynamic_call(self):
        self.do_login()
        thread = None
        proxyServer = None
        try:
            proxyServer = ProxyServer(self, (self.address, self.port), self.lock)
            thread = threading.Thread(target=proxyServer.serve_forever)
            thread.start()
            sleep(1)
            events = []
            shows = ['crid:~~2F~~2Fgn.tv~~2F26434552~~2FSH041927000000']
            channelId = 'NL_000001_019401'
            rslt = self.helper.dynamic_call(LoginSession.delete_recordings,
                                            events=events,
                                            shows=shows,
                                            channelId=channelId)
            print(rslt)
            sleep(1)
            proxyServer.shutdown()
            thread.join()
            print('ProxyServer stopped')

        except IOError as e:
            print('Exception during ProxyServer test: {0}'.format(e))
        except WebException as e:
            print('Web Exception during ProxyServer test: {0}'.format(e))
            print('Message: {0}'.format(e.response))
            print('Status: {0}'.format(e.status))
            if proxyServer is not None:
                proxyServer.shutdown()
            if thread is not None:
                thread.join()
            print('ProxyServer stopped')


if __name__ == '__main__':
    unittest.main()
