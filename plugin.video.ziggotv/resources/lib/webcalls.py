import base64
import datetime
import json
import inspect
from typing import List

from datetime import timezone
from pathlib import Path
import requests

import xbmc
import xbmcaddon
import xbmcvfs
from requests import Response

from resources.lib.channel import Channel
from resources.lib.globals import G, CONST_BASE_HEADERS, ALLOWED_LICENSE_HEADERS
from resources.lib.recording import RecordingList
from resources.lib.streaminginfo import StreamingInfo, ReplayStreamingInfo, VodStreamingInfo, RecordingStreamingInfo
from resources.lib.utils import DatetimeHelper

try:
    import pyjwt
except Exception:
    import jwt as pyjwt


def b2ah(barr):
    return barr.hex()


class WebException(Exception):
    def __init__(self, response: Response):
        funcName = inspect.stack()[1].function
        message = 'Unexpected response status in {0}: {1}'.format(funcName, response.status_code)
        super().__init__(message)
        self.response = response

    def get_response(self):
        return self.response.content

    def get_status(self):
        return self.response.status_code


class Web(requests.Session):

    def __init__(self, addon: xbmcaddon.Addon):
        super().__init__()
        self.printNetworkTraffic = addon.getSettingBool('print-network-traffic')
        self.addonPath = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        self.load_cookies()

    def pluginpath(self, name):
        return self.addonPath + name

    def dump_cookies(self):
        from http.cookiejar import Cookie
        for _cookie in self.cookies:
            c: Cookie = _cookie
            xbmc.log('Cookie: {0}, domain: {1}, value: {2}, path: {3}'.format(c.name, c.domain, c.value, c.path))

    def save_cookies(self, response):
        newCookies = requests.utils.dict_from_cookiejar(response.cookies)
        if Path(self.pluginpath(G.COOKIES_INFO)).exists():
            savedCookies = json.loads(Path(self.pluginpath(G.COOKIES_INFO)).read_text())  # save them to file as JSON
        else:
            savedCookies = {}

        savedCookies = self.merge(newCookies, savedCookies)
        # new_cookies = requests.utils.dict_from_cookiejar(self.session.cookies)  # turn cookiejar into dict
        Path(self.pluginpath(G.COOKIES_INFO)).write_text(json.dumps(savedCookies))  # save them to file as JSON

    def load_cookies(self):
        if Path(self.pluginpath(G.COOKIES_INFO)).exists():
            cookies = json.loads(Path(self.pluginpath(G.COOKIES_INFO)).read_text())  # save them to file as JSON
        else:
            cookies = {}
        cookies = requests.utils.cookiejar_from_dict(cookies)  # turn dict to cookiejar
        self.cookies.update(cookies)
        return cookies

    @staticmethod
    def merge(dict1, dict2):
        dict2.update(dict1)
        return dict2

    def print_dialog(self, response):
        if not self.printNetworkTraffic:
            return

        print("URL: {0} {1}".format(response.request.method, response.url))
        print("Status-code: {0}".format(response.status_code))
        print("Request headers: {0}".format(response.request.headers))
        print("Response headers: {0}".format(response.headers))
        print("Cookies: ", self.cookies.get_dict())

        if response.request.body is None or response.request.body == '':
            print("Request data is empty")
        else:
            if 'Content-Type' in response.request.headers:
                if response.request.headers["Content-Type"][0:16] == "application/json":
                    print("Request JSON-format: {0}".format(response.request.body))
                else:
                    print("Request content: {0}".format(response.request.body))
                    print("HEX: {0}".format(b2ah(response.request.body)))
                    print("B64: {0}".format(base64.b64encode(response.request.body)))
            else:
                if isinstance(response.request.body, str):
                    s = bytearray(response.request.body, 'ascii')
                    print("HEX: {0}".format(b2ah(s)))
                    print("B64: {0}".format(base64.b64encode(s)))
                else:
                    print("HEX: {0}".format(b2ah(response.request.body)))
                    print("B64: {0}".format(base64.b64encode(response.request.body)))

        if response.content is None or response.content == '':
            print("Response data is empty")
        else:
            if "Content-Type" in response.headers:
                if response.headers["Content-Type"][0:16] == "application/json":
                    print("Response JSON-format: {0}".format(json.dumps(response.json())))
                else:
                    print("Response content: {0}".format(response.content))
                    print("HEX: {0}".format(b2ah(response.content)))
                    print("B64: {0}".format(base64.b64encode(response.content)))
            else:
                print("HEX: {0}".format(b2ah(response.content)))
                print("B64: {0}".format(base64.b64encode(response.content)))

    def do_post(self, url: str, data=None, jsonData=None, extraHeaders=None, params=None):
        # pylint: disable=too-many-arguments
        """
         :param params: query parameters
         :param jsonData: (optional) json data to send
         :param url: web address to connect to
         :param data: (optional) data to send with request
         :param extraHeaders: (optional) extra headers to add to default headers send
         :return: response
         """
        if extraHeaders is None:
            extraHeaders = {}
        headers = dict(CONST_BASE_HEADERS)
        if jsonData is not None:
            headers.update({"Content-Type": "application/json; charset=utf-8"})
        for key in extraHeaders:
            headers.update({key: extraHeaders[key]})
        response = super().post(url, data=data, json=jsonData, headers=headers, params=params)
        self.print_dialog(response)
        self.save_cookies(response)
        return response

    def do_get(self, url: str, data=None, jsonData=None, extraHeaders=None, params=None):
        # pylint: disable=too-many-arguments
        """
         :param jsonData: (optional) json data to send
         :param url: web address to connect to
         :param data: (optional) data to send with request
         :param extraHeaders: (optional) extra headers to add to default headers send
         :param params: (optional) params used in query request (get)
         :return: response
         """
        if extraHeaders is None:
            extraHeaders = {}
        headers = dict(CONST_BASE_HEADERS)
        if jsonData is not None:
            headers.update({"Content-Type": "application/json; charset=utf-8"})
        for key in extraHeaders:
            headers.update({key: extraHeaders[key]})
        response = super().get(url, data=data, json=jsonData, headers=headers, params=params)
        self.print_dialog(response)
        # self.dump_cookies()
        self.save_cookies(response)
        return response

    def do_head(self, url: str, data=None, jsonData=None, extraHeaders=None, params=None):
        # pylint: disable=too-many-arguments
        """
         :param jsonData: (optional) json data to send
         :param url: web address to connect to
         :param data: (optional) data to send with request
         :param extraHeaders: (optional) extra headers to add to default headers send
         :param params: (optional) params used in query request (get)
         :return: response
         """
        if extraHeaders is None:
            extraHeaders = {}
        headers = dict(CONST_BASE_HEADERS)
        if jsonData is not None:
            headers.update({"Content-Type": "application/json; charset=utf-8"})
        for key in extraHeaders:
            headers.update({key: extraHeaders[key]})
        response = super().head(url, data=data, json=jsonData, headers=headers, params=params)
        self.print_dialog(response)
        # self.dump_cookies()
        self.save_cookies(response)
        return response

    def do_delete(self, url: str, data=None, jsonData=None, extraHeaders=None, params=None):
        # pylint: disable=too-many-arguments
        """
         :param jsonData: (optional) json data to send
         :param url: web address to connect to
         :param data: (optional) data to send with request
         :param extraHeaders: (optional) extra headers to add to default headers send
         :param params: (optional) params used in query request (get)
         :return: response
         """
        if extraHeaders is None:
            extraHeaders = {}
        headers = dict(CONST_BASE_HEADERS)
        if jsonData is not None:
            headers.update({"Content-Type": "application/json; charset=utf-8"})
        for key in extraHeaders:
            headers.update({key: extraHeaders[key]})
        response = super().delete(url, data=data, json=jsonData, headers=headers, params=params)
        self.print_dialog(response)
        # self.dump_cookies()
        self.save_cookies(response)
        return response


