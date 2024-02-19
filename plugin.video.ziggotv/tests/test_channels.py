# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
import unittest

from resources.lib.channel import ChannelList, Channel
from tests.test_base import TestBase


class TestChannels(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_channels(self):
        self.do_login()
        self.assertFalse(len(self.session.customerInfo) == 0)
        self.session.refresh_channels()
        self.session.refresh_entitlements()
        channels = self.session.get_channels()
        entitlements = self.session.get_entitlements()
        cl = ChannelList(channels, entitlements)
        clByLcn: [Channel] = cl.channels_by_lcn()
        print('First={0}-{1}'.format(clByLcn[0].logicalChannelNumber, clByLcn[0].name))
        print('Second={0}-{1}'.format(clByLcn[1].logicalChannelNumber, clByLcn[1].name))

        clByname: [Channel] = cl.channels_by_name()
        print('First={0}-{1}'.format(clByname[0].logicalChannelNumber, clByname[0].name))
        print('Second={0}-{1}'.format(clByname[1].logicalChannelNumber, clByname[1].name))

        cl.entitledOnly = True
        cl.apply_filter()
        for x in cl:
            c: Channel = x
            if c.isHidden:
                print('Hidden channel: {0}'.format(c.name))
            if not cl.is_entitled(c):
                print('Channel not entitled: {0}'.format(c.name))
        cl.suppressHidden = True
        cl.entitledOnly = False
        cl.apply_filter()
        for x in cl:
            c: Channel = x
            if c.isHidden:
                print('Hidden channel: {0}'.format(c.name))
            if not cl.is_entitled(c):
                print('Channel not entitled: {0}'.format(c.name))


if __name__ == '__main__':
    unittest.main()
