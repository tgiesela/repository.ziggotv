"""
Module with classes to support the API of ziggo-go
"""
# pylint: disable=too-many-lines
import base64
import datetime
import json
from typing import List
from http.cookiejar import Cookie

from datetime import timezone
from pathlib import Path
import requests

import xbmc
import xbmcaddon
import xbmcvfs

from resources.lib.utils import b2ah, WebException
from resources.lib.channel import Channel
from resources.lib.globals import G, CONST_BASE_HEADERS, ALLOWED_LICENSE_HEADERS
from resources.lib.recording import RecordingList
from resources.lib.streaminginfo import StreamingInfo, ReplayStreamingInfo, VodStreamingInfo, RecordingStreamingInfo
from resources.lib.utils import DatetimeHelper


class Web(requests.Session):
    """
    class which extends requests.Session and for use by LoginSession
    """

    def __init__(self, addon: xbmcaddon.Addon):
        super().__init__()
        self.printResponseContent = addon.getSettingBool('print-response-content')
        self.printRequestContent = addon.getSettingBool('print-request-content')
        self.printNetworkTraffic = addon.getSettingBool('print-network-traffic')
        self.addonPath = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        self.load_cookies()

    def pluginpath(self, name):
        """returns full path for the plugin to store a file"""
        return self.addonPath + name

    def dump_cookies(self):
        """routine for debugging"""
        for _cookie in self.cookies:
            c: Cookie = _cookie
            xbmc.log('Cookie: {0}, domain: {1}, value: {2}, path: {3}'.format(c.name, c.domain, c.value, c.path))

    def save_cookies(self, response):
        """save cookies to a file"""
        newCookies = requests.utils.dict_from_cookiejar(response.cookies)
        if Path(self.pluginpath(G.COOKIES_INFO)).exists():
            savedCookies = json.loads(Path(self.pluginpath(G.COOKIES_INFO)).read_text(encoding='utf-8'))
        else:
            savedCookies = {}

        savedCookies = self.merge(newCookies, savedCookies)
        Path(self.pluginpath(G.COOKIES_INFO)).write_text(json.dumps(savedCookies), encoding='utf-8')

    def load_cookies(self):
        """load cookies from disk"""
        if Path(self.pluginpath(G.COOKIES_INFO)).exists():
            cookies = json.loads(Path(self.pluginpath(G.COOKIES_INFO)).read_text(encoding='utf-8'))
        else:
            cookies = {}
        cookies = requests.utils.cookiejar_from_dict(cookies)  # turn dict to cookiejar
        self.cookies.update(cookies)
        return cookies

    @staticmethod
    def merge(dict1, dict2):
        """merge two dictionaries"""
        dict2.update(dict1)
        return dict2

    @staticmethod
    def __print_request(response):
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

    @staticmethod
    def __print_response(response):
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

    def print_dialog(self, response):
        """debugging: print a http dialogue with headers and data from the received response (if any)"""
        if not self.printNetworkTraffic:
            return

        print("URL: {0} {1}".format(response.request.method, response.url))
        print("Status-code: {0}".format(response.status_code))
        print("Request headers: {0}".format(response.request.headers))
        print("Response headers: {0}".format(response.headers))
        print("Cookies: ", self.cookies.get_dict())

        if self.printRequestContent:
            self.__print_request(response)

        if self.printResponseContent:
            self.__print_response(response)

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
    """
    Implements the ziggo-go API (partially)
    """

    # pylint: disable=too-many-instance-attributes, too-many-public-methods
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
        # self.get_session_info() # We always start with a clean session
        # self.get_customer_info()
        # self.get_entitlements()

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
            Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(self.sessionInfo), encoding='utf-8')
        return False

    def get_session_info(self):
        """
        load session information from disk
        @return: nothing
        """
        if Path(self.pluginpath(G.SESSION_INFO)).exists():
            self.sessionInfo = json.loads(Path(self.pluginpath(G.SESSION_INFO)).read_text(encoding='utf-8'))
        else:
            self.sessionInfo = {}
        return self.sessionInfo

    def get_customer_info(self):
        """
        load customer information from disk
        @return: nothing
        """
        if Path(self.pluginpath(G.CUSTOMER_INFO)).exists():
            self.customerInfo = json.loads(Path(self.pluginpath(G.CUSTOMER_INFO)).read_text(encoding='utf-8'))
            self.set_active_profile(self.get_profiles()[0])
        else:
            self.customerInfo = {}
        return self.customerInfo

    def get_channels(self):
        """
        load the channels from disk
        @return: list of Channel objects
        """
        if Path(self.pluginpath(G.CHANNEL_INFO)).exists():
            channelInfo = json.loads(Path(self.pluginpath(G.CHANNEL_INFO)).read_text(encoding='utf-8'))
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
        """
        load entitlement information from disk
        @return: entitlement json string
        """
        if Path(self.pluginpath(G.ENTITLEMENTS_INFO)).exists():
            self.entitlementsInfo = json.loads(Path(self.pluginpath(G.ENTITLEMENTS_INFO)).read_text(encoding='utf-8'))
        else:
            self.entitlementsInfo = {}
        return self.entitlementsInfo

    def __obtain_customer_info(self):
        """
        get customer information from ziggo go and store it in a disk-file
        @return: nothing
        """
        if not self.__claims_token_still_valid():
            self.__delete_cookie("CLAIMSTOKEN")
            url = G.PERSONALISATION_URL.format(householdid=self.sessionInfo['householdId'])
            response = super().do_get(url, params={'with': 'profiles,devices'})
            if not self.__status_code_ok(response):
                raise WebException(response)
            self.customerInfo = response.json()
            Path(self.pluginpath(G.CUSTOMER_INFO)).write_text(json.dumps(self.customerInfo), encoding='utf-8')
            self.refresh_channels()  # Should be sufficient to this only here

    @staticmethod
    def __date_expired(unixDateTime) -> bool:
        dateToCheck = DatetimeHelper.from_unix(unixDateTime)
        expiryDate = DatetimeHelper.now()
        # Here we add 11 minutes because the service will check with an interval of 10 minutes and then
        # the token may expire during processing
        expiryDate = expiryDate + datetime.timedelta(minutes=11)
        xbmc.log('__date_expired: dateToCheck {0} expiryDate {1} expired: {2}'.format(dateToCheck,
                                                                                      expiryDate,
                                                                                      dateToCheck <= expiryDate),
                 xbmc.LOGDEBUG)
        return dateToCheck <= expiryDate

    def __access_token_still_valid(self):
        if 'accessToken' in self.sessionInfo:
            token = self.sessionInfo["accessToken"]
            parts = token.split('.')
            if len(parts) != 3:
                xbmc.log('Invalid jwt', xbmc.LOGERROR)
                return False
            expInfo = json.loads(base64.b64decode(parts[1] + '=='))
            return not self.__date_expired(expInfo['exp'])
        return False

    def __claims_token_still_valid(self):
        if 'claimsToken' in self.customerInfo:
            token = self.customerInfo["claimsToken"]
            parts = token.split('.')
            if len(parts) != 3:
                xbmc.log('Invalid jwt', xbmc.LOGERROR)
                return False
            expInfo = json.loads(base64.b64decode(parts[1] + '=='))
            return not self.__date_expired(expInfo['exp'])
        return False

    def __delete_cookie(self, name):
        try:
            for _cookie in self.cookies:
                c: Cookie = _cookie
                if c.name == name:
                    self.cookies.clear(domain=c.domain, path=c.path, name=c.name)

        # pylint: disable=broad-exception-caught
        except Exception as exc:
            xbmc.log("{0} cannot be removed: {1}".format(name, exc), xbmc.LOGERROR)
            xbmc.log("COOKIES: {0}".format(self.cookies.keys()), xbmc.LOGERROR)

    def __refresh_token_valid(self):
        _valid = False
        if len(self.sessionInfo) == 0:  # Session_info empty, so not successfully logged in
            return False

        # We moeten het JWT token decoderen en daar de geldigheidsdatum uithalen.

        if not self.__date_expired(self.sessionInfo['refreshTokenExpiry']):
            xbmc.log("issued at: {0}".format(DatetimeHelper.from_unix(self.sessionInfo['issuedAt'])),
                     xbmc.LOGDEBUG)
            xbmc.log("refresh at: {0}".format(DatetimeHelper.from_unix(self.sessionInfo['refreshTokenExpiry'])),
                     xbmc.LOGDEBUG)
            xbmc.log("logon still valid",
                     xbmc.LOGDEBUG)
            return True

        return False

    def login(self, username: str, password: str):
        """
        Function to authenticate against the API
        @param username:
        @param password:
        @return: sessionInfo string in json format
        """
        self.username = username
        if self.__access_token_still_valid():
            xbmc.log("Login: Accesstoken still valid", xbmc.LOGDEBUG)
        else:
            if self.__refresh_token_valid():
                xbmc.log("Login: Accesstoken expired, refresh token still valid, refreshing login", xbmc.LOGINFO)
                # Als het token niet meer geldig is moet het ACCESSTOKEN-cookie worden verwijderd!
                self.__delete_cookie('ACCESSTOKEN')
                response = super().do_post(G.AUTHENTICATION_URL + "/refresh",
                                           jsonData={"refreshToken": self.sessionInfo['refreshToken'],
                                                     "username": username})
                if not self.__status_code_ok(response):
                    raise WebException(response)
                self.sessionInfo = response.json()
                Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(self.sessionInfo), encoding='utf-8')
                self.refresh_entitlements()
            else:
                xbmc.log("Login: refresh token expired, new login required", xbmc.LOGINFO)
                self.extraHeaders = {}
                self.cookies.clear_session_cookies()
                Path(self.pluginpath(G.COOKIES_INFO)).unlink(missing_ok=True)
                response = super().do_post(G.AUTHENTICATION_URL, params={'loginAction': 'user'},
                                           jsonData={"password": password,
                                                     "username": username})
                if not self.__status_code_ok(response):
                    raise WebException(response)
                self.sessionInfo = response.json()
                Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(self.sessionInfo), encoding='utf-8')
                self.refresh_entitlements()

        self.__obtain_customer_info()
        if self.activeProfile is None:
            self.activeProfile = self.customerInfo["profiles"][0]
        profileId = self.activeProfile["profileId"]
        trackingId = self.customerInfo["hashedCustomerId"]
        self.extraHeaders = {
            #            'X-OESP-Username': self.username,
            'x-tracking-id': trackingId,
            'X-Profile': profileId
        }
        return self.sessionInfo

    def refresh_channels(self):
        """
        Obtain list of channels via the API and store on disk
        @return: nothing
        """
        response = super().do_get(G.CHANNELS_URL,
                                  params={'cityId': self.customerInfo["cityId"],
                                          'language': 'nl',
                                          'productClass': 'Orion-DASH'},
                                  extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        Path(self.pluginpath(G.CHANNEL_INFO)).write_text(json.dumps(response.json()), encoding='utf-8')

    def refresh_entitlements(self):
        """
        Obtain entitlements via the API and store on disk
        @return: nothing
        """
        url = G.ENTITLEMENTS_URL.format(householdid=self.sessionInfo['householdId'])
        response = super().do_get(url,
                                  params={'enableDayPass': 'true'},
                                  extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        Path(self.pluginpath(G.ENTITLEMENTS_INFO)).write_text(json.dumps(response.json()), encoding='utf-8')

    def refresh_widevine_license(self):
        """
        Obtain widevine license via the API and store on disk
        @return: nothing
        """
        response = super().do_get(G.WIDEVINE_URL,
                                  extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)
        encodedContent = base64.b64encode(response.content)
        Path(self.pluginpath(G.WIDEVINE_LICENSE)).write_text(encodedContent.decode("ascii"), encoding='ascii')

    def obtain_tv_streaming_token(self, channelId, assetType) -> StreamingInfo:
        """
        obtain streaming token for watching a channel
        @param channelId:
        @param assetType: obtained from the channel locators
        @return: StreamingInfo object
        """
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

    def obtain_replay_streaming_token(self, path) -> ReplayStreamingInfo:
        """
        obtain streaming token for replay of an event
        @param path: the id of the event
        @return: ReplayStreamingInfo object
        """
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

    def obtain_vod_streaming_token(self, streamId) -> VodStreamingInfo:
        """
        obtain streaming token for play of a Video On Demand
        @param streamId: the id of the vod
        @return: VodStreamingInfo object
        """
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

    def obtain_recording_streaming_token(self, streamid) -> RecordingStreamingInfo:
        """
        obtain streaming token for play of a recording
        @param streamid: the id of the recording
        @return: RecordingStreamingInfo object
        """
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

    def get_license(self, contentId, requestData, licenseHeaders):
        """
        Get a license to play a channel, recording, vod etc via the API
        @param contentId:
        @param requestData:
        @param licenseHeaders:
        @return: response of the host
        """
        url = G.LICENSE_URL
        licenseHeaders.update({'x-streaming-token': self.streamingToken})
        for key in licenseHeaders:
            if key in ALLOWED_LICENSE_HEADERS:
                pass
            else:
                xbmc.log("HEADER DROPPPED: {0}:{1}".format(key, licenseHeaders[key]), xbmc.LOGDEBUG)
                licenseHeaders[key] = None
        response = super().do_post(url,
                                   params={'ContentId': contentId},
                                   data=requestData,
                                   extraHeaders=licenseHeaders)
        if 'x-streaming-token' in response.headers:
            self.streamingToken = response.headers['x-streaming-token']
        return response

    def update_token(self, streamingToken):
        """
        update a streaming token via the API
        @param streamingToken: the latest token
        @return: new streaming token
        """
        url = G.LICENSE_URL + '/token'
        profileId = self.activeProfile["profileId"]
        trackingId = self.get_customer_info()["hashedCustomerId"]
        self.extraHeaders = {
            #            'X-OESP-Username': self.username,
            'x-tracking-id': trackingId,
            'X-Profile': profileId,
            'x-streaming-token': streamingToken
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

    def delete_token(self, streamingId):
        """
        delete streaming token via the API
        @param streamingId: the token to delete
        @return: nothing
        """
        url = G.LICENSE_URL + '/token'
        profileId = self.activeProfile["profileId"]
        trackingId = self.get_customer_info()["hashedCustomerId"]
        self.extraHeaders = {
            #            'X-OESP-Username': self.username,
            'x-tracking-token': trackingId,
            'X-Profile': profileId,
            'x-streaming-token': streamingId
        }
        response = super().do_delete(url,
                                     data=None,
                                     params=None,
                                     extraHeaders=self.extraHeaders)
        if not self.__status_code_ok(response):
            raise WebException(response)

    def get_manifest(self, url):
        """
        Get a manifest file via the API
        @param url:
        @return:
        """
        response = super().do_get(url, data=None, params=None)
        return response

    def get_profiles(self):
        """
        get the user profiles
        @return: profiles for the customer in json format
        """
        return self.customerInfo["profiles"]

    def set_active_profile(self, profile):
        """
        set the active user profile
        @param profile: the id of the profile
        @return:
        """
        self.activeProfile = profile

    def __get_optin_date(self, optInType, unixTime=False):
        optins = self.customerInfo['customerOptIns']
        i = 0
        while i < len(optins):
            if optins[i]['optInType'] == optInType:
                replayOptinDate = optins[i]['lastModified']
                if unixTime:
                    return DatetimeHelper.to_unix(replayOptinDate, '%Y-%m-%dT%H:%M:%S.%fZ')
                return replayOptinDate
            i += 1
        if unixTime:
            return 0
        return ''

    def obtain_structure(self):
        """
        Obtain structure for the web-page. Currently not used
        @return:
        """
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
        """
        Obtain the home collection for the web-page. Currently not used
        @param collection:
        @return:
        """
        profileId = self.activeProfile["profileId"]
        householdId = self.customerInfo['customerId']
        cityId = self.customerInfo["cityId"]
        replayOptinDate = self.__get_optin_date('replay', unixTime=False)
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

    def obtain_grid_screen_details(self, collectionId):
        """
        obtain a list of movies or series to list in the addon menu
        @param collectionId: the id of a genre
        @return:
        """
        url = G.GRIDSERVICE_URL + collectionId
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

    def obtain_vod_screen_details(self, collectionId):
        """
        obtain a list of genres
        @param collectionId:
        @return:
        """
        url = G.VOD_SERVICE_URL + 'collections-screen/{id}'.format(id=collectionId)
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

    def obtain_asset_details(self, assetId, brandingProviderId=None):
        """
        Obtain movie details
        @param assetId:
        @param brandingProviderId:
        @return: json format of movie details
        """
        url = G.VOD_SERVICE_URL + 'details-screen/{id}'.format(id=assetId)
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

    def obtain_series_overview(self, seriesId):
        """
        obtain series details
        @param seriesId:
        @return: json format of series details
        """
        url = G.PICKERSERVICE_URL + 'showPage/' + seriesId + '/nl'
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
        """
        get a list of additional items to show in the addon menu (e.g. Sky Showtime etc.)
        @return: list of items in json format
        """
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
        """
        get a list of episode for a series/show
        @param item:
        @return: list of episodes in json format
        """
        profileId = self.activeProfile["profileId"]
        cityId = self.customerInfo["cityId"]
        url = G.ZIGGOPROD_URL + 'eng/web/picker-service/v2/episodePicker'
        params = {'seriesCrid': item,
                  'language': 'nl',
                  'country': 'nl',
                  'cityId': cityId,
                  'replayOptedInTime': self.__get_optin_date('replay', unixTime=True),
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
        """
        get information of an episode for a series/show
        @param item:
        @return:
        """
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
                          'replayOptedInTime': self.__get_optin_date('replay', unixTime=True),
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
        """
        get a list of most watched channels (not used)
        @return:
        """
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

    def get_events(self, startTime: str):
        """
        get a list of events to use in the EPG
        :param startTime: datetime in format 'yyyymmddhhss'
        :return: list of events per channel
        """
        url = G.EVENTS_URL + startTime
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
        response = super().do_get(url, params={'isAdult': isAdult,
                                               'offset': 0,
                                               'limit': 100,
                                               # 'sort': 'time',
                                               # 'sortOrder': 'desc',
                                               # 'profileId': self.activeProfile['profileId'],
                                               'language': 'nl'})
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def __get_recordings(self, isAdult: bool):
        """
        Obtain list of recordings
        @param isAdult:
        @return:
        """
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'recordings'
        response = super().do_get(url, params={'isAdult': isAdult,
                                               'offset': 0,
                                               'limit': 100,
                                               # 'sort': 'time',
                                               # 'sortOrder': 'desc',
                                               # 'profileId': self.activeProfile['profileId'],
                                               'language': 'nl'})
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def __get_recordings_season(self, channelId, showId):
        """
        get a list of recordings in a series/show
        @param channelId:
        @param showId:
        @return:
        """
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'episodes/shows/' + showId
        response = super().do_get(url, params={'source': 'booking',
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

    def get_recording_details(self, recordingId):
        """
        get the details of a recording
        @param recordingId:
        @return:
        """
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'details/single/' + recordingId
        response = super().do_get(url, params={'profileId': self.activeProfile['profileId'],
                                               'language': 'nl'
                                               })
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def delete_recordings_planned(self, event=None, show=None, channelId=None):
        """
        delete planned recordings
        @param event: events to delete
        @param show: series/show/season to delete
        @param channelId:
        @return:
        """
        if show is not None and channelId is not None:
            url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'bookings'
            request = {'events': [], 'shows': [{'showId': show, 'channelId': channelId}]}
        elif event is not None:
            url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'bookings/single/' + event
            request = None
        else:
            raise RuntimeError('Logic error: trying to delete booking without parameters')
        response = super().do_delete(url=url, jsonData=request)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def delete_recordings(self, event=None, show=None, channelId=None):
        """
        delete a list of recordings
        @param event: events delete
        @param show: series/show/season to delete
        @param channelId:
        @return:
        """
        if show is not None and channelId is not None:
            url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'recordings'
            request = {'events': [], 'shows': [{'showId': show, 'channelId': channelId}]}
        elif event is not None:
            url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'recordings/single/' + event
            request = None
        else:
            raise RuntimeError('Logic error: trying to delete recording without parameters')
        response = super().do_delete(url=url, jsonData=request)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def record_event(self, eventId):
        """
        Record an event
        @param eventId:
        @return:
        """
        url = G.RECORDINGS_URL.format(householdid=self.sessionInfo['householdId']) + 'bookings/single'
        request = {'eventId': eventId,
                   'retentionLimit': 365}
        response = super().do_post(url=url, jsonData=request)
        if not self.__status_code_ok(response):
            raise WebException(response)
        return json.loads(response.content)

    def record_show(self, eventId, channelId):
        """
        record a show/series/season
        @param eventId:
        @param channelId:
        @return:
        """
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
        Path(self.pluginpath(G.RECORDINGS_INFO)).write_text(json.dumps(recJson), encoding='utf-8')

    def get_recordings_planned(self) -> RecordingList:
        """
        @return: list of planned recordings
        """
        if Path(self.pluginpath(G.RECORDINGS_INFO)).exists():
            recordingsInfo = json.loads(Path(self.pluginpath(G.RECORDINGS_INFO)).read_text(encoding='utf-8'))
            return RecordingList(recordingsInfo['planned'])
        return RecordingList()

    def get_recordings(self) -> RecordingList:
        """
        @return: list of planned recordings
        """
        if Path(self.pluginpath(G.RECORDINGS_INFO)).exists():
            recordingsInfo = json.loads(Path(self.pluginpath(G.RECORDINGS_INFO)).read_text(encoding='utf-8'))
            return RecordingList(recordingsInfo['recorded'])
        return None

    def get_event_details(self, eventId):
        """
        Get the details of an event for the EPG
        @param eventId:
        @return:
        """
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
        """
        get a list of extra headers
        @return:
        """
        return self.extraHeaders

    def get_cookies_dict(self):
        """
        get a list of cookies
        @return:
        """
        return self.cookies.get_dict()
