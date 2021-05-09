# -*- coding: utf-8 -*-

import urllib
import urllib2
import re
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import *
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.jsinterp import JSInterpreter
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.base import InfoExtractor
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError

try:
    import json
except Exception:
    import simplejson as json

from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry

config.plugins.iptvplayer.vevo_default_quality = ConfigSelection(default="1228800", choices=[
("0", _("the worst")),
("245760", "30 KB/s"),
("655360", "80 KB/s"),
("409600", "50 KB/s"),
("655360", "80 KB/s"),
("737280", "90 KB/s"),
("1228800", "150 KB/s"),
("1638400", "200 KB/s"),
("2867200", "350 KB/s"),
("4096000", "500 KB/s"),
("4915200", "600 KB/s"),
("6553600", "800 KB/s"),
("99999999", _("the best"))
])
config.plugins.iptvplayer.vevo_use_default_quality = ConfigYesNo(default=True)
config.plugins.iptvplayer.vevo_allow_hls = ConfigYesNo(default=True)


def _int(data):
    ret = 0
    try:
        ret = int(data)
    except Exception:
        pass
    return ret


class VevoIE(InfoExtractor):
    """
    Accepts urls from vevo.com or in the format 'vevo:{id}'
    (currently used by MTVIE and MySpaceIE)
    """
    _VALID_URL = r'''(?x)
        (?:https?://(?:www\.)?vevo\.com/watch/(?!playlist|genre)(?:[^/]+/(?:[^/]+/)?)?|
           https?://cache\.vevo\.com/m/html/embed\.html\?video=|
           https?://videoplayer\.vevo\.com/embed/embedded\?videoId=|
           vevo:)
        (?P<id>[^&?#]+)'''
    _SMIL_BASE_URL = 'http://smil.lvl3.vevo.com/'
    IE_NAME = 'VEVO'
    _SOURCE_TYPES = {
        0: 'youtube',
        1: 'brightcove',
        2: 'http',
        3: 'hls_ios',
        4: 'hls',
        5: 'smil',  # http
        7: 'f4m_cc',
        8: 'f4m_ak',
        9: 'f4m_l3',
        10: 'ism',
        13: 'smil',  # rtmp
        18: 'dash',
    }
    _VERSIONS = {
        0: 'youtube',  # only in AuthenticateVideo videoVersions
        1: 'level3',
        2: 'akamai',
        3: 'level3',
        4: 'amazon',
    }

    def __init__(self):
        InfoExtractor.__init__(self)
        self._api_url_template = ''

    def printDBG(self, data):
        printDBG("=======================================================")
        printDBG(data)
        printDBG("=======================================================")

    def _initialize_api(self, video_id):
        sts, data = self.cm.getPage('http://www.vevo.com/')
        if sts:
            oauth_token = self.cm.ph.getSearchGroups(data, '''"access_token":"([^"]+?)"''')[0]

        if 'THIS PAGE IS CURRENTLY UNAVAILABLE IN YOUR REGION' in data:
            SetIPTVPlayerLastHostError(_('%s said: This page is currently unavailable in your region') % self.IE_NAME)

        self._api_url_template = 'http://apiv2.vevo.com/%s?token=' + oauth_token

    def _formats_from_json(self, video_info):
        if not video_info:
            return []

        last_version = {'version': -1}
        for version in video_info['videoVersions']:
            # These are the HTTP downloads, other types are for different manifests
            if version['sourceType'] == 2:
                if version['version'] > last_version['version']:
                    last_version = version
        if last_version['version'] == -1:
            raise ExtractorError('Unable to extract last version of the video')

        renditions = re.compile('<rendition ([^>]+?)>').findall(last_version['data'])
        formats = []
        # Already sorted from worst to best quality
        for attr in renditions:
            #format_note = '%(videoCodec)s@%(videoBitrate)4sk, %(audioCodec)s@%(audioBitrate)3sk' % attr
            formats.append({
                'url': self.xmlGetArg(attr, 'url'),
                'format_id': self.xmlGetArg(attr, 'name'),
                'bitrate': (_int(self.xmlGetArg(attr, 'videoBitrate')) + _int(self.xmlGetArg(attr, 'audioBitrate'))) * 1000,
                #'format_note': format_note,
                'height': _int(self.xmlGetArg(attr, 'frameheight')),
                'width': _int(self.xmlGetArg(attr, 'frameWidth')),
            })
        return formats

    def _formats_from_smil(self, smil_xml):
        formats = []

        els = re.compile('<video ([^>]+?)>').findall(smil_xml)
        for el in els:
            src = self.xmlGetArg(el, 'src')
            m = re.match(r'''(?xi)
                (?P<ext>[a-z0-9]+):
                (?P<path>
                    [/a-z0-9]+     # The directory and main part of the URL
                    _(?P<cbr>[0-9]+)k
                    _(?P<width>[0-9]+)x(?P<height>[0-9]+)
                    _(?P<vcodec>[a-z0-9]+)
                    _(?P<vbr>[0-9]+)
                    _(?P<acodec>[a-z0-9]+)
                    _(?P<abr>[0-9]+)
                    \.[a-z0-9]+  # File extension
                )''', src)
            if not m:
                continue

            format_url = self._SMIL_BASE_URL + m.group('path')
            formats.append({
                'url': format_url,
                'format_id': 'SMIL_' + m.group('cbr'),
                'vcodec': m.group('vcodec'),
                'acodec': m.group('acodec'),
                'bitrate': (_int(m.group('vbr')) + _int(m.group('abr'))) * 1000,
                'ext': m.group('ext'),
                'width': _int(m.group('width')),
                'height': _int(m.group('height')),
            })
        return formats

    def _download_api_formats(self, video_id):
        if not self._oauth_token:
            self._downloader.report_warning(
                'No oauth token available, skipping API HLS download')
            return []

        api_url = 'http://apiv2.vevo.com/video/%s/streams/hls?token=%s' % (
            video_id, self._oauth_token)
        api_data = self._download_json(
            api_url, video_id,
            note='Downloading HLS formats',
            errnote='Failed to download HLS format list', fatal=False)
        if api_data is None:
            return []

        m3u8_url = api_data[0]['url']
        return self._extract_m3u8_formats(
            m3u8_url, video_id, entry_protocol='m3u8_native', ext='mp4',
            preference=0)

    def _real_extract2(self, url, hls=None, smil=True):
        mobj = re.match(self._VALID_URL, url)
        video_id = mobj.group('id')

        if hls == None:
            hls = config.plugins.iptvplayer.vevo_allow_hls.value

        json_url = 'http://api.vevo.com/VideoService/AuthenticateVideo?isrc=%s' % video_id
        response = self._download_json(json_url, video_id)
        video_info = response['video'] or {}

        if not video_info and response.get('statusCode') != 909:
            if 'statusMessage' in response:
                SetIPTVPlayerLastHostError(response['statusMessage'])
                raise ExtractorError('%s said: %s' % (self.IE_NAME, response['statusMessage']), expected=True)
            raise ExtractorError('Unable to extract videos')

        if not video_info:
            if url.startswith('vevo:'):
                raise ExtractorError('Please specify full Vevo URL for downloading', expected=True)
            webpage = self._download_webpage(url, video_id)

        formats = self._formats_from_json(video_info)

        is_explicit = video_info.get('isExplicit')
        if is_explicit is True:
            age_limit = 18
        elif is_explicit is False:
            age_limit = 0
        else:
            age_limit = None

        # Download via HLS API
        if hls or 0 == len(formats):
            formats.extend(self._download_api_formats(video_id))

        # Download SMIL
        if smil or 0 == len(formats):
            smil_blocks = sorted((
                f for f in video_info.get('videoVersions', [])
                if f['sourceType'] == 13),
                key=lambda f: f['version'])
            smil_url = '%s/Video/V2/VFILE/%s/%sr.smil' % (
                self._SMIL_BASE_URL, video_id, video_id.lower())
            if smil_blocks:
                smil_url_m = self._search_regex(
                    r'url="([^"]+)"', smil_blocks[-1]['data'], 'SMIL URL',
                    default=None)
                if smil_url_m is not None:
                    smil_url = smil_url_m
            if smil_url:
                smil_xml = self._download_webpage(
                    smil_url, video_id, 'Downloading SMIL info', fatal=False)
                if smil_xml:
                    formats.extend(self._formats_from_smil(smil_xml))

        return {
            'id': video_id,
            'title': '',
            'formats': formats,
            'thumbnail': '',
            'uploader': '',
            'duration': video_info.get('duration', 0),
            'age_limit': age_limit,
        }

    def _call_api(self, path, *args, **kwargs):
        return self._download_json(self._api_url_template % path, *args, **kwargs)

    def _real_extract(self, url, hls=None, smil=True):
        mobj = re.match(self._VALID_URL, url)
        video_id = mobj.group('id')

        if hls == None:
            hls = config.plugins.iptvplayer.vevo_allow_hls.value

        json_url = 'http://api.vevo.com/VideoService/AuthenticateVideo?isrc=%s' % video_id
        response = None #self._download_json(json_url, video_id)
        if response == None:
            video_info = {}
        else:
            video_info = response['video'] or {}

        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>.")
        printDBG(video_info)
        printDBG("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<.")

        artist = None
        featured_artist = None
        uploader = None
        formats = []

        if not video_info:
            try:
                self._initialize_api(video_id)
            except Exception:
                ytid = response.get('errorInfo', {}).get('ytid')
                #if ytid:
                #    self.report_warning(
                #        'Video is geoblocked, trying with the YouTube video %s' % ytid)
                #    return self.url_result(ytid, 'Youtube', ytid)
                raise

            video_info = self._call_api(
                'video/%s' % video_id, video_id, 'Downloading api video info',
                'Failed to download video info')

            video_versions = self._call_api(
                'video/%s/streams' % video_id, video_id,
                'Downloading video versions info',
                'Failed to download video versions info',
                fatal=False)

            # Some videos are only available via webpage (e.g.
            # https://github.com/rg3/youtube-dl/issues/9366)
            if not video_versions:
                webpage = self._download_webpage(url, video_id)
                video_versions = self._extract_json(webpage, video_id, 'streams')[video_id][0]

            artists = video_info.get('artists')
            if artists:
                artist = uploader = artists[0]['name']

            for video_version in video_versions:
                version = self._VERSIONS.get(video_version['version'])
                version_url = video_version.get('url')
                if not version_url:
                    continue

                if '.ism' in version_url:
                    continue
                elif '.mpd' in version_url:
                    continue
                    formats.extend(self._extract_mpd_formats(
                        version_url, video_id, mpd_id='dash-%s' % version,
                        note='Downloading %s MPD information' % version,
                        errnote='Failed to download %s MPD information' % version,
                        fatal=False))
                elif '.m3u8' in version_url and hls:
                    formats.extend(self._extract_m3u8_formats(
                        version_url, video_id, 'mp4', 'm3u8_native',
                        m3u8_id='hls-%s' % version,
                        note='Downloading %s m3u8 information' % version,
                        errnote='Failed to download %s m3u8 information' % version,
                        fatal=False))
                else:
                    m = re.search(r'''(?xi)
                        _(?P<width>[0-9]+)x(?P<height>[0-9]+)
                        _(?P<vcodec>[a-z0-9]+)
                        _(?P<vbr>[0-9]+)
                        _(?P<acodec>[a-z0-9]+)
                        _(?P<abr>[0-9]+)
                        \.(?P<ext>[a-z0-9]+)''', version_url)
                    if not m:
                        continue

                    formats.append({
                        'url': version_url,
                        'format_id': 'http-%s-%s' % (version, video_version['quality']),
                        'vcodec': m.group('vcodec'),
                        'acodec': m.group('acodec'),
                        'bitrate': (_int(m.group('vbr')) + _int(m.group('abr'))) * 1000,
                        'ext': m.group('ext'),
                        'width': _int(m.group('width')),
                        'height': _int(m.group('height')),
                    })
        else:
            artists = video_info.get('mainArtists')
            if artists:
                artist = uploader = artists[0]['artistName']

            featured_artists = video_info.get('featuredArtists')
            if featured_artists:
                featured_artist = featured_artists[0]['artistName']

            smil_parsed = False
            for video_version in video_info['videoVersions']:
                version = self._VERSIONS.get(video_version['version'])
                if version == 'youtube':
                    continue
                else:
                    source_type = self._SOURCE_TYPES.get(video_version['sourceType'])
                    renditions = self.xmlGetText(video_version['data'], 'renditions')
                    if source_type == 'http':
                        tmp = re.compile('<rendition(\s[^>]+?)>').findall(renditions)
                        for rend in tmp:
                            formats.append({
                                'url': self.xmlGetArg(rend, 'url'),
                                'format_id': 'http-%s-%s' % (version, self.xmlGetArg(rend, 'name')),
                                'height': _int(self.xmlGetArg(rend, 'frameheight')),
                                'width': _int(self.xmlGetArg(rend, 'frameWidth')),
                                'vcodec': self.xmlGetArg(rend, 'videoCodec'),
                                'acodec': self.xmlGetArg(rend, 'audioCodec'),
                                'bitrate': (_int(self.xmlGetArg(rend, 'videoBitrate')) + _int(self.xmlGetArg(rend, 'audioBitrate'))) * 1000,
                            })
                    elif source_type == 'hls' and hls:
                        tmp = re.compile('<rendition(\s[^>]+?)>').findall(renditions)
                        for rend in tmp:
                            tmpUrl = self.xmlGetArg(rend, 'url'),
                            formats.extend(self._extract_m3u8_formats(
                                tmpUrl, video_id,
                                'mp4', 'm3u8_native', m3u8_id='hls-%s' % version,
                                note='Downloading %s m3u8 information' % version,
                                errnote='Failed to download %s m3u8 information' % version,
                                fatal=False))
                    elif source_type == 'smil' and version == 'level3' and not smil_parsed:
                        continue
                        formats.extend(self._extract_smil_formats(
                            renditions.find('rendition').attrib['url'], video_id, False))
                        smil_parsed = True

        track = video_info['title']
        if featured_artist:
            artist = '%s ft. %s' % (artist, featured_artist)
        title = '%s - %s' % (artist, track) if artist else track

        genres = video_info.get('genres')
        genre = (
            genres[0] if genres and isinstance(genres, list) and
            isinstance(genres[0], compat_str) else None)

        is_explicit = video_info.get('isExplicit')
        if is_explicit is True:
            age_limit = 18
        elif is_explicit is False:
            age_limit = 0
        else:
            age_limit = None

        duration = video_info.get('duration')

        return {
            'id': video_id,
            'title': '',
            'formats': formats,
            'thumbnail': '',
            'uploader': '',
            'duration': video_info.get('duration', 0),
            'age_limit': age_limit,
        }
