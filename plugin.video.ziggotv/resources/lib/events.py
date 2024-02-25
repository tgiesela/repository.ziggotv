"""
module with classes for program events used for epg, replay and recording
"""
import datetime
from typing import List

from resources.lib import utils
from resources.lib.linkedlist import LinkedList, Node


# pylint: disable=too-many-instance-attributes, too-few-public-methods
class EventDetails:
    """
    class containing the details of an event
    """
    def __init__(self, eventJson):
        if 'shortDescription' in eventJson:
            self.description = eventJson['shortDescription']
        elif 'longDescription' in eventJson:
            self.description = eventJson['longDescription']
        else:
            self.description = ''

        self.eventId = eventJson['eventId']
        self.channelId = eventJson['channelId']
        self.mergedId = None
        if 'mergeId' in eventJson:
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
    def isSeries(self) -> bool:
        """
        property indicating if event is a series/show or single program
        @return: True/False
        """
        return self.seriesId is not None


class Event:
    """
    class containing the basic properties of an event. See EventDetails for more information
    """
    # pylint: disable=too-many-branches
    def __init__(self, eventJson):
        self.programDetails: EventDetails = None
        self.startTime = eventJson['startTime']
        self.endTime = eventJson['endTime']
        self.title = ''
        if 'title' in eventJson:
            self.title = eventJson['title']
        self.id = eventJson['id']
        if 'mergedId' in eventJson:
            self.mergedId = eventJson['mergedId']
        else:
            self.mergedId = ''
        self.minimumAge = 0
        if 'minimumAge' in eventJson:
            self.minimumAge = eventJson['minimumAge']
        self.isPlaceHolder = False
        if 'isPlaceHolder' in eventJson:
            self.isPlaceHolder = eventJson['isPlaceHolder']
        self.replayTVMinAge = 0
        if 'replayTVMinAge' in eventJson:
            self.replayTVMinAge = eventJson['replayTVMinAge']
        self.hasReplayTV = True
        if 'hasReplayTV' in eventJson:
            self.hasReplayTV = eventJson['hasReplayTV']
        self.hasReplayTVOTT = True
        if 'hasReplayTVOTT' in eventJson:
            self.hasReplayTVOTT = eventJson['hasReplayTVOTT']
        self.hasStartOver = True
        if 'hasStartOver' in eventJson:
            self.hasStartOver = eventJson['hasStartOver']

    @property
    def duration(self):
        """
        Length of event in seconds
        @return: length of event in seconds
        """
        return self.endTime - self.startTime

    @duration.setter
    def duration(self, value):
        self.duration = value

    @property
    def hasDetails(self) -> bool:
        """
        Indicates if details are already available
        @return: True/False
        """
        return self.programDetails is not None

    @property
    def details(self) -> EventDetails:
        """
        Get the event details
        @return: details
        """
        return self.programDetails

    @details.setter
    def details(self, value):
        self.programDetails = EventDetails(value)

    @property
    def canReplay(self) -> bool:
        """
        Checks if event supports replay
        @return: True/False
        """
        now = utils.DatetimeHelper.unix_datetime(datetime.datetime.now())
        if self.isPlaying:
            return self.hasStartOver and self.hasReplayTV
        if self.endTime <= now:
            return self.hasStartOver and self.hasReplayTV
        return False

    @property
    def canRecord(self) -> bool:
        """
        Checks if event can be recorded
        @return: True/False
        """
        now = utils.DatetimeHelper.unix_datetime(datetime.datetime.now())
        if self.isPlaying:
            return True
        if self.endTime <= now:
            return False
        if self.startTime > now:
            return True
        return False

    @property
    def isPlaying(self) -> bool:
        """
        Checks if event is currently playing
        @return: True/False
        """
        now = utils.DatetimeHelper.unix_datetime(datetime.datetime.now())
        if self.startTime < now < self.endTime:
            return True
        return False


class EventList(LinkedList):
    """
    class containing the events sorted on start time. Linked List implementation.
    """
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
        """
        Insert event in the linked list of events
        @param event:
        @return:
        """
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

    def get_events_in_window(self, tstart: datetime.datetime, tend: datetime.datetime) -> List[Event]:
        """
        Get a list of events in a specific time window (from tstart until tend)
        @param tstart:
        @param tend:
        @return:
        """
        evtList: List[Event] = []
        evtNode = self.__find_event(tstart, tend)
        endTime = utils.DatetimeHelper.unix_datetime(tend)
        while evtNode is not None:
            evt: Event = evtNode.data
            if evt.startTime >= endTime:
                break
            evtList.append(evtNode.data)
            evtNode = evtNode.next
        return evtList

    def get_current_event(self) -> Event:
        """
        Get the current event playing
        @return: event | None
        """
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
        windowStartTime = utils.DatetimeHelper.unix_datetime(ts)
        windowEndTime = utils.DatetimeHelper.unix_datetime(te)
        currentNode: Node = self.head
        while currentNode is not None:
            currentEvent: Event = currentNode.data
            if windowStartTime >= currentEvent.startTime:  # start of event before start of window
                if currentEvent.endTime > windowStartTime:  # end of event beyond start of window
                    return currentNode
            if windowStartTime < currentEvent.startTime < windowEndTime:
                return currentNode
            if currentEvent.startTime >= windowStartTime:
                return None
            currentNode = currentNode.next
        return None
