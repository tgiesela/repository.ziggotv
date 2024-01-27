import unittest
from time import sleep

from resources.lib import utils
from resources.lib.recording import SavedStateList
from tests.test_base import TestBase

tmr: utils.Timer
tmr_runs = False


def timer_func():
    global tmr_runs
    print("Timer_expired")


def timer_stopit():
    global tmr
    global tmr_runs
    tmr.stop()
    print("Other timer stopped")
    tmr_runs = False


class TestVideoPlayer(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_times(self):
        rslt = utils.DatetimeHelper.toUnix('2021-06-03T18:01:16.974Z', '%Y-%m-%dT%H:%M:%S.%fZ')
        self.assertEqual(rslt, 1622736076)
        print(rslt)

    def test_timer(self):
        global tmr
        global tmr_runs
        tmr = utils.Timer(50, timer_func)
        tmr.start()
        tmr_runs = True

        stop_tmr = utils.Timer(5, timer_stopit)
        stop_tmr.start()
        while tmr_runs:
            sleep(1)
        stop_tmr.stop()


class TestSavedStates(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_login()

    def test_states(self):
        list = SavedStateList(self.addon)
        list.add('crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000~~2F237133469,'
                 'imi:517366be71fa5106c9215d9f1367cbacef4a4772', 350.000)
        list.add('crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000~~2F237133469,'
                 'imi:517366be71fa5106c9215d9f1367cbacef4a4772', 400.000)
        list.add('crid:~~2F~~2Fgn.tv~~3F817615~~2FSH010806510000~~2F237133469,'
                 'imi:517366be71fa5106c9215d9f1367cbacef4a4772', 350.000)
        list.delete('unknown')
        list.delete('crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000~~2F237133469,'
                 'imi:517366be71fa5106c9215d9f1367cbacef4a4772')
        list.cleanup(0)
        list = SavedStateList(self.addon)
        list.cleanup()


if __name__ == '__main__':
    unittest.main()
