import unittest
import os
import json
import threading

import xbmcaddon

from resources.lib.globals import G
from resources.lib.servicemonitor import HttpProxyService
from resources.lib.webcalls import LoginSession


class Addon(xbmcaddon.Addon):
    """
        Class to support use of setting/getting the addon settings
        Very primitive.
    """
    def __init__(self, name):
        super().__init__(name)
        self.settings = {}

    def setSetting(self, id: str, value: str) -> None:
        self.settings.update({id: value})

    def getSetting(self, id: str) -> str:
        return self.settings[id]

    def getSettingBool(self, id: str) -> bool:
        return bool(self.settings[id])

    def getSettingInt(self, id: str) -> int:
        return int(self.settings[id])

    def getSettingNumber(self, id: str) -> float:
        return float(self.settings[id])


class TestBase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addon = Addon('plugin.video.ziggotv')
        self.addon.setSetting('print-network-traffic', 'false')
        self.addon.setSetting('proxy-ip', '127.0.0.1')
        self.addon.setSetting('proxy-port', '6868')
        self.addon.setSetting('use-proxy', 'true')
        self.cleanup_all()
        self.session = LoginSession(xbmcaddon.Addon())
        self.session.print_network_traffic = 'false'
        self.svc = HttpProxyService(threading.Lock())
        self.svc.set_address((self.addon.getSetting('proxy-ip'), self.addon.getSettingInt('proxy-port')))
        self.svc.startHttpServer()

    def setUp(self):
        print("Executing setup")

    def tearDown(self):
        self.session.close()
        self.svc.stopHttpServer()
        self.cleanup_all()

    def remove(self, file):
        if os.path.exists(file):
            os.remove(file)

    def cleanup_cookies(self):
        self.remove(G.COOKIES_INFO)

    def cleanup_channels(self):
        self.remove(G.CHANNEL_INFO)

    def cleanup_customer(self):
        self.remove(G.CUSTOMER_INFO)

    def cleanup_session(self):
        self.remove(G.SESSION_INFO)

    def cleanup_entitlements(self):
        self.remove(G.ENTITLEMENTS_INFO)

    def cleanup_widevine(self):
        self.remove(G.WIDEVINE_LICENSE)
        self.remove(G.WIDEVINE_LICENSE + '.raw')

    def cleanup_all(self):
        self.cleanup_customer()
        self.cleanup_session()
        self.cleanup_channels()
        self.cleanup_cookies()
        self.cleanup_entitlements()
        self.cleanup_widevine()

    def do_login(self):
        with open(f'c:/temp/credentials.json', 'r') as credfile:
            credentials = json.loads(credfile.read())
        self.session.login(credentials['username'], credentials['password'])
