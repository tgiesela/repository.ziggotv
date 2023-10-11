import base64
import json
import sys
import urllib.parse
from pathlib import Path
from urllib.parse import parse_qsl
from resources.lib.sharedcache import SharedCache
from resources.lib.globals import G
# from resources.lib.parser import ProtoParser

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from xbmcaddon import Addon

try:
    from inputstreamhelper import Helper
except:
    pass

from resources.lib.webcalls import LoginSession

channels = {}
session_info = {}
PROTOCOL = 'mpd'
DRM = 'com.widevine.alpha'


def build_url(channel, streaming_token):
    avc = channel["locator"]
    avc = avc.replace("/dash", "/dash,vxttoken=" + streaming_token).replace("http://", "https://")
    #    response = session.do_get(avc)
    #    if response.status_code != 200:
    #        raise RuntimeError("status code <> 200 during load manifest.mpd")

    return avc


def plugin_initialization():
    global channels
    global session_info
    addon_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    Path(addon_path).mkdir(parents=True, exist_ok=True)
    if addon.getSetting('username') == '#notset#' or addon.getSetting('username') == '':
        print("Attempt to open settings")
        xbmcaddon.Addon().openSettings()
    if addon.getSetting('username') == '':
        username = json.loads(Path(r'C:\temp\credentials.json').read_text())['username']
        password = json.loads(Path(r'C:\temp\credentials.json').read_text())['password']
    else:
        username = addon.getSetting('username')
        password = addon.getSetting('password')

    session_info = session.login(username, password)
    if len(session_info) == 0:
        raise RuntimeError("Login failed, check your credentials")
    session.refresh_widevine_license()
    session.refresh_entitlements()

    xbmc.log("ADDON: {0}, authenticated with: {1}".format(addon.getAddonInfo('name'),
                                                          username), 0)


def list_categories():
    """
    Create the list of video categories in the Kodi interface.
    :return: None
    """
    # Get video categories
    categories = {'Channels', 'Series'}
    # Create a list for our items.
    listing = []
    # Iterate through categories
    for category in categories:
        # Create a list item with a text label and a thumbnail image.
        list_item = xbmcgui.ListItem(label=category)
        # Set additional info for the list item.
        # Here we use a category name for both properties for simplicity's sake.
        # setInfo allows to set various information for an item.
        # For available properties see the following link:
        # http://mirrors.xbmc.org/docs/python-docs/15.x-isengard/xbmcgui.html#ListItem-setInfo
        tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
        tag.setTitle(category)
        tag.setMediaType('video')
        tag.setGenres([category])
        # list_item.setInfo('video', {'title': category, 'genre': category})
        # Create a URL for the plugin recursive callback.
        # Example: plugin://plugin.video.example/?action=listing&category=Animals
        url = '{0}?action=listing&category={1}'.format(__url__, category)
        # is_folder = True means that this item opens a sub-list of lower level items.
        is_folder = True
        # Add our item to the listing as a 3-element tuple.
        listing.append((url, list_item, is_folder))
    # Add our listing to Kodi.
    # Large lists and/or slower systems benefit from adding all items at once via addDirectoryItems
    # instead of adding one by ove via addDirectoryItem.
    xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(__handle__)


def list_channels():
    global channels
    # Create a list for our items.
    listing = []
    session.refresh_channels()
    channels = session.get_channels()

    # Iterate through channels
    for video in channels:  # create a list item using the song filename for the label
        if 'isHidden' in video:
            if video['isHidden']:
                continue
        li = listitem_from_channel(video)
        callback_url = '{0}?action=play&video={1}'.format(__url__, video['id'])
        listing.append((callback_url, li, False))
    # Add our listing to Kodi.

    xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(__handle__)


def get_widevine_license(addon_name):
    addon_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    with open(addon_path + "widevine.json", mode="r") as cert_file:
        contents = cert_file.read()

    return contents


