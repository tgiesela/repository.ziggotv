"""
Module containing function to be used from context menus.
Mainly recording related
"""
import argparse
from urllib.parse import unquote

import xbmc
import xbmcaddon

from resources.lib.webcalls import LoginSession
from resources.lib.utils import ProxyHelper


def delete_single_recording(recordingId, recType):
    """
    Delete a single recording
    @param recordingId: id of the series/show recording
    @param recType: type of recording (planned vs recorded)
    @return: nothing
    """
    helper = ProxyHelper(xbmcaddon.Addon('plugin.video.ziggotv'))
    event = recordingId
    if recType == 'planned':
        helper.dynamic_call(LoginSession.delete_recordings_planned, event=event)
    else:
        helper.dynamic_call(LoginSession.delete_recordings, event=event)
    xbmc.log("Recording with id {0} deleted".format(recordingId), xbmc.LOGDEBUG)


def delete_season_recording(seasonId, recType, channelId):
    """
    Delete a series/show recording
    @param channelId: the channel on which the show occurs
    @param seasonId: id of the series/show recordings
    @param recType: type of recording (planned vs recorded)
    @return: nothing
    """
    helper = ProxyHelper(xbmcaddon.Addon('plugin.video.ziggotv'))
    if recType == 'planned':
        helper.dynamic_call(LoginSession.delete_recordings_planned,
                            show=seasonId,
                            channelId=channelId)
    else:
        helper.dynamic_call(LoginSession.delete_recordings,
                            show=seasonId,
                            channelId=channelId)
    xbmc.log("Recording of complete show with id {0} deleted".format(seasonId), xbmc.LOGDEBUG)


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", help="one of delete")
    parser.add_argument("--type", help="one of recording, season")
    parser.add_argument("--id", help="id of recording")
    parser.add_argument("--rectype", help="type of recording: planned or recorded")
    parser.add_argument("--channel", help="channel on which a season is recorded", default='')
    args = parser.parse_args()
    if args.action == 'delete':
        if args.type == 'season':
            delete_season_recording(unquote(args.id), args.rectype, args.channel)
        elif args.type == 'recording':
            delete_single_recording(unquote(args.id), args.rectype)
    xbmc.executebuiltin('Container.Refresh')
