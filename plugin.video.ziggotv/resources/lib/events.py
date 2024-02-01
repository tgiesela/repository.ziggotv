import datetime
import json
from typing import List

from resources.lib import utils
from resources.lib.LinkedList import LinkedList, Node


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
        if 'genres' in eventJson:
            self.genres = eventJson['genres']
        else:
            self.genres = []

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
        currentNode: Node = self.head
        while currentNode is not None:
            currentEvent: Event = currentNode.data
            if currentEvent.startTime == event.startTime and currentEvent.endTime == event.endTime:
                return True
            currentNode = currentNode.next
        return False

    def __findInsertLocation(self, event: Event):
        # The event list is ordered on startTime
        currentNode: Node = self.head
        # if event.startTime < current_event.startTime:
        #     self.insertAtBegin(None)
        #     return self.head
        while currentNode is not None:
            currentEvent: Event = currentNode.data
            if currentEvent.startTime > event.startTime:
                return currentNode
            currentNode = currentNode.next
        return currentNode

    def insertEvent(self, event: Event):
        currentNode: Node = self.head
        if currentNode is None:  # Emtpy list
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
        currentNode: Node = self.head
        while currentNode is not None:
            currentEvent: Event = currentNode.data
            if currentEvent.startTime <= currentTime <= currentEvent.endTime:
                return currentEvent
            if currentTime > currentEvent.endTime:
                currentNode = currentNode.next
            else:
                return None
        return None

    def __findEvent(self, ts: datetime.datetime, te: datetime.datetime) -> Node:
        windowstarttime = utils.DatetimeHelper.unixDatetime(ts)
        windowendtime = utils.DatetimeHelper.unixDatetime(te)
        currentNode: Node = self.head
        while currentNode is not None:
            currentEvent: Event = currentNode.data
            if windowstarttime >= currentEvent.startTime:  # start of event before start of window
                if currentEvent.endTime > windowstarttime:  # end of event beyond start of window
                    return currentNode
            if windowstarttime < currentEvent.startTime < windowendtime:
                return currentNode
            elif currentEvent.startTime >= windowstarttime:
                return None
            currentNode = currentNode.next
        return None

