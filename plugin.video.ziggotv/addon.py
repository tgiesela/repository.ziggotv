import traceback
import json
import os
import sys
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from urllib.parse import parse_qsl, quote

from resources.lib.Channel import Channel, ChannelList
from resources.lib.ZiggoPlayer import VideoHelpers
from resources.lib.events import ChannelGuide
from resources.lib.globals import G, S

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from xbmcaddon import Addon

from resources.lib.recording import RecordingList, SingleRecording, PlannedRecording, SeasonRecording, \
     SavedStateList
from resources.lib.utils import SharedProperties, ProxyHelper

try:
    from inputstreamhelper import Helper
except:
    pass

from resources.lib.webcalls import LoginSession, WebException


class ZiggoPlugin:
    def __init__(self, my_addon):
        self.series_overviews = []
        self.movie_overviews = []
        self.url = None
        self.addon: xbmcaddon.Addon = my_addon
        self.addon_path = xbmcvfs.translatePath(my_addon.getAddonInfo('profile'))
        self.helper = ProxyHelper(my_addon)
        self.videoHelper = VideoHelpers(self.addon)
        self.epg = ChannelGuide(my_addon)
        self.__initialization()

    @staticmethod
    def __stopPlayer():
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()

    def pluginPath(self, name):
        return self.addon_path + name

    def selectProfile(self):
        custinfo: {} = self.helper.dynamicCall(LoginSession.get_customer_info)
        profile_id = self.addon.getSettingString('profile')
        if 'assignedDevices' in custinfo:
            default_profile_id = custinfo['assignedDevices'][0]['defaultProfileId']
        else:
            default_profile_id = None
        if profile_id == '':
            profile_id = default_profile_id
        profiles = {}
        profile_list = []
        preselect_index = 0
        for profile in custinfo['profiles']:
            profiles.update({profile['name']: profile['profileId']})
            profile_list.append(profile['name'])
            if profile['profileId'] == profile_id:
                preselect_index = len(profile_list) - 1

        title = xbmc.getLocalizedString(41003)
        selected_profile = xbmcgui.Dialog().select(heading=title, list=profile_list, preselect=preselect_index)
        profile_id = profiles[profile_list[selected_profile]]
        self.addon.setSetting('profile', profile_id)

    def setActiveProfile(self):
        custinfo: {} = self.helper.dynamicCall(LoginSession.get_customer_info)
        profile = self.addon.getSettingString('profile')
        if 'assignedDevices' in custinfo:
            default_profile_id = custinfo['assignedDevices'][0]['defaultProfileId']
        else:
            default_profile_id = None
        if profile == '':  # not yet set: ask for the profile to use
            self.selectProfile()
        chosen_profile = self.addon.getSetting('profile')
        if chosen_profile == '':  # still not set, use default
            for profile in custinfo['profiles']:
                if profile['profileId'] == default_profile_id:
                    self.helper.dynamicCall(LoginSession.set_active_profile(profile, profile=profile))
                    xbmc.log("ACTIVE PROFILE: {0}".format(default_profile_id), xbmc.LOGDEBUG)
        else:
            for profile in custinfo['profiles']:
                if profile['profileId'] == chosen_profile:
                    self.helper.dynamicCall(LoginSession.set_active_profile, profile=profile)
                    xbmc.log("ACTIVE PROFILE: {0}".format(profile), xbmc.LOGDEBUG)

    def __initialization(self):
        self.checkService()
        self.setActiveProfile()

    def load_movie_overviews(self):
        file = self.pluginPath(G.MOVIE_INFO)
        if Path(file).exists():
            self.movie_overviews = json.loads(Path(file).read_text())
        else:
            self.movie_overviews = []

    def load_series_overviews(self):
        file = self.pluginPath(G.SERIES_INFO)
        if Path(file).exists():
            self.series_overviews = json.loads(Path(file).read_text())
        else:
            self.series_overviews = []

    def saveMovieOverviews(self):
        Path(self.pluginPath(G.MOVIE_INFO)).write_text(json.dumps(self.movie_overviews))

    def saveSeriesOverviews(self):
        Path(self.pluginPath(G.SERIES_INFO)).write_text(json.dumps(self.series_overviews))

    @staticmethod
    def listItem_from_channel(video: Channel) -> xbmcgui.ListItem:
        li = xbmcgui.ListItem(label="{0}. {1}".format(video.logicalChannelNumber, video.name))
        thumbname = xbmc.getCacheThumbName(video.logo['focused'])
        thumbfile = xbmcvfs.translatePath('special://thumbnails/' + thumbname[0:1] + '/' + thumbname)
        if os.path.exists(thumbfile):
            os.remove(thumbfile)
        if len(video.imageStream) > 0:
            thumbname = xbmc.getCacheThumbName(video.imageStream['full'])
            thumbfile = (
                xbmcvfs.translatePath(
                    'special://thumbnails/' + thumbname[0:1] + '/' + thumbname.split('.')[0] + '.jpg'))
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

    def listItem_from_recording(self, recording: SingleRecording, recType) -> xbmcgui.ListItem:
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

    def listItem_from_recordingSeason(self, recording: SeasonRecording, recType) -> xbmcgui.ListItem:
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
        self.__stopPlayer()

        helper = ProxyHelper(addon)
        videoHelper = VideoHelpers(addon)
        channels = helper.dynamicCall(LoginSession.get_channels)
        channel: Channel = None
        for c in channels:
            if c.id == path:
                channel = c
                break

        if channel is None:
            raise RuntimeError("Channel not found: " + path)

        try:
            self.epg.loadStoredEvents()
            self.epg.obtainEvents()
            channel.events = self.epg.getEvents(channel.id)
            xbmcplugin.endOfDirectory(__handle__, succeeded=False, updateListing=False, cacheToDisc=False)
            videoHelper.play_channel(channel=channel)
            event = channel.events.getCurrentEvent()
            secondsElapsed = 0
            while xbmc.Player().isPlaying():
                xbmc.sleep(500)
                secondsElapsed += 0.5
                if secondsElapsed > 60:
                    currentEvent = channel.events.getCurrentEvent()
                    if currentEvent.id != event.id:
                        videoHelper.updateEvent(channel, currentEvent)
                        event = currentEvent
                    secondsElapsed = 0
            xbmc.log('CHANNEL STOPPED: {0}'.format(channel.name), xbmc.LOGDEBUG)

        except Exception as exc:
            xbmc.log('Error in play_video: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)

    def play_movie(self, path):
        """
        Play a movie by the provided path.
        :param path: str
        :return: None
        """
        self.__stopPlayer()
        videoHelper = VideoHelpers(addon)

        parts = path.split(',')

        try:

            self.load_movie_overviews()
            movie_overview = None
            for overview in self.movie_overviews:
                if overview['id'] == parts[0]:
                    movie_overview = overview
                    break
            if movie_overview is None:
                raise Exception('Movie no longer found in stored movies!!')

            videoHelper.play_movie(movie_overview)
            xbmcplugin.endOfDirectory(__handle__, succeeded=False, updateListing=False, cacheToDisc=False)
            while xbmc.Player().isPlaying():
                xbmc.sleep(500)
            xbmc.log('VOD STOPPED: {0}'.format(path), xbmc.LOGDEBUG)

        except Exception as exc:
            xbmc.log('Error in play_movie: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)

    def play_recording(self, path, recType):
        """
        Play a movie by the provided path.
        :param path: str
        :return: None
        @param path: The id of the item to play
        @param recType: The type of recording (planned/recorded)
        """
        self.__stopPlayer()
        videoHelper = VideoHelpers(self.addon)
        if recType == 'planned':
            xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_STILL_PLANNED))
            xbmcplugin.endOfDirectory(__handle__, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        recList = SavedStateList(self.addon)
        resumePoint = recList.get(path)
        if resumePoint is None:
            resumePoint = 0
        else:
            t = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(seconds=resumePoint)
            selected = xbmcgui.Dialog().contextmenu([self.addon.getLocalizedString(S.MSG_PLAY_FROM_BEGINNING),
                                                     self.addon.getLocalizedString(S.MSG_RESUME_FROM).format(t.strftime('%H:%M:%S'))])
            if selected == 0:
                resumePoint = 0

        try:

            # details = self.helper.dynamicCall(LoginSession.getRecordingDetails, id=path)
            # if details is None:
            #     raise Exception('Recording no longer available!!!')

            videoHelper.play_recording(path, resumePoint)
            xbmcplugin.endOfDirectory(__handle__, succeeded=False, updateListing=False, cacheToDisc=False)
            savedTime = None
            while xbmc.Player().isPlaying():
                savedTime = xbmc.Player().getTime()
                xbmc.sleep(500)
            recList.add(path, savedTime)
            xbmc.log('RECORDING STOPPED: {0} at {1}'.format(path, savedTime), xbmc.LOGDEBUG)

        except Exception as exc:
            xbmc.log('Error in play_recording: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)

    def play_episode(self, path, seriesId, seasonId):
        """
        Play a movie by the provided path.
        @param path: str
        @param seasonId:
        @param seriesId:
        :return: None
        """
        self.__stopPlayer()
        videoHelper = VideoHelpers(addon)

        parts = path.split(',')

        try:

            self.load_series_overviews()
            _episode = None
            _season = None
            _overview = None
            for overview in self.series_overviews:
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
                raise Exception('Movie/Series no longer found!!')

            xbmcplugin.endOfDirectory(__handle__, succeeded=False, updateListing=False, cacheToDisc=False)
            while xbmc.Player().isPlaying():
                xbmc.sleep(500)
            xbmc.log('VOD STOPPED: {0}'.format(path), xbmc.LOGDEBUG)

        except Exception as exc:
            xbmc.log('Error in play_movie: type {0}, args {1}'.format(type(exc), exc.args), xbmc.LOGERROR)

    @staticmethod
    def __getPricingFromOffer(instance):
        if 'offers' in instance:
            offer = instance['offers'][0]
            price = '({0} {1})'.format(offer['priceDisplay'], offer['currency'])
            return price
        return '(???)'

    def listItem_from_movie(self, item, details, instance):
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
            tag.setTitle('[COLOR red]' + title + self.__getPricingFromOffer(instance) + '[/COLOR]')
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
    def listItem_from_seriesItem(item, overview):
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
    def listItem_from_genre(genre):
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
    def listItem_from_season(season, episodes):
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

    def listItem_from_episode(self, episode, season, details, instance):
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
                    tag.setTitle('[COLOR red]' + tag.getTitle() + self.__getPricingFromOffer(instance) + '[/COLOR]')
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
            url = '{0}?action=listing&category={2}&categoryId={1}'.format(self.url, categoryname, screen_id)
            is_folder = True
            listing.append((url, list_item, is_folder))
        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS)
        xbmcplugin.endOfDirectory(__handle__)

    def listCategories(self):
        """
        Create the list of video categories in the Kodi interface.
        :return: None
        """
        # Get video categories, the first 2 are fixed
        categories = {'Channels': self.addon.getLocalizedString(S.MENU_CHANNELS),
                      'Guide': self.addon.getLocalizedString(S.MENU_GUIDE),
                      'Recordings': self.addon.getLocalizedString(S.MENU_RECORDINGS),
                      'PlannedRecordings': self.addon.getLocalizedString(S.MENU_PLANNED_RECORDINGS)}
        response = self.helper.dynamicCall(LoginSession.obtain_vod_screens)
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
            list_item = xbmcgui.ListItem(label=categoryName)
            # Set additional info for the list item.
            tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
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
            is_folder = True
            # Add our item to the listing as a 3-element tuple.
            listing.append((url, list_item, is_folder))
        # Add our listing to Kodi.
        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        # xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS)
        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def listRecordings(self, recType):
        listing = []
        self.helper.dynamicCall(LoginSession.refreshRecordings, includeAdult=self.addon.getSettingBool('adult-allowed'))
        if recType == 'planned':
            recordings = self.helper.dynamicCall(LoginSession.getRecordingsPlanned)
        else:
            recordings = self.helper.dynamicCall(LoginSession.getRecordings)

        for rec in recordings.recs:
            if type(rec) is SingleRecording:
                li = self.listItem_from_recording(rec, recType)
                callback_url = (
                    '{0}?action=play&type=recording&id={1}&rectype={2}'.format(self.url, rec.id, recType))
                is_folder = False
            elif type(rec) is PlannedRecording:
                li = self.listItem_from_recording(rec, recType)
                callback_url = (
                    '{0}?action=play&type=recording&id={1}&rectype={2}'.format(self.url, rec.id, rec.recordingState))
                is_folder = False
            elif type(rec) is SeasonRecording:
                season: SeasonRecording = rec
                li = self.listItem_from_recordingSeason(season, recType)
                callback_url = '{0}?action=listshowrecording&recording={1}&type={2}'.format(self.url, rec.id, recType)
                is_folder = True
            else:
                continue
            li.setProperty('IsPlayable', 'false')  # Turn off to avoid kodi complaining about item not playing
            listing.append((callback_url, li, is_folder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def deleteRecording(self, id, recType):
        events = [id]
        shows = []
        if recType == 'planned':
            rslt = self.helper.dynamicCall(LoginSession.deleteRecordingsPlanned, events=events, shows=shows)
        else:
            rslt = self.helper.dynamicCall(LoginSession.deleteRecordings, events=events, shows=shows)
        xbmc.executebuiltin('Container.Update')
        xbmc.executebuiltin('Action(Back)')
        xbmcplugin.endOfDirectory(__handle__, succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __findSeason(recordingId, recordings: RecordingList):
        season: SeasonRecording = None
        for rec in recordings.recs:
            if type(rec) is SeasonRecording:
                if rec.id == recordingId:
                    season: SeasonRecording = rec
                    break
        if season is None:
            raise Exception('Cannot find series of recordings with id: {0}'.format(recordingId))
        return season

    def deleteShowRecording(self, recordingId, recType):
        if recType == 'planned':
            recordings = self.helper.dynamicCall(LoginSession.getRecordingsPlanned)
        else:
            recordings = self.helper.dynamicCall(LoginSession.getRecordings)
        season = self.__findSeason(recordingId, recordings)
        events = []
        shows = [season.showId]
        if recType == 'planned':
            rslt = self.helper.dynamicCall(LoginSession.deleteRecordingsPlanned,
                                           events=events,
                                           shows=shows,
                                           channelId=season.channelId)
        else:
            rslt = self.helper.dynamicCall(LoginSession.deleteRecordings,
                                           events=events,
                                           shows=shows,
                                           channelId=season.channelId)
        xbmc.executebuiltin('Container.Update')
        xbmc.executebuiltin('Action(Back)')
        xbmcplugin.endOfDirectory(__handle__, succeeded=True, updateListing=False, cacheToDisc=False)

    def listShowRecording(self, recordingId, recType):
        listing = []
        if recType == 'planned':
            recordings = self.helper.dynamicCall(LoginSession.getRecordingsPlanned)
        else:
            recordings = self.helper.dynamicCall(LoginSession.getRecordings)
        season: SeasonRecording = self.__findSeason(recordingId, recordings)
        for rec in season.getEpisodes(recType):
            rec.title = season.title
            li = self.listItem_from_recording(rec, recType)
            callback_url = '{0}?action=play&type=recording&id={1}&rectype={2}'.format(self.url,
                                                                                      rec.id, rec.recordingState)
            is_folder = True
            li.setProperty('IsPlayable', 'false')  # Turn off to avoid kodi complaining about item not playing
            listing.append((callback_url, li, is_folder))

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def listChannels(self):
        # Create a list for our items.
        listing = []
        channels = self.helper.dynamicCall(LoginSession.get_channels)
        entitlements = self.helper.dynamicCall(LoginSession.get_entitlements)
        channelList = ChannelList(channels, entitlements)
        channelList.entitledOnly = self.addon.getSettingBool('allowed-channels-only')
        channelList.applyFilter()

        # Iterate through channels
        for channel in channelList:  # create a list item using the song filename for the label
            subscribed = channelList.isEntitled(channel)
            li = self.listItem_from_channel(channel)
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
                callback_url = '{0}?action=play&type=channel&id={1}'.format(self.url, channel.id)
            else:
                tag.setTitle(title[0:title.find('.') + 1] + '[COLOR red]' + title[title.find('.') + 1:] + '[/COLOR]')
                callback_url = '{0}?action=cantplay&video={1}'.format(self.url, channel.id)
            li.setProperty('IsPlayable', 'false')  # Turn off to avoid kodi complaining about item not playing
            listing.append((callback_url, li, False))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def __get_series_overview(self, item_id):
        for overview in self.series_overviews:
            if overview['id'] == item_id:
                return overview

        overview = self.helper.dynamicCall(LoginSession.obtain_series_overview, id=item_id)
        self.series_overviews.append(overview)
        return overview

    def list_series_seasons(self, categoryId):
        listing = []
        self.load_series_overviews()
        overview = self.__get_series_overview(categoryId)
        episodes = self.helper.dynamicCall(LoginSession.get_episode_list, item=categoryId)
        if episodes is not None:
            overview.update({'seasons': episodes['seasons']})
        for season in episodes['seasons']:
            li = self.listItem_from_season(season, episodes)
            callback_url = '{0}?action=listseason&seriesId={1}&seasonId={2}'.format(self.url,
                                                                                    categoryId,
                                                                                    season['id'])
            is_folder = True
            listing.append((callback_url, li, is_folder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        self.saveSeriesOverviews()

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def list_series_episodes(self, seriesId, seasonId):
        listing = []
        self.load_series_overviews()
        _serie = None
        _season = None
        for serie in self.series_overviews:
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
                playable_instance = self.__get_playable_instance(details)
                li = self.listItem_from_episode(episode, _season, details, playable_instance)
                if playable_instance is not None:
                    callback_url = ('{0}?action=play&type=episode&id={1}'
                                    '&seasonId={2}&seriesId={3}').format(self.url,
                                                                         playable_instance['id'],
                                                                         seasonId,
                                                                         seriesId)
                else:
                    callback_url = '{0}?action=cantplay&video={1}'.format(self.url,
                                                                          '')
                li.setProperty('IsPlayable', 'false')
                is_folder = False
                listing.append((callback_url, li, is_folder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        self.saveSeriesOverviews()

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def list_genre_items(self, genreId):
        listing = []
        self.load_series_overviews()
        self.load_movie_overviews()
        grid_content = self.helper.dynamicCall(LoginSession.obtain_grid_screen_details, collection_id=genreId)

        for item in grid_content['items']:
            if item['type'] == 'ASSET':
                details = self.__get_details(item)
                playable_instance = self.__get_playable_instance(details)
                li = self.listItem_from_movie(item, details, playable_instance)
                if li.getProperty('IsPlayable') == 'true':
                    callback_url = '{0}?action=play&type=movie&id={1}'.format(self.url,
                                                                              playable_instance['id'])
                else:
                    callback_url = '{0}?action=cantplay&video={1}'.format(self.url, playable_instance['id'])
                listing.append((callback_url, li, False))
            elif item['type'] == 'SERIES':
                overview = self.__get_series_overview(item['id'])
                li = self.listItem_from_seriesItem(item, overview)
                callback_url = '{0}?action=listseries&seriesId={1}'.format(self.url, item['id'])
                is_folder = True
                listing.append((callback_url, li, is_folder))

        # Save overviews
        self.saveMovieOverviews()
        self.saveSeriesOverviews()
        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def list_genres(self, categoryId):
        listing = []
        screens = self.helper.dynamicCall(LoginSession.obtain_vod_screen_details, collection_id=categoryId)
        for screen in screens['collections']:
            if screen['collectionLayout'] == 'TileCollection':
                for genre in screen['items']:
                    if genre['type'] == 'LINK':
                        li = self.listItem_from_genre(genre)
                        callback_url = '{0}?action=listgenre&genreId={1}'.format(self.url, genre['gridLink']['id'])
                        is_folder = True
                        listing.append((callback_url, li, is_folder))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def listSeries(self, categoryId):
        listing = []
        screen_details = self.helper.dynamicCall(LoginSession.obtain_vod_screen_details, collection_id=categoryId)
        items_seen = []
        self.load_series_overviews()
        for collection in screen_details['collections']:
            for item in collection['items']:
                if item['id'] in items_seen:
                    continue
                if item['type'] == 'SERIES':
                    overview = self.__get_series_overview(item['id'])
                    li = self.listItem_from_seriesItem(item, overview)
                    items_seen.append((item['id']))
                    callback_url = '{0}?action=listseries&seriesId={1}'.format(self.url, item['id'])
                    is_folder = True
                    listing.append((callback_url, li, is_folder))

        # Save overviews
        Path(self.pluginPath(G.SERIES_INFO)).write_text(json.dumps(self.series_overviews))

        # Add our listing to Kodi.

        xbmcplugin.addDirectoryItems(__handle__, listing, len(listing))
        xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(__handle__)

    def __get_details(self, item):
        for overview in self.movie_overviews:
            if overview['id'] == item['id']:
                return overview

        if 'brandingProviderId' in item:
            overview = self.helper.dynamicCall(LoginSession.obtain_asset_details, id=item['id'],
                                               brandingProviderId=item[
                                                   'brandingProviderId'])
        else:
            overview = self.helper.dynamicCall(LoginSession.obtain_asset_details, id=item['id'])
        self.movie_overviews.append(overview)
        return overview

    def listMovies(self, categoryId):
        # Create a list for our items.
        listing = []
        movie_list = self.helper.dynamicCall(LoginSession.obtain_vod_screen_details, collection_id=categoryId)
        items_seen = []
        self.load_movie_overviews()
        for collection in movie_list['collections']:
            for item in collection['items']:
                if item['id'] in items_seen:
                    continue
                if item['type'] == 'ASSET':
                    details = self.__get_details(item)
                    playable_instance = self.__get_playable_instance(details)
                    if playable_instance is not None:
                        li = self.listItem_from_movie(item, details, playable_instance)
                        items_seen.append((item['id']))
                        if li.getProperty('IsPlayable') == 'true':
                            callback_url = '{0}?action=play&type=movie&id={1}'.format(self.url,
                                                                                      playable_instance['id'])
                        else:
                            callback_url = '{0}?action=cantplay&video={1}'.format(self.url, playable_instance['id'])
                        li.setProperty('IsPlayable', 'false')
                        listing.append((callback_url, li, False))

        # Save overviews
        Path(self.pluginPath(G.MOVIE_INFO)).write_text(json.dumps(self.movie_overviews))

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
                if params['categoryId'] == "Channels":
                    self.listChannels()
                elif params['categoryId'] == 'Recordings':
                    self.listRecordings('recorded')
                elif params['categoryId'] == 'PlannedRecordings':
                    self.listRecordings('planned')
                elif params['categoryId'] == G.MOVIES:
                    self.listMovies(params['category'])
                elif params['categoryId'] == G.SERIES:
                    self.listSeries(params['category'])
                elif params['categoryId'] == G.GENRES:
                    self.list_genres(params['category'])
            elif params['action'] == 'epg':
                xbmc.executebuiltin('RunScript(' +
                                    addon.getAddonInfo('path') +
                                    'epgscript.py,' +
                                    addon.getAddonInfo('id') + ')', True)
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
                    self.deleteRecording(params['id'], params['rectype'])
                elif params['type'] == 'showrecording':
                    self.deleteShowRecording(params['id'], params['rectype'])
            elif params['action'] == 'listseries':
                self.list_series_seasons(params['seriesId'])
            elif params['action'] == 'listseason':
                self.list_series_episodes(params['seriesId'], params['seasonId'])
            elif params['action'] == 'listgenre':
                self.list_genre_items(params['genreId'])
            elif params['action'] == 'listshowrecording':
                self.listShowRecording(params['recording'], params['type'])
            elif params['action'] == 'cantplay':
                # Play a video from a provided URL.
                xbmcgui.Dialog().ok('Error', self.addon.getLocalizedString(S.MSG_CANNOTWATCH))
                xbmcplugin.endOfDirectory(__handle__, succeeded=False, updateListing=False, cacheToDisc=False)
            elif params['action'] == 'selectProfile':
                self.selectProfile()
        else:
            # If the plugin is called from Kodi UI without any parameters,
            # display the list of video categories
            self.listCategories()
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
    def checkService():
        home: SharedProperties = SharedProperties(addon=addon)
        if home.isServiceActive():
            return
        secondsToWait = 30
        timeWaiting = 0
        interval = 0.5
        dlg = xbmcgui.DialogProgress()
        dlg.create('ZiggoTV', 'Waiting for service to start...')
        while (not home.isServiceActive() and
               timeWaiting < secondsToWait and not home.isServiceActive() and not dlg.iscanceled()):
            xbmc.sleep(int(interval * 1000))
            timeWaiting += interval
            dlg.update(int(timeWaiting / secondsToWait * 100), 'Waiting for service to start...')
        dlg.close()
        if not home.isServiceActive():
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
        plugin.router(sys.argv[2], __url__)
    except WebException as exc:
        xbmcgui.Dialog().ok('Error', '{0}'.format(exc.getResponse()))
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
    except Exception as exc:
        xbmcgui.Dialog().ok('Error', '{0}'.format(exc))
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
