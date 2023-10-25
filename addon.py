import json
import os
import sys
import typing
import urllib.parse
from collections import namedtuple
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from resources.lib.globals import G

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


class ZiggoPlugin:
    def __init__(self, addon):
        self.url = None
        self.addon: xbmcaddon.Addon = addon
        self.session: LoginSession = LoginSession(addon)
        self.__initialization()

    def get_locator(self, channel) -> typing.Tuple[str, str]:
        assetType = 'Orion-DASH'
        if 'locators' in channel:
            if 'Orion-DASH-HEVC' in channel['locators']:
                avc = channel['locators']['Orion-DASH-HEVC']
                assetType = 'Orion-DASH-HEVC'
            else:
                avc = channel['locators']['Orion-DASH']
        else:
            avc = channel['locator']
        return avc, assetType

    def build_url(self, streaming_token, locator) -> str:
        use_proxy = self.addon.getSettingBool('use-proxy')
        if use_proxy:
            xbmc.log('Using proxy server', xbmc.LOGINFO)
            o = urlparse(locator)
            Components = namedtuple(
                typename='Components',
                field_names=['scheme', 'netloc', 'path', 'url', 'query', 'fragment']
            )

            query_params = {
                'path': o.path,
                'token': streaming_token,
                'hostname': o.hostname
            }

            url = urlunparse(
                Components(
                    scheme='http',
                    netloc='127.0.0.1:6969',
                    query=urlencode(query_params),
                    path='manifest',
                    url='',
                    fragment=''
                )
            )
            print('BUILD URL: ', url)
            return url
        else:
            return locator.replace("/dash", "/dash,vxttoken=" + streaming_token).replace("http://", "https://")

    def build_vod_url(self, streaming_token, locator):
        use_proxy = self.addon.getSettingBool('use-proxy')
        if use_proxy:
            xbmc.log('Using proxy server', xbmc.LOGINFO)
            o = urlparse(locator)
            Components = namedtuple(
                typename='Components',
                field_names=['scheme', 'netloc', 'path', 'url', 'query', 'fragment']
            )

            query_params = {
                'path': o.path,
                'token': streaming_token,
                'hostname': o.hostname
            }

            url = urlunparse(
                Components(
                    scheme='http',
                    netloc='127.0.0.1:6969',
                    query=urlencode(query_params),
                    path='manifest',
                    url='',
                    fragment=''
                )
            )
            print('BUILD URL: ', url)
            return url
        else:
            return locator.replace("/sdash", "/sdash,vxttoken=" + streaming_token).replace("http://", "https://")

    def setActiveProfile(self):
        custinfo = self.session.get_customer_info()
        profile = self.addon.getSettingString('profile')
        if 'assignedDevices' in custinfo:
            default_profile_id = custinfo['assignedDevices'][0]['defaultProfileId']
        else:
            default_profile_id = None
        if profile == '':  # not yet set: ask for the profile to use

            profiles = {}
            for profile in custinfo['profiles']:
                profiles.update({profile['name']: profile['profileId']})

            profile_list = list(profiles.keys())
            selected_profile = xbmcgui.Dialog().select(heading='Profiel', list=profile_list)
            profile_id = profiles[profile_list[selected_profile]]
            self.addon.setSetting('profile', profile_id)

        chosen_profile = self.addon.getSetting('profile')
        if chosen_profile == '':  # still not set, use default
            for profile in custinfo['profiles']:
                if profile['profileId'] == default_profile_id:
                    self.session.set_active_profile(profile)
        else:
            for profile in custinfo['profiles']:
                if profile['profileId'] == chosen_profile:
                    self.session.set_active_profile(profile)

        print("ACTIVE PROFILE", self.session.active_profile['name'])

    def __initialization(self):
        global channels
        global session_info
        addon_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        Path(addon_path).mkdir(parents=True, exist_ok=True)
        if addon.getSetting('username') == '#notset#' or addon.getSetting('username') == '':
            xbmcaddon.Addon().openSettings()
        if addon.getSetting('username') == '':
            username = json.loads(Path(r'C:\temp\credentials.json').read_text())['username']
            password = json.loads(Path(r'C:\temp\credentials.json').read_text())['password']
        else:
            username = addon.getSetting('username')
            password = addon.getSetting('password')

        self.session.load_cookies()
        session_info = self.session.login(username, password)
        if len(session_info) == 0:
            raise RuntimeError("Login failed, check your credentials")
        self.session.refresh_widevine_license()
        self.session.refresh_entitlements()

        self.setActiveProfile()

        xbmc.log("ADDON: {0}, authenticated with: {1}".format(addon.getAddonInfo('name'),
                                                              username), 0)

    def get_widevine_license(self, addon_name):
        addon_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        with open(addon_path + "widevine.json", mode="r") as cert_file:
            contents = cert_file.read()

        return contents

    def listitem_from_url(self, url, streaming_token, drmContentId) -> xbmcgui.ListItem:
        li = xbmcgui.ListItem(path=url)
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setMediaType('video')
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
        license_headers = dict(G.CONST_BASE_HEADERS)
        # 'Content-Type': 'application/octet-stream',
        license_headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
            'Host': 'prod.spark.ziggogo.tv',
            'x-streaming-token': streaming_token,
            'X-cus': self.session.customer_info['customerId'],
            'x-go-dev': '214572a3-2033-4327-b8b3-01a9a674f1e0',  # Dummy?
            'x-drm-schemeId': 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
            'deviceName': 'Firefox'
        })
        for key in self.session.extra_headers:
            license_headers.update({key: self.session.extra_headers[key]})

        from urllib.parse import urlencode
        use_license_proxy = True
        if use_license_proxy:
            url = 'http://127.0.0.1:6969/license'
            params = {'ContentId': drmContentId,
                      'addon': addon.getAddonInfo('id')}
            url = (url + '?' + urllib.parse.urlencode(params) +
                   '|' + urllib.parse.urlencode(license_headers) +
                   '|R{SSM}'
                   '|')
        else:
            cookies = self.session.cookies.get_dict()
            url = G.license_URL
            params = {'ContentId': drmContentId }
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

        li.setProperty(
            key='inputstream.adaptive.license_key',
            value=url)
        # Test
        # server certificate to be used to encrypt messages to the license server. Should be encoded as Base64
        widevine_certificate = self.get_widevine_license(addon.getAddonInfo('id'))
        li.setProperty(
            key='inputstream.adaptive.server_certificate',
            value=widevine_certificate)
        self.send_notification(li, streaming_token, url)  # send the streaming-token to the Service

        return li

    def listitem_from_channel(self, video) -> xbmcgui.ListItem:
        li = xbmcgui.ListItem(label="{0}. {1}".format(video['logicalChannelNumber'], video['name']))
        thumbname = xbmc.getCacheThumbName(video['logo']['focused'])
        thumbfile = xbmcvfs.translatePath('special://thumbnails/' + thumbname[0:1] + '/' + thumbname)
        if os.path.exists(thumbfile):
            os.remove(thumbfile)
        if len(video['imageStream']) > 0:
            thumbname = xbmc.getCacheThumbName(video['imageStream']['full'])
            thumbfile = (
                xbmcvfs.translatePath(
                    'special://thumbnails/' + thumbname[0:1] + '/' + thumbname.split('.')[0] + '.jpg'))
            if os.path.exists(thumbfile):
                os.remove(thumbfile)
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

        return li

    def send_notification(self, item: xbmcgui.ListItem, token, locator):
        tag: xbmc.InfoTagVideo = item.getVideoInfoTag()
        uniqueid = tag.getUniqueID('ziggochannelid')
        params = {'sender': addon.getAddonInfo('id'),
                  'message': tag.getTitle(),
                  'data': {'command': 'play_video',
                           'command_params': {'uniqueId': uniqueid, 'streamingToken': token, 'locator': locator}
                           },
                  }

        command = json.dumps({'jsonrpc': '2.0',
                              'method': 'JSONRPC.NotifyAll',
                              'params': params,
                              'id': 1,
                              })
        result = xbmc.executeJSONRPC(command)

    def play_video(self, path):
        global channels
        """
        Play a video by the provided path.
        :param path: str
        :return: None
        """
        # Create a playable item with a path to play.
        channels = self.session.get_channels()
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

            locator, asset_type = self.get_locator(channel)
            streaming_token = self.session.obtain_tv_streaming_token(channel, asset_type)

            url = self.build_url(streaming_token, locator)
            play_item = self.listitem_from_url(url=url
                                               , streaming_token=streaming_token
                                               , drmContentId=self.session.stream_info['drmContentId'])
            xbmcplugin.setResolvedUrl(__handle__, True, listitem=play_item)

        except Exception as exc:
            print(type(exc))
            print(exc.args)
            print(exc)
            pass

    def play_movie(self, path):
        global channels
        """
        Play a movie by the provided path.
        :param path: str
        :return: None
        """
        # Create a playable item with a path to play.

        try:
            is_helper = Helper(PROTOCOL, drm=DRM)
            if is_helper.check_inputstream():
                xbmc.log('Inside play condition...')

            streaming_token = self.session.obtain_vod_streaming_token(path)

            url = self.build_vod_url(streaming_token, self.session.vod_stream_info['url'])
            play_item = self.listitem_from_url(url=url
                                               , streaming_token=streaming_token
                                               , drmContentId=self.session.vod_stream_info['drmContentId'])
            xbmcplugin.setResolvedUrl(__handle__, True, listitem=play_item)

        except Exception as exc:
            print(type(exc))
            print(exc.args)
            print(exc)
            pass

    def listitem_from_overview(self, item, overview, instance):
        li = xbmcgui.ListItem(label=item['id'])
        if 'image' in item:
            li.setArt({'poster': item['image']})
        else:
            li.setArt({'poster': G.STATIC_URL + 'image-service/intent/{crid}/posterTile'.format(crid=item['id'])})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setTitle(overview['title'])
        tag.setSortTitle(overview['title'])
        tag.setPlot(overview['synopsis'])
        tag.setPlotOutline('')
        tag.setGenres(overview['genres'])
        cast = []
        for person in overview['castAndCrew']:
            cast.append(xbmc.Actor(name=person['name'], role=person['role']))
        tag.setCast(cast)

        tag.setMediaType('video')
        li.setMimeType('application/dash+xml')
        entitled = False
        if instance['offers'][0]['entitled']:
            entitled = True
            tag.setUniqueIDs({'ziggochannelid': instance['offers'][0]['id']})
        if not entitled:
            title = tag.getTitle()
            tag.setTitle('[COLOR red]' + title + '[/COLOR]')

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

    def list_subcategories(self, screen_id):
        """
        Create the list of sub categories in the Kodi interface.
        :return: None
        """
        categories = [G.SERIES, G.MOVIES, G.GENRES]
        listing = []
        for categoryname in categories:
            list_item = xbmcgui.ListItem(label=categoryname)
            tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
            tag.setTitle(categoryname)
            tag.setMediaType('video')
            tag.setGenres([categoryname])
            url = '{0}?action=listing&category={1}&categoryId={2}'.format(self.url, categoryname, screen_id)
            is_folder = True
            listing.append((url, list_item, is_folder))
        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS)
        xbmcplugin.endOfDirectory(__handle__)

    def list_categories(self):
        """
        Create the list of video categories in the Kodi interface.
        :return: None
        """
        # Get video categories
        categories = {'Channels': 'Channels'}
        response = self.session.obtain_vod_screens()
        for screen in response['screens']:
            categories.update({screen['title']: screen['id']})

        # Create a list for our items.
        listing = []
        # Iterate through categories
        for categoryname, categoryId in categories.items():
            # Create a list item with a text label and a thumbnail image.
            list_item = xbmcgui.ListItem(label=categoryname)
            # Set additional info for the list item.
            tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
            tag.setTitle(categoryname)
            tag.setMediaType('video')
            tag.setGenres([categoryname])
            if categoryname == 'Channels':
                url = '{0}?action=listing&category={1}&categoryId={2}'.format(self.url, categoryname, categoryId)
            else:
                url = '{0}?action=subcategory&category={1}&categoryId={2}'.format(self.url, categoryname, categoryId)
            # is_folder = True means that this item opens a sub-list of lower level items.
            is_folder = True
            # Add our item to the listing as a 3-element tuple.
            listing.append((url, list_item, is_folder))
        # Add our listing to Kodi.
        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS)
        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def list_channels(self):
        global channels
        # Create a list for our items.
        listing = []
        self.session.refresh_channels()
        channels = self.session.get_channels()
        entitlements = self.session.get_entitlements()["entitlements"]
        entitlementlist = []
        i = 0
        while i < len(entitlements):
            entitlementlist.append(entitlements[i]["id"])
            i += 1

        # Iterate through channels
        for video in channels:  # create a list item using the song filename for the label
            subscribed = False
            if 'isHidden' in video:
                if video['isHidden']:
                    continue
            if 'linearProducts' in video:
                for linearProduct in video['linearProducts']:
                    if linearProduct in entitlementlist:
                        subscribed = True
            li = self.listitem_from_channel(video)

            tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
            title = tag.getTitle()
            tag.setSortTitle(title)
            tag.setPlot('')
            tag.setPlotOutline('')
            #  see https://alwinesch.github.io/group__python___info_tag_video.html#gaabca7bfa2754c91183000f0d152426dd
            #  for more tags

            if not subscribed:
                li.setProperty('IsPlayable', 'false')
            if video['locator'] is None:
                li.setProperty('IsPlayable', 'false')
            if li.getProperty('IsPlayable') == 'true':
                callback_url = '{0}?action=play&video={1}'.format(self.url, video['id'])
            else:
                tag.setTitle(title[0:title.find('.') + 1] + '[COLOR red]' + title[title.find('.') + 1:] + '[/COLOR]')
                callback_url = '{0}?action=cantplay&video={1}'.format(self.url, video['id'])
            listing.append((callback_url, li, False))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def list_series(self):
        pass

    def list_movies(self, categoryId, category):
        global channels
        # Create a list for our items.
        listing = []

        screen_details = self.session.obtain_vod_screen_details(categoryId)
        items_seen = []
        for collection in screen_details['collections']:
            for item in collection['items']:
                if item['id'] in items_seen:
                    continue
                if category == G.MOVIES:
                    if item['type'] == 'ASSET':
                        if 'brandingProviderId' in item:
                            overview = self.session.obtain_asset_details(item['id'], item['brandingProviderId'])
                        else:
                            overview = self.session.obtain_asset_details(item['id'])
                        playable_instance = self.get_playable_instance(overview)
                        if playable_instance is not None:
                            li = self.listitem_from_overview(item, overview, playable_instance)
                            items_seen.append((item['id']))
                            if li.getProperty('IsPlayable') == 'true':
                                callback_url = '{0}?action=playmovie&video={1}'.format(self.url, playable_instance['id'])
                            else:
                                callback_url = '{0}?action=cantplay&video={1}'.format(self.url, playable_instance['id'])
                            listing.append((callback_url, li, False))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def router(self, param_string, url):
        """
            Router function that calls other functions
            depending on the provided param_string
            :type url: url from plugin invocation
            :param param_string:
            :return:
            """
        # Parse a URL-encoded param_string to the dictionary of
        # {<parameter>: <value>} elements
        self.url = url
        params = dict(parse_qsl(param_string[1:]))
        # Check the parameters passed to the plugin
        if params:
            if params['action'] == 'listing':
                # Display the list of videos in a provided category.
                if params['category'] == "Channels":
                    self.list_channels()
                elif params['category'] == G.MOVIES:
                    self.list_movies(params['categoryId'], params['category'])
            elif params['action'] == 'subcategory':
                self.list_subcategories(params['categoryId'])
            elif params['action'] == 'play':
                # Play a video from a provided URL.
                self.play_video(params['video'])
            elif params['action'] == 'playmovie':
                # Play a video from a provided URL.
                self.play_movie(params['video'])
            elif params['action'] == 'cantplay':
                # Play a video from a provided URL.
                xbmcgui.Dialog().ok('Error', 'Cannot watch this channel')
        else:
            # If the plugin is called from Kodi UI without any parameters,
            # display the list of video categories
            self.list_categories()

    def get_playable_instance(self, overview):
        for instance in overview['instances']:
            if instance['goPlayable']:
                return instance
        else:
            return None


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

    addon: Addon = xbmcaddon.Addon()
    plugin = ZiggoPlugin(addon)

    # Get the plugin url in plugin:// notation.
    __url__ = sys.argv[0]
    # Get the plugin handle as an integer number.
    __handle__ = int(sys.argv[1])
    # Call the router function and pass the plugin call parameters to it.
    plugin.router(sys.argv[2], __url__)
