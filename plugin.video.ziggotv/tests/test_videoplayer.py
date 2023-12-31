import json
import os
import unittest

import xbmcaddon

from resources.lib.UrlTools import UrlTools
from resources.lib.ZiggoPlayer import VideoHelpers
from resources.lib.globals import G
from resources.lib.webcalls import LoginSession
from tests.test_base import TestBase


class TestVideoPlayer(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_login()

    #        self.cleanup_all()
    #        self.session = LoginSession(xbmcaddon.Addon())
    #        self.session.print_network_traffic = 'false'
    #        self.do_login()

    def test_widevine_license(self):
        self.session.refresh_widevine_license()

    def test_buildurl(self):
        urlHelper = UrlTools(self.addon)
        helpers = VideoHelpers(self.addon)
        self.session.refresh_widevine_license()

        # Test for play channels

        url = 'http://wp-obc1-live-nl-prod.prod.cdn.dmdsdp.com/dash/go-dash-hdready-avc/NL_000001_019401/manifest.mpd'
        expected_url = ('http://127.0.0.1:6868/manifest?'
                        'path=%2Fdash%2Fgo-dash-hdready-avc%2FNL_000001_019401%2Fmanifest.mpd&'
                        'token=0123456789ABCDEF&'
                        'hostname=wp-obc1-live-nl-prod.prod.cdn.dmdsdp.com')
        expected_manifest_url = ('https://wp-obc1-live-nl-prod.prod.cdn.dmdsdp.com/dash,'
                                 'vxttoken=0123456789ABCDEF/go-dash-hdready-avc'
                                 '/NL_000001_019401/manifest.mpd')
        redirected_url = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/dash,'
            'vxttoken=0123456789ABCDEF/go-dash-hdready-avc/NL_000001_019401/manifest.mpd')
        created_url = urlHelper.build_url('0123456789ABCDEF', url)
        self.assertEqual(created_url, expected_url, 'URL not as expected')
        s = created_url.find('/manifest')
        manifest_url = urlHelper.get_manifest_url(created_url[s:], '0123456789ABCDEF')
        self.assertEqual(manifest_url, expected_manifest_url, 'URL not as expected')
        print(manifest_url)
        urlHelper.update_redirection(created_url[s:], redirected_url)
        manifest_url = urlHelper.get_manifest_url(created_url[s:], '0123456789ABCDEF')
        self.assertEqual(manifest_url, redirected_url, 'URL not as expected')
        video_url = (
            '/private1/Header.m4s')
        expected_video_url = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/dash,'
            'vxttoken=0123456789ABCDEF/go-dash-hdready-avc/NL_000001_019401/private1/Header.m4s')
        baseurl = urlHelper.replace_baseurl(video_url, '0123456789ABCDEF')
        self.assertEqual(expected_video_url, baseurl, 'URL not as expected')

        li = helpers.listitem_from_url(url, '0123456789ABCDEF', 'content')

        # Tests for replay

        url = ('http://wp-pod3-replay-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash/LIVE$NL_000001_019401/index.mpd'
               '/Manifest?device=AVC-OTT-DASH-PR-WV&start=2023-12-15T14%3A16%3A00Z&end=2023-12-15T14%3A51%3A00Z')
        expected_url = ('http://127.0.0.1:6868/manifest?path=%2Fsdash%2FLIVE%24NL_000001_019401%2Findex.mpd%2FManifest'
                        '&token=0123456789ABCDEF&hostname=wp-pod3-replay-vxtoken-nl-prod.prod.cdn.dmdsdp.com&device'
                        '=AVC-OTT-DASH-PR-WV&start=2023-12-15T14%3A16%3A00Z&end=2023-12-15T14%3A51%3A00Z')
        expected_manifest_url = (
            'https://wp-pod3-replay-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash,'
            'vxttoken=0123456789ABCDEF/LIVE$NL_000001_019401/index.mpd'
            '/Manifest?device=AVC-OTT-DASH-PR-WV&start=2023-12-15T14%3A16%3A00Z&end=2023-12-15T14%3A51%3A00Z')
        redirected_url = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/wp/wp-pod3-replay-vxtoken-nl'
            '-prod.prod.cdn.dmdsdp.com/sdash,vxttoken=0123456789ABCDEF/LIVE$NL_000001_019401/index.mpd/Manifest'
        )
        created_url = urlHelper.build_url('0123456789ABCDEF', url)
        self.assertEqual(created_url, expected_url, 'URL not as expected')
        s = created_url.find('/manifest')
        manifest_url = urlHelper.get_manifest_url(created_url[s:], '0123456789ABCDEF')
        self.assertEqual(manifest_url, expected_manifest_url, 'URL not as expected')
        print(manifest_url)
        # Now update redirection and then create the manifest URL again. it should be identical to the redirected URL
        urlHelper.update_redirection(created_url[s:], redirected_url)
        manifest_url = urlHelper.get_manifest_url(created_url[s:], '0123456789ABCDEF')
        self.assertEqual(manifest_url, redirected_url, 'URL not as expected')

        li = helpers.listitem_from_url(url, '0123456789ABCDEF', 'content')

        video_url = (
            '/S!d2ESQVZDLU9UVC1EQVNILVBSLVdWEgJDeAz7ykSIKfvKFgSf/QualityLevels(128000,'
            'Level_params=dxADIeIBnw..)/Fragments(audio_482_dut=Init)')
        expected_video_url = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/'
            'wp/wp-pod3-replay-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash,'
            'vxttoken=0123456789ABCDEF/LIVE$NL_000001_019401/index.mpd/S'
            '!d2ESQVZDLU9UVC1EQVNILVBSLVdWEgJDeAz7ykSIKfvKFgSf/QualityLevels(128000,'
            'Level_params=dxADIeIBnw..)/Fragments(audio_482_dut=Init)')
        baseurl = urlHelper.replace_baseurl(video_url, '0123456789ABCDEF')
        self.assertEqual(expected_video_url, baseurl, 'URL not as expected')

        # Test for video-on-demand urls

        url = (
            'https://wp-pod1-vod-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash'
            '/0e378a707155514f39851ab1e45b6560_734142457f0da3caf957ba97e73249e6/index.mpd/Manifest?device=BR-AVC-DASH')
        expected_url = ('http://127.0.0.1:6868/manifest?path=%2Fsdash'
                        '%2F0e378a707155514f39851ab1e45b6560_734142457f0da3caf957ba97e73249e6%2Findex.mpd%2FManifest'
                        '&token=0123456789ABCDEF&hostname=wp-pod1-vod-vxtoken-nl-prod.prod.cdn.dmdsdp.com&device=BR'
                        '-AVC-DASH')
        expected_manifest_url = (
            'https://wp-pod1-vod-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash,'
            'vxttoken=0123456789ABCDEF/0e378a707155514f39851ab1e45b6560_734142457f0da3caf957ba97e73249e6/index.mpd'
            '/Manifest?device=BR-AVC-DASH')
        redirected_url = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/wp/wp-pod3-replay-vxtoken-nl'
            '-prod.prod.cdn.dmdsdp.com/sdash,vxttoken=0123456789ABCDEF/LIVE$NL_000001_019401/index.mpd/Manifest'
        )
        created_url = urlHelper.build_url('0123456789ABCDEF', url)
        self.assertEqual(created_url, expected_url, 'URL not as expected')
        s = created_url.find('/manifest')
        manifest_url = urlHelper.get_manifest_url(created_url[s:], '0123456789ABCDEF')
        self.assertEqual(manifest_url, expected_manifest_url, 'URL not as expected')
        print(manifest_url)
        # Now update redirection and then create the manifest URL again. it should be identical to the redirected URL
        urlHelper.update_redirection(created_url[s:], redirected_url)
        manifest_url = urlHelper.get_manifest_url(created_url[s:], '0123456789ABCDEF')
        self.assertEqual(manifest_url, redirected_url, 'URL not as expected')

        li = helpers.listitem_from_url(url, '0123456789ABCDEF', 'content')


if __name__ == '__main__':
    unittest.main()
