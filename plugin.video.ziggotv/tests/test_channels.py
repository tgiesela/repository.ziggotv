import threading
import unittest

from resources.lib.Channel import ChannelList, Channel
from resources.lib.servicemonitor import HttpProxyService
from tests.test_base import TestBase


class TestChannels(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_login()

    def test_channels(self):
        self.session.refresh_channels()
        self.session.refresh_entitlements()
        channels = self.session.get_channels()
        entitlements = self.session.get_entitlements()
        cl = ChannelList(channels, entitlements)
        clByLcn: [Channel] = cl.channelsByLCN()
        print('First={0}-{1}'.format(clByLcn[0].logicalChannelNumber, clByLcn[0].name))
        print('Second={0}-{1}'.format(clByLcn[1].logicalChannelNumber, clByLcn[1].name))

        clByname: [Channel] = cl.channelsByName()
        print('First={0}-{1}'.format(clByname[0].logicalChannelNumber, clByname[0].name))
        print('Second={0}-{1}'.format(clByname[1].logicalChannelNumber, clByname[1].name))

        cl.entitledOnly = True
        cl.applyFilter()
        for x in cl:
            c: Channel = x
            if c.isHidden:
                print('Hidden channel: {0}'.format(c.name))
            if not cl.isEntitled(c):
                print('Channel not entitled: {0}'.format(c.name))
        cl.suppressHidden = True
        cl.entitledOnly = False
        cl.applyFilter()
        for x in cl:
            c: Channel = x
            if c.isHidden:
                print('Hidden channel: {0}'.format(c.name))
            if not cl.isEntitled(c):
                print('Channel not entitled: {0}'.format(c.name))


if __name__ == '__main__':
    unittest.main()