def listitem_from_channel(video, url: str = None) -> xbmcgui.ListItem:
    print("ADDON: channel: {0}".format(video['name']))
    if url is None:
        li = xbmcgui.ListItem(label="{0}. {1}".format(video['logicalChannelNumber'], video['name']))
    else:
        li = xbmcgui.ListItem(path=url)
    if len(video['imageStream']) > 0:
        li.setArt({'icon': video['logo']['focused'],
                   'thumb': video['logo']['focused'],
                   'poster': video['imageStream']['full']})
    else:
        li.setArt({'icon': video['logo']['focused'],
                   'thumb': video['logo']['focused']})

    # set the list item to playable
    li.setProperty('IsPlayable', 'true')
    tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
    tag.setTitle("{0}. {1}".format(video['logicalChannelNumber'], video['name']))
    tag.setGenres(video['genre'])
    tag.setSetId(video['logicalChannelNumber'])
    tag.setMediaType('video')
    tag.setUniqueIDs({'ziggochannelid': video['id']})
    li.setProperty('IsPlayable', 'true')
    li.setMimeType('application/dash+xml')
    li.setContentLookup(False)
    li.setProperty(
        key='inputstream',
        value='inputstream.adaptive')
    li.setProperty(
        key='inputstream.adaptive.license_flags',
        value='persistent_storage')
    li.setProperty(
        key='inputstream.adaptive.manifest_type',
        value=PROTOCOL)
    li.setProperty(
        key='inputstream.adaptive.license_type',
        value=DRM)

    return li


def send_notification(item: xbmcgui.ListItem, token):
    tag: xbmc.InfoTagVideo = item.getVideoInfoTag()
    uniqueid = tag.getUniqueID('ziggochannelid')
    params = {'sender': addon.getAddonInfo('id'),
              'message': tag.getTitle(),
              'data': {'command': 'play_video',
                       'command_params': {'uniqueId': uniqueid, 'streamingToken': token}
                       },
              }

    command = json.dumps({'jsonrpc': '2.0',
                          'method': 'JSONRPC.NotifyAll',
                          'params': params,
                          'id': 1,
                          })
    result = xbmc.executeJSONRPC(command)


def play_video(path):
    global channels
    """
    Play a video by the provided path.
    :param path: str
    :return: None
    """
    # Create a playable item with a path to play.
    print('PLAY ITEM: ' + path)

    channels = session.get_channels()
    channel = {}
    for video in channels:
        if video['id'] == path:
            channel = video
            break

    if len(channel) == 0:
        raise RuntimeError("Channel not found: " + path)

    try:
        is_helper = Helper(PROTOCOL, drm=DRM)
        if is_helper.check_inputstream():
            xbmc.log('Inside play condition...')

        streaming_token = session.get_streaming_token(channel)

        url = build_url(channel, streaming_token)
        play_item = listitem_from_channel(channel, url=url)
        # play_item = xbmcgui.ListItem(path=url)

        license_headers = G.CONST_BASE_HEADERS
        # 'Content-Type': 'application/octet-stream',
        license_headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
            'Host': 'prod.spark.ziggogo.tv',
            'x-streaming-token': streaming_token,
            'X-cus': session.customer_info['customerId'],
            'x-go-dev': '214572a3-2033-4327-b8b3-01a9a674f1e0',  # Dummy?
            'x-drm-schemeId': 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
            'deviceName': 'Firefox'
        })
        for key in session.extra_headers:
            license_headers.update({key: session.extra_headers[key]})

        from urllib.parse import urlencode
        use_proxy = True
        if use_proxy:
            url = 'http://127.0.0.1:6969/license'
            params = {'ContentId': session.stream_info['drmContentId'],
                      'addon': addon.getAddonInfo('id')}
            url = (url + '?' + urllib.parse.urlencode(params) +
                   '|' + urllib.parse.urlencode(license_headers) +
                   '|R{SSM}'
                   '|')
        else:
            cookies = session.cookies.get_dict()
            url = G.license_URL
            params = {'ContentId': session.stream_info['drmContentId']}
            url = (url + '?' + urllib.parse.urlencode(params) +
                   '|' + urllib.parse.urlencode(license_headers) +
                   'Cookie=ACCESSTOKEN={0};CLAIMSTOKEN={1}'.format(cookies['ACCESSTOKEN'], cookies['CLAIMSTOKEN']) +
                   '|R{SSM}'
                   '|')
        # Prefix for request {SSM|SID|KID|PSSH}
        # R - The data will be kept as is raw
        # b - The data will be base64 encoded
        # B - The data will be base64 encoded and URL encoded
        # D - The data will be decimal converted (each char converted as integer concatenated by comma)
        # H - The data will be hexadecimal converted (each character converted as hexadecimal and concatenated)
        # Prefix for response
        # -  Not specified, or, R if the response payload is in binary raw format
        # B if the response payload is encoded as base64
        # J[license tokens] if the response payload is in JSON format. You must specify the license tokens
        #    names to allow inputstream.adaptive searches for the license key and optionally the HDCP limit.
        #    The tokens must be separated by ;. The first token must be for the key license, the second one,
        #    optional, for the HDCP limit. The HDCP limit is the result of resolution width multiplied for
        #    its height. For example to limit until to 720p: 1280x720 the result will be 921600.
        # BJ[license tokens] same meaning of J[license tokens] but the JSON is encoded as base64.
        # HB if the response payload is after two return chars \r\n\r\n in binary raw format.

        play_item.setProperty(
            key='inputstream.adaptive.license_key',
            value=url)
        # Test
        # server certificate to be used to encrypt messages to the license server. Should be encoded as Base64
        widevine_certificate = get_widevine_license(addon.getAddonInfo('id'))
        play_item.setProperty(
            key='inputstream.adaptive.server_certificate',
            value=widevine_certificate)
        # From netflix plugin
        # data comes from cenc:pssh tag in MPD file
        # pssh_kid = ('AAAATHBzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAACwIARIQkOMqRxL1SAureryKT'
        #             '+8l2iIUbmxfdHZfc3RhbmRhYXJkX2NlbmM4AA==|') + kid
        # print('PSSH_KID: ', pssh_kid)
        # play_item.setProperty('inputstream.adaptive.pre_init_data', pssh_kid)
        # end netflix plugin
        # End Test

        # Pass the item to the Kodi player.
        # player = xbmc.Player()
        # player.play(play_item.getPath(), play_item, False)
        # xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocus()
        xbmcplugin.setResolvedUrl(__handle__, True, listitem=play_item)
        #  xbmcplugin.setResolvedUrl(__handle__, True, listitem=play_item)
        #  xbmc.Player().onPlayBackStopped()
        #  print(xbmc.Player().isPlaying())
        send_notification(play_item, streaming_token)
        sharedcache = SharedCache()
        sharedcache.setprop(G.VIDEO_PLAYING, 'true')
        sharedcache.setprop(G.VIDEO_ID, path)

    except Exception as exc:
        print(type(exc))
        print(exc.args)
        print(exc)
        pass


