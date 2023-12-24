import unittest

from resources.lib import utils


class TestVideoPlayer(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_times(self):
        rslt = utils.DatetimeHelper.toUnix('2021-06-03T18:01:16.974Z', '%Y-%m-%dT%H:%M:%S.%fZ')
        self.assertEqual(rslt, 1622736076)
        print(rslt)


if __name__ == '__main__':
    unittest.main()
