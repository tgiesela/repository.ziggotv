"""
Classes for processing channels
"""
import dataclasses
from typing import List, Tuple
from collections import UserList
from resources.lib.events import EventList
import xbmcaddon


class Channel:
    """
    Class to handle all channel data. More robust than querying the json string everywhere
    """
    @dataclasses.dataclass
    class ReplayInfo:
        """
        Dataclass for replay info belonging to a channel
        """
        def __init__(self, eventJson):
            self.replayPrePadding = 0
            self.replayPostPadding = 0
            self.replaySources = {}
            self.replayProducts = {}
            self.ndvrRetentionLimit = 0
            self.avadEnabled = False
            self.adSupport = []
            if 'replayPrePadding' in eventJson:
                self.replayPrePadding = eventJson['replayPrePadding']
            if 'replayPostPadding' in eventJson:
                self.replayPostPadding = eventJson['replayPostPadding']
            if 'replaySources' in eventJson:
                self.replaySources = eventJson['replaySources']
            if 'replayProducts' in eventJson:
                self.replayProducts = eventJson['replayProducts']
            if 'ndvrRetentionLimit' in eventJson:
                self.ndvrRetentionLimit = eventJson['ndvrRetentionLimit']
            if 'avadEnabled' in eventJson:
                self.avadEnabled = True
            if 'adSupport' in eventJson:
                self.adSupport = eventJson['adSupport']

    @dataclasses.dataclass
    class StreamInfo:
        """
        streaming information belonging to a channel
        """
        def __init__(self, eventJson):
            self.streamingApplications = {}
            self.externalStreamingProtocols = {}
            for streamapp in eventJson['streamingApplications']:
                self.streamingApplications[streamapp] = eventJson['streamingApplications'][streamapp]
            if 'externalStreamingProtocols' in eventJson:
                for extstreamapp in eventJson['externalStreamingProtocols']:
                    self.externalStreamingProtocols[extstreamapp] = eventJson['externalStreamingProtocols'][
                        extstreamapp]
            self.imageStream = eventJson['imageStream']

    def __init__(self, channelJson):
        # from resources.lib.events import EventList
        self.jsonData = channelJson
        self.events: EventList = EventList()
        self.logo = {}
        if 'logo' in channelJson:
            for logotype in channelJson['logo']:
                self.logo[logotype] = channelJson['logo'][logotype]
        self.locators = {}
        if 'locators' in channelJson:
            for locator in channelJson['locators']:
                self.locators[locator] = channelJson['locators'][locator]
        self.locators['Default'] = channelJson['locator']
        self.replayInfo = self.ReplayInfo(channelJson)
        if 'genre' in channelJson:
            self.genre = channelJson['genre']
        else:
            self.genre = ''
        self.streamInfo = Channel.StreamInfo(channelJson)

    # properties
    # pylint: disable=missing-function-docstring
    @property
    def id(self):
        return self.jsonData['id']

    @property
    def name(self):
        return self.jsonData['name']

    @property
    def logicalChannelNumber(self):
        return self.jsonData['logicalChannelNumber']

    @property
    def resolution(self):
        return self.jsonData['resolution']

    @property
    def isHidden(self):
        if 'isHidden' in self.jsonData:
            return self.jsonData['isHidden']
        return False

    @property
    def linearProducts(self):
        return self.jsonData['linearProducts']
    # pylint: enable=missing-function-docstring

    def get_locator(self, addon: xbmcaddon.Addon) -> Tuple[str, str]:
        """
        Function to get the correct locator(url) to play a channel. The selected locator
        depends on the maximal resolution allowed according to inputstream adaptive (ISA) and
        the available type of locators.

        @param addon:
        @return: URL of the channel
        """
        try:
            maxResDrm = xbmcaddon.Addon('inputstream.adaptive').getSetting('adaptivestream.res.secure.max')
            hdAllowed = maxResDrm in ['auto', '1080p', '2K', '4K', '1440p']
        # pylint: disable=broad-exception-caught
        except Exception:
            hdAllowed = True
        assetType = 'Orion-DASH'
        fullHD = addon.getSettingBool('full-hd')
        if hdAllowed and not fullHD:
            hdAllowed = False
        if 'Orion-DASH-HEVC' in self.locators and hdAllowed:
            avc = self.locators['Orion-DASH-HEVC']
            assetType = 'Orion-DASH-HEVC'
        elif 'Orion-DASH' in self.locators:
            avc = self.locators['Orion-DASH']
        else:
            avc = self.locators['Default']
        return avc, assetType


class ChannelList(UserList):
    """
    class to get a list of channels with options to suppress hidden channels or only get channels
    for which you ar entitled.
    """
    def __init__(self, channels: [Channel], entitlements):
        super().__init__(channels)
        self.channels: [Channel] = channels
        self.filteredChannels: [Channel] = []
        self.entitlements = entitlements
        self.suppressHidden = True
        self._entitledOnly = False
        self.entitlementList = []
        i = 0
        while i < len(entitlements['entitlements']):
            self.entitlementList.append(entitlements['entitlements'][i]["id"])
            i += 1
        self.apply_filter()

    # properties
    # pylint: disable=missing-function-docstring
    @property
    def hiddenSuppressed(self):
        return self.suppressHidden

    @hiddenSuppressed.setter
    def hiddenSuppressed(self, value):
        self.suppressHidden = value

    @property
    def entitledOnly(self):
        return self._entitledOnly

    @entitledOnly.setter
    def entitledOnly(self, value):
        self._entitledOnly = value
    # pylint: enable=missing-function-docstring

    def apply_filter(self):
        """
        Function to create the resulting list of channels based on the selected filter options:
            hiddenSuppressed
            entitledOnly
        @return:
        """
        self.filteredChannels = []
        for channel in self.channels:
            if channel.isHidden and self.suppressHidden:
                continue
            if self.entitledOnly:
                if self.is_entitled(channel):
                    self.filteredChannels.append(channel)
            else:
                self.filteredChannels.append(channel)
        self.data = self.filteredChannels

    def is_entitled(self, channel: Channel):
        """
        Checks if user is allowed to watch the channel
        @param channel:
        @return:
        """
        for product in channel.linearProducts:
            if product in self.entitlementList:
                return True
        return False

    def supports_replay(self, channel: Channel):
        """
        Checks if the channel supports replay
        @param channel:
        @return:
        """
        for product in channel.replayInfo.replayProducts:
            if product['entitlementId'] in self.entitlementList:
                if product['allowStartOver']:
                    return True
        return False

    def supports_record(self):
        """
        Checks if the channel supports recording
        @param:
        @return:
        """
        return 'PVR' in self.entitlements

    def channels_by_lcn(self) -> List[Channel]:
        """
        Get a list of channels sorted by logical channel number
        @return: List[Channel]
        """
        return sorted(self.channels, key=lambda x: x.logicalChannelNumber, reverse=False)

    def channels_by_name(self) -> List[Channel]:
        """
        Get a list of channels sorted by name
        @return: List[Channel]
        """
        return sorted(self.channels, key=lambda x: x.name, reverse=False)
