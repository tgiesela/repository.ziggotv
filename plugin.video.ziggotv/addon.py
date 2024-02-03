"""
The actual addon implementation. From here the ziggo plugin menus are constructed.
"""

import traceback
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote

from resources.lib.channel import Channel, ChannelList
from resources.lib.ziggoplayer import VideoHelpers
from resources.lib.channel import ChannelGuide
from resources.lib.globals import G, S
from resources.lib.recording import RecordingList, SingleRecording, PlannedRecording, SeasonRecording, \
    SavedStateList
from resources.lib.utils import SharedProperties, ProxyHelper
from resources.lib.webcalls import LoginSession, WebException

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from xbmcaddon import Addon


class ZiggoPlugin:
    """
    Implementation class of the Ziggo plugin
    """

    def __init__(self, myAddon):
        self.handle = None
        self.replicationToken = None
        self.seriesOverviews = []
        self.movieOverviews = []
        self.url = None
        self.addon: xbmcaddon.Addon = myAddon
        self.addonPath = xbmcvfs.translatePath(myAddon.getAddonInfo('profile'))
        self.helper = ProxyHelper(myAddon)
        self.videoHelper = VideoHelpers(self.addon)
        self.epg = None
        self.__initialization()

    @staticmethod
    def __stop_player():
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()

    def plugin_path(self, name):
        """
        Function returns the full filename of the userdata folder of the addon
        @param name:
        @return:
        """
        return self.addonPath + name

    def select_profile(self):
        """
        Function to select the profile from the addon settings menu.
        @return:
        """
        custinfo: {} = self.helper.dynamic_call(LoginSession.get_customer_info)
        profileId = self.addon.getSettingString('profile')
        if 'assignedDevices' in custinfo:
            defaultProfileId = custinfo['assignedDevices'][0]['defaultProfileId']
        else:
            defaultProfileId = None
        if profileId == '':
            profileId = defaultProfileId
        profiles = {}
        profileList = []
        preselectIndex = 0
        for profile in custinfo['profiles']:
            profiles.update({profile['name']: profile['profileId']})
            profileList.append(profile['name'])
            if profile['profileId'] == profileId:
                preselectIndex = len(profileList) - 1

        title = xbmc.getLocalizedString(41003)
        selectedProfile = xbmcgui.Dialog().select(heading=title, list=profileList, preselect=preselectIndex)
        profileId = profiles[profileList[selectedProfile]]
        self.addon.setSetting('profile', profileId)

    def set_active_profile(self):
        """
        Function to set the active profile based on the Addon settings
        @return: nothing
        """
        custInfo: {} = self.helper.dynamic_call(LoginSession.get_customer_info)
        profile = self.addon.getSettingString('profile')
        if 'assignedDevices' in custInfo:
            defaultProfileId = custInfo['assignedDevices'][0]['defaultProfileId']
        else:
            defaultProfileId = None
        if profile == '':  # not yet set: ask for the profile to use
            self.select_profile()
        chosenProfile = self.addon.getSetting('profile')
        if chosenProfile == '':  # still not set, use default
            for profile in custInfo['profiles']:
                if profile['profileId'] == defaultProfileId:
                    self.helper.dynamic_call(LoginSession.set_active_profile(profile, profile=profile))
                    xbmc.log(f"ACTIVE PROFILE: {defaultProfileId}", xbmc.LOGDEBUG)
        else:
            for profile in custInfo['profiles']:
                if profile['profileId'] == chosenProfile:
                    self.helper.dynamic_call(LoginSession.set_active_profile, profile=profile)
                    xbmc.log(f"ACTIVE PROFILE: {profile}", xbmc.LOGDEBUG)

    def __initialization(self):
        self.check_service()
        self.set_active_profile()

    def load_movie_overviews(self):
        file = self.plugin_path(G.MOVIE_INFO)
        if Path(file).exists():
            self.movieOverviews = json.loads(Path(file).read_text())
        else:
            self.movieOverviews = []

    def load_series_overviews(self):
        file = self.plugin_path(G.SERIES_INFO)
        if Path(file).exists():
            self.seriesOverviews = json.loads(Path(file).read_text())
        else:
            self.seriesOverviews = []

    def save_movie_overviews(self):
        Path(self.plugin_path(G.MOVIE_INFO)).write_text(json.dumps(self.movieOverviews))

    def save_series_overviews(self):
        Path(self.plugin_path(G.SERIES_INFO)).write_text(json.dumps(self.seriesOverviews))

    def listitem_from_recording(self, recording: SingleRecording, recType) -> xbmcgui.ListItem:
        try:
            start = datetime.strptime(recording.startTime,
                                      '%Y-%m-%dT%H:%M:%S.%fZ').astimezone()
        except TypeError:
            # Due to a bug in datetime see https://bugs.python.org/issue27400
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

        items = [(self.addon.getLocalizedString(S.MSG_DELETE),
                  'RunAddon({0},action=delete&type=recording&id={1}&rectype={2})'.format(self.addon.getAddonInfo('id'),
                                                                                         quote(recording.id),
                                                                                         recType)),
                 (self.addon.getLocalizedString(S.BTN_PLAY),
                  'RunAddon({0},action=play&type=recording&id={1}&rectype={2})'.format(self.addon.getAddonInfo('id'),
                                                                                       quote(recording.id),
                                                                                       recording.recordingState))]
        li.addContextMenuItems(items, True)

        return li

    def listitem_from_recording_season(self, recording: SeasonRecording, recType) -> xbmcgui.ListItem:
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

        items = [(self.addon.getLocalizedString(S.MSG_DELETE),
                  'RunAddon({0},action=delete&type=showrecording&id={1}&rectype={2})'.format(
                      self.addon.getAddonInfo('id'),
                      quote(recording.id),
                      recType))]
        li.addContextMenuItems(items, True)
        return li

    def play_channel(self, path):
        """
        Play a video by the provided path.
        :param path: str
        :return: None
        """
        # Create a playable item with a path to play.
        # If we do not use a script to play the video, a new instance of the video player is started, so the
        # video callbacks do not work
        self.__stop_player()

        helper = ProxyHelper(self.addon)
        videoHelper = VideoHelpers(self.addon)
        channels = helper.dynamic_call(LoginSession.get_channels)
        channel: Channel = None
        for c in channels:
            if c.id == path:
                channel = c
                break

        if channel is None:
            raise RuntimeError("Channel not found: " + path)

        try:
            self.epg = ChannelGuide(self.addon, channels)
            self.epg.load_stored_events()
            self.epg.obtain_events()
            channel.events = self.epg.get_events(channel.id)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            videoHelper.play_channel(channel=channel)
            event = channel.events.get_current_event()
            secondsElapsed = 0
            while xbmc.Player().isPlaying():
                xbmc.sleep(500)
                secondsElapsed += 0.5
                if secondsElapsed > 60:
                    currentEvent = channel.events.get_current_event()
                    if currentEvent.id != event.id:
                        videoHelper.update_event(channel, currentEvent)
                        event = currentEvent
                    secondsElapsed = 0
            xbmc.log('CHANNEL STOPPED: {0}'.format(channel.name), xbmc.LOGDEBUG)

        except Exception as excpt:
            xbmc.log('Error in play_video: type {0}, args {1}'.format(type(excpt), excpt.args), xbmc.LOGERROR)

    def play_movie(self, path):
        """
        Play a movie by the provided path.
        :param path: str
        :return: None
        """
        self.__stop_player()
        videoHelper = VideoHelpers(self.addon)

        parts = path.split(',')

        try:

            self.load_movie_overviews()
            movieOverview = None
            for overview in self.movieOverviews:
                if overview['id'] == parts[0]:
                    movieOverview = overview
                    break
            if movieOverview is None:
                raise RuntimeError('Movie no longer found in stored movies!!')

            videoHelper.play_movie(movieOverview)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            while xbmc.Player().isPlaying():
                xbmc.sleep(500)
            xbmc.log('VOD STOPPED: {0}'.format(path), xbmc.LOGDEBUG)

        except Exception as excpt:
            xbmc.log('Error in play_movie: type {0}, args {1}'.format(type(excpt), excpt.args), xbmc.LOGERROR)

    def play_recording(self, path, recType):
        """
        Play a movie by the provided path.
        :param path: str
        :return: None
        @param path: The id of the item to play
        @param recType: The type of recording (planned/recorded)
        """
        if recType == 'planned':
            recordings = self.helper.dynamic_call(LoginSession.get_recordings_planned)
        else:
            recordings = self.helper.dynamic_call(LoginSession.get_recordings)

        recording = None
        for rec in recordings.recs:
            if rec.id == path:
                recording = rec
        if recording is None:
            raise RuntimeError("Recording with id {0} not found".format(path))

        self.__stop_player()
        videoHelper = VideoHelpers(self.addon)
        if recType == 'planned':
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_STILL_PLANNED))
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        recList = SavedStateList(self.addon)
        resumePoint = recList.get(path)
        if resumePoint is None:
            resumePoint = 0
        else:
            t = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(seconds=resumePoint)
            selected = xbmcgui.Dialog().contextmenu(
                [self.addon.getLocalizedString(S.MSG_PLAY_FROM_BEGINNING),
                 self.addon.getLocalizedString(S.MSG_RESUME_FROM).format(t.strftime('%H:%M:%S'))])
            if selected == 0:
                resumePoint = 0

        try:

            # details = self.helper.dynamicCall(LoginSession.getRecordingDetails, id=path)
            # if details is None:
            #     raise Exception('Recording no longer available!!!')

            videoHelper.play_recording(recording, resumePoint)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            savedTime = None
            while xbmc.Player().isPlaying():
                savedTime = xbmc.Player().getTime()
                xbmc.sleep(500)
            recList.add(path, savedTime)
            xbmc.log('RECORDING STOPPED: {0} at {1}'.format(path, savedTime), xbmc.LOGDEBUG)

        except Exception as excpt:
            xbmc.log('Error in play_recording: type {0}, args {1}'.format(type(excpt), excpt.args), xbmc.LOGERROR)

    def play_episode(self, path, seriesId, seasonId):
        """
        Play a movie by the provided path.
        @param path: str
        @param seasonId:
        @param seriesId:
        :return: None
        """
        self.__stop_player()
        videoHelper = VideoHelpers(self.addon)

        parts = path.split(',')

        try:

            self.load_series_overviews()
            _episode = None
            _season = None
            _overview = None
            for overview in self.seriesOverviews:
                if overview['id'] == seriesId:
                    _overview = overview
                    for season in overview['seasons']:
                        if season['id'] == seasonId:
                            for episode in season['episodes']:
                                if episode['id'] == parts[0]:
                                    _episode = episode
                                    _season = season
                                    break
                    break
            if _season is not None and _episode is not None:
                overview = _episode['overview']
                videoHelper.play_movie(overview)
            else:
                raise RuntimeError('Movie/Series no longer found!!')

            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            while xbmc.Player().isPlaying():
                xbmc.sleep(500)
            xbmc.log('VOD STOPPED: {0}'.format(path), xbmc.LOGDEBUG)

        except Exception as excpt:
            xbmc.log('Error in play_movie: type {0}, args {1}'.format(type(excpt), excpt.args), xbmc.LOGERROR)

    @staticmethod
    def __get_pricing_from_offer(instance):
        if 'offers' in instance:
            offer = instance['offers'][0]
            price = '({0} {1})'.format(offer['priceDisplay'], offer['currency'])
            return price
        return '(???)'

    @staticmethod
    def listitem_from_channel(video: Channel) -> xbmcgui.ListItem:
        li = xbmcgui.ListItem(label="{0}. {1}".format(video.logicalChannelNumber, video.name))
        thumbname = xbmc.getCacheThumbName(video.logo['focused'])
        thumbfile = xbmcvfs.translatePath('special://thumbnails/' + thumbname[0:1] + '/' + thumbname)
        if os.path.exists(thumbfile):
            os.remove(thumbfile)
        if len(video.imageStream) > 0:
            thumbname = xbmc.getCacheThumbName(video.imageStream['full'])
            thumbfile = (
                xbmcvfs.translatePath(
                    'special://thumbnails/' + thumbname[0:1] + '/' + thumbname.split('.', maxsplit=1)[0] + '.jpg'))
            if os.path.exists(thumbfile):
                os.remove(thumbfile)
            li.setArt({'icon': video.logo['focused'],
                       'thumb': video.logo['focused'],
                       'poster': video.imageStream['full']})
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

        return li

    @staticmethod
    def listitem_from_seriesitem(item, overview):
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

        return li

    def list_subcategories(self, screenId):
        """
        Create the list of sub categories in the Kodi interface.
        :return: None
        """
        categories = [G.SERIES, G.MOVIES, G.GENRES]
        listing = []
        for categoryname in categories:
            listItem = xbmcgui.ListItem(label=categoryname)
            tag: xbmc.InfoTagVideo = listItem.getVideoInfoTag()
            tag.setTitle(categoryname)
            tag.setMediaType('video')
            tag.setGenres([categoryname])
            url = '{0}?action=listing&category={2}&categoryId={1}'.format(self.url, categoryname, screenId)
            isFolder = True
            listing.append((url, listItem, isFolder))
        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS)
        xbmcplugin.endOfDirectory(self.handle)

    def list_categories(self):
        """
        Create the list of video categories in the Kodi interface.
        :return: None
        """
        # Get video categories, the first 2 are fixed
        categories = {'Channels': self.addon.getLocalizedString(S.MENU_CHANNELS),
                      'Guide': self.addon.getLocalizedString(S.MENU_GUIDE),
                      'Recordings': self.addon.getLocalizedString(S.MENU_RECORDINGS),
                      'PlannedRecordings': self.addon.getLocalizedString(S.MENU_PLANNED_RECORDINGS)}
        response = self.helper.dynamic_call(LoginSession.obtain_vod_screens)
        screens = response['screens']
        if self.addon.getSettingBool('adult-allowed'):
            screens.append(response['hotlinks']['adultRentScreen'])
        for screen in screens:
            categories.update({screen['id']: screen['title']})

        # Create a list for our items.
        listing = []
        # Iterate through categories
        for categoryId, categoryName in categories.items():
            # Create a list item with a text label and a thumbnail image.
            listItem = xbmcgui.ListItem(label=categoryName)
            # Set additional info for the list item.
            tag: xbmc.InfoTagVideo = listItem.getVideoInfoTag()
            tag.setTitle(categoryName)
            tag.setMediaType('video')
            tag.setGenres([categoryName])
            if categoryId == 'Channels':
                url = '{0}?action=listing&category={1}&categoryId={2}'.format(self.url, categoryName, categoryId)
            elif categoryId == 'Guide':
                url = '{0}?action=epg'.format(self.url)
            elif categoryId == 'Recordings':
                url = '{0}?action=listing&category={1}&categoryId={2}'.format(self.url, categoryName, categoryId)
            elif categoryId == 'PlannedRecordings':
                url = '{0}?action=listing&category={1}&categoryId={2}'.format(self.url, categoryName, categoryId)
            else:
                url = '{0}?action=subcategory&category={1}&categoryId={2}'.format(self.url, categoryName, categoryId)
            # is_folder = True means that this item opens a sub-list of lower level items.
            isFolder = True
            # Add our item to the listing as a 3-element tuple.
            listing.append((url, listItem, isFolder))
        # Add our listing to Kodi.
        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        # xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS)
        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_recordings(self, recType):
        listing = []
        self.helper.dynamic_call(LoginSession.refresh_recordings,
                                 includeAdult=self.addon.getSettingBool('adult-allowed'))
        if recType == 'planned':
            recordings = self.helper.dynamic_call(LoginSession.get_recordings_planned)
        else:
            recordings = self.helper.dynamic_call(LoginSession.get_recordings)

        for rec in recordings.recs:
            if isinstance(rec, SingleRecording):
                li = self.listitem_from_recording(rec, recType)
                callbackUrl = (
                    '{0}?action=play&type=recording&id={1}&rectype={2}'.format(self.url, rec.id, recType))
                isFolder = False
            elif isinstance(rec, PlannedRecording):
                li = self.listitem_from_recording(rec, recType)
                callbackUrl = (
                    '{0}?action=play&type=recording&id={1}&rectype={2}'.format(self.url, rec.id, rec.recordingState))
                isFolder = False
            elif isinstance(rec, SeasonRecording):
                season: SeasonRecording = rec
                li = self.listitem_from_recording_season(season, recType)
                callbackUrl = '{0}?action=listshowrecording&recording={1}&type={2}'.format(self.url, rec.id, recType)
                isFolder = True
            else:
                continue
            li.setProperty('IsPlayable', 'false')  # Turn off to avoid kodi complaining about item not playing
            listing.append((callbackUrl, li, isFolder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def delete_recording(self, recordingId, recType):
        events = [recordingId]
        shows = []
        if recType == 'planned':
            rslt = self.helper.dynamic_call(LoginSession.delete_recordings_planned, events=events, shows=shows)
            self.replicationToken = rslt['replicationToken']
        else:
            rslt = self.helper.dynamic_call(LoginSession.delete_recordings, events=events, shows=shows)
            self.replicationToken = rslt['replicationToken']
        xbmc.executebuiltin('Container.Update')
        xbmc.executebuiltin('Action(Back)')
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __find_season(recordingId, recordings: RecordingList):
        season: SeasonRecording = None
        for rec in recordings.recs:
            if isinstance(rec, SeasonRecording):
                if rec.id == recordingId:
                    season: SeasonRecording = rec
                    break
        if season is None:
            raise Exception('Cannot find series of recordings with id: {0}'.format(recordingId))
        return season

    def delete_show_recording(self, recordingId, recType):
        if recType == 'planned':
            recordings = self.helper.dynamic_call(LoginSession.get_recordings_planned)
        else:
            recordings = self.helper.dynamic_call(LoginSession.get_recordings)
        season = self.__find_season(recordingId, recordings)
        events = []
        shows = [season.showId]
        if recType == 'planned':
            rslt = self.helper.dynamic_call(LoginSession.delete_recordings_planned,
                                            events=events,
                                            shows=shows,
                                            channelId=season.channelId)
        else:
            rslt = self.helper.dynamic_call(LoginSession.delete_recordings,
                                            events=events,
                                            shows=shows,
                                            channelId=season.channelId)
        xbmc.executebuiltin('Container.Update')
        xbmc.executebuiltin('Action(Back)')
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, updateListing=False, cacheToDisc=False)

    def list_show_recording(self, recordingId, recType):
        listing = []
        if recType == 'planned':
            recordings = self.helper.dynamic_call(LoginSession.get_recordings_planned)
        else:
            recordings = self.helper.dynamic_call(LoginSession.get_recordings)
        season: SeasonRecording = self.__find_season(recordingId, recordings)
        for rec in season.get_episodes(recType):
            rec.title = season.title
            li = self.listitem_from_recording(rec, recType)
            callbackUrl = '{0}?action=play&type=recording&id={1}&rectype={2}'.format(self.url,
                                                                                     rec.id, rec.recordingState)
            isFolder = True
            li.setProperty('IsPlayable', 'false')  # Turn off to avoid kodi complaining about item not playing
            listing.append((callbackUrl, li, isFolder))

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_channels(self):
        # Create a list for our items.
        listing = []
        channels = self.helper.dynamic_call(LoginSession.get_channels)
        entitlements = self.helper.dynamic_call(LoginSession.get_entitlements)
        channelList = ChannelList(channels, entitlements)
        channelList.entitledOnly = self.addon.getSettingBool('allowed-channels-only')
        channelList.apply_filter()

        # Iterate through channels
        for channel in channelList:  # create a list item using the song filename for the label
            subscribed = channelList.is_entitled(channel)
            li = self.listitem_from_channel(channel)
            tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
            title = tag.getTitle()
            tag.setSortTitle(title)
            tag.setPlot('')
            tag.setPlotOutline('')
            #  see https://alwinesch.github.io/group__python___info_tag_video.html#gaabca7bfa2754c91183000f0d152426dd
            #  for more tags

            if not subscribed:
                li.setProperty('IsPlayable', 'false')
            if channel.locators['Default'] is None:
                li.setProperty('IsPlayable', 'false')
            if li.getProperty('IsPlayable') == 'true':
                callbackUrl = '{0}?action=play&type=channel&id={1}'.format(self.url, channel.id)
            else:
                tag.setTitle(title[0:title.find('.') + 1] + '[COLOR red]' + title[title.find('.') + 1:] + '[/COLOR]')
                callbackUrl = '{0}?action=cantplay&video={1}'.format(self.url, channel.id)
            li.setProperty('IsPlayable', 'false')  # Turn off to avoid kodi complaining about item not playing
            listing.append((callbackUrl, li, False))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def __get_series_overview(self, itemId):
        for overview in self.seriesOverviews:
            if overview['id'] == itemId:
                return overview

        overview = self.helper.dynamic_call(LoginSession.obtain_series_overview, id=itemId)
        self.seriesOverviews.append(overview)
        return overview

    def list_series_seasons(self, categoryId):
        listing = []
        self.load_series_overviews()
        overview = self.__get_series_overview(categoryId)
        episodes = self.helper.dynamic_call(LoginSession.get_episode_list, item=categoryId)
        if episodes is not None:
            overview.update({'seasons': episodes['seasons']})
        for season in episodes['seasons']:
            li = self.listitem_from_season(season, episodes)
            callbackUrl = '{0}?action=listseason&seriesId={1}&seasonId={2}'.format(self.url,
                                                                                   categoryId,
                                                                                   season['id'])
            isFolder = True
            listing.append((callbackUrl, li, isFolder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        self.save_series_overviews()

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_series_episodes(self, seriesId, seasonId):
        listing = []
        self.load_series_overviews()
        _serie = None
        _season = None
        for serie in self.seriesOverviews:
            if serie['id'] == seriesId:
                _serie = serie
                for season in serie['seasons']:
                    if season['id'] == seasonId:
                        _season = season
                        break
                break
        if _serie is None or _season is None:
            xbmcgui.Dialog().ok('Error', 'Missing series/season')
            return

        if _season['id'] == seasonId:
            for episode in _season['episodes']:
                details = self.__get_details(episode)
                episode.update({'overview': details})
                playableInstance = self.__get_playable_instance(details)
                li = self.listitem_from_episode(episode, _season, details, playableInstance)
                if playableInstance is not None:
                    callbackUrl = ('{0}?action=play&type=episode&id={1}'
                                   '&seasonId={2}&seriesId={3}').format(self.url,
                                                                        playableInstance['id'],
                                                                        seasonId,
                                                                        seriesId)
                else:
                    callbackUrl = '{0}?action=cantplay&video={1}'.format(self.url,
                                                                         '')
                li.setProperty('IsPlayable', 'false')
                isFolder = False
                listing.append((callbackUrl, li, isFolder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        self.save_series_overviews()

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_genre_items(self, genreId):
        listing = []
        self.load_series_overviews()
        self.load_movie_overviews()
        gridContent = self.helper.dynamic_call(LoginSession.obtain_grid_screen_details, collection_id=genreId)

        for item in gridContent['items']:
            if item['type'] == 'ASSET':
                details = self.__get_details(item)
                playableInstance = self.__get_playable_instance(details)
                li = self.listitem_from_movie(item, details, playableInstance)
                if li.getProperty('IsPlayable') == 'true':
                    callbackUrl = '{0}?action=play&type=movie&id={1}'.format(self.url,
                                                                             playableInstance['id'])
                else:
                    callbackUrl = '{0}?action=cantplay&video={1}'.format(self.url, playableInstance['id'])
                listing.append((callbackUrl, li, False))
            elif item['type'] == 'SERIES':
                overview = self.__get_series_overview(item['id'])
                li = self.listitem_from_seriesitem(item, overview)
                callbackUrl = '{0}?action=listseries&seriesId={1}'.format(self.url, item['id'])
                isFolder = True
                listing.append((callbackUrl, li, isFolder))

        # Save overviews
        self.save_movie_overviews()
        self.save_series_overviews()
        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_genres(self, categoryId):
        listing = []
        screens = self.helper.dynamic_call(LoginSession.obtain_vod_screen_details, collection_id=categoryId)
        for screen in screens['collections']:
            if screen['collectionLayout'] == 'TileCollection':
                for genre in screen['items']:
                    if genre['type'] == 'LINK':
                        li = self.listitem_from_genre(genre)
                        callbackUrl = '{0}?action=listgenre&genreId={1}'.format(self.url, genre['gridLink']['id'])
                        isFolder = True
                        listing.append((callbackUrl, li, isFolder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_series(self, categoryId):
        listing = []
        screenDetails = self.helper.dynamic_call(LoginSession.obtain_vod_screen_details, collection_id=categoryId)
        itemsSeen = []
        self.load_series_overviews()
        for collection in screenDetails['collections']:
            for item in collection['items']:
                if item['id'] in itemsSeen:
                    continue
                if item['type'] == 'SERIES':
                    overview = self.__get_series_overview(item['id'])
                    li = self.listitem_from_seriesitem(item, overview)
                    itemsSeen.append((item['id']))
                    callbackUrl = '{0}?action=listseries&seriesId={1}'.format(self.url, item['id'])
                    isFolder = True
                    listing.append((callbackUrl, li, isFolder))

        # Save overviews
        Path(self.plugin_path(G.SERIES_INFO)).write_text(json.dumps(self.seriesOverviews))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def __get_details(self, item):
        for overview in self.movieOverviews:
            if overview['id'] == item['id']:
                return overview

        if 'brandingProviderId' in item:
            overview = self.helper.dynamic_call(LoginSession.obtain_asset_details, id=item['id'],
                                                brandingProviderId=item[
                                                   'brandingProviderId'])
        else:
            overview = self.helper.dynamic_call(LoginSession.obtain_asset_details, id=item['id'])
        self.movieOverviews.append(overview)
        return overview

    def list_movies(self, categoryId):
        # Create a list for our items.
        listing = []
        movieList = self.helper.dynamic_call(LoginSession.obtain_vod_screen_details, collection_id=categoryId)
        itemsSeen = []
        self.load_movie_overviews()
        for collection in movieList['collections']:
            for item in collection['items']:
                if item['id'] in itemsSeen:
                    continue
                if item['type'] == 'ASSET':
                    details = self.__get_details(item)
                    playableInstance = self.__get_playable_instance(details)
                    if playableInstance is not None:
                        li = self.listitem_from_movie(item, details, playableInstance)
                        itemsSeen.append((item['id']))
                        if li.getProperty('IsPlayable') == 'true':
                            callbackUrl = '{0}?action=play&type=movie&id={1}'.format(self.url,
                                                                                      playableInstance['id'])
                        else:
                            callbackUrl = '{0}?action=cantplay&video={1}'.format(self.url, playableInstance['id'])
                        li.setProperty('IsPlayable', 'false')
                        listing.append((callbackUrl, li, False))

        # Save overviews
        Path(self.plugin_path(G.MOVIE_INFO)).write_text(json.dumps(self.movieOverviews))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def router(self, paramString, url, handle):
        """
            Router function that calls other functions
            depending on the provided param_string
            :type url: url from plugin invocation
            :param paramString:
            :return:
            """
        # Parse a URL-encoded param_string to the dictionary of
        # {<parameter>: <value>} elements
        self.url = url
        self.handle = handle
        params = dict(parse_qsl(paramString[1:]))
        # Check the parameters passed to the plugin
        if params:
            if params['action'] == 'listing':
                # Display the list of videos in a provided category.
                if params['categoryId'] == "Channels":
                    self.list_channels()
                elif params['categoryId'] == 'Recordings':
                    self.list_recordings('recorded')
                elif params['categoryId'] == 'PlannedRecordings':
                    self.list_recordings('planned')
                elif params['categoryId'] == G.MOVIES:
                    self.list_movies(params['category'])
                elif params['categoryId'] == G.SERIES:
                    self.list_series(params['category'])
                elif params['categoryId'] == G.GENRES:
                    self.list_genres(params['category'])
            elif params['action'] == 'epg':
                xbmc.executebuiltin('RunScript(' +
                                    self.addon.getAddonInfo('path') +
                                    'epgscript.py,' +
                                    self.addon.getAddonInfo('id') + ')', True)
            elif params['action'] == 'subcategory':
                self.list_subcategories(params['categoryId'])
            elif params['action'] == 'play':
                # Play a video from a provided URL.
                if params['type'] == 'channel':
                    self.play_channel(params['id'])
                elif params['type'] == 'recording':
                    self.play_recording(params['id'], params['rectype'])
                elif params['type'] == 'episode':
                    self.play_episode(params['id'], params['seriesId'], params['seasonId'])
                elif params['type'] == 'movie':
                    self.play_movie(params['id'])
            elif params['action'] == 'delete':
                if params['type'] == 'recording':
                    self.delete_recording(params['id'], params['rectype'])
                elif params['type'] == 'showrecording':
                    self.delete_show_recording(params['id'], params['rectype'])
            elif params['action'] == 'listseries':
                self.list_series_seasons(params['seriesId'])
            elif params['action'] == 'listseason':
                self.list_series_episodes(params['seriesId'], params['seasonId'])
            elif params['action'] == 'listgenre':
                self.list_genre_items(params['genreId'])
            elif params['action'] == 'listshowrecording':
                self.list_show_recording(params['recording'], params['type'])
            elif params['action'] == 'cantplay':
                # Play a video from a provided URL.
                xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_CANNOTWATCH))
                xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            elif params['action'] == 'selectProfile':
                self.select_profile()
        else:
            # If the plugin is called from Kodi UI without any parameters,
            # display the list of video categories
            self.list_categories()
        # Close opened session if any
        # self.helper.dynamicCall(LoginSession.close)

    @staticmethod
    def __get_playable_instance(overview):
        if 'instances' in overview:
            for instance in overview['instances']:
                if instance['goPlayable']:
                    return instance

            return overview['instances'][0]  # return the first one if none was goPlayable
        return None

    @staticmethod
    def check_service():
        home: SharedProperties = SharedProperties(addon=addon)
        if home.is_service_active():
            return
        secondsToWait = 30
        timeWaiting = 0
        interval = 0.5
        dlg = xbmcgui.DialogProgress()
        dlg.create('ZiggoTV', 'Waiting for service to start...')
        while (not home.is_service_active() and
               timeWaiting < secondsToWait and not home.is_service_active() and not dlg.iscanceled()):
            xbmc.sleep(int(interval * 1000))
            timeWaiting += interval
            dlg.update(int(timeWaiting / secondsToWait * 100), 'Waiting for service to start...')
        dlg.close()
        if not home.is_service_active():
            raise RuntimeError('Service did not start in time')


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
    # if sys.argv[1] == 'selectProfile':
    #     plugin.selectProfile()
    #     exit(0)

    # Get the plugin url in plugin:// notation.
    __url__ = sys.argv[0]
    # Get the plugin handle as an integer number.
    __handle__ = int(sys.argv[1])
    # Call the router function and pass the plugin call parameters to it.
    try:
        plugin.router(sys.argv[2], __url__, __handle__)
    except WebException as exc:
        xbmcgui.Dialog().ok('Error', '{0}'.format(exc.get_response()))
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
    except Exception as exc:
        xbmcgui.Dialog().ok('Error', f'{exc}')
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
