import binascii
from datetime import datetime
from enum import Enum, IntEnum
import threading
import time
from typing import Any
import requests
import json
import pickle

import xbmc
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
        date_time_max = datetime(2035, 12, 31, 0, 0)
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


class ProxyHelper:
    def __init__(self, addon: xbmcaddon.Addon):
        self.port = addon.getSetting('proxy-port')
        self.ip = addon.getSetting('proxy-ip')
        self.host = 'http://{0}:{1}/'.format(self.ip, self.port)

    def dynamicCall(self, method, **kwargs) -> Any:
        """
        Helper function to call a function in the service which is running.
        If successful, the response will be the response from the called function.
        On failure, a WebException will be raised, which contains the response from
        the server.

        method: the function to be called e.g. LoginSession.login
        kwargs: the named arguments of the function to be called.

        example: helper.dynamicCall(LoginSession.login,username='a',password='b'
        """
        from resources.lib.webcalls import WebException
        try:
            if kwargs is None:
                arguments = {}
            else:
                arguments = kwargs
            response = requests.get(
                url=self.host + 'function/{method}'.format(method=method.__name__),
                params={'args': json.dumps(arguments)},
                timeout=60)
            if response.status_code != 200:
                raise WebException(response)
            contentType = response.headers.get('content-type')
            if contentType == 'text/html':
                return response.content
            elif contentType == 'application/octet-stream':
                result = pickle.loads(response.content)
                return result
            else:
                return None
        except WebException as exc:
            raise exc
        except Exception as exc:
            xbmc.log('Exception during dynamic Call: {0}'.format(exc), xbmc.LOGERROR)


if __name__ == '__main__':
    pass
