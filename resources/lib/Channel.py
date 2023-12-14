
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


