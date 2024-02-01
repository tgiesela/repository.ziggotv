"""
Classes for processing channels
"""
import typing
import datetime
import json
from collections import UserList
from pathlib import Path

from resources.lib.events import Event, EventList
from resources.lib.globals import G
from resources.lib.utils import ProxyHelper, DatetimeHelper

import xbmc
import xbmcaddon
import xbmcvfs


class Channel:
    def __init__(self, eventJson):
        # from resources.lib.events import EventList
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
            maxResDrm = xbmcaddon.Addon('inputstream.adaptive').getSetting('adaptivestream.res.secure.max')
            if maxResDrm in ['auto', '1080p', '2K', '4K', '1440p']:
                hdAllowed = True
            else:
                hdAllowed = False
        except Exception as exc:
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


class ChannelGuide:
    class GuideWindow:
        def __init__(self, date=None):
            self.isProcessed = False
            self.data = None
            self.startDate = None
            self.endDate = None
            if date is None:
                self.__setWindow(datetime.datetime.now().astimezone(datetime.timezone.utc))
            else:
                self.__setWindow(date)

        def __setWindow(self, dt: datetime.datetime):
            self.startDate = dt.replace(hour=int(dt.hour / 6) * 6, minute=0, second=0, microsecond=0)
            self.endDate = self.startDate + datetime.timedelta(hours=6)

        def dateInWindow(self, evtDate: datetime.datetime):
            if self.startDate <= evtDate < self.endDate:
                return True
            return False

        def nextWindow(self):
            return self.startDate + datetime.timedelta(hours=6)

        def previousWindow(self):
            return self.startDate - datetime.timedelta(hours=6)

        def setData(self, data):
            self.data = data

        def getData(self):
            return self.data

        @property
        def processed(self):
            return self.isProcessed

        @processed.setter
        def processed(self, value):
            self.isProcessed = value

    def __init__(self, addon: xbmcaddon.Addon, channels):
        self.eventsJson = {}
        self.addon = addon
        self.addonPath = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        self.helper = ProxyHelper(self.addon)
        self.windows = []
        self.channels = channels.copy()

    def __currentWindow(self):
        dtNow = datetime.datetime.now().astimezone(datetime.timezone.utc)
        for w in self.windows:
            window: ChannelGuide.GuideWindow = w
            if window.dateInWindow(dtNow):
                return w
        currentWindow = ChannelGuide.GuideWindow(dtNow)
        return currentWindow

    def __isWindowPresent(self, evtDate: datetime.datetime):
        for w in self.windows:
            window: ChannelGuide.GuideWindow = w
            if window.dateInWindow(evtDate):
                return True
        return False

    def __findWindow(self, evtDate: datetime.datetime) -> GuideWindow:
        for w in self.windows:
            window: ChannelGuide.GuideWindow = w
            if window.dateInWindow(evtDate):
                return w
        return None

    def __findLastWindow(self):
        if len(self.windows) == 0:
            return self.__currentWindow()
        lastDate = datetime.datetime.min
        window: ChannelGuide.GuideWindow = self.windows[0]
        for w in self.windows:
            w: ChannelGuide.GuideWindow = w
            if w.startDate > lastDate:
                lastDate = w.startDate
                window = w
        return window

    def __findFirstWindow(self):
        if len(self.windows) == 0:
            return self.__currentWindow()
        firstDate = datetime.datetime.max
        window: ChannelGuide.GuideWindow = self.windows[0]
        for w in self.windows:
            w: ChannelGuide.GuideWindow = w
            if w.startDate < firstDate:
                firstDate = w.startDate
                window = w
        return window

    def __processEvents(self, window):
        # from resources.lib.channel import Channel
        for channel in window.getData():
            currentChannel: Channel = None
            for c in self.channels:
                if c.id == channel['channelId']:
                    currentChannel = c
                    break
            if currentChannel is None:
                xbmc.log('Channel {0} not found'.format(channel['channelId']), xbmc.LOGDEBUG)
                continue
            if 'events' in channel:
                for event in channel['events']:
                    evt = Event(event)
                    currentChannel.events.insertEvent(evt)
            else:
                xbmc.log('No events', xbmc.LOGDEBUG)
        window.processed = True

    def __obtainEvents(self, window: GuideWindow):
        """
            Obtain events not yet stored in epg.json and append them
            to the internal events. Update the channels with the new events

            @param window:
                window with startDate for the events
        """
        from resources.lib.webcalls import LoginSession
        response = self.helper.dynamicCall(LoginSession.get_events, starttime=window.startDate.strftime('%Y%m%d%H%M%S'))
        self.windows.append(window)
        window.setData(response['entries'])
        self.appendEvents(response, window.startDate)
        self.__processEvents(window)

    def obtainEvents(self):
        window = self.__currentWindow()
        if self.__isWindowPresent(window.startDate):
            window = self.__findWindow(window.startDate)
            if not window.processed:
                self.__processEvents(window)
        else:
            self.__obtainEvents(window)

    def obtainEventsInWindow(self, startDate: datetime, endDate: datetime):
        """
        Startdate for the window is determined. This is a date with a 6-hour interval

        @param startDate:
        @param endDate:
        @return:
        """
        if self.__isWindowPresent(startDate):
            startWindow = self.__findWindow(startDate)
            if not startWindow.processed:
                self.__processEvents(startWindow)
        else:
            startWindow = ChannelGuide.GuideWindow(startDate)
            self.__obtainEvents(startWindow)

        if self.__isWindowPresent(endDate):
            endWindow = self.__findWindow(endDate)
            if not endWindow.processed:
                self.__processEvents(endWindow)
        else:
            endWindow = ChannelGuide.GuideWindow(endDate)
            self.__obtainEvents(endWindow)

        nextWindow = ChannelGuide.GuideWindow(startWindow.nextWindow())
        while nextWindow.startDate < endWindow.startDate:
            self.__obtainEvents(nextWindow)
            nextWindow = ChannelGuide.GuideWindow(nextWindow.nextWindow())

    def getEvents(self, channelId):
        for channel in self.channels:
            if channel.id == channelId:
                return channel.events

    def appendEvents(self, response, startTime):
        if 'segments' not in self.eventsJson:
            self.eventsJson = {'segments': []}
        for segment in self.eventsJson['segments']:
            if segment['starttime'] == DatetimeHelper.unixDatetime(startTime):
                self.eventsJson['segments'].remove(segment)
        self.eventsJson['segments'].append({'starttime': DatetimeHelper.unixDatetime(startTime),
                                            'events': response})
        # Path(self.pluginPath(G.GUIDE_INFO)).write_text(json.dumps(self.eventsJson))

    def pluginPath(self, name):
        return self.addonPath + name

    def loadStoredEvents(self):
        self.windows = []
        if Path(self.pluginPath(G.GUIDE_INFO)).exists():
            epgStr = Path(self.pluginPath(G.GUIDE_INFO)).read_text()
        else:
            epgStr = ''
        if epgStr is None or epgStr == '':
            self.eventsJson = {'segments': []}
        else:
            self.eventsJson = json.loads(epgStr)
            self.cleanEvents()
            for segment in self.eventsJson['segments']:
                dt = DatetimeHelper.fromUnix(segment['starttime'])
                dt = dt.replace(tzinfo=datetime.timezone.utc)
                window = ChannelGuide.GuideWindow(dt)
                window.setData(segment['events']['entries'])
                self.windows.append(window)
                # self.__processEvents(window)

    def __reprocess(self):
        for channel in self.channels:
            channel.events = EventList()
        for w in self.windows:
            window: ChannelGuide.GuideWindow = w
            if window.processed:
                self.__processEvents(window)

    def cleanEvents(self):
        for segment in self.eventsJson['segments']:
            oldestTime = datetime.datetime.now() + datetime.timedelta(days=-5)
            if segment['starttime'] < DatetimeHelper.unixDatetime(oldestTime):
                self.eventsJson['segments'].remove(segment)
        self.__reprocess()
    #        Path(self.pluginPath(G.GUIDE_INFO)).write_text(json.dumps(self.eventsJson))

    def storeEvents(self):
        Path(self.pluginPath(G.GUIDE_INFO)).write_text(json.dumps(self.eventsJson))
