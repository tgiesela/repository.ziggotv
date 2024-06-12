"""
Listitem helpers
"""
import os
import json
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

import xbmc
import xbmcgui
import xbmcvfs

from resources.lib.channel import Channel
from resources.lib.globals import S, G, CONST_BASE_HEADERS
from resources.lib.recording import SingleRecording, SeasonRecording, PlannedRecording
from resources.lib.utils import ProxyHelper, SharedProperties
from resources.lib.webcalls import LoginSession

try:
    # pylint: disable=import-error, broad-exception-caught
    from inputstreamhelper import Helper
except Exception as excpt:
    from tests.testinputstreamhelper import Helper


class ListitemHelper:
    """
    Class holding several methods to create listitems for a specific purpose
    """

    def __init__(self, addon):
        self.addon = addon
        self.uuId = SharedProperties(addon=self.addon).get_uuid()
        self.helper = ProxyHelper(addon)
        self.customerInfo = self.helper.dynamic_call(LoginSession.get_customer_info)
        self.home = SharedProperties(addon=self.addon)
        self.kodiMajorVersion = self.home.get_kodi_version_major()
        self.kodiMinorVersion = self.home.get_kodi_version_minor()


    @staticmethod
    def __get_pricing_from_offer(instance):
        if 'offers' in instance:
            offer = instance['offers'][0]
            price = '({0} {1})'.format(offer['priceDisplay'], offer['currency'])
            return price
        return '(???)'

    def __get_widevine_license(self):
        addonPath = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        # pylint: disable=unspecified-encoding
        with open(addonPath + "widevine.json", mode="r") as certFile:
            contents = certFile.read()

        return contents

    def __send_notification(self, item: xbmcgui.ListItem, token, locator):
        tag: xbmc.InfoTagVideo = item.getVideoInfoTag()
        uniqueid = tag.getUniqueID('ziggochannelid')
        params = {'sender': self.addon.getAddonInfo('id'),
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
        xbmc.executeJSONRPC(command)

    def listitem_from_url(self, requesturl, streamingToken, drmContentId) -> xbmcgui.ListItem:
        """
        create a listitem from an url
        @param requesturl:
        @param streamingToken:
        @param drmContentId:
        @return: ListItem
        """

        isHelper = Helper(G.PROTOCOL, drm=G.DRM)
        isHelper.check_inputstream()

        li = xbmcgui.ListItem(path=requesturl)
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setMediaType('video')
        li.setMimeType('application/dash+xml')
        li.setContentLookup(False)
        if self.kodiMajorVersion >= 19:
            li.setProperty(
                key='inputstream',
                value=isHelper.inputstream_addon)
        else:
            li.setProperty(
                key='inputstreamaddon',
                value=isHelper.inputstream_addon)

        li.setProperty(
            key='inputstream.adaptive.license_flags',
            value='persistent_storage')
        # See wiki of InputStream Adaptive. Also depends on header in manifest response. See Proxyserver.
        if self.kodiMajorVersion < 21:
            li.setProperty(
               key='inputstream.adaptive.manifest_type',
               value=G.PROTOCOL)
        li.setProperty(
            key='inputstream.adaptive.license_type',
            value=G.DRM)
        licenseHeaders = dict(CONST_BASE_HEADERS)
        # 'Content-Type': 'application/octet-stream',
        licenseHeaders.update({
            'Host': G.ZIGGO_HOST,
            'x-streaming-token': streamingToken,
            'X-cus': self.customerInfo['customerId'],
            'x-go-dev': self.uuId,
            'x-drm-schemeId': 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
            'deviceName': 'Firefox'
        })
        extraHeaders = ProxyHelper(self.addon).dynamic_call(LoginSession.get_extra_headers)
        for key in extraHeaders:
            licenseHeaders.update({key: extraHeaders[key]})

        port = self.addon.getSetting('proxy-port')
        ip = self.addon.getSetting('proxy-ip')
        url = 'http://{0}:{1}/license'.format(ip, port)
        params = {'ContentId': drmContentId,
                  'addon': self.addon.getAddonInfo('id')}
        url = (url + '?' + urlencode(params) +
               '|' + urlencode(licenseHeaders) +
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
        widevineCertificate = self.__get_widevine_license()
        li.setProperty(
            key='inputstream.adaptive.server_certificate',
            value=widevineCertificate)
        self.__send_notification(li, streamingToken, url)  # send the streaming-token to the Service

        return li

    def listitem_from_recording(self, recording, recType, season: SeasonRecording=None) -> xbmcgui.ListItem:
        """
        Creates a ListItem from a SingleRecording
        @param season: the information of the season to which the recording belongs
        @param recording: the recording to use
        @param recType: the type of recording (planned|recorded)
        @return: listitem
        """
        try:
            start = datetime.strptime(recording.startTime,
                                      '%Y-%m-%dT%H:%M:%S.%fZ').astimezone()
        except TypeError:
            # Due to a bug in datetime see https://bugs.python.org/issue27400
            # pylint: disable=import-outside-toplevel
            import time
            start = datetime.fromtimestamp(time.mktime(time.strptime(recording.startTime,
                                                                     '%Y-%m-%dT%H:%M:%S.%fZ')))
        start = start.replace(tzinfo=timezone.utc).astimezone(tz=None)
        title = "{0} ({1})".format(recording.title, start.strftime('%Y-%m-%d %H:%M'))
        li = xbmcgui.ListItem(label=title)
        thumbname = xbmc.getCacheThumbName(recording.poster.url)
        thumbfile = xbmcvfs.translatePath('special://thumbnails/' + thumbname[0:1] + '/' + thumbname)
        if os.path.exists(thumbfile):
            os.remove(thumbfile)
        li.setArt({'icon': recording.poster.url,
                   'thumb': recording.poster.url})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        if recording.recordingState == 'planned':
            tag.setTitle('[COLOR red]' + title + '[/COLOR]')
        else:
            tag.setTitle(title)
        tag.setMediaType('video')
        tag.setUniqueIDs({'ziggoRecordingId': recording.id})
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('application/dash+xml')
        li.setContentLookup(False)
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        title = tag.getTitle()
        tag.setSortTitle(title)
        tag.setPlot('')
        tag.setPlotOutline('')

        # Add context menu for delete
        scriptname = self.addon.getAddonInfo('path') + 'contextactions.py'
        if isinstance(recording, (SingleRecording, PlannedRecording)):
            if season is not None:
                items = [(self.addon.getLocalizedString(S.MSG_DELETE),
                          'RunScript({0},--action=delete,--type=recording,--id={1},--rectype={2})'.format(
                              scriptname,
                              quote(recording.id),
                              recType)),
                         (self.addon.getLocalizedString(S.MSG_DELETE_SEASON),
                          'RunScript({0},--action=delete,--type=season,--id={1},--rectype={2},--channel={3})'.format(
                              scriptname,
                              quote(season.showId),
                              recType,
                              season.channelId))]
            else:
                items = [(self.addon.getLocalizedString(S.MSG_DELETE),
                          'RunScript({0},--action=delete,--type=recording,--id={1},--rectype={2})'.format(
                              scriptname,
                              quote(recording.id),
                              recType))]
        else:
            items = []
        items.append((self.addon.getLocalizedString(S.BTN_PLAY),
                      'RunAddon({0},action=play&type=recording&id={1}&rectype={2})'.format(
                          self.addon.getAddonInfo('id'),
                          quote(recording.id),
                          recording.recordingState)))
        li.addContextMenuItems(items, True)

        return li

    def listitem_from_recording_season(self, recording: SeasonRecording, recType) -> xbmcgui.ListItem:
        """
        Creates a ListItem from a SeasonRecording
        @param recording: the recording to use
        @param recType: the type of recording (planned|recorded)
        @return: listitem
        """
        description = self.addon.getLocalizedString(S.MSG_EPISODES).format(len(recording.episodes))
        title = "{0} ({1})".format(recording.title, description)
        li = xbmcgui.ListItem(label=title)
        thumbname = xbmc.getCacheThumbName(recording.poster.url)
        thumbfile = xbmcvfs.translatePath('special://thumbnails/' + thumbname[0:1] + '/' + thumbname)
        if os.path.exists(thumbfile):
            os.remove(thumbfile)
        li.setArt({'poster': recording.poster.url})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setTitle(title)
        # tag.setSetId(recording.id)
        tag.setMediaType('video')
        tag.setUniqueIDs({'ziggoRecordingId': recording.id})
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('application/dash+xml')
        li.setContentLookup(False)
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        title = tag.getTitle()
        tag.setSortTitle(title)
        tag.setPlot('')
        tag.setPlotOutline('')

        scriptname = self.addon.getAddonInfo('path') + 'contextactions.py'
        if isinstance(recording, SeasonRecording):
            items = [(self.addon.getLocalizedString(S.MSG_DELETE),
                      'RunScript({0},--action=delete,--type=season,--id={1},--rectype={2},--channel={3})'.format(
                          scriptname,
                          quote(recording.showId),
                          recType,
                          recording.channelId))]
            li.addContextMenuItems(items, True)
        return li

    @staticmethod
    def listitem_from_channel(video: Channel) -> xbmcgui.ListItem:
        """
        Creates a ListItem from a Channel
        @param video: the channel
        @return: listitem
        """

        li = xbmcgui.ListItem(label="{0}. {1}".format(video.logicalChannelNumber, video.name))
        thumbname = xbmc.getCacheThumbName(video.logo['focused'])
        thumbfile = xbmcvfs.translatePath('special://thumbnails/' + thumbname[0:1] + '/' + thumbname)
        if os.path.exists(thumbfile):
            os.remove(thumbfile)
        if len(video.streamInfo.imageStream) > 0:
            thumbname = xbmc.getCacheThumbName(video.streamInfo.imageStream['full'])
            thumbfile = (
                xbmcvfs.translatePath(
                    'special://thumbnails/' + thumbname[0:1] + '/' + thumbname.split('.', maxsplit=1)[0] + '.jpg'))
            if os.path.exists(thumbfile):
                os.remove(thumbfile)
            li.setArt({'icon': video.logo['focused'],
                       'thumb': video.logo['focused'],
                       'poster': video.streamInfo.imageStream['full']})
        else:
            li.setArt({'icon': video.logo['focused'],
                       'thumb': video.logo['focused']})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setTitle("{0}. {1}".format(video.logicalChannelNumber, video.name))
        tag.setGenres(video.genre)
        tag.setSetId(video.logicalChannelNumber)
        tag.setMediaType('video')
        tag.setUniqueIDs({'ziggochannelid': video.id})
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('application/dash+xml')
        li.setContentLookup(False)

        return li

    def listitem_from_movie(self, item, details, instance):
        """
        Creates a ListItem from a Movie
        @param item: the movie information
        @param details: the movie details
        @param instance: list of instances that can be played
        @return: listitem
        """

        li = xbmcgui.ListItem(label=item['id'])
        if 'image' in item:
            li.setArt({'poster': item['image']})
        else:
            li.setArt({'poster': G.STATIC_URL + 'image-service/intent/{crid}/posterTile'.format(crid=item['id'])})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setTitle(details['title'])
        tag.setSortTitle(details['title'])
        if 'synopsis' in details:
            tag.setPlot(details['synopsis'])
        tag.setPlotOutline('')
        if 'genres' in details:
            tag.setGenres(details['genres'])
        cast = []
        if 'castAndCrew' in details:
            for person in details['castAndCrew']:
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
            tag.setTitle('[COLOR red]' + title + self.__get_pricing_from_offer(instance) + '[/COLOR]')
            li.setProperty('IsPlayable', 'false')

        li.setContentLookup(False)

        return li

    @staticmethod
    def listitem_from_seriesitem(item, overview):
        """
        Creates a ListItem from a Series/Show
        @param item: the series/show information
        @param overview: addition info for the show
        @return: ListItem
        """
        li = xbmcgui.ListItem(label=item['id'])
        if 'image' in item:
            li.setArt({'poster': item['image']})
        else:
            li.setArt({'poster': G.STATIC_URL + 'image-service/intent/{crid}/posterTile'.format(crid=item['id'])})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setTitle(item['title'])
        tag.setSortTitle(item['title'])
        tag.setPlot(overview['synopsis'])
        tag.setMediaType('set')
        if 'genres' in overview:
            tag.setGenres(overview['genres'])

        return li

    @staticmethod
    def listitem_from_genre(genre):
        """
        Creates a ListItem from a Genre
        @param genre: the genre information
        @return: ListItem
        """
        li = xbmcgui.ListItem(label=genre['id'])
        if 'image' in genre:
            li.setArt({'poster': genre['image']})
        else:
            li.setArt({'poster': G.STATIC_URL + 'image-service/intent/{crid}/posterTile'.format(crid=genre['id'])})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setTitle(genre['gridLink']['title'])
        tag.setSortTitle(genre['gridLink']['title'])
        tag.setMediaType('set')
        tag.setGenres([tag.getTitle()])  # Genre is same as title here

        return li

    @staticmethod
    def listitem_from_season(season, episodes):
        """
        Creates a ListItem from a Series/Show season
        @param season: the series/show season information
        @param episodes: episode information
        @return: ListItem
        """
        li = xbmcgui.ListItem(label=season['id'])
        if 'image' in season:
            li.setArt({'poster': season['image']})
        else:
            li.setArt({'poster': G.STATIC_URL + 'image-service/intent/{crid}/posterTile'.format(crid=season['id'])})
        # set the list item to playable
        li.setProperty('IsPlayable', 'false')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setTitle('{0}. {1}'.format(season['season'], season['title']))
        tag.setSortTitle('{0}. {1}'.format(season['season'], season['title']))
        if 'synopsis' in episodes:
            tag.setPlot(episodes['synopsis'])
        tag.setMediaType('season')
        tag.setSeason(len(episodes['seasons']))
        tag.setYear(episodes['startYear'])
        if 'genres' in episodes:
            tag.setGenres(episodes['genres'])

        return li

    def listitem_from_episode(self, episode, season, details, instance):
        # pylint: disable=too-many-branches
        """
        Creates a ListItem from a Series/Show episode
        @param episode: episode information
        @param season: the series/show season information
        @param details: details of the episode
        @param instance: list of instances that can be played
        @return: ListItem
        """
        li = xbmcgui.ListItem(label=episode['id'])
        if 'image' in episode:
            li.setArt({'poster': episode['image']})
        else:
            li.setArt({'poster': G.STATIC_URL + 'image-service/intent/{crid}/posterTile'.format(crid=episode['id'])})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        if 'title' in episode:
            tag.setTitle(episode['title'])
            tag.setSortTitle(episode['title'])
        elif 'episode' in episode:
            tag.setTitle('Aflevering {0}'.format(episode['episode']))
            tag.setSortTitle('Aflevering {0}'.format(episode['episode']))
        if 'synopsis' in season:
            tag.setPlot(season['synopsis'])
        else:
            if 'synopsis' in episode:
                tag.setPlot(episode['synopsis'])
        tag.setPlotOutline('')
        entitled = False
        if 'entitlementState' in episode['source']:
            if episode['source']['entitlementState'] == 'entitled':
                entitled = True
        if 'genres' in details:
            tag.setGenres(details['genres'])
        if 'castAndCrew' in details:
            cast = []
            for person in details['castAndCrew']:
                cast.append(xbmc.Actor(name=person['name'], role=person['role']))
            tag.setCast(cast)

        if not entitled:
            if instance is not None:
                if instance['offers'][0]['entitled']:
                    entitled = True
                else:
                    tag.setTitle('[COLOR red]' + tag.getTitle() + self.__get_pricing_from_offer(instance) + '[/COLOR]')
            else:
                tag.setTitle('[COLOR red]' + tag.getTitle() + '[/COLOR]')
        if not entitled:
            li.setProperty('IsPlayable', 'false')
        else:
            tag.setUniqueIDs({'ziggochannelid': instance['offers'][0]['id']})

        tag.setSeason(season['season'])
        tag.setEpisode(episode['episode'])
        tag.setMediaType('episode')
        li.setMimeType('application/dash+xml')

        li.setContentLookup(False)

        return li
