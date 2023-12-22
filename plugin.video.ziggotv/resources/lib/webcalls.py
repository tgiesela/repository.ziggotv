import base64
import datetime
import json
from typing import List

import requests
from datetime import timezone
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcvfs

from resources.lib.Channel import Channel
from resources.lib.globals import G
from resources.lib.utils import DatetimeHelper

try:
    import pyjwt
except:
    import jwt as pyjwt


def b2ah(barr):
    return barr.hex()


class Web(requests.Session):
    addon_path = ''

    def __init__(self, addon: xbmcaddon.Addon):
        super().__init__()
        self.print_network_traffic = addon.getSettingBool('print-network-traffic')
        self.addon_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        self.load_cookies()

    def pluginpath(self, name):
        return self.addon_path + name

    def dump_cookies(self):
        print(len(self.cookies))
        print(self.cookies)

    def save_cookies(self, response):
        new_cookies = requests.utils.dict_from_cookiejar(response.cookies)
        if Path(self.pluginpath(G.COOKIES_INFO)).exists():
            saved_cookies = json.loads(Path(self.pluginpath(G.COOKIES_INFO)).read_text())  # save them to file as JSON
        else:
            saved_cookies = {}

        saved_cookies = self.merge(new_cookies, saved_cookies)
        # new_cookies = requests.utils.dict_from_cookiejar(self.session.cookies)  # turn cookiejar into dict
        Path(self.pluginpath(G.COOKIES_INFO)).write_text(json.dumps(saved_cookies))  # save them to file as JSON

    def load_cookies(self):
        if Path(self.pluginpath(G.COOKIES_INFO)).exists():
            cookies = json.loads(Path(self.pluginpath(G.COOKIES_INFO)).read_text())  # save them to file as JSON
        else:
            cookies = {}
        cookies = requests.utils.cookiejar_from_dict(cookies)  # turn dict to cookiejar
        self.cookies.update(cookies)
        return cookies

    def merge(self, dict1, dict2):
        dict2.update(dict1)
        return dict2

    def print_dialog(self, response):
        if not self.print_network_traffic:
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
                if type(response.request.body) is str:
                    s = bytearray(response.request.body,'ascii')
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

    def do_post(self, url: str, data=None, json_data=None, extra_headers=None, params=None):
        """
         :param params: query parameters
         :param json_data: (optional) json data to send
         :param url: web address to connect to
         :param data: (optional) data to send with request
         :param extra_headers: (optional) extra headers to add to default headers send
         :return: response
         """
        if extra_headers is None:
            extra_headers = {}
        headers = dict(G.CONST_BASE_HEADERS)
        if json_data is not None:
            headers.update({"Content-Type": "application/json; charset=utf-8"})
        for key in extra_headers:
            headers.update({key: extra_headers[key]})
        response = super().post(url, data=data, json=json_data, headers=headers, params=params)
        self.print_dialog(response)
        self.save_cookies(response)
        return response

    def do_get(self, url: str, data=None, json_data=None, extra_headers=None, params=None):
        """
         :param json_data: (optional) json data to send
         :param url: web address to connect to
         :param data: (optional) data to send with request
         :param extra_headers: (optional) extra headers to add to default headers send
         :param params: (optional) params used in query request (get)
         :return: response
         """
        if extra_headers is None:
            extra_headers = {}
        headers = dict(G.CONST_BASE_HEADERS)
        if json_data is not None:
            headers.update({"Content-Type": "application/json; charset=utf-8"})
        for key in extra_headers:
            headers.update({key: extra_headers[key]})
        response = super().get(url, data=data, json=json_data, headers=headers, params=params)
        self.print_dialog(response)
        # self.dump_cookies()
        self.save_cookies(response)
        return response

    def do_delete(self, url: str, data=None, json_data=None, extra_headers=None, params=None):
        """
         :param json_data: (optional) json data to send
         :param url: web address to connect to
         :param data: (optional) data to send with request
         :param extra_headers: (optional) extra headers to add to default headers send
         :param params: (optional) params used in query request (get)
         :return: response
         """
        if extra_headers is None:
            extra_headers = {}
        headers = dict(G.CONST_BASE_HEADERS)
        if json_data is not None:
            headers.update({"Content-Type": "application/json; charset=utf-8"})
        for key in extra_headers:
            headers.update({key: extra_headers[key]})
        response = super().delete(url, data=data, json=json_data, headers=headers, params=params)
        self.print_dialog(response)
        # self.dump_cookies()
        self.save_cookies(response)
        return response


