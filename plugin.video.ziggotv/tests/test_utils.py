# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring

import unittest
from time import sleep

from resources.lib import utils
from resources.lib.recording import SavedStateList
from tests.test_base import TestBase


def timer_func():
    print("Timer_expired")


class TestVideoPlayer(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tmr: utils.Timer
        self.tmrRuns = False

    def timer_stopit(self):
        self.tmr.stop()
        print("Other timer stopped")
        self.tmrRuns = False

    def test_times(self):
        rslt = utils.DatetimeHelper.to_unix('2021-06-03T18:01:16.974Z', '%Y-%m-%dT%H:%M:%S.%fZ')
        self.assertEqual(rslt, 1622736076)
        print(rslt)

    def test_timer(self):
        self.tmr = utils.Timer(50, timer_func)
        self.tmr.start()
        self.tmrRuns = True

        stopTmr = utils.Timer(5, self.timer_stopit)
        stopTmr.start()
        while self.tmrRuns:
            sleep(1)
        stopTmr.stop()


class TestSavedStates(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_login()

    def test_states(self):
        recList = SavedStateList(self.addon)
        recList.add('crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000~~2F237133469,'
                    'imi:517366be71fa5106c9215d9f1367cbacef4a4772', 350.000)
        recList.add('crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000~~2F237133469,'
                    'imi:517366be71fa5106c9215d9f1367cbacef4a4772', 400.000)
        recList.add('crid:~~2F~~2Fgn.tv~~3F817615~~2FSH010806510000~~2F237133469,'
                    'imi:517366be71fa5106c9215d9f1367cbacef4a4772', 350.000)
        recList.delete('unknown')
        recList.delete('crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000~~2F237133469,'
                       'imi:517366be71fa5106c9215d9f1367cbacef4a4772')
        recList.cleanup(0)
        recList = SavedStateList(self.addon)
        recList.cleanup()


if __name__ == '__main__':
    unittest.main()
