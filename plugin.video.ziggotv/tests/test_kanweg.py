import unittest
from enum import Enum, IntEnum


class GlobalVariables:
    ZIGGO_URL = 'https://www.ziggogo.tv/'
    ZIGGOPROD_URL = 'https://prod.spark.ziggogo.tv/'
    STATIC_URL = 'https://staticqbr-nl-prod.prod.cdn.dmdsdp.com/'
    STATICPROD_URL = 'https://static.spark.ziggogo.tv/'
    authentication_URL = ZIGGOPROD_URL + 'auth-service/v1/authorization'
    personalisation_URL = ZIGGOPROD_URL + 'eng/web/personalization-service/v1/customer/{householdid}'
    entitlements_URL = ZIGGOPROD_URL + 'eng/web/purchase-service/v2/customers/{householdid}/entitlements'
    widevine_URL = ZIGGOPROD_URL + 'eng/web/session-manager/license/certificate/widevine'
    license_URL = ZIGGOPROD_URL + 'eng/web/session-manager/license'
    channels_URL = ZIGGOPROD_URL + 'eng/web/linear-service/v2/channels'
    streaming_URL = ZIGGOPROD_URL + 'eng/web/session-service/session/v2/web-desktop/customers/{householdid}'
    homeservice_URL = ZIGGOPROD_URL + 'eng/web/personal-home-service/'
    vod_service_URL = ZIGGOPROD_URL + 'eng/web/vod-service/v3/'
    linearservice_v2_URL = ZIGGOPROD_URL + 'eng/web/linear-service/v2/'
    linearservice_v1_URL = ZIGGOPROD_URL + 'eng/web/linear-service/v1/'
    pickerservice_URL = ZIGGOPROD_URL + 'eng/web/picker-service/v1/'
    gridservice_URL = ZIGGOPROD_URL + 'eng/web/vod-service/v3/grid-screen/'
    events_URL = STATICPROD_URL + 'eng/web/epg-service-lite/nl/nl/events/segments/'
    replayEvent_URL = ZIGGOPROD_URL + 'eng/web/linear-service/v2/replayEvent/'
    recordings_URL = ZIGGOPROD_URL + 'eng/web/recording-service/customers/{householdid}/'
    discovery_URL = ZIGGOPROD_URL + 'eng/web/discovery-service/v2/learn-actions/'

    SESSION_INFO = 'session.json'
    CUSTOMER_INFO = 'customer.json'
    CHANNEL_INFO = 'channels.json'
    ENTITLEMENTS_INFO = 'entitlements.json'
    WIDEVINE_LICENSE = 'widevine.json'
    COOKIES_INFO = 'cookies.json'
    MOVIE_INFO = 'movies.json'
    SERIES_INFO = 'series.json'
    GUIDE_INFO = 'epg.json'
    RECORDINGS_INFO = 'recordings.json'

    SERIES = 'Series'
    MOVIES = 'Movies'
    GENRES = 'Genre'

    PROTOCOL = 'mpd'
    DRM = 'com.widevine.alpha'


class ALIGNMENT(IntEnum):
    XBFONT_LEFT = 0x00000000
    XBFONT_RIGHT = 0x00000001
    XBFONT_CENTER_X = 0x00000002
    XBFONT_CENTER_Y = 0x00000004
    XBFONT_TRUNCATED = 0x00000008
    XBFONT_JUSTIFIED = 0x00000010


def __init__(self):
    pass


class TestEnum(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_enum(self):
        from resources.lib.globals import G
        # g = GlobalVariables(GlobalVariables.COOKIES_INFO)
        rslt = '\\bladie\\bla\\' + G.COOKIES_INFO
        print(G.MOVIE_INFO)


if __name__ == '__main__':
    unittest.main()
