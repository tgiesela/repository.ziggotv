import xbmc

from resources.lib.servicemonitor import ServiceMonitor

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
    monitor_service = ServiceMonitor()
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
    monitor_service.shutdown()
