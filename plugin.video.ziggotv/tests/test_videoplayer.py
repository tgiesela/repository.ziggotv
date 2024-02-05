# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
import unittest
from urllib.parse import unquote

from resources.lib.listitemhelper import ListitemHelper
from resources.lib.urltools import UrlTools
from tests.test_base import TestBase


class TestVideoPlayer(TestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_login()
        self.session.refresh_entitlements()

    #        self.cleanup_all()
    #        self.session = LoginSession(xbmcaddon.Addon())
    #        self.session.print_network_traffic = 'false'
    #        self.do_login()

    def test_widevine_license(self):
        self.session.refresh_widevine_license()

    def test_buildurl(self):
        # pylint: disable=too-many-statements
        urlHelper = UrlTools(self.addon)
        helpers = ListitemHelper(self.addon)
        self.session.refresh_widevine_license()

        # Test for play channels

        url = 'http://wp-obc1-live-nl-prod.prod.cdn.dmdsdp.com/dash/go-dash-hdready-avc/NL_000001_019401/manifest.mpd'
        expectedUrl = ('http://127.0.0.1:6868/manifest?'
                       'path=%2Fdash%2Fgo-dash-hdready-avc%2FNL_000001_019401%2Fmanifest.mpd&'
                       'token=0123456789ABCDEF&'
                       'hostname=wp-obc1-live-nl-prod.prod.cdn.dmdsdp.com')
        expectedManifestUrl = ('https://wp-obc1-live-nl-prod.prod.cdn.dmdsdp.com/dash,'
                               'vxttoken=0123456789ABCDEF/go-dash-hdready-avc'
                               '/NL_000001_019401/manifest.mpd')
        redirectedUrl = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/dash,'
            'vxttoken=0123456789ABCDEF/go-dash-hdready-avc/NL_000001_019401/manifest.mpd')
        createdUrl = urlHelper.build_url('0123456789ABCDEF', url)
        self.assertEqual(createdUrl, expectedUrl, 'URL not as expected')
        s = createdUrl.find('/manifest')
        manifestUrl = urlHelper.get_manifest_url(createdUrl[s:], '0123456789ABCDEF')
        self.assertEqual(manifestUrl, expectedManifestUrl, 'URL not as expected')
        print(manifestUrl)
        urlHelper.update_redirection(createdUrl[s:], redirectedUrl)
        manifestUrl = urlHelper.get_manifest_url(createdUrl[s:], '0123456789ABCDEF')
        self.assertEqual(manifestUrl, redirectedUrl, 'URL not as expected')
        videoUrl = (
            '/private1/Header.m4s')
        expectedVideoUrl = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/dash,'
            'vxttoken=0123456789ABCDEF/go-dash-hdready-avc/NL_000001_019401/private1/Header.m4s')
        baseurl = urlHelper.replace_baseurl(videoUrl, '0123456789ABCDEF')
        self.assertEqual(expectedVideoUrl, baseurl, 'URL not as expected')

        li = helpers.listitem_from_url(url, '0123456789ABCDEF', 'content')
        print(li.getLabel())
        # Tests for replay

        url = ('http://wp-pod3-replay-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash/LIVE$NL_000001_019401/index.mpd'
               '/Manifest?device=AVC-OTT-DASH-PR-WV&start=2023-12-15T14%3A16%3A00Z&end=2023-12-15T14%3A51%3A00Z')
        expectedUrl = ('http://127.0.0.1:6868/manifest?path=%2Fsdash%2FLIVE%24NL_000001_019401%2Findex.mpd%2FManifest'
                       '&token=0123456789ABCDEF&hostname=wp-pod3-replay-vxtoken-nl-prod.prod.cdn.dmdsdp.com&device'
                       '=AVC-OTT-DASH-PR-WV&start=2023-12-15T14%3A16%3A00Z&end=2023-12-15T14%3A51%3A00Z')
        expectedManifestUrl = (
            'https://wp-pod3-replay-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash,'
            'vxttoken=0123456789ABCDEF/LIVE$NL_000001_019401/index.mpd'
            '/Manifest?device=AVC-OTT-DASH-PR-WV&start=2023-12-15T14%3A16%3A00Z&end=2023-12-15T14%3A51%3A00Z')
        redirectedUrl = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/wp/wp-pod3-replay-vxtoken-nl'
            '-prod.prod.cdn.dmdsdp.com/sdash,vxttoken=0123456789ABCDEF/LIVE$NL_000001_019401/index.mpd/Manifest'
        )
        createdUrl = urlHelper.build_url('0123456789ABCDEF', url)
        self.assertEqual(createdUrl, expectedUrl, 'URL not as expected')
        s = createdUrl.find('/manifest')
        manifestUrl = urlHelper.get_manifest_url(createdUrl[s:], '0123456789ABCDEF')
        self.assertEqual(manifestUrl, expectedManifestUrl, 'URL not as expected')
        print(manifestUrl)
        # Now update redirection and then create the manifest URL again. it should be identical to the redirected URL
        urlHelper.update_redirection(createdUrl[s:], redirectedUrl)
        manifestUrl = urlHelper.get_manifest_url(createdUrl[s:], '0123456789ABCDEF')
        self.assertEqual(manifestUrl, redirectedUrl, 'URL not as expected')

        li = helpers.listitem_from_url(url, '0123456789ABCDEF', 'content')

        videoUrl = (
            '/S!d2ESQVZDLU9UVC1EQVNILVBSLVdWEgJDeAz7ykSIKfvKFgSf/QualityLevels(128000,'
            'Level_params=dxADIeIBnw..)/Fragments(audio_482_dut=Init)')
        expectedVideoUrl = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/'
            'wp/wp-pod3-replay-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash,'
            'vxttoken=0123456789ABCDEF/LIVE$NL_000001_019401/index.mpd/S'
            '!d2ESQVZDLU9UVC1EQVNILVBSLVdWEgJDeAz7ykSIKfvKFgSf/QualityLevels(128000,'
            'Level_params=dxADIeIBnw..)/Fragments(audio_482_dut=Init)')
        baseurl = urlHelper.replace_baseurl(videoUrl, '0123456789ABCDEF')
        self.assertEqual(expectedVideoUrl, baseurl, 'URL not as expected')

        # Test for video-on-demand urls

        url = (
            'https://wp-pod1-vod-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash'
            '/0e378a707155514f39851ab1e45b6560_734142457f0da3caf957ba97e73249e6/index.mpd/Manifest?device=BR-AVC-DASH')
        expectedUrl = ('http://127.0.0.1:6868/manifest?path=%2Fsdash'
                       '%2F0e378a707155514f39851ab1e45b6560_734142457f0da3caf957ba97e73249e6%2Findex.mpd%2FManifest'
                       '&token=0123456789ABCDEF&hostname=wp-pod1-vod-vxtoken-nl-prod.prod.cdn.dmdsdp.com&device=BR'
                       '-AVC-DASH')
        expectedManifestUrl = (
            'https://wp-pod1-vod-vxtoken-nl-prod.prod.cdn.dmdsdp.com/sdash,'
            'vxttoken=0123456789ABCDEF/0e378a707155514f39851ab1e45b6560_734142457f0da3caf957ba97e73249e6/index.mpd'
            '/Manifest?device=BR-AVC-DASH')
        redirectedUrl = (
            'https://da-d436304820010b88000108000000000000000008.id.cdn.upcbroadband.com/wp/wp-pod3-replay-vxtoken-nl'
            '-prod.prod.cdn.dmdsdp.com/sdash,vxttoken=0123456789ABCDEF/LIVE$NL_000001_019401/index.mpd/Manifest'
        )
        createdUrl = urlHelper.build_url('0123456789ABCDEF', url)
        self.assertEqual(createdUrl, expectedUrl, 'URL not as expected')
        s = createdUrl.find('/manifest')
        manifestUrl = urlHelper.get_manifest_url(createdUrl[s:], '0123456789ABCDEF')
        self.assertEqual(manifestUrl, expectedManifestUrl, 'URL not as expected')
        print(manifestUrl)
        # Now update redirection and then create the manifest URL again. it should be identical to the redirected URL
        urlHelper.update_redirection(createdUrl[s:], redirectedUrl)
        manifestUrl = urlHelper.get_manifest_url(createdUrl[s:], '0123456789ABCDEF')
        self.assertEqual(manifestUrl, redirectedUrl, 'URL not as expected')

        url = ('http://wp4-vxtoken-anp-g05060506-hzn-nl.t1.prd.dyncdn.dmdsdp.com/live/disk1/'
               'NL_000011_019563/go-dash-hdready-avc/NL_000011_019563.mpd')
        expectedUrl = ('http://127.0.0.1:6868/manifest?path=/live/disk1/NL_000011_019563/go-dash-hdready-avc/'
                       'NL_000011_019563.mpd&token=0123456789ABCDEF&'
                       'hostname=wp4-vxtoken-anp-g05060506-hzn-nl.t1.prd.dyncdn.dmdsdp.com')
        expectedManifestUrl = (
            'https://wp4-vxtoken-anp-g05060506-hzn-nl.t1.prd.dyncdn.dmdsdp.com/live,vxttoken=0123456789ABCDEF/disk1/'
            'NL_000011_019563/go-dash-hdready-avc/NL_000011_019563.mpd')
        redirectedUrl = (
            'https://da-d436304520010b88000108000000000000000005.id.cdn.upcbroadband.com/wp/'
            'wp4-vxtoken-anp-g05060506-hzn-nl.t1.prd.dyncdn.dmdsdp.com/live,vxttoken=0123456789ABCDEF/disk1/'
            'NL_000011_019563/go-dash-hdready-avc/NL_000011_019563.mpd'
        )
        createdUrl = urlHelper.build_url('0123456789ABCDEF', url)
        self.assertEqual(unquote(createdUrl), expectedUrl, 'URL not as expected')
        s = createdUrl.find('/manifest')
        manifestUrl = urlHelper.get_manifest_url(createdUrl[s:], '0123456789ABCDEF')
        self.assertEqual(manifestUrl, expectedManifestUrl, 'URL not as expected')
        print(manifestUrl)
        # Now update redirection and then create the manifest URL again. it should be identical to the redirected URL
        urlHelper.update_redirection(createdUrl[s:], redirectedUrl, '../_shared_a997aca19aa594f6aba2bcbd76c87946/')
        manifestUrl = urlHelper.get_manifest_url(createdUrl[s:], '0123456789ABCDEF')
        self.assertEqual(manifestUrl, redirectedUrl, 'URL not as expected')
        videoUrl = ('http://127.0.0.1:6868/_shared_a997aca19aa594f6aba2bcbd76c87946/NL_000011_019563-mp4a_128000_nld'
                    '=20000-init.mp4')
        expectedUrl = (
            'https://da-d436304520010b88000108000000000000000005.id.cdn.upcbroadband.com/wp/'
            'wp4-vxtoken-anp-g05060506-hzn-nl.t1.prd.dyncdn.dmdsdp.com/live,vxttoken=0123456789ABCDEF/disk1/'
            'NL_000011_019563/_shared_a997aca19aa594f6aba2bcbd76c87946/NL_000011_019563-mp4a_128000_nld=20000-init.mp4')
        defaultUrl = urlHelper.replace_baseurl(videoUrl, '0123456789ABCDEF')
        self.assertEqual(expectedUrl, defaultUrl, 'URL not as expected')
        print(defaultUrl)


if __name__ == '__main__':
    unittest.main()
