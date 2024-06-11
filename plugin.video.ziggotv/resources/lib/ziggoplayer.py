"""
Module with classes for playing videos
"""
from datetime import datetime, timedelta

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib.channel import Channel, ChannelList
from resources.lib.listitemhelper import ListitemHelper
from resources.lib.recording import SingleRecording, SavedStateList
from resources.lib.streaminginfo import ReplayStreamingInfo
from resources.lib.urltools import UrlTools
from resources.lib.events import Event
from resources.lib.globals import S
from resources.lib.utils import ProxyHelper, SharedProperties
from resources.lib.webcalls import LoginSession


class ZiggoPlayer(xbmc.Player):
    """
    class extending the default VideoPlayer.
    """

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
        """
        method to set that the video is for replay and set an optional start time to position the video
        @param isReplay:
        @param time:
        @return:
        """
        self.replay = isReplay
        self.prePadding = time


class VideoHelpers:
    """
    class with helper functions to prepare playing a video/recording etc.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, addon: xbmcaddon.Addon):
        self.addon = addon
        self.helper = ProxyHelper(addon)
        self.player: ZiggoPlayer = ZiggoPlayer()
        self.liHelper: ListitemHelper = ListitemHelper(addon)
        self.customerInfo = self.helper.dynamic_call(LoginSession.get_customer_info)
        self.entitlements = self.helper.dynamic_call(LoginSession.get_entitlements)
        self.channels = ChannelList(self.helper.dynamic_call(LoginSession.get_channels), self.entitlements)
        self.uuId = SharedProperties(addon=self.addon).get_uuid()

    def user_wants_switch(self):
        """
        ask the use if a switch to channel is requested
        @return:
        """
        choice = xbmcgui.Dialog().yesno('Play',
                                        self.addon.getLocalizedString(S.MSG_SWITCH),
                                        self.addon.getLocalizedString(S.BTN_CANCEL),
                                        self.addon.getLocalizedString(S.BTN_SWITCH),
                                        False,
                                        xbmcgui.DLG_YESNO_NO_BTN)
        return choice

    def __add_event_info(self, playItem, channel: Channel, event):
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
            return None
        streamInfo = self.helper.dynamic_call(LoginSession.obtain_tv_streaming_token,
                                              channelId=channel.id, assetType=assetType)
        try:
            url = urlHelper.build_url(streamInfo.token, locator)
            playItem = self.liHelper.listitem_from_url(requesturl=url,
                                                       streamingToken=streamInfo.token,
                                                       drmContentId=streamInfo.drmContentId)
            event = channel.events.get_current_event()
            self.__add_event_info(playItem, channel, event)
            self.player.set_replay(False, 0)
            self.player.play(item=url, listitem=playItem)
            self.__wait_for_player()
            return playItem
        # pylint: disable=broad-exception-caught
        except Exception as exc:
            xbmc.log('Error in __play_channel: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamic_call(LoginSession.delete_token, streamingId=streamInfo.token)
            return None

    def __replay_event(self, event: Event, channel: Channel):
        if not event.canReplay:
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_REPLAY_NOT_AVAIALABLE))
            return
        resumePoint = self.get_resume_point(event.id)
        urlHelper = UrlTools(self.addon)
        streamInfo: ReplayStreamingInfo = self.helper.dynamic_call(LoginSession.obtain_replay_streaming_token,
                                                                   path=event.details.eventId)
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)
            playItem = self.liHelper.listitem_from_url(requesturl=url,
                                                       streamingToken=streamInfo.token,
                                                       drmContentId=streamInfo.drmContentId)
            self.__add_event_info(playItem, channel, event)
            #            if streamInfo.skip_forward_allowed:
            if resumePoint > 0:
                self.player.set_replay(True, int(resumePoint * 1000))
            else:
                self.player.set_replay(True, streamInfo.prePaddingTime)
            self.player.play(item=url, listitem=playItem)
            self.__wait_for_player()
            self.monitor_state(event.id)
        # pylint: disable=broad-exception-caught
        except Exception as exc:
            xbmc.log('Error in __replay_event: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamic_call(LoginSession.delete_token, streamingId=streamInfo.token)

    @staticmethod
    def __get_playable_instance(overview):
        if 'instances' in overview:
            for instance in overview['instances']:
                if instance['goPlayable']:
                    return instance

            return overview['instances'][0]  # return the first one if none was goPlayable
        return None

    def __play_vod(self, overview, resumePoint) -> xbmcgui.ListItem:
        playableInstance = self.__get_playable_instance(overview)
        if playableInstance is None:
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_CANNOTWATCH))
            return None

        urlHelper = UrlTools(self.addon)
        streamInfo = self.helper.dynamic_call(LoginSession.obtain_vod_streaming_token, streamId=playableInstance['id'])
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)

            playItem = self.liHelper.listitem_from_url(
                requesturl=url,
                streamingToken=streamInfo.token,
                drmContentId=streamInfo.drmContentId)
            self.__add_vod_info(playItem, overview)
            if resumePoint > 0:
                self.player.set_replay(True, int(resumePoint * 1000))
            else:
                self.player.set_replay(True, 0)
            self.player.play(item=url, listitem=playItem)
            self.__wait_for_player()
            return playItem
        # pylint: disable=broad-exception-caught
        except Exception as exc:
            xbmc.log('Error in __play_vod: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamic_call(LoginSession.delete_token, streamingId=streamInfo.token)
            return None

    def __play_recording(self, recording: SingleRecording, resumePoint) -> xbmcgui.ListItem:
        urlHelper = UrlTools(self.addon)
        streamInfo = self.helper.dynamic_call(LoginSession.obtain_recording_streaming_token, streamid=recording.id)
        try:
            url = urlHelper.build_url(streamInfo.token, streamInfo.url)

            playItem = self.liHelper.listitem_from_url(
                requesturl=url,
                streamingToken=streamInfo.token,
                drmContentId=streamInfo.drmContentId
            )
            details = self.helper.dynamic_call(LoginSession.get_recording_details, recordingId=recording.id)
            self.__add_recording_info(playItem, details)
            if resumePoint > 0:
                self.player.set_replay(True, int(resumePoint * 1000))
            else:
                self.player.set_replay(True, streamInfo.prePaddingTime)
            self.player.play(item=url, listitem=playItem)
            self.__wait_for_player()
            return playItem
        # pylint: disable=broad-exception-caught
        except Exception as exc:
            xbmc.log('Error in __play_vod: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)
            if streamInfo is not None and streamInfo.token is not None:
                self.helper.dynamic_call(LoginSession.delete_token, streamingId=streamInfo.token)
            return None

    def __record_event(self, event):
        self.helper.dynamic_call(LoginSession.record_event, eventId=event.id)
        xbmcgui.Dialog().notification('Info',
                                      self.addon.getLocalizedString(S.MSG_EVENT_SCHEDULED),
                                      xbmcgui.NOTIFICATION_INFO,
                                      2000)

    def __record_show(self, event, channel):
        self.helper.dynamic_call(LoginSession.record_show, eventId=event.id, channelId=channel.id)
        xbmcgui.Dialog().notification('Info',
                                      self.addon.getLocalizedString(S.MSG_SHOW_SCHEDULED),
                                      xbmcgui.NOTIFICATION_INFO,
                                      2000)

    def update_event(self, channel: Channel, event):
        """
        update the event information in the player to reflect the current event
        @param channel:
        @param event:
        @return:
        """
        if event is not None:
            title = event.title
        else:
            title = ''

        item = self.player.getPlayingItem()
        item.setLabel('{0}. {1}: {2}'.format(channel.logicalChannelNumber, channel.name, title))
        if event is not None:
            if not event.hasDetails:
                event.details = self.helper.dynamic_call(LoginSession.get_event_details, eventId=event.id)
            tag = item.getVideoInfoTag()
            tag.setPlot(event.details.description)
            tag.setTitle(event.title)
            if event.details.isSeries:
                tag.setEpisode(event.details.episode)
                tag.setSeason(event.details.season)
            tag.setArtists(event.details.actors)
        self.player.updateInfoTag(item)

    # pylint: disable=too-many-branches
    def play_epg(self, event: Event, channel: Channel):
        """
        Function to play something from the EPG. Can be an event, record event, record show, switch to channel
        @param event:
        @param channel:
        @return:
        """
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()

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
        choices.update({self.addon.getLocalizedString(S.BTN_CANCEL): 'cancel'})
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
        elif action == 'cancel':
            pass

    def play_movie(self, movieOverview, resumePoint) -> xbmcgui.ListItem:
        """
        Play a movie
        @param movieOverview:
        @return:
        """
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        return self.__play_vod(movieOverview, resumePoint)

    def play_recording(self, recording: SingleRecording, resumePoint):
        """
        play recording
        @param recording:
        @param resumePoint:
        @return:
        """
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        return self.__play_recording(recording, resumePoint)

    def play_channel(self, channel: Channel) -> xbmcgui.ListItem:
        """
        Play a channel
        @param channel:
        @return:
        """
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

    def monitor_state(self, path):
        """
        Function to save the position of a playing recording or replay of an event. This allows restart at
        a saved position.
        @param path:
        @return:
        """
        recList = SavedStateList(self.addon)
        savedTime = None
        while xbmc.Player().isPlaying():
            savedTime = xbmc.Player().getTime()
            xbmc.sleep(500)
        recList.add(path, savedTime)
        xbmc.log('PLAYING ITEM STOPPED: {0} at {1}'.format(path, savedTime), xbmc.LOGDEBUG)

    def get_resume_point(self, path) -> float:
        """
        Function to ask for a resume point if available. Then event or recording can be started from a
        saved position
        @param path:
        @return: position as fractional seconds
        """
        recList = SavedStateList(self.addon)
        resumePoint = recList.get(path)
        if resumePoint is None:
            return 0
        t = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(seconds=resumePoint)
        selected = xbmcgui.Dialog().contextmenu(
            [self.addon.getLocalizedString(S.MSG_PLAY_FROM_BEGINNING),
             self.addon.getLocalizedString(S.MSG_RESUME_FROM).format(t.strftime('%H:%M:%S'))])
        if selected == 0:
            resumePoint = 0
        return resumePoint
