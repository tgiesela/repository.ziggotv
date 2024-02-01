import datetime

import xbmcaddon
import xbmcvfs
import json
import os

from resources.lib import utils


class Poster:
    def __init__(self, posterjson):
        self.url = posterjson['url']
        self.type = posterjson['type']  # values seen: HighResPortrait


class Recording:
    class Language:
        def __init__(self, languagejson):
            self.language = languagejson['lang']
            self.purpose = languagejson['purpose']

    def __init__(self, recordingjson):
        self.poster = Poster(posterjson=recordingjson['poster'])
        self.recordingState = recordingjson['recordingState']  # recorded, planned
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
        if 'captionLanguages' in recordingjson:
            for subtitle in recordingjson['captionLanguages']:
                self.subtitles.append(self.Language(subtitle))
        self.audioLanguages = []
        if 'audioLanguages' in recordingjson:
            for subtitle in recordingjson['audioLanguages']:
                self.audioLanguages.append(self.Language(subtitle))
        self.ottMarkers = []
        if 'ottMarkers' in recordingjson:
            self.ottMarkers = recordingjson['ottMarkers']
        self.channelId = None
        if 'channelId' in recordingjson:
            self.channelId = recordingjson['channelId']  # NL_000001_019401
        self.prePaddingOffset = recordingjson['prePaddingOffset']  # 300
        self.postPaddingOffset = recordingjson['postPaddingOffset']  # 900
        self.recordingType = recordingjson['recordingType']  # nDVR
        self.showId = None
        if 'showId' in recordingjson:
            self.showId = recordingjson['showId']  # crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000
        self.title = None
        if 'title' in recordingjson:
            self.title = recordingjson['title']
        self.startTime = recordingjson['startTime']  # 2024-01-17T11:00:00.000Z
        self.endTime = recordingjson['endTime']  # 2024-01-17T11:16:00.000Z
        self.source = recordingjson['source']  # single
        if 'id' in recordingjson:
            self.id = recordingjson['id']  # crid:~~2F~~2Fgn.tv~~2F817615~~2FSH010806510000~~2F237133469,
            # imi:517366be71fa5106c9215d9f1367cbacef4a4772
        else:
            self.id = recordingjson['episodeId']
        # self.type = recordingjson['type']  # single or season
        if 'ottPaddingsBlackout' in recordingjson:
            self.ottPaddingsBlackout = recordingjson['ottPaddingsBlackout']  # false
        else:
            self.ottPaddingsBlackout = recordingjson['isOttBlackout']  # false
        self.isPremiereAirings = recordingjson['isPremiereAirings']  # false
        if 'deleteTime' in recordingjson:
            self.deleteTime = recordingjson['deleteTime']  # 2025-01-16T11:16:00.000Z
        else:
            self.deleteTime = recordingjson['expirationDate']  # ???
        if 'retentionPeriod' in recordingjson:
            self.retentionPeriod = recordingjson['retentionPeriod']  # 365
        else:
            self.retentionPeriod = 0
        if 'autoDeletionProtected' in recordingjson:
            self.autoDeletionProtected = recordingjson['autoDeletionProtected']  # false
        else:
            self.autoDeletionProtected = False
        self.isPremiere = recordingjson['isPremiere']  # false, true: when latest episode playing
        self.trickPlayControl = recordingjson['trickPlayControl']

    @property
    def isRecording(self):
        return self.recordingState == 'recording' or self.recordingState == 'ongoing'

    @property
    def isPlanned(self):
        return self.recordingState == 'planned'

    @property
    def isRecorded(self):
        return self.recordingState == 'recorded'


class SeasonRecording:
    def __init__(self, recordingJson):
        self.poster = Poster(posterjson=recordingJson['poster'])
        self.episodes = recordingJson['noOfEpisodes']
        self.seasonTitle = recordingJson['seasonTitle']
        self.showId = recordingJson['showId']
        self.minimumAge = recordingJson['minimumAge']
        self.channelId = recordingJson['channelId']
        if 'diskSpace' in recordingJson:
            self.diskSpace = recordingJson['diskSpace']
        else:
            self.diskSpace = 0
        self.title = recordingJson['title']
        self.source = recordingJson['source']
        self.id = recordingJson['id']
        self.isPremiereAirings = recordingJson['isPremiereAirings']
        self.relevantEpisode = recordingJson['mostRelevantEpisode']
        self.episodes = []
        if 'episodes' in recordingJson:
            episodes = recordingJson['episodes']
            self.images = episodes['images']
            self.seasons = episodes['seasons']
            self.genres = episodes['genres']
            self.synopsis = episodes['shortSynopsis']
            self.cnt = episodes['total']
            self.episodes = []
            for episode in episodes['data']:
                if episode['recordingState'] == 'planned':
                    recPlanned = PlannedRecording(episode)
                    self.episodes.append(recPlanned)
                else:
                    recSingle = SingleRecording(episode)
                    self.episodes.append(recSingle)

    def getEpisodes(self, recType):
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
    def __init__(self, recordingJson):
        super().__init__(recordingJson)
        self.minimumAge = recordingJson['minimumAge']
        self.viewState = 'notWatched'


class RecordingList:
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
        for rec in self.recs:
            if type(rec) is SeasonRecording:
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
    def __init__(self, addon: xbmcaddon.Addon):
        self.addon = addon
        self.addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.states = {}
        self.fileName = self.addon_path + 'playbackstates.json'
        targetdir = os.path.dirname(self.fileName)
        if targetdir == '':
            targetdir = os.getcwd()
        if not os.path.exists(targetdir):
            os.makedirs(targetdir)
        if not os.path.exists(self.fileName):
            with open(self.fileName, 'w') as file:
                json.dump(self.states, file)
        self.__load()

    def __load(self):
        with open(self.fileName, 'r+') as file:
            self.states = json.load(file)

    def add(self, id, position):
        self.states.update({id: {'position': position,
                                 'dateAdded': utils.DatetimeHelper.unixDatetime(datetime.datetime.now())}})
        with open(self.fileName, 'w') as file:
            json.dump(self.states, file)

    def delete(self, id):
        if id in self.states:
            self.states.pop(id)

    def get(self, id):
        for item in self.states:
            if item == id:
                return self.states[item]['position']
        return None

    def cleanup(self, daystokeep=365):
        expDate = datetime.datetime.now() - datetime.timedelta(days=daystokeep)
        for item in list(self.states):
            if self.states[item]['dateAdded'] < utils.DatetimeHelper.unixDatetime(expDate):
                self.delete(item)
        with open(self.fileName, 'w') as file:
            json.dump(self.states, file)
