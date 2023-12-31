class StreamingInfo:
    '"deviceRegistrationRequired": false, "drmContentId": "nl_tv_standaard_cenc", "isAdult": false'

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
