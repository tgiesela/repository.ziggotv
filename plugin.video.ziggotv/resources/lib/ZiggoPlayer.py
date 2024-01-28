import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import json

from resources.lib.Channel import Channel, ChannelList
from resources.lib.UrlTools import UrlTools
from resources.lib.events import Event
from resources.lib.globals import G, S
from resources.lib.utils import ProxyHelper, SharedProperties
from resources.lib.webcalls import LoginSession

try:
    from inputstreamhelper import Helper
except:
    pass


class ZiggoPlayer(xbmc.Player):

    def __init__(self):
        super().__init__()
        self.prePadding = None
        xbmc.log("ZIGGOPLAYER CREATED", xbmc.LOGDEBUG)
        self.replay = False

    def __del__(self):
        xbmc.log("ZIGGOPLAYER DELETED", xbmc.LOGDEBUG)

    def onPlayBackStopped(self) -> None:
        xbmc.log("ZIGGOPLAYER STOPPED at {0}".format(self.getTime()), xbmc.LOGDEBUG)

    def onPlayBackPaused(self) -> None:
        xbmc.log("ZIGGOPLAYER PAUSED", xbmc.LOGDEBUG)

    def onAVStarted(self) -> None:
        xbmc.log("ZIGGOPLAYER AVSTARTED", xbmc.LOGDEBUG)
        if self.replay:
            xbmc.log("ZIGGOPLAYER POSITIONED TO BEGINNING", xbmc.LOGDEBUG)
            self.seekTime(self.prePadding / 1000)

    def onPlayBackStarted(self) -> None:
        xbmc.log("ZIGGOPLAYER PLAYBACK STARTED", xbmc.LOGDEBUG)

    def onPlayBackError(self) -> None:
        xbmc.log("ZIGGOPLAYER PLAYBACK ERROR", xbmc.LOGDEBUG)

    def setReplay(self, isReplay, time=0):
        self.replay = isReplay
        self.prePadding = time


