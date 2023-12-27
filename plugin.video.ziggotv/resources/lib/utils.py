import binascii
from datetime import datetime
from enum import Enum, IntEnum
import threading
import time
import xbmcaddon
import xbmcgui


def hexlify(barr):
    binascii.hexlify(bytearray(barr))


def ah2b(s):
    return bytes.fromhex(s)


def b2ah(barr):
    return barr.hex()


def atoh(barr):
    return "".join("{:02x}".format(ord(c)) for c in barr)


class ServiceStatus(IntEnum):
    STARTING = 1,
    STOPPING = 2,
    STARTED = 3,
    STOPPED = 4


class SharedProperties:
    def __init__(self, addon: xbmcaddon.Addon):
        self.addon: xbmcaddon.Addon = addon
        self.window: xbmcgui.Window = xbmcgui.Window(10000)

    def setServiceStatus(self, status: ServiceStatus):
        self.window.setProperty(self.addon.getAddonInfo('id') + 'ServiceStatus', str(status.value))

    def isServiceActive(self) -> bool:
        if self.window.getProperty(self.addon.getAddonInfo('id') + 'ServiceStatus') == str(ServiceStatus.STARTED.value):
            return True
        else:
            return False


class Timer(threading.Thread):

    def __init__(self, interval, callback_function=None):
        self._timer_runs = threading.Event()
        self._timer_runs.set()
        self.interval = interval
        self.callback_function = callback_function
        super().__init__()

    def run(self):
        expired_secs = 0
        while self._timer_runs.is_set():
            time.sleep(1)
            expired_secs += 1
            if expired_secs >= self.interval:
                self.timer()
                expired_secs = 0

    def stop(self):
        self._timer_runs.clear()
        self.join()

    def timer(self):
        self.callback_function()


class DatetimeHelper:
    @staticmethod
    def fromUnix(unix_time: int, tz: datetime.tzinfo = None) -> datetime:
        date_time_max = datetime(2100, 12, 31, 0, 0)
        max_unix_time_in_secs = time.mktime(date_time_max.timetuple())
        if unix_time > max_unix_time_in_secs:
            return datetime.fromtimestamp(unix_time / 1000, tz)
        else:
            return datetime.fromtimestamp(unix_time, tz)

    @staticmethod
    def now(tz: datetime.tzinfo = None) -> datetime:
        return datetime.now(tz)

    @staticmethod
    def toUnix(dt: str, dt_format: str):
        return int(time.mktime(datetime.strptime(dt, dt_format).timetuple()))

    @staticmethod
    def unixDatetime(dt: datetime):
        return int(time.mktime(dt.timetuple()))


if __name__ == '__main__':
    pass
