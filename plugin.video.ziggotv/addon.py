"""
The actual addon implementation. From here the ziggo plugin menus are constructed.
"""

import traceback
import json
import sys
import typing
from pathlib import Path
from urllib.parse import parse_qsl

from resources.lib.channel import Channel, ChannelList
from resources.lib.listitemhelper import ListitemHelper
from resources.lib.ziggoplayer import VideoHelpers
from resources.lib.channelguide import ChannelGuide
from resources.lib.globals import G, S
from resources.lib.recording import RecordingList, SingleRecording, PlannedRecording, SeasonRecording
from resources.lib.utils import SharedProperties, ProxyHelper, WebException
from resources.lib.webcalls import LoginSession

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs


class ZiggoPlugin:
    # pylint: disable=too-many-instance-attributes
    """
    Implementation class of the Ziggo plugin
    """
    ADDONPATH = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
    ADDON: xbmcaddon.Addon = xbmcaddon.Addon()

    def __init__(self):
        self.handle = None
        self.replicationToken = None
        self.seriesOverviews = []
        self.movieOverviews = []
        self.url = None
        self.helper = ProxyHelper(self.ADDON)
        self.videoHelper = VideoHelpers(self.ADDON)
        self.listitemHelper = ListitemHelper(self.ADDON)
        self.__initialization()

    def plugin_path(self, name):
        """
        Function returns the full filename of the userdata folder of the addon
        @param name:
        @return:
        """
        return self.ADDONPATH + name

    def select_profile(self):
        """
        Function to select the profile from the addon settings menu.
        @return:
        """
        custinfo: {} = self.helper.dynamic_call(LoginSession.get_customer_info)
        profileId = self.ADDON.getSettingString('profile')
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
        self.ADDON.setSetting('profile', profileId)

    def __set_active_profile(self):
        """
        Function to set the active profile based on the Addon settings
        @return: nothing
        """
        custInfo: {} = self.helper.dynamic_call(LoginSession.get_customer_info)
        profile = self.ADDON.getSettingString('profile')
        if 'assignedDevices' in custInfo:
            defaultProfileId = custInfo['assignedDevices'][0]['defaultProfileId']
        else:
            defaultProfileId = None
        if profile == '':  # not yet set: ask for the profile to use
            self.select_profile()
        chosenProfile = self.ADDON.getSetting('profile')
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
        self.__check_service()
        self.__set_active_profile()

    def __load_movie_overviews(self):
        """
        loads the movies from disk if the file is present and stores it in the class variable movieOverviews
        this is used in between calls from the addon
        @return: nothing
        """
        file = self.plugin_path(G.MOVIE_INFO)
        if Path(file).exists():
            self.movieOverviews = json.loads(Path(file).read_text(encoding='utf-8'))
        else:
            self.movieOverviews = []

    def __load_series_overviews(self):
        """
        loads the series from disk if the file is present and stores it in the class variable seriesOverviews
        @return: nothing
        """
        file = self.plugin_path(G.SERIES_INFO)
        if Path(file).exists():
            self.seriesOverviews = json.loads(Path(file).read_text(encoding='utf-8'))
        else:
            self.seriesOverviews = []

    def __save_movie_overviews(self):
        """
        Saves the obtained movies in a disk file to be used during subsequent calls to the addon
        @return:
        """
        Path(self.plugin_path(G.MOVIE_INFO)).write_text(json.dumps(self.movieOverviews), encoding='utf-8')

    def __save_series_overviews(self):
        """
        Saves the obtained series in a disk file to be used during subsequent calls to the addon
        @return:
        """
        Path(self.plugin_path(G.SERIES_INFO)).write_text(json.dumps(self.seriesOverviews), encoding='utf-8')

    def play_channel(self, path):
        """
        Play a video by the provided path.
        :param path: str
        :return: None
        """
        # Create a playable item with a path to play.
        # If we do not use a script to play the video, a new instance of the video player is started, so the
        # video callbacks do not work
        helper = ProxyHelper(self.ADDON)
        videoHelper = VideoHelpers(self.ADDON)
        channels = helper.dynamic_call(LoginSession.get_channels)
        channel: Channel = None
        for c in channels:
            if c.id == path:
                channel = c
                break

        if channel is None:
            raise RuntimeError("Channel not found: " + path)

        try:
            epg = ChannelGuide(self.ADDON, channels)
            # epg.load_stored_events()
            epg.obtain_events()
            channel.events = epg.get_events(channel.id)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            videoHelper.play_channel(channel=channel)
            event = channel.events.get_current_event()
            secondsElapsed = 0
            while xbmc.Player().isPlaying():
                xbmc.sleep(500)
                secondsElapsed += 0.5
                if secondsElapsed > 60:
                    currentEvent = channel.events.get_current_event()
                    if currentEvent is not None:
                        if currentEvent.id != event.id:
                            videoHelper.update_event(channel, currentEvent)
                            event = currentEvent
                    secondsElapsed = 0
            xbmc.log('CHANNEL STOPPED: {0}'.format(channel.name), xbmc.LOGDEBUG)

        # pylint: disable=broad-exception-caught
        except Exception as excpt:
            xbmc.log('Error in play_video: type {0}, args {1}'.format(type(excpt), excpt.args), xbmc.LOGERROR)

    def play_movie(self, path):
        """
        Play a movie by the provided path.
        :param path: str
        :return: None
        """
        videoHelper = VideoHelpers(self.ADDON)

        parts = path.split(',')

        try:

            self.__load_movie_overviews()
            movieOverview = None
            for overview in self.movieOverviews:
                if overview['id'] == parts[0]:
                    movieOverview = overview
                    break
            if movieOverview is None:
                raise RuntimeError('Movie no longer found in stored movies!!')

            videoHelper.play_movie(movieOverview)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            videoHelper.monitor_state(path)

        # pylint: disable=broad-exception-caught
        except Exception as excpt:
            xbmc.log('Error in play_movie: type {0}, args {1}'.format(type(excpt), excpt.args), xbmc.LOGERROR)

    def play_recording(self, path, recType, seasonId=None):
        """
        Play a movie by the provided path.
        :param path: str
        :return: None
        @param seasonId: id of the season if applicable
        @param path: The id of the item to play
        @param recType: The type of recording (planned/recorded)
        """
        if recType == 'planned':
            recordings = self.helper.dynamic_call(LoginSession.get_recordings_planned)
        else:
            recordings = self.helper.dynamic_call(LoginSession.get_recordings)
        recording = None
        if seasonId is not None:
            season: SeasonRecording = self.__find_season(seasonId, recordings)
            for rec in season.get_episodes(recType):
                if rec.id == path:
                    recording = rec
        else:
            for rec in recordings.recs:
                if rec.id == path:
                    recording = rec
        if recording is None:
            raise RuntimeError("Recording with id {0} not found".format(path))

        videoHelper = VideoHelpers(self.ADDON)
        if recType == 'planned':
            xbmcgui.Dialog().ok('Error', self.ADDON.getLocalizedString(S.MSG_STILL_PLANNED))
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        resumePoint = videoHelper.get_resume_point(path)

        try:

            # details = self.helper.dynamicCall(LoginSession.getRecordingDetails, id=path)
            # if details is None:
            #     raise Exception('Recording no longer available!!!')

            videoHelper.play_recording(recording, resumePoint)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False, updateListing=False, cacheToDisc=False)
            videoHelper.monitor_state(path)

        # pylint: disable=broad-exception-caught
        except Exception as excpt:
            xbmc.log('Error in play_recording: type {0}, args {1}'.format(type(excpt), excpt.args), xbmc.LOGERROR)

    @staticmethod
    def __get_episode_and_season(seasons, seasonId, episodeId) -> typing.Tuple[str, str]:
        _season = ''
        _episode = ''
        for season in seasons:
            if season['id'] == seasonId:
                for episode in season['episodes']:
                    if episode['id'] == episodeId:
                        _episode = episode
                        _season = season
                        break
        return _season, _episode

    def play_episode(self, path, seriesId, seasonId):
        """
        Play a movie by the provided path.
        @param path: str
        @param seasonId:
        @param seriesId:
        :return: None
        """
        videoHelper = VideoHelpers(self.ADDON)

        parts = path.split(',')

        try:

            self.__load_series_overviews()
            _episode = None
            _season = None
            _overview = None
            for overview in self.seriesOverviews:
                if overview['id'] == seriesId:
                    _overview = overview
                    _season, _episode = self.__get_episode_and_season(overview['seasons'], seasonId, parts[0])
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

        # pylint: disable=broad-exception-caught
        except Exception as excpt:
            xbmc.log('Error in play_movie: type {0}, args {1}'.format(type(excpt), excpt.args), xbmc.LOGERROR)

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
        categories = {'Channels': self.ADDON.getLocalizedString(S.MENU_CHANNELS),
                      'Guide': self.ADDON.getLocalizedString(S.MENU_GUIDE),
                      'Recordings': self.ADDON.getLocalizedString(S.MENU_RECORDINGS),
                      'PlannedRecordings': self.ADDON.getLocalizedString(S.MENU_PLANNED_RECORDINGS)}
        response = self.helper.dynamic_call(LoginSession.obtain_vod_screens)
        screens = response['screens']
        if self.ADDON.getSettingBool('adult-allowed'):
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
        """
        Create list of recordings (planned or recorded)
        @param recType: type of recording (planned vs recorded)
        @return: nothing
        """

        listing = []
        self.helper.dynamic_call(LoginSession.refresh_recordings,
                                 includeAdult=self.ADDON.getSettingBool('adult-allowed'))
        if recType == 'planned':
            recordings = self.helper.dynamic_call(LoginSession.get_recordings_planned)
        else:
            recordings = self.helper.dynamic_call(LoginSession.get_recordings)

        for rec in recordings.recs:
            if isinstance(rec, SingleRecording):
                li = self.listitemHelper.listitem_from_recording(rec, recType)
                callbackUrl = (
                    '{0}?action=play&type=recording&id={1}&rectype={2}'.format(self.url, rec.id, recType))
                isFolder = False
            elif isinstance(rec, PlannedRecording):
                li = self.listitemHelper.listitem_from_recording(rec, recType)
                callbackUrl = (
                    '{0}?action=play&type=recording&id={1}&rectype={2}'.format(self.url, rec.id, rec.recordingState))
                isFolder = False
            elif isinstance(rec, SeasonRecording):
                season: SeasonRecording = rec
                li = self.listitemHelper.listitem_from_recording_season(season, recType)
                callbackUrl = '{0}?action=sublist&type=recording&recording={1}&rectype={2}'.format(self.url,
                                                                                                   rec.id,
                                                                                                   recType)
                isFolder = True
            else:
                continue
            li.setProperty('IsPlayable', 'false')  # Turn off to avoid kodi complaining about item not playing
            listing.append((callbackUrl, li, isFolder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle, updateListing=True)

    @staticmethod
    def __find_season(recordingId, recordings: RecordingList):
        season: SeasonRecording = None
        for rec in recordings.recs:
            if isinstance(rec, SeasonRecording):
                if rec.id == recordingId:
                    season: SeasonRecording = rec
                    break
        return season

    def list_show_recording(self, seasonId, recType):
        """
        Create list of episodes for a series/show
        @param seasonId: id of the show recording
        @param recType: type of recording (planned vs recorded)
        @return: nothing
        """

        listing = []
        self.helper.dynamic_call(LoginSession.refresh_recordings,
                                 includeAdult=self.ADDON.getSettingBool('adult-allowed'))
        if recType == 'planned':
            recordings = self.helper.dynamic_call(LoginSession.get_recordings_planned)
        else:
            recordings = self.helper.dynamic_call(LoginSession.get_recordings)
        season: SeasonRecording = self.__find_season(seasonId, recordings)
        if season is not None:
            for rec in season.get_episodes(recType):
                rec.title = season.title
                li = self.listitemHelper.listitem_from_recording(rec, recType, season)
                callbackUrl = ('{0}?action=play&type=recording&id={1}&rectype={2}&seasonId={3}'
                               .format(self.url,
                                       rec.id,
                                       rec.recordingState,
                                       season.id))
                isFolder = True
                li.setProperty('IsPlayable', 'false')  # Turn off to avoid kodi complaining about item not playing
                listing.append((callbackUrl, li, isFolder))
        else:
            xbmc.log('Season with id: {0} no longer found, maybe deleted via context menu'.format(seasonId),
                     xbmc.LOGDEBUG)

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle, updateListing=True)

    def list_channels(self):
        """
        Create list of channels
        @return: nothing
        """

        # Create a list for our items.
        listing = []
        channels = self.helper.dynamic_call(LoginSession.get_channels)
        entitlements = self.helper.dynamic_call(LoginSession.get_entitlements)
        channelList = ChannelList(channels, entitlements)
        channelList.entitledOnly = self.ADDON.getSettingBool('allowed-channels-only')
        channelList.apply_filter()

        # Iterate through channels
        for channel in channelList:  # create a list item using the song filename for the label
            subscribed = channelList.is_entitled(channel)
            li = self.listitemHelper.listitem_from_channel(channel)
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

        overview = self.helper.dynamic_call(LoginSession.obtain_series_overview, seriesId=itemId)
        self.seriesOverviews.append(overview)
        return overview

    def list_series_seasons(self, categoryId):
        """
        Create list of seasons for a series/show
        @param categoryId: id of the series/show
        @return: nothing
        """
        listing = []
        self.__load_series_overviews()
        overview = self.__get_series_overview(categoryId)
        episodes = self.helper.dynamic_call(LoginSession.get_episode_list, item=categoryId)
        if episodes is not None:
            overview.update({'seasons': episodes['seasons']})
        for season in episodes['seasons']:
            li = self.listitemHelper.listitem_from_season(season, episodes)
            callbackUrl = '{0}?action=sublist&type=season&seriesId={1}&seasonId={2}'.format(self.url,
                                                                                            categoryId,
                                                                                            season['id'])
            isFolder = True
            listing.append((callbackUrl, li, isFolder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        self.__save_series_overviews()

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_series_episodes(self, seriesId, seasonId):
        """
        Create list of episodes for a series/show
        @param seriesId: id of the series/show
        @param seasonId: id of the season
        @return: nothing
        """
        listing = []
        self.__load_series_overviews()
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
                li = self.listitemHelper.listitem_from_episode(episode, _season, details, playableInstance)
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

        self.__save_series_overviews()

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_genre_items(self, genreId):
        """
        Create list of movies/series for a specific genre
        @param genreId:
        @return: nothing
        """

        listing = []
        self.__load_series_overviews()
        self.__load_movie_overviews()
        gridContent = self.helper.dynamic_call(LoginSession.obtain_grid_screen_details, collectionId=genreId)

        for item in gridContent['items']:
            if item['type'] == 'ASSET':
                details = self.__get_details(item)
                playableInstance = self.__get_playable_instance(details)
                li = self.listitemHelper.listitem_from_movie(item, details, playableInstance)
                if li.getProperty('IsPlayable') == 'true':
                    callbackUrl = '{0}?action=play&type=movie&id={1}'.format(self.url,
                                                                             playableInstance['id'])
                else:
                    callbackUrl = '{0}?action=cantplay&video={1}'.format(self.url, playableInstance['id'])
                li.setProperty('IsPlayable', 'false')
                listing.append((callbackUrl, li, False))
            elif item['type'] == 'SERIES':
                overview = self.__get_series_overview(item['id'])
                li = self.listitemHelper.listitem_from_seriesitem(item, overview)
                callbackUrl = '{0}?action=sublist&type=series&seriesId={1}'.format(self.url, item['id'])
                isFolder = True
                listing.append((callbackUrl, li, isFolder))

        # Save overviews
        self.__save_movie_overviews()
        self.__save_series_overviews()
        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_genres(self, categoryId):
        """
        Create list of genres for movies and series
        @param categoryId:
        @return: nothing
        """

        listing = []
        screens = self.helper.dynamic_call(LoginSession.obtain_vod_screen_details, collectionId=categoryId)
        for screen in screens['collections']:
            if screen['collectionLayout'] == 'TileCollection':
                for genre in screen['items']:
                    if genre['type'] == 'LINK':
                        li = self.listitemHelper.listitem_from_genre(genre)
                        callbackUrl = '{0}?action=sublist&type=genre&genreId={1}'.format(self.url,
                                                                                         genre['gridLink']['id'])
                        isFolder = True
                        listing.append((callbackUrl, li, isFolder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_series(self, categoryId):
        """
        Create list of series (vod)
        @param categoryId:
        @return: nothing
        """

        listing = []
        screenDetails = self.helper.dynamic_call(LoginSession.obtain_vod_screen_details, collectionId=categoryId)
        itemsSeen = []
        self.__load_series_overviews()
        for collection in screenDetails['collections']:
            for item in collection['items']:
                if item['id'] in itemsSeen:
                    continue
                if item['type'] == 'SERIES':
                    overview = self.__get_series_overview(item['id'])
                    li = self.listitemHelper.listitem_from_seriesitem(item, overview)
                    itemsSeen.append((item['id']))
                    callbackUrl = '{0}?action=sublist&type=series&seriesId={1}'.format(self.url, item['id'])
                    isFolder = True
                    listing.append((callbackUrl, li, isFolder))

        # Save overviews
        Path(self.plugin_path(G.SERIES_INFO)).write_text(json.dumps(self.seriesOverviews), encoding='utf-8')

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
            overview = self.helper.dynamic_call(LoginSession.obtain_asset_details, assetId=item['id'],
                                                brandingProviderId=item[
                                                    'brandingProviderId'])
        else:
            overview = self.helper.dynamic_call(LoginSession.obtain_asset_details, assetId=item['id'])
        self.movieOverviews.append(overview)
        return overview

    def list_movies(self, categoryId):
        """
        Create list of movies (vod)
        @param categoryId:
        @return: nothing
        """
        # Create a list for our items.
        listing = []
        movieList = self.helper.dynamic_call(LoginSession.obtain_vod_screen_details, collectionId=categoryId)
        itemsSeen = []
        self.__load_movie_overviews()
        for collection in movieList['collections']:
            for item in collection['items']:
                if item['id'] in itemsSeen:
                    continue
                if item['type'] == 'ASSET':
                    details = self.__get_details(item)
                    playableInstance = self.__get_playable_instance(details)
                    if playableInstance is not None:
                        li = self.listitemHelper.listitem_from_movie(item, details, playableInstance)
                        itemsSeen.append((item['id']))
                        if li.getProperty('IsPlayable') == 'true':
                            callbackUrl = '{0}?action=play&type=movie&id={1}'.format(self.url,
                                                                                     playableInstance['id'])
                        else:
                            callbackUrl = '{0}?action=cantplay&video={1}'.format(self.url, playableInstance['id'])
                        li.setProperty('IsPlayable', 'false')
                        listing.append((callbackUrl, li, False))

        # Save overviews
        Path(self.plugin_path(G.MOVIE_INFO)).write_text(json.dumps(self.movieOverviews), encoding='utf-8')

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(self.handle, listing, len(listing))
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def __router_list(self, params):
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

    def __router_play(self, params):
        # Play a video from a provided URL.
        if params['type'] == 'channel':
            self.play_channel(params['id'])
        elif params['type'] == 'recording':
            if 'seasonId' in params:
                self.play_recording(params['id'], params['rectype'], params['seasonId'])
            else:
                self.play_recording(params['id'], params['rectype'])
        elif params['type'] == 'episode':
            self.play_episode(params['id'], params['seriesId'], params['seasonId'])
        elif params['type'] == 'movie':
            self.play_movie(params['id'])

    def __router_sublist(self, params):
        if params['type'] == 'series':
            self.list_series_seasons(params['seriesId'])
        elif params['type'] == 'season':
            self.list_series_episodes(params['seriesId'], params['seasonId'])
        elif params['type'] == 'genre':
            self.list_genre_items(params['genreId'])
        elif params['type'] == 'recording':
            self.list_show_recording(params['recording'], params['rectype'])

    def router(self, paramString, url, handle):
        """
            Router function that calls other functions
            depending on the provided param_string

            @param paramString: string containing the parameters from the url
            @param url:
            @param handle: to be used in xbmc calls
            """
        # Parse a URL-encoded param_string to the dictionary of
        # {<parameter>: <value>} elements
        self.url = url
        self.handle = handle
        params = dict(parse_qsl(paramString[1:]))
        # Check the parameters passed to the plugin
        if params:
            if params['action'] == 'listing':
                self.__router_list(params)
            elif params['action'] == 'epg':
                xbmc.executebuiltin('RunScript(' +
                                    self.ADDON.getAddonInfo('path') +
                                    'epgscript.py,' +
                                    self.ADDON.getAddonInfo('id') + ')', True)
            elif params['action'] == 'subcategory':
                self.list_subcategories(params['categoryId'])
            elif params['action'] == 'play':
                self.__router_play(params)
            elif params['action'] == 'sublist':
                self.__router_sublist(params)
            elif params['action'] == 'cantplay':
                # Play a video from a provided URL.
                xbmcgui.Dialog().ok('Error', self.ADDON.getLocalizedString(S.MSG_CANNOTWATCH))
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

    def __check_service(self):
        home: SharedProperties = SharedProperties(addon=self.ADDON)
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

    plugin = ZiggoPlugin()

    # Get the plugin url in plugin:// notation.
    __url__ = sys.argv[0]
    # Get the plugin handle as an integer number.
    __handle__ = int(sys.argv[1])
    # Call the router function and pass the plugin call parameters to it.
    try:
        plugin.router(sys.argv[2], __url__, __handle__)
    except WebException as exc:
        xbmcgui.Dialog().ok('Error', '{0}'.format(exc.response))
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
    # pylint: disable=broad-exception-caught
    except Exception as exc:
        xbmcgui.Dialog().ok('Error', f'{exc}')
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
