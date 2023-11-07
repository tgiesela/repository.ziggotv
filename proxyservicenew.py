import asyncio
import sys
import threading
from resources.lib.servicemonitor import ServiceMonitor

async def main():
    lock = threading.Lock()
    monitor = ServiceMonitor(loop)
    await monitor.run()
    print("STOPPING PROXY SERVICE")
    await asyncio.sleep(100)
    await monitor.stop_proxy()

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
    # loop = asyncio.get_event_loop()

    if sys.platform == "win32" and sys.version_info >= (3, 8, 0):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.modules['_asyncio'] = None
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(main())

