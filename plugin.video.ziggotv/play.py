import xbmc
import xbmcaddon
import sys

from resources.lib.Channel import Channel
from resources.lib.ZiggoPlayer import VideoHelpers
from resources.lib.events import ChannelGuide
from resources.lib.utils import ProxyHelper
from resources.lib.webcalls import LoginSession


def play(playType, path):
    """
    Routine to play a channel or a video on demand (vod)
    The routine will stay active as long as the video is playing. This avoids
    that our ZiggoPlayer is replaced by the standard VideoPlayer. Probable cause
    is that the instance of ZiggoPlayer is destroyed when the script ends

    @param playType: one of 'channel', 'vod'
    @param path: for channel: channel.id for vod the id of the movie
    @return:
    """
    helper = ProxyHelper(addon)
    videoHelper = VideoHelpers(addon)
    epg = ChannelGuide(addon)
    channels = helper.dynamicCall(LoginSession.get_channels)
    channel: Channel = None
    for c in channels:
        if c.id == path:
            channel = c
            break

    if channel is None:
        raise RuntimeError("Channel not found: " + path)

    try:
        epg.loadEvents()
        channel.events = epg.getEvents(channel.id)
        if playType == 'channel':
            videoHelper.play_channel(channel=channel)
        elif playType == 'vod':
            videoHelper.play_movie(path)
        else:
            return
        while xbmc.Player().isPlaying():
            xbmc.sleep(500)
    except Exception as exc:
        xbmc.log('Error in play script: {0}'.format(exc))


REMOTE_DEBUG = False
if __name__ == '__main__':
    # if REMOTE_DEBUG:
    #     try:
    #         sys.path.append('E:\Eclipse IDE\eclipse\plugins\org.python.pydev.core_10.2.1.202307021217\pysrc')
    #         import pydevd
    #
    #         pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
    #     except:
    #         sys.stderr.write("Error: " + "You must add org.python.pydev.debug.pysrc to your PYTHONPATH")
    #         sys.stderr.write("Error: " + "Debug not available")
    addonid = sys.argv[1]
    addon = xbmcaddon.Addon(addonid)
    xbmc.executebuiltin('Dialog.Close(busydialog)', True)
    play(sys.argv[2], sys.argv[3])
    xbmc.log('Play script terminated')
