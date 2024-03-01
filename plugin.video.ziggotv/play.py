"""
Attempt to play a video file from a script
"""
import sys
import xbmc
import xbmcaddon

from resources.lib.channel import Channel
from resources.lib.ziggoplayer import VideoHelpers
from resources.lib.channelguide import ChannelGuide
from resources.lib.utils import ProxyHelper
from resources.lib.webcalls import LoginSession


def play(playType, path, addon):
    """
    Routine to play a channel or a video on demand (vod)
    The routine will stay active as long as the video is playing. This avoids
    that our ZiggoPlayer is replaced by the standard VideoPlayer. Probable cause
    is that the instance of ZiggoPlayer is destroyed when the script ends

    @param addon: the xbmcaddon.Addon()
    @param playType: one of 'channel', 'vod'
    @param path: for channel: 'channel.id' for vod the id of the movie
    @return:
    """
    helper = ProxyHelper(addon)
    videoHelper = VideoHelpers(addon)
    channels = helper.dynamic_call(LoginSession.get_channels)
    epg = ChannelGuide(addon, channels)
    channel: Channel = None
    for c in channels:
        if c.id == path:
            channel = c
            break

    if channel is None:
        raise RuntimeError("Channel not found: " + path)

    try:
        # epg.load_stored_events()
        channel.events = epg.get_events(channel.id)
        if playType == 'channel':
            videoHelper.play_channel(channel=channel)
        elif playType == 'vod':
            videoHelper.play_movie(path)
        else:
            return
        while xbmc.Player().isPlaying():
            xbmc.sleep(500)
    # pylint: disable=broad-exception-caught
    except Exception as exc:
        xbmc.log(f'Error in play script: {exc}')


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
    xbmc.executebuiltin('Dialog.Close(busydialog)', True)
    play(sys.argv[2], sys.argv[3], xbmcaddon.Addon(addonid))
    xbmc.log('Play script terminated')
