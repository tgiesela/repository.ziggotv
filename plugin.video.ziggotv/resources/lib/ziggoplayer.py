import json

from urllib.parse import urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib.channel import Channel, ChannelList
from resources.lib.recording import SingleRecording
from resources.lib.streaminginfo import ReplayStreamingInfo
from resources.lib.urltools import UrlTools
from resources.lib.events import Event
from resources.lib.globals import G, S, CONST_BASE_HEADERS
from resources.lib.utils import ProxyHelper, SharedProperties
from resources.lib.webcalls import LoginSession

try:
    # pylint: disable=import-error
    from inputstreamhelper import Helper
except Exception as excpt:
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
        xbmc.log("ZIGGOPLAYER STOPPED", xbmc.LOGDEBUG)

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

    def set_replay(self, isReplay, time=0):
        self.replay = isReplay
        self.prePadding = time


class VideoHelpers:
    def __init__(self, addon: xbmcaddon.Addon):
        self.addon = addon
        self.helper = ProxyHelper(addon)
        self.player: ZiggoPlayer = ZiggoPlayer()
        self.customerInfo = self.helper.dynamic_call(LoginSession.get_customer_info)
        self.entitlements = self.helper.dynamic_call(LoginSession.get_entitlements)
        self.channels = ChannelList(self.helper.dynamic_call(LoginSession.get_channels), self.entitlements)
        self.uuId = SharedProperties(addon=self.addon).get_uuid()

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
        li = xbmcgui.ListItem(path=requesturl)
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
            value=G.PROTOCOL)
        li.setProperty(
            key='inputstream.adaptive.license_type',
            value=G.DRM)
        licenseHeaders = dict(CONST_BASE_HEADERS)
        # 'Content-Type': 'application/octet-stream',
        licenseHeaders.update({
            'Host': 'prod.spark.ziggogo.tv',
            'x-streaming-token': streamingToken,
            'X-cus': self.customerInfo['customerId'],
            'x-go-dev': self.uuId,
            'x-drm-schemeId': 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
            'deviceName': 'Firefox'
        })
        extraHeaders = ProxyHelper(self.addon).dynamic_call(LoginSession.get_extra_headers)
        for key in extraHeaders:
            licenseHeaders.update({key: extraHeaders[key]})

        useLicenseProxy = True
        if useLicenseProxy:
            port = self.addon.getSetting('proxy-port')
            ip = self.addon.getSetting('proxy-ip')
            url = 'http://{0}:{1}/license'.format(ip, port)
            params = {'ContentId': drmContentId,
                      'addon': self.addon.getAddonInfo('id')}
            url = (url + '?' + urlencode(params) +
                   '|' + urlencode(licenseHeaders) +
                   '|R{SSM}'
                   '|')
        else:
            cookies = ProxyHelper(self.addon).dynamic_call(LoginSession.get_cookies_dict)
            url = G.LICENSE_URL
            params = {'ContentId': drmContentId}
            url = (url + '?' + urlencode(params) +
                   '|' + urlencode(licenseHeaders) +
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
        widevineCertificate = self.__get_widevine_license()
        li.setProperty(
            key='inputstream.adaptive.server_certificate',
            value=widevineCertificate)
        self.__send_notification(li, streamingToken, url)  # send the streaming-token to the Service

        return li

    def user_wants_switch(self):
        choice = xbmcgui.Dialog().yesno('Play',
                                        self.addon.getLocalizedString(S.MSG_SWITCH),
                                        self.addon.getLocalizedString(S.BTN_CANCEL),
                                        self.addon.getLocalizedString(S.BTN_SWITCH),
                                        False,
                                        xbmcgui.DLG_YESNO_NO_BTN)
        return choice

    def __add_event_info(self, playItem, channel: Channel, event):
        title = ''
        if event is not None:
            title = '{0}. {1}: {2}'.format(channel.logicalChannelNumber, channel.name, event.title)
            if not event.hasDetails:
                event.details = self.helper.dynamic_call(LoginSession.get_event_details, eventId=event.id)
        else:
            title = '{0}. {1}'.format(channel.logicalChannelNumber, channel.name)
        tag: xbmc.InfoTagVideo = playItem.getVideoInfoTag()
        playItem.setLabel(title)
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
    def __add_vod_info(playItem, overview):
        tag: xbmc.InfoTagVideo = playItem.getVideoInfoTag()
        playItem.setLabel(overview['title'])
        tag.setPlot(overview['synopsis'])
        tag.setGenres(overview['genres'])
        if 'episode' in overview:
            tag.setEpisode(int(overview['episode']))
        if 'season' in overview:
            tag.setSeason(int(overview['season']))

    @staticmethod
    def __add_recording_info(playItem, overview):
        tag: xbmc.InfoTagVideo = playItem.getVideoInfoTag()
        playItem.setLabel(overview['title'])
        tag.setPlot(overview['synopsis'])
        tag.setGenres(overview['genres'])
        if 'episode' in overview:
            tag.setEpisode(int(overview['episodeNumber']))
        if 'season' in overview:
            tag.setSeason(int(overview['seasonNumber']))

    def __play_channel(self, channel):
        urlHelper = UrlTools(self.addon)
        locator, assetType = channel.get_locator(self.addon)
        if locator is None:
            xbmcgui.Dialog().ok('Info', self.addon.getLocalizedString(S.MSG_CANNOTWATCH))
            return
        streamInfo = self.helper.dynamic_call(LoginSession.obtain_tv_streaming_token,
                                              channelId=channel.id, assetType=assetType)
        try:
            url = urlHelper.build_url(streamInfo.token, locator)
            playItem = self.listitem_from_url(requesturl=url,
                                              streamingToken=streamInfo.token,
                                              drmContentId=streamInfo.drmContentId)
            event = channel.events.get_current_event()
            self.__add_event_info(playItem, channel, event)
            self.player.set_replay(False, 0)
            self.player.play(item=url, listitem=playItem)
            self.__wait_for_player()
            return playItem
        except Exception as exc:
            xbmc.log('Error in __play_channel: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamic_call(LoginSession.delete_token, streaming_id=streamInfo.token)
            return None

    def __replay_event(self, event: Event, channel: Channel):
        if not event.canReplay:
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_REPLAY_NOT_AVAIALABLE))
            return
        urlHelper = UrlTools(self.addon)
        streamInfo: ReplayStreamingInfo = self.helper.dynamic_call(LoginSession.obtain_replay_streaming_token,
                                              path=event.details.eventId)
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)
            playItem = self.listitem_from_url(requesturl=url,
                                              streamingToken=streamInfo.token,
                                              drmContentId=streamInfo.drmContentId)
            self.__add_event_info(playItem, channel, event)
