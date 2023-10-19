import binascii


def hexlify(barr):
    binascii.hexlify(bytearray(barr))


def ah2b(s):
    return bytes.fromhex(s)


def b2ah(barr):
    return barr.hex()


def atoh(barr):
    return "".join("{:02x}".format(ord(c)) for c in barr)


def main():
    pass


import threading
import time


class Timer(threading.Thread):

    def __init__(self, interval, callback_function=None):
        self._timer_runs = threading.Event()
        self._timer_runs.set()
        self.interval = interval
        self.callback_function = callback_function
        super().__init__()

    def run(self):
        while self._timer_runs.is_set():
            time.sleep(self.interval)
            self.timer()

    def stop(self):
        self._timer_runs.clear()

    def timer(self):
        self.callback_function()


if __name__ == '__main__':
    pass
