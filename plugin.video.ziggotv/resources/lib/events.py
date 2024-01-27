import datetime
import json
from pathlib import Path
from typing import List

import xbmc
import xbmcaddon
import xbmcvfs

from resources.lib import utils
from resources.lib.LinkedList import LinkedList, Node
from resources.lib.globals import G
from resources.lib.utils import ProxyHelper
from resources.lib.webcalls import LoginSession


class EventDetails:
    def __init__(self, eventJson):
        if 'shortDescription' in eventJson:
            self.description = eventJson['shortDescription']
        elif 'longDescription' in eventJson:
            self.description = eventJson['longDescription']
        else:
            self.description = ''

        self.eventId = eventJson['eventId']
        self.channelId = eventJson['channelId']
        self.mergedId = eventJson['mergedId']
        self.seriesId = None
        if 'seriesId' in eventJson:
            self.seriesId = eventJson['seriesId']
            self.episode = eventJson['episodeNumber']
            self.season = eventJson['seasonNumber']
            if 'episodeName' in eventJson:
                self.episodeName = eventJson['episodeName']
        if 'actors' in eventJson:
            self.actors = eventJson['actors']
        else:
            self.actors = []

    @property
    def isSeries(self):
        return self.seriesId is not None


class Event:
    def __init__(self, eventJson):
        self.__programDetails: EventDetails = None
        self.startTime = eventJson['startTime']
        self.endTime = eventJson['endTime']
        self.title = eventJson['title']
        self.id = eventJson['id']
        if 'mergedId' in eventJson:
            self.mergedId = eventJson['mergedId']
        else:
            self.mergedId = ''
        if 'minimumAge' in eventJson:
            self.minimumAge = eventJson['minimumAge']
        else:
            self.minimumAge = 0
        if 'isPlaceHolder' in eventJson:
            self.isPlaceHolder = eventJson['isPlaceHolder']
        else:
            self.isPlaceHolder = False
        if 'replayTVMinAge' in eventJson:
            self.replayTVMinAge = eventJson['replayTVMinAge']
        else:
            self.replayTVMinAge = 0
        if 'hasReplayTV' in eventJson:
            self.__hasReplayTV = eventJson['hasReplayTV']
        else:
            self.__hasReplayTV = True
        if 'hasReplayTVOTT' in eventJson:
            self.__hasReplayTVOTT = eventJson['hasReplayTVOTT']
        else:
            self.__hasReplayTVOTT = True
        if 'hasStartOver' in eventJson:
            self.__hasStartOver = eventJson['hasStartOver']
        else:
            self.__hasStartOver = True

    @property
    def duration(self):
        return self.endTime - self.startTime

    @duration.setter
    def duration(self, value):
        self.duration = value

    @property
    def hasDetails(self):
        return self.__programDetails is not None

    @property
    def details(self):
        return self.__programDetails

    @details.setter
    def details(self, value):
        self.__programDetails = EventDetails(value)

    @property
    def canReplay(self):
        now = utils.DatetimeHelper.unixDatetime(datetime.datetime.now())
        if self.startTime < now < self.endTime or self.endTime <= now:
            return self.__hasStartOver and self.__hasReplayTV
        else:
            return False

    @property
    def canRecord(self):
        now = utils.DatetimeHelper.unixDatetime(datetime.datetime.now())
        if self.startTime < now < self.endTime or self.endTime <= now:
            return self.__hasStartOver and self.__hasReplayTV
        else:
            if self.startTime > now:
                return True
            else:
                return False

    @property
    def isPlaying(self):
        now = utils.DatetimeHelper.unixDatetime(datetime.datetime.now())
        if self.startTime < now < self.endTime:
            return True
        else:
            return False


