import asyncio
import sys
import threading

import requests
import xbmc

from resources.lib.proxy import ProxyServer
from resources.lib.servicemonitor import ServiceMonitor


async def start_service():
    lock = threading.Lock()
    proxy = ProxyServer(lock)
    proxy.serve_forever()
    monitor_service = ServiceMonitor(proxy)
    try:
        print("SERVICE-MONITOR loop entered ")
        while not monitor_service.abortRequested():
            if monitor_service.waitForAbort(10):
                # Abort was requested while waiting. We should exit
                xbmc.log("MONITOR PROXYSERVICE WAITFORABORT timeout", xbmc.LOGDEBUG)
                break
    except Exception as exc:
        print("SERVICE-MONITOR Exception: ", exc)
    try:
        requests.delete('http://127.0.0.1:6969/shutdown')
    except Exception as exc:
        pass

REMOTE_DEBUG = False
if __name__ == '__main__':
    # if REMOTE_DEBUG:
    #     try:
    #         sys.path.append('E:\Eclipse IDE\eclipse\plugins\org.python.pydev.core_10.2.1.202307021217\pysrc')
    #         import pydevd
    #         pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
    #     except:
    #         sys.stderr.write("Error: " + "You must add org.python.pydev.debug.pysrc to your PYTHONPATH")
    #         sys.stderr.write("Error: " + "Debug not available")
    # else:
    #     import web_pdb
    #     web_pdb.set_trace()
    if sys.platform == "win32" and sys.version_info >= (3, 8, 0):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    sys.modules['_asyncio'] = None
    loop.run_until_complete(start_service())
