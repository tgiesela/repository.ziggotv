# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
import unittest
import datetime

from resources.lib import utils
from resources.lib.channelguide import ChannelGuide
from resources.lib.events import EventList
from tests.test_base import TestBase


class TestEvents(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_events(self):
        self.do_login()
        self.session.refresh_channels()

        guide = ChannelGuide(self.addon, self.session.get_channels())
        guide.load_stored_events()

        for channel in self.session.get_channels():
            channel.events = guide.get_events(channel.id)

        startDate = datetime.datetime.now()
        endDate = startDate + datetime.timedelta(hours=2)
        guide.obtain_events_in_window(startDate.astimezone(datetime.timezone.utc),
                                      endDate.astimezone(datetime.timezone.utc))

        for channel in self.session.get_channels():
            channel.events = guide.get_events(channel.id)

        latestEndDate = endDate
        startDate = startDate + datetime.timedelta(days=-6)
        oldestStartDate = startDate
        endDate = startDate + datetime.timedelta(hours=2)
        guide.obtain_events_in_window(startDate.astimezone(datetime.timezone.utc),
                                      endDate.astimezone(datetime.timezone.utc))
        startDate = startDate + datetime.timedelta(hours=6)
        endDate = startDate + datetime.timedelta(hours=2)
        guide.obtain_events_in_window(startDate.astimezone(datetime.timezone.utc),
                                      endDate.astimezone(datetime.timezone.utc))
        guide.store_events()
        channels = []
        for channel in self.session.get_channels():
            channel.events = guide.get_events(channel.id)
            events: EventList = channel.events
            if events is not None and events.head is not None:
                event = events.head.data
                event.details = self.session.get_event_details(event.id)
            channels.append(channel)

        for channel in channels:
            print('Channel id: {0}, name: {1}'.format(channel.id, channel.name))
            evts = channel.events.get_events_in_window(oldestStartDate, latestEndDate)
            for evt in evts:
                print('    Event: {0}, duration: {1}, start: {2}, end: {3}'.format(
                    evt.title,
                    evt.duration,
                    utils.DatetimeHelper.from_unix(evt.startTime).strftime('%y-%m-%d %H:%M'),
                    utils.DatetimeHelper.from_unix(evt.endTime).strftime('%y-%m-%d %H:%M')))
            # evt = channel.events.__findEvent(datetime.datetime.now())
            # if evt is not None:
            #    print('    Current event: {0}: start: {1}, end: {2}'.format(evt.data.title
            #                                                                , evt.data.startTime
            #                                                               , evt.data.endTime))


if __name__ == '__main__':
    unittest.main()
