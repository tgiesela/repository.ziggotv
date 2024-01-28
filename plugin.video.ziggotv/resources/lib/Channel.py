import typing
from collections import UserList

import xbmcaddon


class Channel:
    def __init__(self, eventJson):
        from resources.lib.events import EventList
        self.events: EventList = EventList()
        self.channelId = eventJson['id']
        self.name = eventJson['name']
        self.logicalChannelNumber = eventJson['logicalChannelNumber']
        self.logo = {}
        if 'logo' in eventJson:
            for logotype in eventJson['logo']:
                self.logo[logotype] = eventJson['logo'][logotype]
        self.locators = {}
        if 'locators' in eventJson:
            for locator in eventJson['locators']:
                self.locators[locator] = eventJson['locators'][locator]
        self.locators['Default'] = eventJson['locator']
        self.resolution = eventJson['resolution']
        if 'replayPrePadding' in eventJson:
            self.replayPrePadding = eventJson['replayPrePadding']
        else:
            self.replayPrePadding = 0
        if 'replayPostPadding' in eventJson:
            self.replayPostPadding = eventJson['replayPostPadding']
        else:
            self.replayPostPadding = 0
        self.replaySources = {}
        if 'replaySources' in eventJson:
            self.replaySources = eventJson['replaySources']
        self.replayProducts = {}
        if 'replayProducts' in eventJson:
            self.replayProducts = eventJson['replayProducts']
        self.linearProducts = {}
        self.linearProducts = eventJson['linearProducts']
        if 'genre' in eventJson:
            self.genre = eventJson['genre']
        else:
            self.genre = ''
        if 'ndvrRetentionLimit' in eventJson:
            self.ndvrRetentionLimit = eventJson['ndvrRetentionLimit']
        else:
            self.ndvrRetentionLimit = 0
        self.streamingApplications = {}
        for streamapp in eventJson['streamingApplications']:
            self.streamingApplications[streamapp] = eventJson['streamingApplications'][streamapp]
        self.externalStreamingProtocols = {}
        if 'externalStreamingProtocols' in eventJson:
            for extstreamapp in eventJson['externalStreamingProtocols']:
                self.externalStreamingProtocols[extstreamapp] = eventJson['externalStreamingProtocols'][extstreamapp]
        self.imageStream = eventJson['imageStream']
        self.isHidden = False
        if 'isHidden' in eventJson:
            self.isHidden = True

    @property
    def id(self):
        return self.channelId

    def getLocator(self, addon: xbmcaddon.Addon) -> typing.Tuple[str, str]:
        try:
            # max_res = xbmcaddon.Addon('inputstream.adaptive').getSetting('adaptivestream.res.max')
            max_res_drm = xbmcaddon.Addon('inputstream.adaptive').getSetting('adaptivestream.res.secure.max')
            if max_res_drm in ['auto', '1080p', '2K', '4K', '1440p']:
                hd_allowed = True
            else:
                hd_allowed = False
        except Exception as exc:
            hd_allowed = True
        asset_type = 'Orion-DASH'
        fullHD = addon.getSettingBool('full-hd')
        if hd_allowed and not fullHD:
            hd_allowed = False
        if 'Orion-DASH-HEVC' in self.locators and hd_allowed:
            avc = self.locators['Orion-DASH-HEVC']
            asset_type = 'Orion-DASH-HEVC'
        elif 'Orion-DASH' in self.locators:
            avc = self.locators['Orion-DASH']
        else:
            avc = self.locators['Default']
        return avc, asset_type


class ChannelList(UserList):
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
        self.applyFilter()

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

    def applyFilter(self):
        self.filteredChannels = []
        for channel in self.channels:
            if channel.isHidden and self.suppressHidden:
                continue
            if self.entitledOnly:
                if self.isEntitled(channel):
                    self.filteredChannels.append(channel)
            else:
                self.filteredChannels.append(channel)
        self.data = self.filteredChannels

    def isEntitled(self, channel):
        for product in channel.linearProducts:
            if product in self.entitlementList:
                return True
        return False

    def supportsReplay(self, channel):
        for product in channel.replayProducts:
            if product['entitlementId'] in self.entitlementList:
                if product['allowStartOver']:
                    return True
        return False

    def supportsRecord(self):
        return 'PVR' in self.entitlements

    def channelsByLCN(self):
        return sorted(self.channels, key=lambda x: x.logicalChannelNumber, reverse=False)

    def channelsByName(self):
        return sorted(self.channels, key=lambda x: x.name, reverse=False)
