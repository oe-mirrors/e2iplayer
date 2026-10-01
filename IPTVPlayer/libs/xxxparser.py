# -*- coding: utf-8 -*-
###################################################
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, GetTmpDir, byteify
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, unpackJSPlayerParams, TEAMCASTPL_decryptPlayerParams
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
import re
import base64
import codecs
import hashlib
import random
import time
import subprocess

try:
	import http.client as httplib  # Python 3
except ImportError:
	import httplib  # Python 2

try:
	import json
except ImportError:
	import simplejson as json
try:
	from urllib.parse import quote, unquote, urlencode, urlsplit, parse_qs
	from urllib.request import urlopen
except ImportError:
	from urllib import quote, unquote, urlencode
	from urllib2 import urlopen  # Python 2: urllib.urlopen() has no timeout argument
	from urlparse import urlsplit, parse_qs
from os.path import join
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Screens.MessageBox import MessageBox

try:
	basestring  # Python 2
except NameError:
	basestring = str  # Python 3
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0'


def checkhttp(url):
	if url.startswith('//'):
		url = 'http:%s' % url
	return url


def checkhttps(url):
	if url.startswith('//'):
		url = 'https:%s' % url
	return url


# sites of the txxx network (hostxxx.py TXXX_NETWORK), same videofile API
TXXX_NETWORK_SITES = ('https://upornia.com', 'https://hdzog.com', 'https://vxxx.com')

# plain KVS sites (hostxxx.py KVS_NETWORK), resolved by the shared KVS branch
KVS_SITES = ('https://freshporno.org', 'https://www.freepornvideos.xxx', 'https://www.fpo.xxx', 'https://heroero.com', 'https://porndd.com', 'https://amateurporn.me')

# WordPress tube theme sites (hostxxx.py WPTUBE_NETWORK): own player page or a file hoster iframe
WPTUBE_SITES = ('https://pornmz.com', 'https://www.hitprn.net', 'https://pornobae.com')

# live cam sites (hostxxx.py SITEDATA_CAMS), the stream is looked up when it is played
LIVECAM_SITES = ('https://www.cam4.com', 'https://www.camsoda.com', 'https://www.myfreecams.com', 'https://streamate.com', 'https://www.xlovecam.com', 'https://api.sinparty.com', 'https://stripchat.com')

# the txxx network hides its base64 video path behind look-alike cyrillic letters
TXXX_CHARMAP = {
	u'А': 'A', u'В': 'B', u'С': 'C', u'Е': 'E', u'Н': 'H', u'К': 'K',
	u'М': 'M', u'О': 'O', u'Р': 'P', u'Т': 'T', u'Х': 'X',
	u'а': 'a', u'с': 'c', u'е': 'e', u'к': 'k', u'о': 'o', u'р': 'p',
	u'х': 'x', u'у': 'y', '~': '=', '.': '+', ',': '/',
}


def decodeTxxxUrl(encoded):
	for key, value in TXXX_CHARMAP.items():
		encoded = encoded.replace(key, value)
	encoded = re.sub(r'[^A-Za-z0-9+/=]', '', encoded)
	encoded += '=' * (-len(encoded) % 4)
	try:
		videoUrl = base64.b64decode(encoded.encode('ascii'))
	except Exception:
		printExc()
		return ''
	if not isinstance(videoUrl, str):
		videoUrl = videoUrl.decode('utf-8', 'ignore')
	return videoUrl.strip()


def fix_escaped_url(text):
    text = text.replace('\\\\', '\\')

    def replace_unicode_escapes(match):
        try:
            return chr(int(match.group(1), 16))
        except Exception:
            return match.group(0)

    text = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode_escapes, text)

    text = text.replace('\\/', '/')
    text = text.replace('"', '')
    return text


