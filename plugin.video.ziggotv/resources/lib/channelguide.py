"""
Module for a channel guide containing channels with events
"""
import datetime
import json
from pathlib import Path

from resources.lib.channel import Channel
from resources.lib.events import Event, EventList
from resources.lib.webcalls import LoginSession
from resources.lib.globals import G
from resources.lib.utils import ProxyHelper, DatetimeHelper

import xbmc
import xbmcvfs
import xbmcaddon


class ChannelGuide:
    """
    class implementing obtaining and consulting the events for all the channels
    """
    class GuideWindow:
        """
        class holding the obtained json data for a specific event-window (6 hours)
        """
        def __init__(self, date=None):
            self.isProcessed = False
            self.data = None
            self.startDate = None
            self.endDate = None
            if date is None:
                self.__set_window(datetime.datetime.now().astimezone(datetime.timezone.utc))
            else:
                self.__set_window(date)

        def __set_window(self, dt: datetime.datetime):
            self.startDate = dt.replace(hour=int(dt.hour / 6) * 6, minute=0, second=0, microsecond=0)
            self.endDate = self.startDate + datetime.timedelta(hours=6)

        def date_in_window(self, evtDate: datetime.datetime):
            """
            test if a specific date falls within this window
            @param evtDate: datetime in utc which is to be tested
            @return:
            """
            if self.startDate <= evtDate < self.endDate:
                return True
            return False

        def next_window(self):
            """
            Gets the next event-window (e.g. adds 6 hours to it own datetime)
            @return: the next event-window in utc timezone
            """
            return self.startDate + datetime.timedelta(hours=6)

        def previous_window(self):
            """
            Gets the previous event-window (e.g. subtracts 6 hours to it own datetime)
            @return: the next event-window in utc timezone
            """
            return self.startDate - datetime.timedelta(hours=6)

        def set_data(self, data):
            """
            sets the events in json format
            @param data:
            @return: nothing
            """
            self.data = data

        def get_data(self):
            """
            gets the events in json format
            @return: events in json format
            """
            return self.data

        @property
        def processed(self) -> bool:
            """
            property indicating if the data was processed
            @return: True/False
            """
            return self.isProcessed

        @processed.setter
        def processed(self, value: bool):
            self.isProcessed = value

    def __init__(self, addon: xbmcaddon.Addon, channels):
        self.eventsJson = {}
        self.addon = addon
        self.addonPath = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        self.helper = ProxyHelper(self.addon)
        self.windows = []
        self.channels = channels.copy()

    def __current_window(self):
        dtNow = datetime.datetime.now().astimezone(datetime.timezone.utc)
        for w in self.windows:
            window: ChannelGuide.GuideWindow = w
            if window.date_in_window(dtNow):
                return w
        currentWindow = ChannelGuide.GuideWindow(dtNow)
        return currentWindow

    def __is_window_present(self, evtDate: datetime.datetime):
        for w in self.windows:
            window: ChannelGuide.GuideWindow = w
            if window.date_in_window(evtDate):
                return True
        return False

    def __find_window(self, evtDate: datetime.datetime) -> GuideWindow:
        for w in self.windows:
            window: ChannelGuide.GuideWindow = w
            if window.date_in_window(evtDate):
                return w
        return None

    def __process_events(self, window):
        # from resources.lib.channel import Channel
        for channel in window.get_data():
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
                    currentChannel.events.insert_event(evt)
            else:
                xbmc.log('No events', xbmc.LOGDEBUG)
        window.processed = True

    def __obtain_events(self, window: GuideWindow):
        """
            Obtain events not yet stored in epg.json and append them
            to the internal events. Update the channels with the new events

            @param window:
                window with startDate for the events
        """
        response = self.helper.dynamic_call(LoginSession.get_events,
                                            startTime=window.startDate.strftime('%Y%m%d%H%M%S'))
        self.windows.append(window)
        window.set_data(response['entries'])
        self.__append_events(response, window.startDate)
        self.__process_events(window)

    def obtain_events(self):
        """
        Function to obtain the events in the current window (based on current datetime)
        Use getEvents to get the results
        @return:
        """
        window = self.__current_window()
        if self.__is_window_present(window.startDate):
            window = self.__find_window(window.startDate)
            if not window.processed:
                self.__process_events(window)
        else:
            self.__obtain_events(window)

    def obtain_events_in_window(self, startDate: datetime, endDate: datetime):
        """
        Function to obtain events in a specific datetime-window
        Use getEvents to get the results
        @param startDate: start datetime of the window in utc
        @param endDate:end datetime of the window in utc
        @return: nothing
        """
        if self.__is_window_present(startDate):
            startWindow = self.__find_window(startDate)
            if not startWindow.processed:
                self.__process_events(startWindow)
        else:
            startWindow = ChannelGuide.GuideWindow(startDate)
            self.__obtain_events(startWindow)

        if self.__is_window_present(endDate):
            endWindow = self.__find_window(endDate)
            if not endWindow.processed:
                self.__process_events(endWindow)
        else:
            endWindow = ChannelGuide.GuideWindow(endDate)
            self.__obtain_events(endWindow)

        nextWindow = ChannelGuide.GuideWindow(startWindow.next_window())
        while nextWindow.startDate < endWindow.startDate:
            self.__obtain_events(nextWindow)
            nextWindow = ChannelGuide.GuideWindow(nextWindow.next_window())

    def get_events(self, channelId) -> EventList:
        """
        Get the events for a specific channel. obtain_events*** must be called before
        @param channelId:
        @return: Events for the channel
        """
        for channel in self.channels:
            if channel.id == channelId:
                return channel.events
        return EventList()

    def __append_events(self, response, startTime):
        if 'segments' not in self.eventsJson:
            self.eventsJson = {'segments': []}
        for segment in self.eventsJson['segments']:
            if segment['starttime'] == DatetimeHelper.unix_datetime(startTime):
                self.eventsJson['segments'].remove(segment)
        self.eventsJson['segments'].append({'starttime': DatetimeHelper.unix_datetime(startTime),
                                            'events': response})

    def __plugin_path(self, name):
        return self.addonPath + name

    def load_stored_events(self):
        """
        Function to load the events stored on disk. The data is split into windows (segments).
        @return: nothing
        """
        self.windows = []
        if Path(self.__plugin_path(G.GUIDE_INFO)).exists():
            epgStr = Path(self.__plugin_path(G.GUIDE_INFO)).read_text(encoding='utf-8')
        else:
            epgStr = ''
        if epgStr is None or epgStr == '':
            self.eventsJson = {'segments': []}
        else:
            self.eventsJson = json.loads(epgStr)
            self.__clean_events()
            for segment in self.eventsJson['segments']:
                dt = DatetimeHelper.from_unix(segment['starttime'])
                dt = dt.replace(tzinfo=datetime.timezone.utc)
                window = ChannelGuide.GuideWindow(dt)
                window.set_data(segment['events']['entries'])
                self.windows.append(window)
                # self.__processEvents(window)

    def __reprocess(self):
        for channel in self.channels:
            channel.events = EventList()
        for w in self.windows:
            window: ChannelGuide.GuideWindow = w
            if window.processed:
                self.__process_events(window)

    def __clean_events(self):
        for segment in self.eventsJson['segments']:
            oldestTime = datetime.datetime.now() + datetime.timedelta(days=-5)
            if segment['starttime'] < DatetimeHelper.unix_datetime(oldestTime):
                self.eventsJson['segments'].remove(segment)
        self.__reprocess()

    #        Path(self.pluginPath(G.GUIDE_INFO)).write_text(json.dumps(self.eventsJson))

    def store_events(self):
        """
        Stores the events in json format to disk. Can be loaded via load_stored_events()
        @return: nothing
        """
        Path(self.__plugin_path(G.GUIDE_INFO)).write_text(json.dumps(self.eventsJson), encoding='utf-8')
