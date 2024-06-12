# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
import base64
import datetime
import json
import unittest
import uuid
from http.cookiejar import Cookie

from xml.dom import minidom

import requests
import xbmcaddon

from resources.lib.globals import G
from resources.lib.urltools import UrlTools
from resources.lib.utils import WebException, DatetimeHelper
from resources.lib.webcalls import LoginSession
from tests.test_base import TestBase


class TestWebCalls(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_login()

    def __check_cookies(self):
        cookies = self.session.load_cookies()
        cookiesDict = requests.utils.dict_from_cookiejar(cookies)
        if 'ACCESSTOKEN' in cookiesDict and 'CLAIMSTOKEN' in cookiesDict:
            pass
        else:
            self.fail('Expected cookies not found')

    def test_login(self):
        self.cleanup_all()
        self.session = LoginSession(self.addon)
        try:
            self.session.login('baduser', 'badpassword')
        except WebException as exc:
            print(exc.response)
            print(exc.status)
        self.do_login()
        self.__check_cookies()
        self.session.dump_cookies()
        # Test expired accesstoken in sessionInfo
        self.session.sessionInfo['accessToken'] = \
            ('eyJ0eXAiOiJKV1QiLCJraWQiOiJvZXNwX3Rva2VuX3Byb2RfMjAyMDA4MTkiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3ZWItYXBpLXBy'
             'b2Qtb2JvLmhvcml6b24udHYiLCJzaWQiOiJlYzYxNDE5NWE0NjdkNWM5ZGZkM2Q0MGQ2MzVmYTdhZjA4NmU4MzEzZDZhOGUyODQ5NDQ3Z'
             'Dk3ZTg4NGIzMzkzIiwiaWF0IjoxNzA1NzM2Mjc0LCJleHAiOjE3MDU3NDM0NzQsInN1YiI6Ijg2NTQ4MDdfbmwifQ.SAD1RuDYX60_tq7'
             'Zt0v-Zh3iKKS2hU6nv34-zAEKl2w')
        self.do_login()
        self.__check_cookies()
        # Test without ACCESSTOKEN cookie
        for _cookie in self.session.cookies:
            c: Cookie = _cookie
            if c.name == 'ACCESSTOKEN':
                self.session.cookies.clear(domain=c.domain, path=c.path, name=c.name)
        self.session.sessionInfo['accessToken'] = \
            ('eyJ0eXAiOiJKV1QiLCJraWQiOiJvZXNwX3Rva2VuX3Byb2RfMjAyMDA4MTkiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3ZWItYXBpLXBy'
             'b2Qtb2JvLmhvcml6b24udHYiLCJzaWQiOiJlYzYxNDE5NWE0NjdkNWM5ZGZkM2Q0MGQ2MzVmYTdhZjA4NmU4MzEzZDZhOGUyODQ5NDQ3Z'
             'Dk3ZTg4NGIzMzkzIiwiaWF0IjoxNzA1NzM2Mjc0LCJleHAiOjE3MDU3NDM0NzQsInN1YiI6Ijg2NTQ4MDdfbmwifQ.SAD1RuDYX60_tq7'
             'Zt0v-Zh3iKKS2hU6nv34-zAEKl2w')
        self.do_login()
        self.__check_cookies()
        # Test with expired accessToken
        accessToken = self.session.sessionInfo['accessToken']
        parts = accessToken.split('.')
        jsondata = json.loads(base64.b64decode(parts[1]+'=='))
        jsondata['exp'] = DatetimeHelper.unix_datetime(DatetimeHelper.now() - datetime.timedelta(hours=2))
        parts[1] = base64.b64encode(bytes(json.dumps(jsondata), 'ascii')).decode('ascii')[:-2]
        accessToken = '.'.join(parts)
        self.session.sessionInfo['accessToken'] = accessToken
        self.do_login()
        self.__check_cookies()
        self.do_login()
        self.__check_cookies()

    def test_channels(self):
        self.do_login()
        self.cleanup_channels()
        channels = self.session.get_channels()
        self.assertEqual(0, len(channels))
        self.session.refresh_channels()
        channels = self.session.get_channels()
        self.assertNotEqual(len(channels), 0)

    def test_entitlements(self):
        self.cleanup_all()
        self.session = LoginSession(xbmcaddon.Addon())
        self.session.printNetworkTraffic = 'false'
        self.do_login()
        self.session.refresh_entitlements()
        entitlements = self.session.get_entitlements()
        self.assertFalse(entitlements == {})

    def test_widevine_license(self):
        self.session.refresh_widevine_license()

    def test_tokens(self):
        self.do_login()
        self.session.refresh_channels()
        channels = self.session.get_channels()
        channel = channels[0]  # Simply use the first channel
        streamInfo = self.session.obtain_tv_streaming_token(channel.id, assetType='Orion-DASH')
        self.session.streamingToken = streamInfo.token
        headers = {}
        hwUuid = str(uuid.UUID(hex=hex(uuid.getnode())[2:]*2+'00000000'))
        headers.update({
            'Host': G.ZIGGO_HOST,
            'x-streaming-token': streamInfo.token,
            'X-cus': self.session.customerInfo['customerId'],
            'x-go-dev': hwUuid,
            'x-drm-schemeId': 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
            'deviceName': 'Firefox',
#            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
        })

        response = self.session.get_license('nl_tv_standaard_cenc', '\x08\x04', headers)
        updatedStreamingToken = response.headers['x-streaming-token']
        self.assertFalse(updatedStreamingToken == streamInfo.token)
        # self.session.obtain_customer_info()
        newStreamingToken = self.session.update_token(updatedStreamingToken)
        self.assertFalse(newStreamingToken == streamInfo.token)
        self.session.delete_token(newStreamingToken)

    def baseurl_from_manifest(self, manifest):
        document = minidom.parseString(manifest)
        for parent in document.getElementsByTagName('MPD'):
            periods = parent.getElementsByTagName('Period')
            for period in periods:
                baseURL = period.getElementsByTagName('BaseURL')
                if baseURL.length == 0:
                    return None
                return baseURL[0].childNodes[0].data
        return None

    def test_manifest(self):
        tools = UrlTools(self.addon)
        self.do_login()
        self.session.refresh_channels()
        self.session.printNetworkTraffic = True
        channels = self.session.get_channels()
        channel = channels[0]  # Simply use the first channel
        locator, assetType = channel.get_locator(self.addon)
        tkn = self.session.obtain_tv_streaming_token(channel.id, assetType)
        locator = channel.locators['Default'].replace('http://', 'https://')
        if '/dash' in locator:
            locator = locator.replace("/dash", "/dash,vxttoken=" + tkn.token).replace("http://", "https://")
        elif 'sdash' in locator:
            locator = locator.replace("/sdash", "/sdash,vxttoken=" + tkn.token).replace("http://", "https://")
        elif '/live' in locator:
            locator = locator.replace("/live", "/live,vxttoken=" + tkn.token).replace("http://", "https://")
        response = self.session.get_manifest(locator)
        self.session.delete_token(tkn.token)
        mpd = str(response.content, 'utf-8')
        self.assertFalse(mpd == '')
        self.assertTrue(mpd.find('<MPD') > 0)
        baseURL = self.baseurl_from_manifest(response.content)
        if baseURL is None:
            print('BaseURL not found')
        tools.update_redirection(locator, 'https://da-d436304520010b88000108000000000000000005.id.cdn.upcbroadband'
                                          '.com/wp/wp4-vxtoken-anp-g05060506-hzn-nl.t1.prd.dyncdn.dmdsdp.com/live,'
                                          'vxttoken'
                                          '=YXNzVHlwPU9yaW9uLURBU0gmYy1pcC11bmxvY2tlZD0xJmNvbklkPU5MXzAwMDAxMV8wMTk1Nj'
                                          'MmY29uVHlwZT00JmN1c0lkPTg2NTQ4MDdfbmwmZGV2RmFtPXdlYi1kZXNrdG9wJmRyPTAmZHJtQ'
                                          '29uSWQ9bmxfdHZfc3RhbmRhYXJkX2NlbmMmZHJtRGV2SWQ9YTZjOTBlZTZjMGYxYzczMjEyNTAy'
                                          'Yjc2ODA0ZTc2MGQ2MTQwY2ZlMmNhYzZiNDQ4MjI5MGNhZWZlNTQ0MDc3OCZleHBpcnk9MTcwNjI'
                                          '2ODA3NCZmbj1zaGEyNTYmcGF0aFVSST0lMkZsaXZlJTJGZGlzazElMkZOTF8wMDAwMTFfMDE5NT'
                                          'YzJTJGZ28tZGFzaC1oZHJlYWR5LWF2YyUyRiUyQSZwcm9maWxlPTA5OGFjYzBmLTFlNGItNDNhZ'
                                          'i04ODk3LWI2ZWJkOGVhNWRjYiZyZXVzZT0tMSZzTGltPTMmc2VzSWQ9LTFJa0pSNVJpTUR2M3lG'
                                          'dGRCcVVLM29TYmkyV2o2STlKUEZ6JnNlc1RpbWU9MTcwNjI2NzkyMyZzdHJMaW09Myw4NWYxZjU'
                                          '1OTY0NTQxYTlhNGJhYTQyODhhYjFlNzI3YzU1Y2Q1MzAyNWUxYmRjZmQ2N2UzMjg5NGVjYTg3Nz'
                                          'A4/disk1/NL_000011_019563/go-dash-hdready-avc/NL_000011_019563.mpd', baseURL)
        print('REDIRECTED URL: {0}'.format(tools.redirectedUrl))

        for c in channels:
            if c.name == 'STAR Channel':
                channel = c
                break
        locator, assetType = channel.get_locator(self.addon)
        tkn = self.session.obtain_tv_streaming_token(channel.id, assetType)
        locator = channel.locators['Default'].replace('http://', 'https://')
        if '/dash' in locator:
            locator = locator.replace("/dash", "/dash,vxttoken=" + tkn.token).replace("http://", "https://")
        elif 'sdash' in locator:
            locator = locator.replace("/sdash", "/sdash,vxttoken=" + tkn.token).replace("http://", "https://")
        elif '/live' in locator:
            locator = locator.replace("/live", "/live,vxttoken=" + tkn.token).replace("http://", "https://")
        response = self.session.get_manifest(locator)
        self.session.delete_token(tkn.token)
        mpd = str(response.content, 'utf-8')
        self.assertFalse(mpd == '')
        self.assertTrue(mpd.find('<MPD') > 0)

        baseURL = self.baseurl_from_manifest(response.content)
        if baseURL is None:
            print('BaseURL not found')
            return
        tools.update_redirection(locator, 'https://da-d436304520010b88000108000000000000000005.id.cdn.upcbroadband'
                                          '.com/wp/wp4-vxtoken-anp-g05060506-hzn-nl.t1.prd.dyncdn.dmdsdp.com/live,'
                                          'vxttoken'
                                          '=YXNzVHlwPU9yaW9uLURBU0gmYy1pcC11bmxvY2tlZD0xJmNvbklkPU5MXzAwMDAxMV8wMTk1Nj'
                                          'MmY29uVHlwZT00JmN1c0lkPTg2NTQ4MDdfbmwmZGV2RmFtPXdlYi1kZXNrdG9wJmRyPTAmZHJtQ'
                                          '29uSWQ9bmxfdHZfc3RhbmRhYXJkX2NlbmMmZHJtRGV2SWQ9YTZjOTBlZTZjMGYxYzczMjEyNTAy'
                                          'Yjc2ODA0ZTc2MGQ2MTQwY2ZlMmNhYzZiNDQ4MjI5MGNhZWZlNTQ0MDc3OCZleHBpcnk9MTcwNjI'
                                          '2ODA3NCZmbj1zaGEyNTYmcGF0aFVSST0lMkZsaXZlJTJGZGlzazElMkZOTF8wMDAwMTFfMDE5NT'
                                          'YzJTJGZ28tZGFzaC1oZHJlYWR5LWF2YyUyRiUyQSZwcm9maWxlPTA5OGFjYzBmLTFlNGItNDNhZ'
                                          'i04ODk3LWI2ZWJkOGVhNWRjYiZyZXVzZT0tMSZzTGltPTMmc2VzSWQ9LTFJa0pSNVJpTUR2M3lG'
                                          'dGRCcVVLM29TYmkyV2o2STlKUEZ6JnNlc1RpbWU9MTcwNjI2NzkyMyZzdHJMaW09Myw4NWYxZjU'
                                          '1OTY0NTQxYTlhNGJhYTQyODhhYjFlNzI3YzU1Y2Q1MzAyNWUxYmRjZmQ2N2UzMjg5NGVjYTg3Nz'
                                          'A4/disk1/NL_000011_019563/go-dash-hdready-avc/NL_000011_019563.mpd', baseURL)
        print('REDIRECTED URL: {0}'.format(tools.redirectedUrl))

    def test_voor_jou(self):
        self.do_login()
        profiles = self.session.get_profiles()
        for profile in profiles:
            print('Profile: {0}\n'.format(profile['name']))
            self.session.set_active_profile(profile)
            response = self.session.obtain_structure()
            response = json.loads(response)
            requestcolls = []
            for item in response:
                print(item['id'], item['type'])
                if item['type'] == 'MostWatchedChannels':
                    mostwatched = json.loads(self.session.get_mostwatched_channels())
                    print('Mostwatched: ', mostwatched)
                # if item['type'] in ['CombinedCollection', 'RecommendedForYou']:
                else:
                    requestcolls.append(item['id'])
                    homeColl = json.loads(self.session.obtain_home_collection(requestcolls))
                    # print(homeColl)
                    for collection in homeColl['collections']:
                        self.process_collection_voor_jou(collection)

    def test_movies_and_series(self):
        self.do_login()
        profiles = self.session.get_profiles()
        for profile in profiles:
            print('Profile: {0}\n'.format(profile['name']))
            self.session.set_active_profile(profile)
            response = self.session.obtain_vod_screens()
            combinedlist = response['screens']
            combinedlist.append(response['hotlinks']['adultRentScreen'])
            for screen in combinedlist:
                print('Screen: ' + screen['title'], 'id: ', screen['id'])
                screenDetails = self.session.obtain_vod_screen_details(screen['id'])
                if 'collections' in screenDetails:
                    for collection in screenDetails['collections']:
                        self.process_collection_movies(collection)
            break # We only test one profile !
            # print(response)

    def process_collection_voor_jou(self, collection):
        print('\tCollection: ' + collection['title'])
        if 'subcollections' in collection:
            for subcoll in collection['subcollections']:
                print('\t\tSubcollection: ' + subcoll['title'], 'type: ', subcoll['type'])
        if 'items' in collection:
            for item in collection['items']:
                if 'entitlementState' in item:
                    entitled = item['entitlementState'].lower() == 'entitled'
                else:
                    entitled = False
                print('\t\tItem: ', item['title'], ',', item['type'], ', entitlementState: ', entitled)
                if 'brandingProviderId' in item:
                    print('\t\t      Branding-provider', item['brandingProviderId'])
                episoderesponse, asset = self.session.get_episode(item)
                print("Episo-resp:", episoderesponse)
                print("Asset-resp:", asset)
                if asset != '':
                    assetJson = json.loads(asset)
                    print("CHANNEL=", assetJson['channelId'])
                    print("STARTTIME:", datetime.datetime.fromtimestamp(assetJson['startTime']))
                    print("ENDTIME:", datetime.datetime.fromtimestamp(assetJson['endTime']))

    def process_collection_movies(self, collection):
        # pylint: disable=too-many-branches
        if collection['collectionLayout'] == 'BasicCollection':
            print('\t{0}, type: {1}'.format(collection['title'], collection['contentType']))
        else:
            print('\t{0}, type: {1}'.format(collection['collectionLayout'], collection['contentType']))
        for item in collection['items']:
            if item['type'] == 'LINK':
                try:
                    _ = self.session.obtain_grid_screen_details(item['gridLink']['id'])
                    print('\t\t{0}:{1}'.format(item['type'], item['gridLink']['title']))
                # pylint: disable=broad-exception-caught
                except Exception:
                    print(
                        '\t\tFAILED: {0}:{1}'.format(item['type'], item['gridLink']['title']))
            else:
                print('\t\t{0}-{1}:{2}'.format(item['type'], item['assetType'], item['title']))
                if item['type'] == 'SERIES':
                    overview = self.session.obtain_series_overview(item['id'])
                    print('\t\t{0}'.format(','.join(overview['genres'])))
                    print('\t\t{0}'.format(overview['synopsis']))
                    episodes = self.session.get_episode_list(item['id'])
                    for season in episodes['seasons']:
                        self.process_collection_movies_season(season)
                elif item['type'] == 'ASSET':
                    if 'brandingProviderId' in item:
                        overview = self.session.obtain_asset_details(item['id'], item['brandingProviderId'])
                    else:
                        overview = self.session.obtain_asset_details(item['id'])
                    if 'genres' in overview:
                        print('\t\t{0}'.format(','.join(overview['genres'])))
                    print('\t\t{0}'.format(overview['synopsis']))
                    print('\t\t\tinstances')
                    for instance in overview['instances']:
                        print('\t\t\t\t' + instance['id'])  # used to get streaming token
                        print('\t\t\t\tentitled {0}, price {1}'.format(
                            instance['offers'][0]['entitled']
                            , instance['offers'][0]['price']))

    def process_collection_movies_season(self, season):
        print('\t\t\tSeizoen {0}, afl: {1}'.format(
            season['season']
            , season['totalEpisodes']))
        for episode in season['episodes']:
            if 'entitlementState' in episode['source']:
                entitled = episode['source']['entitlementState'].lower() == 'entitled'
            else:
                entitled = False
            if 'type' in episode['source']:
                episodeType = episode['source']['type']
            else:
                episodeType = '?'
            title = episode['title'] if 'title' in episode else '?'
            print('\t\t\tAfl {0}, afl: {1} source {2} entitled {3} type {4}'.format(
                episode['episode']
                , title, episode['source']['titleId']
                , entitled
                , episodeType))
            details = self.session.obtain_asset_details(episode['id'])
            if 'instances' in details:
                print('\t\t\tInstances found')
            else:
                print('\t\t\t{0}Instances NOT found, entitled: {1}'.format(title,
                                                                           entitled))
            # details2 = self.session.obtain_asset_details(episode['source']['eventId'])


if __name__ == '__main__':
    unittest.main()