#            if streamInfo.skip_forward_allowed:
            self.player.set_replay(True, streamInfo.prePaddingTime)
            self.player.play(item=url, listitem=playItem)
            self.__wait_for_player()
        except Exception as exc:
            xbmc.log('Error in __replay_event: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamic_call(LoginSession.delete_token, streaming_id=streamInfo.token)

    @staticmethod
    def __get_playable_instance(overview):
        if 'instances' in overview:
            for instance in overview['instances']:
                if instance['goPlayable']:
                    return instance

            return overview['instances'][0]  # return the first one if none was goPlayable
        return None

    def __play_vod(self, overview) -> xbmcgui.ListItem:
        playableInstance = self.__get_playable_instance(overview)
        if playableInstance is None:
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_CANNOTWATCH))

        helper = VideoHelpers(self.addon)
        urlHelper = UrlTools(self.addon)
        streamInfo = self.helper.dynamic_call(LoginSession.obtain_vod_streaming_token, streamId=playableInstance['id'])
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)

            playItem = helper.listitem_from_url(
                requesturl=url,
                streamingToken=streamInfo.token,
                drmContentId=streamInfo.drmContentId)
            self.__add_vod_info(playItem, overview)
            self.player.play(item=url, listitem=playItem)
            self.__wait_for_player()
            return playItem
        except Exception as exc:
            xbmc.log('Error in __play_vod: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamic_call(LoginSession.delete_token, streaming_id=streamInfo.token)
            return None

    def __play_recording(self, recording: SingleRecording, resumePoint) -> xbmcgui.ListItem:
        helper = VideoHelpers(self.addon)
        urlHelper = UrlTools(self.addon)
        streamInfo = self.helper.dynamic_call(LoginSession.obtain_recording_streaming_token, streamid=recording.id)
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)

            playItem = helper.listitem_from_url(
                requesturl=url,
                streamingToken=streamInfo.token,
                drmContentId=streamInfo.drmContentId)
            details = self.helper.dynamic_call(LoginSession.get_recording_details, id=recording.id)
            self.__add_recording_info(playItem, details)
            if resumePoint > 0:
                self.player.set_replay(True, resumePoint * 1000)
            else:
                self.player.set_replay(True, streamInfo.prePaddingTime)
            self.player.play(item=url, listitem=playItem)
            self.__wait_for_player()
            return playItem
        except Exception as exc:
            xbmc.log('Error in __play_vod: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamic_call(LoginSession.delete_token, streaming_id=streamInfo.token)
            return None

    def __record_event(self, event):
        self.helper.dynamic_call(LoginSession.record_event, eventId=event.id)

    def __record_show(self, event, channel):
        self.helper.dynamic_call(LoginSession.record_show, eventId=event.id, channelId=channel.channelId)

    def update_event(self, channel: Channel, event):
        if event is None:
            return
        if not event.hasDetails:
            event.details = self.helper.dynamic_call(LoginSession.get_event_details, eventId=event.id)

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
        isHelper = Helper(G.PROTOCOL, drm=G.DRM)
        isHelper.check_inputstream()

        if not self.channels.is_entitled(channel):
            xbmcgui.Dialog().ok('Info', self.addon.getLocalizedString(S.MSG_NOT_ENTITLED))
            return
        if not event.hasDetails:
            event.details = self.helper.dynamic_call(LoginSession.get_event_details, eventId=event.id)

        if not self.channels.supports_replay(channel):
            if self.user_wants_switch():
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

    def play_movie(self, movieOverview) -> xbmcgui.ListItem:
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        return self.__play_vod(movieOverview)

    def play_recording(self, recording: SingleRecording, resumePoint):
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        return self.__play_recording(recording, resumePoint)

    def play_channel(self, channel: Channel) -> xbmcgui.ListItem:
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        return self.__play_channel(channel)

    def __wait_for_player(self):
        cnt = 0
        while cnt < 10 and not self.player.isPlaying():
            cnt += 1
            xbmc.sleep(500)
        if cnt >= 10:
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_VIDEO_NOT_STARTED))
