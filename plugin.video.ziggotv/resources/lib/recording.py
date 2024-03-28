"""
module containing classes for recordings
"""
import dataclasses
import json
import os
import datetime

import xbmcaddon
import xbmcvfs

from resources.lib import utils
from resources.lib.globals import G


@dataclasses.dataclass
class Poster:
    """
    Small data class to store the poster
    """

    def __init__(self, posterJson):
        self.url = posterJson['url']
        self.type = posterJson['type']  # values seen: HighResPortrait


class Recording:
    """
    class to store all the data for a recording. Is used as a base class for others.
    """

    # pylint: disable=too-many-instance-attributes
    @dataclasses.dataclass
    class Language:
        """
        small class to store the data for a language
        """

        def __init__(self, languageJson):
            self.language = languageJson['lang']
            self.purpose = languageJson['purpose']

    def __init__(self, recordingJson):
        # pylint: disable=too-many-branches, too-many-statements
        self.poster = Poster(posterJson=recordingJson['poster'])
        self.recordingState = recordingJson['recordingState']  # recorded, planned
        self.minimumAge = 0
        self.private = False
        self.isAdult = False
        self.diskSpace = 0
        self.expirationDate = ''
        self.technicalDuration = 0
        self.isOttBlackout = False
        self.duration = 0
        self.bookmark = 0
        self.subtitles = []
        if 'captionLanguages' in recordingJson:
            for subtitle in recordingJson['captionLanguages']:
                self.subtitles.append(self.Language(subtitle))
        self.audioLanguages = []
        if 'audioLanguages' in recordingJson:
            for subtitle in recordingJson['audioLanguages']:
                self.audioLanguages.append(self.Language(subtitle))
        self.ottMarkers = []
        if 'ottMarkers' in recordingJson:
            self.ottMarkers = recordingJson['ottMarkers']
        self.channelId = None
        if 'channelId' in recordingJson:
            self.channelId = recordingJson['channelId']  # NL_000001_019401
        self.prePaddingOffset = recordingJson['prePaddingOffset']  # 300
        self.postPaddingOffset = recordingJson['postPaddingOffset']  # 900
        self.recordingType = recordingJson['recordingType']  # nDVR
        self.showId = None
        if 'showId' in recordingJson:
            self.showId = recordingJson['showId']  # crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000
        self.title = None
        if 'title' in recordingJson:
            self.title = recordingJson['title']
        self.startTime = recordingJson['startTime']  # 2024-01-17T11:00:00.000Z
        self.endTime = recordingJson['endTime']  # 2024-01-17T11:16:00.000Z
        self.source = recordingJson['source']  # single
        if 'id' in recordingJson:
            self.id = recordingJson['id']  # crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000~~2F237133469,
            # imi:517366be71fa5106c9215d9f1367cbacef4a4772
        else:
            self.id = recordingJson['episodeId']
        # self.type = recordingjson['type']  # single or season
        if 'ottPaddingsBlackout' in recordingJson:
            self.ottPaddingsBlackout = recordingJson['ottPaddingsBlackout']  # false
        else:
            self.ottPaddingsBlackout = recordingJson['isOttBlackout']  # false
        if 'isPremiereAirings' in recordingJson:
            self.isPremiereAirings = recordingJson['isPremiereAirings']  # false
        else:
            self.isPremiereAirings = False
        if 'deleteTime' in recordingJson:
            self.deleteTime = recordingJson['deleteTime']  # 2025-01-16T11:16:00.000Z
        else:
            self.deleteTime = recordingJson['expirationDate']  # ???
        if 'retentionPeriod' in recordingJson:
            self.retentionPeriod = recordingJson['retentionPeriod']  # 365
        else:
            self.retentionPeriod = 0
        if 'autoDeletionProtected' in recordingJson:
            self.autoDeletionProtected = recordingJson['autoDeletionProtected']  # false
        else:
            self.autoDeletionProtected = False
        self.isPremiere = recordingJson['isPremiere']  # false, true: when latest episode playing
        self.trickPlayControl = recordingJson['trickPlayControl']

    @property
    def isRecording(self) -> bool:
        """
        Returns True if the state of the Recording is recording or ongoing
        @return: True/False
        """
        return self.recordingState in ['recording', 'ongoing']

    @property
    def isPlanned(self):
        """
        Returns True if the state of the Recording is planned
        @return: True/False
        """
        return self.recordingState == 'planned'

    @property
    def isRecorded(self):
        """
        Returns True if the state of the Recording is recorded
        @return: True/False
        """
        return self.recordingState == 'recorded'


class SeasonRecording:
    """
    class for season/series recording
    """

    # pylint: disable=too-many-instance-attributes, too-few-public-methods
    def __init__(self, recordingJson):
        self.poster = Poster(posterJson=recordingJson['poster'])
        self.episodes = recordingJson['noOfEpisodes']
        self.seasonTitle = recordingJson['seasonTitle']
        self.showId = recordingJson['showId']
        self.minimumAge = 0
        if 'minimumAge' in recordingJson:
            self.minimumAge = recordingJson['minimumAge']
        self.channelId = recordingJson['channelId']
        self.diskSpace = 0
        if 'diskSpace' in recordingJson:
            self.diskSpace = recordingJson['diskSpace']
        self.title = recordingJson['title']
        self.source = recordingJson['source']
        self.id = recordingJson['id']
        self.isPremiereAirings = False
        if 'isPremiereAirings' in recordingJson:
            self.isPremiereAirings = recordingJson['isPremiereAirings']
        self.relevantEpisode = None
        if 'mostRelevantEpisode' in recordingJson:
            self.relevantEpisode = recordingJson['mostRelevantEpisode']
        self.episodes = []
        if 'episodes' in recordingJson:
            episodes = recordingJson['episodes']
            self.images = episodes['images']
            self.seasons = episodes['seasons']
            self.genres = episodes['genres']
            self.synopsis = ''
            if 'shortSynopsis' in episodes:
                self.synopsis = episodes['shortSynopsis']
            self.cnt = 0
            if 'total' in episodes:
                self.cnt = episodes['total']
            self.episodes = []
            for episode in episodes['data']:
                if episode['recordingState'] == 'planned':
                    recPlanned = PlannedRecording(episode)
                    self.episodes.append(recPlanned)
                else:
                    recSingle = SingleRecording(episode)
                    self.episodes.append(recSingle)

    def get_episodes(self, recType):
        """

        @param recType: one 'planned|recorded'
        @return: list of requested types
        """
        retList = []
        for episode in self.episodes:
            if recType == 'planned':
                if episode.recordingState == 'planned':
                    retList.append(episode)
            elif recType == 'recorded':
                if episode.recordingState != 'planned':
                    retList.append(episode)
        return retList


