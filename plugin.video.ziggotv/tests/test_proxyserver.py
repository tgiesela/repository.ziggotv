import threading
import unittest
import json
from time import sleep

from resources.lib.proxyserver import HTTPRequestHandler, ProxyServer
from resources.lib.utils import ProxyHelper
from resources.lib.webcalls import WebException, LoginSession
from tests.test_base import TestBase


class TestProxyServer(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = threading.Lock()
        self.port = 8888
        self.address = '127.0.0.1'
        self.session.printNetworkTraffic = True
        self.helper = ProxyHelper(self.addon)
        self.do_login()

    def do_login(self):
        with open(f'c:/temp/credentials.json', 'r') as credfile:
            credentials = json.loads(credfile.read())
        self.helper.dynamic_call(LoginSession.login, username=credentials['username'], password=credentials['password'])

    def test_startProxy(self):
        thread = None
        try:
            self.ProxyServer = ProxyServer(self, (self.address, self.port), self.lock)
            thread = threading.Thread(target=self.ProxyServer.serve_forever)
            thread.start()
            self.HTTPServerThread = thread
            sleep(1)
            rslt = self.helper.dynamic_call(LoginSession.login, username='bad', password='bad')
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
            print('Message: {0}'.format(e.get_response()))
            print('Status: {0}'.format(e.get_status()))
            self.ProxyServer.shutdown()
            if thread is not None:
                thread.join()
            print('ProxyServer stopped')

    def test_dynamicCall(self):
        thread = None
        try:
            self.ProxyServer = ProxyServer(self, (self.address, self.port), self.lock)
            thread = threading.Thread(target=self.ProxyServer.serve_forever)
            thread.start()
            self.HTTPServerThread = thread
            sleep(1)
            events = []
            shows = ['crid:~~2F~~2Fgn.tv~~2F26434552~~2FSH041927000000']
            channelId = 'NL_000001_019401'
            rslt = self.helper.dynamic_call(LoginSession.delete_recordings,
                                            events=events,
                                            shows=shows,
                                            channelId=channelId)
            sleep(1)
            self.ProxyServer.shutdown()
            thread.join()
            print('ProxyServer stopped')

        except IOError as e:
            print('Exception during ProxyServer test: {0}'.format(e))
        except WebException as e:
            print('Web Exception during ProxyServer test: {0}'.format(e))
            print('Message: {0}'.format(e.get_response()))
            print('Status: {0}'.format(e.get_status()))
            self.ProxyServer.shutdown()
            if thread is not None:
                thread.join()
            print('ProxyServer stopped')


if __name__ == '__main__':
    unittest.main()
