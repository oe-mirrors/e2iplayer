# -*- coding: utf-8 -*-

import urllib
import urllib2
import re
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import *
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.jsinterp import JSInterpreter
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.base import InfoExtractor

try:
    import json
except Exception:
    import simplejson as json


class MTVServicesInfoExtractor(InfoExtractor):
    _MOBILE_TEMPLATE = None
    _LANG = None

    def __init__(self):
        InfoExtractor.__init__(self)
        self.cm.HOST = 'python-urllib/2.7'

    @staticmethod
    def _id_from_uri(uri):
        return uri.split(':')[-1]

    # This was originally implemented for ComedyCentral, but it also works here
    @staticmethod
    def _transform_rtmp_url(rtmp_video_url):
        m = re.match(r'^rtmpe?://.*?/(?P<finalid>gsp\..+?/.*)$', rtmp_video_url)
        if not m:
            return rtmp_video_url
        base = 'http://viacommtvstrmfs.fplive.net/'
        return base + m.group('finalid')

    def _get_feed_url(self, uri):
        return self._FEED_URL

    def _get_thumbnail_url(self, uri, itemdoc):
        search_path = '%s/%s' % (_media_xml_tag('group'), _media_xml_tag('thumbnail'))
        thumb_node = itemdoc.find(search_path)
        if thumb_node is None:
            return None
        else:
            return thumb_node.attrib['url']

    def _extract_mobile_video_formats(self, mtvn_id):
        webpage_url = self._MOBILE_TEMPLATE % mtvn_id
        webpage = self._download_webpage(webpage_url, mtvn_id, params={'header': {'User-Agent': 'curl/7'}})
        metrics_url = unescapeHTML(self._search_regex(r'<a href="(http://metrics.+?)"', webpage, 'url'))
        req = HEADRequest(metrics_url)
        response = self._request_webpage(req, mtvn_id, 'Resolving url')
        url = response.geturl()
        # Transform the url to get the best quality:
        url = re.sub(r'.+pxE=mp4', 'http://mtvnmobile.vo.llnwd.net/kip0/_pxn=0+_pxK=18639+_pxE=mp4', url, 1)
        return [{'url': url, 'ext': 'mp4'}]

    def _extract_video_formats(self, mdoc, mtvn_id):
        if re.match(r'.*/(error_country_block\.swf|geoblock\.mp4)$', self.xmlGetText(mdoc, 'src')) is not None:
            if mtvn_id is not None and self._MOBILE_TEMPLATE is not None:
                printDBG('The normal version is not available from your country, trying with the mobile version')
                return self._extract_mobile_video_formats(mtvn_id)
            raise ExtractorError('This video is not available from your country.')

        formats = []
        data = mdoc[mdoc.find('<rendition'):mdoc.rfind('</rendition>')]
        data = mdoc.split('</rendition>')

        for rendition in data:
            try:
                rtmp_video_url = self.xmlGetText(rendition, 'src')
                if rtmp_video_url.endswith('siteunavail.png'):
                    continue
                params = {}
                params['type'] = self.xmlGetArg(rendition, 'type')
                if 'video/' not in params['type']:
                    continue
                params['url'] = self._transform_rtmp_url(rtmp_video_url)
                params['width'] = self.xmlGetArg(rendition, 'width')
                params['height'] = self.xmlGetArg(rendition, 'height')
                params['bitrate'] = self.xmlGetArg(rendition, 'bitrate')
                formats.append(params)
            except Exception:
                printExc()
        return formats

    def _extract_subtitles(self, mdoc, mtvn_id):
        subtitles = {}
        for transcript in mdoc.findall('.//transcript'):
            if transcript.get('kind') != 'captions':
                continue
            lang = transcript.get('srclang')
            subtitles[lang] = [{
                'url': compat_str(typographic.get('src')),
                'ext': typographic.get('format')
            } for typographic in transcript.findall('./typographic')]
        return subtitles

    def _get_video_info(self, itemdoc):
        uri = self.xmlGetText(itemdoc, 'guid')
        video_id = self._id_from_uri(uri)
        mediagen_url = self.cm.ph.getSearchGroups(self.xmlGetText(itemdoc, 'media:group'), '<media\:content[^>]+?url="([^"]+?)"')[0]
        # Remove the templates, like &device={device}
        mediagen_url = re.sub(r'&[^=]*?={.*?}(?=(&|$))', '', mediagen_url)
        if 'acceptMethods' not in mediagen_url:
            mediagen_url += '&acceptMethods=fms'

        sts, mediagen_doc = self.cm.getPage(mediagen_url)
        if not sts:
            return None

        # This a short id that's used in the webpage urls
        mtvn_id = None
        mtvn_id_node = self.xmlGetText(itemdoc, 'media:category scheme="urn:mtvn:id"')
        if mtvn_id_node != '':
            mtvn_id = mtvn_id_node

        formats = self._extract_video_formats(mediagen_doc, mtvn_id)
        #subtitles = self._extract_subtitles(mediagen_doc, mtvn_id)
        #thumbnail = self._get_thumbnail_url(uri, itemdoc)
        return {'formats': formats}

    def _get_videos_info(self, uri):
        video_id = self._id_from_uri(uri)
        feed_url = self._get_feed_url(uri)
        data = compat_urllib_parse.urlencode({'uri': uri})
        info_url = feed_url + '?'
        if self._LANG:
            info_url += 'lang=%s&' % self._LANG
        info_url += data
        sts, data = self.cm.getPage(info_url)

        data = data[data.find('<item>'):]
        data = data.split('</item>')
        urlTabs = []
        for item in data:
            params = self._get_video_info(item)
            if None != params:
                urlTabs.append(params)
        return urlTabs

    def _real_extract(self, url):
        title = url_basename(url)
        webpage = self._download_webpage(url, title)
        try:
            # the url can be http://media.mtvnservices.com/fb/{mgid}.swf
            # or http://media.mtvnservices.com/{mgid}
            og_url = self._og_search_video_url(webpage)
            mgid = url_basename(og_url)
            if mgid.endswith('.swf'):
                mgid = mgid[:-4]
        except Exception:
            mgid = None

        if mgid is None or ':' not in mgid:
            mgid = self._search_regex(
                [r'data-mgid="(.*?)"', r'swfobject.embedSWF\(".*?(mgid:.*?)"'],
                webpage, 'mgid')

        videos_info = self._get_videos_info(mgid)
        return videos_info


