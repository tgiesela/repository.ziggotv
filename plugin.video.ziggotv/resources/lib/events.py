import datetime
from typing import List

import xbmc

from resources.lib import utils
from resources.lib.LinkedList import LinkedList, Node
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
        self.__programdetails: EventDetails = None
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
        return self.__programdetails is not None

    @property
    def details(self):
        return self.__programdetails

    @details.setter
    def details(self, value):
        self.__programdetails = EventDetails(value)

    @property
    def canReplay(self):
        return self.__hasStartOver and self.__hasReplayTV


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
    def __init__(self, session):
        self.session: LoginSession = session
        self.windows = []
        # self.session.refresh_channels()
        self.channels = []
        for channel in self.session.get_channels():
            self.channels.append(channel)

    @staticmethod
    def __setWindow(dt: datetime.datetime):
        evtDate = dt
        evtDate = evtDate.replace(hour=int(evtDate.hour / 6) * 6, minute=0, second=0, microsecond=0)
        return evtDate

    def __currentWindow(self):
        return self.__setWindow(datetime.datetime.now().astimezone(datetime.timezone.utc))

    @staticmethod
    def __nextWindow(evtDate: datetime.datetime):
        return evtDate + datetime.timedelta(hours=6)

    @staticmethod
    def __previousWindow(evtDate: datetime.datetime):
        return evtDate - datetime.timedelta(hours=6)

    def __isWindowPresent(self, evtDate: datetime.datetime):
        for date in self.windows:
            if date == evtDate:
                return True
        return False

    def __dateInWindow(self, evtDate: datetime.datetime):
        for date in self.windows:
            if date <= evtDate < date + datetime.timedelta(hours=6):
                return True
        return False

    def __findLastWindow(self):
        if len(self.windows) == 0:
            return self.__currentWindow()
        lastdate = self.windows[0]
        for date in self.windows:
            if date > lastdate:
                lastdate = date
        return lastdate

    def __findFirstWindow(self):
        if len(self.windows) == 0:
            return self.__currentWindow()
        firstdate = self.windows[0]
        for date in self.windows:
            if date < firstdate:
                firstdate = date
        return firstdate

    def __processEvents(self, evtDate: datetime.datetime):
        response = self.session.get_events(evtDate.strftime('%Y%m%d%H%M%S'))
        for channel in response['entries']:
            from resources.lib.Channel import Channel
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

    def obtainEvents(self):
        evtDate = self.__currentWindow()
        if self.__isWindowPresent(evtDate):
            pass
        else:
            self.windows.append(evtDate)
            self.__processEvents(evtDate)
        evtDate = self.__nextWindow(evtDate)
        if self.__isWindowPresent(evtDate):
            pass
        else:
            self.windows.append(evtDate)
            self.__processEvents(evtDate)

    def obtainNextEvents(self):
        evtDate = self.__findLastWindow()
        evtDate = self.__nextWindow(evtDate)
        self.windows.append(evtDate)
        self.__processEvents(evtDate)

    def obtainPreviousEvents(self):
        evtDate = self.__findFirstWindow()
        evtDate = self.__previousWindow(evtDate)
        self.windows.append(evtDate)
        self.__processEvents(evtDate)

    def obtainEventsInWindow(self, startDate: datetime, endDate: datetime):
        startEvtDate = self.__setWindow(startDate)
        endEvtDate = self.__setWindow(endDate)
        if self.__isWindowPresent(startEvtDate):
            if self.__dateInWindow(endEvtDate):
                pass  # All events are already present
            else:
                evtDate = self.__nextWindow(startEvtDate)
                self.windows.append(evtDate)
                self.__processEvents(evtDate)
        else:
            self.windows.append(startEvtDate)
            self.__processEvents(startEvtDate)
            if self.__dateInWindow(endEvtDate):
                pass
            else:
                self.windows.append(endEvtDate)
                self.__processEvents(endEvtDate)

    def getEvents(self, channelId):
        for channel in self.channels:
            if channel.id == channelId:
                return channel.events

    def windowAvailable(self, start: datetime, end: datetime):
        if self.__dateInWindow(start):
            if self.__dateInWindow(end):
                return True
        return False
