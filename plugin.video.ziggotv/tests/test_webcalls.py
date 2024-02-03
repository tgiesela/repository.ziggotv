import datetime
import json
import unittest
import urllib.parse
import uuid
from collections import namedtuple
from urllib.parse import urlparse

import requests
import xbmcaddon

from resources.lib.urltools import UrlTools
from resources.lib.webcalls import LoginSession, WebException
from tests.test_base import TestBase


class TestWebCalls(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_login()

    def test_login(self):
        self.cleanup_all()
        self.session = LoginSession(self.addon)
        try:
            self.session.login('baduser', 'badpassword')
        except WebException as exc:
            print(exc.get_response())
            print(exc.get_status())
        self.do_login()
        cookies = self.session.load_cookies()
        cookies_dict = requests.utils.dict_from_cookiejar(cookies)
        if 'ACCESSTOKEN' in cookies_dict and 'CLAIMSTOKEN' in cookies_dict:
            pass
        else:
            self.fail('Expected cookies not found')
        self.session.dump_cookies()
        self.session.sessionInfo['accessToken'] = \
            ('eyJ0eXAiOiJKV1QiLCJraWQiOiJvZXNwX3Rva2VuX3Byb2RfMjAyMDA4MTkiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3ZWItYXBpLXBy'
             'b2Qtb2JvLmhvcml6b24udHYiLCJzaWQiOiJlYzYxNDE5NWE0NjdkNWM5ZGZkM2Q0MGQ2MzVmYTdhZjA4NmU4MzEzZDZhOGUyODQ5NDQ3Z'
             'Dk3ZTg4NGIzMzkzIiwiaWF0IjoxNzA1NzM2Mjc0LCJleHAiOjE3MDU3NDM0NzQsInN1YiI6Ijg2NTQ4MDdfbmwifQ.SAD1RuDYX60_tq7'
             'Zt0v-Zh3iKKS2hU6nv34-zAEKl2w')
        self.do_login()
        self.session.cookies.pop('ACCESSTOKEN')
        self.session.sessionInfo['accessToken'] = \
            ('eyJ0eXAiOiJKV1QiLCJraWQiOiJvZXNwX3Rva2VuX3Byb2RfMjAyMDA4MTkiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3ZWItYXBpLXBy'
             'b2Qtb2JvLmhvcml6b24udHYiLCJzaWQiOiJlYzYxNDE5NWE0NjdkNWM5ZGZkM2Q0MGQ2MzVmYTdhZjA4NmU4MzEzZDZhOGUyODQ5NDQ3Z'
             'Dk3ZTg4NGIzMzkzIiwiaWF0IjoxNzA1NzM2Mjc0LCJleHAiOjE3MDU3NDM0NzQsInN1YiI6Ijg2NTQ4MDdfbmwifQ.SAD1RuDYX60_tq7'
             'Zt0v-Zh3iKKS2hU6nv34-zAEKl2w')
        self.do_login()

    def test_channels(self):
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
        entitlements = self.session.get_entitlements()
        self.assertDictEqual({}, entitlements)
        entitlements = self.session.refresh_entitlements()
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
        hw_uuid = str(uuid.UUID(hex=hex(uuid.getnode())[2:]*2+'00000000'))
        headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
            'Host': 'prod.spark.ziggogo.tv',
            'x-streaming-token': streamInfo.token,
            'X-cus': self.session.customerInfo['customerId'],
            'x-go-dev': hw_uuid,  # '214572a3-2033-4327-b8b3-01a9a674f1e0',
            'x-drm-schemeId': 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
            'deviceName': 'Firefox'
        })

        response = self.session.get_license('nl_tv_standaard_cenc', '\x08\x04', headers)
        updated_streaming_token = response.headers['x-streaming-token']
        self.assertFalse(updated_streaming_token == streamInfo.token)
        self.session.obtain_customer_info()
        new_streaming_token = self.session.update_token(updated_streaming_token)
        self.assertFalse(new_streaming_token == streamInfo.token)
        self.session.delete_token(new_streaming_token)

    def baseURL_from_manifest(self, manifest):
        from xml.dom import minidom
        document = minidom.parseString(manifest)
        for parent in document.getElementsByTagName('MPD'):
            periods = parent.getElementsByTagName('Period')
            for period in periods:
                baseURL = period.getElementsByTagName('BaseURL')
                if baseURL.length == 0:
                    return None
                else:
                    return baseURL[0].childNodes[0].data
        return None

    def test_manifest(self):
        tools = UrlTools(self.addon)
        self.do_login()
        self.session.refresh_channels()
        self.session.printNetworkTraffic = True
        channels = self.session.get_channels()
        channel = channels[0]  # Simply use the first channel
        locator, asset_type = channel.get_locator(self.addon)
        tkn = self.session.obtain_tv_streaming_token(channel.id, asset_type)
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
        baseURL = self.baseURL_from_manifest(response.content)
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
        locator, asset_type = channel.get_locator(self.addon)
        tkn = self.session.obtain_tv_streaming_token(channel.id, asset_type)
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

        baseURL = self.baseURL_from_manifest(response.content)
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
                print(item['title'], item['id'])
                if item['type'] == 'MostWatchedChannels':
                    mostwatched = json.loads(self.session.get_mostwatched_channels())
                    print('Mostwatched: ', mostwatched)
                # if item['type'] in ['CombinedCollection', 'RecommendedForYou']:
                else:
                    requestcolls.append(item['id'])
                    home_coll = json.loads(self.session.obtain_home_collection(requestcolls))
                    # print(home_coll)
                    for collection in home_coll['collections']:
                        print('\tCollection: ' + collection['title'])
                        if 'subcollections' in collection:
                            for subcoll in collection['subcollections']:
                                print('\t\tSubcollection: ' + subcoll['title'], 'type: ', subcoll['type'])
                        if 'items' in collection:
                            for item in collection['items']:
                                if 'entitlementState' in item:
                                    if item['entitlementState'].lower() == 'entitled':
                                        entitled = True
                                    else:
                                        entitled = False
                                else:
                                    entitled = False
                                print('\t\tItem: ', item['title'], ',', item['type'], ', entitlementState: ', entitled)
                                if 'brandingProviderId' in item:
                                    print('\t\t      Branding-provider', item['brandingProviderId'])
                                episoderesponse, asset = self.session.get_episode(item)
                                print("Episo-resp:", episoderesponse)
                                print("Asset-resp:", asset)
                                if asset != '':
                                    asset_json = json.loads(asset)
                                    print("CHANNEL=", asset_json['channelId'])
                                    print("STARTTIME:", datetime.datetime.fromtimestamp(asset_json['startTime']))
                                    print("ENDTIME:", datetime.datetime.fromtimestamp(asset_json['endTime']))

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
                screen_details = self.session.obtain_vod_screen_details(screen['id'])
                for collection in screen_details['collections']:
                    if collection['collectionLayout'] == 'BasicCollection':
                        print('\t{0}, type: {1}'.format(collection['title'], collection['contentType']))
                    else:
                        print('\t{0}, type: {1}'.format(collection['collectionLayout'], collection['contentType']))
                    for item in collection['items']:
                        if item['type'] == 'LINK':
                            try:
                                grid = self.session.obtain_grid_screen_details(item['gridLink']['id'])
                                print(
                                    '\t\t{0}:{2}'.format(item['type'], item['gridLink']['type'],
                                                         item['gridLink']['title']))
                            except Exception as exc:
                                print(
                                    '\t\tFAILED: {0}:{2}'.format(item['type'], item['gridLink']['type'],
                                                                 item['gridLink']['title']))
                        else:
                            print('\t\t{0}-{1}:{2}'.format(item['type'], item['assetType'], item['title']))
                            if item['type'] == 'SERIES':
                                overview = self.session.obtain_series_overview(item['id'])
                                print('\t\t{0}'.format(','.join(overview['genres'])))
                                print('\t\t{0}'.format(overview['synopsis']))
                                episodes = self.session.get_episode_list(item['id'])
                                for season in episodes['seasons']:
                                    print('\t\t\tSeizoen {0}, afl: {1}'.format(
                                        season['season']
                                        , season['totalEpisodes']))
                                    for episode in season['episodes']:
                                        if 'entitlementState' in episode['source']:
                                            if episode['source']['entitlementState'].lower() == 'entitled':
                                                entitled = True
                                            else:
                                                entitled = False
                                        else:
                                            entitled = False
                                        if 'type' in episode['source']:
                                            episode_type = episode['source']['type']
                                        else:
                                            episode_type = '?'
                                        title = episode['title'] if 'title' in episode else '?'
                                        print('\t\t\tAfl {0}, afl: {1} source {2} entitled {3} type {4}'.format(
                                            episode['episode']
                                            , title, episode['source']['titleId']
                                            , entitled
                                            , episode_type))
                                        details = self.session.obtain_asset_details(episode['id'])
                                        if 'instances' in details:
                                            print('\t\t\tInstances found')
                                        else:
                                            print('\t\t\t{0}Instances NOT found, entitled: {1}'.format(title,
                                                                                                       entitled))
                                        # details2 = self.session.obtain_asset_details(episode['source']['eventId'])
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
            break # We only test one profile !
            # print(response)


if __name__ == '__main__':
    unittest.main()
