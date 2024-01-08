import threading
from resources.lib.servicemonitor import ServiceMonitor, HttpProxyService

import xbmc
import xbmcaddon


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
    lock = threading.Lock()
    proxy_service = HttpProxyService(lock)
    port = xbmcaddon.Addon().getSettingNumber('proxy-port')
    ip = xbmcaddon.Addon().getSetting('proxy-ip')
    proxy_service.set_address((ip, int(port)))
    proxy_service.clearBrowserLock()
    monitor_service = ServiceMonitor(proxy_service, lock)
    proxy_service.startHttpServer()
    try:
        while not monitor_service.abortRequested():
            # Sleep/wait for abort for 5 seconds
            if monitor_service.waitForAbort(5):
                # Abort was requested while waiting. We should exit
                xbmc.log("MONITOR PROXYSERVICE WAITFORABORT timeout", xbmc.LOGINFO)
                break

    except:
        pass
    xbmc.log("STOPPING PROXYSERVICE", xbmc.LOGINFO)
    proxy_service.stopHttpServer()
