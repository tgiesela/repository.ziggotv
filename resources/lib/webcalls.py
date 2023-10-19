import datetime, io, json, os, re, sys, threading, time, requests
from pathlib import Path
from datetime import timezone
from resources.lib.globals import G
import base64
import xbmcvfs

try:
    import pyjwt
except:
    import jwt as pyjwt


def b2ah(barr):
    return barr.hex()


class Web(requests.Session):
    addon_path = ''

    def __init__(self, addon):
        super().__init__()
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
        print("COOKIES saved: ", saved_cookies)

    def load_cookies(self):
        if Path(self.pluginpath(G.COOKIES_INFO)).exists():
            cookies = json.loads(Path(self.pluginpath(G.COOKIES_INFO)).read_text())  # save them to file as JSON
        else:
            cookies = {}
        cookies = requests.utils.cookiejar_from_dict(cookies)  # turn dict to cookiejar
        self.cookies.update(cookies)
        print("COOKIES loaded: ", self.cookies)
        return cookies

    def merge(self, dict1, dict2):
        dict2.update(dict1)
        return dict2

    def print_dialog(self, response):

        print("URL:", response.url)
        print("Status-code:", response.status_code)
        print("Request headers:", response.request.headers)
        print("Response headers:", response.headers)
        print("Cookies: ", self.cookies.get_dict())
        if response.request.body is None or response.request.body == '':
            print("Request data is empty")
        else:
            if "Content-Type" in response.request.headers:
                if response.request.headers["Content-Type"][0:16] == "application/json":
                    print("Request JSON-format:", response.request.body)
                else:
                    print("Request content:", response.request.body)
                    print("HEX: ", b2ah(response.request.body))
                    print("B64: ", base64.b64encode(response.request.body))
            else:
                print("HEX: ", b2ah(response.request.body))
                print("B64: ", base64.b64encode(response.request.body))

        if response.content is None or response.content == '':
            print("Response data is empty")
        else:
            if "Content-Type" in response.headers:
                if response.headers["Content-Type"][0:16] == "application/json":
                    print("Response JSON-format:", json.dumps(response.json()))
                else:
                    print("Response content:", response.content)
                    print("HEX: ", b2ah(response.content))
                    print("B64: ", base64.b64encode(response.content))
            else:
                print("HEX: ", b2ah(response.content))
                print("B64: ", base64.b64encode(response.content))

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
        #        self.session.cookies.get_dict()
        # self.dump_cookies()
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
    customer_info = {}
    logged_on = False

    def __init__(self, addon):
        super().__init__(addon)
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
        else:
            self.customer_info = {}
        return self.customer_info

    def get_channels(self):
        if Path(self.pluginpath(G.CHANNEL_INFO)).exists():
            self.channel_info = json.loads(Path(self.pluginpath(G.CHANNEL_INFO)).read_text())
        else:
            self.channel_info = {}
        return self.channel_info

    def get_entitlements(self):
        if Path(self.pluginpath(G.ENTITLEMENTS_INFO)).exists():
            self.entitlements_info = json.loads(Path(self.pluginpath(G.ENTITLEMENTS_INFO)).read_text())
        else:
            self.entitlements_info = {}
        return self.entitlements_info

    def __login_valid(self):
        _valid = False
        if len(self.session_info) == 0:  # Session_info empty, so not successfully logged in
            return False

        # We moeten het JWT token decoderen en daar de geldigheidsdatum uithalen.
        # Als het token niet meer geldig is moet het ACCESSTOKEN-cookie worden verwijderd!

        if datetime.datetime.fromtimestamp(self.session_info['refreshTokenExpiry']) > datetime.datetime.now():
            print("issued at:", datetime.datetime.fromtimestamp(self.session_info['issuedAt']))
            print("refresh at:", datetime.datetime.fromtimestamp(self.session_info['refreshTokenExpiry']))
            print("logon still valid")
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

            url = G.personalisation_URL.format(householdid=self.session_info['householdId'])
            response = super().do_get(url, params={'with': 'profiles,devices'})
            if not self.__status_code_ok(response):
                raise RuntimeError("status code <> 200 during obtain personalization info")
            Path(self.pluginpath(G.CUSTOMER_INFO)).write_text(json.dumps(response.json()))

        else:
            # Zie comment bij login_valid()
            try:
                jwt_decoded = pyjwt.decode(self.session_info["accessToken"], options={"verify_signature": False})
                exp = datetime.datetime.fromtimestamp(jwt_decoded["exp"])
                now = datetime.datetime.now()
            except pyjwt.exceptions.ExpiredSignatureError:
                exp = datetime.datetime.now()
                now = exp
            if exp > now:
                pass
            else:
                self.cookies.pop("ACCESSTOKEN")
                response = super().do_post(G.authentication_URL + "/refresh",
                                           json_data={"refreshToken": self.session_info['refreshToken'],
                                                      "username": username})
                if not self.__status_code_ok(response):
                    raise RuntimeError("status code <> 200 during authentication")
                Path(self.pluginpath(G.SESSION_INFO)).write_text(json.dumps(response.json()))
            self.session_info = self.get_session_info()

        profile_id = self.get_customer_info()["profiles"][0]["profileId"]
        tracking_id = self.get_customer_info()["hashedCustomerId"]
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
        Path(self.pluginpath(G.WIDEVINE_LICENSE) + '.raw').write_bytes(response.content)

    def obtain_streaming_token(self, channel):
        url = G.streaming_URL.format(householdid=self.session_info['householdId'])
        response = super().do_post(url,
                                   params={
                                       'channelId': channel['id']
                                       , 'assetType': 'Orion-DASH'
                                       , 'profileId': self.customer_info['profiles'][0]['profileId']
                                       , 'liveContentTimestamp': datetime.datetime.now(timezone.utc).isoformat()
                                   },
                                   extra_headers=self.extra_headers)
        if not self.__status_code_ok(response):
            raise RuntimeError("status code <> 200 during obtain streaming info")
        self.stream_info = json.loads(response.content)
        self.streaming_token = response.headers["x-streaming-token"]
        return response.headers["x-streaming-token"]

    def get_license(self, content_id, request_data, license_headers):
        url = G.license_URL
        license_headers.update({'x-streaming-token': self.streaming_token})
        for key in license_headers:
            if key in G.ALLOWED_LICENSE_HEADERS:
                pass
            else:
                print("HEADER DROPPPED: {0}:{1}".format(key, license_headers[key]))
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
        profile_id = self.get_customer_info()["profiles"][0]["profileId"]
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
        profile_id = self.get_customer_info()["profiles"][0]["profileId"]
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