class VideoHelpers:
    def __init__(self, addon: xbmcaddon.Addon):
        self.addon = addon
        self.helper = ProxyHelper(addon)
        self.player: ZiggoPlayer = ZiggoPlayer()
        self.customer_info = self.helper.dynamicCall(LoginSession.get_customer_info)
        self.entitlements = self.helper.dynamicCall(LoginSession.get_entitlements)
        self.channels = ChannelList(self.helper.dynamicCall(LoginSession.get_channels), self.entitlements)
        self.UUID = SharedProperties(addon=self.addon).getUUID()

    def __get_widevine_license(self, addon_name):
        addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        with open(addon_path + "widevine.json", mode="r") as cert_file:
            contents = cert_file.read()

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
        result = xbmc.executeJSONRPC(command)

    def listitem_from_url(self, requesturl, streaming_token, drmContentId) -> xbmcgui.ListItem:
        li = xbmcgui.ListItem(path=requesturl)
        li.setProperty('IsPlayable', 'true')
        rslt = li.getProperty('isplayable')
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
            value=G.PROTOCOL)
        li.setProperty(
            key='inputstream.adaptive.license_type',
            value=G.DRM)
        license_headers = dict(G.CONST_BASE_HEADERS)
        # 'Content-Type': 'application/octet-stream',
        license_headers.update({
            'Host': 'prod.spark.ziggogo.tv',
            'x-streaming-token': streaming_token,
            'X-cus': self.customer_info['customerId'],
            'x-go-dev': self.UUID,
            'x-drm-schemeId': 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
            'deviceName': 'Firefox'
        })
        extra_headers = ProxyHelper(self.addon).dynamicCall(LoginSession.get_extra_headers)
        for key in extra_headers:
            license_headers.update({key: extra_headers[key]})

        from urllib.parse import urlencode
        use_license_proxy = True
        if use_license_proxy:
            port = self.addon.getSetting('proxy-port')
            ip = self.addon.getSetting('proxy-ip')
            url = 'http://{0}:{1}/license'.format(ip, port)
            params = {'ContentId': drmContentId,
                      'addon': self.addon.getAddonInfo('id')}
            url = (url + '?' + urlencode(params) +
                   '|' + urlencode(license_headers) +
                   '|R{SSM}'
                   '|')
        else:
            cookies = ProxyHelper(self.addon).dynamicCall(LoginSession.get_cookies_dict)
            url = G.license_URL
            params = {'ContentId': drmContentId}
            url = (url + '?' + urlencode(params) +
                   '|' + urlencode(license_headers) +
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
        widevine_certificate = self.__get_widevine_license(self.addon.getAddonInfo('id'))
        li.setProperty(
            key='inputstream.adaptive.server_certificate',
            value=widevine_certificate)
        self.__send_notification(li, streaming_token, url)  # send the streaming-token to the Service

        return li

    def userWantsSwitch(self):
        choice = xbmcgui.Dialog().yesno('Play',
                                        self.addon.getLocalizedString(S.MSG_SWITCH),
                                        self.addon.getLocalizedString(S.BTN_CANCEL),
                                        self.addon.getLocalizedString(S.BTN_SWITCH),
                                        False,
                                        xbmcgui.DLG_YESNO_NO_BTN)
        return choice

    def __addEventInfo(self, play_item, channel: Channel, event):
        title = ''
        if event is not None:
            title = '{0}. {1}: {2}'.format(channel.logicalChannelNumber, channel.name, event.title)
            if not event.hasDetails:
                event.details = self.helper.dynamicCall(LoginSession.get_event_details, eventId=event.id)
        else:
            title = '{0}. {1}'.format(channel.logicalChannelNumber, channel.name)
        tag: xbmc.InfoTagVideo = play_item.getVideoInfoTag()
        play_item.setLabel(title)
        if event is not None:
            tag.setPlot(event.details.description)
            if event.details.isSeries:
                tag.setEpisode(event.details.episode)
                tag.setSeason(event.details.season)
            tag.setArtists(event.details.actors)
            genres = []
            for genre in event.details.genres:
                genres.append(genre)
        else:
            genres = []
        for genre in channel.genre:
            genres.append(genre)
        tag.setGenres(genres)

    @staticmethod
    def __addChannelInfo(play_item, channel):
        tag: xbmc.InfoTagVideo = play_item.getVideoInfoTag()
        play_item.setLabel('{0}. {1}'.format(channel.logicalChannelNumber, channel.name))
        genres = []
        for genre in channel.genre:
            genres.append(genre)
        tag.setGenres(genres)

    @staticmethod
    def __addVodInfo(play_item, overview):
        tag: xbmc.InfoTagVideo = play_item.getVideoInfoTag()
        play_item.setLabel(overview['title'])
        tag.setPlot(overview['synopsis'])
        tag.setGenres(overview['genres'])
        if 'episode' in overview:
            tag.setEpisode(int(overview['episode']))
        if 'season' in overview:
            tag.setSeason(int(overview['season']))

    @staticmethod
    def __addRecordingInfo(play_item, overview):
        tag: xbmc.InfoTagVideo = play_item.getVideoInfoTag()
        play_item.setLabel(overview['title'])
        tag.setPlot(overview['synopsis'])
        tag.setGenres(overview['genres'])
        if 'episode' in overview:
            tag.setEpisode(int(overview['episodeNumber']))
        if 'season' in overview:
            tag.setSeason(int(overview['seasonNumber']))

    def __play_channel(self, channel):
        urlHelper = UrlTools(self.addon)
        locator, asset_type = channel.getLocator(self.addon)
        if locator is None:
            xbmcgui.Dialog().ok('Info', self.addon.getLocalizedString(S.MSG_CANNOTWATCH))
            return
        streamInfo = self.helper.dynamicCall(LoginSession.obtain_tv_streaming_token,
                                             channelId=channel.id, asset_type=asset_type)
        try:
            url = urlHelper.build_url(streamInfo.token, locator)
            play_item = self.listitem_from_url(requesturl=url,
                                               streaming_token=streamInfo.token,
                                               drmContentId=streamInfo.drmContentId)
            event = channel.events.getCurrentEvent()
            self.__addEventInfo(play_item, channel, event)
            self.player.setReplay(False, 0)
            self.player.play(item=url, listitem=play_item)
            self.__waitForPlayer()
            return play_item
        except Exception as exc:
            xbmc.log('Error in __play_channel: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamicCall(LoginSession.delete_token, streaming_id=streamInfo.token)

    def __replay_event(self, event: Event, channel: Channel):
        if not event.canReplay:
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_REPLAY_NOT_AVAIALABLE))
            return
        urlHelper = UrlTools(self.addon)
        streamInfo = self.helper.dynamicCall(LoginSession.obtain_replay_streaming_token,
                                             path=event.details.eventId)
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)
            play_item = self.listitem_from_url(requesturl=url,
                                               streaming_token=streamInfo.token,
                                               drmContentId=streamInfo.drmContentId)
            self.__addEventInfo(play_item, channel, event)
            self.player.setReplay(True, streamInfo.prePaddingTime)
            self.player.play(item=url, listitem=play_item)
        except Exception as exc:
            xbmc.log('Error in __replay_event: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamicCall(LoginSession.delete_token, streaming_id=streamInfo.token)

    @staticmethod
    def __get_playable_instance(overview):
        if 'instances' in overview:
            for instance in overview['instances']:
                if instance['goPlayable']:
                    return instance

            return overview['instances'][0]  # return the first one if none was goPlayable
        return None

    def __play_vod(self, overview) -> xbmcgui.ListItem:
        playable_instance = self.__get_playable_instance(overview)
        if playable_instance is None:
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_CANNOTWATCH))

        helper = VideoHelpers(self.addon)
        urlHelper = UrlTools(self.addon)
        streamInfo = self.helper.dynamicCall(LoginSession.obtain_vod_streaming_token, id=playable_instance['id'])
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)

            play_item = helper.listitem_from_url(
                requesturl=url,
                streaming_token=streamInfo.token,
                drmContentId=streamInfo.drmContentId)
            self.__addVodInfo(play_item, overview)
            self.player.play(item=url, listitem=play_item)
            self.__waitForPlayer()
            return play_item
        except Exception as exc:
            xbmc.log('Error in __play_vod: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamicCall(LoginSession.delete_token, streaming_id=streamInfo.token)
            return None

    def __play_recording(self, id, resumePoint) -> xbmcgui.ListItem:
        helper = VideoHelpers(self.addon)
        urlHelper = UrlTools(self.addon)
        streamInfo = self.helper.dynamicCall(LoginSession.obtain_recording_streaming_token, id=id)
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)

            play_item = helper.listitem_from_url(
                requesturl=url,
                streaming_token=streamInfo.token,
                drmContentId=streamInfo.drmContentId)
            details = self.helper.dynamicCall(LoginSession.getRecordingDetails, id=id)
            self.__addRecordingInfo(play_item, details)
            if resumePoint > 0:
                self.player.setReplay(True, resumePoint * 1000)
            else:
                self.player.setReplay(True, streamInfo.prePaddingTime)
            self.player.play(item=url, listitem=play_item)
            self.__waitForPlayer()
            return play_item
        except Exception as exc:
            xbmc.log('Error in __play_vod: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamicCall(LoginSession.delete_token, streaming_id=streamInfo.token)
            return None

    def __record_event(self, event):
        self.helper.dynamicCall(LoginSession.recordEvent, eventId=event.id)

    def __record_show(self, event, channel):
        self.helper.dynamicCall(LoginSession.recordShow, eventId=event.id, channelId=channel.channelId)

    def updateEvent(self, channel: Channel, event):
        if event is None:
            return
        if not event.hasDetails:
            event.details = self.helper.dynamicCall(LoginSession.get_event_details, eventId=event.id)

        item = self.player.getPlayingItem()
        item.setLabel('{0}. {1}: {2}'.format(channel.logicalChannelNumber, channel.name, event.title))
        tag = item.getVideoInfoTag()
        tag.setPlot(event.details.description)
        tag.setTitle(event.title)
        if event.details.isSeries:
            tag.setEpisode(event.details.episode)
            tag.setSeason(event.details.season)
        tag.setArtists(event.details.actors)
        self.player.updateInfoTag(item)

    def play_epg(self, event: Event, channel: Channel):
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        is_helper = Helper(G.PROTOCOL, drm=G.DRM)
        is_helper.check_inputstream()

        if not self.channels.isEntitled(channel):
            xbmcgui.Dialog().ok('Info', self.addon.getLocalizedString(S.MSG_NOT_ENTITLED))
            return
        if not event.hasDetails:
            event.details = self.helper.dynamicCall(LoginSession.get_event_details, eventId=event.id)

        if not self.channels.supportsReplay(channel):
            if self.userWantsSwitch():
                self.__play_channel(channel)
            return

        choices = {self.addon.getLocalizedString(S.MSG_SWITCH_CHANNEL): 'switch'}
        if event.canReplay:
            choices.update({self.addon.getLocalizedString(S.MSG_REPLAY_EVENT): 'replay'})
        if event.canRecord:
            choices.update({self.addon.getLocalizedString(S.MSG_RECORD_EVENT): 'record'})
            if event.details.isSeries:
                choices.update({self.addon.getLocalizedString(S.MSG_RECORD_SHOW): 'recordshow'})
        choicesList = list(choices.keys())
        selected = xbmcgui.Dialog().contextmenu(choicesList)
        action = choices[choicesList[selected]]
        if action == 'switch':
            self.__play_channel(channel)
        elif action == 'replay':
            self.__replay_event(event, channel)
        elif action == 'record':
            self.__record_event(event)
        elif action == 'recordshow':
            self.__record_show(event, channel)
        #     if event.isPlaying:
        #
        #         choice = xbmcgui.Dialog().yesnocustom('Play',
        #                                               self.addon.getLocalizedString(S.MSG_SWITCH_OR_PLAY),
        #                                               self.addon.getLocalizedString(S.BTN_CANCEL),
        #                                               self.addon.getLocalizedString(S.BTN_PLAY),
        #                                               self.addon.getLocalizedString(S.BTN_SWITCH),
        #                                               False,
        #                                               xbmcgui.DLG_YESNO_CUSTOM_BTN)
        #         if choice in [-1, 2]:
        #             return
        #         else:
        #             if choice == 0:  # nobutton -> Play event
        #                 self.__replay_event(event)
        #             elif choice == 1:  # yesbutton -> Switch to channel
        #                 self.__play_channel(channel)
        #     else:  # event already finished
        #         self.__replay_event(event)
        # else:
        #     if self.userWantsSwitch():
        #         self.__play_channel(channel)

    def play_movie(self, movie_overview) -> xbmcgui.ListItem:
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        return self.__play_vod(movie_overview)

    def play_recording(self, details, resumePoint):
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        return self.__play_recording(details, resumePoint)

    def play_channel(self, channel: Channel) -> xbmcgui.ListItem:
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        return self.__play_channel(channel)

    def __waitForPlayer(self):
        cnt = 0
        while cnt < 10 and not self.player.isPlaying():
            cnt += 1
            xbmc.sleep(500)
        if cnt >= 10:
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_VIDEO_NOT_STARTED))