class LoginSession(Web):
    session_info = {}
    channel_info = {}
    channels: List[Channel] = []
    customer_info = {}
    logged_on = False

    def __init__(self, addon):
        super().__init__(addon)
        self.vod_stream_info = None
        self.replay_stream_info = None
        self.active_profile = None
        self.streaming_token = None
        self.entitlements_info = None
        self.extra_headers = {}
        self.stream_info = None
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
        if response.status_code == 200 or response.status_code == 204:
            return True
        if response.status_code == 401:  # not authenticated
            self.session_info = {}
            Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(self.session_info))
        return False

    def get_session_info(self):
        if Path(self.pluginpath(G.SESSION_INFO)).exists():
            self.session_info = json.loads(Path(self.pluginpath(G.SESSION_INFO)).read_text())
        else:
            self.session_info = {}
        return self.session_info

    def get_customer_info(self):
        if Path(self.pluginpath(G.CUSTOMER_INFO)).exists():
            self.customer_info = json.loads(Path(self.pluginpath(G.CUSTOMER_INFO)).read_text())
            self.set_active_profile(self.get_profiles()[0])
        else:
            self.customer_info = {}
        return self.customer_info

    def get_channels(self):
        if Path(self.pluginpath(G.CHANNEL_INFO)).exists():
            channel_info = json.loads(Path(self.pluginpath(G.CHANNEL_INFO)).read_text())
            self.channels.clear()
            for channel in channel_info:
                channel = Channel(channel)
                self.channels.append(channel)
        else:
            self.channels = []
        return self.channels

    def get_entitlements(self):
        if Path(self.pluginpath(G.ENTITLEMENTS_INFO)).exists():
            self.entitlements_info = json.loads(Path(self.pluginpath(G.ENTITLEMENTS_INFO)).read_text())
        else:
            self.entitlements_info = {}
        return self.entitlements_info

    def obtain_customer_info(self):
        try:
            self.cookies.pop("CLAIMSTOKEN")
        except:
            pass
        url = G.personalisation_URL.format(householdid=self.session_info['householdId'])
        response = super().do_get(url, params={'with': 'profiles,devices'})
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain customer info")
        Path(self.pluginpath(G.CUSTOMER_INFO)).write_text(json.dumps(response.json()))

    def __login_valid(self):
        _valid = False
        if len(self.session_info) == 0:  # Session_info empty, so not successfully logged in
            return False

        # We moeten het JWT token decoderen en daar de geldigheidsdatum uithalen.
        # Als het token niet meer geldig is moet het ACCESSTOKEN-cookie worden verwijderd!

        if DatetimeHelper.fromUnix(self.session_info['refreshTokenExpiry']) > datetime.datetime.now():
            xbmc.log("issued at: {0}".format(DatetimeHelper.fromUnix(self.session_info['issuedAt']))
                     , xbmc.LOGDEBUG)
            xbmc.log("refresh at: {0}".format(DatetimeHelper.fromUnix(self.session_info['refreshTokenExpiry']))
                     , xbmc.LOGDEBUG)
            xbmc.log("logon still valid"
                     , xbmc.LOGINFO)
            return True

        return False

    def login(self, username: str, password: str):
        self.username = username
        if not self.__login_valid():
            self.extra_headers = {}
            self.cookies.clear_session_cookies()
            Path(self.pluginpath(G.COOKIES_INFO)).unlink(missing_ok=True)
            response = super().do_post(G.authentication_URL,
                                       json_data={"password": password,
                                                  "username": username})
            if not self.__status_code_ok(response):
                raise RuntimeError("status code <> 200 during authentication")
            Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(response.json()))
            self.session_info = self.get_session_info()

            self.obtain_customer_info()
        else:
            # Zie comment bij login_valid()
            try:
                jwt_decoded = pyjwt.decode(self.session_info["accessToken"], options={"verify_signature": False})
                exp = DatetimeHelper.fromUnix(jwt_decoded["exp"])
                now = DatetimeHelper.now()
            except pyjwt.exceptions.ExpiredSignatureError:
                exp = DatetimeHelper.now()
                now = exp
            if exp > now:
                xbmc.log("Accesstoken still valid", xbmc.LOGINFO)
            else:
                self.cookies.pop("ACCESSTOKEN")
                response = super().do_post(G.authentication_URL + "/refresh",
                                           json_data={"refreshToken": self.session_info['refreshToken'],
                                                      "username": username})
                if not self.__status_code_ok(response):
                    raise RuntimeError("status code <> 200 during authentication")
                Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(response.json()))

                self.obtain_customer_info()
            self.session_info = self.get_session_info()

        self.customer_info = self.get_customer_info()
        if self.active_profile is None:
            self.active_profile = self.customer_info["profiles"][0]
        profile_id = self.active_profile["profileId"]
        tracking_id = self.customer_info["hashedCustomerId"]
        self.extra_headers = {
            'X-OESP-Username': self.username,
            'x-tracking-id': tracking_id,
            'X-Profile': profile_id
        }
        return self.session_info

    def refresh_channels(self):
        response = super().do_get(G.channels_URL,
                                  params={'cityId': self.customer_info["cityId"],
                                          'language': 'nl',
                                          'productClass': 'Orion-DASH'},
                                  extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain channel info")
        Path(self.pluginpath(G.CHANNEL_INFO)).write_text(json.dumps(response.json()))

    def refresh_entitlements(self):
        url = G.entitlements_URL.format(householdid=self.session_info['householdId'])
        response = super().do_get(url,
                                  params={'enableDayPass': 'true'},
                                  extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain entitlement info")
        Path(self.pluginpath(G.ENTITLEMENTS_INFO)).write_text(json.dumps(response.json()))

    def refresh_widevine_license(self):
        response = super().do_get(G.widevine_URL,
                                  extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain widevine info")
        encoded_content = base64.b64encode(response.content)
        Path(self.pluginpath(G.WIDEVINE_LICENSE)).write_text(encoded_content.decode("ascii"))

    def obtain_tv_streaming_token(self, channel: Channel, asset_type):
        url = G.streaming_URL.format(householdid=self.session_info['householdId']) + '/live'
        response = super().do_post(url,
                                   params={
                                       'channelId': channel.id
                                       , 'assetType': asset_type
                                       , 'profileId': self.active_profile['profileId']
                                       , 'liveContentTimestamp': DatetimeHelper.now(timezone.utc).isoformat()
                                   },
                                   extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain streaming info")
        self.stream_info = json.loads(response.content)
        self.streaming_token = response.headers["x-streaming-token"]
        return response.headers["x-streaming-token"]

    def obtain_replay_streaming_token(self, path):
        url = G.streaming_URL.format(householdid=self.session_info['householdId']) + '/replay'
        response = super().do_post(url,
                                   params={
                                       'eventId': path,
                                       'abrType': 'BR-AVC-DASH',
                                       'profileId': self.active_profile['profileId']
                                   },
                                   extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain replay streaming info")
        self.replay_stream_info = json.loads(response.content)
        self.streaming_token = response.headers["x-streaming-token"]
        return response.headers["x-streaming-token"]

    def obtain_vod_streaming_token(self, id):
        url = G.streaming_URL.format(householdid=self.session_info['householdId']) + '/vod'
        response = super().do_post(url,
                                   params={
                                       'contentId': id,
                                       'abrType': 'BR-AVC-DASH',
                                       'profileId': self.active_profile['profileId']
                                   },
                                   extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain vod streaming info")
        self.vod_stream_info = json.loads(response.content)
        self.streaming_token = response.headers["x-streaming-token"]
        return response.headers["x-streaming-token"]

    def get_license(self, content_id, request_data, license_headers):
        url = G.license_URL
        license_headers.update({'x-streaming-token': self.streaming_token})
        for key in license_headers:
            if key in G.ALLOWED_LICENSE_HEADERS:
                pass
            else:
                xbmc.log("HEADER DROPPPED: {0}:{1}".format(key, license_headers[key]), xbmc.LOGDEBUG)
                license_headers[key] = None
        response = super().do_post(url,
                                   params={'ContentId': content_id},
                                   data=request_data,
                                   extra_headers=license_headers)
        if 'x-streaming-token' in response.headers:
            self.streaming_token = response.headers['x-streaming-token']
        return response

    def update_token(self, streaming_token):
        url = G.license_URL + '/token'
        profile_id = self.active_profile["profileId"]
        tracking_id = self.get_customer_info()["hashedCustomerId"]
        self.extra_headers = {
            'X-OESP-Username': self.username,
            'x-tracking-id': tracking_id,
            'X-Profile': profile_id,
            'x-streaming-token': streaming_token
        }
        response = super().do_post(url,
                                   data=None,
                                   params=None,
                                   extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during update token")
        if 'x-streaming-token' in response.headers:
            self.streaming_token = response.headers['x-streaming-token']
            return response.headers["x-streaming-token"]
        else:
            return ''

    def delete_token(self, streaming_id):
        url = G.license_URL + '/token'
        profile_id = self.active_profile["profileId"]
        tracking_id = self.get_customer_info()["hashedCustomerId"]
        self.extra_headers = {
            'X-OESP-Username': self.username,
            'x-tracking-token': tracking_id,
            'X-Profile': profile_id,
            'x-streaming-token': streaming_id
        }
        response = super().do_delete(url,
                                     data=None,
                                     params=None,
                                     extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during delete token")

    def get_manifest(self, url):
        response = super().do_get(url, data=None, params=None)
        return response

    def get_profiles(self):
        return self.customer_info["profiles"]

    def set_active_profile(self, profile):
        self.active_profile = profile

    def __getOptinDate(self, optin_type, unixtime=False):
        optins = self.customer_info['customerOptIns']
        i = 0
        replay_optin_date = None
        while i < len(optins):
            if optins[i]['optInType'] == optin_type:
                replay_optin_date = optins[i]['lastModified']
                if unixtime:
                    return DatetimeHelper.toUnix(replay_optin_date, '%Y-%m-%dT%H:%M:%S.%fZ')
                #                    return int(time.mktime(datetime.datetime.strptime(replay_optin_date
                #                                                                      , '%Y-%m-%dT%H:%M:%S.%fZ').timetuple()))
                else:
                    return replay_optin_date
            i += 1
        if unixtime:
            return 0
        else:
            return ''

    def obtain_structure(self):
        url = G.homeservice_URL + 'structure/'
        params = {
            'profileId': self.active_profile["profileId"]
            , 'language': 'nl'
            , 'optIn': 'true'
            , 'clientType': 'HZNGO-WEB'
            # , 'version': '5.05'
            , 'featureFlags': 'client_Mobile'
        }
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain movies and series")
        return response.content

    def obtain_home_collection(self, collection: []):
        profile_id = self.active_profile["profileId"]
        household_id = self.customer_info['customerId']
        city_id = self.customer_info["cityId"]
        replay_optin_date = self.__getOptinDate('replay', unixtime=False)
        url = (G.homeservice_URL
               + 'customers/{household_id}/profiles/{profile_id}/screen'.format(household_id=household_id
                                                                                , profile_id=profile_id))
        params = {
            'id': ','.join(collection)
            , 'language': 'nl'
            , 'clientType': 'HZNGO-WEB'
            , 'maxRes': '4K'
            , 'cityId': city_id
            , 'replayOptInDate': replay_optin_date
            , 'goPlayable': 'false'
            , 'sharedProfile': self.active_profile['shared']
            , 'optIn': 'true'
            # , 'version': '5.05'
            , 'featureFlags': 'client_Mobile'
            , 'productClass': 'Orion-DASH'
            , 'useSeriesLogic': 'true'
        }
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain movies and series")

        return response.content

    def obtain_grid_screen_details(self, collection_id):
        url = G.gridservice_URL + collection_id
        city_id = self.customer_info["cityId"]
        profile_id = self.active_profile["profileId"]
        params = {
            'language': 'nl'
            , 'profileId': profile_id
            , 'type': 'Editorial'
            , 'sortType': 'popularity'
            , 'sortDirection': 'descending'
            , 'pagingOffset': '0'
            , 'maxRes': '4K'
            , 'cityId': city_id
            , 'onlyGoPlayable': 'false'
            , 'goDownloadable': 'false'
            , 'excludeAdult': 'false'
            , 'entityVersion': '1'
        }

        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain obtain_grid_screen_details")
        return json.loads(response.content)

    def obtain_vod_screen_details(self, collection_id):
        url = G.vod_service_URL + 'collections-screen/{id}'.format(id=collection_id)
        city_id = self.customer_info["cityId"]
        profile_id = self.active_profile["profileId"]
        params = {
            'language': 'nl'
            , 'profileId': profile_id
            , 'optIn': 'true'
            , 'sharedProfile': self.active_profile['shared']
            , 'maxRes': '4K'
            , 'cityId': city_id
            , 'excludeAdult': 'false'
            , 'onlyGoPlayable': 'false'
            , 'fallbackRootId': 'omw_hzn4_vod'
            , 'featureFlags': 'client_Mobile'
            , 'entityVersion': '1'
        }
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain obtain_vod_screen_details")
        return json.loads(response.content)

    def obtain_asset_details(self, id, brandingProviderId=None):
        url = G.vod_service_URL + 'details-screen/{id}'.format(id=id)
        city_id = self.customer_info["cityId"]
        profile_id = self.active_profile["profileId"]
        params = {
            'language': 'nl'
            , 'profileId': profile_id
            , 'maxRes': '4K'
            , 'cityId': city_id
            , 'brandingProviderId': brandingProviderId
        }
        if brandingProviderId is None:
            pass
        else:
            params.update({'brandingProviderId': brandingProviderId})
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain obtain asset details")
        return json.loads(response.content)

    def obtain_series_overview(self, id):
        url = G.pickerservice_URL + 'showPage/' + id + '/nl'
        city_id = self.customer_info["cityId"]
        params = {
            'cityId': city_id
            , 'country': 'nl'
            , 'mergingOn': 'true'
        }
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain obtain_series_overview")
        return json.loads(response.content)

    def obtain_vod_screens(self):
        url = G.vod_service_URL + 'structure/omw_play'
        params = {
            'language': 'nl'
            , 'menu': 'vod'
            , 'optIn': 'true'
            , 'fallbackRootId': 'omw_hzn4_vod'
            , 'featureFlags': 'client_Mobile'
            , 'maxRes': '4K'
            , 'excludeAdult': 'false'
            , 'entityVersion': '1'
        }
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain movies and series")

        return json.loads(response.content)

    def get_episode_list(self, item):
        profile_id = self.active_profile["profileId"]
        city_id = self.customer_info["cityId"]
        url = G.ZIGGOPROD_URL + 'eng/web/picker-service/v2/episodePicker'
        params = {'seriesCrid': item['id']
            , 'language': 'nl'
            , 'country': 'nl'
            , 'cityId': city_id
            , 'replayOptedInTime': self.__getOptinDate('replay', unixtime=True)
            , 'profileId': profile_id
            , 'maxRes': '4K'
            , 'mergingOn': 'true'
            , 'goPlayableOnly': 'false'}
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during get_episode_list")
        return json.loads(response.content)

    def get_episode(self, item):
        profile_id = self.active_profile["profileId"]
        city_id = self.customer_info["cityId"]
        if item['type'] == 'REPLAY':
            mostrelevant_episode = ''
            asset = ''
            if item['subType'] == 'SERIES':
                # first het episode info
                url = G.ZIGGOPROD_URL + 'eng/web/picker-service/v2/mostRelevantEpisode'
                params = {'seriesId': item['id']
                    , 'language': 'nl'
                    , 'country': 'nl'
                    , 'cityId': city_id
                    , 'replayOptedInTime': self.__getOptinDate('replay', unixtime=True)
                    , 'profileId': profile_id
                    , 'maxRes': '4K'
                    , 'mergingOn': 'true'
                    , 'goPlayableOnly': 'false'}

                response = super().do_get(url=url
                                          , params=params)
                if not self.__status_code_ok(response):
                    raise RuntimeError("status code <> 200 during obtain episode")
                mostrelevant_episode = response.content
            if item['subType'] in ['ASSET']:
                url = G.linearservice_v2_URL + 'replayEvent/{item}'.format(item=item['id'])
                params = {'language': 'nl'
                    , 'returnLinearContent': 'true'
                    , 'forceLinearResponse': 'false'}
                response = super().do_get(url=url
                                          , params=params)
                if not self.__status_code_ok(response):
                    raise RuntimeError("status code <> 200 during obtain episode")
                asset = response.content

            return mostrelevant_episode, asset
        return '', ''

    def get_mostwatched_channels(self):
        url = G.linearservice_v1_URL + 'mostWatchedChannels'
        city_id = self.customer_info["cityId"]
        params = {
            'cityId': city_id
            , 'productClass': 'Orion-DASH'}
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain mostwatched channels")
        return response.content

    def get_events(self, starttime: str):
        """

        :param starttime: datetime in format yyyymmddhhss
        :return: list of events per channel
        """
        url = G.events_URL + starttime
        response = super().do_get(url=url)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during get_events")
        return json.loads(response.content)

    def get_event_details(self, eventId):
        url = G.replayEvent_URL + eventId
        params = {
            'returnLinearContent': 'true'
            , 'forceLinearResponse': 'true'
            , 'language': 'nl'}
        response = super().do_get(url=url
                                  , params=params)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during get_event_details")
        return json.loads(response.content)
