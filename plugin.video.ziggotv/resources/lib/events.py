import datetime
from typing import List

from resources.lib import utils
from resources.lib.linkedlist import LinkedList, Node


# pylint: disable=too-many-instance-attributes, too-few-public-methods
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
    # pylint: disable=too-many-branches
    def __init__(self, eventJson):
        self.programDetails: EventDetails = None
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
            self.hasReplayTV = eventJson['hasReplayTV']
        else:
            self.hasReplayTV = True
        if 'hasReplayTVOTT' in eventJson:
            self.hasReplayTVOTT = eventJson['hasReplayTVOTT']
        else:
            self.hasReplayTVOTT = True
        if 'hasStartOver' in eventJson:
            self.hasStartOver = eventJson['hasStartOver']
        else:
            self.hasStartOver = True

    @property
    def duration(self):
        return self.endTime - self.startTime

    @duration.setter
    def duration(self, value):
        self.duration = value

    @property
    def hasDetails(self):
        return self.programDetails is not None

    @property
    def details(self):
        return self.programDetails

    @details.setter
    def details(self, value):
        self.programDetails = EventDetails(value)

    @property
    def canReplay(self):
        now = utils.DatetimeHelper.unix_datetime(datetime.datetime.now())
        if self.startTime < now < self.endTime or self.endTime <= now:
            return self.hasStartOver and self.hasReplayTV
        return False

    @property
    def canRecord(self):
        now = utils.DatetimeHelper.unix_datetime(datetime.datetime.now())
        if self.startTime < now < self.endTime or self.endTime <= now:
            return self.hasStartOver and self.hasReplayTV
        if self.startTime > now:
            return True
        return False

    @property
    def isPlaying(self):
        now = utils.DatetimeHelper.unix_datetime(datetime.datetime.now())
        if self.startTime < now < self.endTime:
            return True
        return False


class EventList(LinkedList):
    def __is_duplicate(self, event: Event):
        currentNode: Node = self.head
        while currentNode is not None:
            currentEvent: Event = currentNode.data
            if currentEvent.startTime == event.startTime and currentEvent.endTime == event.endTime:
                return True
            currentNode = currentNode.next
        return False

    def __find_insert_location(self, event: Event):
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

    def insert_event(self, event: Event):
        currentNode: Node = self.head
        if currentNode is None:  # Emtpy list
            self.insert_at_begin(event)
            return
        if self.__is_duplicate(event):
            return
        node = self.__find_insert_location(event)
        if node is None:
            self.insert_at_end(event)
        else:
            if node.data is None:
                node.data = event
            else:
                self.insert_before(node, event)

    @staticmethod
    def next_event(node) -> Event:
        if node is None:
            return None
        return node.next.data

    def get_events_in_window(self, tstart: datetime.datetime, tend: datetime.datetime) -> List[Event]:
        evtlist: List[Event] = []
        evtnode = self.__find_event(tstart, tend)
        endtime = utils.DatetimeHelper.unix_datetime(tend)
        while evtnode is not None:
            evt: Event = evtnode.data
            if evt.startTime >= endtime:
                break
            evtlist.append(evtnode.data)
            evtnode = evtnode.next
        return evtlist

    def get_current_event(self) -> Event:
        currentTime: datetime.datetime = utils.DatetimeHelper.unix_datetime(datetime.datetime.now())
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

    def __find_event(self, ts: datetime.datetime, te: datetime.datetime) -> Node:
        windowstarttime = utils.DatetimeHelper.unix_datetime(ts)
        windowendtime = utils.DatetimeHelper.unix_datetime(te)
        currentNode: Node = self.head
        while currentNode is not None:
            currentEvent: Event = currentNode.data
            if windowstarttime >= currentEvent.startTime:  # start of event before start of window
                if currentEvent.endTime > windowstarttime:  # end of event beyond start of window
                    return currentNode
            if windowstarttime < currentEvent.startTime < windowendtime:
                return currentNode
            if currentEvent.startTime >= windowstarttime:
                return None
            currentNode = currentNode.next
        return None
