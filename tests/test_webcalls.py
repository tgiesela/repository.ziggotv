import datetime
import json
import os
import unittest

import requests
import xbmcaddon

from resources.lib.webcalls import LoginSession
from resources.lib.globals import G


class TestWebcalls(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleanup_all()
        self.session = LoginSession(xbmcaddon.Addon())
        self.session.print_network_traffic = 'false'
        self.do_login()

    def remove(self, file):
        if os.path.exists(file):
            os.remove(file)

    def cleanup_cookies(self):
        self.remove(G.COOKIES_INFO)

    def cleanup_channels(self):
        self.remove(G.CHANNEL_INFO)

    def cleanup_customer(self):
        self.remove(G.CUSTOMER_INFO)

    def cleanup_session(self):
        self.remove(G.SESSION_INFO)

    def cleanup_entitlements(self):
        self.remove(G.ENTITLEMENTS_INFO)

    def cleanup_widevine(self):
        self.remove(G.WIDEVINE_LICENSE)
        self.remove(G.WIDEVINE_LICENSE + '.raw')

    def cleanup_all(self):
        self.cleanup_customer()
        self.cleanup_session()
        self.cleanup_channels()
        self.cleanup_cookies()
        self.cleanup_entitlements()
        self.cleanup_widevine()

    def setUp(self):
        print("Executing setup")

    def do_login(self):
        with open(f'c:/temp/credentials.json', 'r') as credfile:
            credentials = json.loads(credfile.read())
        self.session.login(credentials['username'], credentials['password'])

    def test_login(self):
        self.cleanup_all()
        try:
            self.session.login('baduser', 'badpassword')
        except Exception as exc:
            print(exc)
            pass
        self.do_login()
        cookies = self.session.load_cookies()
        cookies_dict = requests.utils.dict_from_cookiejar(cookies)
        if 'ACCESSTOKEN' in cookies_dict and 'CLAIMSTOKEN' in cookies_dict:
            pass
        else:
            self.fail('Expected cookies not found')
        self.session.dump_cookies()
        self.do_login()

    def test_channels(self):
        self.cleanup_channels()
        channels = self.session.get_channels()
        self.assertDictEqual({}, channels)
        channels = self.session.refresh_channels()
        self.assertFalse(channels == {})

    def test_entitlements(self):
        self.cleanup_all()
        self.session = LoginSession(xbmcaddon.Addon())
        self.session.print_network_traffic = 'false'
        self.do_login()
        entitlements = self.session.get_entitlements()
        self.assertDictEqual({}, entitlements)
        entitlements = self.session.refresh_entitlements()
        self.assertFalse(entitlements == {})

    def test_widevine_license(self):
        self.session.refresh_widevine_license()

    def test_tokens(self):
        self.session.refresh_channels()
        channels = self.session.get_channels()
        channel = channels[0]  # Simply use the first channel
        streaming_token = self.session.obtain_tv_streaming_token(channel)
        headers = {}
        headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
            'Host': 'prod.spark.ziggogo.tv',
            'x-streaming-token': streaming_token,
            'X-cus': self.session.customer_info['customerId'],
            'x-go-dev': '214572a3-2033-4327-b8b3-01a9a674f1e0',
            'x-drm-schemeId': 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
            'deviceName': 'Firefox'
        })

        response = self.session.get_license('nl_tv_standaard_cenc', '\x08\x04', headers)
        updated_streaming_token = response.headers['x-streaming-token']
        self.assertFalse(updated_streaming_token == streaming_token)
        new_streaming_token = self.session.update_token(updated_streaming_token)
        self.assertFalse(new_streaming_token == streaming_token)
        self.session.delete_token(new_streaming_token)

    def test_manifest(self):
        self.session.refresh_channels()
        channels = self.session.get_channels()
        channel = channels[0]  # Simply use the first channel
        response = self.session.get_manifest(channel['locator'])
        mpd = str(response.content, 'utf-8')
        self.assertFalse(mpd == '')
        self.assertTrue(mpd.find('<MPD') > 0)

    def test_voor_jou(self):
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
        profiles = self.session.get_profiles()
        for profile in profiles:
            print('Profile: {0}\n'.format(profile['name']))
            self.session.set_active_profile(profile)
            response = self.session.obtain_vod_screens()
            for screen in response['screens']:
                print('Screen: ' + screen['title'], 'id: ', screen['id'])
                screen_details = self.session.obtain_vod_screen_details(screen['id'])
                for collection in screen_details['collections']:
                    if collection['collectionLayout'] == 'BasicCollection':
                        print('\t{0}, type: {1}'.format(collection['title'], collection['contentType']))
                    else:
                        print('\t{0}, type: {1}'.format(collection['collectionLayout'], collection['contentType']))
                    for item in collection['items']:
                        if item['type'] == 'LINK':
                            print(
                                '\t\t{0}:{2}'.format(item['type'], item['gridLink']['type'], item['gridLink']['title']))
                        else:
                            print('\t\t{0}-{1}:{2}'.format(item['type'], item['assetType'], item['title']))
                            if item['type'] == 'SERIES':
                                overview = self.session.obtain_vod_screen_overview(item['id'])
                                print('\t\t{0}'.format(','.join(overview['genres'])))
                                print('\t\t{0}'.format(overview['synopsis']))
                                episodes = self.session.get_episode_list(item)
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
                                        print('\t\t\tAfl {0}, afl: {1} source {2} entitled {3} type {4}'.format(
                                            episode['episode']
                                            , episode['title'], episode['source']['titleId']
                                            , entitled
                                            , episode_type))

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

            # print(response)


if __name__ == '__main__':
    unittest.main()