class MTVServicesEmbeddedIE(MTVServicesInfoExtractor):
    IE_NAME = 'mtvservices:embedded'
    _VALID_URL = r'https?://media\.mtvnservices\.com/embed/(?P<mgid>.+?)(\?|/|$)'

    def _get_feed_url(self, uri):
        video_id = self._id_from_uri(uri)
        site_id = uri.replace(video_id, '')
        config_url = ('http://media.mtvnservices.com/pmt/e1/players/{0}/'
                      'context4/context5/config.xml'.format(site_id))
        config_doc = self._download_xml(config_url, video_id)
        feed_node = config_doc.find('.//feed')
        feed_url = feed_node.text.strip().split('?')[0]
        return feed_url

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        mgid = mobj.group('mgid')
        return self._get_videos_info(mgid)


class MTVIE(MTVServicesInfoExtractor):
    _VALID_URL = r'''(?x)^https?://
        (?:(?:www\.)?mtv\.com/videos/.+?/(?P<videoid>[0-9]+)/[^/]+$|
           m\.mtv\.com/videos/video\.rbml\?.*?id=(?P<mgid>[^&]+))'''

    _FEED_URL = 'http://www.mtv.com/player/embed/AS3/rss/'

    def _get_thumbnail_url(self, uri, itemdoc):
        return 'http://mtv.mtvnimages.com/uri/' + uri

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        video_id = mobj.group('videoid')
        uri = mobj.groupdict().get('mgid')
        if uri is None:
            webpage = self._download_webpage(url, video_id)

            # Some videos come from Vevo.com
            m_vevo = re.search(
                r'(?s)isVevoVideo = true;.*?vevoVideoId = "(.*?)";', webpage)
            if m_vevo:
                vevo_id = m_vevo.group(1)
                self.to_screen('Vevo video detected: %s' % vevo_id)
                return self.url_result('vevo:%s' % vevo_id, ie='Vevo')

            uri = self._html_search_regex(r'/uri/(.*?)\?', webpage, 'uri')
        return self._get_videos_info(uri)


class MTVIggyIE(MTVServicesInfoExtractor):
    IE_NAME = 'mtviggy.com'
    _VALID_URL = r'https?://www\.mtviggy\.com/videos/.+'
    _FEED_URL = 'http://all.mtvworldverticals.com/feed-xml/'


class GametrailersIE(MTVServicesInfoExtractor):
    _VALID_URL = r'http://www\.gametrailers\.com/(?P<type>videos|reviews|full-episodes)/(?P<id>.*?)/(?P<title>.*)'
    _FEED_URL = 'http://www.gametrailers.com/feeds/mrss'
