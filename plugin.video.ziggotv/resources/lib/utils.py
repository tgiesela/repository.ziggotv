import binascii
from datetime import datetime
from enum import IntEnum
import threading
import time
from typing import Any
import requests
import json
import pickle
import uuid

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
    STARTING = 1
    STOPPING = 2
    STARTED = 3
    STOPPED = 4


class SharedProperties:
    def __init__(self, addon: xbmcaddon.Addon):
        self.addon: xbmcaddon.Addon = addon
        self.window: xbmcgui.Window = xbmcgui.Window(10000)

    def set_service_status(self, status: ServiceStatus):
        self.window.setProperty(self.addon.getAddonInfo('id') + 'ServiceStatus', str(status.value))

    def is_service_active(self) -> bool:
        return self.window.getProperty(
                    self.addon.getAddonInfo('id') + 'ServiceStatus') == str(ServiceStatus.STARTED.value)

    def set_uuid(self):
        self.window.setProperty(self.addon.getAddonInfo('id') + 'UUID',
                                str(uuid.UUID(hex=hex(uuid.getnode())[2:]*2+'00000000')))

    def get_uuid(self):
        return self.window.getProperty(self.addon.getAddonInfo('id') + 'UUID')


class Timer(threading.Thread):

    def __init__(self, interval, callback_function=None):
        self.timerRuns = threading.Event()
        self.timerRuns.set()
        self.interval = interval
        self.callbackFunction = callback_function
        super().__init__()

    def run(self):
        expiredSecs = 0
        while self.timerRuns.is_set():
            time.sleep(1)
            expiredSecs += 1
            if expiredSecs >= self.interval:
                self.timer()
                expiredSecs = 0

    def stop(self):
        self.timerRuns.clear()
        self.join()

    def timer(self):
        self.callbackFunction()


class DatetimeHelper:
    @staticmethod
    def from_unix(unixTime: int, tz: datetime.tzinfo = None) -> datetime:
        dateTimeMax = datetime(2035, 12, 31, 0, 0)
        maxUnixTimeInSecs = time.mktime(dateTimeMax.timetuple())
        if unixTime > maxUnixTimeInSecs:
            return datetime.fromtimestamp(unixTime / 1000, tz)
        return datetime.fromtimestamp(unixTime, tz)

    @staticmethod
    def now(tz: datetime.tzinfo = None) -> datetime:
        return datetime.now(tz)

    @staticmethod
    def to_unix(dt: str, dtFormat: str):
        return int(time.mktime(datetime.strptime(dt, dtFormat).timetuple()))

    @staticmethod
    def unix_datetime(dt: datetime):
        return int(time.mktime(dt.timetuple()))


class ProxyHelper:
    def __init__(self, addon: xbmcaddon.Addon):
        self.port = addon.getSetting('proxy-port')
        self.ip = addon.getSetting('proxy-ip')
        self.host = 'http://{0}:{1}/'.format(self.ip, self.port)

    def dynamic_call(self, method, **kwargs) -> Any:
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
            if contentType == 'application/octet-stream':
                result = pickle.loads(response.content)
                return result
            return None
        except WebException as exc:
            raise exc
        except Exception as exc:
            xbmc.log('Exception during dynamic Call: {0}'.format(exc), xbmc.LOGERROR)
            return None


if __name__ == '__main__':
    pass