class LoginSession(Web):

    def __init__(self, addon):
        super().__init__(addon)
        self.sessionInfo = {}
        self.channels: List[Channel] = []
        self.customerInfo = {}
        self.recStreamInfo: RecordingStreamingInfo = None
        self.vodStreamInfo: VodStreamingInfo = None
        self.replayStreamInfo: ReplayStreamingInfo = None
        self.activeProfile = None
        self.streamingToken = None
        self.entitlementsInfo = None
        self.extraHeaders = {}
        self.streamInfo: StreamingInfo = None
        self.username = None
        self.get_channels()
        self.get_session_info()
        self.get_customer_info()
        self.get_entitlements()

    def __status_code_ok(self, response):
        """
        If status_code == 401 the session_info is reset

        :param response: the received response
        :return: True if status is OK
                 False if other status

        """
        if response.status_code in [200, 204]:
            return True
        if response.status_code == 401:  # not authenticated
            self.sessionInfo = {}
            Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(self.sessionInfo))
        return False

    def get_session_info(self):
        if Path(self.pluginpath(G.SESSION_INFO)).exists():
            self.sessionInfo = json.loads(Path(self.pluginpath(G.SESSION_INFO)).read_text())
        else:
            self.sessionInfo = {}
        return self.sessionInfo

    def get_customer_info(self):
        if Path(self.pluginpath(G.CUSTOMER_INFO)).exists():
            self.customerInfo = json.loads(Path(self.pluginpath(G.CUSTOMER_INFO)).read_text())
            self.set_active_profile(self.get_profiles()[0])
        else:
            self.customerInfo = {}
        return self.customerInfo

    def get_channels(self):
        if Path(self.pluginpath(G.CHANNEL_INFO)).exists():
            channelInfo = json.loads(Path(self.pluginpath(G.CHANNEL_INFO)).read_text())
            self.channels.clear()
            for info in channelInfo:
                channel = Channel(info)
                if channel.isHidden:
                    continue
                self.channels.append(channel)
        else:
            self.channels = []
        return self.channels

    def get_entitlements(self):
        if Path(self.pluginpath(G.ENTITLEMENTS_INFO)).exists():
            self.entitlementsInfo = json.loads(Path(self.pluginpath(G.ENTITLEMENTS_INFO)).read_text())
        else:
            self.entitlementsInfo = {}
        return self.entitlementsInfo

    def obtain_customer_info(self):
        try:
            self.cookies.pop("CLAIMSTOKEN")
        except Exception:
            pass
        url = G.PERSONALISATION_URL.format(householdid=self.sessionInfo['householdId'])
        response = super().do_get(url, params={'with': 'profiles,devices'})
        if not self.__status_code_ok(response):
            raise WebException(response)
        Path(self.pluginpath(G.CUSTOMER_INFO)).write_text(json.dumps(response.json()))

    def __login_valid(self):
        _valid = False
        if len(self.sessionInfo) == 0:  # Session_info empty, so not successfully logged in
            return False

        # We moeten het JWT token decoderen en daar de geldigheidsdatum uithalen.
        # Als het token niet meer geldig is moet het ACCESSTOKEN-cookie worden verwijderd!

        if DatetimeHelper.from_unix(self.sessionInfo['refreshTokenExpiry']) > datetime.datetime.now():
            xbmc.log("issued at: {0}".format(DatetimeHelper.from_unix(self.sessionInfo['issuedAt'])),
                     xbmc.LOGDEBUG)
            xbmc.log("refresh at: {0}".format(DatetimeHelper.from_unix(self.sessionInfo['refreshTokenExpiry'])),
                     xbmc.LOGDEBUG)
            xbmc.log("logon still valid",
                     xbmc.LOGDEBUG)
            return True

        return False

    def login(self, username: str, password: str):
        self.username = username
        if not self.__login_valid():
            self.extraHeaders = {}
            self.cookies.clear_session_cookies()
            Path(self.pluginpath(G.COOKIES_INFO)).unlink(missing_ok=True)
            response = super().do_post(G.AUTHENTICATION_URL,
                                       jsonData={"password": password,
                                                  "username": username})
            if not self.__status_code_ok(response):
                raise WebException(response)
            Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(response.json()))
            self.sessionInfo = self.get_session_info()
        else:
            # Zie comment bij login_valid()
            try:
                jwtDecoded = pyjwt.decode(self.sessionInfo["accessToken"], options={"verify_signature": False})
                exp = DatetimeHelper.from_unix(jwtDecoded["exp"])
                now = DatetimeHelper.now()
            except pyjwt.exceptions.ExpiredSignatureError:
                exp = DatetimeHelper.now()
                now = exp
            if exp > now:
                xbmc.log("Accesstoken still valid", xbmc.LOGDEBUG)
            else:
                # from urllib.parse import urlparse
                # domain = urlparse(G.authentication_URL).netloc
                try:
                    self.cookies.clear(domain='', path='/', name='ACCESSTOKEN')
                except Exception as exc:
                    xbmc.log("ACCESSTOKEN cannot be removed: {0}".format(exc), xbmc.LOGERROR)
                    xbmc.log("COOKIES: {0}".format(self.cookies.keys()), xbmc.LOGERROR)
                #  self.cookies.pop("ACCESSTOKEN") # Causes duplicate error in some cases
                response = super().do_post(G.AUTHENTICATION_URL + "/refresh",
                                           jsonData={"refreshToken": self.sessionInfo['refreshToken'],
                                                      "username": username})
                if not self.__status_code_ok(response):
                    raise WebException(response)
                Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(response.json()))

            self.sessionInfo = self.get_session_info()

        self.obtain_customer_info()
        self.customerInfo = self.get_customer_info()
        if self.activeProfile is None:
            self.activeProfile = self.customerInfo["profiles"][0]
        profileId = self.activeProfile["profileId"]
        trackingId = self.customerInfo["hashedCustomerId"]
        self.extraHeaders = {
            'X-OESP-Username': self.username,
            'x-tracking-id': trackingId,
            'X-Profile': profileId
        }
        return self.sessionInfo

    def refresh_channels(self):
        response = super().do_get(G.CHANNELS_URL,
                                  params={'cityId': self.customerInfo["cityId"],
                                          'language': 'nl',
                                          'productClass': 'Orion-DASH'},
                                  extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        Path(self.pluginpath(G.CHANNEL_INFO)).write_text(json.dumps(response.json()))

    def refresh_entitlements(self):
        url = G.ENTITLEMENTS_URL.format(householdid=self.sessionInfo['householdId'])
        response = super().do_get(url,
                                  params={'enableDayPass': 'true'},
                                  extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        Path(self.pluginpath(G.ENTITLEMENTS_INFO)).write_text(json.dumps(response.json()))

    def refresh_widevine_license(self):
        response = super().do_get(G.WIDEVINE_URL,
                                  extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        encodedContent = base64.b64encode(response.content)
        Path(self.pluginpath(G.WIDEVINE_LICENSE)).write_text(encodedContent.decode("ascii"))

    def obtain_tv_streaming_token(self, channelId, assetType):
        url = G.STREAMING_URL.format(householdid=self.sessionInfo['householdId']) + '/live'
        response = super().do_post(url,
                                   params={
                                       'channelId': channelId,
                                       'assetType': assetType,
                                       'profileId': self.activeProfile['profileId'],
                                       'liveContentTimestamp': DatetimeHelper.now(timezone.utc).isoformat()
                                   },
                                   extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        self.streamInfo = StreamingInfo(json.loads(response.content))
        self.streamInfo.token = response.headers["x-streaming-token"]
        return self.streamInfo

    def obtain_replay_streaming_token(self, path):
        url = G.STREAMING_URL.format(householdid=self.sessionInfo['householdId']) + '/replay'
        response = super().do_post(url,
                                   params={
                                       'eventId': path,
                                       'abrType': 'BR-AVC-DASH',
                                       'profileId': self.activeProfile['profileId']
                                   },
                                   extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        self.replayStreamInfo = ReplayStreamingInfo(json.loads(response.content))
        self.replayStreamInfo.token = response.headers["x-streaming-token"]
        return self.replayStreamInfo

    def obtain_vod_streaming_token(self, streamId):
        url = G.STREAMING_URL.format(householdid=self.sessionInfo['householdId']) + '/vod'
        response = super().do_post(url,
                                   params={
                                       'contentId': streamId,
                                       'abrType': 'BR-AVC-DASH',
                                       'profileId': self.activeProfile['profileId']
                                   },
                                   extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        self.vodStreamInfo = VodStreamingInfo(json.loads(response.content))
        self.vodStreamInfo.token = response.headers["x-streaming-token"]
        return self.vodStreamInfo

    def obtain_recording_streaming_token(self, streamid):
        url = G.STREAMING_URL.format(householdid=self.sessionInfo['householdId']) + '/recording'
        response = super().do_post(url,
                                   params={
                                       'recordingId': streamid,
                                       'abrType': 'BR-AVC-DASH',
                                       'profileId': self.activeProfile['profileId']
                                   },
                                   extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        self.recStreamInfo = RecordingStreamingInfo(json.loads(response.content))
        self.recStreamInfo.token = response.headers["x-streaming-token"]
        return self.recStreamInfo

    def get_license(self, content_id, request_data, license_headers):
        url = G.LICENSE_URL
        license_headers.update({'x-streaming-token': self.streamingToken})
        for key in license_headers:
            if key in ALLOWED_LICENSE_HEADERS:
                pass
            else:
                xbmc.log("HEADER DROPPPED: {0}:{1}".format(key, license_headers[key]), xbmc.LOGDEBUG)
                license_headers[key] = None
        response = super().do_post(url,
                                   params={'ContentId': content_id},
                                   data=request_data,
                                   extraHeaders=license_headers)
        if 'x-streaming-token' in response.headers:
            self.streamingToken = response.headers['x-streaming-token']
        return response

    def update_token(self, streaming_token):
        url = G.LICENSE_URL + '/token'
        profileId = self.activeProfile["profileId"]
        trackingId = self.get_customer_info()["hashedCustomerId"]
        self.extraHeaders = {
            'X-OESP-Username': self.username,
            'x-tracking-id': trackingId,
            'X-Profile': profileId,
            'x-streaming-token': streaming_token
        }
        response = super().do_post(url,
                                   data=None,
                                   params=None,
                                   extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        if 'x-streaming-token' in response.headers:
            self.streamingToken = response.headers['x-streaming-token']
            return response.headers["x-streaming-token"]
        return ''

    def delete_token(self, streaming_id):
        url = G.LICENSE_URL + '/token'
        profileId = self.activeProfile["profileId"]
        trackingId = self.get_customer_info()["hashedCustomerId"]
        self.extraHeaders = {
            'X-OESP-Username': self.username,
            'x-tracking-token': trackingId,
            'X-Profile': profileId,
            'x-streaming-token': streaming_id
        }
        response = super().do_delete(url,
                                     data=None,
                                     params=None,
                                     extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)

    def get_manifest(self, url):
        response = super().do_get(url, data=None, params=None)
        return response

    def get_profiles(self):
        return self.customerInfo["profiles"]

    def set_active_profile(self, profile):
        self.activeProfile = profile

    def __get_optin_date(self, optinType, unixtime=False):
        optins = self.customerInfo['customerOptIns']
        i = 0
        while i < len(optins):
            if optins[i]['optInType'] == optinType:
                replayOptinDate = optins[i]['lastModified']
                if unixtime:
                    return DatetimeHelper.to_unix(replayOptinDate, '%Y-%m-%dT%H:%M:%S.%fZ')
                return replayOptinDate
            i += 1
        if unixtime:
            return 0
        return ''

    def obtain_structure(self):
        url = G.HOMESERVICE_URL + 'structure/'
        params = {
            'profileId': self.activeProfile["profileId"],
            'language': 'nl',
            'optIn': 'true',
            'clientType': 'HZNGO-WEB',
            # , 'version': '5.05'
            'featureFlags': 'client_Mobile'
        }
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return response.content

    def obtain_home_collection(self, collection: []):
        profileId = self.activeProfile["profileId"]
        householdId = self.customerInfo['customerId']
        cityId = self.customerInfo["cityId"]
        replayOptinDate = self.__get_optin_date('replay', unixtime=False)
        url = (G.HOMESERVICE_URL
               + 'customers/{household_id}/profiles/{profile_id}/screen'.format(household_id=householdId,
                                                                                profile_id=profileId))
        params = {
            'id': ','.join(collection),
            'language': 'nl',
            'clientType': 'HZNGO-WEB',
            'maxRes': '4K',
            'cityId': cityId,
            'replayOptInDate': replayOptinDate,
            'goPlayable': 'false',
            'sharedProfile': self.activeProfile['shared'],
            'optIn': 'true',
            # , 'version': '5.05'
            'featureFlags': 'client_Mobile',
            'productClass': 'Orion-DASH',
            'useSeriesLogic': 'true'
        }
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)

        return response.content

    def obtain_grid_screen_details(self, collection_id):
        url = G.GRIDSERVICE_URL + collection_id
        cityId = self.customerInfo["cityId"]
        profileId = self.activeProfile["profileId"]
        params = {
            'language': 'nl',
            'profileId': profileId,
            'type': 'Editorial',
            'sortType': 'popularity',
            'sortDirection': 'descending',
            'pagingOffset': '0',
            'maxRes': '4K',
            'cityId': cityId,
            'onlyGoPlayable': 'false',
            'goDownloadable': 'false',
            'excludeAdult': 'false',
            'entityVersion': '1'
        }

        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def obtain_vod_screen_details(self, collection_id):
        url = G.VOD_SERVICE_URL + 'collections-screen/{id}'.format(id=collection_id)
        cityId = self.customerInfo["cityId"]
        profileId = self.activeProfile["profileId"]
        params = {
            'language': 'nl',
            'profileId': profileId,
            'optIn': 'true',
            'sharedProfile': self.activeProfile['shared'],
            'maxRes': '4K',
            'cityId': cityId,
            'excludeAdult': 'false',
            'onlyGoPlayable': 'false',
            'fallbackRootId': 'omw_hzn4_vod',
            'featureFlags': 'client_Mobile',
            'entityVersion': '1'
        }
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def obtain_asset_details(self, id, brandingProviderId=None):
        url = G.VOD_SERVICE_URL + 'details-screen/{id}'.format(id=id)
        cityId = self.customerInfo["cityId"]
        profileId = self.activeProfile["profileId"]
        params = {
            'language': 'nl',
            'profileId': profileId,
            'maxRes': '4K',
            'cityId': cityId,
            'brandingProviderId': brandingProviderId
        }
        if brandingProviderId is None:
            pass
        else:
            params.update({'brandingProviderId': brandingProviderId})
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def obtain_series_overview(self, id):
        url = G.PICKERSERVICE_URL + 'showPage/' + id + '/nl'
        cityId = self.customerInfo["cityId"]
        params = {
            'cityId': cityId,
            'country': 'nl',
            'mergingOn': 'true'
        }
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def obtain_vod_screens(self):
        url = G.VOD_SERVICE_URL + 'structure/omw_play'
        params = {
            'language': 'nl',
            'menu': 'vod',
            'optIn': 'true',
            'fallbackRootId': 'omw_hzn4_vod',
            'featureFlags': 'client_Mobile',
            'maxRes': '4K',
            'excludeAdult': 'false',
            'entityVersion': '1'
        }
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)

        return json.loads(response.content)

    def get_episode_list(self, item):
        profileId = self.activeProfile["profileId"]
        cityId = self.customerInfo["cityId"]
        url = G.ZIGGOPROD_URL + 'eng/web/picker-service/v2/episodePicker'
        params = {'seriesCrid': item,
                  'language': 'nl',
                  'country': 'nl',
                  'cityId': cityId,
                  'replayOptedInTime': self.__get_optin_date('replay', unixtime=True),
                  'profileId': profileId,
                  'maxRes': '4K',
                  'mergingOn': 'true',
                  'goPlayableOnly': 'false'}
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def get_episode(self, item):
        profileId = self.activeProfile["profileId"]
        cityId = self.customerInfo["cityId"]
        if item['type'] == 'REPLAY':
            mostrelevantEpisode = ''
            asset = ''
            if item['subType'] == 'SERIES':
                # first het episode info
                url = G.ZIGGOPROD_URL + 'eng/web/picker-service/v2/mostRelevantEpisode'
                params = {'seriesId': item['id'],
                          'language': 'nl',
                          'country': 'nl',
                          'cityId': cityId,
                          'replayOptedInTime': self.__get_optin_date('replay', unixtime=True),
                          'profileId': profileId,
                          'maxRes': '4K',
                          'mergingOn': 'true',
                          'goPlayableOnly': 'false'}

                response = super().do_get(url=url,
                                          params=params)
                if not self.__status_code_ok(response):
                    raise WebException(response)
                mostrelevantEpisode = response.content
            if item['subType'] in ['ASSET']:
                url = G.LINEARSERVICE_V2_URL + 'replayEvent/{item}'.format(item=item['id'])
                params = {'language': 'nl',
                          'returnLinearContent': 'true',
                          'forceLinearResponse': 'false'}
                response = super().do_get(url=url,
                                          params=params)
                if not self.__status_code_ok(response):
                    raise WebException(response)
                asset = response.content

            return mostrelevantEpisode, asset
        return '', ''

    def get_mostwatched_channels(self):
        url = G.LINEARSERVICE_V1_URL + 'mostWatchedChannels'
        cityId = self.customerInfo["cityId"]
        params = {
            'cityId': cityId,
            'productClass': 'Orion-DASH'}
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return response.content

    def get_events(self, starttime: str):
        """

        :param starttime: datetime in format yyyymmddhhss
        :return: list of events per channel
        """
        url = G.EVENTS_URL + starttime
        response = super().do_get(url=url)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def __get_recordings_planned(self, isAdult: bool):
        """
        Obtain list of planned recordings
        @param isAdult:
        @return:
        """
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'bookings'
        response = super().do_get(url, params={'with': 'profiles,devices',
                                               'isAdult': isAdult,
                                               'offset': 0,
                                               'limit': 100,
                                               # 'sort': 'time',
                                               # 'sortOrder': 'desc',
                                               'profileId': self.activeProfile['profileId'],
                                               'language': 'nl'})
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def __get_recordings(self, isAdult: bool):
        """
        Obtain list of planned recordings
        @param isAdult:
        @return:
        """
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'recordings'
        response = super().do_get(url, params={'with': 'profiles,devices',
                                               'isAdult': isAdult,
                                               'offset': 0,
                                               'limit': 100,
                                               # 'sort': 'time',
                                               # 'sortOrder': 'desc',
                                               'profileId': self.activeProfile['profileId'],
                                               'language': 'nl'})
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def __get_recordings_season(self, channelId, showId):
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'episodes/shows/' + showId
        response = super().do_get(url, params={'source': 'recording',
                                               'isAdult': 'false',
                                               'offset': 0,
                                               'limit': 100,
                                               # 'sort': 'time',
                                               # 'sortOrder': 'desc',
                                               'profileId': self.activeProfile['profileId'],
                                               'language': 'nl',
                                               'channelId': channelId
                                               })
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def get_recording_details(self, id):
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'details/single/' + id
        response = super().do_get(url, params={'profileId': self.activeProfile['profileId'],
                                               'language': 'nl'
                                               })
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def delete_recordings_planned(self, events: [], shows: [], channelId=None):
        eventList = []
        showList = []
        for event in events:
            eventList.append({'eventId': event})
        for show in shows:
            if channelId is not None:
                showList.append({'showId': show, 'channelId': channelId})
            else:
                showList.append({'showId': show})
        request = {'events': eventList, 'shows': showList}
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'bookings'
        response = super().do_delete(url=url, jsonData=request)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def delete_recordings(self, events: [], shows: [], channelId=None):
        eventList = []
        showList = []
        for event in events:
            eventList.append({'eventId': event})
        for show in shows:
            if channelId is not None:
                showList.append({'showId': show, 'channelId': channelId})
            else:
                showList.append({'showId': show})
        request = {'events': eventList, 'shows': showList}
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'recordings'
        response = super().do_delete(url=url, jsonData=request)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def record_event(self, eventId):
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'bookings/single'
        request = {'eventId': eventId,
                   'retentionLimit': 365}
        response = super().do_post(url=url, jsonData=request)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def record_show(self, eventId, channelId):
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'bookings/show'
        request = {'eventId': eventId,
                   'channelId': channelId,
                   'retentionLimit': 365}
        response = super().do_post(url=url, jsonData=request)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def refresh_recordings(self, includeAdult=False):
        """
        Routine to (re)load the recordings.
        They will be stored in recordings.json
        @param includeAdult:
        @return: nothing
        """
        recJson = {'planned': [], 'recorded': []}
        recordingsPlanned = self.__get_recordings_planned(isAdult=False)
        for recording in recordingsPlanned['data']:
            if recording['type'] == 'season':
                seasonRecordings = self.__get_recordings_season(recording['channelId'], recording['showId'])
                recording.update({'episodes': seasonRecordings})
        if includeAdult:
            adultRecordingsPlanned = self.__get_recordings_planned(isAdult=True)
            for recording in adultRecordingsPlanned['data']:
                if recording['type'] == 'season':
                    seasonRecordings = self.__get_recordings_season(recording['channelId'], recording['showId'])
                    recording.update({'episodes': seasonRecordings})
        recJson.update({'planned': recordingsPlanned})
        recordings = self.__get_recordings(isAdult=False)
        for recording in recordings['data']:
            if recording['type'] == 'season':
                seasonRecordings = self.__get_recordings_season(recording['channelId'], recording['showId'])
                recording.update({'episodes': seasonRecordings})
        if includeAdult:
            adultRecordings = self.__get_recordings(isAdult=True)
            for recording in adultRecordings['data']:
                if recording['type'] == 'season':
                    seasonRecordings = self.__get_recordings_season(recording['channelId'], recording['showId'])
                    recording.update({'episodes': seasonRecordings})
        recJson.update({'recorded': recordings})
        Path(self.pluginpath(G.RECORDINGS_INFO)).write_text(json.dumps(recJson))

    def get_recordings_planned(self) -> RecordingList:
        """
        @return: list of planned recordings
        """
        if Path(self.pluginpath(G.RECORDINGS_INFO)).exists():
            recordingsInfo = json.loads(Path(self.pluginpath(G.RECORDINGS_INFO)).read_text())
            return RecordingList(recordingsInfo['planned'])
        return RecordingList()

    def get_recordings(self) -> RecordingList:
        """
        @return: list of planned recordings
        """
        if Path(self.pluginpath(G.RECORDINGS_INFO)).exists():
            recordingsInfo = json.loads(Path(self.pluginpath(G.RECORDINGS_INFO)).read_text())
            return RecordingList(recordingsInfo['recorded'])
        return None

    def get_event_details(self, eventId):
        url = G.REPLAYEVENT_URL + eventId
        params = {
            'returnLinearContent': 'true',
            'forceLinearResponse': 'true',
            'language': 'nl'}
        response = super().do_get(url=url,
                                  params=params)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def get_extra_headers(self):
        return self.extraHeaders

    def get_cookies_dict(self):
        return self.cookies.get_dict()
