"""
Global definitions.
Constants are grouped in classes. The classes are imported (with some exceptions)
"""
import dataclasses
from enum import IntEnum


@dataclasses.dataclass
class StringIds:
    """
    Id of strings in the language files. Changing them here also requires a change in the strings.po files
    of the different languages.
    """
    MSG_SWITCH_OR_PLAY = 40004
    MSG_SWITCH = 40005
    MSG_CANNOTWATCH = 40009
    MSG_REPLAY_NOT_AVAIALABLE = 40012
    MSG_NOT_ENTITLED = 40013
    MSG_VIDEO_NOT_STARTED = 40014
    BTN_PLAY = 40006
    BTN_SWITCH = 40007
    BTN_CANCEL = 40008
    MENU_CHANNELS = 40010
    MENU_GUIDE = 40011
    MENU_RECORDINGS = 40015
    MSG_EPISODES = 40016
    MENU_PLANNED_RECORDINGS = 40017
    MSG_STILL_PLANNED = 40018
    MSG_DELETE = 40019
    MSG_RESUME_FROM = 40020
    MSG_PLAY_FROM_BEGINNING = 40021
    MSG_RECORD_EVENT = 40022
    MSG_RECORD_SHOW = 40023
    MSG_REPLAY_EVENT = 40024
    MSG_SWITCH_CHANNEL = 40025
    MSG_DELETE_SEASON = 40026
    MSG_EVENT_SCHEDULED = 40027
    MSG_SHOW_SCHEDULED = 40028

    def __init__(self):
        pass


@dataclasses.dataclass
class GlobalVariables:
    """
    General global variables. Mainly the URLs used, filenames, and texts
    """
    ZIGGO_URL = 'https://www.ziggogo.tv/'
    ZIGGO_HOST = 'spark-prod-nl.gnp.cloud.ziggogo.tv'
    STATIC_URL = 'https://staticqbr-nl-prod.prod.cdn.dmdsdp.com/'
    STATICPROD_URL = 'https://static.spark.ziggogo.tv/'
    ZIGGOPROD_URL = 'https://' + ZIGGO_HOST + '/'
    LANG = 'eng'
    AUTHENTICATION_URL = ZIGGOPROD_URL + 'auth-service/v1/authorization'
    PERSONALISATION_URL = ZIGGOPROD_URL + LANG + '/web/personalization-service/v1/customer/{householdid}'
    ENTITLEMENTS_URL = ZIGGOPROD_URL + LANG + '/web/purchase-service/v2/customers/{householdid}/entitlements'
    WIDEVINE_URL = ZIGGOPROD_URL + LANG + '/web/session-manager/license/certificate/widevine'
    LICENSE_URL = ZIGGOPROD_URL + LANG + '/web/session-manager/license'
    CHANNELS_URL = ZIGGOPROD_URL + LANG + '/web/linear-service/v2/channels'
    STREAMING_URL = ZIGGOPROD_URL + LANG + '/web/session-service/session/v2/web-desktop/customers/{householdid}'
    HOMESERVICE_URL = ZIGGOPROD_URL + LANG + '/web/personal-home-service/'
    VOD_SERVICE_URL = ZIGGOPROD_URL + LANG + '/web/vod-service/v3/'
    LINEARSERVICE_V2_URL = ZIGGOPROD_URL + LANG + '/web/linear-service/v2/'
    LINEARSERVICE_V1_URL = ZIGGOPROD_URL + LANG + '/web/linear-service/v1/'
    PICKERSERVICE_URL = ZIGGOPROD_URL + LANG + '/web/picker-service/v1/'
    GRIDSERVICE_URL = ZIGGOPROD_URL + LANG + '/web/vod-service/v3/grid-screen/'
    EVENTS_URL = STATICPROD_URL + LANG + '/web/epg-service-lite/nl/nl/events/segments/'
    REPLAYEVENT_URL = ZIGGOPROD_URL + LANG + '/web/linear-service/v2/replayEvent/'
    RECORDINGS_URL = ZIGGOPROD_URL + LANG + '/web/recording-service/customers/{householdid}/'
    DISCOVERY_URL = ZIGGOPROD_URL + 'web/discovery-service/v2/learn-actions/'

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
    PLAYBACK_INFO = 'playbackstates.json'

    SERIES = 'Series'
    MOVIES = 'Movies'
    GENRES = 'Genre'

    PROTOCOL = 'mpd'
    DRM = 'com.widevine.alpha'

    def __init__(self):
        pass


class Alignment(IntEnum):
    """
    xbmc alignment constants (not available in current version of xbmcgui
    """
    XBFONT_LEFT = 0x00000000
    XBFONT_RIGHT = 0x00000001
    XBFONT_CENTER_X = 0x00000002
    XBFONT_CENTER_Y = 0x00000004
    XBFONT_TRUNCATED = 0x00000008
    XBFONT_JUSTIFIED = 0x00000010


CONST_BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9,nl;q=0.8',
    'Cache-Control': 'no-cache',
#    'DNT': '1',
    'TE': 'trailers',
    'Origin': 'https://www.ziggogo.tv',
#    'Pragma': 'no-cache',
    'Referer': 'https://www.ziggogo.tv/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'X-Device-Code': 'web'
}
ALLOWED_LICENSE_HEADERS = [
    "Accept",
    "Accept-Encoding",
    "Accept-Language",
#    "Cache-Control",
    "Connection",
    "Content-Length",
    "Cookie",
    "deviceName",
#    "DNT",
    "Host",
    "Origin",
#    "Pragma",
    "Referer",
    "Sec-Fetch-Dest",
    "Sec-Fetch-Mode",
    "Sec-Fetch-Site",
    "TE",
    "User-Agent",
#    "X-cus",
    "x-drm-schemeId",
    "x-go-dev",
#    "X-OESP-Username",
    "X-Profile",
    "x-streaming-token",
    "x-tracking-id"
]

G = GlobalVariables()
S = StringIds()
A = Alignment(Alignment.XBFONT_CENTER_X)
