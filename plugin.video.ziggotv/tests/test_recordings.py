import datetime
import unittest

from resources.lib.channel import ChannelList, Channel
from resources.lib.channel import ChannelGuide
from resources.lib.recording import Recording, RecordingList, SingleRecording, SeasonRecording, PlannedRecording
from tests.test_base import TestBase


class TestRecordings(TestBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_login()

    def print_recordings(self, recs: RecordingList):
        print('#: {0}, size: {1}, quota: {2}, used: {3}'.format(recs.total,
                                                                recs.size,
                                                                recs.quota,
                                                                recs.occupied))
        for rec in recs.recs:
            if type(rec) is SingleRecording:
                print('Single {0}: {1}'.format(rec.title, rec.recordingState))
            elif type(rec) is PlannedRecording:
                print('Planned {0}: {1}'.format(rec.title, rec.recordingState))
            elif type(rec) is SeasonRecording:
                season: SeasonRecording = rec
                print('Season {0} #: {1}'.format(season.title, season.episodes))
                for episode in season.get_episodes('planned'):
                    print(season.title + ' ' + episode.startTime)
                for episode in season.get_episodes('recorded'):
                    print(season.title + ' ' + episode.startTime)

    def test_planned(self):
        self.session.refresh_recordings(True)
        recs = self.session.get_recordings_planned()
        self.print_recordings(recs)
        for rec in recs.recs:
            if type(rec) is SeasonRecording:
                print('SHOW ' + rec.title + '\n')
                season: SeasonRecording = rec
                for episode in season.episodes:
                    print(season.title + ' ' + episode.startTime)

    def test_recorded(self):
        self.session.refresh_recordings(True)
        recs = self.session.get_recordings()
        self.print_recordings(recs)

    def test_record(self):
        self.session.refresh_channels()
        self.session.refresh_entitlements()
        self.session.refresh_recordings(False)
        recs = self.session.get_recordings()
        self.print_recordings(recs)
        epg = ChannelGuide(self.addon, self.session.get_channels())
        epg.load_stored_events()
        epg.obtain_events()
        channels = ChannelList(self.session.get_channels(), self.session.get_entitlements())
        npo1: Channel = None
        for channel in channels:
            if channel.name == 'NPO 1':
                npo1 = channel
                break
        self.assertIsNotNone(npo1)
        npo1.events = epg.get_events(npo1.id)
        # currentEvent = npo1.events.getCurrentEvent()
        windowEvents = npo1.events.get_events_in_window(datetime.datetime.now(),
                                                        datetime.datetime.now() + datetime.timedelta(hours=2))
        self.assertTrue(len(windowEvents) >= 2)
        rec1 = self.session.record_event(windowEvents[0].id)
        print(rec1)
        rec2 = self.session.record_event(windowEvents[1].id)
        print(rec2)
        recs = self.session.get_recordings()
        self.print_recordings(recs)
        recs = self.session.get_recordings_planned()
        self.print_recordings(recs)
        rslt = self.session.delete_recordings(events=[windowEvents[0].id], shows=[])
        print(rslt)
        rslt = self.session.delete_recordings(events=[windowEvents[1].id], shows=[])
        print(rslt)


if __name__ == '__main__':
    unittest.main()