def list_series():
    pass


def router(param_string):
    """
        Router function that calls other functions
        depending on the provided param_string
        :param param_string:
        :return:
        """
    # Parse a URL-encoded param_string to the dictionary of
    # {<parameter>: <value>} elements
    params = dict(parse_qsl(param_string[1:]))
    # Check the parameters passed to the plugin
    if params:
        if params['action'] == 'listing':
            # Display the list of videos in a provided category.
            if params['category'] == "Channels":
                list_channels()
                print("ADDON: {0}, Channel-list created".format(addon.getAddonInfo('name')))
            elif params['category'] == 'Series':
                list_series()
                print("ADDON: {0}, Categories-list created".format(addon.getAddonInfo('name')))
        elif params['action'] == 'play':
            # Play a video from a provided URL.
            print("ADDON: {0}, Play video {1}".format(addon.getAddonInfo('name'), params['video']))
            play_video(params['video'])
    else:
        # If the plugin is called from Kodi UI without any parameters,
        # display the list of video categories
        list_categories()


REMOTE_DEBUG = True
if __name__ == '__main__':
    if REMOTE_DEBUG:
        try:
            sys.path.append('E:\Eclipse IDE\eclipse\plugins\org.python.pydev.core_10.2.1.202307021217\pysrc')
            import pydevd

            pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
        except:
            sys.stderr.write("Error: " + "You must add org.python.pydev.debug.pysrc to your PYTHONPATH")
            sys.stderr.write("Error: " + "Debug not available")
    addon: Addon = xbmcaddon.Addon()
    print("ADDON: ", addon.getAddonInfo('name'))
    for i in range(len(sys.argv)):
        print("arg{0}: {1}".format(i, sys.argv[i]))
    session: LoginSession = LoginSession(addon)
    plugin_initialization()

    # Get the plugin url in plugin:// notation.
    __url__ = sys.argv[0]
    # Get the plugin handle as an integer number.
    __handle__ = int(sys.argv[1])
    # Call the router function and pass the plugin call parameters to it.
    router(sys.argv[2])