class EventList(LinkedList):
    def __isDuplicate(self, event: Event):
        current_node: Node = self.head
        while current_node is not None:
            current_event: Event = current_node.data
            if current_event.startTime == event.startTime and current_event.endTime == event.endTime:
                return True
            else:
                current_node = current_node.next
        return False

    def __findInsertLocation(self, event: Event):
        # The event list is ordered on startTime
        current_node: Node = self.head
        # if event.startTime < current_event.startTime:
        #     self.insertAtBegin(None)
        #     return self.head
        while current_node is not None:
            current_event: Event = current_node.data
            if current_event.startTime > event.startTime:
                return current_node
            else:
                current_node = current_node.next
        return current_node

    def insertEvent(self, event: Event):
        current_node: Node = self.head
        if current_node is None:  # Emtpy list
            self.insertAtBegin(event)
            return
        if self.__isDuplicate(event):
            return
        node = self.__findInsertLocation(event)
        if node is None:
            self.insertAtEnd(event)
        else:
            if node.data is None:
                node.data = event
            else:
                self.insertBefore(node, event)

    @staticmethod
    def nextEvent(node) -> Event:
        if node is None:
            return None
        else:
            return node.next.data

    def getEventsInWindow(self, tstart: datetime.datetime, tend: datetime.datetime) -> List[Event]:
        evtlist: List[Event] = []
        evtnode = self.__findEvent(tstart, tend)
        endtime = utils.DatetimeHelper.unixDatetime(tend)
        while evtnode is not None:
            evt: Event = evtnode.data
            if evt.startTime >= endtime:
                break
            evtlist.append(evtnode.data)
            evtnode = evtnode.next
        return evtlist

    def getCurrentEvent(self) -> Event:
        currentTime: datetime.datetime = utils.DatetimeHelper.unixDatetime(datetime.datetime.now())
        current_node: Node = self.head
        while current_node is not None:
            current_event: Event = current_node.data
            if current_event.startTime <= currentTime <= current_event.endTime:
                return current_event
            else:
                if currentTime > current_event.endTime:
                    current_node = current_node.next
                else:
                    return None
        return None

    def __findEvent(self, ts: datetime.datetime, te: datetime.datetime) -> Node:
        windowstarttime = utils.DatetimeHelper.unixDatetime(ts)
        windowendtime = utils.DatetimeHelper.unixDatetime(te)
        current_node: Node = self.head
        while current_node is not None:
            current_event: Event = current_node.data
            if windowstarttime >= current_event.startTime:  # start of event before start of window
                if current_event.endTime > windowstarttime:  # end of event beyond start of window
                    return current_node
            if windowstarttime < current_event.startTime < windowendtime:
                return current_node
            elif current_event.startTime >= windowstarttime:
                return None
            current_node = current_node.next
        return None


class ChannelGuide:
    class GuideWindow:
        def __init__(self, date=None):
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

    def __init__(self, addon: xbmcaddon.Addon):
        self.eventsJson = {}
        self.addon = addon
        self.addon_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        self.helper = ProxyHelper(self.addon)
        self.windows = []
        self.channels = []
        self.__initializeSession()

    # Private methods
    def __initializeSession(self):
        for channel in self.helper.dynamicCall(LoginSession.get_channels):
            self.channels.append(channel)

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

    def __findWindow(self, evtDate: datetime.datetime):
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

    def __processEvents(self, entries):
        from resources.lib.Channel import Channel
        for channel in entries:
            current_channel: Channel = None
            for c in self.channels:
                if c.id == channel['channelId']:
                    current_channel = c
                    break
            if current_channel is None:
                xbmc.log('Channel {0} not found'.format(channel['channelId']), xbmc.LOGDEBUG)
                continue
            if 'events' in channel:
                for event in channel['events']:
                    evt = Event(event)
                    current_channel.events.insertEvent(evt)
            else:
                xbmc.log('No events', xbmc.LOGDEBUG)

    def __obtainEvents(self, window: GuideWindow):
        """
            Obtain events not yet stored in epg.json and append them
            to the internal events. Update the channels with the new events

            @param window:
                window with startDate for the events
        """
        response = self.helper.dynamicCall(LoginSession.get_events, starttime=window.startDate.strftime('%Y%m%d%H%M%S'))
        self.windows.append(window)
        self.appendEvents(response, window.startDate)
        self.__processEvents(response['entries'])

    def obtainEvents(self):
        window = self.__currentWindow()
        if self.__isWindowPresent(window.startDate):
            pass
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
        else:
            startWindow = ChannelGuide.GuideWindow(startDate)
            self.__obtainEvents(startWindow)

        if self.__isWindowPresent(endDate):
            endWindow = self.__findWindow(endDate)
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
            if segment['starttime'] == utils.DatetimeHelper.unixDatetime(startTime):
                self.eventsJson['segments'].remove(segment)
        self.eventsJson['segments'].append({'starttime': utils.DatetimeHelper.unixDatetime(startTime),
                                            'events': response})
        # Path(self.pluginPath(G.GUIDE_INFO)).write_text(json.dumps(self.eventsJson))

    def pluginPath(self, name):
        return self.addon_path + name

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
                dt = utils.DatetimeHelper.fromUnix(segment['starttime'])
                dt = dt.replace(tzinfo=datetime.timezone.utc)
                window = ChannelGuide.GuideWindow(dt)
                self.windows.append(window)
                self.__processEvents(segment['events']['entries'])

    def cleanEvents(self):
        for segment in self.eventsJson['segments']:
            oldestTime = datetime.datetime.now() + datetime.timedelta(days=-5)
            if segment['starttime'] < utils.DatetimeHelper.unixDatetime(oldestTime):
                self.eventsJson['segments'].remove(segment)

    #        Path(self.pluginPath(G.GUIDE_INFO)).write_text(json.dumps(self.eventsJson))

    def storeEvents(self):
        Path(self.pluginPath(G.GUIDE_INFO)).write_text(json.dumps(self.eventsJson))