class SingleRecording(Recording):
    """
    class for a SingleRecording (not planned, not season).
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, recordingJson, season: SeasonRecording = None):
        super().__init__(recordingJson)
        if 'privateCopy' in recordingJson:
            self.private = recordingJson['privateCopy']
        else:
            self.private = False
        self.isAdult = recordingJson['containsAdult']
        if '' in recordingJson:
            self.diskSpace = recordingJson['diskSpace']  # 0.041527778
        else:
            self.diskSpace = 0
        self.technicalDuration = recordingJson['technicalDuration']
        self.isOttBlackout = recordingJson['isOttBlackout']  # false
        self.duration = recordingJson['duration']  # 598,
        self.bookmark = recordingJson['bookmark']  # 0
        self.viewState = recordingJson['viewState']  # notWatched
        self.season: SeasonRecording = season
        if self.season is not None:
            if self.channelId is None:
                self.channelId = self.season.channelId
            if self.showId is None:
                self.showId = self.season.showId
            if self.title is None:
                self.title = self.season.title


class PlannedRecording(Recording):
    """
    class for a planned recording (not a season or single recording).
    """

    def __init__(self, recordingJson):
        super().__init__(recordingJson)
        self.minimumAge = 0
        if 'minimumAge' in recordingJson:
            self.minimumAge = recordingJson['minimumAge']
        self.viewState = 'notWatched'


class RecordingList:
    """
    container class for a list of recordings of any type
    """

    # pylint: disable=too-few-public-methods
    def __init__(self, recordingsJson=None):
        self.recs = []
        if recordingsJson is None:
            self.total = 0
            self.size = 0
            self.quota = 0
            self.occupied = 0
            return

        self.total = recordingsJson['total']
        self.size = recordingsJson['size']
        self.quota = recordingsJson['quota']['quota']
        self.occupied = recordingsJson['quota']['occupied']
        for data in recordingsJson['data']:
            if data['type'] == 'season':
                season = SeasonRecording(data)
                self.recs.append(season)
            elif data['type'] == 'single':
                if data['recordingState'] == 'planned':
                    recPlanned = PlannedRecording(data)
                    self.recs.append(recPlanned)
                else:
                    recSingle = SingleRecording(data)
                    self.recs.append(recSingle)

    def find(self, eventId):
        """
        function to find a recording by its id
        @param eventId:
        @return: recording
        """
        for rec in self.recs:
            if isinstance(rec, SeasonRecording):
                season: SeasonRecording = rec
                for srec in season.episodes:
                    if srec.id == eventId:
                        return srec
            else:
                recording: Recording = rec
                if recording.id == eventId:
                    return rec
        return None


class SavedStateList:
    """
    class to keep the state of played recording. This is used to resume a recording at the point where
    playback was stopped the last time
    """

    def __init__(self, addon: xbmcaddon.Addon):
        self.addon = addon
        self.addonPath = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.states = {}
        self.fileName = self.addonPath + G.PLAYBACK_INFO
        targetdir = os.path.dirname(self.fileName)
        if targetdir == '':
            targetdir = os.getcwd()
        if not os.path.exists(targetdir):
            os.makedirs(targetdir)
        if not os.path.exists(self.fileName):
            with open(self.fileName, 'w', encoding='utf-8') as file:
                json.dump(self.states, file)
        self.__load()

    def __load(self):
        with open(self.fileName, 'r+', encoding='utf-8') as file:
            self.states = json.load(file)

    def add(self, itemId, position):
        """
        function to add/update the position of a recording
        @param itemId:
        @param position:
        @return:
        """
        self.states.update({itemId: {'position': position,
                                     'dateAdded': utils.DatetimeHelper.unix_datetime(datetime.datetime.now())}})
        with open(self.fileName, 'w', encoding='utf-8') as file:
            json.dump(self.states, file)

    def delete(self, itemId):
        """
        function to delete the recording from the state list
        @param itemId:
        @return:
        """
        if itemId in self.states:
            self.states.pop(itemId)

    def get(self, itemId):
        """
       function to find a recording by its id
       @param itemId:
       @return:
        """
        for item in self.states:
            if item == itemId:
                return self.states[item]['position']
        return None

    def cleanup(self, daysToKeep=365):
        """
        function to clean up saved recording states
        @param daysToKeep: 
        @return: 
        """
        expDate = datetime.datetime.now() - datetime.timedelta(days=daysToKeep)
        for item in list(self.states):
            if self.states[item]['dateAdded'] < utils.DatetimeHelper.unix_datetime(expDate):
                self.delete(item)
        with open(self.fileName, 'w', encoding='utf-8') as file:
            json.dump(self.states, file)
