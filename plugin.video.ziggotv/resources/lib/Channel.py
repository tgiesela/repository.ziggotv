import typing
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

    def get_locator(self, addon: xbmcaddon.Addon) -> typing.Tuple[str, str]:
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