class XXXParser:

	def _uhdAllowed(self):
		# config xxx4k "Playback UHD", set by Host.__init__ / listsItems / IPTVHost.getResolvedURL
		return getattr(self, 'format4k', True)

	def _labelHeight(self, text):
		# '2160p 4K', '1080p FHD', '..._720p.mp4', '4K Ultra HD' -> 2160 / 1080 / 720 / 2160; 0 if unknown
		height = int(self.cm.ph.getSearchGroups(text, r'([0-9]{3,4})[pP]', 1, True)[0] or 0)
		if not height and re.search(r'(?i)(?:^|[^0-9a-z])4k(?:$|[^0-9a-z])', text):
			height = 2160
		return height

	def _pickByHeight(self, candidates):
		# candidates: [(height, url)]; the highest one, above 1080p only when UHD playback is on
		# (equal heights keep their order, the first one wins)
		if not candidates:
			return ''
		candidates = sorted(candidates, key=lambda c: c[0], reverse=True)
		if not self._uhdAllowed():
			candidates = [c for c in candidates if c[0] <= 1080] or candidates[-1:]
		return candidates[0][1]

	def _turbovidhls(self, embedUrl, referer):
		# turbovidhls player page (321TUBE, PORN4DAYS server 1): HLS whose segments are TS behind a PNG header on
		# Google's image CDN, or a plain MP4 in urlPlay/file on newer uploads
		header = self.cm.getDefaultHeader(browser='chrome')
		header['Referer'] = referer
		sts, data = self.cm.getPage(embedUrl, {'header': header, 'return_data': True})
		if not sts:
			return ''
		videoUrl = self.cm.ph.getSearchGroups(data, r'''(https?://[^"'<>\s]+\.m3u8[^"'<>\s]*)''', 1, True)[0] or self.cm.ph.getSearchGroups(data, r'''(?:urlPlay|file)\s*[:=]\s*["'](https?://[^"']+\.mp4[^"']*)["']''', 1, True)[0]
		if not videoUrl:
			return ''
		# no Referer: the turbovidhls player page is "no-referrer", and Google's image CDN answers 429 to segment
		# requests that carry the turbovidhls Referer (200 without it)
		meta = {'User-Agent': header.get('User-Agent', '')}
		if '.m3u8' in videoUrl:
			# exteplayer3/gstplayer find no tracks behind the PNG header, hlsdl just fetches the bytes -> buffer only
			meta['iptv_buffering'] = 'required'
		return urlparser.decorateUrl(videoUrl.replace('\\/', '/'), meta)

	def _bestFromQualityList(self, url, handler, maxHeight=0):
		# "use the best quality": build the list the host's quality menu (handler) would show and take the
		# best entry (label '1080p' / '4K Ultra HD' / '1920x1080'); maxHeight skips entries the site locks
		try:
			items = self.listsItems(-1, url, handler) or []
		except Exception:
			printExc()
			return ''
		candidates = []
		for item in items:
			if item.type != 'VIDEO' or not item.urlItems:
				continue
			height = self._labelHeight(item.name) or int(self.cm.ph.getSearchGroups(item.name, r'[0-9]{3,4}x([0-9]{3,4})', 1, True)[0] or 0)
			if maxHeight and height > maxHeight:
				continue
			candidates.append((height, item.urlItems[0].url))
		return self._pickByHeight(candidates)

	def _mediaCandidates(self, data):
		# [(height, url)] of a video page, best first among equal heights (bitrate, then the later entry - KVS lists
		# video_url before the better video_alt_url): KVS flashvars video_url / video_alt_urlN (+ _text;
		# a page may carry several player blocks), else <source> tags (label/res/title or the file name, _720p.mp4).
		# 'High Quality' without a number (KVS: the original upload) counts as 1080p.
		entries = []
		for key, isText, value in re.findall(r"(video_url|video_alt_url[0-9]*)(_text)?\s*:\s*'([^']*)'", data):
			if isText:
				for entry in reversed(entries):
					if entry[0] == key:
						entry[1] = value
						break
			elif value:
				entries.append([key, '', value])
		if not entries:
			for tag in re.findall(r'<source\b[^>]*>', data):
				src = self.cm.ph.getSearchGroups(tag, r'''src=["']([^"']+)["']''', 1, True)[0]
				if src:
					label = ' '.join(self.cm.ph.getSearchGroups(tag, r'''%s=["']([^"']*)["']''' % attr, 1, True)[0] for attr in ('label', 'res', 'size', 'title', 'data-quality'))
					entries.append(['source', label, decodeHtml(src)])
		licenseCode = self.cm.ph.getSearchGroups(data, r"license_code\s*:\s*'([^']+)'", 1, True)[0]
		candidates, seen = [], set()
		for order, (_key, label, videoUrl) in enumerate(entries):
			if videoUrl.startswith('function/0/') and licenseCode:
				videoUrl = decryptHash(videoUrl, licenseCode, '16')
			if videoUrl.startswith('//'):
				videoUrl = 'https:' + videoUrl
			if videoUrl in seen or (not videoUrl.startswith('http') and not videoUrl.startswith('/')):
				continue
			seen.add(videoUrl)
			height = self._labelHeight(label) or self._labelHeight(videoUrl.split('?')[0])
			if not height and re.search(r'(?i)high|\bhq\b|\bhd\b|original', label):
				height = 1080
			bitrate = int(self.cm.ph.getSearchGroups(videoUrl, r'[?&]br=([0-9]+)', 1, True)[0] or 0)
			candidates.append((height, bitrate, order, videoUrl))
		candidates.sort(key=lambda c: (c[1], c[2]), reverse=True)
		return [(height, videoUrl) for height, _bitrate, _order, videoUrl in candidates]

	def _bestM3U8Variant(self, videoUrl, **kwargs):
		# best variant (bitrate) of an HLS master, >1080p variants skipped when UHD playback is off; '' if none
		kwargs.setdefault('checkContent', True)
		try:
			variants = getDirectM3U8Playlist(videoUrl, sortWithMaxBitrate=999999999, **kwargs)
		except Exception:
			printExc()
			return ''
		if not self._uhdAllowed():
			variants = [v for v in variants if min(int(v.get('height') or 0), int(v.get('width') or 0) or 99999) <= 1080] or variants[-1:]
		for v in variants:
			if v.get('url'):
				return v['url']
		return ''

	def getLinksForVideo(self, url):
		printDBG("Urllist.getLinksForVideo url[%s]" % url)
		videoUrls = []
		uri, params = DMHelper.getDownloaderParamFromUrl(url)
		printDBG(params)
		uri = urlparser.decorateUrl(uri, params)

		urlSupport = self.up.checkHostSupport(uri)
		if 1 == urlSupport:
			retTab = self.up.getVideoLinkExt(uri)
			videoUrls.extend(retTab)
			printDBG("Video url[%s]" % videoUrls)
			return videoUrls

	def getParser(self, url):
		printDBG('Host getParser begin')
		printDBG('Host getParser mainurl: ' + self.MAIN_URL)
		printDBG('Host getParser url	: ' + url)

		if url.startswith('https://www.xnxx.com') or 'xnxx-cdn.com' in url:
			return 'https://www.xnxx.com'
		if url.startswith('https://www.porntrex.com'):
			return 'https://www.porntrex.com'
		if url.startswith(('https://relax-sex.com', 'https://relaxporn.net', 'https://handjobhub.com', 'https://www.xnxxhamster.net')):
			return 'https://relax-sex.com'
		if url.startswith('https://porcore.com'):
			return 'https://porcore.com'
		if url.startswith('https://www.al4a.com'):
			return 'https://www.al4a.com'
		if url.startswith('https://xxxdan.com'):
			return 'https://xxxdan.com'
		if url.startswith('https://www.trendyporn.com'):
			return 'https://www.trendyporn.com'
		if url.startswith('https://hypnotube.com'):
			return 'https://hypnotube.com'
		if url.startswith('https://www.alotporn.com'):
			return 'https://www.alotporn.com'
		if url.startswith('https://www.mypornhere.com'):
			return 'https://www.mypornhere.com'
		if url.startswith('https://veporn.com'):
			return 'https://veporn.com'
		if url.startswith('https://pxp.news'):
			return 'https://pxp.news'
		if url.startswith('https://pornoflix.com'):
			return 'https://pornoflix.com'
		if url.startswith('https://en.pornoreino.com'):
			return 'https://en.pornoreino.com'
		if url.startswith('https://www.whoreshub.com'):
			return 'https://www.whoreshub.com'
		if url.startswith('https://www.camhub.cc'):
			return 'https://www.camhub.cc'
		if url.startswith(('https://babes34.me', 'https://youramateurtube.com')):
			return 'https://babes34.me'
		if url.startswith('https://streamwish.'):
			return 'https://streamwish.to'
		if url.startswith(('https://emturbovid.com', 'https://www.turbovid.com')):
			return 'https://emturbovid.com'
		if url.startswith('https://sex3.com'):
			return 'https://sex3.com'
		if url.startswith('https://www.porntube.com'):
			return 'https://www.4tube.com'
		if url.startswith(('https://www.4tube.com', 'https://4tube.com')):
			return 'https://www.4tube.com'
		if url.startswith('https://www.ah-me.com'):
			return 'https://www.ah-me.com'
		if url.startswith(('https://www.pornhat.com/', 'https://pornhat.com/')):
			return 'https://www.pornhat.com/'
		if url.startswith('https://ruleporn.com'):
			return 'https://ruleporn.com'
		if url.startswith('https://www.drtuber.com'):
			return 'https://www.drtuber.com'
		if url.startswith('https://www.eporner.com'):
			return 'https://www.eporner.com'
		if url.startswith(('https://www.yourupload.com', 'https://yourupload.com')):
			return 'https://www.yourupload.com'
		if url.startswith(('https://www.hclips.com', 'https://hclips.com')):
			return 'https://www.hclips.com'
		if url.startswith('https://www.hdporn.net'):
			return 'https://www.hdporn.net'
		if url.startswith('https://hdsite.net'):
			return 'https://hdsite.net'
		if url.startswith('https://www.alohatube.com'):
			return 'https://www.alohatube.com'
		if url.startswith('https://hentaigasm.com'):
			return 'https://hentaigasm.com'
		if url.startswith('https://www.homemoviestube.com'):
			return 'https://www.homemoviestube.com'
		if url.startswith('https://zbporn.com'):
			return 'https://zbporn.com'
		if url.startswith('https://www.katestube.com'):
			return 'https://www.katestube.com'
		if url.startswith('https://www.koloporno.com'):
			return 'https://www.koloporno.com'
		if url.startswith('https://mangovideo'):
			return 'https://mangovideo'
		if url.startswith('https://videos.porndig.com'):
			return 'https://porndig.com'
		if url.startswith('https://www.playvids.com'):
			return 'https://www.playvids.com'
		if url.startswith(('https://glavmatures.com', 'https://www.glavmatures.com')):
			return 'https://glavmatures.com'
		if url.startswith('https://xcum.com'):
			return 'https://xcum.com'
		if url.startswith('https://www.pornhd.com'):
			return 'https://www.pornhd.com'
		if url.startswith(('https://www.pornhub.com/embed/', 'https://pl.pornhub.com/embed/')):
			return 'https://www.pornhub.com/embed/'
		if url.startswith(('https://pl.pornhub.com', 'https://www.pornhub.com')):
			return 'https://www.pornhub.com'
		if url.startswith('https://m.pornhub.com'):
			return 'https://m.pornhub.com'
		if url.startswith(('https://pornicom.com', 'https://www.pornicom.com')):
			return 'https://pornicom.com'
		if url.startswith('https://www.pornid.xxx'):
			return 'https://www.pornid.xxx'
		if url.startswith('https://www.pornoxo.com'):
			return 'https://www.pornoxo.com'
		if url.startswith('https://www.pornrabbit.com'):
			return 'https://www.pornrabbit.com'
		if url.startswith('https://www.pornrewind.com'):
			return 'https://www.pornrewind.com'
		if url.startswith('https://motherlesss.net'):
			return 'https://motherlesss.net'
		if url.startswith('https://embed.redtube.com'):
			return 'https://embed.redtube.com'
		if url.startswith('https://www.redtube.com'):
			return 'https://www.redtube.com'
		if url.startswith('https://shooshtime.com'):
			return 'https://shooshtime.com'
		if url.startswith('https://www.tnaflix.com'):
			return 'https://www.tnaflix.com'
		if url.startswith('https://alpha.tnaflix.com'):
			return 'https://alpha.tnaflix.com'
		if url.startswith('https://www.tube8.com/embed/'):
			return 'https://www.tube8.com/embed/'
		if url.startswith('https://www.tube8.com'):
			return 'https://www.tube8.com'
		if url.startswith('https://m.tube8.com'):
			return 'https://m.tube8.com'
		if url.startswith('https://pornone.com'):
			return 'https://pornone.com'
		if url.startswith(('https://xhamster.com', 'https://xh.video')):
			return 'https://xhamster.com'
		if url.startswith('https://www.xvideos.com'):
			return 'https://www.xvideos.com'
		if url.startswith('https://porngo.com'):
			return 'https://porngo.com'
		if url.startswith('https://www.youjizz.com'):
			return 'https://www.youjizz.com'
		if url.startswith('https://www.youporn.com/embed/'):
			return 'https://www.youporn.com/embed/'
		if url.startswith('https://www.youporn.com'):
			return 'https://www.youporn.com'
		if url.startswith('https://sxyprn.com'):
			return 'https://sxyprn.com'
		if url.startswith('https://mini.zbiornik.com'):
			return 'https://mini.zbiornik.com'
		if url.startswith('https://sexkino.to'):
			return 'https://sexkino.to'
		if url.startswith('https://www.plashporn.com'):
			return 'https://sexkino.to'
		if url.startswith(('https://www.alphaporno.com', 'https://crocotube.com', 'https://www.tubewolf.com', 'https://zedporn.com')):
			return 'https://www.tubewolf.com'
		if url.startswith('https://www.fetishpapa.com'):
			return 'https://www.fetishpapa.com'
		if url.startswith('https://upstream.to'):
			return 'https://upstream.to'
		if url.startswith('https://prostream.to'):
			return 'https://prostream.to'
		if url.startswith('https://www.bravotube.net'):
			return 'https://www.hdporn.net'
		if url.startswith('https://lecoinporno.fr'):
			return 'https://lecoinporno.fr'
		if url.startswith('https://mompornonly.com'):
			return 'https://mompornonly.com'
		if url.startswith('https://videobin.co'):
			return 'https://videobin.co'
		if url.startswith(('https://dato.porn', 'https://datoporn.co', 'https://www.datoporn.com')):
			return 'https://dato.porn'
		if url.startswith('https://vidlox.tv'):
			return 'https://vidlox.tv'
		if url.startswith('http://pornvideos4k.com/en'):  # NOSONAR - site deactivated, kept for possible future reactivation
			return 'http://pornvideos4k.com/en'  # NOSONAR - site deactivated, kept for possible future reactivation
		if url.startswith('https://www.watchmygf.me'):
			return 'https://mangovideo'
		if 'mix-porn' in url or 'mixporn' in url:
			return 'https://rusporn.tv'
		if url.startswith(('https://www.slutsxmovies.com/embed/', 'https://www.cumyvideos.com/embed/', 'https://www.nuvid.com', 'https://porneo.com')):
			return 'https://www.nuvid.com'
		if url.startswith('https://www.sleazyneasy.com'):
			return 'https://www.sleazyneasy.com'
		if url.startswith('https://www.sheshaft.com'):
			return 'https://www.deviants.com'
		if url.startswith(('https://theclassicporn.com', 'https://www.tryboobs.com', 'https://www.azzzian.com', 'https://www.finevids.xxx', 'https://www.pornoid.com', 'https://www.wetplace.com', 'https://www.pornalized.com')):
			return "video_url: '"
		if url.startswith('https://www.faphub.xxx'):
			return 'https://www.faphub.xxx'
		if url.startswith('https://www.proporn.com'):
			return 'https://www.proporn.com'
		if url.startswith('https://www.viptube.com'):
			return 'https://www.nuvid.com'
		if url.startswith('https://www.jizz.us'):
			return 'https://www.x3xtube.com'
		if url.startswith('https://hellmoms.com/'):
			return 'https://xbabe.com'
		if url.startswith('https://streamtape.com'):
			return 'xxxlist.txt'
		if url.startswith('https://filemoon.sx'):
			return 'https://filemoon.sx'
		if url.startswith((
			'https://doodstream.com', 'https://www.doodstream.com', 'https://dood.pm',
			'https://dood.la', 'https://www.dood.la', 'https://www.dood.pm',
			'https://dood.re', 'https://www.dood.re', 'https://d000d.com',
			'https://playmogo.com'
		)):
			return 'doodstream.com'
		if url.startswith('https://streamvid.net'):
			return 'https://streamvid.net'
		if url.startswith('https://www.amdahost.com'):
			return 'https://www.amdahost.com'
		if url.startswith(('https://www.bravoporn.com', 'https://www.bravoteens.com')) or self.MAIN_URL == 'https://www.bravoteens.com':
			return 'https://www.bravoporn.com'
		if url.startswith('https://www.sexvid.xxx'):
			return 'https://familyporn.tv'
		if url.startswith('https://www.momvids.com'):
			return 'https://www.momvids.com'
		if url.startswith('https://hellporno.com/'):
			return 'https://hellporno.com/'
		if url.startswith('https://sextubefun.com/'):
			return 'https://sextubefun.com/'
		if url.startswith('https://www.xxxbule.com/'):
			return 'https://www.xxxbule.com/'
		if url.startswith('https://www.porndig.com'):
			return 'https://www.porndig.com'
		if url.startswith('https://www.filmyporno.tv'):
			return 'https://www.filmyporno.tv'
		if url.startswith('https://xcafe.com'):
			return 'https://xcafe.com'
		if url.startswith('https://topvids.net'):
			return 'https://topvids.net'
		if url.startswith(('https://www.firstanalvideos.com/', 'https://www.deviants.com', 'http://pornbimbo.com', 'https://pornbimbo.com', 'http://www.pornfd.com', 'https://www.punishbang.com', 'https://www.pornwhite.com', 'https://www.wankoz.com', 'https://www.boundhub.com', 'https://shameless.com', 'https://www.amateur8.com/', 'https://www.xozilla.com', 'https://xozilla.com', 'https://www.ohsexfilm.com', 'https://www.mature-amateur-sex.com', 'https://thepornarea.com', 'https://camstreams.tv/', 'https://www.momslust.com', 'https://porn2all.com', 'https://in35.com', 'https://www.camvideos.tv', 'https://www.shemalehd.sex', 'https://jizzboom.com', 'https://www.javbangers.com', 'https://www.sunporno.com', 'https://www.ebony8.com', 'https://nudez.com', 'https://severeporn.com', 'https://neporn.com')):
			return 'https://www.deviants.com'
		if url.startswith(('https://www.3movs.com', 'https://www.pervclips.com', 'https://hqbang.com/')):
			return 'https://www.3movs.com'
		if url.startswith('https://chaturbate.com'):
			return 'https://chaturbate.com'
		if url.startswith('https://yourlive.webcam'):
			return 'https://yourlive.webcam'
		if url.startswith('https://jizzbunker.com'):
			return 'https://jizzbunker.com'
		if url.startswith('https://lulustream.com'):
			return 'https://lulustream.com'
		if url.startswith('https://luluvid.com'):
			return 'https://luluvid.com'
		if url.startswith('https://playmate.to'):
			return 'https://playmate.to'
		if url.startswith('https://mixdrop.my'):
			return 'https://mixdrop.my'
		if url.startswith('https://voe.sx'):
			return 'https://voe.sx'
		if url.startswith('https://www.moviefap.com'):
			return 'https://www.moviefap.com'
		if url.startswith('https://www.sexmature.xxx'):
			return 'https://www.sexmature.xxx'
		if url.startswith('https://www.teentuber.xxx'):
			return 'https://www.teentuber.xxx'
		if url.startswith('https://www.porndroids.com'):
			return 'https://www.porndroids.com'
		if url.startswith('https://www.perfectgirls.xxx'):
			return 'https://www.perfectgirls.xxx'
		if url.startswith('https://femefun.com'):
			return 'https://femefun.com'
		if url.startswith('https://hqporner.com'):
			return 'https://hqporner.com'

		if url.endswith(('.mjpg', '.cgi')):
			return 'mjpg_stream'
		if url.startswith((
			'https://gounlimited.to', 'https://openload.co', 'https://oload.tv',
			'https://www.cda.pl', 'https://hqq.tv', 'https://hqq.to',
			'https://www.rapidvideo.com', 'https://videomega.tv', 'https://www.flashx.tv',
			'https://streamcloud.eu', 'https://thevideo.me', 'https://vidoza.net',
			'https://fileone.tv', 'https://streamcherry.com', 'https://vk.com',
			'https://www.fembed.com'
		)) or self.MAIN_URL in [
			'https://streamporn.pw',
			'https://streamporn.org',
			'https://streamporn.vip',
			'https://streamporn.li',
			'https://pandamovies.org',
			'https://www.xxxstreams.org',
			'https://www.pornrewind.com',
			'https://watchpornx.com',
			'https://ebuxxx.net',
			''
		]:
			return 'xxxlist.txt'

		if self.MAIN_URL in [
			'https://xxxdessert.com',
			'https://www.pornalin.com',
		]:
			return 'https://www.youx.xxx'

		if self.MAIN_URL == 'https://www.porntube.com':
			return 'https://www.4tube.com'

		if url.startswith('https://www.cuckoldplacetube.com'):
			return 'https://www.cuckoldplacetube.com'
		if url.startswith('https://baddies.xxx'):
			return 'https://baddies.xxx'
		if url.startswith('https://www.amazingcuckold.com'):
			return 'https://www.amazingcuckold.com'

		if url.startswith('https://www.xxbrits.com'):
			return 'https://www.xxbrits.com'
		if url.startswith('https://hdpussy.xxx'):
			return 'https://hdpussy.xxx'
		if url.startswith('https://cambeauties.com'):
			return 'https://cambeauties.com'
		if url.startswith('https://www.xpaja.net'):
			return 'https://www.xpaja.net'
		if url.startswith('https://www.xrares.com'):
			return 'https://www.xrares.com'
		if url.startswith('https://www.xtits.com'):
			return 'https://www.xtits.com'
		if url.startswith('https://amateur.red'):
			return 'https://amateur.red'
		if url.startswith('https://www.terk.nl'):
			return 'https://www.terk.nl'
		if url.startswith('https://hardsexvids.com'):
			return 'https://hardsexvids.com'
		if url.startswith(('https://www.fuqer.com', 'https://fuqer.com')):
			return 'https://www.fuqer.com'
		if url.startswith('https://young-sex-tube.com'):
			return 'https://young-sex-tube.com'
		if url.startswith('https://javteentube.com'):
			return 'https://javteentube.com'
		if url.startswith('https://pornvideosbest.com'):
			return 'https://pornvideosbest.com'
		if url.startswith('https://www.oriental-sex.com'):
			return 'https://www.oriental-sex.com'
		if url.startswith('https://69teentube.com'):
			return 'https://69teentube.com'
		if url.startswith('https://www.milffox.com'):
			return 'https://www.milffox.com'
		if url.startswith('https://9vids.com'):
			return 'https://9vids.com'
		if url.startswith('https://www.porndr.com'):
			return 'https://www.porndr.com'
		if url.startswith('https://moreamateurs.com'):
			return 'https://moreamateurs.com'
		if url.startswith('https://blowjobit.com'):
			return 'https://blowjobit.com'
		if url.startswith('https://www.amateur-cougar.com'):
			return 'https://www.amateur-cougar.com'
		if url.startswith('https://www.moms-sex-videos.com'):
			return 'https://www.moms-sex-videos.com'
		if url.startswith('https://www.justporn.com'):
			return 'https://www.justporn.com'
		if url.startswith('https://www.worldsex.com'):
			return 'https://www.worldsex.com'
		if url.startswith('https://engorgedtits.com'):
			return 'https://engorgedtits.com'
		if url.startswith('https://bdsm.one'):
			return 'https://bdsm.one'
		if url.startswith('https://vagina.nl'):
			return 'https://vagina.nl'
		if url.startswith('https://indianporntube.net'):
			return 'https://indianporntube.net'
		if url.startswith('https://voyeurhit.com'):
			return 'https://voyeurhit.com'
		if url.startswith('https://www.realmatureporn.com'):
			return 'https://www.realmatureporn.com'
		if url.startswith('https://run.porn'):
			return 'https://run.porn'
		if url.startswith('https://www.nakedgirls.mobi'):
			return 'https://www.nakedgirls.mobi'
		if url.startswith('https://yespornpleasexxx.com'):
			return 'https://yespornpleasexxx.com'
		if url.startswith('https://www.hdtube.porn'):
			return 'https://www.hdtube.porn'
		if url.startswith('https://www.pornslash.com'):
			return 'https://www.pornslash.com'
		if url.startswith('https://www.realgfporn.com'):
			return 'https://www.realgfporn.com'
		if url.startswith('https://en.paradisehill.cc'):
			return 'https://en.paradisehill.cc'
		if url.startswith('https://www.erogarga.com'):
			return 'https://www.erogarga.com'
		if url.startswith('https://www.tubev.sex'):
			return 'https://www.tubev.sex'
		if url.startswith('https://senioras.com'):
			return 'https://senioras.com'
		if url.startswith('https://www.xmegadrive.com'):
			return 'https://www.xmegadrive.com'
		if url.startswith('https://xhand.net'):
			return 'https://xhand.net'
		if url.startswith('https://www.lesbian8.com'):
			return 'https://www.lesbian8.com'
		if url.startswith('https://mylust.com'):
			return 'https://mylust.com'
		if url.startswith('https://w1mp.com'):
			return 'https://w1mp.com'
		if url.startswith('https://porndreamz.com'):
			return 'https://porndreamz.com'
		if url.startswith('https://bigbuttholes.com'):
			return 'https://bigbuttholes.com'
		if url.startswith('https://www.vikiporn.com'):
			return 'https://www.vikiporn.com'
		if url.startswith('https://maturexy.com'):
			return 'https://maturexy.com'
		if url.startswith('https://xxxbunker.com'):
			return 'https://xxxbunker.com'
		if url.startswith('https://pornmeka.com'):
			return 'https://pornmeka.com'
		if url.startswith('https://letsporn.com'):
			return 'https://letsporn.com'
		if url.startswith('https://jizzberry.com'):
			return 'https://jizzberry.com'
		if url.startswith('https://moantube.com'):
			return 'https://moantube.com'
		if url.startswith('https://www.definebabe.com'):
			return 'https://www.definebabe.com'
		if url.startswith('https://fit.porn'):
			return 'https://fit.porn'
		if url.startswith('https://www.rat.xxx'):
			return 'https://www.rat.xxx'
		if url.startswith('https://fapnfuck.com'):
			return 'https://fapnfuck.com'
		if url.startswith('https://fapality.com'):
			return 'https://fapality.com'
		if url.startswith('https://homemade.xxx'):
			return 'https://homemade.xxx'
		if url.startswith('https://anal.media'):
			return 'https://anal.media'
		if url.startswith('https://www.porngem.com'):
			return 'https://www.porngem.com'
		if url.startswith('https://lustysextube.com'):
			return 'https://lustysextube.com'
		if url.startswith('https://www.sexsq.com'):
			return 'https://www.sexsq.com'
		if url.startswith('https://bigboobsxxx.com'):
			return 'https://bigboobsxxx.com'
		if url.startswith('https://www.tabootube.xxx'):
			return 'https://www.tabootube.xxx'
		if url.startswith('https://leslez.com'):
			return 'https://leslez.com'
		if url.startswith('https://hardporno.tube'):
			return 'https://hardporno.tube'
		if url.startswith('https://eboblack.com'):
			return 'https://eboblack.com'
		if url.startswith('https://deepfaceporn.com'):
			return 'https://deepfaceporn.com'
		if url.startswith('https://www.pornekip.com'):
			return 'https://www.pornekip.com'
		if url.startswith('https://www.sexocean.net'):
			return 'https://www.sexocean.net'
		if url.startswith('https://hog.tv'):
			return 'https://hog.tv'
		if url.startswith('https://www.fetishshrine.com'):
			return 'https://www.fetishshrine.com'
		if url.startswith('https://wankgalore.com'):
			return 'https://wankgalore.com'
		if url.startswith('https://www.uiporn.com'):
			return 'https://www.uiporn.com'
		if url.startswith('https://www.dafreeporn.com'):
			return 'https://www.dafreeporn.com'
		if url.startswith('https://www.cuckoldsporn.porn'):
			return 'https://www.cuckoldsporn.porn'
		if url.startswith('https://some.porn'):
			return 'https://some.porn'
		if url.startswith('https://pornxxxvideos.net'):
			return 'https://pornxxxvideos.net'
		if url.startswith('https://xdporner.com'):
			return 'https://xdporner.com'
		if url.startswith('https://mondetube.com'):
			return 'https://mondetube.com'
		if url.startswith('https://pimpbunny.com'):
			return 'https://pimpbunny.com'
		if url.startswith('https://fyxxr.to'):
			return 'https://fyxxr.to'
		if url.startswith('https://www.superporn.com'):
			return 'https://www.superporn.com'
		if url.startswith('https://www.crazy-amateurs.com'):
			return 'https://www.crazy-amateurs.com'
		if url.startswith('https://xxxelf.com'):
			return 'https://xxxelf.com'
		if url.startswith('https://modporn.com'):
			return 'https://modporn.com'
		if url.startswith('https://max.porn'):
			return 'https://max.porn'
		if url.startswith('https://eroticmv.com'):
			return 'https://eroticmv.com'
		if url.startswith('https://porn4days.pw'):
			return 'https://porn4days.pw'
		if url.startswith('https://8kporner.com'):
			return 'https://8kporner.com'
		if url.startswith('https://www.pornpapa.com'):
			return 'https://www.pornpapa.com'
		if url.startswith('https://hqfap.com'):
			return 'https://hqfap.com'
		if url.startswith('https://naijapornsite.com'):
			return 'https://naijapornsite.com'
		if url.startswith('https://juicyvid.com'):
			return 'https://juicyvid.com'
		if url.startswith('https://www.lapippa.com'):
			return 'https://www.lapippa.com'
		if url.startswith('https://faplane.com'):
			return 'https://faplane.com'
		if url.startswith('https://www.inxxx.com'):
			return 'https://www.inxxx.com'
		if url.startswith('https://www.fucker.com'):
			return 'https://www.fucker.com'
		if url.startswith('https://w4nkr.com'):
			return 'https://w4nkr.com'
		if url.startswith('https://pornyteen.com'):
			return 'https://pornyteen.com'
		if url.startswith('https://momxl.com'):
			return 'https://momxl.com'
		if url.startswith('https://yourlust.com'):
			return 'https://yourlust.com'
		if url.startswith('https://www.its.porn'):
			return 'https://www.its.porn'
		if url.startswith('https://www.theyarehuge.com'):
			return 'https://www.theyarehuge.com'
		if url.startswith('https://ok.xxx'):
			return 'https://ok.xxx'
		if url.startswith('https://www.laidhub.com'):
			return 'https://www.laidhub.com'
		if url.startswith('https://xxxshake.com'):
			return 'https://xxxshake.com'
		if url.startswith('https://pornbolt.com'):
			return 'https://pornbolt.com'
		if url.startswith('https://www.wetsins.com'):
			return 'https://www.wetsins.com'
		if url.startswith('https://pornenix.com'):
			return 'https://www.wetsins.com'
		if url.startswith('https://www.pornohammer.com'):
			return 'https://www.pornohammer.com'
		if url.startswith('https://hello.porn'):
			return 'https://hello.porn'
		if url.startswith('https://everycamgirl.com'):
			return 'https://everycamgirl.com'
		if url.startswith('https://www.masturbate2gether.com'):
			return 'https://www.masturbate2gether.com'
		if url.startswith('https://cam-sex.net'):
			return 'https://cam-sex.net'
		if url.startswith('https://anacams.com'):
			return 'https://anacams.com'
		if url.startswith('https://mustjav.com'):
			return 'https://mustjav.com'
		if url.startswith('https://fullxcinema.com'):
			return 'https://fullxcinema.com'
		if url.startswith('https://teenxy.com'):
			return 'https://teenxy.com'
		if url.startswith('https://warddogs.com'):
			return 'https://warddogs.com'
		if url.startswith('https://anyporn.com'):
			return 'https://anyporn.com'
		if url.startswith('https://anysex.com/'):
			return 'https://anysex.com/'
		if url.startswith(('http://www.flyflv.com', 'https://www.flyflv.com')):
			return 'https://www.flyflv.com'
		if url.startswith(('http://www.xtube.com', 'https://www.xtube.com', 'https://xtube.com')):
			return 'https://vidlox.tv'
		if url.startswith(('http://xxxkingtube.com', 'https://xxxkingtube.com')):
			return 'https://xxxkingtube.com'
		if url.startswith(('http://www.vivatube.com', 'https://www.vivatube.com', 'https://vivatube.com')):
			return 'https://vivatube.com'
		if url.startswith('https://www.empflix.com'):
			return 'https://www.empflix.com'
		if url.startswith('https://www.camwhoresbay.com'):
			return 'https://www.camwhoresbay.com'
		if url.startswith('https://tik.porn'):
			return 'https://tik.porn'
		if url.startswith('https://teenager365.to'):
			return 'https://teenager365.to'
		if url.startswith('https://shareanynudes.com'):
			return 'https://shareanynudes.com'
		if url.startswith('https://24porn.com'):
			return 'https://24porn.com'
		if url.startswith('https://adultxhub.com'):
			return 'https://adultxhub.com'
		if url.startswith('https://analpornosex.com'):
			return 'https://analpornosex.com'
		if url.startswith('https://asianporn.life'):
			return 'https://asianporn.life'
		if url.startswith('https://www.videosdemadurasx.com'):
			return 'https://www.videosdemadurasx.com'
		if url.startswith('https://bigtitsxl.com'):
			return 'https://bigtitsxl.com'
		if url.startswith('https://bigbumbabes.com'):
			return 'https://bigbumbabes.com'
		if url.startswith('https://desiresxl.com'):
			return 'https://desiresxl.com'
		if url.startswith('https://avexxx.com'):
			return 'https://avexxx.com'
		if url.startswith('https://cherrygasp.com'):
			return 'https://cherrygasp.com'
		if url.startswith('https://18tokyo.com'):
			return 'https://18tokyo.com'
		if url.startswith('https://ebonyplayz.com'):
			return 'https://ebonyplayz.com'
		if url.startswith('https://japanesematures.com'):
			return 'https://japanesematures.com'
		if url.startswith('https://fukxl.com'):
			return 'https://fukxl.com'
		if url.startswith('https://hornyfap.tv'):
			return 'https://hornyfap.tv'
		if url.startswith('https://lesb8.com'):
			return 'https://lesb8.com'
		if url.startswith('https://www.shemaletubevideos.com'):
			return 'https://www.shemaletubevideos.com'
		if url.startswith('https://morehardporn.com'):
			return 'https://morehardporn.com'
		if url.startswith('https://www.porntry.com'):
			return 'https://www.porntry.com'
		if url.startswith('https://pornx.to'):
			return 'https://pornx.to'
		if url.startswith('https://redporn.porn'):
			return 'https://redporn.porn'
		if url.startswith('https://throatlust.com'):
			return 'https://throatlust.com'
		if url.startswith('https://zzztube.tv'):
			return 'https://zzztube.tv'
		if url.startswith('https://spankbang.com'):
			return 'https://spankbang.com'
		if 'freeomovie.to' in url:
			return 'https://www.freeomovie.to'
		if url.startswith('https://www.amateurdoporn.com'):
			return 'https://www.amateurdoporn.com'
		if url.startswith('https://beeg.com'):
			return 'https://beeg.com'
		if url.startswith('https://www.tokyomotion.net'):
			return 'https://www.tokyomotion.net'
		if url.startswith('https://hentai-moon.com'):
			return 'https://hentai-moon.com'
		if url.startswith('https://hentai2w.com'):
			return 'https://hentai2w.com'
		if url.startswith('https://www.hentaicity.com'):
			return 'https://www.hentaicity.com'

		if url.startswith(('https://anybunny.org', 'https://anybunny.com')):
			return 'https://anybunny.org'
		for site in TXXX_NETWORK_SITES:
			if url.startswith(site + '/'):
				return site
		if re.match(r'https://v[0-9]+\.erome\.com/', url):
			return 'https://www.erome.com'
		for site in LIVECAM_SITES + KVS_SITES + WPTUBE_SITES + ('https://en.luxuretv.com', 'https://beta.xfreehd.com', 'https://321tube.com', 'https://alpenrammler.com'):
			if url.startswith(site + '/'):
				return site
		return self.MAIN_URL

	def _parse_base64_m3u8(self, url, cookie_name):
		"""Handler for base64-encoded URLs with M3U8 playlist support"""
		COOKIEFILE = join(GetCookieDir(), cookie_name)
		self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
		self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
		sts, data = self._getPage(url, self.defaultParams)
		if not sts:
			return ''
		EncodedUrl = re.search('-hstyle=["]([^@]+?)["]', data).group(1)
		printDBG('ENCODEDURL: ' + str(EncodedUrl))
		videoUrl = base64.b64decode(EncodedUrl)
		videoUrl = videoUrl.decode("utf-8")
		videoUrl = videoUrl.replace("b'", "").replace("'", "")
		printDBG('DECODEDURL: ' + str(videoUrl))
		if 'm3u8' in videoUrl:
			tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
			for item in tmp:
				printDBG('M3U8 End: ' + item['url'])
				return item['url']
		printDBG('End: ' + videoUrl)
		return videoUrl

	def _parse_embedUrl(self, url, cookie_name):
		"""Handler for embedUrl pattern with double-fetch extraction"""
		COOKIEFILE = join(GetCookieDir(), cookie_name)
		self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
		self.HTTP_HEADER['Referer'] = url
		self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
		sts, data = self.get_Page(url, self.defaultParams)
		if not sts:
			return ''
		EmbedUrl = self.cm.ph.getSearchGroups(data, '''embedUrl":.["']([^"^']+?)["]''', 1, True)[0]
		printDBG('Embed URL: ' + EmbedUrl)
		EmbedUrl = checkhttps(EmbedUrl)
		sts, data = self.get_Page(EmbedUrl)
		if not sts:
			return ''
		videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"]+?)['"].ty.+mp4''', 1, True)[0]
		videoUrl = checkhttps(videoUrl)
		printDBG('Final videolink: ' + videoUrl)
		return videoUrl

	def getResolvedURL(self, url):
		printDBG('Host getResolvedURL begin')
		printDBG('Host getResolvedURL url: ' + url)
		videoUrl = ''
		parser = self.getParser(url)
		printDBG('Host getResolvedURL parser: ' + parser)

		if 'gounlimited.to' in url and 'embed' not in url:
			url = 'https://gounlimited.to/embed-{0}.html'.format(url.split('/')[3])

		if parser == 'https://letsporn.com':
			printDBG('LETSPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'letsporn.cookie')
			self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.HTTP_HEADER['User-Agent'] = self.USER_AGENT
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True, 'timeout': 15}
			sts, data = self.getPage(url, 'letsporn.cookie', 'letsporn.com', self.defaultParams)
			if not sts or not data:
				printDBG('LETSPORN: page load failed')
				return ''

			def clean(value):
				value = (value or '').strip().replace('\\/', '/').replace('\\u002F', '/').replace('\\u002f', '/').replace('\\u003A', ':').replace('\\u003a', ':').replace('&amp;', '&')
				if value.startswith('//'):
					return 'https:' + value
				if value.startswith('/'):
					return urljoin(url, value)
				return value

			def valid(value):
				v = value.lower()
				if not v.startswith('http'):
					return False
				if any(x in v for x in ('/contents/videos_screenshots/', '.jpg', '.jpeg', '.png', '.webp', '.vtt')):
					return False
				return '.mp4' in v or '.m3u8' in v or '/stream/' in v or '/video/' in v

			def first_valid(candidates):
				for item in candidates:
					candidate = clean(item)
					if valid(candidate):
						return candidate
				return ''

			anyMedia = r'''["']((?:https?:)?//[^"'\s<>]+?\.(?:mp4|m3u8)(?:\?[^"'\s<>]*)?)["']'''
			# video_url is 480p, video_alt_url 720p
			videoUrl = first_valid([self._pickByHeight(self._mediaCandidates(data))])
			for pat in () if videoUrl else (r'''["']video_url["']\s*[:=]\s*["']([^"']+)["']''',
						r'''\bvideo_url\s*[:=]\s*["']([^"']+)["']''',
						r'''["']videoUrl["']\s*[:=]\s*["']([^"']+)["']''',
						r'''\bvideoUrl\s*[:=]\s*["']([^"']+)["']''',
						r'''["']file["']\s*[:=]\s*["']([^"']+)["']''',
						r'''\bfile\s*[:=]\s*["']([^"']+\.(?:mp4|m3u8)(?:\?[^"']*)?)["']''',
						r'''<source[^>]+src=["']([^"']+\.(?:mp4|m3u8)(?:\?[^"']*)?)["']''',
						r'''contentUrl["']?\s*[:=]\s*["']([^"']+\.(?:mp4|m3u8)(?:\?[^"']*)?)["']''',
						anyMedia):
				videoUrl = first_valid(re.findall(pat, data, re.I | re.S))
				if videoUrl:
					break
			if not videoUrl:
				embed = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=["']([^"']+?)["']''', 1, True)[0]
				if embed:
					embed = clean(embed)
					printDBG('LETSPORN iframe: ' + embed)
					sts2, data2 = self.getPage(embed, 'letsporn.cookie', 'letsporn.com', self.defaultParams)
					if sts2 and data2:
						videoUrl = first_valid(re.findall(anyMedia, data2, re.I))
			if videoUrl:
				printDBG('LETSPORN video URL: ' + videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})
			printDBG('LETSPORN: no video URL found')
			return ''

		if parser == 'mjpg_stream':
			try:
				stream = urlopen(url, timeout=15)
				# raw bytes: b'' literals are plain str on Python 2, bytes on Python 3
				_bytes = b''
				while True:
					chunk = stream.read(1024)
					if not chunk:
						break  # stream ended without a complete frame
					_bytes += chunk
					a = _bytes.find(b'\xff\xd8')  # JPEG start marker
					if a == -1:
						_bytes = _bytes[-1:]  # keep one byte, the marker may be split across two reads
						continue
					b = _bytes.find(b'\xff\xd9', a + 2)  # end marker of *this* frame
					if b == -1:
						_bytes = _bytes[a:]  # drop what precedes the frame start
						if len(_bytes) > 2 * 1024 * 1024:
							break  # no end marker in sight, give up
						continue
					jpg = _bytes[a:b + 2]
					snapshotFile = GetTmpDir('obraz.jpg')
					with open(snapshotFile, 'wb') as titleFile:
						titleFile.write(jpg)
						return 'file://' + snapshotFile
			except Exception:
				pass
			return ''

		self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

		if parser == 'https://www.porntrex.com':
			COOKIEFILE = join(GetCookieDir(), 'porntrex.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'headers': {'User-Agent': USER_AGENT, 'Referer': url, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Connection': 'keep-alive', }}
			sts, data = self.getPage(url, 'porntrex.cookie', 'porntrex.com', self.defaultParams)
			if not sts:
				return ''
			if 'video is a private' in data:
				SetIPTVPlayerLastHostError(_('This video is a private.'))
				return []
			# video_url / video_alt_urlN (+ _text labels): the slots shift per video (alt_url3 is 2160p on one, 1080p on another)
			texts = dict(re.findall(r"(video_url|video_alt_url[0-9]*)_text\s*:\s*['\"]([^'\"]*)['\"]", data))
			candidates = []
			for key, value in re.findall(r"(video_url|video_alt_url[0-9]*)\s*:\s*['\"]([^'\"]+)['\"]", data):
				if value.startswith('http'):
					candidates.append((self._labelHeight(texts.get(key, '') + ' ' + value), value))
			videoPage = self._pickByHeight(candidates)
			if videoPage:
				printDBG('Host videoPage: ' + videoPage)
				return strwithmeta(videoPage, {'Referer': url})
			return ''

		if parser == 'https://www.pornoxo.com':
			printDBG('PORNOXO PARSER STARTED')
			COOKIEFILE = join(GetCookieDir(), 'pornoxo.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornoxo.cookie', 'pornoxo.com', self.defaultParams)
			if not sts:
				return ''
			hlsUrl = self.cm.ph.getSearchGroups(data, '''"hlsAuto":"([^"]+)"''')[0].replace(r'\/', '/')
			if hlsUrl:
				# the master playlist URL ends in _TPL_.mp4, so skip the extension check
				tmp = getDirectM3U8Playlist(strwithmeta(hlsUrl, {'Referer': url}), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
				if tmp:
					return tmp[0]['url']
				return strwithmeta(hlsUrl, {'iptv_proto': 'm3u8', 'Referer': url})
			videoUrl = re.search('sources.{,6}src":"([^"]+)","d', data)
			if not videoUrl:
				return ''
			videoUrl = videoUrl.group(1).replace(r'\/', '/')
			printDBG('Link a video: ' + str(videoUrl))
			return unquote(videoUrl)

		if parser == 'https://www.hclips.com':
			COOKIEFILE = join(GetCookieDir(), 'hclips.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'hclips.cookie', 'hclips.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url.+['"]([^"^']+?)['"],"''')[0]
			printDBG('Fetched url: ' + videoUrl)
			replacemap = {'M': '\\u041c', 'A': '\\u0410', 'B': '\\u0412', 'C': '\\u0421', 'E': '\\u0415', '=': '~', '+': '.', '/': ','}
			for key in replacemap:
				videoUrl = videoUrl.replace(replacemap[key], key)
			printDBG('New url: ' + videoUrl)
			videoUrl = base64.b64decode(videoUrl)
			videoUrl = videoUrl.decode("utf-8")
			printDBG('Decoded address: ' + videoUrl)
			videoUrl = checkhttps(videoUrl)
			if videoUrl.startswith('/'):
				videoUrl = 'https://hclips.com' + videoUrl
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://mompornonly.com':
			return self._parse_base64_m3u8(url, 'mompornonly.cookie')

		if parser == 'https://lecoinporno.fr':
			return self._parse_base64_m3u8(url, 'lecoinporno.cookie')

		if parser == 'https://emturbovid.com':
			COOKIEFILE = join(GetCookieDir(), 'emturbovid.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			videoUrl = self.cm.ph.getSearchGroups(data, '''urlPlay.+?['"]([^"^']+?)['"];''')[0]
			printDBG('End Link: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://streamwish.to':
			COOKIEFILE = join(GetCookieDir(), 'streamwish.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self._getPage(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''sources.+?['"]([^"^']+?)['"].+?,''')[0]
			printDBG('End Link: ' + str(videoUrl))
			return videoUrl

		if parser == 'http://pornvideos4k.com/en':  # NOSONAR - site deactivated, kept for possible future reactivation
			COOKIEFILE = join(GetCookieDir(), 'pornvideos4k.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self._getPage(url, self.defaultParams)
			if not sts:
				return ''
			phUrl = self.cm.ph.getDataBeetwenMarkers(data, "<video id='my-video' ><source src='", "' type='video/mp4", False)[1]
			phUrl = 'https:' + phUrl
			printDBG('End: ' + str(phUrl))
			return phUrl

		if parser == 'https://tubepornclassic.com':
			COOKIEFILE = join(GetCookieDir(), 'tubepornclassic.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'tubepornclassic.cookie', 'tubepornclassic.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = ph.search(data, '''video_url":"([^"]+?)"''')[0]
			replacemap = {'M': '\\u041c', 'A': '\\u0410', 'B': '\\u0412', 'C': '\\u0421', 'E': '\\u0415', '=': '~', '+': '.', '/': ','}
			for key in replacemap:
				videoUrl = videoUrl.replace(replacemap[key], key)
			videoUrl = base64.b64decode(videoUrl)
			# py3: bytes - str(bytes) left a trailing ' on the URL
			if not isinstance(videoUrl, str):
				videoUrl = videoUrl.decode('utf-8', 'ignore')
			printDBG('After decoding: ' + videoUrl)
			videoUrl = checkhttps(videoUrl)
			if videoUrl.startswith('/'):
				videoUrl = 'https://tubepornclassic.com' + videoUrl
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.alohatube.com':
			COOKIEFILE = join(GetCookieDir(), 'alohatube.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'alohatube.cookie', 'alohatube.com', self.defaultParams)
			if not sts:
				return ''
			printDBG('Video data: ' + url)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, '"contentUrl": "', '"', False)[1]
			videoUrl = videoUrl.replace(r'\/', '/')
			printDBG('Alohatube Link:' + videoUrl)
			return videoUrl

		if parser == 'https://xbabe.com':
			sts, data = self.get_Page(url)
			Urls = self.cm.ph.getDataBeetwenMarkers(data, '<video id="', 'is_mobile', False)[1]
			videoUrls = self.cm.ph.getAllItemsBeetwenMarkers(Urls, 'src="', '" title', False)
			videoUrl = videoUrls[-1]
			return videoUrl

		if parser == 'https://showup.tv':
			COOKIEFILE = join(GetCookieDir(), 'showup.cookie')
			try:
				data = self.cm.getURLRequestData({'url': url, 'use_host': False, 'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True})
			except Exception:
				printDBG('Host getResolvedURL query error url: ' + url)
				return ''
			parse = re.search("var srvE = '(.*?)'", data, re.S)
			if parse:
				printDBG('Host Url: ' + url)
				printDBG('Host rtmp: ' + parse.group(1))
			startChildBug = re.search(r"startChildBug\(user\.uid, '', '([\s\S]+?)'", data, re.I)
			if startChildBug:
				import websocket
				s = startChildBug.group(1)
				printDBG('Host startChildBug: ' + s)
				ip = ''
				t = re.search(r"(.*?):(.*?)", s, re.I)
				if t.group(1) == 'j12.showup.tv':
					ip = '94.23.171.122'
				if t.group(1) == 'j13.showup.tv':
					ip = '94.23.171.121'
				if t.group(1) == 'j11.showup.tv':
					ip = '94.23.171.115'
				if t.group(1) == 'j14.showup.tv':
					ip = '94.23.171.120'
				printDBG('Host IP: ' + ip)
				port = s.replace(t.group(1) + ':', '')
				printDBG('Host Port: ' + port)
				modelName = url.replace('https://showup.tv/', '')
				printDBG('Host modelName: ' + modelName)

				wsURL1 = 'ws://' + s
				wsURL2 = 'ws://' + ip + ':' + port
				printDBG('Host wsURL1: ' + wsURL1)
				printDBG('Host wsURL2: ' + wsURL2)
				ws = websocket.create_connection(wsURL2)

				zapytanie = '{ "id": 0, "value": ["", ""]}'
				printDBG('Host zapytanie1: ' + zapytanie)
				ws.send(zapytanie)
				result = ws.recv()
				printDBG('Host result1: ' + result)

				zapytanie = '{ "id": 2, "value": ["%s"]}' % modelName
				printDBG('Host zapytanie2: ' + zapytanie)
				ws.send(zapytanie)
				result = ws.recv()
				printDBG('Host result2: ' + result)

				playpath = re.search(r'value":\["(.*?)"', result)

				if playpath:
					Checksum = playpath.group(1)
					if len(Checksum) < 30:
						privateMsg = ''
						for _x in range(1, 10):
							ws.send(zapytanie)
							result = ws.recv()
							czas = re.search(r'(\d+)\[:\](\d+)\[', result)
							if czas:
								printDBG('Host time group(1): ' + czas.group(1))
								printDBG('Host time group(2): ' + czas.group(2))
								czas = int(czas.group(1)) - int(czas.group(2))
								printDBG('Host a: ' + str(czas))
								if czas <= 0:
									privateMsg = _('PRIVATE - wait a few seconds')
								else:
									privateMsg = _('PRIVATE - wait %s seconds') % czas
								break
						if privateMsg:
							Checksum = privateMsg
						elif Checksum == '' or Checksum == 'failure':
							Checksum = _('OFFLINE')
						ws.close()
						SetIPTVPlayerLastHostError(Checksum)
						return []
					videoUrl = 'rtmp://cdn-t0.showup.tv:1935/webrtc/' + Checksum + '_aac'  # token=fake'
					ws.close()
					try:
						for x in range(1, 9):
							cmd = '/usr/bin/rtmpdump -B 1 -r "%s"' % videoUrl.replace('cdn-t0', 'cdn-t0' + str(x))
							wow = subprocess.getoutput(cmd)
							printDBG('HostXXX cmd > ' + cmd)
							if 'StreamNotFound' not in wow:
								return videoUrl.replace('cdn-t0', 'cdn-t0' + str(x)) + ' live=1'
							printDBG('HostXXX GUZIK ')
					except Exception:
						printDBG('HostXXX error commands.getoutput ')
					return videoUrl.replace('cdn-t0', 'cdn-t01') + ' live=1'

			return ''

		if parser == 'https://pl.bongacams.com':
			printDBG('Host url: ' + url)
			username = url
			printDBG('Host username: ' + username)
			COOKIEFILE = join(GetCookieDir(), 'bongacams.cookie')
			header = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/json', 'Accept-Language': 'en,en-US;q=0.7,en;q=0.3', 'Referer': 'https://en.bongacams.com/' + username, 'Origin': 'https://en.bongacams.com'}
			self.defaultParams = {'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True}
			sts, data = self.cm.getPage('https://en.bongacams.com/' + username, self.defaultParams)
			if not sts:
				return ''
			amf = self.cm.ph.getSearchGroups(data, r'''MobileChatService\(\'\/([^"^']+?)\'\+\$''')[0]
			if not amf:
				amf = 'tools/amf.php?x-country=pl&m=1&res='
			url_amf = 'https://en.bongacams.com/' + amf + str(random.randint(2100000, 3200000))
			printDBG('Host url_amf: ' + url_amf)
			postdata = {'method': 'getRoomData', 'args[]': username}
			header = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml,application/json', 'Accept-Language': 'en,en-US;q=0.7,en;q=0.3', 'X-Requested-With': 'XMLHttpRequest', 'Referer': 'https://en.bongacams.com/' + username, 'Origin': 'https://en.bongacams.com'}
			self.defaultParams = {'url': url_amf, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': True, 'return_data': True}
			sts, data = self.cm.getPage(url_amf, self.defaultParams, postdata)
			if not sts:
				return ''
			server = self.cm.ph.getSearchGroups(data, '''"videoServerUrl":['"]([^"^']+?)['"]''', 1, True)[0]
			printDBG('Parser Bonga server: ' + server)
			url_m3u8 = 'https:' + server.replace(r'\/', '/') + '/hls/stream_' + username + '/playlist.m3u8'
			if server:
				videoUrl = urlparser.decorateUrl(url_m3u8, {'User-Agent': USER_AGENT, 'Referer': 'https://bongacams.com/' + username})
				if self.cm.isValidUrl(videoUrl):
					tmp = getDirectM3U8Playlist(videoUrl)
					try:
						tmp = sorted(tmp, key=lambda item: int(item.get('bitrate', '0')))
					except Exception:
						pass
					for item in tmp:
						printDBG('Host listsItems valtab: ' + str(item))
					try:
						return '' if item['bitrate'] == 'unknown' else item['url']
					except Exception:
						pass
			return ''

		if parser == 'https://faapy.com':
			printDBG('FAAPY PARSER')
			COOKIEFILE = join(GetCookieDir(), 'faapy.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			params = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True, 'timeout': 15}
			sts, pageData = self.getPage(url, 'faapy.cookie', 'faapy.com', params)
			if not sts:
				return ''
			# the /get_file/ MP4 only plays with the session cookie of this video page
			try:
				cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
			except Exception:
				printExc()
				cookieHeader = ''

			# Try the player iframe when the video page exposes one.  If the
			# iframe itself returns 404, keep the original video-page HTML and
			# continue searching it for a real source.
			data = pageData
			embed = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src=["\']([^"\']*(?:/embed/|embed/)[^"\']*)["\']', 1, True)[0]
			if embed:
				embed = embed.replace('\\/', '/').strip()
				embed = checkhttps(embed)
				if embed.startswith('/'):
					embed = 'https://faapy.com' + embed
				sts2, data2 = self.getPage(embed, 'faapy.cookie', 'faapy.com', params)
				if sts2 and data2:
					data = data2

			# Search both player HTML and the original video page.  FAAPY has
			# used several JS/source formats, so accept direct MP4/M3U8 URLs,
			# JSON file/src fields and escaped URLs.  Never return trailer/preview
			# files or the known generic HCL1 placeholder.
			search_blocks = [data]
			if data is not pageData:
				search_blocks.append(pageData)
			patterns = [
				r'(?:file|src|source|videoUrl|video_url|fileUrl|file_url)\s*[:=]\s*["\']([^"\']+\.(?:mp4|m3u8)(?:[/\?][^"\']*)?)["\']',
				r'(?:file|src|source|videoUrl|video_url|fileUrl|file_url)\\?\s*[:=]\\?\s*["\']([^"\']+\.(?:mp4|m3u8)(?:[/\\?][^"\']*)?)["\']',
				r'<source[^>]+src=["\']([^"\']+\.(?:mp4|m3u8)(?:\?[^"\']*)?)["\']',
				r'(https?://[^"\'\s<>]+\.(?:mp4|m3u8)(?:\?[^"\'\s<>]*)?)',
			]
			for block in search_blocks:
				for pat in patterns:
					for match in re.finditer(pat, block, re.I):
						videoUrl = match.group(1).replace('\\/', '/').replace('\\u0026', '&')
						videoUrl = checkhttps(videoUrl)
						low = videoUrl.lower()
						if 'hcl1 - en.mp4' in low or 'trailer' in low or 'preview' in low:
							continue
						if '.mp4' in low or '.m3u8' in low:
							meta = {'Referer': url, 'Origin': 'https://faapy.com', 'User-Agent': self.HTTP_HEADER.get('User-Agent', USER_AGENT)}
							if cookieHeader:
								meta['Cookie'] = cookieHeader
							return urlparser.decorateUrl(videoUrl, meta)
			return ''

		if parser == 'https://hellporno.com/':
			COOKIEFILE = join(GetCookieDir(), 'hellporno.cookie')
			self.cm.HEADER = {'User-Agent': self.cm.getDefaultHeader()['User-Agent'], 'X-Requested-With': 'XMLHttpRequest'}
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.get_Page(url)
			self.cm.HEADER = None
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"].{8}1080''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"].{8}720''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"].{8}480''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"].{8}360''')[0]
			printDBG('Final URL: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER['User-Agent']})

		if parser == 'https://www.sexmature.xxx':
			return self._parse_embedUrl(url, 'sexmature.cookie')

		if parser == 'https://www.teentuber.xxx':
			return self._parse_embedUrl(url, 'teentuber.cookie')

		if parser == 'https://www.porn7.xxx':
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, r'''<source src=['"]([^"']+?\.mp4[^"']*)['"]''', 1, True)[0] if sts else ''
			return videoUrl.replace('&amp;', '&') if videoUrl else self._parse_embedUrl(url, 'porn7.cookie')

		if parser == 'https://relax-sex.com':
			COOKIEFILE = join(GetCookieDir(), 'relax-sex.cookie')
			printDBG('PARSERURL: ' + url)
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			printDBG('Main URL: ' + str(url))
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"](.+?)['"].{5,15}mp4''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''player.+src=['"](.+?)['"].media''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"](.+?)['"].type.{0,10}mp4''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''&quot;src&quot;:&quot;(https:.*?\.m3u8)&quot;''', 1, True)[0].replace('\\/', '/')
			printDBG('First videolink: ' + videoUrl)
			if '.m3u8' in videoUrl:
				if self.cm.isValidUrl(videoUrl):
					best = self._bestM3U8Variant(videoUrl)  # the first variant of the master was its lowest
					if best:
						return best
			printDBG('Final videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://porcore.com':
			COOKIEFILE = join(GetCookieDir(), 'porcore.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"](.+?)['"]''', 1, True)[0]
			printDBG('MAIN URL: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.al4a.com':
			COOKIEFILE = join(GetCookieDir(), 'al4a.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search('source.src=["]([^$]+?)["].{8,13}mp4', data).group(1)
			printDBG('MAIN URL: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://xxxdan.com':
			COOKIEFILE = join(GetCookieDir(), 'xxxdan.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search("mp4',src:[']([^$]+?)[']", data).group(1)
			printDBG('MAIN URL: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://www.trendyporn.com':
			COOKIEFILE = join(GetCookieDir(), 'trendyporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search('source.src=["]([^$]+?)["].*mp4', data).group(1)
			printDBG('MAIN URL: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://hypnotube.com':
			COOKIEFILE = join(GetCookieDir(), 'hypnotube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			if 'hypnotube.com\\/age-gate' in data or 'hypnotube.com/age-gate' in data:
				# the video page redirects to an access check that its JavaScript passes with a POST of the time zone
				# and languages; the answer releases the session cookie, then the video page loads
				header = dict(self.HTTP_HEADER)
				header.update({'Content-Type': 'application/json', 'Accept': 'application/json', 'Origin': 'https://hypnotube.com', 'Referer': 'https://hypnotube.com/age-gate'})
				params = dict(self.defaultParams, header=header, raw_post_data=True, return_data=True)
				self.cm.getPage('https://hypnotube.com/age-gate?return=%2F', params, json.dumps({'timeZone': 'Europe/Berlin', 'languages': ['de-DE', 'de', 'en']}))
				sts, data = self.get_Page(url, self.defaultParams)
				if not sts:
					return ''
			videoUrl = re.search('source.src=["]([^$]+?)["].*mp4', data)
			if not videoUrl:
				return ''
			videoUrl = videoUrl.group(1)
			printDBG('MAIN URL: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://www.alotporn.com':
			COOKIEFILE = join(GetCookieDir(), 'alotporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self._pickByHeight(self._mediaCandidates(data))
			if not videoUrl:
				videoUrl = re.findall("source.src=[']([^$]+?)['].*mp4", data, re.S)
				videoUrl = videoUrl[-1] if videoUrl else ''
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			if not real_url.startswith('http'):
				return []
			videoUrl = str(real_url)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			return videoUrl

		if parser == 'https://anon-v.com':
			COOKIEFILE = join(GetCookieDir(), 'anon-v.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search("source.src=[']([^$]+?)['].*mp4", data).group(1)
			printDBG('MAIN URL: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://www.mypornhere.com':
			COOKIEFILE = join(GetCookieDir(), 'mypornhere.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search('source.src=["]([^$]+?)["].*mp4', data).group(1)
			if videoUrl.startswith('/'):
				videoUrl = 'https://www.mypornhere.com' + videoUrl
			printDBG('MAIN URL: ' + str(videoUrl))
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.camhub.cc':
			printDBG('START PARSING: ' + url)
			COOKIEFILE = join(GetCookieDir(), 'camhub.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'camhub.cookie', 'camhub.cc', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			printDBG('LICENSE: ' + license_code)
			if not license_code or license_code == '':
				printDBG('NO LICENSE, STARTING BRANCH:')
				embedUrl = re.search('<iframe.*?src=["]([a-z:/.?=0-9]+?)["]', data).group(1)
				printDBG('EMBEDDED URL: ' + url)
				sts, data = self.get_Page(embedUrl)
				if not sts:
					return ''
				embedUrl = re.search('link.href=["]([^@]+?)["]', data).group(1)
				printDBG('EMBEDURL 2: ' + embedUrl)
				sts, data = self.get_Page(embedUrl)
				if not sts:
					return ''
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			printDBG('LICENSE 2: ' + license_code)
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			return videoUrl if videoUrl else ''

		if parser == 'https://babes34.me':
			COOKIEFILE = join(GetCookieDir(), 'babes34.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"](.+?)['"].{5,15}mp4''', 1, True)[0]
			printDBG('Final videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://pornbolt.com':
			COOKIEFILE = join(GetCookieDir(), 'pornbolt.cookie')
			url = url.replace('ä', '%C3%A4').replace('ß', '%C3%9').replace('ü', '%C3%BC')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			# the player's <source src='/get_video.php?vid=..' type='application/x-mpegURL'> answers with the HLS master
			# (1080p/720p...); the page's other <source type="video/mp4"> is a channel promo clip (315x300_1.)
			master = self.cm.ph.getSearchGroups(data, r'''<source\s+src=['"]([^"']+?)['"]\s+type=['"]application/x-mpegURL''', 1, True)[0]
			if master:
				return self._bestM3U8Variant(urlparser.decorateUrl(urljoin(url, master), {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')}), checkExt=False)
			videoUrl = self.cm.ph.getSearchGroups(data, r'''<video[^>]+id=['"]video['"][\s\S]*?<source[^>]+src=['"]([^"']+?\.mp4[^"']*)['"]''', 1, True)[0]
			printDBG('Final videolink: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if videoUrl else ''

		if parser == 'https://www.wetsins.com':
			COOKIEFILE = join(GetCookieDir(), 'uniparser.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''Quality.*src=['"](.+?)['"].{10,16}mp4''', 1, True)[0]
			if not videoUrl:
				EmbedUrl = self.cm.ph.getSearchGroups(data, '''iframe.{1,20}src=['"](.+?)['"]''', 1, True)[0]
				sts, data2 = self.get_Page(EmbedUrl)
				if not sts:
					return ''
				videoUrl = self.cm.ph.getSearchGroups(data2, '''source.src=['"](.+?)['"]''', 1, True)[0]
			printDBG('Final videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.pornohammer.com':
			COOKIEFILE = join(GetCookieDir(), 'uniparser.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"](.+?)['"].{10,16}mp4''', 1, True)[0]
			if not videoUrl:
				EmbedUrl = self.cm.ph.getSearchGroups(data, '''iframe.src=&quot[;](.+?)[&]quot''', 1, True)[0]
				sts, data2 = self.get_Page(EmbedUrl)
				if not sts:
					return ''
				videoUrl = self.cm.ph.getSearchGroups(data2, '''source.src=['"](.+?)['"]''', 1, True)[-1]
			printDBG('Final videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://xgroovy.com':
			COOKIEFILE = join(GetCookieDir(), 'xgroovy.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"](.+?)['"].{10,16}mp4''', 1, True)[0]
			printDBG('Final videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://xxxshake.com':
			COOKIEFILE = join(GetCookieDir(), 'xxxshake.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			match = re.findall('src=["]([^"]+?)["].type="video/mp4', data, re.S)
			if match:
				return urlparser.decorateUrl(match[0], {'Referer': url})
			else:
				printDBG('Found nothing.')

		if parser == 'xxxlist.txt':
			videoUrls = self.getLinksForVideo(url)
			if videoUrls:
				for item in videoUrls:
					Url = item['url']
					Name = item['name']
					printDBG('Host url: ' + Url)
					return Url
			return ''

		if parser == 'https://www.redtube.com':
			COOKIEFILE = join(GetCookieDir(), 'redtube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''

			hlsUrl = re.search('hls","videoUrl":["]([^"]+?)["]', data).group(1).replace(r"\/", "/")
			if hlsUrl:
				hlsUrl = self.MAIN_URL + hlsUrl
				sts, data = self.getPageWithCFBypass(hlsUrl)
				if not sts:
					return ''
				streams = re.findall('videoUrl":["]([^"]+?)["]', data)
				printDBG("STREAMS: " + str(streams))
				videoUrl = streams[-1].replace(r"\/", "/")
				return videoUrl

		if parser == 'https://www.tube8.com/embed/':
			return self.getResolvedURL(url.replace(r"embed/", r""))

		if parser == 'https://www.tube8.com':
			COOKIEFILE = join(GetCookieDir(), 'tube8.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			printDBG('Videolink: ' + url)
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			headUrl = self.cm.ph.getSearchGroups(data, '''mp4.+videoUrl['"]:['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			printDBG('Video page: ' + headUrl)
			sts, data = self.get_Page(headUrl)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''videoUrl.+?['"]([^"^']+?)['"]''')[0].replace('%3D', '=').replace(r"\/", "/")
			printDBG('Ready link: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.4tube.com':
			COOKIEFILE = join(GetCookieDir(), '4tube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}

			# Current 4TUBE video cards use /out/?l=... links. The l parameter
			# is base64-wrapped binary data which still contains the real source
			# URL as plain text. Do not fetch /out/ itself: that endpoint is an
			# advertising/redirect wrapper and is not the old player JSON.
			if '/out/' in url:
				try:
					query = parse_qs(urlsplit(url).query)
					lparam = query.get('l', [''])[0]
					if lparam:
						try:
							decoded = base64.b64decode(lparam + '===')
						except Exception:
							decoded = b''
						text = decoded.decode('utf-8', 'ignore') if decoded else ''
						printDBG('4TUBE decoded redirect data: ' + text[:1000])
						targets = re.findall(r'https?://[^\"\'\s<>]+', text)
						for target in targets:
							# The binary redirect payload continues after the real URL with
							# control bytes (metadata). Strip those bytes before handing the
							# target to another parser; otherwise urllib raises InvalidURL.
							target = re.split(r'[\x00-\x1f]', target, maxsplit=1)[0]
							target = target.rstrip('\\').replace(r'\/', '/')
							if not target:
								continue
							printDBG('4TUBE source target: ' + target)
							if re.search(r'\.(?:mp4|m3u8)(?:\?|$)', target, re.I):
								return target
							try:
								retTab = self.up.getVideoLinkExt(target)
								for item in retTab or []:
									if isinstance(item, dict) and item.get('url'):
										resolvedUrl = item['url']
										# Some external parsers return the page URL unchanged.
										# Accept only an actual media URL here; otherwise continue
										# with the direct-media extraction below.
										if re.search(r'\.(?:mp4|m3u8)(?:\?|$)', resolvedUrl, re.I):
											printDBG('4TUBE resolved external media: ' + resolvedUrl)
											return resolvedUrl
							except Exception:
								printExc()
							try:
								if self.getParser(target) not in ('', 'https://www.4tube.com'):
									resolved = self.getResolvedURL(target)
									if isinstance(resolved, basestring) and re.search(r'\.(?:mp4|m3u8)(?:\?|$)', resolved, re.I):
										return resolved
							except Exception:
								printExc()
							try:
								sts, page = self.get_Page(target)
								if sts and page:
									page = page.replace(r'\/', '/').replace('\\u0026', '&')
									patterns = [
										r'contentUrl\s*[=:]\s*[\"\'](https?://[^\"\']+)',
										r'(?:videoUrl|video_url|file|src)\s*[=:]\s*[\"\'](https?://[^\"\']+)',
										r'https?://[^\"\'\s<>]+\.(?:mp4|m3u8)(?:\?[^\"\'\s<>]*)?',
									]
									for pat in patterns:
										media = re.findall(pat, page, re.I)
										for mediaUrl in reversed(media):
											# the token URL of the sponsor's CDN sits in the HTML with "&amp;" and only answers with the sponsor
											# site as Referer (403 otherwise)
											mediaUrl = mediaUrl.rstrip('\\').replace('&amp;', '&')
											if re.search(r'\.(?:mp4|m3u8)(?:\?|$)', mediaUrl, re.I):
												printDBG('4TUBE direct media fallback: ' + mediaUrl)
												return urlparser.decorateUrl(mediaUrl, {'Referer': target, 'User-Agent': USER_AGENT})
							except Exception:
								printExc()
				except Exception:
					printExc()
				# All decode/resolve attempts above failed - this /out/ card has no
				# extractable video (often an ad/affiliate redirect to a partner site's
				# landing page, e.g. ersties.com, with nothing to play behind it).
				# Do not fall through to the legacy INITIALSTATE parser below: it expects
				# an old-style 4TUBE watch page, not an /out/ redirect wrapper, so it would
				# just re-fetch this same URL and fail again with a confusing traceback.
				return ''

			sts, data = self.get_Page(url)
			if not sts:
				return ''
			domena = url.split('/')[2].replace('www.', '')
			videoID = re.findall(r'data-id=[\"\'](\d+)[\"\'].*?data-quality=[\"\'](\d+)[\"\']', data, re.S)
			try:
				init = self.cm.ph.getSearchGroups(data, r"window\.INITIALSTATE\s*?=\s*?[\"']([^\"']+?)[\"']", 1, True)[0]
				init = unquote(base64.b64decode(init))
				result = byteify(json.loads(init)['page'])
				videoID = result['video']['mediaId']
				res = ''
				for item in result['video']['encodings']:
					res += str(item['height']) + '+'
				res = res.rstrip('+')
				posturl = "https://token.%s/0000000%s/desktop/%s" % (domena, videoID, res)
				printDBG('Host getResolvedURL posturl: ' + posturl)
				sts, tokenData = self.get_Page(posturl)
				if not sts:
					return ''
				videoUrl = re.findall(r'token\":\"(.*?)\"', tokenData, re.S)
				if videoUrl:
					return videoUrl[-1]
			except Exception:
				printExc()
			if videoID:
				res = ''.join(x[1] + '+' for x in videoID).rstrip('+')
				posturl = "https://token.%s/0000000%s/desktop/%s" % (domena, videoID[-1][0], res)
				printDBG('Host getResolvedURL posturl: ' + posturl)
				sts, tokenData = self.get_Page(posturl)
				if not sts:
					return ''
				videoUrl = re.findall(r'token\":\"(.*?)\"', tokenData, re.S)
				if videoUrl:
					return videoUrl[-1]
			return ''

		if parser == 'https://zbporn.com':
			COOKIEFILE = join(GetCookieDir(), 'zbporn.cookie')
			header = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
			try:
				data = self.cm.getURLRequestData({'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True})
			except Exception:
				printDBG('Host getResolvedURL query error url: ' + url)
				return ''
			return self._pickByHeight(self._mediaCandidates(data)) or self.cm.ph.getDataBeetwenMarkers(data, "video_url: '", "',", False)[1]

		if parser == 'https://www.txxx.com':
			COOKIEFILE = join(GetCookieDir(), 'txxx.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'txxx.cookie', 'txxx.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search('video_url":"([^"]+)', data).group(1)
			printDBG('Fetched code: ' + videoUrl)
			replacemap = {'M': '\\u041c', 'A': '\\u0410', 'B': '\\u0412', 'C': '\\u0421', 'E': '\\u0415', '=': '~', '+': '.', '/': ','}
			for key in replacemap:
				videoUrl = videoUrl.replace(replacemap[key], key)
			printDBG('TXXX After ReplaceMAP: ' + str(videoUrl))
			videoUrl = base64.b64decode(videoUrl)
			printDBG('Fixed TXXX address: ' + str(videoUrl))
			fakeUrl = str(videoUrl)
			goodUrl = fakeUrl.replace("b'", "").replace("'", "")
			printDBG('Converted TXXX address: ' + goodUrl)
			goodUrl = checkhttps(goodUrl)
			if goodUrl.startswith('/'):
				goodUrl = 'https://txxx.com' + goodUrl
			printDBG('Final TXXX address: ' + goodUrl)
			return urlparser.decorateUrl(goodUrl, {'Referer': url})

		if parser == 'https://www.youporn.com':
			COOKIEFILE = join(GetCookieDir(), 'youporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			self.defaultParams['header']['Referer'] = url
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			result = self.cm.ph.getSearchGroups(data, '''"videoUrl":['"]([^'"]+?)['"]''')[0].replace('&amp;', '&').replace(r"\/", r"/")
			allUrl = result.replace("/api", "https://www.youporn.com/api")
			sts, data = self.get_Page(allUrl)
			hlsUrl = self.cm.ph.getDataBeetwenMarkers(data, 'videoUrl":"', '","', False)[1]
			videoUrl = hlsUrl.replace(r"\/", "/").replace('\\u0026', '&')
			return videoUrl

		if parser == 'https://streamvid.net':
			COOKIEFILE = join(GetCookieDir(), 'streamvid.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			url = url.replace('https://streamvid.net/', 'https://streamvid.net/embed-')
			printDBG('Streamvid url: ' + url)
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			printDBG('Streamvid URL: ' + url)
			preTag_1 = self.cm.ph.getSearchGroups(data, '''pics[|]([^|^']+?)[|]''', 1, True)[0]
			if not preTag_1:
				preTag_1 = self.cm.ph.getSearchGroups(data, '''media[|]([^|^']+?)[|].vvplay''', 1, True)[0]
			if not preTag_1:
				preTag_1 = self.cm.ph.getSearchGroups(data, '''biz[|]([^|^']+?)[|].vvplay''', 1, True)[0]
			if not preTag_1:
				preTag_1 = self.cm.ph.getSearchGroups(data, '''media[|]([^|^']+?)[|].+vvplay''', 1, True)[0]
			printDBG('Pretag1: ' + preTag_1)
			preTag_2 = self.cm.ph.getSearchGroups(data, '''if[|]([^|^']+?)[|]''', 1, True)[0]
			printDBG('Pretag2: ' + preTag_2)
			server = self.cm.ph.getSearchGroups(data, '''[|]([^|^']+?)[|]vvplay''', 1, True)[0]
			if not server:
				server = self.cm.ph.getSearchGroups(data, '''[|]([^|^']+?)[|]https''', 1, True)[0]
			printDBG('Server: ' + server)
			id = self.cm.ph.getSearchGroups(data, '''master.urlset[|]([^"^']+?)[|]hls|sources''', 1, True)[0]
			printDBG('Identifier: ' + id)
			if server == 'streamvid':
				videoUrl = 'https://' + preTag_1 + '.' + server + '.' + preTag_2 + '/hls/' + id + '/index-v1-a1.m3u8'
			if preTag_2 == server:
				videoUrl = 'https://' + server + '.streamvid.net/hls/' + id + '/index-v1-a1.m3u8'
			if preTag_2 == 'biz':
				videoUrl = 'https://' + preTag_1 + '.streamvid.' + preTag_2 + '/hls/' + id + '/index-v1-a1.m3u8'
			if preTag_2 == 'pics':
				videoUrl = 'https://' + server + '.' + preTag_1 + '.' + preTag_2 + '/hls/' + id + '/index-v1-a1.m3u8'
			if preTag_2 == 'n22515y':
				videoUrl = 'https://' + preTag_2 + '.streamvid.net/hls/' + id + '/index-v1-a1.m3u8'
			if preTag_2 == 'media':
				videoUrl = 'https://' + preTag_1 + '.streamvid.' + preTag_2 + '/hls/' + id + '/index-v1-a1.m3u8'
			printDBG('This is the end: ' + videoUrl)
			if '.m3u8' in videoUrl:
				if self.cm.isValidUrl(videoUrl):
					best = self._bestM3U8Variant(videoUrl)  # the first variant of the master was its lowest
					if best:
						return best
			printDBG('Final URL: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.amdahost.com':
			COOKIEFILE = join(GetCookieDir(), 'amdahost.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			printDBG('AMDAHOST url: ' + url)
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"]''', 1, True)[0]
			if videoUrl.startswith('videos'):
				videoUrl = 'https://www.amdahost.com/' + videoUrl
			return videoUrl

		if parser == 'doodstream.com':
			baseUrl = url
			printDBG("parserDOOD baseUrl [%s]" % baseUrl)
			httpParams = {'header': {'User-Agent': USER_AGENT, 'Accept': '*/*', 'Accept-Encoding': 'gzip', 'Referer': baseUrl}, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': GetCookieDir("dood.cookie"), 'max_data_size': 0, 'no_redirection': True}
			urlsTab = []
			if '/d/' in baseUrl:
				baseUrl = baseUrl.replace('/d/', '/e/')
			sts, data = self.cm.getPage(baseUrl, httpParams)
			url = self.cm.meta.get('location', '')
			if url != '':
				baseUrl = url
				httpParams['header']['Referer'] = baseUrl
			del httpParams['max_data_size']
			del httpParams['no_redirection']
			sts, data = self.cm.getPage(baseUrl, httpParams)
			subTracks = []
			tracks = self.cm.ph.getAllItemsBeetwenMarkers(data, '<track', '>', withMarkers=True)
			for track in tracks:
				track_kind = self.cm.ph.getSearchGroups(track, '''kind=['"]([^'^"]+?)['"]''')[0]
				if 'caption' in track_kind:
					srtUrl = self.cm.ph.getSearchGroups(track, '''src=['"]([^'^"]+?)['"]''')[0]
					srtLabel = self.cm.ph.getSearchGroups(track, '''label=['"]([^'^"]+?)['"]''')[0]
					srtFormat = srtUrl[-3:]
					params = {'title': srtLabel, 'url': srtUrl, 'lang': srtLabel.lower()[:3], 'format': srtFormat}
					subTracks.append(params)
			pass_md5_url = self.cm.ph.getSearchGroups(data, r'''; \$.get.['"](.+?)['"],''', 1, True)[0]
			makePlay = self.cm.ph.getSearchGroups(data, r'''(function makePlay\(\) \{.+?\};)''', 1, True)[0]
			if pass_md5_url and makePlay:
				pass_md5_url = self.cm.getFullUrl(pass_md5_url, self.cm.getBaseUrl(url))
				sts, new_url = self.cm.getPage(pass_md5_url, httpParams)
				if sts:
					code = "var url = '%s';\n%s\nconsole.log(url + makePlay());" % (new_url, makePlay)
					ret = js_execute(code)
					newUrl = ret['data'].replace("\n", "")
					if newUrl:
						if subTracks:
							newUrl = urlparser.decorateUrl(newUrl, {'Referer': baseUrl, 'external_sub_tracks': subTracks, 'iptv_format': 'mp4'})
						else:
							newUrl = urlparser.decorateUrl(newUrl, {'Referer': baseUrl, 'iptv_format': 'mp4'})
						params = {'name': 'link', 'url': newUrl}
						urlsTab.append(params)
			return urlsTab

		if parser == 'https://www.playvids.com':
			COOKIEFILE = join(GetCookieDir(), 'playvids.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'playvids.cookie', 'playvids.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''hls-src720=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if '' == videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''hls-src480=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if '' == videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''hls-src360=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				# the hls-src master lists its lowest variant first
				videoUrl = self.FullUrl(videoUrl)
				return self._bestM3U8Variant(urlparser.decorateUrl(videoUrl, {'Referer': url}), checkExt=False) or videoUrl

			videoUrl = self.cm.ph.getSearchGroups(data, '''src720=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				return self.FullUrl(videoUrl)
			videoUrl = self.cm.ph.getSearchGroups(data, '''src480=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				return self.FullUrl(videoUrl)
			videoUrl = self.cm.ph.getSearchGroups(data, '''src360=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''<source\ssrc=['"]([^"']+?)['"]''')[0].replace('&amp;', '&')
				if '.m3u8' in videoUrl:
					# one <source> with the HLS master (.urlset/master.m3u8), lowest variant first
					videoUrl = self.FullUrl(videoUrl)
					return self._bestM3U8Variant(urlparser.decorateUrl(videoUrl, {'Referer': url})) or videoUrl
			return self.FullUrl(videoUrl) if videoUrl else ''

		if parser == 'https://www.tubewolf.com':
			COOKIEFILE = join(GetCookieDir(), 'tubewolf.cookie')
			for _x in range(1, 10):
				self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
				self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
				sts, data = self.get_Page(url)
				if not sts:
					return ''
				data = self.cm.ph.getDataBeetwenMarkers(data, '<video id', '</video>', False)[1]
				videoUrl = self._pickByHeight(self._mediaCandidates(data))
				if videoUrl:
					return videoUrl

		if parser == 'https://www.youjizz.com':
			COOKIEFILE = join(GetCookieDir(), 'youjizz.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return
			videoPage = self.cm.ph.getSearchGroups(data, '''"quality":"1080","filename":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			if videoPage:
				videoPage = checkhttp(videoPage)
				return videoPage.replace("&amp;", "&")
			videoPage = self.cm.ph.getSearchGroups(data, '''"quality":"720","filename":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			if videoPage:
				videoPage = checkhttp(videoPage)
				return videoPage.replace("&amp;", "&")
			videoPage = self.cm.ph.getSearchGroups(data, '''"quality":"480","filename":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			if videoPage:
				videoPage = checkhttp(videoPage)
				return videoPage.replace("&amp;", "&")
			videoPage = self.cm.ph.getSearchGroups(data, '''"quality":"360","filename":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			if videoPage:
				videoPage = checkhttp(videoPage)
				return videoPage.replace("&amp;", "&")
			videoPage = self.cm.ph.getSearchGroups(data, '''"quality":"288","filename":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			if videoPage:
				videoPage = checkhttp(videoPage)
				return videoPage.replace("&amp;", "&")
			videoPage = self.cm.ph.getSearchGroups(data, '''"quality":"270","filename":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			if videoPage:
				videoPage = checkhttp(videoPage)
				return videoPage.replace("&amp;", "&")
			videoPage = self.cm.ph.getSearchGroups(data, '''"filename":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			if videoPage:
				videoPage = checkhttp(videoPage)
				return videoPage.replace("&amp;", "&")
			videoPage = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0]
			if videoPage:
				videoPage = checkhttp(videoPage)
				return videoPage.replace("&amp;", "&")

			error = self.cm.ph.getDataBeetwenMarkers(data, '<p class="text-gray">', '</p>', False)[1]
			if error:
				SetIPTVPlayerLastHostError(_(error))
				return []
			return ''

		if parser == 'https://www.pornhub.com':
			COOKIEFILE = join(GetCookieDir(), 'pornhub.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self._getPage(url, self.defaultParams)
			if not sts:
				return ''
			embedUrl = self.cm.ph.getSearchGroups(data, '''video:url".content=['"]([^"^']+?)['"]./>''', 1, True)[0]
			printDBG('Embedded page: ' + embedUrl)
			sts, data = self.get_Page(embedUrl)
			if not sts:
				return ''
			printDBG('Embedded: ' + embedUrl)
			videoUrl = self.cm.ph.getSearchGroups(data, '''true.+?hls.{13}['"]([^"^']+?)['"]''', 1, True)[0].replace(r"\/", "/")
			printDBG('Video Link: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': 'https://www.pornhub.com/', 'User-Agent': USER_AGENT, 'Origin': 'https://www.pornhub.com'})

		if parser == 'https://chaturbate.com':
			printDBG('Host listsItems Parser-Name= ' + parser)
			COOKIEFILE = join(GetCookieDir(), 'chaturbate.cookie')
			agid_value = 'ag:persönlichen Agid einfügen'
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER.update({'Accept': 'application/json, text/javascript, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest', 'Referer': self.MAIN_URL + '/', 'Accept-Language': 'en-US,en;q=0.9', 'Cookie': 'agid=%s' % agid_value})
			self.defaultParams = {'header': self.HTTP_HEADER, 'cookiefile': COOKIEFILE, 'use_cookie': True, 'save_cookie': True, 'load_cookie': True}
			sts, data = self.get_Page(url, self.defaultParams)
			mainUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{,15}[2]([^"^']+?)[,]''')[0]
			printDBG('HLS URL: ' + mainUrl)
			videoUrl = mainUrl.replace('\\/', '/').replace('\\u002D', '-').replace('\\u002d', '-').replace('\\-', '-').replace('\\u0022', '').replace('\\u003D', '=').replace('\\u003d', '=')
			videoUrl = videoUrl.replace('m3u8\\', 'm3u8')
			printDBG('Korrigierte URL: ' + videoUrl)
			if videoUrl.startswith('//'):
				videoUrl = 'https:' + videoUrl
			if self.cm.isValidUrl(videoUrl):
				metaParams = {'Referer': url, 'Origin': 'https://chaturbate.com', 'iptv_proto': 'm3u8'}
				try:
					tmp = getDirectM3U8Playlist(strwithmeta(videoUrl, metaParams))
					if tmp:
						tmp = sorted(tmp, key=lambda item: int(item.get('bitrate', 0)))
						MAX_BITRATE_1080P = 8000000
						for item in reversed(tmp):
							bitrate = int(item.get('bitrate', 0))
							if bitrate <= MAX_BITRATE_1080P:
								printDBG('1080p MAX: ' + str(bitrate) + ' -> ' + item['url'])
								return urlparser.decorateUrl(item['url'], metaParams)
				except Exception as e:
					printDBG('getDirectM3U8Playlist EXCEPTION: ' + str(e))
			printDBG('Master-URL Fallback')
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'Origin': 'https://chaturbate.com', 'iptv_proto': 'm3u8'})
			return ''

		if parser == 'https://www.xxxbule.com/':
			COOKIEFILE = join(GetCookieDir(), 'xxxbule.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			# the list puts the clip id behind '#': many new clips have no page yet (404), the API needs only the id
			url, _sep, videoId = url.partition('#')
			sizes = '144,240,360,480,720,1080,2160'
			data = ''
			if not videoId:
				sts, data = self._getPage(url, self.defaultParams)
				if not sts:
					return ''
				videoId = self.cm.ph.getSearchGroups(data, '''data-video-id=['"]([0-9]+?)['"]''')[0]
				sizes = self.cm.ph.getSearchGroups(data, '''data-video-sizes=['"]([0-9,]+?)['"]''')[0] or sizes
			if videoId:
				sts, api = self._getPage('https://api.xxxbule.com/hls', self.defaultParams, {'id': videoId, 'sizes': sizes})
				try:
					mp4 = [(self._labelHeight(x.get('title', '')), x['src']) for x in json.loads(api).get('mp4', []) if x.get('src')] if sts else []
				except Exception:
					mp4 = []
				if mp4:
					return urlparser.decorateUrl(self._pickByHeight(mp4), {'Referer': url})
			if not data:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_src".href=['"]([^"^']+?)['"]./>''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''contentUrl":.['"]([^"^']+?)['"]''')[0]
			return videoUrl if videoUrl else ''

		if parser == 'https://www.filmyporno.tv':
			COOKIEFILE = join(GetCookieDir(), 'filmyporno.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			match = re.findall('source src="(.*?)"', data, re.S)
			printDBG('FILMYPORNO MATCH: ' + str(match))
			if match:
				videoUrl = match[0]
				return urlparser.decorateUrl(videoUrl, {'Referer': 'https://www.filmyporno.tv'})
			else:
				return ''

		if parser == 'https://www.porndig.com':
			COOKIEFILE = join(GetCookieDir(), 'porndig.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self._getPage(url, self.defaultParams)
			if not sts:
				return
			playerUrl = self.cm.ph.getSearchGroups(data, r'''src=['"](https://videos\.porndig\.com/player/[^"^']+?)['"]''')[0]
			if not playerUrl:
				return ''
			sts, data = self._getPage(playerUrl, self.defaultParams)
			if not sts:
				return ''
			videoLinks = re.findall(r'"src":"([^"]+?_h264_[^"]+?)"', data.replace('\\/', '/'))
			printDBG('Links: ' + str(videoLinks))
			return videoLinks[0] if videoLinks else ''

		if parser == 'https://www.tnaflix.com':
			COOKIEFILE = join(GetCookieDir(), 'tnaflix.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return
			data = self.cm.ph.getDataBeetwenMarkers(data, 'id="video-player">', 'id="preroll', False)[1]
			sources = data.split('<source')
			if sources:
				del sources[0]
			results = []
			for item in sources:
				url = self.cm.ph.getSearchGroups(item, 'src=["]([^$]+?)["]')[0]
				size = self.cm.ph.getSearchGroups(item, 'size=["]([0-9]+?)["]')[0]
				results.append((url, int(size)))
			results = sorted(results, key=lambda x: x[1], reverse=True)
			sorted_urls = [url for (url, size) in results]
			videoUrl = sorted_urls[0]
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://pornmaki.com':
			COOKIEFILE = join(GetCookieDir(), 'pornmaki.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'file:"', '"};', False)[1]
			return videoUrl if videoUrl else ''

		if parser == 'https://www.moviefap.com':
			COOKIEFILE = join(GetCookieDir(), 'moviefap.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			self.HEADER = {'User-Agent': USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
			self.defaultParams = {'header': dict(self.HEADER)}
			self.defaultParams['header']['Referer'] = url
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return
			xml = self.cm.ph.getSearchGroups(data, '''flashvars.config.*?//([^"^']+?)['"]''')[0]
			if not xml:
				xml = self.cm.ph.getSearchGroups(data, '''name="config".*?//([^"^']+?)['"]''')[0]
			if xml:
				videoUrl = "https://" + xml
				sts, data = self.get_Page(videoUrl, self.defaultParams)
				if not sts:
					return
				url = re.findall('<videoLink>.*?//(.*?)(?:]]>|</videoLink>)', data, re.S)
				if url:
					return "https://" + url[-1].replace('&amp;', '&')
			return ''

		if parser == 'https://www.pornhd.com':
			COOKIEFILE = join(GetCookieDir(), 'pornhd.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornhd.cookie', 'pornhd.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''"1080p":['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''"720p":['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''"480p":['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''"360p":['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl.startswith('/'):
				videoUrl = 'https://www.pornhd.com' + videoUrl
			self.defaultParams['max_data_size'] = 0
			sts, data = self.getPage(videoUrl, 'pornhd.cookie', 'pornhd.com', self.defaultParams)
			return '' if not sts else data.meta['url']

		if parser == 'https://www.balkanjizz.com':
			COOKIEFILE = join(GetCookieDir(), 'balkanjizz.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=["'](/media/videos/[^"^']+?)["']''', 1, True)[0]
			if not videoUrl:
				return ''
			return 'https://www.balkanjizz.com' + videoUrl

		if parser == 'https://pornorussia.mobi':
			COOKIEFILE = join(GetCookieDir(), 'pornorussia.cookie')
			for _x in range(1, 10):
				sts, data = self.getPage(url, 'pornorussia.cookie', 'pornorussia.mobi', self.defaultParams)
				if not sts:
					return ''
				videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'file:"', '"', False)[1]
				printDBG('Link: ' + videoUrl)
				if videoUrl:
					return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})
			return ''

		if parser == 'https://www.3movs.com':
			COOKIEFILE = join(GetCookieDir(), '3movs.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.cm.getPage(url)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0].replace(r'\/', '/').replace('&amp;', '&').strip()
			if '720p' not in videoUrl or not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0].replace(r'\/', '/').replace('&amp;', '&').strip()
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.camwhoresbay.com':
			COOKIEFILE = join(GetCookieDir(), 'camwhoresbay.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.cm.getPage(url)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrls = re.findall("video.{0,5}url.{0,5}'(.*?.mp4/)'", data, re.S)
			printDBG('Videolink: ' + str(videoUrls))
			if videoUrls:
				videoUrl = videoUrls[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://xcafe.com':
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			matches = re.findall(r'''source\s+id=["']video_source_\d+["']\s+src=["']([^"^']+?)["']\s+type=["']video/mp4["']''', data)
			videoUrl = ''
			bestBr = -1
			for m in matches:
				brMatch = re.search(r'[?&]br=([0-9]+)', m)
				br = int(brMatch.group(1)) if brMatch else 0
				if br > bestBr:
					bestBr = br
					videoUrl = m
			printDBG('VideoLink: ' + videoUrl)
			return videoUrl if videoUrl else ''

		if parser == 'https://topvids.net':
			printDBG('TOPVIDS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'topvids.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'topvids.cookie', 'topvids.net', self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			printDBG('License code: ' + license_code)
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			if '720p' not in videoUrl or not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Decoding: ' + videoUrl)
			videoUrl = videoUrl.replace('.mp4/', '.mp4')
			printDBG('Videolink final: ' + videoUrl)
			if not videoUrl:
				return ''
			cfUserAgent = data.meta.get('cf_user', '') or USER_AGENT
			cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'Cookie': cookieHeader, 'User-Agent': cfUserAgent})

		if parser == 'https://www.deviants.com':
			printDBG('START PARSING THIS URL: ' + url)
			COOKIEFILE = join(GetCookieDir(), 'deviants.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'deviants.cookie', 'deviants.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			printDBG('License code: ' + license_code)
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			if '720p' not in videoUrl or not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Decoding: ' + videoUrl)
			printDBG('Videolink second: ' + videoUrl)
			videoUrl = videoUrl.replace('.mp4/', '.mp4')
			printDBG('Videolink third: ' + videoUrl)
			if 'br=' in videoUrl:
				videoUrl = videoUrl.split('?')[0]
			if 'porn2all' in videoUrl:
				return videoUrl
			printDBG('Videolink 4: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT}) if videoUrl else ''

		if parser == 'https://baddies.xxx':
			COOKIEFILE = join(GetCookieDir(), 'baddies.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'baddies.cookie', 'baddies.xxx', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			if videoUrl.endswith('/'):
				videoUrl = videoUrl.rpartition('/')[0]
			printDBG('Videolink third: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://www.cuckoldplacetube.com':
			COOKIEFILE = join(GetCookieDir(), 'cuckoldplacetube.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'cuckoldplacetube.cookie', 'cuckoldplacetube.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)['],", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			if videoUrl.endswith('/'):
				videoUrl = videoUrl.rpartition('/')[0]
			printDBG('Videolink third: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.amazingcuckold.com':
			COOKIEFILE = join(GetCookieDir(), 'amazingcuckold.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'amazingcuckold.cookie', 'amazingcuckold.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)['],", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			return videoUrl

		if parser == 'https://shareanynudes.com':
			COOKIEFILE = join(GetCookieDir(), 'shareanynudes.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'shareanynudes.cookie', 'shareanynudes.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)['],", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://24porn.com':
			COOKIEFILE = join(GetCookieDir(), '24porn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, '24porn.cookie', '24porn.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall(r'source\ssrc=["]([^"]+?)["]\sdata-url', data, re.S)
			if not videoUrl:
				return ''
			videoUrl = decodeUrl(videoUrl[-1])
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://adultxhub.com':
			COOKIEFILE = join(GetCookieDir(), 'adultxhub.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'adultxhub.cookie', 'adultxhub.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall(r'contentUrl":\s["]([^"]+?mp4/)["]', data, re.S)
			if not videoUrl:
				return ''
			videoUrl = decodeUrl(videoUrl[0])
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://analpornosex.com':
			COOKIEFILE = join(GetCookieDir(), 'analpornosex.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'analpornosex.cookie', 'analpornosex.com', self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, 'embedURL" content="(.*?)"')[0]
			if not embedUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, r'sive-player.{,100}src=["]([^"]+?)["]')[0]
			if not embedUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, r'player.{,150}src=["]([^"]+?)["]')[0]
			if not embedUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'source\ssrc=["]([^"]+?)["]')[0]
				if videoUrl:
					return urlparser.decorateUrl(videoUrl, {'Referer': url})
			sts, data = self.get_Page(embedUrl)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r"setVideoHLS\([']([^']+?)[']", 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r"setVideoUrlHigh\([']([^']+?)[']", 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r"iframeElement.{,20}=\s['](https[^']+?)[']", 1, True)[0]
				sts, data = self.get_Page(videoUrl)
				if not sts:
					return ''
				savedVideo = self.cm.ph.getSearchGroups(data, 'contentUrl":["]([^"]+?)["],"id"', 1, True)[0]
				savedVideo = savedVideo.replace('\\/', '/')
				if savedVideo.startswith('//'):
					savedVideo = 'https:' + savedVideo
				return urlparser.decorateUrl(savedVideo, {'Referer': url})
			if not videoUrl:
				videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'videoUrl":"', '","', False)[1]
				videoUrl = videoUrl.replace('\\/', '/').replace('\\u0026', '&')
			if 'm3u8' in videoUrl:
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			else:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://asianporn.life':
			COOKIEFILE = join(GetCookieDir(), 'asianporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'asianporn.cookie', 'asianporn.life', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, r'src=["]([^"]+?)["]\stype="application/x-mpeg')[0]
			if 'm3u8' in videoUrl:
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://www.videosdemadurasx.com':
			COOKIEFILE = join(GetCookieDir(), 'videosdemadurasx.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'videosdemadurasx.cookie', 'videosdemadurasx.com', self.defaultParams)
			if not sts:
				return ''
			EmbedUrl = self.cm.ph.getSearchGroups(data, r'''player"\scontent=["']([^"^']+?)["]''', 1, True)[0]
			sts, data = self.get_Page(EmbedUrl)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code':\s['"]([^"^']+?)['"]''')[0]
			videoUrl = re.findall(r'''video.{,5}url':\s['"]([^"^']+?)['"]''', data, re.S)
			if videoUrl:
				videoUrl = videoUrl[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://bigtitsxl.com':
			COOKIEFILE = join(GetCookieDir(), 'bigtitsxl.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'bigtitsxl.cookie', 'bigtitsxl.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall('source\\ssrc=["]([^"]+?)["]\\stype="video/mp4', data, re.S)
			if not videoUrl:
				return ''
			videoUrl = videoUrl[0]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://bigbumbabes.com':
			COOKIEFILE = join(GetCookieDir(), 'bigbumbabes.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'bigbumbabes.cookie', 'bigbumbabes.com', self.defaultParams)
			if not sts:
				return ''
			checker = self.cm.ph.getSearchGroups(data, 'data-hls-host=["]([^"]+?)["]')[0]
			videoUrl = re.findall('source\\ssrc=["]([^"]+?)["]\\s', data, re.S)
			if not videoUrl:
				return ''
			videoUrl = videoUrl[0]
			if checker:
				HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
				HTTP_HEADER['Referer'] = url
				sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
				if not sts or response is None:
					return []
				real_url = response.geturl()
				response.close()
				return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})
			return videoUrl

		if parser == 'https://desiresxl.com':
			COOKIEFILE = join(GetCookieDir(), 'desiresxl.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'desiresxl.cookie', 'desiresxl.com', self.defaultParams)
			if not sts:
				return ''
			videoUrls = re.findall('source\\ssrc=["]([^"]+?)["]', data, re.S)
			if not videoUrls:
				return ''
			videoUrl = videoUrls[-1]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://avexxx.com':
			COOKIEFILE = join(GetCookieDir(), 'avexxx.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'avexxx.cookie', 'avexxx.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, r"video.{0,8}url:\s[']([^']+?)[']")[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://cherrygasp.com':
			COOKIEFILE = join(GetCookieDir(), 'cherrygasp.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'cherrygasp.cookie', 'cherrygasp.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrls = re.findall(r"video.{0,8}url:\s[']([^']+?)[']", data, re.S)
			videoUrl = videoUrls[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://18tokyo.com':
			COOKIEFILE = join(GetCookieDir(), 'japaneseteens.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'japaneseteens.cookie', '18tokyo.com', self.defaultParams)
			videoUrl = re.findall(r'contentUrl":\s["]([^"]+?mp4/)["]', data, re.S)
			if videoUrl:
				videoUrl = decodeUrl(videoUrl[0])
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://ebonyplayz.com':
			COOKIEFILE = join(GetCookieDir(), 'ebonyplayz.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'ebonyplayz.cookie', 'ebonyplayz.com', self.defaultParams)
			checker = self.cm.ph.getSearchGroups(data, 'data-hls-host=["]([^"]+?)["]')[0]
			videoUrl = re.findall('source\\ssrc=["]([^"]+?)["]\\s', data, re.S)
			if videoUrl:
				videoUrl = videoUrl[0]
			if checker:
				HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
				HTTP_HEADER['Referer'] = url
				sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
				if not sts or response is None:
					return []
				real_url = response.geturl()
				response.close()
				return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})
			return videoUrl

		if parser == 'https://japanesematures.com':
			COOKIEFILE = join(GetCookieDir(), 'japanesematures.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'japanesematures.cookie', 'japanesematures.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall(r'contentUrl":\s["]([^"]+?)["]', data, re.S)
			if not videoUrl:
				return ''
			videoUrl = videoUrl[0]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://fukxl.com':
			COOKIEFILE = join(GetCookieDir(), 'fukxl.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'fukxl.cookie', 'fukxl.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall('src=["]([^"]+?)["]\\stype="video/mp4', data, re.S)
			if not videoUrl:
				return ''
			videoUrl = videoUrl[-1]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://hornyfap.tv':
			COOKIEFILE = join(GetCookieDir(), 'hornyfap.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'hornyfap.cookie', 'hornyfap.tv', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, r"video_url:\s[']([^']+?)[']")[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://lesb8.com':
			COOKIEFILE = join(GetCookieDir(), 'lesb8.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'lesb8.cookie', 'lesb8.com', self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, '<source\\ssrc="(.*?)"\\stype="application/x-mpegURL')[0]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = embedUrl
			sts, response = self.cm.getPage(embedUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			if real_url:
				# <source type="application/x-mpegURL"> - the redirect target need not end in .m3u8; the master lists
				# 360p first
				master = urlparser.decorateUrl(str(real_url), {'Referer': url})
				return self._bestM3U8Variant(master, checkExt=False) or urlparser.decorateUrl(str(real_url), {'Referer': url, 'iptv_proto': 'm3u8'})

		if parser == 'https://www.shemaletubevideos.com':
			COOKIEFILE = join(GetCookieDir(), 'shemaletube.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'shemaletube.cookie', 'shemaletubevideos.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall('type="video/mp4"\\ssrc=["]([^"]+?)["]', data, re.S)
			if not videoUrl:
				return ''
			videoUrl = videoUrl[0]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://morehardporn.com':
			COOKIEFILE = join(GetCookieDir(), 'morehardporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'morehardporn.cookie', 'morehardporn.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, r"video.{0,8}url:\s[']([^']+?)[']")[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://www.porntry.com':
			COOKIEFILE = join(GetCookieDir(), 'porntry.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, "<source\\ssrc='(.*?)'\\stype='video/mp4")[0]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = embedUrl
			sts, response = self.cm.getPage(embedUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			videoUrl = str(real_url)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://pornx.to':
			COOKIEFILE = join(GetCookieDir(), 'pornx.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornx.cookie', 'pornx.to', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, 'application/x-mpegURL"\\ssrc=["]([^"]+?)["]')[0]
			if 'm3u8' in videoUrl:
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://redporn.porn':
			COOKIEFILE = join(GetCookieDir(), 'redporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'redporn.cookie', 'redporn.porn', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall('source\\ssrc=["]([^"]+?)["]\\s', data, re.S)
			if not videoUrl:
				return ''
			videoUrl = decodeUrl(videoUrl[-1])
			if 'multi' in videoUrl:
				sts, tmp = self.get_Page(videoUrl)
				if 'expired' in tmp:
					msg = _('ACCESS DENIED.\nTHIS VIDEO IS DELETED OR NOT AVAILABLE TO YOUR REGION.')
					self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_INFO)
					return None
				lines = tmp.splitlines()
				urls = []
				for i, line in enumerate(lines):
					if line.startswith('#EXT-X-STREAM-INF'):
						if i + 1 < len(lines):
							urls.append(lines[i + 1].strip())
				videoUrl = urljoin(videoUrl, urls[-1])
				return strwithmeta(videoUrl, {'iptv_proto': 'm3u8'})  # variant line of the master playlist
			else:
				HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
				HTTP_HEADER['Referer'] = videoUrl
				sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
				if not sts or response is None:
					msg = _('ACCESS DENIED.\nTHIS VIDEO IS DELETED OR NOT AVAILABLE TO YOUR REGION.')
					self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_INFO)
					return None
				real_url = response.geturl()
				response.close()
				return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://throatlust.com':
			COOKIEFILE = join(GetCookieDir(), 'throatlust.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'throatlust.cookie', 'throatlust.com', self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, 'iframe\\ssrc=["]([^"]+?)["]')[0]
			sts, data = self.getPage(embedUrl, 'throatlust.cookie', embedUrl, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, 'source.src=["]([^"]+?)["]')[0]
			if videoUrl:
				return videoUrl

		if parser == 'https://zzztube.tv':
			COOKIEFILE = join(GetCookieDir(), 'zzztube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'zzztube.cookie', 'zzztube.tv', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall('source\\ssrc=["]([^"]+?)["]\\sdata-url', data, re.S)
			if not videoUrl:
				# Nuxt page: {"hls": .., "mp4": [..]} in __NUXT_DATA__ with \u002F-escaped slashes, the plain mp4 is the one without media=hls
				videoUrl = [x for x in re.findall(r'"(https:[^"]+?key=[^"]+?\.mp4)"', data.replace('\\u002F', '/')) if 'media=hls' not in x]
				if videoUrl:
					return urlparser.decorateUrl(videoUrl[-1], {'Referer': url, 'User-Agent': USER_AGENT})
				return ''
			videoUrl = decodeUrl(videoUrl[-1])
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(videoUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				return []
			real_url = response.geturl()
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://www.xxbrits.com':
			COOKIEFILE = join(GetCookieDir(), 'xxbrits.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'xxbrits.cookie', 'xxbrits.com', self.defaultParams)
			if 'This video is a private video' in data:
				self.sessionEx.open(MessageBox, _("This video is a private video."), type=MessageBox.TYPE_INFO, timeout=10)
				return ''
			else:
				license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
				# the 1080p slot is only '?login' for guests
				videoUrl = [x for x in re.findall("video.{1,6}url.{2,4}[']([^@]+?)['],", data, re.S) if '?login' not in x]
				if not videoUrl:
					return ''
				videoUrl = videoUrl[-1]
				printDBG('Videolink first: ' + videoUrl)
				if 'function/0/' in videoUrl:
					videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
				return videoUrl

		if parser == 'https://hdpussy.xxx':
			printDBG('STARTED HDPUSSY PARSER')
			COOKIEFILE = join(GetCookieDir(), 'hdpussy.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'hdpussy.cookie', 'hdpussy.xxx', self.defaultParams)
			try:
				videoUrl = re.findall('source.src=["]([^@]+?)["].{,14}/mp4', data, re.S)[0]
				printDBG('Videolink: ' + videoUrl)
			except Exception:
				self.sessionEx.open(MessageBox, _("This video has been deleted."), type=MessageBox.TYPE_INFO, timeout=10)
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if self.cm.isValidUrl(videoUrl) else ''

		if parser == 'https://cambeauties.com':
			printDBG('STARTED CAMBEAUTIES PARSER')
			COOKIEFILE = join(GetCookieDir(), 'cambeauties.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'cambeauties.cookie', 'cambeauties.com', self.defaultParams)
			videoUrl = ''
			try:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''source\ssrc=["']([^"^']+?)["']\stype''', 1, True)[0]
				if not videoUrl:
					videoUrl = self.cm.ph.getSearchGroups(data, r'''source\ssrc=([^"'\s]+)\stype''', 1, True)[0]
				videoUrl = videoUrl.replace(' ', '%20')
				printDBG('Videolink: ' + videoUrl)
			except Exception:
				self.sessionEx.open(MessageBox, _("This video has been deleted."), type=MessageBox.TYPE_INFO, timeout=10)
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if self.cm.isValidUrl(videoUrl) else ''

		if parser == 'https://www.xpaja.net':
			printDBG('STARTED XPAJA PARSER')
			self.MAIN_URL = 'https://www.xpaja.net'
			COOKIEFILE = join(GetCookieDir(), 'xpaja.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'xpaja.cookie', 'xpaja.net', self.defaultParams)
			try:
				urls = re.findall('source.src=["]([^"]+?)["].{,40}/(?:mp4|x-mpegURL)', data, re.S)[0]
				videoUrl = urljoin(self.MAIN_URL + '/', urls)
				printDBG('Videolink: ' + videoUrl)
			except Exception:
				self.sessionEx.open(MessageBox, _("This video has been deleted."), type=MessageBox.TYPE_INFO, timeout=10)
				return ''
			if '.m3u8' in videoUrl:
				# the master lists 240p first - handed over as it is, the player stayed on 240p
				return self._bestM3U8Variant(urlparser.decorateUrl(videoUrl, {'Referer': url}), checkExt=False) or urlparser.decorateUrl(videoUrl, {'Referer': url, 'iptv_proto': 'm3u8'})
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if self.cm.isValidUrl(videoUrl) else ''

		if parser == 'https://www.xrares.com':
			printDBG('STARTED XRARES PARSER')
			COOKIEFILE = join(GetCookieDir(), 'xrares.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			url = url.replace('\xc3\xa4', '%C3%A4')
			printDBG('REPLACED URL: ' + str(url))
			sts, data = self.getPage(url, 'xrares.cookie', 'xrares.com', self.defaultParams)
			try:
				videoUrl = re.findall('source.src=["]([^@]+?)["].type=.video/mp4', data, re.S)[0]
				printDBG('Videolink: ' + videoUrl)
				return videoUrl
			except Exception:
				SetIPTVPlayerLastHostError(_('THIS IS A PRIVATE VIDEO.'))

		if parser == 'https://www.xtits.com':
			COOKIEFILE = join(GetCookieDir(), 'xtits.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'xtits.cookie', 'xtits.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)['],", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			return videoUrl

		if parser == 'https://amateur.red':
			printDBG('STARTED AMATEUR.RED PARSER')
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"]''')[0]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.terk.nl':
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"]''')[0]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				return videoUrl
			else:
				self.MAIN_URL = 'https://shooshtime.com'
				license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
				if not videoUrl:
					videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
				if videoUrl.startswith('/'):
					videoUrl = self.MAIN_URL + videoUrl
				printDBG('Videolink first: ' + videoUrl)
				if 'function/0/' in videoUrl:
					videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
				if videoUrl:
					return videoUrl
			return ''

		if parser == 'https://hardsexvids.com':
			COOKIEFILE = join(GetCookieDir(), 'hardsexvids.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'hardsexvids.cookie', 'hardsexvids.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			if videoUrl.startswith('/'):
				videoUrl = self.MAIN_URL + videoUrl
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})
			return ''

		if parser == 'https://young-sex-tube.com':
			printDBG('STARTED YOUNG SEX TUBE PARSER')
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"]''')[0]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://javteentube.com':
			printDBG('JAVTEENTUBE PARSER')
			sts, data = self.get_Page(url)
			embedUrl = self.cm.ph.getSearchGroups(data, '''iframe.+src=['"]([^"^']+?)['"]''')[0]
			sts, data2 = self.get_Page(embedUrl)
			videoUrl = self.cm.ph.getSearchGroups(data2, '''source.src=['"]([^"^']+?)['"]''')[0]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://pornvideosbest.com':
			printDBG('PORNVIDEOSBEST PARSER')
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, "video_url'].=.[']([^']+?)[']")[0]
			if videoUrl.startswith('/'):
				videoUrl = 'https://pornvideosbest.com' + videoUrl
			printDBG('Videolink: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT}) if videoUrl else ''

		if parser == 'https://www.oriental-sex.com':
			printDBG('ORIENTAL SEX PARSER')
			sts, data = self.get_Page(url, {'header': {'User-Agent': USER_AGENT}})
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"]([^"']+?)['"]''')[0].replace('&amp;', '&')
			if not videoUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"']+?/embed/[^"']+?)['"]''')[0]
				if not embedUrl:
					return ''
				sts, data = self.get_Page(embedUrl, {'header': {'User-Agent': USER_AGENT, 'Referer': url}})
				if not sts:
					return ''
				videoUrl = self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"]([^"']+?)['"]''')[0].replace('&amp;', '&')
			printDBG('VideoLink: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if videoUrl else ''

		if parser == 'https://69teentube.com':
			printDBG('69TEENTUBE PARSER')
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, 'video".src=["]([^"]+?)["].+video/mp4')[0]
			if not videoUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, 'frame.+src=["]([^"]+?)["]')[0]
				printDBG('EMBEDURL: ' + str(embedUrl))
				sts, data2 = self.get_Page(embedUrl)
				if not sts:
					return ''
				videoUrl = self.cm.ph.getSearchGroups(data2, 'source.src=["]([^"]+?)["]')[0]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.milffox.com':
			printDBG('MILF FOX PARSER')
			COOKIEFILE = join(GetCookieDir(), 'milffox.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'milffox.cookie', 'milffox.com', self.defaultParams)
			if not sts:
				return ''
			# Playerjs: get_video.php redirects to the signed mp4 (needs the session cookie of the page)
			videoUrl = self._pickByHeight([(int(h), u) for h, u in re.findall(r'''\[([0-9]+)p\](//[^,"]+?get_video\.php\?q=[0-9]+p)''', data)])
			if videoUrl:
				params = dict(self.defaultParams)
				params.update({'header': {'User-Agent': USER_AGENT, 'Referer': url}, 'return_data': False})
				sts, response = self.cm.getPage('https:' + videoUrl, params)
				if not sts or response is None:
					return ''
				videoUrl = response.geturl()
				response.close()
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			return videoUrl

		if parser == 'https://9vids.com':
			printDBG('9VIDS PARSER V1')
			COOKIEFILE = join(GetCookieDir(), '9vids.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, '9vids.cookie', '9vids.com', self.defaultParams)
			if not sts or not data:
				return ''

			candidates = []
			patterns = [
				r'''<source[^>]+src=["']([^"']+?)["']''',
				r'''(?:file|videoUrl|video_url|videoSource|video_source|mediaUrl|media_url)\s*[:=]\s*["']([^"']+?)["']''',
				r'''(?:src|url)\s*[:=]\s*["']([^"']+\.(?:m3u8|mp4)(?:\?[^"']*)?)["']''',
				r'''https?:\/\/[^"'\s<>]+?\.(?:m3u8|mp4)(?:\?[^"'<>
\s]*)?'''
			]
			for pattern in patterns:
				for match in re.findall(pattern, data, re.I):
					candidates.append(match)

			iframes = re.findall(r'''<iframe[^>]+src=["']([^"']+?)["']''', data, re.I)
			for embedUrl in iframes:
				embedUrl = urljoin(url, embedUrl)
				printDBG('9VIDS iframe: ' + embedUrl)
				sts2, data2 = self.getPage(embedUrl, '9vids.cookie', '9vids.com', self.defaultParams)
				if not sts2 or not data2:
					continue
				for pattern in patterns:
					for match in re.findall(pattern, data2, re.I):
						candidates.append(match)

				scripts = re.findall(r'''<script[^>]+src=["']([^"']+?)["']''', data2, re.I)
				for scriptUrl in scripts[:8]:
					scriptUrl = urljoin(embedUrl, scriptUrl)
					sts3, scriptData = self.getPage(scriptUrl, '9vids.cookie', '9vids.com', self.defaultParams)
					if sts3 and scriptData:
						for pattern in patterns:
							for match in re.findall(pattern, scriptData, re.I):
								candidates.append(match)

			for videoUrl in candidates:
				videoUrl = fix_escaped_url(videoUrl).replace('&amp;', '&').strip()
				videoUrl = checkhttps(videoUrl)
				if videoUrl.startswith('/'):
					videoUrl = urljoin(url, videoUrl)
				if '.m3u8' in videoUrl.lower() or re.search(r'\.mp4(?:\?|$)', videoUrl, re.I):
					printDBG('9VIDS FINAL: ' + videoUrl)
					return urlparser.decorateUrl(videoUrl, {'Referer': url, 'Origin': 'https://9vids.com', 'User-Agent': self.HTTP_HEADER.get('User-Agent', USER_AGENT)})

			printDBG('9VIDS PARSER: no media URL found')
			return ''

		if parser == 'https://www.porndr.com':
			printDBG('PORNDR PARSER')
			COOKIEFILE = join(GetCookieDir(), 'porndr.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'porndr.cookie', 'porndr.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:\n.+['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:\n.+[']([^"^']+?)['],''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:\n.+[']([^"^']+?)['],''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			return videoUrl

		if parser == 'https://moreamateurs.com':
			printDBG('MOREAMATEURS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'moreamateurs.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'moreamateurs.cookie', 'moreamateurs.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.[']([^"^']+?)['],''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.[']([^"^']+?)['],''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.fuqer.com':
			printDBG('FUQER PARSER')
			COOKIEFILE = join(GetCookieDir(), 'fuqer.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'fuqer.cookie', 'fuqer.com', self.defaultParams)
			if not sts:
				return ''
			# the player signs the media path through secure_link.php (expires/md5 query)
			mediaUri = self.cm.ph.getSearchGroups(data, r'''signedMediaUri\s*=\s*['"]([^"']+?)['"]''')[0].replace('\\/', '/')
			if not mediaUri:
				return ''
			sts, data = self.getPage('https://www.fuqer.com/secure_link.php?path=%s&ttl=1800' % quote(mediaUri, safe=''), 'fuqer.cookie', 'fuqer.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, r'''"url"\s*:\s*"([^"]+?)"''')[0].replace('\\/', '/') if sts else ''
			printDBG('Videolink: ' + videoUrl)
			# the media host (Cloudflare) answers 403 when no User-Agent comes along - exteplayer3 sends none of its own;
			# a player User-Agent, as for CAMSODA, since ffmpeg's TLS does not match a browser one
			return urlparser.decorateUrl(urljoin('https://www.fuqer.com/', videoUrl), {'Referer': url, 'User-Agent': 'VLC/3.0.20 LibVLC/3.0.20'}) if videoUrl else ''

		if parser == 'https://blowjobit.com':
			printDBG('BLOWJOBIT PARSER')
			COOKIEFILE = join(GetCookieDir(), 'blowjobit.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'blowjobit.cookie', 'blowjobit.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=["]([^"^']+?)["]''')[0]
			printDBG('Videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.amateur-cougar.com':
			printDBG('AMATEURCOUGAR PARSER')
			COOKIEFILE = join(GetCookieDir(), 'amateurcougar.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'amateurcougar.cookie', 'amateur-cougar.com', self.defaultParams)
			EmbedUrl = self.cm.ph.getSearchGroups(data, 'iframe.src=["]([^"]+?)["]', 1, True)[0]
			printDBG('Embed URL: ' + EmbedUrl)
			sts, data = self.getPage(EmbedUrl, 'amateurcougar.cookie', EmbedUrl, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, 'source.src=["]([^"]+?)["].type="video/mp4')[0]
			printDBG('Videolink: ' + videoUrl)
			if videoUrl:
				return videoUrl

		if parser == 'https://www.moms-sex-videos.com':
			printDBG('MOMS-SEX-VIDEOS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'momssexvideos.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'momssexvideos.cookie', 'moms-sex-videos.com', self.defaultParams)
			EmbedUrl = self.cm.ph.getSearchGroups(data, 'iframe.src=["]([^"]+?)["]', 1, True)[0]
			printDBG('Embed URL: ' + EmbedUrl)
			sts, data = self.getPage(EmbedUrl, 'momssexvideos.cookie', EmbedUrl, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, 'source.src=["]([^"]+?)["].type="video/mp4')[0]
			printDBG('Videolink: ' + videoUrl)
			if videoUrl:
				return videoUrl

		if parser == 'https://www.justporn.com':
			printDBG('JUSTPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'justporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'justporn.cookie', 'justporn.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			printDBG('LICENSE: ' + license_code)
			videoUrl = re.findall("video.{,6}url:.[']([^']+?)[']", data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[-1]
				if 'function/0/' in videoUrl:
					videoUrl = decryptHash(videoUrl, license_code, '16')
					printDBG('Videolink second: ' + videoUrl)
				return videoUrl
			return ''

		if parser == 'https://www.worldsex.com':
			printDBG('WORLDSEX PARSER')
			COOKIEFILE = join(GetCookieDir(), 'worldsex.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'worldsex.cookie', 'worldsex.com', self.defaultParams)
			videoUrl = re.findall('source.src=["]([^"]+?)["]', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
				return videoUrl

		if parser == 'https://engorgedtits.com':
			# watch.html?id=<id> -> the JSON API names the file: free videos are plain MP4, encrypted HLS is premium only
			videoId = self.cm.ph.getSearchGroups(url, r'[?&]id=([0-9]+)', 1, True)[0]
			if not videoId:
				return ''
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			sts, data = self.cm.getPage('https://engorgedtits.com/api/videos/' + videoId, {'header': self.HTTP_HEADER, 'return_data': True})
			try:
				video = json.loads(data).get('video', {}) if sts else {}
			except Exception:
				printExc()
				video = {}
			videoUrl = video.get('videoUrl', '')
			if video.get('hlsKeyId') or '.m3u8' in videoUrl:
				SetIPTVPlayerLastHostError(_('THIS IS A PREMIUM VIDEO.\nLOGIN OR PREMIUM REQUIRED.'))
				return ''
			if not videoUrl.startswith('http'):
				return ''
			return urlparser.decorateUrl(videoUrl, {'Referer': 'https://engorgedtits.com/', 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser == 'https://bdsm.one':
			printDBG('BDSMTUBE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'bdsm.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'bdsm.cookie', 'bdsm.one', self.defaultParams)
			videoUrl = re.findall('source-video" src=["]([^"]+?)["]', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
				return videoUrl

		if parser == 'https://vagina.nl':
			printDBG('VAGINA PARSER')
			COOKIEFILE = join(GetCookieDir(), 'vagina.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'vagina.cookie', 'vagina.nl', self.defaultParams)
			videoUrl = re.findall('video".content=["]([^"]+?)["]/><meta.proper', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
				return videoUrl

		if parser == 'https://indianporntube.net':
			printDBG('INDIANPORNTUBE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'indianporntube.cookie')
			self.USER_AGENT = 'Mozilla/5.0 (iPad; CPU OS 8_1_3 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B466 Safari/600.1.4'
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			time.sleep(5)
			sts, data = self.getPage(url, 'indianporntube.cookie', 'indianporntube.net', self.defaultParams)
			data = self.cm.ph.getDataBeetwenMarkers(data, 'VIDEO CONTENT', '#thisPlayer', False)[1]
			videoUrl = self.cm.ph.getSearchGroups(data, '''source src=["]([^"]+?)["]''')[0]
			if videoUrl:
				printDBG('READY LINK: ' + str(videoUrl))
				return videoUrl
			return ''

		if parser == 'https://voyeurhit.com':
			printDBG('VOYEURHIT PARSER')
			COOKIEFILE = join(GetCookieDir(), 'voyeurhit.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'voyeurhit.cookie', 'voyeurhit.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search('video_url":"([^"]+)', data).group(1)
			printDBG('Fetched code: ' + videoUrl)
			replacemap = {'M': '\\u041c', 'A': '\\u0410', 'B': '\\u0412', 'C': '\\u0421', 'E': '\\u0415', '=': '~', '+': '.', '/': ','}
			for key in replacemap:
				videoUrl = videoUrl.replace(replacemap[key], key)
			printDBG('New url: ' + videoUrl)
			videoUrl = base64.b64decode(videoUrl)
			videoUrl = videoUrl.decode("utf-8")
			printDBG('Decoded address: ' + videoUrl)
			if videoUrl.startswith('//'):
				videoUrl = 'https:' + videoUrl
			if videoUrl.startswith('/'):
				videoUrl = 'https://voyeurhit.com' + videoUrl
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.realmatureporn.com':
			printDBG('REALMATUREPORN PARSER')
			# the listing links to /c/?g=<obfuscated>&t=..&i=..&c=.. , a
			# redirect gateway - g is base64(reversed) encoding of the real
			# "/?video=X&category=Y" path, decoding it locally skips the
			# gateway hop itself, but the destination is behind the same
			# Cloudflare protection as the gateway (intermittent - not every
			# request gets challenged), so it still needs the real CF-solver
			g = self.cm.ph.getSearchGroups(url, r'[?&]g=([^&]+)', 1, True)[0]
			g = unquote(g)
			decoded = ''
			try:
				pad = (-len(g)) % 4
				decoded = base64.b64decode(g[::-1] + '=' * pad).decode('utf-8', 'ignore')
			except Exception:
				printExc()
			printDBG('REALMATUREPORN decoded path: ' + decoded)
			if not decoded.startswith('/'):
				return ''
			directUrl = 'https://www.realmatureporn.com' + decoded
			COOKIEFILE = join(GetCookieDir(), 'realmatureporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(directUrl, 'realmatureporn.cookie', 'realmatureporn.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'''source\ssrc=["']([^"^']+?)["']''', 1, True)[0]
			printDBG('Videolink: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': directUrl})
			return ''

		if parser == 'https://www.sexetag.com':
			printDBG('SEXETAG PARSER')
			COOKIEFILE = join(GetCookieDir(), 'sexetag.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'sexetag.cookie', 'sexetag.com', self.defaultParams)
			videoUrl = re.findall(r'''source[^>]*?src=["']([^"']+?)["'][^>]*?type=["']video/mp4''', data, re.S)
			printDBG('Videolink: ' + str(videoUrl))
			if videoUrl:
				return urlparser.decorateUrl(videoUrl[0], {'Referer': url})
			self.sessionEx.open(MessageBox, _("This video is Premium-only content."), type=MessageBox.TYPE_INFO, timeout=10)
			return ''

		if parser == 'https://run.porn':
			printDBG('RUNPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'runporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'runporn.cookie', 'run.porn', self.defaultParams)
			hlsUrl = re.search('src-hls=["]([^"]+?)["]', data)
			if hlsUrl:
				hlsUrl = hlsUrl.group(1)
			else:
				return ''
			printDBG('HLS ADDRESS: ' + str(hlsUrl))
			sts, data2 = self.get_Page(hlsUrl)
			if not sts:
				return ''
			videoUrl = re.findall(r'"[\s](https[^#]+?m3u8)', data2, re.S)
			printDBG('Video links: ' + str(videoUrl))
			videoUrl = videoUrl[-1]
			if '.m3u8' in videoUrl and self.cm.isValidUrl(videoUrl):
				best = self._bestM3U8Variant(videoUrl)  # the first variant of the master was its lowest
				if best:
					return best
			if videoUrl:
				return videoUrl

		if parser == 'https://www.nakedgirls.mobi':
			printDBG('NAKEDGIRLS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'nakedgirls.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'nakedgirls.cookie', 'nakedgirls.mobi', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			printDBG('License code: ' + license_code)
			videoUrl = re.findall("video.{0,5}url.{2,3}[']([^']+?)['],", data, re.S)
			if videoUrl:
				videoUrl = videoUrl[-1]
			else:
				return ''
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Decoding: ' + videoUrl)
			printDBG('Videolink second: ' + videoUrl)
			if 'br=' in videoUrl:
				videoUrl = videoUrl.split('?')[0]
			printDBG('Videolink third: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})
			return ''

		if parser == 'https://yespornpleasexxx.com':
			printDBG('YESPORNPLEASE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'yespornplease.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			EmbedUrl = self.cm.ph.getSearchGroups(data, r'data-litespeed-src=["](https:[^"]+)["]\sframe.*iframe', 1, True)[0]
			printDBG('EMBEDURL: ' + str(EmbedUrl))
			sts, data2 = self.get_Page(EmbedUrl)
			videoUrls = re.findall('source.{0,20}src=["](.*?)["]', data2, re.S)
			printDBG('Video links: ' + str(videoUrls))
			if videoUrls:
				videoUrl = decodeUrl(videoUrls[0])
				printDBG('Videolink: ' + videoUrl)
				if videoUrl:
					return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})
			return ''

		if parser == 'https://www.hdtube.porn':
			COOKIEFILE = join(GetCookieDir(), 'hdtube.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'hdtube.cookie', 'hdtube.porn', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data, re.S)[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			if videoUrl.endswith('/'):
				videoUrl = videoUrl.rpartition('/')[0]
			printDBG('Videolink third: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://www.pornslash.com':
			printDBG('PORNSLASH PARSER')
			if 'watch' in url:
				sts, data2 = self.getPageWithCFBypass(url)
				EmbedUrl = self.cm.ph.getSearchGroups(data2, 'loadSource.["](https:[^"]+)["]', 1, True)[0]
				printDBG('EMBEDURL: ' + str(EmbedUrl))
				sts, data2 = self.getPageWithCFBypass(EmbedUrl)
				if not sts or data2 is None or 'code":"2200' in data2:
					SetIPTVPlayerLastHostError(_('THIS VIDEO IS UNAVAILABLE.\nTRY AGAIN LATER!'))
					return []
				data2 = data2 + '#'
				videoUrls = data2.split('X-STREAM-INF')[1:]
				printDBG('Video links: ' + str(videoUrls))
				# variants are listed low to high; reversed, so the last one wins among equal (unknown) heights
				candidates = [(int(self.cm.ph.getSearchGroups(item, r'RESOLUTION=[0-9]+x([0-9]+)', 1, True)[0] or 0), self.cm.ph.getSearchGroups(item, '["]([^"]+?)[#]', 1, True)[0].strip()) for item in reversed(videoUrls)]
				videoUrl = self._pickByHeight([c for c in candidates if c[1]])
				printDBG('Selected URL: ' + str(videoUrl))
				return strwithmeta(videoUrl, {'iptv_proto': 'm3u8'})  # variant line of the master playlist
			else:
				printDBG('SELECTED RESOLUTION:\n' + url)
				return strwithmeta(url, {'iptv_proto': 'm3u8'})  # variant picked in hostxxx PORNSLASH-server

		if parser == 'https://www.realgfporn.com':
			printDBG('REALGFPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'realgfporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'realgfporn.cookie', 'realgfporn.com', self.defaultParams)
			videoUrl = re.findall(r"source\ssrc=[']([^@]+?)[']\stype='video/mp4", data, re.S)[0]
			if videoUrl:
				printDBG('Videolink: ' + videoUrl)
				try:
					return urlparser.decorateUrl(videoUrl, {'Referer': url})
				except Exception:
					return videoUrl

		if parser == 'https://en.paradisehill.cc':
			printDBG('PARADISEHILL PARSER')
			if url:
				return url
			return ''

		if parser == 'https://www.erogarga.com':
			printDBG('EROGARGA PARSER')
			COOKIEFILE = join(GetCookieDir(), 'erogarga.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'erogarga.cookie', 'erogarga.com', self.defaultParams)
			EmbedUrl = self.cm.ph.getSearchGroups(data, 'iframe.+src=["](https:[^"]+)["]', 1, True)[0]
			printDBG('EMBEDURL: ' + str(EmbedUrl))
			if not EmbedUrl:
				self.sessionEx.open(MessageBox, _("This page has no video (blog article)."), type=MessageBox.TYPE_INFO, timeout=10)
				return ''
			sts, data2 = self.getPageWithCFBypass(EmbedUrl)
			if not sts or data2 is None or 'code":"2200' in data2:
				SetIPTVPlayerLastHostError(_('THIS VIDEO IS UNAVAILABLE.\nTRY AGAIN LATER!'))
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data2, r'source\ssrc=["]([^"]+?)["]', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data2, r"video_url:\s[']([^']+?)[']", 1, True)[0]
			printDBG('videoURL: ' + str(videoUrl))
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.tubev.sex':
			printDBG('TUBEV PARSER')
			COOKIEFILE = join(GetCookieDir(), 'tubev.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'tubev.cookie', 'tubev.sex', self.defaultParams)
			if not sts:
				return ''
			# The old bare re.search(...).group(1) crashed with AttributeError
			# whenever the primary pattern didn't match at all - added a fallback
			# pattern plus a guard instead of letting that raise.
			m = re.search('contentUrl":.["]([^"]+)["]', data)
			if m:
				videoUrl = m.group(1)
			else:
				m = re.search('source\\ssrc=["]([^"]+)["]\\stype="video/mp4', data)
				videoUrl = m.group(1) if m else ''
			if not videoUrl:
				return ''
			printDBG('Videolink: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': 'https://www.tubev.sex'})
			except Exception:
				return videoUrl

		if parser == 'https://senioras.com':
			printDBG('SENIORAS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'senioras.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'senioras.cookie', 'senioras.com', self.defaultParams)
			videoId = self.cm.ph.getSearchGroups(data, r'"videoId":([0-9]+)')[0] if sts else ''
			if not videoId:
				return ''
			params = dict(self.defaultParams)
			params['header'] = {'User-Agent': self.cm.getDefaultHeader(browser='chrome')['User-Agent'], 'X-Requested-With': 'XMLHttpRequest', 'Referer': url}
			sts, data = self.get_Page('https://senioras.com/api/video-info', params, {'videoId': videoId})
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'"sources":\[\{"src":"([^"]+?)"')[0].replace('\\/', '/')
			if not videoUrl:
				return ''
			printDBG('Videolink first: ' + videoUrl)
			if videoUrl.startswith('//'):
				videoUrl = 'https:' + videoUrl
			printDBG('Videolink second: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.xmegadrive.com':
			printDBG('XMEGADRIVE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'xmegadrive.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'xmegadrive.cookie', 'xmegadrive.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			if '720p' not in videoUrl or not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			if videoUrl.endswith('/'):
				videoUrl = videoUrl.rpartition('/')[0]
			printDBG('Videolink third: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl
			return ''

		if parser == 'https://xhand.net':
			printDBG('XHAND PARSER')
			COOKIEFILE = join(GetCookieDir(), 'xhand.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'xhand.cookie', 'xhand.net', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)[']", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://www.lesbian8.com':
			printDBG('LESBIAN8 PARSER')
			COOKIEFILE = join(GetCookieDir(), 'lesbian8.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'lesbian8.cookie', 'lesbian8.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)[']", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://mylust.com':
			printDBG('MYLUST PARSER')
			COOKIEFILE = join(GetCookieDir(), 'mylust.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'mylust.cookie', 'mylust.com', self.defaultParams)
			videoUrl = re.findall(r'src=["]([^"]+?)["]\stype="video/mp4', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://porndreamz.com':
			printDBG('PORNDREAMZ PARSER')
			videoId = self.cm.ph.getSearchGroups(url, r'/video/(\d+)/', 1, True)[0]
			if not videoId:
				return ''
			embedUrl = 'https://porndreamz.com/embed/%s/' % videoId
			sts, data = self.getPageWithCFBypass(embedUrl)
			if not sts:
				return ''
			iframeUrl = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=["']([^"^']+?)["']''', 1, True)[0]
			if not iframeUrl:
				return ''
			printDBG('PORNDREAMZ iframe: ' + iframeUrl)
			return self.getResolvedURL(iframeUrl)

		if parser == 'https://w1mp.com':
			printDBG('W1MP PARSER')
			COOKIEFILE = join(GetCookieDir(), 'w1mp.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'w1mp.cookie', 'w1mp.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, r'''source\ssrc=["']([^"^']+?)["'].type="video/mp4"''', 1, True)[0]
			if not videoUrl:
				license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
				videoUrls = re.findall("video.{1,6}url.{2,4}[']([^@]+?)[']", data, re.S)
				if videoUrls:
					videoUrl = videoUrls[-1]
					if 'function/0/' in videoUrl:
						videoUrl = decryptHash(videoUrl, license_code, '16')
					videoUrl = videoUrl.split('/?br')[0]
			printDBG('Videolink: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://bigbuttholes.com':
			printDBG('BIGBUTTHOLES PARSER')
			COOKIEFILE = join(GetCookieDir(), 'bigbuttholes.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'bigbuttholes.cookie', 'bigbuttholes.com', self.defaultParams)
			if not sts:
				return ''
			# <source> of the player, else the schema.org contentUrl; both redirect to the real file
			streamUrl = self.cm.ph.getSearchGroups(data, r'<source\ssrc="(.*?)"\stype="video/mp4')[0] or self.cm.ph.getSearchGroups(data, r'contentUrl":\s["]([^"]+?)["]')[0]
			if not streamUrl:
				return ''
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			sts, response = self.cm.getPage(streamUrl, {'header': HTTP_HEADER, 'return_data': False})
			if not sts or response is None:
				printDBG('BIGBUTTHOLES: failed to retrieve the stream URL')
				return ''
			videoUrl = str(response.geturl())
			response.close()
			printDBG('BIGBUTTHOLES videolink: ' + videoUrl)
			if not videoUrl.startswith('http'):
				return ''
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.vikiporn.com':
			printDBG('VIKIPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'vikiporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'vikiporn.cookie', 'vikiporn.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)[']", data, re.S)[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			if videoUrl.endswith('/'):
				videoUrl = videoUrl.rpartition('/')[0]
			printDBG('Videolink final: ' + videoUrl)
			return unquote(videoUrl)

		if parser == 'https://maturexy.com':
			printDBG('MATUREXY PARSER')
			COOKIEFILE = join(GetCookieDir(), 'maturexy.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'maturexy.cookie', 'maturexy.com', self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, r'<source\ssrc="(.*?)"\stype="video/mp4')[0]
			printDBG('EMBEDURL: ' + embedUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = embedUrl
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(embedUrl, params)
			if not sts or response is None:
				printDBG("MATUREXY: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			videoUrl = str(real_url)
			printDBG('Videolink: ' + str(videoUrl))
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://xxxbunker.com':
			printDBG('XXXBUNKER PARSER')
			COOKIEFILE = join(GetCookieDir(), 'xxxbunker.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'xxxbunker.cookie', 'xxxbunker.com', self.defaultParams)
			EmbedUrl = re.search(r'iframe\sid="player"\sdata-src=["]([^@]+?)["]', data).group(1)
			sts, data = self.get_Page(EmbedUrl)
			if not sts:
				return ''
			videoUrl = re.findall(r'source\ssrc=["]([^@]+?)["]', data, re.S)[0]
			printDBG('Videolink final: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://pornmeka.com':
			printDBG('PORNMEKA PARSER')
			COOKIEFILE = join(GetCookieDir(), 'pornmeka.cookie')
			self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornmeka.cookie', 'pornmeka.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, "license_code:.[']([^']+?)['],")[0].strip()
			printDBG('LICENSE CODE: ' + license_code)
			if not license_code:
				SetIPTVPlayerLastHostError(_('THIS VIDEO IS JUST A PREVIEW ON EXTERNAL STORAGE.\nVIEWING IT HERE IS NOT SUPPORTED.'))
				return []
			videoUrl = self.cm.ph.getSearchGroups(data, "video.{,6}url.{,3}[']([^']+?)[']")[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://jizzberry.com':
			printDBG('JIZZBERRY PARSER')
			COOKIEFILE = join(GetCookieDir(), 'jizzberry.cookie')
			self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'jizzberry.cookie', 'jizzberry.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall(r'video_source_."\ssrc=["]([^@]+?)["]', data, re.S)[0]
			printDBG('Videolink first: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://moantube.com':
			printDBG('MOANTUBE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'moantube.cookie')
			self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'moantube.cookie', 'moantube.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, "license_code:.[']([^']+?)['],")[0].strip()
			printDBG('LICENSE CODE: ' + license_code)
			if not license_code:
				SetIPTVPlayerLastHostError(_('THIS VIDEO IS JUST A PREVIEW ON EXTERNAL STORAGE.\nVIEWING IT HERE IS NOT SUPPORTED.'))
				return []
			videoUrl = self.cm.ph.getSearchGroups(data, "video.{,6}url.{,3}[']([^']+?)[']")[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.definebabe.com':
			printDBG('DEFINEBABE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'definebabe.cookie')
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER}
			sts, data = self.cm.getPage(url, params)
			if not sts:
				return []
			match = re.search('file.{,10}[/]([^"]+?)[,]', data)
			if match:
				video_php = match.group(1).strip()
				stream_url = 'https://' + video_php
			if not match:
				return []
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(stream_url, params)
			if not sts or response is None:
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			if not real_url.startswith('http'):
				return []
			videoUrl = str(real_url)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://fit.porn':
			COOKIEFILE = join(GetCookieDir(), 'fitporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'fitporn.cookie', 'fitporn.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			try:
				videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data, re.S)[-1]
				printDBG('Videolink first: ' + videoUrl)
			except Exception:
				embedUrl = re.search('getEmbed.+\n.+\n.+src=["]([a-z:/0-9.]+?)["]', data).group(1)
				printDBG('EMBEDURL: ' + embedUrl)
				sts, data2 = self.get_Page(embedUrl)
				videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data2, re.S)[-1]
				printDBG('EMBED VIDEOURL: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			videoUrl = videoUrl.replace('true', 'false')
			printDBG('Videolink third: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.rat.xxx':
			COOKIEFILE = join(GetCookieDir(), 'ratxxx.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'ratxxx.cookie', 'rat.xxx', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, "license_code:.[']([^']+?)['],")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			try:
				videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data, re.S)[-1]
				printDBG('Videolink first: ' + videoUrl)
			except Exception:
				embedUrl = re.search('getEmbed.+\n.+\n.+src=["]([a-z:/0-9.]+?)["]', data).group(1)
				printDBG('EMBEDURL: ' + embedUrl)
				sts, data2 = self.get_Page(embedUrl)
				videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data2, re.S)[-1]
				printDBG('EMBED VIDEOURL: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			videoUrl = videoUrl.replace('true', 'false')
			printDBG('Videolink third: ' + videoUrl)
			return videoUrl

		if parser == 'https://fapnfuck.com':
			printDBG('FAPNFUCK PARSER')
			COOKIEFILE = join(GetCookieDir(), 'fapnfuck.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'fapnfuck.cookie', 'fapnfuck.com', self.defaultParams)
			if not sts:
				return ''
			patterns = [
				r'<source[^>]+src=["\']([^"\']+)',
				r'(?:videoUrl|video_url|contentUrl|file)["\'\s:]+["\'](https?://[^"\']+)',
			]
			for pattern in patterns:
				m = re.search(pattern, data, re.I | re.S)
				if m and m.group(1).strip():
					videoUrl = m.group(1).strip()
					printDBG('FAPNFUCK VIDEOURL: ' + videoUrl)
					return videoUrl
			return ''

		if parser == 'https://fapality.com':
			printDBG('FAPALITY PARSER')
			COOKIEFILE = join(GetCookieDir(), 'fapality.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'fapality.cookie', 'fapality.com', self.defaultParams)
			stream_url = re.findall(r'video_source_."\ssrc=["]([^@]+?)["]', data, re.S)[0]
			printDBG('EMBED VIDEOURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(stream_url, params)
			if not sts or response is None:
				printDBG("FAPALITY: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REAL URL: ' + str(real_url))
			response.close()
			if not real_url.startswith('http'):
				printDBG("FAPALITY: incorrect redirect URL")
				return []
			if real_url:
				return urlparser.decorateUrl(real_url, {'Referer': url})
			return real_url

		if parser == 'https://homemade.xxx':
			printDBG('HOMEMADE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'homemade.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'homemade.cookie', 'homemade.xxx', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, "license_code:.[']([^']+?)['],")[0].strip()
			try:
				videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data, re.S)[-1]
				printDBG('Videolink first: ' + videoUrl)
			except Exception:
				embedUrl = re.search('getEmbed.+\n.+\n.+src=["]([a-z:/0-9.]+?)["]', data).group(1)
				sts, data2 = self.get_Page(embedUrl)
				videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data2, re.S)[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			videoUrl = videoUrl.replace('true', 'false')
			return videoUrl

		if parser == 'https://anal.media':
			printDBG('ANALMEDIA PARSER')
			COOKIEFILE = join(GetCookieDir(), 'analmedia.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'analmedia.cookie', 'anal.media', self.defaultParams)
			playlist = self.cm.ph.getSearchGroups(data, r'video:url"\scontent=["]([^ ^#]+?m3u8)["]', 1, True)[0]
			if playlist:
				tmp = getDirectM3U8Playlist(playlist, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			return videoUrl

		if parser == 'https://www.porngem.com':
			printDBG('PORNGEM PARSER')
			COOKIEFILE = join(GetCookieDir(), 'porngem.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'porngem.cookie', 'porngem.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, "license_code:.[']([^']+?)['],")[0].strip()
			try:
				videoUrl = re.findall("video.{1,6}url.{2,4}[']([^']+?)[']", data, re.S)[-1]
				printDBG('Videolink first: ' + videoUrl)
			except Exception:
				embedUrl = re.search('iframe.+src=["]([a-z:/0-9.]+?)["]', data).group(1)
				sts, data2 = self.get_Page(embedUrl)
				videoUrl = re.findall("video.{1,6}url.{2,4}[']([^']+?)[']", data2, re.S)[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			return videoUrl

		if parser == 'https://lustysextube.com':
			printDBG('LUSTYSEXTUBE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'lustysextube.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'lustysextube.cookie', 'lustysextube.com', self.defaultParams)
			playlist = self.cm.ph.getSearchGroups(data, 'data-src-hls=["]([^ ^#]+?m3u8)["]', 1, True)[0]
			if playlist:
				tmp = getDirectM3U8Playlist(playlist, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			return videoUrl

		if parser == 'https://www.sexsq.com':
			printDBG('SEXSQ PARSER')
			COOKIEFILE = join(GetCookieDir(), 'sexsq.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'sexsq.cookie', 'sexsq.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)[']", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			videoUrl = videoUrl.split('/?br')[0]
			printDBG('Videolink third: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://bigboobsxxx.com':
			printDBG('BIGBOOBS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'bigboobs.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'bigboobs.cookie', 'bigboobsxxx.com', self.defaultParams)
			stream_url = self.cm.ph.getSearchGroups(data, 'contentUrl":.["]([^"]+?)["]')[0]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(stream_url, params)
			if not sts or response is None:
				printDBG("BIGBOOBS: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			response.close()
			tmp = getDirectM3U8Playlist(real_url, checkContent=True, sortWithMaxBitrate=999999999)
			for item in tmp:
				return item['url']
			return videoUrl

		if parser == 'https://www.tabootube.xxx':
			printDBG('TABOOTUBE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'tabootube.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'tabootube.cookie', 'tabootube.xxx', self.defaultParams)
			EmbedUrl = self.cm.ph.getSearchGroups(data, r'embedUrl":\s["]([^"]+?)["],', 1, True)[0]
			printDBG('Embed URL: ' + EmbedUrl)
			sts, data = self.get_Page(EmbedUrl)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@']+?e)[']", data, re.S)[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://leslez.com':
			printDBG('LESLEZ PARSER')
			COOKIEFILE = join(GetCookieDir(), 'leslez.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'leslez.cookie', 'leslez.com', self.defaultParams)
			stream_url = self.cm.ph.getSearchGroups(data, r'source\ssrc=["]([^"]+?)["]')[0]
			if stream_url.startswith('/'):
				stream_url = 'https://leslez.com' + stream_url
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(stream_url, params)
			if not sts or response is None:
				printDBG("LESLEZ: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			response.close()
			# HLS master with 360p first
			return self._bestM3U8Variant(urlparser.decorateUrl(real_url, {'Referer': url}), checkExt=False) or urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://hardporno.tube':
			printDBG('HARDPORNO PARSER')
			COOKIEFILE = join(GetCookieDir(), 'hardporno.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'hardporno.cookie', 'hardporno.tube', self.defaultParams)
			stream_url = self.cm.ph.getSearchGroups(data, r'source\ssrc=["]([^"]+?)["]')[0]
			if not stream_url:
				links = [v.replace('\\u002F', '/') for v in re.findall(r'"(https:\\u002F\\u002Fvcdn[^"]+?\.mp4)"', data) if 'media=hls' not in v]
				if not self._uhdAllowed():
					links = [v for v in links if not v.endswith('_2160.mp4')] or links
				stream_url = links[-1] if links else ''
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(stream_url, params)
			if not sts or response is None:
				printDBG("HARDPORNO: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://eboblack.com':
			printDBG('EBOBLACK PARSER')
			COOKIEFILE = join(GetCookieDir(), 'eboblack.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'eboblack.cookie', 'eboblack.com', self.defaultParams)
			stream_url = self.cm.ph.getSearchGroups(data, r'source\ssrc=["]([^"]+?)["]')[0]
			if not stream_url:
				links = [v.replace('\\u002F', '/') for v in re.findall(r'"(https:\\u002F\\u002Fvcdn[^"]+?\.mp4)"', data) if 'media=hls' not in v]
				if not self._uhdAllowed():
					links = [v for v in links if not v.endswith('_2160.mp4')] or links
				stream_url = links[-1] if links else ''
			if stream_url.startswith('/'):
				stream_url = 'https://eboblack.com' + stream_url
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(stream_url, params)
			if not sts or response is None:
				printDBG("EBOBLACK: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://deepfaceporn.com':
			printDBG('DEEPFACEPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'deepspaceporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'deepfaceporn.cookie', 'deepfaceporn.com', self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, r'iframe\ssrc=["]([^"]+?)["]')[0]
			sts, data2 = self.get_Page(embedUrl)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data2, r'source\ssrc=["]([^"]+?mp4)["]')[0]
			printDBG('videoURL: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.pornekip.com':
			printDBG('PORNEKIP PARSER')
			COOKIEFILE = join(GetCookieDir(), 'pornekip.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornekip.cookie', 'pornekip.com', self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, 'iframe.{,30}src=["]([^"]+?)["]')[0]
			printDBG('EMBED URL (IF NEED): ' + embedUrl)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = self.cm.ph.getSearchGroups(data, "video_url:.[']([^']+?)[']")[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('videoURL: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.sexocean.net':
			printDBG('SEXOCEAN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'sexocean.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPageWithCFBypass(url)
			if not sts:
				return ''
			videoUrl = re.findall(r'contentUrl":\s["]([^"]+?)["]', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
			printDBG('videoURL: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://hog.tv':
			printDBG('HOG TV PARSER')
			vidM = re.search(r'/video/(\d+)', url)
			videoId = vidM.group(1) if vidM else ''
			if not videoId:
				return ''
			COOKIEFILE = join(GetCookieDir(), 'hogtv.cookie')
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			HTTP_HEADER['X-Requested-With'] = 'XMLHttpRequest'
			self.defaultParams = {'header': HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.cm.getPage('https://hog.tv/api/video-info', self.defaultParams, {'videoId': videoId})
			if not sts or not data:
				return ''
			try:
				obj = json.loads(data)
			except Exception:
				return ''
			sources = ((obj.get('playerData') or {}).get('sources')) or []
			videoUrl = ''
			for s in sources:
				if isinstance(s, dict) and s.get('quality') == '720p':
					videoUrl = s.get('src', '')
					break
			if not videoUrl and sources and isinstance(sources[0], dict):
				videoUrl = sources[0].get('src', '')
			if not videoUrl:
				return ''
			if videoUrl.startswith('//'):
				videoUrl = 'https:' + videoUrl
			printDBG('LINK: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.fetishshrine.com':
			printDBG('FETISHSHRINE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'fetishshrine.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'fetishshrine.cookie', 'fetishshrine.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r"video_url:\s[']([^']+\.mp4[^']*)[']")[-1]
			if not videoUrl:
				return ''
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("FETISHSHRINE: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://wankgalore.com':
			printDBG('WANKGALORE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'wankgalore.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'wankgalore.cookie', 'wankgalore.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search("video/mp4',src:[']([^']+?)[']", data).group(1)
			printDBG('LINK: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.uiporn.com':
			printDBG('UIPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'uiporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'uiporn.cookie', 'uiporn.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search(r"rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = self.cm.ph.getSearchGroups(data, r"video_url:\s[']([^']+?)[']")[-1]
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("UIPORN: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://www.dafreeporn.com':
			printDBG('DAFREEPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'dafreeporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'dafreeporn.cookie', 'dafreeporn.com', self.defaultParams)
			embedUrl = re.search('iframe.{,30}src=["]([a-z:/0-9.]+?)["]', data).group(1)
			sts, data2 = self.get_Page(embedUrl)
			license_code = self.cm.ph.getSearchGroups(data2, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data2).group(1)
			videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?|http[^']+?)[']", data2, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = videoUrl
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("DAFREEPORN: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

		if parser == 'https://www.cuckoldsporn.com':
			printDBG('CUCKOLDSPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'cuckoldsporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'cuckoldsporn.cookie', 'cuckoldsporn.com', self.defaultParams)
			if not sts or not data:
				return ''

			license_code = self.cm.ph.getSearchGroups(data, r'license_code\s*[:=]\s*[\"\']([^\"\']+)', 1, True)[0].strip()
			# video_url is 360p, video_alt_url 720p
			videoUrl = self._pickByHeight(self._mediaCandidates(data))
			patterns = [] if videoUrl else [
				r'[\"\']video_url[\"\']\s*[:=]\s*[\"\']([^\"\']+)',
				r'video_url\s*[:=]\s*[\"\']([^\"\']+)',
				r'[\"\']videoUrl[\"\']\s*[:=]\s*[\"\']([^\"\']+)',
				r'[\"\']contentUrl[\"\']\s*:\s*[\"\']([^\"\']+\.(?:mp4|m3u8)(?:[^\"\']*)?)',
				r'<source[^>]+src=[\"\']([^\"\']+\.(?:mp4|m3u8)(?:[^\"\']*)?)',
			]
			for pattern in patterns:
				videoUrl = self.cm.ph.getSearchGroups(data, pattern, 1, True)[0]
				if videoUrl:
					break
			if not videoUrl:
				printDBG('CUCKOLDSPORN: video URL not found in page')
				return ''

			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl and license_code:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink decrypted: ' + videoUrl)
			if videoUrl.startswith('//'):
				videoUrl = 'https:' + videoUrl
			elif videoUrl.startswith('/'):
				videoUrl = 'https://www.cuckoldsporn.com' + videoUrl
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if sts and response is not None:
				real_url = response.geturl()
				response.close()
				printDBG('REALURL: ' + str(real_url))
				return urlparser.decorateUrl(real_url, {'Referer': url})
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://some.porn':
			printDBG('SOMEPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'someporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'someporn.cookie', 'some.porn', self.defaultParams)
			EmbedUrl = self.cm.ph.getSearchGroups(data, r'og:video"\scontent=["](https[^"]+?)["]', 1, True)[0]
			printDBG('Embed URL: ' + EmbedUrl)
			sts, data = self.get_Page(EmbedUrl)
			if not sts:
				return ''
			data = self.cm.ph.getDataBeetwenMarkers(data, 'video id="video-page', '</video>', False)[1]
			videoUrl = re.findall('source\n.+src=["]([^"]+?)["]', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
			printDBG('videoURL: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://pornxxxvideos.net':
			printDBG('PORNXXXVIDEOS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'pornxxxvideos.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornxxxvideos.cookie', 'pornxxxvideos.net', self.defaultParams)
			data = self.cm.ph.getDataBeetwenMarkers(data, 'VIDEO CONTENT', 'layoutControls', False)[1]
			videoUrl = self.cm.ph.getSearchGroups(data, 'src=["]([^"]+?mp4)["]')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'source\ssrc=["]([^"]+?)["]', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, 'src=["]([^"]+?mp4)["]', 1, True)[0]
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://xdporner.com':
			printDBG('XDPORNER PARSER')
			COOKIEFILE = join(GetCookieDir(), 'xdporner.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'xdporner.cookie', 'xdporner.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, 'src=["]([^"]+?mp4)["]')[0]
			if videoUrl.startswith('/'):
				videoUrl = 'https://xdporner.com' + videoUrl
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://mondetube.com':
			printDBG('MONDETUBE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'mondetube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'mondetube.cookie', 'mondetube.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = self.cm.ph.getSearchGroups(data, r"video.{,5}url.{0,1}:\s[']([^']+?)[']")[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("MONDETUBE: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://pimpbunny.com':
			printDBG('PIMPBUNNY PARSER')
			COOKIEFILE = join(GetCookieDir(), 'pimpbunny.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pimpbunny.cookie', 'pimpbunny.com', self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search(r"rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall(r"video.{,5}url.{0,1}:\s[']([^']+?\.mp4[^']*)[']", data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[-1]
			if not videoUrl:
				return ''
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("PIMPBUNNY: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://fyxxr.to':
			printDBG('FYXXR PARSER')
			COOKIEFILE = join(GetCookieDir(), 'fyxxr.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'fyxxr.cookie', 'fyxxr.to', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search(r"rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall(r"video.{,5}url.{0,1}:\s[']([^']+?)[']", data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("FYXXR: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://www.superporn.com':
			printDBG('SUPERPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'superporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'superporn.cookie', 'superporn.com', self.defaultParams)
			videoUrl = re.findall(r'<source\ssrc="(.*?)"', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[-1]
			printDBG('videoURL: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://www.crazy-amateurs.com':
			printDBG('CRAZYAMATEURS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'crazyamateurs.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'crazyamateurs.cookie', 'crazy-amateurs.com', self.defaultParams)
			EmbedUrl = self.cm.ph.getSearchGroups(data, 'iframe.{1,20}src=["](.+?)["]', 1, True)[0]
			sts, data2 = self.get_Page(EmbedUrl)
			if not sts:
				return ''
			videoUrl = re.findall(r'<source\ssrc="(.*?)"', data2, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[-1]
			printDBG('videoURL: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://xxxelf.com':
			printDBG('XXXELF PARSER')
			COOKIEFILE = join(GetCookieDir(), 'xxxelf.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'xxxelf.cookie', 'xxxelf.com', self.defaultParams)
			apiUrl = self.cm.ph.getSearchGroups(data, 'contentUrl":["]([^"]+?)["],"actor')[0]
			printDBG('APIURL: ' + apiUrl)
			ID = self.cm.ph.getSearchGroups(apiUrl, r'\d[/]([0-9]+)$')[0]
			printDBG('ID: ' + str(ID))
			res = self.cm.ph.getSearchGroups(apiUrl, 'ce[/]([0-9]+)[/]')[0]
			printDBG('RES: ' + str(res))
			videoUrl = 'https://xxxelf.com/api/video/%s/stream/%s' % (ID, res)
			if videoUrl:
				printDBG('videoURL: ' + videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://modporn.com':
			printDBG('MODPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'modporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'modporn.cookie', 'modporn.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall(r"video.{,5}url.{0,1}:\s[']([^']+?)[']", data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("MODPORN: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://max.porn':
			printDBG('MAXPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'maxporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPageWithCFBypass(url)
			if not sts:
				return ''
			videoUrl = re.findall(r'source\ssrc=["]([^$]+?)["]', data, re.S)
			if videoUrl:
				printDBG('ALL LINKS: ' + str(videoUrl))
				videoUrl = videoUrl[-1]
				printDBG('MAIN URL: ' + str(videoUrl))
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("MAXPORN: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			tmp = getDirectM3U8Playlist(real_url, checkContent=True, sortWithMaxBitrate=999999999)
			for item in tmp:
				printDBG('M3U8 END: ' + item['url'])
				return item['url']
			return videoUrl

		if parser == 'https://eroticmv.com':
			printDBG('EROTICMV PARSER V3')
			COOKIEFILE = join(GetCookieDir(), 'eroticmv.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPageWithCFBypass(url)
			if not sts:
				return ''

			videoUrls = []
			for pattern in (
				r'video:url"\scontent="([^"]+m3u8)["]',
				r"<source[^>]+src=[\"']([^\"']+?m3u8[^\"']*)",
				r"[\"']contentUrl[\"']\s*:\s*[\"']([^\"']+?m3u8[^\"']*)",
			):
				try:
					found = self.cm.ph.getSearchGroups(data, pattern, 1, True)
					for item in found:
						if item and item not in videoUrls:
							videoUrls.append(item)
				except Exception:
					pass
			printDBG('EROTICMV VIDEO URLS V3: ' + str(videoUrls))

			for candidate in videoUrls:
				videoUrl = (candidate or '').strip().replace(r'\/', '/')
				token = videoUrl
				if token.startswith('http://') or token.startswith('https://'):
					token = token.split('://', 1)[1]
				if '/' not in token and token.lower().endswith('.m3u8'):
					encoded = token[:-5]
					try:
						padded = encoded + ('=' * ((4 - len(encoded) % 4) % 4))
						decoded = base64.b64decode(padded).decode('utf-8').strip()
						if decoded.startswith('http://') or decoded.startswith('https://'):
							videoUrl = decoded
							printDBG('EROTICMV DECODED CDN URL V3: ' + videoUrl)
					except Exception as e:
						printDBG('EROTICMV Base64 decode exception V3: ' + str(e))
				if videoUrl.startswith('//'):
					videoUrl = 'https:' + videoUrl
				if not videoUrl:
					continue
				# every candidate is an m3u8 match, but the base64-decoded CDN URL has no .m3u8 in it
				meta = {'Referer': url, 'Origin': 'https://eroticmv.com', 'User-Agent': self.HTTP_HEADER.get('User-Agent', USER_AGENT), 'iptv_proto': 'm3u8'}
				return urlparser.decorateUrl(videoUrl, meta)
			return ''

		if parser == 'https://porn4days.pw':
			printDBG('PORN4DAYS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'porn4days.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPageWithCFBypass(url)
			if not sts:
				return ''
			embedUrl = self.cm.ph.getSearchGroups(data, "videoPlayer.{,40}src=[']([^']+?)[']")[0]
			if not embedUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, r'const\sSERVER\d_URL\s=\s["]([^"]+)["];')[0]
			if not embedUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, r'embedUrl":\s["]([^"]+)["]')[0]
			printDBG('EMBEDURL: ' + embedUrl)
			if 'openload' in embedUrl:
				msg = _('THIS VIDEO HAS BEEN REMOVED DUE TO COPYRIGHT INFRINGEMENT.\n PLEASE CHOOSE ANOTHER ONE!')
				self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_INFO)
				return self.listsItems(-1, self.MAIN_URL, 'PORN4DAYS')
			# the page names up to four mirrors (SERVER1_URL..): turbovidhls, direct files, streamtape, doodstream ...
			servers = [s for s in re.findall(r'SERVER\d_URL\s*=\s*"([^"]+)"', data) if s]
			if embedUrl and embedUrl not in servers:
				servers.insert(0, embedUrl)
			for server in servers:
				if 'turbovidhls.' in server:
					videoUrl = self._turbovidhls(server, url)
				elif re.search(r'\.(?:mp4|m3u8)(?:\?|$)', server):
					# a direct file (iceyfile, redirects to a tokenised download URL)
					videoUrl = urlparser.decorateUrl(server, {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})
				elif self.up.checkHostSupport(server) == 1:
					links = self.up.getVideoLinkExt(server)
					videoUrl = links[0].get('url', '') if links else ''
				else:
					videoUrl = ''
				printDBG('PORN4DAYS %s -> %s' % (server, videoUrl))
				if videoUrl:
					return videoUrl
			sts, data2 = self.get_Page(embedUrl)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data2, r'source\ssrc=["]([^"]+?)["]')[0]
			if videoUrl:
				printDBG('videoURL: ' + videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://8kporner.com':
			printDBG('8KPORNER PARSER')
			COOKIEFILE = join(GetCookieDir(), '8kporner.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			if 'html' in url:
				printDBG('VideoPage: ' + url)
				sts, data = self.getPage(url, '8kporner.cookie', '8kporner.com', self.defaultParams)
				if not sts:
					return ''
				videoUrl = re.findall(r'file":\s["]([^"]+?)["],\s"label', data, re.S)[0]
				printDBG('direkt link: ' + str(videoUrl))
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			else:
				printDBG('Selected Resolution: ' + url)
				videoUrl = urlparser.decorateUrl(url, {'Referer': url})
				if videoUrl:
					return videoUrl
			return ''

		if parser == 'https://www.pornpapa.com':
			printDBG('PORNPAPA PARSER')
			COOKIEFILE = join(GetCookieDir(), 'pornpapa.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPageWithCFBypass(url)
			if not sts:
				return ''
			videoUrl = re.findall(r"source.src=[']([^']+?mp4/)[']\stype='video/mp4", data, re.S)[-1]
			printDBG('VIDEOURL: ' + videoUrl)
			self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0'
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("PORNPAPA: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://hqfap.com':
			printDBG('HQFAP PARSER')
			COOKIEFILE = join(GetCookieDir(), 'hqfap.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			if 'html' in url:
				printDBG('VideoPage: ' + url)
				sts, data = self.getPage(url, 'hqfap.cookie', 'hqfap.com', self.defaultParams)
				if not sts:
					return ''
				videoUrl = re.findall(r'file":\s["]([^"]+?)["],\s"label', data, re.S)[0]
				printDBG('direkt link: ' + str(videoUrl))
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			else:
				printDBG('Selected Resolution: ' + url)
				videoUrl = urlparser.decorateUrl(url, {'Referer': url})
				if videoUrl:
					return videoUrl

		if parser == 'https://naijapornsite.com':
			printDBG('NAIJAPORNSITE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'naijapornsite.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPageWithCFBypass(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'"contentUrl"\scontent=["]([^"]+mp4)["]>')[0]
			if videoUrl:
				videoUrl = videoUrl.replace('&#039;', "'")
				printDBG('direkt link: ' + str(videoUrl))
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			else:
				msg = _('THIS LINK CONTAINS PHOTOS ONLY.\n PLEASE CHOOSE ANOTHER ONE!')
				self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_INFO)
				return []

		if parser == 'https://www.nuvid.com':
			COOKIEFILE = join(GetCookieDir(), 'nuvid.cookie')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			videoID = self.cm.ph.getSearchGroups(url, 'video[/]([0-9]+?)[/]')[0]
			if videoID:
				embedUrl = 'https://m.nuvid.com/play/%s?from=video_bottom' % videoID
				printDBG('EMBEDURL' + embedUrl)
				sts, data = self.getPageWithCFBypass(embedUrl)
				videoUrl = self.cm.ph.getSearchGroups(data, r'holder\svideo.+href=["]([^"]+?)["]\sdata')[0]
				printDBG('videourl: ' + videoUrl)
				if videoUrl:
					return videoUrl
			return ''

		if parser == 'https://juicyvid.com':
			printDBG('JUICYVID PARSER')
			COOKIEFILE = join(GetCookieDir(), 'juicyvid.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'juicyvid.cookie', 'juicyvid.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall(r"video.{,5}url.{0,1}:\s[']([^']+?)[']", data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[-1]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("JUICYVID: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://www.lapippa.com':
			printDBG('LAPIPPA PARSER')
			COOKIEFILE = join(GetCookieDir(), 'lapippa.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			embed = self.cm.ph.getSearchGroups(data, '''data-src=["'](/embed/[^"']+)''')[0]
			if embed:
				sts, data = self.cm.getPage('https://www.lapippa.com' + embed, self.defaultParams)
				if not sts:
					return ''
			videoUrl = re.findall(r'<source\ssrc="(.*?)"', data, re.S)
			if videoUrl:
				printDBG('videoURL: ' + str(videoUrl[-1]))
				return videoUrl[-1]
			return ''

		if parser == 'https://faplane.com':
			printDBG('FAPLANE V6 PARSER')
			COOKIEFILE = join(GetCookieDir(), 'faplane.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			# Next.js site: the player asks /api/v1/videos/<slug>/playback (by slug - the uuid gives "not playable")
			m = re.search(r'faplane\.com/(?:video/([0-9]+)(?:/([^/?#]+))?|watch/([^/?#]+))', url)
			if m:
				slug = m.group(2) or m.group(3)
				if not slug:
					sts, data = self.getPage('https://faplane.com/api/v1/videos/by-pid/' + m.group(1), 'faplane.cookie', 'faplane.com', self.defaultParams)
					slug = self.cm.ph.getSearchGroups(data, r'''"slug"\s*:\s*"([^"]+)"''')[0] if sts else ''
				if slug:
					sts, data = self.getPage('https://faplane.com/api/v1/videos/%s/playback' % slug, 'faplane.cookie', 'faplane.com', self.defaultParams)
					try:
						playback = json.loads(data) if sts else {}
					except Exception:
						playback = {}
					if playback.get('mp4_url'):
						return urlparser.decorateUrl(playback['mp4_url'], {'Referer': 'https://faplane.com/', 'User-Agent': self.USER_AGENT})
					if playback.get('hls_master_url'):
						videoUrl = self._bestM3U8Variant(urlparser.decorateUrl(playback['hls_master_url'], {'Referer': 'https://faplane.com/', 'User-Agent': self.USER_AGENT}))
						if videoUrl:
							return videoUrl
					printDBG('FAPLANE playback: %s' % str(data)[:200])
			sts, data = self.getPage(url, 'faplane.cookie', 'faplane.com', self.defaultParams)
			if not sts or not data:
				return []
			# (contentUrl in the JSON-LD is the /watch/ page, not the video)
			for pat in (r'<source[^>]+src=["\']([^"\']+)', r'videoUrl["\']?\s*[:=]\s*["\']([^"\']+)'):
				m = re.search(pat, data, re.I | re.S)
				if m and m.group(1):
					videoUrl = self.cm.getFullUrl(m.group(1), url)
					printDBG('FAPLANE direct videoURL: ' + videoUrl)
					return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*[:=]\s*['"]([^'"]+?)['"]''')[0].strip()
			videoUrls = re.findall(r'''video.{0,8}url.{0,3}[:=]\s*['"]([^'"]+?)['"]''', data, re.S | re.I)
			videoUrl = videoUrls[-1] if videoUrls else ''
			if not videoUrl:
				for pat in (r'playerData.{0,500}?file\s*[:=]\s*["\']([^"\']+)', r'file\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)(?:\?[^"\']*)?)'):
					m = re.search(pat, data, re.I | re.S)
					if m:
						videoUrl = m.group(1)
						break
			if not videoUrl:
				printDBG('FAPLANE: no video URL found in page')
				return []
			if 'function/0/' in videoUrl:
				if not license_code:
					printDBG('FAPLANE: encrypted URL found but license_code is missing')
					return []
				videoUrl = decryptHash(videoUrl, license_code, '16')
			videoUrl = self.cm.getFullUrl(videoUrl, url)
			printDBG('FAPLANE resolved videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG('FAPLANE: failed to retrieve the stream URL')
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://www.inxxx.com':
			printDBG('INXXX PARSER')
			COOKIEFILE = join(GetCookieDir(), 'inxxx.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'inxxx.cookie', 'inxxx.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = re.findall(r"video.{,5}url.{0,1}:\s[']([^']+?)['],.{,15}postfix", data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("INXXX: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://www.fucker.com':
			printDBG('FUCKER PARSER')
			COOKIEFILE = join(GetCookieDir(), 'fucker.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'fucker.cookie', 'fucker.com', self.defaultParams)
			videoUrl = re.findall(r'<source\ssrc="(.*?)"\stype="video/mp4', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
			videoUrl = videoUrl.replace("&amp;", "&")
			printDBG('VideoURL fixed: ' + videoUrl)
			return videoUrl

		if parser == 'https://w4nkr.com':
			printDBG('W4NKR PARSER')
			COOKIEFILE = join(GetCookieDir(), 'w4nkr.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'w4nkr.cookie', 'w4nkr.com', self.defaultParams)
			videoUrl = re.findall(r'source\ssrc=["]([^"]+?)["]\stype="video/mp4', data, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("W4NKR: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://femefun.com':
			printDBG('FEMEFUN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'femefun.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'femefun.cookie', 'femefun.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			return videoUrl or ""

		if parser == 'https://en.pornoreino.com':
			COOKIEFILE = join(GetCookieDir(), 'pornoreino.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornoreino.cookie', 'pornoreino.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)['],", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			if 'mp4/' in videoUrl:
				videoUrl = videoUrl.replace('mp4/', 'mp4?rnd=') + rnd
			printDBG('Videolink third: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.whoreshub.com':
			COOKIEFILE = join(GetCookieDir(), 'whoreshub.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'whoreshub.cookie', 'whoreshub.com', self.defaultParams)
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			refID = self.cm.ph.getSearchGroups(data, '''og:image".content=["]([^@]+?)[/]contents''')[0]
			printDBG('REFID: ' + str(refID))
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0]
			videoUrl = re.findall("video.{1,6}url.{1,3}[']([^']+?)[']", data, re.S)
			videoUrl = videoUrl[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				videoID = re.search("file.{9,35}[/]([^']+?)[_]", videoUrl).group(1)
				printDBG('Fetched videoID: ' + str(videoID))
				token = re.search("1[/]([^']+?)[/]", videoUrl).group(1)
				printDBG('Fetched Token: ' + str(token))
				videoUrl = refID + '/contents/videos/' + videoID + '.mp4?expires=' + rnd + '&token=' + token
				printDBG('Videolink third: ' + videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			return ''

		if parser == 'https://veporn.com':
			# VEPORN-clips stores the direct cdnUrl (an actual .mp4 file) as the
			# item's URL, so most videos never need a page fetch/parse below at
			# all - that HTML parsing only remains as a fallback for anything
			# that still points at a watch-page URL (e.g. old search-history entries).
			if 'mp4' in url:
				printDBG('VEPORN VIDEOURL: ' + url)
				return url
			COOKIEFILE = join(GetCookieDir(), 'veporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'veporn.cookie', 'veporn.com', self.defaultParams)
			if not sts:
				return ''
			try:
				videoUrl = re.search('contentUrl...":...["]([^ß]+?mp4)...["]', data).group(1)
				return videoUrl
			except Exception:
				pass
			try:
				videoUrl = re.search('source.src=["]([^ß]+?)["].{9,12}/mp4', data).group(1)
				return videoUrl
			except Exception:
				pass
			try:
				videoUrl = re.search('width="560.{9,15}src=["]([^ß]+?)["]', data).group(1)
			except Exception:
				return ''
			sts, data2 = self.getPage(videoUrl, 'veporn.cookie', 'veporn.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall('source.src=.["]([^"]+?)["]', data2, re.S)
			if not videoUrl:
				return ''
			return "https:" + videoUrl[-1].replace('\\', '')

		if parser == 'https://pxp.news':
			COOKIEFILE = join(GetCookieDir(), 'pornxp.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornxp.cookie', 'pornxp.org', self.defaultParams)
			videoUrl = re.findall('source.src=["]([^"]+?)["].title', data, re.S)
			printDBG('Links: ' + str(videoUrl))
			videoUrl = "https:" + videoUrl[-1]
			printDBG('LEGJOBB LINK: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://pornoflix.com':
			COOKIEFILE = join(GetCookieDir(), 'pornoflix.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornoflix.cookie', 'pornoflix.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, '''"contentUrl":"(https?://[^"]+?)"''')[0]
			if videoUrl:
				return videoUrl
			videoUrl = re.findall('source.src=["]([^"]+?)["].type', data, re.S)
			try:
				videoUrl = videoUrl[-1]
				return videoUrl
			except Exception:
				headUrl = re.search('id="player.+\n.+src=["]([^"]+?)["]', data).group(1)
				sts, data2 = self.get_Page(headUrl)
				if not sts:
					return ''
				videoUrls = re.findall("a.href=[']([^']+?)[']", data2, re.S)
				videoUrl = videoUrls[-1]
				videoUrl = 'https:' + videoUrl
				return videoUrl
			return ''

		if parser == 'https://pornyteen.com':
			COOKIEFILE = join(GetCookieDir(), 'pornyteen.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornyteen.cookie', 'pornyteen.com', self.defaultParams)
			videoUrl = re.findall('source.src=["]([^"]+?)["].type', data, re.S)
			videoUrl = videoUrl[-1]
			printDBG('Videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.pornid.xxx':
			COOKIEFILE = join(GetCookieDir(), 'pornid.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornid.cookie', 'pornid.com', self.defaultParams)
			data = self.cm.ph.getDataBeetwenMarkers(data, "} else {", "flashvars['js']='1';", False)[1]
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT}) if videoUrl else ''

		if parser == 'https://www.theyarehuge.com':
			COOKIEFILE = join(GetCookieDir(), 'theyarehuge.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'theyarehuge.cookie', 'theyarehuge.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''alt_url3:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''alt_url2:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''alt_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Legjobb URL: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Decoding: ' + videoUrl)
			printDBG('Videolink second: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT}) if videoUrl else ''

		if parser == 'https://ok.xxx':
			COOKIEFILE = join(GetCookieDir(), 'okxxx.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'okxxx.cookie', 'ok.xxx', self.defaultParams)
			videoUrls = self.cm.ph.getAllItemsBeetwenMarkers(data, 'source src="', '" type="video/mp4', False)
			if not videoUrls:
				return ''
			videoUrl = urlparser.decorateUrl(videoUrls[-1], {'Referer': 'https://ok.xxx'})
			# the _720p.mp4 link answers with an HLS master that lists 360p first
			return self._bestM3U8Variant(videoUrl, checkExt=False) or videoUrl

		if parser == 'https://www.laidhub.com':
			COOKIEFILE = join(GetCookieDir(), 'laidhub.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'laidhub.cookie', 'laidhub.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].type="video/mp4''')[0]
			printDBG('Videolink: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT}) if videoUrl else ''

		if parser == 'https://momxl.com':
			COOKIEFILE = join(GetCookieDir(), 'momxl.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, r'<source\s+src="([^"]+)"', 1, True)[0]
			printDBG('Videolink: ' + str(videoUrl))
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://yourlust.com':
			COOKIEFILE = join(GetCookieDir(), 'yourlust.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, '''contentUrl.{2,10}=['"]([^"^']+?)['"]''')[0].strip()
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''source.{3,21}src=['"]([^"^']+?)['"].type''')[0].strip()
			printDBG('Videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.its.porn':
			COOKIEFILE = join(GetCookieDir(), 'itsporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, '''src-hls=['"]([^"^']+?)['"]''')[0].strip()
			if 'm3u8' in videoUrl:
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			printDBG('Videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://sex3.com':
			COOKIEFILE = join(GetCookieDir(), 'sex3.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			videoUrls = re.findall('source.{0,9}src="(.*?)".type', data, re.S)
			printDBG('Videolink: ' + str(videoUrls))
			return videoUrls[-1] if videoUrls else ''

		if parser == 'https://sextubefun.com/':
			COOKIEFILE = join(GetCookieDir(), 'sextubefun.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'sextubefun.cookie', 'sextubefun.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].type="video/mp4''')[0]
			printDBG('Videolink: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT}) if videoUrl else ''

		if parser == 'https://www.analdin.com':
			COOKIEFILE = join(GetCookieDir(), 'analdin.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'analdin.cookie', 'analdin.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url:\s*['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
			if videoUrl.startswith('/'):
				videoUrl = 'https://www.analdin.com' + videoUrl
			self.defaultParams['max_data_size'] = 0
			sts, data = self.getPage(videoUrl, 'analdin.cookie', 'analdin.com', self.defaultParams)
			return '' if not sts else data.meta['url']

		if parser == 'https://www.perfectgirls.xxx':
			baseUrl = strwithmeta(url)
			referer = baseUrl.meta.get('Referer', '')
			COOKIEFILE = join(GetCookieDir(), 'perfectgirls.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'perfectgirls.cookie', 'perfectgirls.com', self.defaultParams)
			if not sts:
				return ''
			# every <source> (360p/480p/720p, labelled) redirects to the same HLS master playlist; take the best variant
			# from it - the old fixed "1280" line match returned just "h" for portrait videos (1080x1920)
			sources = [(self._labelHeight(label), src) for src, label in re.findall(r'''<source[^>]+src=["']([^"']+)["'][^>]+label=["']([^"']+)["']''', data) if label != 'Auto']
			master = self._pickByHeight(sources)
			if not master:
				return ''
			videoUrl = self._bestM3U8Variant(urlparser.decorateUrl(master, {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')}), checkExt=False)
			return strwithmeta(videoUrl, {'iptv_proto': 'm3u8', 'Referer': url}) if videoUrl else ''

		if parser == 'https://jizzbunker.com':
			COOKIEFILE = join(GetCookieDir(), 'jizzbunker.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			embedUrl = self.cm.ph.getSearchGroups(data, '''embedUrl":['"]([^"^']+?)['"]''', 1, True)[0].replace(r"\/", "/")
			sts, data = self.get_Page(embedUrl)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''mp4.+:['"]([^"^']+?)['"]''', 1, True)[0]
			if videoUrl.startswith('/'):
				videoUrl = self.MAIN_URL + videoUrl
			printDBG('This is the end: ' + videoUrl)
			return videoUrl

		if parser == 'https://lulustream.com':
			COOKIEFILE = join(GetCookieDir(), 'lulustream.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''sources.{2,5}file:['"]([^"^']+?)['"]}''', 1, True)[0]
			printDBG('Fetched link: ' + videoUrl)
			if 'm3u8' in videoUrl:
				videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': "https://1fo1ndyf09qz.tnmr.org", "Origin": "https://lulustream.com"})
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			printDBG('This is the end: ' + videoUrl)
			return videoUrl

		if parser in ('https://luluvid.com', 'https://playmate.to', 'https://mixdrop.my'):
			# these embed hosts already have generic resolvers in urlparser.py
			# (parserJWPLAYER/parserPLAYMATE) - reuse them instead of duplicating
			videoUrl = self.up.getVideoLink(url)
			printDBG('VideoLink: ' + str(videoUrl))
			return videoUrl if videoUrl else ''

		if parser == 'https://voe.sx':
			# the urlparser's VOE parser is kept up to date; the old decoding below stays as the fallback
			try:
				for item in self.up.getVideoLinkExt(url) or []:
					if isinstance(item, dict) and item.get('url'):
						return item['url']
			except Exception:
				printExc()
			COOKIEFILE = join(GetCookieDir(), 'voe.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			baseUrl = self.cm.ph.getSearchGroups(data, '''location.{4,8}['"]([^"^']+?)['"];''', 1, True)[0]
			sts, data = self.get_Page(baseUrl)
			if not sts:
				return ''
			url = self.cm.ph.getDataBeetwenMarkers(data, "'hls': '", "'", False)[1]
			if 'm3u8' not in url:
				videoUrl = base64.b64decode(url)
				videoUrl = videoUrl.decode("utf-8")
				printDBG('Decoded Link: ' + str(videoUrl))
			if not videoUrl:
				videoUrl = self.cm.ph.getDataBeetwenMarkers(data, "'mp4': '", "'", False)[1]
			if 'm3u8' in videoUrl:
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			printDBG('Ready link: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.koloporno.com':
			COOKIEFILE = join(GetCookieDir(), 'koloporno.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'koloporno.cookie', 'koloporno.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'''<source\ssrc=['"]([^"^']+?)['"]''')[0]
			videoUrl = checkhttp(videoUrl)
			return videoUrl

		if parser == 'https://www.sunporno.com':
			COOKIEFILE = join(GetCookieDir(), 'sunporno.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			videoPage = re.findall('video src="(.*?)"', data, re.S)
			if videoPage:
				printDBG('Host videoPage:' + videoPage[0])
				return urlparser.decorateUrl(videoPage[0], {'Referer': url})
			return ''

		if parser == 'https://mini.zbiornik.com':
			COOKIEFILE = join(GetCookieDir(), 'zbiornikmini.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			videoUrl = checkhttp(videoUrl)
			return unquote(videoUrl)

		if parser == 'https://dato.porn':
			COOKIEFILE = join(GetCookieDir(), 'datoporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'datoporn.cookie', 'datoporn.co', self.defaultParams)
			if not sts:
				return ''
			allUrl = self.cm.ph.getDataBeetwenMarkers(data, 'Download:', '<div class="block-flagging">', False)[1]
			printDBG('Videok: ' + allUrl)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(allUrl, '<a href="', '" data', False)[1]
			printDBG('Link: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://www.porndroids.com':
			COOKIEFILE = join(GetCookieDir(), 'porndroids.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, '<source src="', '" type="video/mp4">', False)[1]
			videoUrl = videoUrl.replace('amp;', '')
			printDBG('Final Url: ' + videoUrl)
			return videoUrl

		if parser == 'https://videobin.co':
			baseUrl = strwithmeta(url)
			referer = baseUrl.meta.get('Referer', '')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			if referer != '':
				self.HTTP_HEADER['Referer'] = referer
			COOKIEFILE = join(GetCookieDir(), 'videobin.cookie')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			data = self.cm.ph.getDataBeetwenMarkers(data, 'sources:', ']', False)[1]
			data = self.RE_HTTP_URL.findall(data)
			for videoUrl in data:
				if videoUrl.split('?')[0].endswith('m3u8'):
					printDBG('Host videoUrl: %s' % videoUrl)
				elif videoUrl.split('?')[0].endswith('mp4'):
					printDBG('Host videoUrl: %s' % videoUrl)
					videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': referer, 'User-Agent': USER_AGENT})
					return videoUrl
			return ''

		if parser == 'https://lovehomeporn.com/':
			COOKIEFILE = join(GetCookieDir(), 'lovehomeporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			self.defaultParams['header']['Referer'] = parser
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			id = self.cm.ph.getSearchGroups(data, r'''video_id\s*=\s*['"]([^"^']+?)['"]''')[0]
			videoUrl = "https://lovehomeporn.com/media/nuevo/config.php?key=%s" % id
			sts, data = self.get_Page(videoUrl)
			if not sts:
				return ''
			videoUrl = ph.search(data, '''<file>([^>]+?)<''')[0].replace('&amp;', '&')
			videoUrl = checkhttp(videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.pornrabbit.com':
			self.cm.HEADER = {'User-Agent': self.cm.getDefaultHeader()['User-Agent'], 'X-Requested-With': 'XMLHttpRequest'}
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			COOKIEFILE = join(GetCookieDir(), 'pornrabbit.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornrabbit.cookie', 'pornrabbit.com', self.defaultParams)
			self.cm.HEADER = None
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_alt_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				# player block is an xhamster embed now, the xhamster branch resolves the video page
				xhId = self.cm.ph.getSearchGroups(data, r'''xhamster\.com/embed/([0-9A-Za-z]+)''')[0]
				if xhId:
					videoUrl = self.getResolvedURL('https://xhamster.com/videos/' + xhId)
					if not videoUrl:
						# xhamster answers 410 for the videos deleted there, pornrabbit still lists them
						SetIPTVPlayerLastHostError(_('This video was embedded from xHamster and has been deleted there.'))
					return videoUrl
			if not videoUrl and 'kt_player' not in data and 'xhamster' not in data:
				# the newer cam recordings have no player on the site at all - their embed page is a cam advert
				SetIPTVPlayerLastHostError(_('The site has no player for this video (it only shows a cam advert).'))
				return ''
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''embedUrl":.['"]([^"^']+?)['"]''')[0]
				sts, data = self.get_Page(videoUrl)
				if not sts:
					return ''
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''')[0]
				sts, data = self.get_Page(videoUrl)
				if not sts:
					return ''
				videoUrl = self.cm.ph.getSearchGroups(data, r'''HD[0-9A-Za-z,:{}"\]]+url":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
				printDBG('Xhamster Multi: ' + videoUrl)
				if not videoUrl:
					videoUrl = self.cm.ph.getSearchGroups(data, '''true[a-z":,]+videoUrl":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
					printDBG('Fetched link: ' + videoUrl)
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			if 'm3u8' in videoUrl:
				videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, "Origin": "https://www.pornrabbit.com"})
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			printDBG('Final URL: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.eroprofile.com':
			COOKIEFILE = join(GetCookieDir(), 'eroprofile.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			videoUrl = checkhttp(videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'http://www.absoluporn.com':
			COOKIEFILE = join(GetCookieDir(), 'absoluporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			videoUrl = checkhttp(videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://mangovideo':
			COOKIEFILE = join(GetCookieDir(), 'mangovideo.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER['User-Agent']})

		if parser == 'https://anybunny.org':
			COOKIEFILE = join(GetCookieDir(), 'anybunny.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'anybunny.cookie', 'anybunny.org', self.defaultParams)
			if not sts:
				return ''
			# the video page embeds a player page whose Playerjs "file" lists
			# "[quality]url:cast:url" entries; the stream1 URLs redirect to the CDN
			embedUrl = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=["']([^"']+?)["']''', 1, True)[0]
			if not embedUrl:
				# /too/ links redirect to a /to/<id>.html page that carries the MP4 directly (inside a JS string)
				videoUrl = self.cm.ph.getSearchGroups(data, r'''<source src=\\?['"](https?://[^'"\\]+\.mp4[^'"\\]*)''', 1, True)[0]
				if videoUrl:
					return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})
				printDBG('ANYBUNNY: player iframe not found')
				return ''
			embedUrl = urljoin(url, embedUrl.replace('&amp;', '&'))
			sts, data = self.getPage(embedUrl, 'anybunny.cookie', 'anybunny.org', self.defaultParams)
			if not sts:
				return ''
			fileStr = self.cm.ph.getSearchGroups(data, r'''file\s*:\s*["']([^"']+)["']''', 1, True)[0]
			candidates = []
			for part in re.split(r',(?=\[)', fileStr):
				m = re.match(r'\[(\d+)[^\]]*\](.+)', part)
				if not m:
					continue
				for streamUrl in m.group(2).split(':cast:'):
					streamUrl = re.sub(r'\s+', '', streamUrl)
					if streamUrl.startswith('http'):
						candidates.append((int(m.group(1)), streamUrl))
			if not candidates:
				printDBG('ANYBUNNY: no stream in the player')
				return ''
			# single qualities of a video answer 403 (a different one per video): take the best one that answers
			candidates.sort(key=lambda c: c[0], reverse=True)
			header = {'User-Agent': USER_AGENT, 'Referer': embedUrl, 'Range': 'bytes=0-0'}
			for quality, streamUrl in candidates:
				sts, response = self.cm.getPage(streamUrl, {'header': header, 'return_data': False})
				if sts and response is not None:
					response.close()
					printDBG('ANYBUNNY %sp: %s' % (quality, streamUrl))
					return urlparser.decorateUrl(streamUrl, {'Referer': embedUrl, 'User-Agent': USER_AGENT})
				printDBG('ANYBUNNY %sp refused: %s' % (quality, streamUrl))
			SetIPTVPlayerLastHostError(_('The site refuses all qualities of this video at the moment (HTTP 403). Try again later.'))
			return ''

		if parser == 'https://hqporner.com':
			if '/hdporn/' in url:
				# video page: list item with "use the best quality" on
				url = self._bestFromQualityList(url, 'hqporner-serwer')
				if not url:
					return ''
			videoUrl = urlparser.decorateUrl(url, {'Referer': url})
			return videoUrl if videoUrl else ''

		if parser == 'https://www.eporner.com':
			if '/dload/' not in url:
				# video page: list item with "use the best quality" on; downloads from 1080p on need a login
				url = self._bestFromQualityList(url, 'eporner-serwer', 720)
				if not url:
					return ''
			printDBG('Selected Resolution: ' + url)
			if url.startswith('http'):
				videoUrl = url
			else:
				videoUrl = "https://www.eporner.com" + url
			printDBG('Last link: ' + videoUrl)
			videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': videoUrl})
			return videoUrl if videoUrl else ''

		if parser == 'https://hello.porn':
			if '.m3u8' not in url:
				# video page: list item with "use the best quality" on
				url = self._bestFromQualityList(url, 'HELLOPORN-serwer')
				if not url:
					return ''
			printDBG('Selected Resolution: ' + url)
			# url is a variant line picked in hostxxx HELLOPORN-serwer
			videoUrl = urlparser.decorateUrl(url, {'Referer': url, 'iptv_proto': 'm3u8'})
			return videoUrl if videoUrl else ''

		if parser == 'https://dansmovies.com':
			COOKIEFILE = join(GetCookieDir(), 'dansmovies.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'source src="', '" type=', False)[1]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttps(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://www.pornrewind.com':
			COOKIEFILE = join(GetCookieDir(), 'pornrewind.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].type="video''')[0]
			return videoUrl

		if parser == 'https://shooshtime.com':
			self.MAIN_URL = 'https://shooshtime.com'
			COOKIEFILE = join(GetCookieDir(), 'shooshtime.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'shooshtime.cookie', 'shooshtime.com', self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			if videoUrl.startswith('/'):
				videoUrl = self.MAIN_URL + videoUrl
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT}) if videoUrl else ''

		if parser == 'https://prostream.to':
			COOKIEFILE = join(GetCookieDir(), 'prostream.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'prostream.cookie', 'prostream.to', self.defaultParams)
			if not sts:
				return ''
			if "eval(function(p,a,c,k,e,d)" in data:
				printDBG('Host resolveUrl packed')
				packed = self.RE_EVAL_PACKED.findall(data)
				if packed:
					packed = packed[-1]
				else:
					return ''
				try:
					videoPage = unpackJSPlayerParams(packed, TEAMCASTPL_decryptPlayerParams, 0, True, True)
				except Exception:
					pass
				printDBG('Host videoPage: ' + str(videoPage))
				videoUrl = ph.search(videoPage, '''file:['"]([^'^"]+?)['"]''')[0]
				if not videoUrl:
					videoUrl = ph.search(videoPage, r'''sources:\[['"]([^'^"]+?)['"]''')[0]
				videoUrl = checkhttp(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://www.cumlouder.com':
			COOKIEFILE = join(GetCookieDir(), 'cumlouder.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'cumlouder.cookie', 'cumlouder.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			videoUrl = checkhttp(videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://pornone.com':
			COOKIEFILE = join(GetCookieDir(), 'pornone.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornone.cookie', 'pornone.com', self.defaultParams)
			videoUrl = re.findall('source.src=["]([^@]+?)["]', data, re.S)[0]
			printDBG('Link 1: ' + videoUrl)
			if not videoUrl:
				videoUrl = re.search('contentUrl":.["]([^"]+)["],', data).group(1)
			printDBG('Link: ' + videoUrl)
			return videoUrl

		if parser == 'https://sexu.com':
			COOKIEFILE = join(GetCookieDir(), 'sexu.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''downloadUrl":['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': 'https://sexu.com/'})
			videoUrl = re.findall(r'"file":"(.*?\.mp4)"', data, re.S)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl[-1], {'Referer': 'https://sexu.com/'})
			videoUrl = self.cm.ph.getSearchGroups(data, '''"src":['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': 'https://sexu.com/'})
			videoUrl = self.cm.ph.getSearchGroups(data, '''contentUrl":['"]([^"^']+?)['"]''')[0]
			if videoUrl:
				return urlparser.decorateUrl(checkhttp(videoUrl), {'Referer': 'https://sexu.com/'})

		if parser == 'https://www.hdporn.net':
			COOKIEFILE = join(GetCookieDir(), 'hdporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return
			match = re.findall('source src="(.*?)"', data, re.S)
			if match:
				return match[0]
			else:
				return ''

		if parser == 'https://pornicom.com':
			COOKIEFILE = join(GetCookieDir(), 'pornicom.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			url = url.replace('ä', '%C3%A4').replace('ß', '%C3%9').replace('ü', '%C3%BC')
			printDBG('PORNICOM URL: ' + str(url))
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			data2 = self.cm.ph.getDataBeetwenMarkers(data, 'var flashvars', '}', False)[1]
			if data2:
				printDBG('Host data2:%s' % data2)
				return self.cm.ph.getSearchGroups(data2, r'''video_url:\s*?['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			videoPage = self.cm.ph.getSearchGroups(data, '''file: ['"]([^"^']+?)['"]''')[0]
			if videoPage:
				printDBG('Host data file:%s' % videoPage)
				return videoPage
			return ''

		if parser == 'https://www.porn00.org':
			COOKIEFILE = join(GetCookieDir(), 'porn00.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'porn00.cookie', 'porn00.org', self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_alt_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if 'login' in videoUrl or '' == videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://porngo.com':
			COOKIEFILE = join(GetCookieDir(), 'porngo.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'porngo.cookie', 'porngo.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.FullUrl(self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"]([^"^']+?)['"]''')[0])
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if videoUrl else ''

		if parser == 'https://glavmatures.com':
			printDBG('GLAVMATURES PARSER START')

			video_url = url
			if video_url.startswith('/'):
				video_url = 'https://www.glavmatures.com' + video_url

			# reuse the session cookie the host created while browsing
			COOKIEFILE = join(GetCookieDir(), 'glavmatures.cookie')
			header = self.cm.getDefaultHeader(browser='chrome')
			header['Referer'] = video_url
			header['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
			header['Accept-Language'] = 'en-US,en;q=0.7'

			params = {
				'header': header,
				'use_cookie': True,
				'load_cookie': True,
				'save_cookie': True,
				'cookiefile': COOKIEFILE,
				'return_data': True,
				'timeout': 30
			}

			printDBG('GLAVMATURES VIDEO PAGE GET: ' + video_url)
			sts, data = self.cm.getPage(video_url, params)
			printDBG('GLAVMATURES VIDEO PAGE RESULT sts=%s len=%s' % (str(sts), str(len(data) if data else 0)))

			if not sts or not data:
				printDBG('GLAVMATURES PARSER: page load failed')
				return ''

			if data.strip() == 'Something went wrong :( Try to refresh the page.':
				printDBG('GLAVMATURES PARSER: site returned error page')
				return ''

			def norm(value):
				value = value.replace('\\/', '/')
				value = value.replace('&amp;', '&')
				value = value.replace('&quot;', '"')
				if value.startswith('//'):
					value = 'https:' + value
				return value

			urls = []

			# player variables first, then direct m3u8/mp4 URLs in the page
			for rx in [
				r'setVideoHLS\s*\(\s*[\'"]([^\'"]+?\.m3u8[^\'"]*)[\'"]',
				r'setVideoUrlHigh\s*\(\s*[\'"]([^\'"]+?\.mp4[^\'"]*)[\'"]',
				r'setVideoUrlLow\s*\(\s*[\'"]([^\'"]+?\.mp4[^\'"]*)[\'"]',
				r'[\'"](https?://[^\'"]+?\.m3u8(?:\?[^\'"]*)?)[\'"]',
				r'[\'"](https?://[^\'"]+?\.mp4(?:\?[^\'"]*)?)[\'"]'
			]:
				for um in re.finditer(rx, data, re.I):
					u = norm(um.group(1))
					if u and u not in urls:
						urls.append(u)

			printDBG('GLAVMATURES VIDEO URLS: ' + str(urls[:5]))

			for u in urls:
				stream_header = {
					'Referer': video_url,
					'User-Agent': header.get('User-Agent', USER_AGENT)
				}

				if '.m3u8' in u.lower():
					decorated = urlparser.decorateUrl(u, stream_header)
					try:
						ret = getDirectM3U8Playlist(decorated, checkContent=True, sortWithMaxBitrate=999999999)
						if ret:
							printDBG('GLAVMATURES HLS RESOLVED LINKS: ' + str(len(ret)))
							# getResolvedURL returns one URL, not a list of links
							resolved_url = ret[0].get('url', '')
							if resolved_url:
								resolved_url = urlparser.decorateUrl(resolved_url, stream_header)
								printDBG('GLAVMATURES FINAL HLS URL: ' + resolved_url)
								return resolved_url
					except Exception as e:
						printDBG('GLAVMATURES HLS resolve exception: ' + str(e))

					return decorated

				if '.mp4' in u.lower():
					return urlparser.decorateUrl(u, stream_header)

			printDBG('GLAVMATURES: no playable URL found')
			return ''

		if parser == 'https://www.pornheed.com':
			COOKIEFILE = join(GetCookieDir(), 'pornheed.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornheed.cookie', 'pornheed.com', self.defaultParams)
			if not sts:
				return ''
			embedUrl = re.search('video:url..content=["]([^@]+?)["]', data).group(1)
			sts, data = self.get_Page(embedUrl)
			videoUrl = re.findall('source.src=["]([^"]+?)["]', data, re.S)
			return videoUrl[-1] if videoUrl else ''

		if parser == 'https://ziporn.com/':
			COOKIEFILE = join(GetCookieDir(), 'ziporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'ziporn.cookie', 'ziporn.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''contentURL".content=['"]([^"^']+?)['"] /><meta''', 1, True)[0]
			if not videoUrl:
				phUrl = self.cm.ph.getSearchGroups(data, '''<iframe.src=['"]([^"^']+?)['"].frame''', 1, True)[0]
				sts, data = self.get_Page(phUrl)
				if not sts:
					return ''
				embedUrl = self.cm.ph.getSearchGroups(data, '''<iframe.src=['"]([^"^']+?)['"].frame''', 1, True)[0]
				printDBG('Embedded page: ' + embedUrl)
				viewKey = self.cm.ph.getSearchGroups(embedUrl, r'pornhub\.com/embed/([0-9a-z]+)', 1, True)[0]
				if viewKey:
					# a Pornhub embed: its HLS link needs Pornhub's headers (played without them: "Invalid data") -
					# the Pornhub resolver sets them and picks the quality
					videoUrl = self.getResolvedURL('https://www.pornhub.com/view_video.php?viewkey=' + viewKey)
					if not videoUrl:
						SetIPTVPlayerLastHostError(_('This video was embedded from Pornhub and is no longer available there.'))
					return videoUrl
				sts, data = self.get_Page(embedUrl)
				if not sts:
					return ''
				printDBG('Embedded: ' + embedUrl)
				videoUrl = self.cm.ph.getSearchGroups(data, '''true.+?hls.{13}['"]([^"^']+?)['"]''', 1, True)[0].replace(r"\/", "/")
			printDBG('Video Link: ' + videoUrl)
			return videoUrl

		if parser == 'https://hdsite.net':
			COOKIEFILE = join(GetCookieDir(), 'hdsite.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER['User-Agent']})

		if parser == 'https://www.porn300.com':
			sts, data = self.get_Page(url)
			data = self.cm.ph.getDataBeetwenMarkers(data, '</svg> Resume video', 'html5-video-support/"', False)[1]
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'src="', '"', False)[1]
			videoUrl = videoUrl.replace('amp;', '')
			printDBG('Final Url: ' + videoUrl)
			return videoUrl

		if parser == 'https://ruleporn.com':
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Final Url: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.megatube.xxx':
			COOKIEFILE = join(GetCookieDir(), 'megatube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, "video_url: '", "/',", False)[1]
			printDBG('VideoLink: ' + videoUrl)
			return videoUrl

		if parser == 'https://anyporn.com':
			COOKIEFILE = join(GetCookieDir(), 'anyporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'anyporn.cookie', 'anyporn.com', self.defaultParams)
			if not sts:
				return ''
			data = self.cm.ph.getDataBeetwenMarkers(data, 'const sources', 'src in sources', False)[1]
			videoUrl = self.cm.ph.getSearchGroups(data, '''['"]([^"^']+?)['"]\n''', 1, True)[0]
			printDBG('Videolink: ' + videoUrl)
			return strwithmeta(videoUrl, {'Referer': url})

		if parser == 'https://www.bravoporn.com':
			COOKIEFILE = join(GetCookieDir(), 'bravoporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'bravoporn.cookie', 'bravoporn.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"].{5,25}HQ''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"].{5,25}LQ''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"].{10,20}mp4''', 1, True)[0]
			printDBG('BRAVOPORN / BRAVOTEENS Videolink: ' + videoUrl)
			return strwithmeta(videoUrl, {'Referer': url})

		if parser == 'https://anysex.com/':
			COOKIEFILE = join(GetCookieDir(), 'anysex.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'anysex.cookie', 'anysex.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall('source.{2,5}src="(.*?)"', data, re.S)
			return videoUrl[0] if videoUrl else ''

		if parser == 'https://www.sleazyneasy.com':
			COOKIEFILE = join(GetCookieDir(), 'sleazyneasy.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'sleazyneasy.cookie', 'sleazyneasy.com', self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			videoUrl = checkhttp(videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': self.cm.meta['url']})

		if parser == 'https://www.freeones.com':
			COOKIEFILE = join(GetCookieDir(), 'freeones.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'freeones.cookie', 'freeones.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = ''
			patterns = (r'''contentUrl\":\"([^\"]+)''', r'''contentUrl\"\s*:\s*[\"]([^\"]+)''', r'''(?:file|src|videoUrl|video_url)\s*[:=]\s*[\"]([^\"]+?(?:\.m3u8|\.mp4)(?:\?[^\"]*)?)[\"]''', r'''<source[^>]+src=['\"]([^'\"]+?\.(?:m3u8|mp4)(?:\?[^'\"]*)?)['\"]''')
			for pattern in patterns:
				videoUrl = self.cm.ph.getSearchGroups(data, pattern, 1, True)[0]
				if videoUrl:
					break
			videoUrl = videoUrl.replace(r'\/', '/')
			if videoUrl.startswith('//'):
				videoUrl = 'https:' + videoUrl
			if videoUrl and not videoUrl.startswith(('http://', 'https://')):
				videoUrl = urljoin(url, videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if videoUrl else ''

		if parser == 'https://www.youx.xxx':
			COOKIEFILE = join(GetCookieDir(), 'youx.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url: ['"]([^"^']+?)['"],''')[0]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			videoUrl = checkhttps(videoUrl)
			printDBG('Ready link: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.yourupload.com':
			COOKIEFILE = join(GetCookieDir(), 'yourupload.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'''file\s*:\s*['"]([^"^']+?)['"]''')[0]
			videoUrl = checkhttp(videoUrl)
			videoUrl = urljoin(url, videoUrl)
			self.defaultParams['max_data_size'] = 0
			sts, data = self.get_Page(videoUrl, self.defaultParams)
			return '' if not sts else strwithmeta(self.cm.meta['url'], {'User-Agent': self.HTTP_HEADER['User-Agent'], 'Referer': url})  #

		if parser == 'https://xcum.com':
			COOKIEFILE = join(GetCookieDir(), 'xcum.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.cm.getPage(url)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''src=["']([^"^']+?)["]+[ a-z="/]+1080''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=["']([^"^']+?)["]+[ a-z="/]+720''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=["']([^"^']+?)["]+[ a-z="/]+480''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=["']([^"^']+?)["]+[ a-z="/]+360''')[0]
			printDBG('Video address' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER['User-Agent']})

		if parser == 'https://familyporn.tv':
			COOKIEFILE = join(GetCookieDir(), 'familyporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return []
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_alt_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if videoUrl == '':
				videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if url.startswith('https://www.sexvid.xxx'):
				videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
				if videoUrl == '':
					videoUrl = self.cm.ph.getSearchGroups(data, r'''video_alt_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER['User-Agent']})

		# This SPANKBANG block used to sit AFTER the generic fallback fetch below
		# (query_data = {...}). That fallback is unconditional - it runs for any
		# parser that reaches this point in the function - and its raw request
		# (no Referer/Cookie) sometimes threw an exception for spankbang.com,
		# which returned immediately and never reached this block at all. That
		# is exactly why some videos silently had "no valid link": it depended on
		# whether the earlier, irrelevant generic pre-fetch happened to succeed
		# or throw, not on anything about the video itself. Moved here so this
		# block always runs for spankbang.com regardless of that fallback.
		if parser == 'https://beeg.com':
			vid = url.rstrip('/').rsplit('/', 1)[-1]
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Accept'] = 'application/json'
			self.HTTP_HEADER['Referer'] = 'https://beeg.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage('https://store.externulls.com/facts/file/' + vid, self.defaultParams)
			if not sts:
				return ''
			try:
				jdata = json.loads(data)
			except Exception:
				printExc()
				return ''
			hls = {}
			fileNode = jdata.get('file') if isinstance(jdata, dict) else None
			if isinstance(fileNode, dict) and isinstance(fileNode.get('hls_resources'), dict):
				hls = fileNode['hls_resources']
			if not hls:
				facts = jdata.get('fc_facts') if isinstance(jdata, dict) else None
				if facts and isinstance(facts, list) and isinstance(facts[0], dict):
					hls = facts[0].get('hls_resources') or {}
			resource = hls.get('fl_cdn_multi') or hls.get('fl_cdn_720') or hls.get('fl_cdn_1080') or hls.get('fl_cdn_480') or hls.get('fl_cdn_360')
			videoUrl = ''
			if resource:
				resource = str(resource).strip()
				if resource.startswith('//'):
					videoUrl = 'https:' + resource
				elif resource.startswith('http://') or resource.startswith('https://'):
					videoUrl = resource
				elif resource.startswith('/'):
					videoUrl = 'https://video.externulls.com' + resource
				else:
					videoUrl = 'https://video.externulls.com/' + resource
				if not videoUrl.split('?')[0].endswith('.m3u8'):
					videoUrl += '.m3u8'
			if not videoUrl:
				return ''
			if 'm3u8' in videoUrl:
				try:
					tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
					for item in tmp:
						videoUrl = item['url']
						break
				except Exception:
					printExc()
			return strwithmeta(videoUrl, {'Referer': 'https://beeg.com/'})

		if parser == 'https://www.tokyomotion.net':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://www.tokyomotion.net/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			# the title part of /video/<id>/<title> is often Japanese; the page is the same without it
			url = self.cm.ph.getSearchGroups(url, r'''(https?://[^/]+/video/[0-9]+/)''', 1, True)[0] or url
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			sources = re.findall(r'<source\b[^>]*>', data, re.I)
			best = ''
			bestRank = -1
			for tag in sources:
				srcm = re.search(r'''src=["']([^"']+)["']''', tag)
				if not srcm or '/vsrc/' not in srcm.group(1):
					continue
				titlem = re.search(r'''title=["']([^"']*)["']''', tag)
				title = (titlem.group(1) if titlem else '').strip().upper()
				rank = 2 if title == 'HD' else (1 if title == 'SD' else 0)
				if rank > bestRank:
					bestRank = rank
					best = checkhttps(srcm.group(1))
			if not best:
				return ''
			# /vsrc/hd/<id> has no file extension
			return strwithmeta(best, {'Referer': url, 'iptv_format': 'mp4'})

		if parser == 'https://hentai-moon.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://hentai-moon.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''', 1, True)[0].strip()
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''', 1, True)[0]
			if videoUrl and 'function/0/' in videoUrl and license_code:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			if not videoUrl:
				return ''
			return strwithmeta(videoUrl, {'Referer': url})

		if parser in TXXX_NETWORK_SITES:
			vid = self.cm.ph.getSearchGroups(url, r'/video/([0-9]+)/', 1, True)[0]
			if not vid:
				return ''
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(parser + '/api/videofile.php?video_id=%s&lifetime=8640000' % vid, self.defaultParams)
			if not sts:
				return ''
			try:
				sources = [s for s in json.loads(data) if s.get('video_url') and s.get('format') != '_tr.mp4']
			except Exception:
				printExc()
				return ''
			if not sources:
				return ''
			# '_hd.mp4' > '.mp4' > '_sd.mp4'
			rank = {'_hd.mp4': 2, '.mp4': 1}
			sources.sort(key=lambda s: rank.get(s.get('format'), 0), reverse=True)
			videoUrl = decodeTxxxUrl(sources[0]['video_url'])
			if not videoUrl:
				return ''
			return urlparser.decorateUrl(urljoin(parser + '/', videoUrl), {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser == 'https://xhamster.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://xhamster.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'''<link rel="preload" href="([^"]+\.m3u8)"''', 1, True)[0]
			if videoUrl:
				# the master playlist is sometimes AV1 only, the same path serves H.264 too
				videoUrl = re.sub(r'\.av1\.mp4\.m3u8', '.h264.mp4.m3u8', videoUrl)
				videoUrl = self._bestM3U8Variant(videoUrl) or videoUrl  # the masters list up to 2160p
			else:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''<noscript>.*?<video[^>]+src="([^"]+\.mp4[^"]*)"''', 1, True)[0]
			if not videoUrl:
				return ''
			return strwithmeta(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser == 'https://www.thumbzilla.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://www.thumbzilla.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			mediaUrl = self.cm.ph.getSearchGroups(data, r'"videoUrl":"([^"]+?media\\?/mp4\\?/[^"]+)"', 1, True)[0].replace('\\/', '/')
			if not mediaUrl:
				return ''
			self.HTTP_HEADER['Referer'] = url
			self.HTTP_HEADER['X-Requested-With'] = 'XMLHttpRequest'
			sts, data = self.cm.getPage(mediaUrl, self.defaultParams)
			if not sts:
				return ''
			try:
				sources = [s for s in json.loads(data) if s.get('videoUrl')]
			except Exception:
				printExc()
				return ''
			if not sources:
				return ''
			sources.sort(key=lambda s: int(re.sub(r'[^0-9]', '', str(s.get('quality', ''))) or 0), reverse=True)
			return urlparser.decorateUrl(sources[0]['videoUrl'], {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser == 'https://noodlemagazine.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://noodlemagazine.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			playerUrl = decodeHtml(self.cm.ph.getSearchGroups(data, r'''<meta\s+property=["']og:video["']\s+content=["']([^"']+)["']''', 1, True)[0])
			if not playerUrl:
				return ''
			self.HTTP_HEADER['Referer'] = url
			sts, data = self.cm.getPage(playerUrl, self.defaultParams)
			if not sts:
				return ''
			playlist = self.cm.ph.getSearchGroups(data, r'(?s)window\.playlist\s*=\s*(\{.*?\});', 1, True)[0]
			try:
				sources = [s for s in json.loads(playlist).get('sources', []) if '.mp4' in s.get('file', '')]
			except Exception:
				printExc()
				return ''
			if not sources:
				return ''
			sources.sort(key=lambda s: int(re.sub(r'[^0-9]', '', str(s.get('label', ''))) or 0), reverse=True)
			return urlparser.decorateUrl(sources[0]['file'], {'Referer': playerUrl, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser == 'https://missav123.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://missav123.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			# the packed player JS only builds https://surrit.com/<uuid>/playlist.m3u8,
			# the uuid is also in the plain seek-thumbnail list
			uuid = self.cm.ph.getSearchGroups(data, r'surrit\.com\\*/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', 1, True)[0]
			if not uuid:
				return ''
			videoUrl = strwithmeta('https://surrit.com/%s/playlist.m3u8' % uuid, {'Referer': url})
			try:
				for item in getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999):
					videoUrl = item['url']
					break
			except Exception:
				printExc()
			# the segments are only served with a referer; surrit.com is Cloudflare, which answers 403 to
			# exteplayer3/ffmpeg sending a browser User-Agent - a player User-Agent passes, as for CAMSODA
			return strwithmeta(videoUrl, {'Referer': url, 'User-Agent': 'VLC/3.0.20 LibVLC/3.0.20', 'iptv_proto': 'm3u8'})

		if parser == 'https://sxyprn.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://sxyprn.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			vnfo = self.cm.ph.getSearchGroups(data, r"data-vnfo='([^']+)'", 1, True)[0]
			try:
				path = list(json.loads(vnfo).values())[0]
			except Exception:
				printExc()
				return ''
			# the player shifts the obfuscated /cdn/ path by the digit sums of two of its parts
			parts = path.split('/')
			if len(parts) < 8 or not parts[5].isdigit():
				return ''

			def digitSum(text):
				return sum(int(c) for c in text if c.isdigit())
			ss, es = digitSum(parts[6]), digitSum(parts[7])
			token = base64.b64encode(('%d-sxyprn.com-%d' % (ss, es)).encode('utf-8'))
			if not isinstance(token, str):
				token = token.decode('utf-8')
			parts[1] += '8/' + token
			parts[5] = str(int(parts[5]) - ss - es)
			videoUrl = urljoin('https://sxyprn.com/', '/'.join(parts))
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', ''), 'iptv_format': 'mp4'})

		if parser == 'https://fullporner.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://fullporner.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True, 'timeout': 60}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			# player iframe //xiaoshenke.net/video/<id>/<quality bit mask 1=360 2=480 4=720 8=1080>
			m = re.search(r'''src=["']//xiaoshenke\.net/video/([a-z0-9]+)/([0-9]+)["']''', data, re.I)
			if not m:
				return ''
			mask = int(m.group(2))
			qualities = [q for bit, q in ((1, 360), (2, 480), (4, 720), (8, 1080)) if mask & bit]
			if not qualities:
				return ''
			videoUrl = 'https://xiaoshenke.net/vid/%s/%d' % (m.group(1)[::-1], max(qualities))
			return urlparser.decorateUrl(videoUrl, {'Referer': 'https://xiaoshenke.net/', 'User-Agent': self.HTTP_HEADER.get('User-Agent', ''), 'iptv_format': 'mp4'})

		if parser == 'https://www.erome.com':
			# the album page already lists the direct MP4 files, they only need an erome referer
			return urlparser.decorateUrl(url, {'Referer': 'https://www.erome.com/', 'User-Agent': self.cm.getDefaultHeader(browser='chrome').get('User-Agent', '')})

		if parser == 'https://hentaiocean.com':
			slug = url.rstrip('/').split('/')[-1]
			embedUrl = 'https://hentaiocean.com/embed/' + slug
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(embedUrl, self.defaultParams)
			if not sts:
				return ''
			jsondata = self.cm.ph.getSearchGroups(data, r'(?s)var\s+jsondata\s*=\s*(\{.*?\})\s*</script>', 1, True)[0]
			try:
				mirrors = json.loads(jsondata).get('mirrors', [])
			except Exception:
				printExc()
				return ''
			for mirror in mirrors:
				# https://w2.hentaiocean.com/play?vid=<file name> is played from /video/<file name>
				mirrorUrl = mirror.get('mirrorurl', '').replace('\\/', '/').replace('&amp;', '&')
				m = re.match(r'(https?://[^/]*hentaiocean\.com)/play\?vid=(.+)$', mirrorUrl)
				if m:
					fileName = unquote(m.group(2))
					if not isinstance(fileName, str):
						fileName = fileName.encode('utf-8')  # Python 2: quote() needs bytes
					videoUrl = m.group(1) + '/video/' + quote(fileName)
					# that file is AV1, which most receivers cannot decode (sound only); the site's "Universal Mirror"
					# is an H.264 copy at w1/w2 .../video/h264/<file name> - use it when it exists, like the site does
					header = {'User-Agent': self.HTTP_HEADER.get('User-Agent', ''), 'Referer': embedUrl, 'Range': 'bytes=0-0'}
					for host in ('https://w1.hentaiocean.com', 'https://w2.hentaiocean.com'):
						h264Url = host + '/video/h264/' + quote(fileName)
						sts, response = self.cm.getPage(h264Url, {'header': header, 'return_data': False})
						if sts and response is not None:
							response.close()
							videoUrl = h264Url
							break
					return urlparser.decorateUrl(videoUrl, {'Referer': embedUrl, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})
			return ''

		if parser == 'https://hentaidude.xxx':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://hentaidude.xxx/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			playerUrl = decodeHtml(self.cm.ph.getSearchGroups(data, r'''(https://hentaidude\.xxx/wp-content/plugins/player-logic/player\.php\?data=[^"']+)''', 1, True)[0])
			if not playerUrl:
				return ''
			self.HTTP_HEADER['Referer'] = url
			sts, data = self.cm.getPage(playerUrl, self.defaultParams)
			if not sts:
				return ''
			# x-secure-token = json, three times rot13 + base64
			token = self.cm.ph.getSearchGroups(data, r'<meta name="x-secure-token" content="([^"]+)"', 1, True)[0].replace('sha512-', '')
			try:
				for _i in range(3):
					token = codecs.decode(token, 'rot_13')
					token = base64.b64decode(token + '=' * (-len(token) % 4))
					if not isinstance(token, str):
						token = token.decode('utf-8')
				token = json.loads(token)
			except Exception:
				printExc()
				return ''
			apiUrl = urljoin('https:' + token['uri'] if token.get('uri', '').startswith('//') else token.get('uri', ''), 'api.php')
			sts, data = self.cm.getPage(apiUrl, self.defaultParams, {'action': 'zarat_get_data_player_ajax', 'a': token.get('en', ''), 'b': token.get('iv', '')})
			if not sts:
				return ''
			try:
				sources = json.loads(data).get('data', {}).get('sources', [])
			except Exception:
				printExc()
				return ''
			if not sources or not sources[0].get('src'):
				return ''
			# master playlist on purpose: the audio is a separate rendition group
			return urlparser.decorateUrl(sources[0]['src'], {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser == 'https://hstream.moe':
			COOKIEFILE = join(GetCookieDir(), 'hstream.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://hstream.moe/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			episodeId = self.cm.ph.getSearchGroups(data, r'''id=["']e_id["'][^>]+value=["']([^"']+)''', 1, True)[0]
			token = self.cm.ph.getSearchGroups(data, r'''name=["']_token["']\s+value=["']([^"']+)''', 1, True)[0]
			if not episodeId or not token:
				return ''
			# the player API needs the session cookie of the page load and its CSRF token
			header = dict(self.HTTP_HEADER)
			header.update({'Referer': url, 'Origin': 'https://hstream.moe', 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-TOKEN': token})
			params = {'header': header, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'raw_post_data': True, 'return_data': True}
			sts, data = self.cm.getPage('https://hstream.moe/player/api', params, json.dumps({'episode_id': episodeId}))
			if not sts:
				return ''
			try:
				data = json.loads(data)
				videoUrl = '%s/%s/x264.720p.mp4' % (str(data['stream_domains'][0]).rstrip('/'), str(data['stream_url']).strip('/'))
			except Exception:
				printExc()
				return ''
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser in KVS_SITES:
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = parser + '/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			# a plain <source src="/contents/videos/...mp4"> (amateurporn.me since 10.2026) is relative to the page
			candidates = [(c[0], urljoin(url, c[1])) for c in self._mediaCandidates(data)]
			candidates = [c for c in candidates if c[1].startswith('http')]
			if not candidates and 'This is premium video' not in data and '/embed/' not in url:
				# a duplicate entry only embeds another (free) video of the same site
				embedId = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=["']%s/embed/([0-9]+)''' % re.escape(parser), 1, True)[0]
				if embedId and '/videos/%s/' % embedId not in url:
					return self.getResolvedURL('%s/embed/%s/' % (parser, embedId))
			if not candidates:
				if 'embed.clips4sale.com' in data:
					# some list entries are only an embedded clips4sale trailer for a paid clip
					SetIPTVPlayerLastHostError(_('This is only an advert for a paid clip (clips4sale), there is no free video.'))
				elif 'This is premium video' in data:
					# KVS premium videos: paying members only (the list entry looks like any other)
					SetIPTVPlayerLastHostError(_("This video is Premium-only content."))
				elif 'data-fancybox="ajax">log in</a>' in data:
					# KVS private videos: shown to logged-in members only, even with a free account
					SetIPTVPlayerLastHostError(_("This video is a private video."))
				return ''
			return urlparser.decorateUrl(self._pickByHeight(candidates), {'Referer': url, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser == 'https://alpenrammler.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = parser + '/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			# the page only names the 360p file (contentUrl); its embed wraps a lapippa.com player listing all qualities
			videoUrl = self.cm.ph.getSearchGroups(data, r'''contentUrl"\s*:\s*"([^"]+)"''', 1, True)[0]
			embedUrl = self.cm.ph.getSearchGroups(data, r'''embedUrl"\s*:\s*"([^"]+)"''', 1, True)[0]
			if embedUrl:
				self.HTTP_HEADER['Referer'] = url
				sts, embed = self.cm.getPage(embedUrl, self.defaultParams)
				playerUrl = self.cm.ph.getSearchGroups(embed, r'''<iframe[^>]+src=["']([^"']+)["']''', 1, True)[0] if sts else ''
				if playerUrl:
					self.HTTP_HEADER['Referer'] = embedUrl
					sts, player = self.cm.getPage(playerUrl, self.defaultParams)
					sources = re.findall(r'''<source[^>]+src=["']([^"']+)["']''', player) if sts else []
					sources.sort(key=lambda src: int(self.cm.ph.getSearchGroups(src, r'_([0-9]{3,4})p\.', 1, True)[0] or 0), reverse=True)
					if sources:
						videoUrl = sources[0]
			if not videoUrl:
				return ''
			return urlparser.decorateUrl(videoUrl, {'Referer': self.HTTP_HEADER['Referer'], 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})

		if parser == 'https://321tube.com':
			# EXPERIMENTAL: turbovidhls player; its HLS segments are TS behind a PNG header on Google's image CDN
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://321tube.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			embedUrl = self.cm.ph.getSearchGroups(data, r'''<iframe\b[^>]+src=["']([^"']+)["']''', 1, True)[0] or self.cm.ph.getSearchGroups(data, r'''["'](https?://(?:www\.)?turbovidhls\.com/[^"']+)["']''', 1, True)[0]
			if not embedUrl:
				return ''
			return self._turbovidhls(urljoin(url, decodeHtml(embedUrl)), url)

		if parser in ('https://en.luxuretv.com', 'https://beta.xfreehd.com'):
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = parser + '/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			if parser == 'https://beta.xfreehd.com':
				# <source src="..." title="SD|HD">, HD first
				sources = sorted(re.findall(r'''src="([^"]+)"\s*title="(SD|HD)"''', data), key=lambda s: s[1] == 'HD', reverse=True)
				videoUrl = decodeHtml(sources[0][0]) if sources else ''
			else:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''<source\s*src="([^"]+)"''', 1, True)[0]
			if not videoUrl:
				return ''
			userAgent = self.HTTP_HEADER.get('User-Agent', '')
			if '/cf-stream/' in videoUrl:
				# LUXURETV streams through Cloudflare, which answers 403 to exteplayer3/ffmpeg sending a browser
				# User-Agent (the TLS handshake gives it away); a player User-Agent passes, as for CAMSODA
				userAgent = 'VLC/3.0.20 LibVLC/3.0.20'
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': userAgent})

		if parser in WPTUBE_SITES:
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = parser + '/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			frames = [decodeHtml(f) for f in re.findall(r'''<iframe[^>]+?(?:data-lazy-src|data-src|src)=["']([^"']+)["']''', data, re.I)]
			frames = [urljoin(url, f) for f in frames if not re.search(r'ads|adtng|banner|chaturbate|stripchat|bongacams', f)]
			for frame in frames:
				if re.search(r'//(?:www\.)?pbtube\.net/', frame):
					# netu.tv player (pornobae): a click captcha, then an IP-bound link on netu's own CDN
					SetIPTVPlayerLastHostError(_('This video is only on the netu.tv player (pbtube.net), which E2iPlayer cannot play.'))
					continue
				if frame.startswith(parser + '/'):
					# the site's own player page lists the stream directly
					self.HTTP_HEADER['Referer'] = url
					sts, player = self.cm.getPage(frame, self.defaultParams)
					videoUrl = self.cm.ph.getSearchGroups(player, r'''<source[^>]+src=["']([^"']+)["']''', 1, True)[0] if sts else ''
					if videoUrl:
						meta = {'User-Agent': self.HTTP_HEADER.get('User-Agent', '')}
						# video.twimg.com refuses foreign referers (403)
						if 'twimg.com' not in videoUrl:
							meta['Referer'] = frame
						return urlparser.decorateUrl(decodeHtml(videoUrl), meta)
					continue
				# file hoster embed; lulust.com is the same service as luluvdo.com, which urlparser knows
				frame = re.sub(r'^https?://(?:www\.)?lulust\.com/', 'https://luluvdo.com/', frame)
				if 1 != self.up.checkHostSupport(frame):
					# unknown hoster (e.g. tubexplayer.com): packed JWPlayer setup with the playlist in "file"
					self.HTTP_HEADER['Referer'] = url
					sts, player = self.cm.getPage(frame, self.defaultParams)
					packed = re.findall(r'(?s)>eval\(function\(p,a,c,k,e,d\)(.+?)</script>', player) if sts else []
					try:
						player = unpackJSPlayerParams(packed[-1], TEAMCASTPL_decryptPlayerParams, 0, True, True) if packed else player
					except Exception:
						printExc()
					videoUrl = self.cm.ph.getSearchGroups(player or '', r'''file\s*:\s*["']([^"']+\.(?:m3u8|mp4)[^"']*)["']''', 1, True)[0]
					if videoUrl:
						return urlparser.decorateUrl(videoUrl, {'Referer': frame, 'User-Agent': self.HTTP_HEADER.get('User-Agent', '')})
					continue
				try:
					for item in self.up.getVideoLinkExt(frame) or []:
						if isinstance(item, dict) and item.get('url'):
							return item['url']
				except Exception:
					printExc()
			return ''

		if parser in LIVECAM_SITES:
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = parser + '/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			model = url.rstrip('/').split('/')[-1].lstrip('#')
			videoUrl = ''
			try:
				if parser == 'https://www.cam4.com':
					sts, data = self.cm.getPage('https://www.cam4.com/rest/v1.0/profile/%s/streamInfo' % model, self.defaultParams)
					videoUrl = json.loads(data).get('cdnURL', '') if sts else ''
				elif parser == 'https://www.camsoda.com':
					sts, data = self.cm.getPage('https://www.camsoda.com/api/v1/chat/react/%s?username=guest_%d' % (model, random.randrange(100, 55555)), self.defaultParams)
					stream = json.loads(data).get('stream', {}) if sts else {}
					if stream.get('edge_servers'):
						videoUrl = 'https://%s/%s_v1/index.ll.m3u8?token=%s' % (random.choice(stream['edge_servers']), stream['stream_name'], stream['token'])
				elif parser == 'https://www.myfreecams.com':
					sts, data = self.cm.getPage('https://api-edge.myfreecams.com/usernameLookup/' + model, self.defaultParams)
					user = json.loads(data).get('result', {}).get('user', {}) if sts else {}
					session = (user.get('sessions') or [{}])[0]
					# vstate 0 = public show, the channel id is the user id + 100000000
					if session.get('vstate') == 0 and session.get('server_name'):
						videoUrl = 'https://%s.myfreecams.com/NxServer/ngrp:mfc_%s%d.f4v_mobile/playlist.m3u8' % (session['server_name'], session.get('phase') or '', int(user['id']) + 100000000)
				elif parser == 'https://streamate.com':
					# 403/404 while the model is in a private show or gone
					sts, data = self.cm.getPage('https://manifest-server.naiadsystems.com/live/s:%s.json?last=load&format=mp4-hls' % model, self.defaultParams)
					hls = json.loads(data).get('formats', {}).get('mp4-hls', {}) if sts and data.lstrip().startswith('{') else {}
					# the master manifest only lists 768x432; the encodings also offer 720p as a direct playlist
					encodings = [e for e in hls.get('encodings') or [] if e.get('location')]
					videoUrl = max(encodings, key=lambda e: e.get('videoHeight') or 0)['location'] if encodings else hls.get('manifest', '')
				elif parser == 'https://www.xlovecam.com':
					# the list POST filtered by nickname returns a fresh playlist token
					self.HTTP_HEADER.update({'Referer': 'https://www.xlovecam.com/en/', 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'})
					postData = {'config[nickname]': model, 'config[favorite]': '0', 'config[recent]': '0', 'config[vip]': '0', 'config[sort][id]': '35', 'offset[from]': '0', 'offset[length]': '35',
								'origin': 'fetch-stat-on-load', 'stat': '1', 'data[from]': '0', 'data[time]': str(int(time.time())), 'data[off]': ''}
					sts, data = self.cm.getPage('https://www.xlovecam.com/en/performerAction/onlineList/', self.defaultParams, postData)
					for item in (json.loads(data).get('content', {}).get('performerList', []) if sts else []):
						if item.get('nickname', '').lower() == model.lower():
							videoUrl = item.get('hlsPlaylist', '')
							break
					# hlsPlaylist is the low bitrate ".../safe.m3u8"; the same stream is served in higher quality as high.m3u8
					if '/safe.m3u8' in videoUrl:
						sts, data = self.cm.getPage(videoUrl.replace('/safe.m3u8', '/high.m3u8'), self.defaultParams)
						if sts and '#EXTINF' in data:
							videoUrl = videoUrl.replace('/safe.m3u8', '/high.m3u8')
				elif parser == 'https://api.sinparty.com':
					self.HTTP_HEADER.update({'Referer': 'https://sinparty.com/', 'Origin': 'https://sinparty.com'})
					sts, data = self.cm.getPage(url, self.defaultParams)
					data = json.loads(data).get('data', {}) if sts else {}
					if data.get('isLive') is not False and data.get('type') != 'private':
						videoUrl = data.get('playback_url') or ''
				elif parser == 'https://stripchat.com':
					sts, data = self.cm.getPage('https://go.stripchat.com/api/models?limit=1&modelsList=' + model, self.defaultParams)
					for item in (json.loads(data).get('models', []) if sts else []):
						if item.get('username', '').lower() == model.lower() and item.get('status') == 'public':
							videoUrl = (item.get('stream') or {}).get('url', '')
					# the API hands out the 480p master (MOUFLON-obfuscated); the "_160p" master of the same stream also
					# lists the untouched "source" rendition (up to 1080p) as a plain fMP4 playlist
					streamId = self.cm.ph.getSearchGroups(videoUrl, r'''/hls/([0-9]+)/''', 1, True)[0]
					if streamId:
						self.HTTP_HEADER['Origin'] = 'https://stripchat.com'
						sts, data = self.cm.getPage('%s/hls/%s/master/%s_160p.m3u8' % (videoUrl.split('/hls/')[0], streamId, streamId), self.defaultParams)
						source = self.cm.ph.getSearchGroups(data, r'''NAME="source"[^\n]*\n([^\n#]+)''', 1, True)[0].strip() if sts else ''
						if source:
							videoUrl = urljoin(videoUrl, source)
			except Exception:
				printExc()
			if not videoUrl:
				SetIPTVPlayerLastHostError(_('The model is offline or in a private show.'))
				return ''
			userAgent = self.HTTP_HEADER.get('User-Agent', '')
			if parser == 'https://www.camsoda.com':
				# the stream edges (Cloudflare) answer 403 to a browser User-Agent sent by ffmpeg/exteplayer3 (TLS does
				# not match the claimed browser); a player User-Agent passes. Buffering is no way out: hlsdl drops the
				# separate audio track of these streams
				userAgent = 'VLC/3.0.20 LibVLC/3.0.20'
			videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': parser + '/', 'User-Agent': userAgent, 'iptv_livestream': True})
			variants = []
			if parser == 'https://www.camsoda.com':
				# exteplayer3 plays the first variant of the master playlist, here the smallest (256x144); take the best
				# one, merged with the separate audio rendition
				variants = getDirectM3U8Playlist(videoUrl, checkExt=False, sortWithMaxBitrate=999999999)
			elif parser == 'https://api.sinparty.com' and '_adaptive.m3u8' in videoUrl:
				# the top variant of these (Ant Media) playlists is the model's untouched WebRTC source (1080p, ~10 Mbit/s,
				# 8 s segments) that plays without sound; take the best transcoded one (up to 720p) instead
				variants = getDirectM3U8Playlist(videoUrl, checkExt=False, sortWithMaxBitrate=5000000)
			if variants:
				videoUrl = variants[0]['url']
				videoUrl.meta['iptv_livestream'] = True
			return videoUrl

		if parser == 'https://hentai2w.com':
			vid = self.cm.ph.getSearchGroups(url, r'-(\d+)\.html', 1, True)[0]
			if not vid:
				return ''
			embedUrl = 'https://hentai2w.com/embed/' + vid
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(embedUrl, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'''<source src=["']([^"']+?)["']''', 1, True)[0]
			if not videoUrl:
				return ''
			return strwithmeta(videoUrl, {'Referer': embedUrl})

		if parser == 'https://www.hentaicity.com':
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://www.hentaicity.com/'
			self.defaultParams = {'header': self.HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, r'''(https://[^"'\s]+?/mobile\.mp4)''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''(https://[^"'\s]+?/master\.m3u8[^"'\s<]*)''', 1, True)[0]
			if videoUrl:
				videoUrl = videoUrl.replace('\\/', '/')
			if not videoUrl:
				return ''
			return strwithmeta(videoUrl, {'Referer': url})

		if parser == 'https://www.amateurdoporn.com':
			COOKIEFILE = join(GetCookieDir(), 'amateurdoporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'amateurdoporn.cookie', 'amateurdoporn.com', self.defaultParams)
			if not sts:
				return ''
			m = re.search(r'source\ssrc=["]([^$]+?)["]\stype="application', data)
			if not m:
				return ''
			videoUrl = m.group(1)
			if 'm3u8' in videoUrl:
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
				return ''
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://spankbang.com':
			COOKIEFILE = join(GetCookieDir(), 'spankbang.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = 'https://spankbang.com/'
			self.HTTP_HEADER['Cookie'] = 'country=US'
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'spankbang.cookie', 'spankbang.com', self.defaultParams)
			if not sts or not data:
				printDBG('SPANKBANG: video page fetch failed')
				return ''

			videoUrl = ''
			m = re.search(r"stream_url_[^\s=]+\s*=\s*([\"'])(.+?)\1", data)
			if m:
				videoUrl = m.group(2).replace('\\/', '/')
				printDBG('SPANKBANG direct stream URL: ' + videoUrl)
			if not videoUrl:
				sdm = re.search(r"stream_data\s*=\s*\{(.{1,5000})\}", data, re.S)
				if sdm:
					sd = sdm.group(1)
					qm = re.search(r"'m3u8'\s*:\s*\[\s*'([^']+)'", sd)
					if not qm:
						for q in ('1080p', '720p', '480p', '320p', '240p'):
							qm = re.search(r"'%s'\s*:\s*\[\s*'([^']+)'" % q, sd)
							if qm:
								break
					if qm and qm.group(1).startswith('http'):
						videoUrl = qm.group(1).replace('\\/', '/')
						printDBG('SPANKBANG stream_data URL: ' + videoUrl)
			if not videoUrl:
				m = re.search(r"data-streamkey\s*=\s*([\"'])(.+?)\1", data, re.I | re.S)
				if not m:
					printDBG('SPANKBANG: data-streamkey not found')
					return ''
				streamKey = m.group(2)
				printDBG('SPANKBANG stream key length: %d' % len(streamKey))

				apiHeader = self.cm.getDefaultHeader(browser='chrome')
				apiHeader['Referer'] = url
				apiHeader['X-Requested-With'] = 'XMLHttpRequest'
				apiHeader['Origin'] = 'https://spankbang.com'
				apiHeader['Accept'] = 'application/json, text/javascript, */*; q=0.01'
				apiHeader['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
				apiParams = {'header': apiHeader, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
				postData = {'id': streamKey, 'data': 0}
				sts, out = self.getPage('https://spankbang.com/api/videos/stream', 'spankbang.cookie', 'spankbang.com', apiParams, post_data=postData)
				printDBG('SPANKBANG API status: ' + str(sts))
				printDBG('SPANKBANG API response: ' + str(out)[:2000])

				if not sts or not out or str(out).strip() == '{}':
					try:
						query = {'id': streamKey, 'data': 0}
						requestData = {'url': 'https://spankbang.com/api/videos/stream', 'header': apiHeader, 'use_host': False, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'use_post': True, 'return_data': True, 'data': urlencode(query)}
						out = self.cm.getURLRequestData(requestData)
						printDBG('SPANKBANG API fallback response: ' + str(out)[:2000])
					except Exception:
						printExc()
						out = ''

				try:
					obj = json.loads(out) if out else {}
				except Exception:
					printDBG('SPANKBANG: invalid stream API JSON')
					return ''
				candidates = []
				for key2, value in obj.items():
					if isinstance(value, list):
						for valueItem in value:
							if valueItem:
								candidates.append((key2, valueItem))
					elif value:
						candidates.append((key2, value))
				if not candidates:
					printDBG('SPANKBANG: stream API returned no usable URLs')
					return ''
				candidates.sort(key=lambda x: (0 if '.m3u8' in str(x[1]).lower() else 1, x[0]))
				videoUrl = str(candidates[0][1]).replace('\\/', '/')
				printDBG('SPANKBANG selected stream [%s]: %s' % (candidates[0][0], videoUrl))

			meta = {'Referer': url, 'Origin': 'https://spankbang.com', 'User-Agent': self.HTTP_HEADER.get('User-Agent', USER_AGENT)}
			if '.m3u8' in videoUrl.lower():
				decorated = urlparser.decorateUrl(videoUrl, meta)
				finalUrl = self._bestM3U8Variant(decorated)
				if finalUrl:
					finalUrl = urlparser.decorateUrl(finalUrl, meta)
					printDBG('SPANKBANG FINAL HLS URL: ' + finalUrl)
					return finalUrl
			return urlparser.decorateUrl(videoUrl, meta)

		query_data = {'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
		try:
			data = self.cm.getURLRequestData(query_data)
		except Exception:
			printDBG('Host getResolvedURL query error')
			return videoUrl

		if parser == 'https://www.ah-me.com':
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.homemoviestube.com':
			videoUrl = self.cm.ph.getSearchGroups(data, '''value="settings=([^"^']+?)['"]''')[0]
			if videoUrl:
				query_data = {'url': videoUrl, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
				try:
					data = self.cm.getURLRequestData(query_data)
				except Exception:
					printDBG('Host listsItems query error url: ' + url)
				return self.cm.ph.getSearchGroups(data, '''flvMask:([^"^']+?);''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&').replace(' ', '%20')
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				if videoUrl.startswith('/'):
					videoUrl = 'https://www.homemoviestube.com' + videoUrl
				return videoUrl
			return ''

		if parser == 'https://www.homepornking.com':
			printDBG('data: ' + data)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'source type="video/mp4" src="', '" /></video></div>', False)[1]
			printDBG('VideoLink: ' + videoUrl)
			return videoUrl

		if parser == 'https://motherlesss.net':
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=["]([^"^']+?)["]''', 1, True)[0]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://mustjav.com':
			sts, data = self.get_Page(url)
			data2 = self.cm.ph.getDataBeetwenMarkers(data, 'target="#video-share', '#videoEmbedHtml', False)[1]
			printDBG('Video data: ' + videoUrl)
			videoUrl = self.cm.ph.getSearchGroups(data2, '''iframe.+?[;]([^"^']+?)[&]#''')[0].replace('&amp;', '&')
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://fullxcinema.com':
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, '''contentURL.+?=['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''iframe.src=['"]([^"^']+?)['"]''')[0]
			if videoUrl.startswith('/'):
				videoUrl = 'https:' + videoUrl
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://teenxy.com':
			sts, data = self.get_Page(url)
			self.MAIN_URL = 'https://teenxy.com'
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].type''')[0]
			if videoUrl:
				videoUrl = checkhttps(videoUrl)
				if videoUrl.startswith('/'):
					videoUrl = self.MAIN_URL + videoUrl
				printDBG('VideoLink: ' + videoUrl)
				return videoUrl
			return ''

		if parser == 'https://warddogs.com':
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, '''<video[^>]*?src=['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].type''')[0]
			videoUrl = videoUrl.replace('&#038;', '&')
			printDBG('VideoLink: ' + videoUrl)
			return videoUrl if videoUrl else ''

		if parser == 'https://videosection.com':
			# Resolve the page's own video_url/video_alt_url before considering
			# any page-wide HLS URL - page-wide growcdnssedge HLS links can belong
			# to LiveCams/recommended content and are not safe as the selected clip.
			printDBG('VIDEOSECTION PARSER V10')
			COOKIEFILE = join(GetCookieDir(), 'videosection.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {
				'header': self.HTTP_HEADER,
				'use_cookie': True,
				'load_cookie': True,
				'save_cookie': True,
				'cookiefile': COOKIEFILE,
				'return_data': True
			}

			sts, data = self.get_Page(url, self.defaultParams)
			if not sts or not data:
				printDBG('VideoSection V10: page fetch failed')
				return ''

			video_id = ''
			m = re.search(r'/video/(\d+)(?:[/?#]|$)', str(url))
			if m:
				video_id = m.group(1)
			printDBG('VideoSection V10 page video_id: ' + video_id)

			license_code = ''
			for pattern in (
				r'''license_code\s*:\s*['"]([^'"]+)['"]''',
				r'''license_code\s*=\s*['"]([^'"]+)['"]''',
			):
				license_code = self.cm.ph.getSearchGroups(data, pattern, 1, True)[0].strip()
				if license_code:
					break
			printDBG('VideoSection V10 license_code: ' + ('FOUND' if license_code else ''))

			video_candidates = []
			patterns = (
				r'''video_url\s*:\s*['"]([^'"]+)['"]''',
				r'''video_alt_url\s*:\s*['"]([^'"]+)['"]''',
				r'''video_url\s*=\s*['"]([^'"]+)['"]''',
				r'''video_alt_url\s*=\s*['"]([^'"]+)['"]''',
				r'''"video_url"\s*:\s*"([^"]+)"''',
				r'''"video_alt_url"\s*:\s*"([^"]+)"''',
				r'''videoUrl\s*:\s*['"]([^'"]+)['"]''',
				r'''video_url\s*:\s*\n.+?['"]([^'"]+)['"]''',
			)
			for pattern in patterns:
				try:
					found = self.cm.ph.getSearchGroups(data, pattern, 1, True)
					for item in found:
						if item and item not in video_candidates:
							video_candidates.append(item)
				except Exception:
					pass

			try:
				found = re.findall(r'''video.{1,6}url.{0,3}:\s*['"]([^'"]+)['"]''', data, re.S)
				for item in found:
					if item and item not in video_candidates:
						video_candidates.append(item)
			except Exception:
				pass

			printDBG('VideoSection V10 KVS candidates: ' + str(video_candidates))

			def _clean_video_url(videoUrl):
				videoUrl = (videoUrl or '').strip()
				videoUrl = videoUrl.replace(r'\/', '/').replace('&amp;', '&')
				videoUrl = videoUrl.replace('\\u002F', '/').replace('\\u002f', '/')
				videoUrl = videoUrl.replace('\\u003A', ':').replace('\\u003a', ':')
				if videoUrl.startswith('//'):
					videoUrl = 'https:' + videoUrl
				elif videoUrl.startswith('/'):
					videoUrl = urljoin(self.MAIN_URL + '/', videoUrl)
				return videoUrl

			videoUrl = ''
			for candidate in video_candidates:
				candidate = _clean_video_url(candidate)
				if not candidate:
					continue

				# KVS protected URLs are commonly returned as function/0/...
				if 'function/0/' in candidate and license_code:
					try:
						candidate = decryptHash(candidate, license_code, '16')
						candidate = _clean_video_url(candidate)
						printDBG('VideoSection V10 decrypted video URL: ' + candidate)
					except Exception as e:
						printDBG('VideoSection V10 decrypt exception: ' + str(e))
						continue

				candidate = candidate.split('/?br')[0]
				candidate = candidate.replace('.mp4/', '.mp4')
				if candidate and ('m3u8' in candidate or '.mp4' in candidate):
					videoUrl = candidate
					break

			if videoUrl:
				printDBG('VideoSection V10 FINAL KVS videoUrl: ' + videoUrl)
				metaParams = {
					'Referer': url,
					'User-Agent': self.HTTP_HEADER.get('User-Agent', USER_AGENT)
				}

				if '.m3u8' in videoUrl:
					metaParams['Origin'] = 'https://videosection.com'
					try:
						decorated = urlparser.decorateUrl(videoUrl, metaParams)
						tmp = getDirectM3U8Playlist(
							decorated,
							checkContent=True,
							sortWithMaxBitrate=999999999
						)
						for item in tmp:
							if item.get('url'):
								return urlparser.decorateUrl(item['url'], metaParams)
					except Exception as e:
						printDBG('VideoSection V10 KVS HLS exception: ' + str(e))
					return urlparser.decorateUrl(videoUrl, metaParams)

				return urlparser.decorateUrl(videoUrl, metaParams)

			direct_candidates = []
			for pattern in (
				r'''<source[^>]+src=['"]([^'"]+)['"]''',
				r'''<video[^>]+src=['"]([^'"]+)['"]''',
				r'''contentUrl\s*[:=]\s*['"]([^'"]+)['"]''',
				r'''["']contentUrl["']\s*:\s*["']([^"']+)["']''',
			):
				try:
					found = self.cm.ph.getSearchGroups(data, pattern, 1, True)
					for item in found:
						item = _clean_video_url(item)
						if item and item not in direct_candidates:
							direct_candidates.append(item)
				except Exception:
					pass

			for candidate in direct_candidates:
				if 'growcdnssedge.com' in candidate:
					continue
				if 'heat-preview' in candidate or '/static/img/' in candidate or '.svg' in candidate:
					continue
				if '.m3u8' in candidate or '.mp4' in candidate:
					printDBG('VideoSection V10 direct player candidate: ' + candidate)
					metaParams = {
						'Referer': url,
						'User-Agent': self.HTTP_HEADER.get('User-Agent', USER_AGENT)
					}
					if '.m3u8' in candidate:
						metaParams['Origin'] = 'https://videosection.com'
						try:
							decorated = urlparser.decorateUrl(candidate, metaParams)
							tmp = getDirectM3U8Playlist(
								decorated,
								checkContent=True,
								sortWithMaxBitrate=999999999
							)
							for item in tmp:
								if item.get('url'):
									return urlparser.decorateUrl(item['url'], metaParams)
						except Exception as e:
							printDBG('VideoSection V10 direct HLS exception: ' + str(e))
					return urlparser.decorateUrl(candidate, metaParams)

			printDBG('VIDEOSECTION PARSER V11 dynamic stream scan')

			def _v11_clean(value):
				value = (value or '').strip().replace(r'\\/', '/')
				value = value.replace('\\u002F', '/').replace('\\u002f', '/')
				value = value.replace('\\u003A', ':').replace('\\u003a', ':')
				value = value.replace('&amp;', '&')
				if value.startswith('//'):
					value = 'https:' + value
				elif value.startswith('/'):
					value = urljoin('https://videosection.com', value)
				return value

			def _v11_find_stream(text, source_name):
				if not text:
					return ''
				patterns = [
					r"https?://[^\"'\s<>]+videosection\.com/[^\"'\s<>]+/stream/[^\"'\s<>]+",
				r"https?://[^\"'\s<>]+/c/[0-9a-z]+/[0-9a-z]+/[0-9a-f]+/stream/[^\"'\s<>]+",
				r"/c/[0-9a-z]+/[0-9a-z]+/[0-9a-f]+/stream/[^\"'\s<>]+",
				r"(?:streamUrl|stream_url|mediaUrl|media_url|videoSource|video_source|playlistUrl|playlist_url)\s*[:=]\s*[\"']([^\"']+)[\"']",
				r"[\"']([^\"']*/stream/(?:240p|360p|480p|720p|1080p)/[^\"']*seg-[^\"']+\.ts[^\"']*)[\"']",
				]
				for pat in patterns:
					try:
						found = re.findall(pat, text, re.I | re.S)
					except Exception:
						found = []
					for item in found:
						if isinstance(item, tuple):
							item = item[0]
						item = _v11_clean(item)
						if '/stream/' in item and ('/c/' in item or 'streamUrl' in pat or 'stream_url' in pat):
							printDBG('VideoSection V11 stream candidate from %s: %s' % (source_name, item))
							return item
				return ''

			videoUrl = _v11_find_stream(data, 'page')
			if not videoUrl:
				script_urls = re.findall(r"<script[^>]+src=[\"']([^\"']+)[\"']", data, re.I)
				seen = set()
				checked = 0
				for script_url in script_urls:
					if checked >= 8:
						break
					script_url = _v11_clean(script_url)
					if not script_url or script_url in seen or 'videosection.com' not in script_url:
						continue
					seen.add(script_url)
					checked += 1
					try:
						sts_js, data_js = self.get_Page(script_url, self.defaultParams)
					except Exception:
						sts_js, data_js = False, ''
					if sts_js and data_js:
						printDBG('VideoSection V11 scanned JS: ' + script_url)
						videoUrl = _v11_find_stream(data_js, script_url)
						if videoUrl:
							break

			if videoUrl:
				metaParams = {'Referer': url, 'Origin': 'https://videosection.com', 'User-Agent': self.HTTP_HEADER.get('User-Agent', USER_AGENT)}
				# a single nginx-vod segment (.../seg-1-v1-a1.ts) would play only a few
				# seconds - its media playlist is .../index-v1-a1.m3u8
				segUrl = re.sub(r'/seg-\d+-(v\d+(?:-a\d+)?)\.ts', r'/index-\1.m3u8', videoUrl)
				if segUrl != videoUrl:
					videoUrl = segUrl
					metaParams['iptv_proto'] = 'm3u8'
				videoUrl = urlparser.decorateUrl(videoUrl, metaParams)
				printDBG('VideoSection V11 FINAL dynamic stream: ' + videoUrl)
				return videoUrl

			printDBG('VideoSection V11: no dynamic stream found in page or player JS')
			return ''

		if parser == 'https://everycamgirl.com':
			COOKIEFILE = join(GetCookieDir(), 'everycamgirl.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			printDBG('PAGE TITLE: ' + url)
			# everycamgirl.com embeds the real CDN stream URL directly on its own
			# model page via data-src, regardless of the underlying platform
			# (Chaturbate/Stripchat/BongaCams/CamSoda/...) - no need to visit the
			# platform site itself (which for Chaturbate is blocked behind a
			# login/age-verification wall anyway).
			videoUrl = self.cm.ph.getSearchGroups(data, '''data-src=['"]([^"^']+?)['"]''')[0]
			videoUrl = videoUrl.replace('&amp;', '&')
			videoUrl = videoUrl.replace('%3A', ':').replace('%2B', '+').replace('%2F', '/')
			printDBG('EVERYCAMGIRL stream link: ' + videoUrl)
			if not videoUrl:
				self.sessionEx.open(MessageBox, _("This room is currently offline or unavailable."), type=MessageBox.TYPE_INFO, timeout=10)
				return ''
			if self.cm.isValidUrl(videoUrl):
				tmp = getDirectM3U8Playlist(videoUrl)
				try:
					tmp = sorted(tmp, key=lambda item: int(item.get('bitrate', '0')))
				except Exception:
					pass
				for item in tmp:
					printDBG('Host listsItems valtab: ' + str(item))
				try:
					return '' if item['bitrate'] == 'unknown' else item['url']
				except Exception:
					pass
			printDBG('VideoLink: ' + videoUrl)
			videoUrl = decodeUrl(videoUrl)
			printDBG('VideoLink fixed: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttps(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://cam-sex.net':
			COOKIEFILE = join(GetCookieDir(), 'chaturbate.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			printDBG('PAGE TITLE: ' + url)
			videoUrl = self.cm.ph.getSearchGroups(data, '''iframe.src=['"]([^"^']+?)['"]''')[0]
			printDBG('video link: ' + videoUrl)
			videoUrl2 = strwithmeta(videoUrl)
			printDBG('METADATA: ' + str(videoUrl2))
			mainUrl = self.cm.ph.getSearchGroups(videoUrl, '''([^"^']+?)[i]n/''')[0]
			printDBG('MAIN URL: ' + mainUrl)
			room = self.cm.ph.getSearchGroups(videoUrl, '''room[=]([^"^']+?)[&]''')[0]
			printDBG('Room data: ' + room)
			campaign = self.cm.ph.getSearchGroups(videoUrl, '''campaign[=]([^"^']+?)[&]''')[0]
			printDBG('Campaign data: ' + campaign)
			settings = self.cm.ph.getSearchGroups(videoUrl, '''&room=.{,20}[&](.+)''')[0]
			printDBG('SETTINGS data: ' + settings)
			tour = self.cm.ph.getSearchGroups(videoUrl, '''tour[=]([^"^']+?)[&]''')[0]
			printDBG('Tour data: ' + tour)
			videoUrl = "%sfullvideo/?b=%s&campaign=%s&%s&tour=%s" % (mainUrl, room, campaign, settings, tour)
			printDBG('READY URL: ' + videoUrl)
			COOKIEFILE = join(GetCookieDir(), 'chaturbate.cookie')
			self.cm.HEADER = {'User-Agent': self.cm.getDefaultHeader()['User-Agent'], 'X-Requested-With': 'XMLHttpRequest'}
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.get_Page(videoUrl, self.defaultParams)
			linkUrl = self.cm.ph.getSearchGroups(data, '''rel="canonical" href=["]([^"^']+?)["]''')[0]
			printDBG('Original title: ' + linkUrl)
			sts, data = self.get_Page(linkUrl, self.defaultParams)
			self.cm.HEADER = None
			mainUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{,15}[2]([^"^']+?)[,]''')[0]
			printDBG('Original title: ' + mainUrl)
			videoUrl = mainUrl.replace('\\u002D', '-').replace(r'\-', '-').replace('\\u0022', '')
			videoUrl = videoUrl.replace('m3u8\\', 'm3u8')
			printDBG('Corrected address: ' + videoUrl)
			if self.cm.isValidUrl(videoUrl):
				tmp = getDirectM3U8Playlist(videoUrl)
				try:
					tmp = sorted(tmp, key=lambda item: int(item.get('bitrate', '0')))
				except Exception:
					pass
				for item in tmp:
					printDBG('Host listsItems valtab: ' + str(item))
				try:
					return '' if item['bitrate'] == 'unknown' else item['url']
				except Exception:
					pass
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttps(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://anacams.com':
			headUrl = self.cm.ph.getSearchGroups(data, '''iframe.{20,35}src=['"]([^"^']+?)['"]''')[0]
			printDBG('Fetched Link: ' + headUrl)
			sts, data = self.get_Page(headUrl)
			videoUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{8,15}[2]([^"^']+?)[,]''')[0].replace('\\u002D', '-').replace('\\u0022', '')
			printDBG('ANACAMS linklista: ' + videoUrl)
			if not videoUrl:
				self.sessionEx.waitForFinishOpen(MessageBox, _('HIDDEN CAM SHOW IN PROGRESS. TRY AGAIN LATER!'), type=MessageBox.TYPE_INFO, timeout=30)
				return ''
			if self.cm.isValidUrl(videoUrl):
				tmp = getDirectM3U8Playlist(videoUrl)
				try:
					tmp = sorted(tmp, key=lambda item: int(item.get('bitrate', '0')))
				except Exception:
					pass
				for item in tmp:
					printDBG('Host listsItems valtab: ' + str(item))
				try:
					return '' if item['bitrate'] == 'unknown' else item['url']
				except Exception:
					pass
			printDBG('Ready link: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttps(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://www.masturbate2gether.com':
			COOKIEFILE = join(GetCookieDir(), 'chaturbate.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			printDBG('#--- Parser for Chaturbate Cams ---#')
			headUrl = self.cm.ph.getSearchGroups(data, '''chaturbate.+src=['"]([^"^']+?)['"]''')[0]
			if not headUrl:
				return ''
			sts, data = self.get_Page(headUrl)
			if not sts:
				return ''
			try:
				mainUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{13}[2]([^"^']+?)[u]0022''')[0]
			except Exception:
				self.sessionEx.open(MessageBox, _("This show is private. Try again later!"), type=MessageBox.TYPE_INFO, timeout=10)
			mainUrl = mainUrl.rstrip('\\')
			printDBG('Original title: ' + mainUrl)
			if mainUrl:
				videoUrl = mainUrl.replace('\\u002D', '-').replace(r'\-', '-')
				videoUrl = videoUrl.replace('m3u8\\', 'm3u8').replace('\\u003D', '=')
				if self.cm.isValidUrl(videoUrl):
					tmp = getDirectM3U8Playlist(videoUrl)
					try:
						tmp = sorted(tmp, key=lambda item: int(item.get('bitrate', '0')))
					except Exception:
						self.sessionEx.open(MessageBox, _("This model is offline."), type=MessageBox.TYPE_INFO, timeout=10)
					for item in tmp:
						printDBG('Host listsItems valtab: ' + str(item))
					try:
						return '' if item['bitrate'] == 'unknown' else item['url']
					except Exception:
						self.sessionEx.open(MessageBox, _("This model is offline."), type=MessageBox.TYPE_INFO, timeout=10)
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttps(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://yourlive.webcam':
			printDBG('Host listsItems parser name= ' + parser)
			sts, data = self.get_Page(url)
			firstUrl = self.cm.ph.getSearchGroups(data, '''mainframe.+src=['"]([^"^']+?)['"]''')[0].strip()
			printDBG('VideoLink: ' + firstUrl)
			sts, data2 = self.get_Page(firstUrl)
			mainUrl = self.cm.ph.getSearchGroups(data2, '''hls_source.{13}[2]([^"^']+?)[u]0022''')[0]
			mainUrl = mainUrl.rstrip('\\')
			printDBG('Original title: ' + mainUrl)
			if not mainUrl:
				self.sessionEx.open(MessageBox, _("This room is offline. Try again later!"), type=MessageBox.TYPE_INFO, timeout=10)
			if mainUrl:
				videoUrl = mainUrl.replace('\\u002D', '-').replace('\\-', '-')
				videoUrl = videoUrl.replace('m3u8\\', 'm3u8').replace('\\u003D', '=')
				printDBG('Fixed address ' + videoUrl)
				videoUrl2 = strwithmeta(videoUrl)
				if sts and videoUrl2.meta.get('status_code', 0) in [410, 404]:
					self.sessionEx.waitForFinishOpen(MessageBox, _('HIDDEN CAM SHOW IN PROGRESS. TRY AGAIN LATER!'), type=MessageBox.TYPE_INFO, timeout=30)
					return ''
				if self.cm.isValidUrl(videoUrl):
					try:
						tmp = getDirectM3U8Playlist(videoUrl)
					except Exception:
						self.sessionEx.open(MessageBox, _("This model is offline."), type=MessageBox.TYPE_INFO, timeout=10)
						return ''

					def _bitrateKey(item):
						try:
							return int(item.get('bitrate', '0'))
						except (TypeError, ValueError):
							return 0
					tmp = sorted(tmp, key=_bitrateKey)
					for item in tmp:
						printDBG('Host listsItems valtab: ' + str(item))
					try:
						return '' if item['bitrate'] == 'unknown' else item['url']
					except Exception:
						self.sessionEx.open(MessageBox, _("This model is offline."), type=MessageBox.TYPE_INFO, timeout=10)
			printDBG('Ready link: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttps(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://hentaigasm.com':
			videoUrl = self.cm.ph.getSearchGroups(data, '''file: ['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			printDBG('Fetched Link: ' + videoUrl)
			videoUrl = checkhttps(videoUrl).replace(' ', '%20')
			return videoUrl

		if parser == 'https://rusporn.tv':
			sts, data = self.getPage(url, 'rusporn.cookie', 'rusporn.tv', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, '''href=['"]([^"^']+?)['"].data-attach''')[0]
			printDBG('New parser: ' + videoUrl)
			if videoUrl:
				return videoUrl
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			printDBG('License key: ' + license_code)
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url2:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_alt_url:.['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url: ['"]([^"^']+?)['"]''')[0]
			printDBG('Fetched link: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			return videoUrl

		if parser == 'https://www.katestube.com':
			data2 = self.cm.ph.getDataBeetwenMarkers(data, 'var flashvars', '}', False)[1]
			printDBG('Fetched data: ' + data2)
			license_code = self.cm.ph.getSearchGroups(data2, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			if data2:
				return self.cm.ph.getSearchGroups(data2, '''['"](https://www.katestube.com/get_file[^"^']+?)['"]''')[0].replace('&amp;', '&')
			data2 = self.cm.ph.getDataBeetwenMarkers(data, 'sources:', ']', False)[1]
			if data2:
				return self.cm.ph.getSearchGroups(data, r'''src:\s['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			videoUrl = self.cm.ph.getSearchGroups(data, '''file: ['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return unquote(videoUrl)
			videoUrl = self.cm.ph.getSearchGroups(data, '''['"](https://www.katestube.com/get_file[^"^']+?)['"]''')[0].replace('&amp;', '&')
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data2, '''video_url:.['"]([^"^']+?)['"]''')[0].replace(r'\/', '/').replace('&amp;', '&').strip()
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			return unquote(videoUrl) if videoUrl else ''

		if parser == 'https://alpha.tnaflix.com':
			videoPage = re.findall('"embedUrl" content="(.*?)"', data, re.S)
			if videoPage:
				printDBG('Host videoPage:' + videoPage[0])
				return 'http:' + videoPage[0]
			return ''

		if parser == 'https://www.faphub.xxx':
			videoPage = re.findall("url: '(.*?)'", data, re.S)
			if videoPage:
				printDBG('Host videoPage:' + videoPage[0])
				return videoPage[0]
			return ''

		if parser == 'https://www.proporn.com':
			videoPage = re.findall('source src="(.*?)"', data, re.S)
			if videoPage:
				printDBG('Host videoPage:' + videoPage[0])
				return videoPage[0]
			return ''

		if parser == 'https://www.xnxx.com':
			if url:
				printDBG('XNXX PARSER LINK: ' + url)
			if 'm3u8' in url:
				videoUrl = self._bestM3U8Variant(url)
				if videoUrl:
					return videoUrl
			else:
				COOKIEFILE = join(GetCookieDir(), 'xnxx.cookie')
				self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
				sts, data = self._getPage(url, self.defaultParams)
				videoUrl = self.cm.ph.getSearchGroups(data, r'''VideoHLS\(['"]([^ ^#]+?)['"].;''', 1, True)[0]
				printDBG('Videolink: ' + videoUrl)
				url = (self._bestM3U8Variant(videoUrl) or videoUrl) if videoUrl else videoUrl
			printDBG('Videolink: ' + url)
			return unquote(url)

		if parser == 'https://www.xvideos.com':
			printDBG('data: ' + data)
			videoUrl = re.search(r"setVideoUrlHigh\('(.*?)'", data, re.S)
			if videoUrl:
				return decodeUrl(videoUrl.group(1))
			videoUrl = re.search('flv_url=(.*?)&', data, re.S)
			return decodeUrl(videoUrl.group(1)) if videoUrl else ''

		if parser == 'https://embed.redtube.com':
			videoPage = re.findall('sources:.*?":"(.*?)"', data, re.S)
			if videoPage:
				link = videoPage[-1].replace(r"\/", r"/")
				link = checkhttps(link)
				return link
			return ''
		if parser == 'https://m.tube8.com':
			match = self.RE_DIV_PLAY_HREF.findall(data)
			return match[0]

		if parser == 'https://m.pornhub.com':
			match = self.RE_DIV_PLAY_HREF.findall(data)
			return match[0]

		if parser == 'https://www.pornhat.com/':
			data = self.cm.ph.getDataBeetwenMarkers(data, ' data-hls', '</video>', False)[1]
			printDBG('To Link: ' + data)

			videoUrl = re.findall('source.src=["]([^"]+?)["]', data, re.S)
			if videoUrl:
				videoUrl = videoUrl[-1]
				printDBG('Final: ' + videoUrl)
			sts, data2 = self.get_Page(videoUrl)
			if not sts:
				return ''
			match = re.findall('[\n]([^"]+?)[\n]', data2, re.S)
			if match:
				videoUrl = match[-1]
				printDBG('Fetched new VIDEOURL:\n' + videoUrl)
			else:
				match = re.findall('"[\n]([^"]+?)[\n]', data2, re.S)
				videoUrl = match[-1]
				printDBG('Fetched new VIDEOURL 2:\n' + videoUrl)
			return strwithmeta(videoUrl, {'iptv_proto': 'm3u8'})  # variant line of the master playlist

		if parser == 'https://www.drtuber.com':
			params = re.findall(r'params\s\+=\s\'h=(.*?)\'.*?params\s\+=\s\'%26t=(.*?)\'.*?params\s\+=\s\'%26vkey=\'\s\+\s\'(.*?)\'', data, re.S)
			if params:
				for (param1, param2, param3) in params:
					bparam3 = param3
					if isinstance(param3, basestring):
						bparam3 = param3.encode('utf-8')
					_hash = hashlib.md5(bparam3 + base64.b64decode('UFQ2bDEzdW1xVjhLODI3')).hexdigest()
					printDBG('Ready HASH: ' + str(_hash))
					url = '%s/player_config/?h=%s&t=%s&vkey=%s&pkey=%s&aid=' % ("https://www.drtuber.com", param1, param2, param3, _hash)
					printDBG('Ready URL: ' + url)
					query_data = {'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
					try:
						data = self.cm.getURLRequestData(query_data)
					except Exception:
						printDBG('Host listsItems query error')
						printDBG('Host listsItems query error url: ' + url)
					url = re.findall(r'video_file>.*?(http.*?)\]\]><\/video_file>', data, re.S)
					if url:
						url = str(url[0])
						url = url.replace("&amp;", "&")
						printDBG('Host listsItems url: ' + url)
						return url
			return ''

		if parser == 'https://vidlox.tv':
			parse = re.search('sources.*?"(http.*?)"', data, re.S)
			return parse.group(1).replace(r'\/', '/') if parse else ''

		if parser == 'https://xxxkingtube.com':
			parse = re.search("File = '(http.*?)'", data, re.S)
			return parse.group(1).replace(r'\/', '/') if parse else ''

		if parser == 'https://www.flyflv.com':
			parse = re.search('fileUrl="([^"]+?)"', data, re.S)
			return checkhttps(parse.group(1).replace(r'\/', '/')) if parse else ''

		if parser == 'https://vivatube.com':
			videoUrl = re.search('video_id = "(.*?)"', data, re.S)
			if videoUrl:
				xml = 'https://vivatube.com/player_config_json/?vid=%s&aid=0&domain_id=0&embed=0&ref=&check_speed=0' % videoUrl.group(1)
				try:
					data = self.cm.getURLRequestData({'url': xml, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
				except Exception:
					printDBG('Host getResolvedURL query error xml')
					return ''
				videoPage = re.search('"hq":"(http.*?)"', data, re.S)
				if videoPage:
					return videoPage.group(1).replace(r'\/', '/')
				videoPage = re.search('"lq":"(http.*?)"', data, re.S)
				if videoPage:
					return videoPage.group(1).replace(r'\/', '/')
			return ''

		if parser == 'https://porndig.com':
			videoUrl = self.cm.ph.getSearchGroups(data, r'''<source\ssrc=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			videoUrl = checkhttp(videoUrl)
			if '.m3u8' in videoUrl and self.cm.isValidUrl(videoUrl):
				best = self._bestM3U8Variant(videoUrl)  # the first variant of the master was its lowest
				if best:
					return best
			if 'sources": ' in data:
				try:
					sources = self.cm.ph.getDataBeetwenMarkers(data, 'sources": ', ']', False)[1]
					result = byteify(json.loads(sources + ']'))
					for item in result:
						try:
							if str(item["label"]) == '720p':
								return str(item["src"]).replace(r'\/', '/')
							if str(item["label"]) == '480p':
								return str(item["src"]).replace(r'\/', '/')
							if str(item["label"]) == '360p':
								return str(item["src"]).replace(r'\/', '/')
							if str(item["label"]) == '240p':
								return str(item["src"]).replace(r'\/', '/')
						except Exception:
							printExc()
				except Exception:
					printExc()
			return videoUrl

		if parser == 'https://www.fetishpapa.com':
			COOKIEFILE = join(GetCookieDir(), 'fetishpapa.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'fetishpapa.cookie', 'fetishpapa.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.findall(r"<source[^>]+src=[\"']([^\"']+)[\"'][^>]*>", data, re.I | re.S)
			if not videoUrl:
				videoUrl = re.findall(r"(?:src|file|videoUrl|video_url)[\"']?\s*[:=]\s*[\"']([^\"']+?\.(?:mp4|m3u8)(?:\?[^\"']*)?)[\"']", data, re.I | re.S)
			if not videoUrl:
				videoUrl = re.findall(r"https?[^\"'\s]+?\.(?:mp4|m3u8)(?:\?[^\"'\s<]*)?", data, re.I)
			if not videoUrl:
				return ''
			hlsUrl = decodeHtml(videoUrl[0]).replace(r'\/', '/')
			printDBG('FETISHPAPA VIDEO URL: ' + str(hlsUrl))
			return urlparser.decorateUrl(hlsUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://www.empflix.com':
			printDBG('EMPFLIX PARSER')
			COOKIEFILE = join(GetCookieDir(), 'empflix.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'empflix.cookie', 'empflix.com', self.defaultParams)
			videoUrl = re.findall(r'source\ssrc=["]([^"]+?)["]\stype="video/mp4', data, re.S)
			if videoUrl:
				printDBG('Videolinks: ' + str(videoUrl))
				videoUrl = videoUrl[0]
				printDBG('End Link: ' + videoUrl)
				return videoUrl
			return ''

		if parser == 'https://sexkino.to':
			videoUrl = re.findall('<iframe.*?src="(.*?)"', data, re.S)
			if videoUrl:
				return self.getResolvedURL(videoUrl[-1])

		if parser == 'https://tik.porn':
			printDBG('TIKPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'tikporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'tikporn.cookie', 'tik.porn', self.defaultParams)
			videoUrl = re.findall('contentUrl":["]([^"]+?mp4)["]', data, re.S)
			if videoUrl:
				printDBG('Videolinks: ' + str(videoUrl))
				videoUrl = videoUrl[0]
				printDBG('End Link: ' + videoUrl)
				return videoUrl
			return ''

		if parser == 'https://teenager365.to':
			printDBG('TEENAGER365 PARSER')
			COOKIEFILE = join(GetCookieDir(), 'teenager365.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'teenager365.cookie', 'teenager365.to', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = re.findall(r"video.{,5}url.{0,1}:\s[']([^']+?)['],", data, re.S)
			if videoUrl:
				printDBG('Videolinks: ' + str(videoUrl))
				videoUrl = videoUrl[0]
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('videoURL: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://www.freeomovie.to':
			printDBG('FREEOMOVIE PARSER START')
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			params = {'header': HTTP_HEADER, 'return_data': True}
			sts, data = self.cm.getPage(url, params)
			if not sts or not data:
				printDBG('FREEOMOVIE: could not fetch video page')
				return ''
			tabsMatch = re.search(r'var\s+TABS\s*=\s*(\[.*?\]);', data, re.S)
			if not tabsMatch:
				printDBG('FREEOMOVIE: no TABS array found on video page')
				return ''
			embedUrls = re.findall(r'"url"\s*:\s*"([^"]+)"', tabsMatch.group(1))
			for embedUrl in embedUrls:
				embedUrl = embedUrl.replace('\\/', '/')
				printDBG('FREEOMOVIE embed candidate: ' + embedUrl)
				videoUrls = self.getLinksForVideo(embedUrl)
				if videoUrls:
					for item in videoUrls:
						itemUrl = item.get('url', '') if isinstance(item, dict) else item
						if itemUrl:
							printDBG('FREEOMOVIE RESOLVED URL: ' + str(itemUrl))
							return itemUrl
			printDBG('FREEOMOVIE: no playable URL found in tabs')
			return ''

		return ''


def decodeUrl(text):
	replacements = {'%20': ' ', '%21': '!', '%22': '"', '%23': '&', '%24': '$', '%25': '%', '%26': '&', '%2B': '+', '%2F': '/', '%3A': ':', '%3B': ';', '%3D': '=', '&#x3D;': '=', '%3F': '?', '%40': '@'}
	for key, value in replacements.items():
		text = text.replace(key, value)
	return text


def decodeHtml(text):
	replacements = {
		'&auml;': 'ä', '\\u00e4': 'ä', '&#228;': 'ä',
		'&oacute;': 'ó', '&eacute;': 'e', '&aacute;': 'a', '&ntilde;': 'n',
		'&Auml;': 'Ä', '\\u00c4': 'Ä', '&#196;': 'Ä',
		'&ouml;': 'ö', '\\u00f6': 'ö', '&#246;': 'ö',
		'&Ouml;': 'Ö', '\\u00d6': 'Ö', '&#214;': 'Ö',
		'&uuml;': 'ü', '\\u00fc': 'ü', '&#252;': 'ü',
		'&Uuml;': 'Ü', '\\u00dc': 'Ü', '&#220;': 'Ü',
		'&szlig;': 'ß', '\\u00df': 'ß', '&#223;': 'ß',
		'&amp;': '&', '&quot;': '\"', '&quot_': '\"',
		'&gt;': '>', '&apos;': "'", '&acute;': '\'',
		'&ndash;': '-', '&bdquo;': '"', '&rdquo;': '"',
		'&ldquo;': '"', '&lsquo;': '\'', '&rsquo;': '\'',
		'&#034;': '\'', '&#038;': '&', '&#039;': '\'',
		'&#39;': '\'', '&#160;': ' ', '\\u00a0': ' ',
		'&#174;': '', '&#225;': 'a', '&#233;': 'e',
		'&#243;': 'o', '&#8211;': "-", '\\u2013': "-",
		'&#8216;': "'", '&#8217;': "'", '#8217;': "'",
		'&#8220;': "'", '&#8221;': '"', '&#8222;': ',',
		'&#x27;': "'", '&#8230;': '...', '\\u2026': '...',
		'&#41;': ')', '&lowbar;': '_', '&lpar;': '(',
		'&rpar;': ')', '&comma;': ',', '&period;': '.',
		'&plus;': '+', '&num;': '#', '&excl;': '!',
		'&#039': '\'', '&semi;': '', '&lbrack;': '[',
		'&rsqb;': ']', '&nbsp;': '', '&#133;': '',
		'&#4': '', '&#40;': '', '&atilde;': "'",
		'&colon;': ':', '&sol;': '/', '&percnt;': '%',
		'&commmat;': ' ', '&#58;': ':'}
	for key, value in replacements.items():
		text = text.replace(key, value)
	return text


def decryptHash(videoUrl, licenseCode, hashRange):
	result = ''
	videoUrlPart = videoUrl.split('/')
	hash = videoUrlPart[7][:2 * int(hashRange)]
	nonConvertHash = videoUrlPart[7][2 * int(hashRange):]
	seed = calcSeed(licenseCode, hashRange)
	if (seed != '' and hash != ''):
		for k in range(len(hash) - 1, -1, -1):
			l = k
			for m in range(k, len(hash)):
				l += int(seed[m])
			l = l % len(hash)
			n = ''
			for o in range(0, len(hash)):
				n = n + hash[l] if o == k else n + hash[k] if o == l else n + hash[o]
			hash = n
		videoUrlPart[7] = hash + nonConvertHash
		videoUrlPart.pop(0)
		videoUrlPart.pop(0)
		result = '/'.join(videoUrlPart)
	return result


def calcSeed(licenseCode, hashRange):
	f = licenseCode.replace('$', '').replace('0', '1')
	j = int(len(f) / 2)
	k = int(f[:len(f) - j])
	l = int(f[j:])
	g = abs(l - k)
	fi = 4 * g
	i = int(int(hashRange) / 2 + 2)
	m = ''
	for g2 in range(0, j + 1):
		for h in range(1, 5):
			n = int(licenseCode[g2 + h]) + int(str(fi)[g2])
			if n >= i:
				n -= i
			m = m + str(n)
	return m
