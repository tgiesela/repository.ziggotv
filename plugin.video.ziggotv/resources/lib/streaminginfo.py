"""
Contains classes to hold streaming info, including token, for different types
"""


class StreamingInfo:
    """
    Base Class containing streaming info
    """

    def __init__(self, streamingJson):
        self.registrationRequired = streamingJson['deviceRegistrationRequired']
        self.drmContentId = streamingJson['drmContentId']
        self.isAdult = False
        if 'isAdult' in streamingJson:
            self.isAdult = streamingJson['isAdult']
        self.token = None


class ReplayStreamingInfo:

    def __init__(self, streamingJson):
        self.registrationRequired = streamingJson['deviceRegistrationRequired']
        self.drmContentId = streamingJson['drmContentId']
        if 'licenceDurationSeconds' in streamingJson:
            self.licenseDurationSeconds = streamingJson['licenceDurationSeconds']
        else:
            self.licenseDurationSeconds = -1
        self.endTime = streamingJson['eventSessionEndTime']
        self.startTime = streamingJson['eventSessionStartTime']
        self.prePaddingTime = streamingJson['prePaddingTime']
        self.postPaddingTime = streamingJson['postPaddingTime']
        self.thumbnailUrl = streamingJson['thumbnailServiceUrl']
        self.isAdult = False
        if 'isAdult' in streamingJson:
            self.isAdult = streamingJson['isAdult']
        self.ageRating = streamingJson['ageRating']
        self.fallbackUrl = streamingJson['fallbackUrl']
        self.url = streamingJson['url']
        self.isAvad = streamingJson['isAvad']
        self.token = None


class VodStreamingInfo:
    def __init__(self, streamingJson):
        self.registrationRequired = streamingJson['deviceRegistrationRequired']
        self.drmContentId = streamingJson['drmContentId']
        self.displayProviderName = streamingJson['displayProviderName']
        self.displayProvider = streamingJson['displayProvider']
        self.contentProviderName = streamingJson['contentProviderName']
        self.contentProvider = streamingJson['contentProvider']
        self.thumbnailUrl = streamingJson['thumbnailServiceUrl']
        self.url = streamingJson['url']
        if 'licenceDurationSeconds' in streamingJson:
            self.licenseDurationSeconds = streamingJson['licenceDurationSeconds']
        else:
            self.licenseDurationSeconds = -1
        self.token = None


class RecordingStreamingInfo:
    def __init__(self, streamingJson):
        self.registrationRequired = streamingJson['deviceRegistrationRequired']
        self.trickPlayControl = streamingJson['trickPlayControl']
        self.thumbnailUrl = streamingJson['thumbnailServiceUrl']
        self.eventSessionStartTime = streamingJson['eventSessionStartTime']
        self.eventSessionEndTime = streamingJson['eventSessionEndTime']
        self.prePaddingTime = streamingJson['prePaddingTime']
        self.postPaddingTime = streamingJson['postPaddingTime']
        self.drmContentId = streamingJson['drmContentId']
        self.isAvad = streamingJson['isAvad']
        self.actualProgramStartOffset = streamingJson['actualProgramStartOffset']
        self.url = streamingJson['url']
        self.fallbackUrl = streamingJson['fallbackUrl']
        self.token = None
