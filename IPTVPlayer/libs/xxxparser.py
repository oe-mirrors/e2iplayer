# -*- coding: utf-8 -*-
###################################################
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, byteify
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, unpackJSPlayerParams, TEAMCASTPL_decryptPlayerParams
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
import re
import base64
import math
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
	from urllib.parse import unquote
	from urllib.request import urlopen
except ImportError:
	from urllib import urlopen, unquote
from datetime import datetime
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
		if url.startswith('https://www.tropictube.com'):
			return 'https://www.tropictube.com'
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
		if url.startswith('https://pornxp.org'):
			return 'https://pornxp.org'
		if url.startswith('https://pornoflix.com'):
			return 'https://pornoflix.com'
		if url.startswith('https://www.freepornhq.xxx'):
			return 'https://www.freepornhq.xxx'
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
		if url.startswith('https://www.amateurporn.'):
			return 'https://www.amateurporn.me'
		if url.startswith(('https://emturbovid.com', 'https://www.turbovid.com')):
			return 'https://emturbovid.com'
		if url.startswith('https://sex3.com'):
			return 'https://sex3.com'
		if url.startswith('https://www.porntube.com'):
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
		if url.startswith('https://glavmatures.com'):
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
		if url.startswith(('https://motherless.com', 'https://www.motherless.com')):
			return 'https://motherless.com'
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
			return 'https://yourporn.sexy'
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
		if url.startswith('https://sinparty.com'):
			return 'https://sinparty.com'
		if url.startswith('https://vidlox.tv'):
			return 'https://vidlox.tv'
		if url.startswith('http://pornvideos4k.com/en'):
			return 'http://pornvideos4k.com/en'
		if url.startswith('https://www.watchmygf.me'):
			return 'https://mangovideo'
		# NEWEST PARSERS
		if 'mix-porn' in url or 'mixporn' in url:
			return 'https://rusporn.tv'
		if url.startswith(('https://www.slutsxmovies.com/embed/', 'https://www.cumyvideos.com/embed/', 'https://www.nuvid.com', 'https://porneo.com')):
			return 'https://www.nuvid.com'
		if url.startswith(('https://hornygorilla.com', 'https://www.sleazyneasy.com', 'https://www.5fing.com', 'https://www.sheshaft.com')):
			return 'file: '
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
		if url.startswith(('https://www.pornstep.com', 'https://www.xfig.net')):
			return 'videoFile="'
		if url.startswith(('https://www.clipcake.com', 'https://www.cliplips.com', 'https://www.vid2c.com', 'https://www.bonertube.com')):
			return 'videoFile="'
		if url.startswith('https://hellmoms.com/'):
			return 'https://xbabe.com'
		if url.startswith('https://streamtape.com'):
			return 'xxxlist.txt'
		if url.startswith('https://filemoon.sx'):
			return 'https://filemoon.sx'
		if url.startswith((
			'https://doodstream.com', 'https://www.doodstream.com', 'https://dood.pm',
			'https://dood.la', 'https://www.dood.la', 'https://www.dood.pm',
			'https://dood.re', 'https://www.dood.re', 'https://d000d.com'
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
		if url.startswith('https://www.pornburst.xxx/'):
			return 'https://www.pornburst.xxx/'
		if url.startswith('https://www.xxxbule.com/'):
			return 'https://www.xxxbule.com/'
		if url.startswith('https://www.porndig.com'):
			return 'https://www.porndig.com'
		if url.startswith('https://www.filmyporno.tv'):
			return 'https://www.filmyporno.tv'
		if url.startswith(('https://www.firstanalvideos.com/', 'https://www.deviants.com', 'http://pornbimbo.com', 'http://www.pornfd.com', 'https://www.punishbang.com', 'https://www.pornwhite.com', 'https://www.wankoz.com', 'https://xcafe.com', 'https://www.boundhub.com', 'https://shameless.com', 'https://www.amateur8.com/', 'https://www.xozilla.com', 'https://xozilla.com', 'https://www.ohsexfilm.com', 'https://www.mature-amateur-sex.com', 'https://thepornarea.com', 'https://topvids.net', 'https://camstreams.tv/', 'https://www.momslust.com', 'https://porn2all.com', 'https://in35.com', 'https://www.camvideos.tv', 'https://www.shemalehd.sex', 'https://mrdeepfakes.com', 'https://jizzboom.com', 'https://www.javbangers.com', 'https://www.sunporno.com', 'https://www.ebony8.com', 'https://nudez.com', 'https://severeporn.com', 'https://neporn.com')):
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

		# Test mjpg
		if url.endswith(('.mjpg', '.cgi')):
			return 'mjpg_stream'
		# URLPARSER
		if url.startswith((
			'https://gounlimited.to', 'https://openload.co', 'https://oload.tv',
			'https://www.cda.pl', 'https://hqq.tv', 'https://hqq.to',
			'https://www.rapidvideo.com', 'https://videomega.tv', 'https://www.flashx.tv',
			'https://streamcloud.eu', 'https://thevideo.me', 'https://vidoza.net',
			'https://fileone.tv', 'https://streamcherry.com', 'https://vk.com',
			'https://www.fembed.com'
		)) or self.MAIN_URL in [
			'https://www.freeomovie.to/',
			'https://streamporn.pw',
			'https://streamporn.org',
			'https://streamporn.vip',
			'https://www.xxxstreams.org',
			'https://pandamovie.info',
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

		if self.MAIN_URL == 'https://xhamsterlive.com':
			return 'https://xhamster.com/cams'
		if self.MAIN_URL == 'https://www.porntube.com':
			return 'https://www.4tube.com'

		if url.startswith('https://www.cuckoldplacetube.com'):
			return 'https://www.cuckoldplacetube.com'
		if url.startswith('https://baddies.xxx'):
			return 'https://baddies.xxx'
		if url.startswith('https://www.amazingcuckold.com'):
			return 'https://www.amazingcuckold.com'

		if url.startswith('https://www.beautymovies.com'):
			return 'https://www.beautymovies.com'
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
		if url.startswith('https://young-sex-tube.com'):
			return 'https://young-sex-tube.com'
		if url.startswith('https://javteentube.com'):
			return 'https://javteentube.com'
		if url.startswith('https://pornvideosbest.com'):
			return 'https://pornvideosbest.com'
		if url.startswith('https://www.mature-girls.com'):
			return 'https://www.mature-girls.com'
		if url.startswith('https://www.oriental-sex.com'):
			return 'https://www.oriental-sex.com'
		if url.startswith('https://69teentube.com'):
			return 'https://69teentube.com'
		if url.startswith('http://www.wifevideos.net'):
			return 'http://www.wifevideos.net'
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
		if url.startswith('https://porndreamz.com'):
			return 'https://porndreamz.com'
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
		if url.startswith('https://smutr.com'):
			return 'https://smutr.com'
		if url.startswith('https://hqfap.com'):
			return 'https://hqfap.com'
		if url.startswith('https://naijapornsite.com'):
			return 'https://naijapornsite.com'
		if url.startswith('https://www.nuvid.com'):
			return 'https://www.nuvid.com'
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
		if url.startswith('http://www.pornrox.com'):
			return 'https://www.alohatube.com'
		if url.startswith('https://anyporn.com'):
			return 'https://anyporn.com'
		if url.startswith('https://anysex.com/'):
			return 'https://anysex.com/'
		if url.startswith('http://www.flyflv.com'):
			return 'http://www.flyflv.com'
		if url.startswith('http://www.xtube.com'):
			return 'https://vidlox.tv'
		if url.startswith('http://xxxkingtube.com'):
			return 'http://xxxkingtube.com'
		if url.startswith('http://www.boyfriendtv.com'):
			return 'source src="'
		if url.startswith('http://pornxs.com'):
			return 'http://pornxs.com'
		if url.startswith('http://pornsharing.com'):
			return 'http://pornsharing.com'
		if url.startswith('http://www.vivatube.com'):
			return 'http://vivatube.com'
		if url.startswith('https://www.empflix.com'):
			return 'https://www.empflix.com'
		if url.startswith('https://www.camwhoresbay.com'):
			return 'https://www.camwhoresbay.com'
		if url.startswith('https://tik.porn'):
			return 'https://tik.porn'
		if url.startswith('https://teenager365.to'):
			return 'https://teenager365.to'

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
		# printDBG('video page: ' + data)
		EmbedUrl = self.cm.ph.getSearchGroups(data, '''embedUrl":.["']([^"^']+?)["]''', 1, True)[0]
		printDBG('Embed URL: ' + EmbedUrl)
		EmbedUrl = checkhttps(EmbedUrl)
		sts, data = self.get_Page(EmbedUrl)
		if not sts:
			return ''
		# printDBG('Final DATA: ' + data)
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
		if 'clipwatching.com' in url and 'embed' not in url:
			video_id = self.cm.ph.getSearchGroups(url, 'clipwatching.com/([A-Za-z0-9]{12})[/.-]')[0]
			url = 'http://clipwatching.com/embed-{0}.html'.format(video_id)

		if parser == 'mjpg_stream':
			try:
				stream = urlopen(url)
				_bytes = ''
				while True:
					_bytes += stream.read(1024)
					a = _bytes.find('\xff\xd8')
					b = _bytes.find('\xff\xd9')
					if a != -1 and b != -1:
						jpg = _bytes[a:b + 2]
						_bytes = _bytes[b + 2:]
						with open('/tmp/obraz.jpg', 'w') as titleFile:
							titleFile.write(jpg)
							return 'file:///tmp/obraz.jpg'
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
			printDBG('PORNTREX PARSERDATA: ' + str(data))
			if 'video is a private' in data:
				SetIPTVPlayerLastHostError(_(' This video is a private.'))
				return []
			if self.format4k:
				videoPage = self.cm.ph.getSearchGroups(data, '''video_alt_url5: ['"]([^"^']+?)['"]''')[0]
				if videoPage:
					printDBG('Host videoPage video_alt_url5 4k: ' + videoPage)
					return strwithmeta(videoPage, {'Referer': url})
				videoPage = self.cm.ph.getSearchGroups(data, '''video_alt_url4: ['"]([^"^']+?)['"]''')[0]
				if videoPage:
					printDBG('Host videoPage video_alt_url4 High HD: ' + videoPage)
					return strwithmeta(videoPage, {'Referer': url})
				videoPage = self.cm.ph.getSearchGroups(data, '''video_alt_url3: ['"]([^"^']+?)['"]''')[0]
				if videoPage:
					printDBG('Host videoPage video_alt_url3 Full High: ' + videoPage)
					return strwithmeta(videoPage, {'Referer': url})
			videoPage = self.cm.ph.getSearchGroups(data, '''video_alt_url2: ['"]([^"^']+?)['"]''')[0]
			if videoPage:
				printDBG('Host videoPage video_alt_url2 HD: ' + videoPage)
				return strwithmeta(videoPage, {'Referer': url})
			videoPage = self.cm.ph.getSearchGroups(data, '''video_alt_url: ['"]([^"^']+?)['"]''')[0]
			if videoPage:
				printDBG('Host videoPage video_alt_url Medium: ' + videoPage)
				return strwithmeta(videoPage, {'Referer': url})
			videoPage = self.cm.ph.getSearchGroups(data, '''video_url: ['"]([^"^']+?)['"]''')[0]
			if videoPage:
				printDBG('Host videoPage video_url Low: ' + videoPage)
				return strwithmeta(videoPage, {'Referer': url})
			return ''

		if parser == 'https://www.pornoxo.com':
			printDBG('PORNOXO PARSER STARTED')
			COOKIEFILE = join(GetCookieDir(), 'pornoxo.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornoxo.cookie', 'pornoxo.com', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search('sources.{,6}src":"([^"]+)","d', data).group(1)
			videoUrl = videoUrl.replace(r'\/', '/')
			printDBG('Link a video: ' + str(videoUrl))
			return unquote(videoUrl)

		if parser == 'https://www.hclips.com':
			COOKIEFILE = join(GetCookieDir(), 'hclips.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'hclips.cookie', 'hclips.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + data)
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
			printDBG('data: ' + data)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''sources.+?['"]([^"^']+?)['"].+?,''')[0]
			printDBG('End Link: ' + str(videoUrl))
			return videoUrl

		if parser == 'http://pornvideos4k.com/en':
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
			# printDBG('Host listsItems data: ' + data)
			videoUrl = ph.search(data, '''video_url":"([^"]+?)"''')[0]
			replacemap = {'M': '\\u041c', 'A': '\\u0410', 'B': '\\u0412', 'C': '\\u0421', 'E': '\\u0415', '=': '~', '+': '.', '/': ','}
			for key in replacemap:
				videoUrl = videoUrl.replace(replacemap[key], key)
			videoUrl = base64.b64decode(videoUrl)
			printDBG('After decoding: ' + str(videoUrl))
			videoUrl = str(videoUrl).replace("b'", "")
			printDBG('After repair: ' + str(videoUrl))
			videoUrl = checkhttps(videoUrl)
			if videoUrl.startswith('/'):
				videoUrl = 'https://tubepornclassic.com' + videoUrl
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.hdzog.com':
			COOKIEFILE = join(GetCookieDir(), 'hdzog.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'hdzog.cookie', 'hdzog.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + str(data))
			posturl = 'https://%s/sn4diyux.php' % url.split('/')[2]
			pC3 = re.search('''pC3:'([^']+)''', data)
			if not pC3:
				return ''
			pC3 = pC3.group(1)
			vidid = re.search(r'''video_id["|']?:\s?(\d+)''', data).group(1)
			postdata = '%s,%s' % (vidid, pC3)
			sts, data = self.getPage(posturl, 'hclips.cookie', 'hclips.com', self.defaultParams, post_data={'param': postdata})
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + str(data))
			videoUrl = re.search('video_url":"([^"]+)', data).group(1)
			printDBG('Host videoUrl:%s' % videoUrl)
			replacemap = {'M': '\\u041c', 'A': '\\u0410', 'B': '\\u0412', 'C': '\\u0421', 'E': '\\u0415', '=': '~', '+': '.', '/': ','}
			for key in replacemap:
				videoUrl = videoUrl.replace(replacemap[key], key)
			videoUrl = base64.b64decode(videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.alohatube.com':
			COOKIEFILE = join(GetCookieDir(), 'alohatube.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'alohatube.cookie', 'alohatube.com', self.defaultParams)
			if not sts:
				return ''
			printDBG('Video data: ' + url)
			if 'pornrox.com' in url:
				videoUrl = self.cm.ph.getDataBeetwenMarkers(data, '"contentUrl": "', '"', False)[1]
				videoUrl = videoUrl.replace(r'\/', '/')
				printDBG('Pornrox Link:' + videoUrl)
				return videoUrl
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

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
			# printDBG('Host getResolvedURL data: ' + data)
			parse = re.search("var srvE = '(.*?)'", data, re.S)
			if parse:
				printDBG('Host Url: ' + url)
				printDBG('Host rtmp: ' + parse.group(1))
				rtmp = parse.group(1)
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
				zapytanie = zapytanie.decode("utf-8")
				printDBG('Host zapytanie1: ' + zapytanie)
				ws.send(zapytanie)
				result = ws.recv()
				printDBG('Host result1: ' + result)

				zapytanie = '{ "id": 2, "value": ["%s"]}' % modelName
				zapytanie = zapytanie.decode("utf-8")
				printDBG('Host zapytanie2: ' + zapytanie)
				ws.send(zapytanie)
				result = ws.recv()
				printDBG('Host result2: ' + result)

				playpath = re.search(r'value":\["(.*?)"', result)

				if playpath:
					Checksum = playpath.group(1)
					if len(Checksum) < 30:
						for x in range(1, 10):
							ws.send(zapytanie)
							result = ws.recv()
							czas = re.search(r'(\d+)\[:\](\d+)\[', result)
							if czas:
								printDBG('Host czas.group(1): ' + czas.group(1))
								printDBG('Host czas.group(2): ' + czas.group(2))
								czas = int(czas.group(1)) - int(czas.group(2))
								printDBG('Host a: ' + str(czas))
								a = str(czas)
								if a == '0':
									a = 'kilka'
								Checksum = 'PRIVATE - Czekaj ' + a + ' sekund'
								break
						if Checksum == '' or Checksum == 'failure':
							Checksum = 'OFFLINE'
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

		if parser == 'https://hellporno.com/':
			COOKIEFILE = join(GetCookieDir(), 'hellporno.cookie')
			self.cm.HEADER = {'User-Agent': self.cm.getDefaultHeader()['User-Agent'], 'X-Requested-With': 'XMLHttpRequest'}
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.get_Page(url)
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
			return self._parse_embedUrl(url, 'porn7.cookie')

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
			printDBG('First videolink: ' + videoUrl)
			if '.m3u8' in videoUrl:
				if self.cm.isValidUrl(videoUrl):
					tmp = getDirectM3U8Playlist(videoUrl)
					for item in tmp:
						printDBG('Host listsItems valtab: ' + str(item))
						return item['url']
			printDBG('Final videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.tropictube.com':
			COOKIEFILE = join(GetCookieDir(), 'tropictube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			if '?' in url:
				url = url.rpartition('?')[0]
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_src.{2,6}=['"](.+?)['"]''', 1, True)[0]
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
			videoUrl = re.search('source.src=["]([^$]+?)["].*mp4', data).group(1)
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
			videoUrl = re.findall("source.src=[']([^$]+?)['].*mp4", data, re.S)
			if videoUrl:
				videoUrl = videoUrl[-1]
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
			printDBG('MAIN URL: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://www.freepornhq.xxx':
			COOKIEFILE = join(GetCookieDir(), 'freepornhq.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			printDBG('FREEPORNHQ PARSER URL: ' + url)
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search('source.src=["]([^$]+?)["].*mp4', data).group(1)
			printDBG('MAIN URL: ' + str(videoUrl))
			return videoUrl

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
			printDBG('Video page: ' + data)
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
			printDBG('PORNBOLT Video page: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"](.+?)['"].{10,16}mp4''', 1, True)[0]
			printDBG('Final videolink: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.wetsins.com':
			COOKIEFILE = join(GetCookieDir(), 'uniparser.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			printDBG('WETSINS and PORNENIX Video page: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''Quality.*src=['"](.+?)['"].{10,16}mp4''', 1, True)[0]
			if not videoUrl:
				EmbedUrl = self.cm.ph.getSearchGroups(data, '''iframe.{1,20}src=['"](.+?)['"]''', 1, True)[0]
				sts, data2 = self.get_Page(EmbedUrl)
				if not sts:
					return ''
				printDBG('Final DATA: ' + data2)
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
			printDBG('PORNOHAMMER Video page: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"](.+?)['"].{10,16}mp4''', 1, True)[0]
			if not videoUrl:
				EmbedUrl = self.cm.ph.getSearchGroups(data, '''iframe.src=&quot[;](.+?)[&]quot''', 1, True)[0]
				sts, data2 = self.get_Page(EmbedUrl)
				if not sts:
					return ''
				printDBG('Final DATA: ' + data2)
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
			printDBG('XGROOVY Video page: ' + data)
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
			printDBG('video page: ' + data)
			match = re.findall('src=["]([^"]+?)["].type', data, re.S)
			if match:
				return match[0]
			else:
				printDBG('Found nothing.')

		if parser == 'https://www.camsoda.com/':
			if 'rtmp' in url:
				rtmp = 1
			else:
				rtmp = 0
			url = url.replace('rtmp', '')
			query_data = {'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
			try:
				data = self.cm.getURLRequestData(query_data)
			except Exception:
				printDBG('Host getResolvedURL query error url: ' + url)
				return ''
			dane = '[' + data + ']'
			result = json.loads(dane)
			if result:
				try:
					for item in result:
						token = str(item["token"])
						app = str(item["app"])
						serwer = str(item["edge_servers"][0])
						stream_name = str(item["stream_name"])
						name = re.sub('-enc.+', '', stream_name)
						if rtmp == 0:
							Url = 'https://%s/%s/mp4:%s_aac/playlist.m3u8?token=%s' % (serwer, app, stream_name, token)
							Url = urlparser.decorateUrl(Url, {'User-Agent': USER_AGENT})
							if self.cm.isValidUrl(Url):
								tmp = getDirectM3U8Playlist(Url)
								for item in tmp:
									if str(item["with"]) == '0':
										SetIPTVPlayerLastHostError(' OFFLINE')
										return []
									return item['url']
							SetIPTVPlayerLastHostError(' OFFLINE')
							return []
						else:
							Url = 'rtmp://%s:1935/%s?token=%s/ playpath=?mp4:%s swfUrl=https://www.camsoda.com/lib/video-js/video-js.swf live=1 pageUrl=https://www.camsoda.com/%s' % (serwer, app, token, stream_name, name)
							return Url
				except Exception:
					printExc()
			return ''

		if parser == 'xxxlist.txt':
			videoUrls = self.getLinksForVideo(url)
			if videoUrls:
				for item in videoUrls:
					Url = item['url']
					Name = item['name']
					printDBG('Host url: ' + Url)
					return Url
			return ''

		if parser == 'https://xhamster.com/cams':
			config = 'https://xhamsterlive.com/api/front/config'
			COOKIEFILE = join(GetCookieDir(), 'xhamsterlive.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(config)
			if not sts:
				return ''
			printDBG('Host listsItems data1: ' + data)
			parse = re.search('"sessionHash":"(.*?)"', data, re.S)
			if not parse:
				return ''
			sessionHash = parse.group(1)
			printDBG('Host sessionHash: ' + sessionHash)

			models = 'https://xhamsterlive.com/api/front/models'
			COOKIEFILE = join(GetCookieDir(), 'xhamsterlive.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(models)
			if not sts:
				return ''
			printDBG('Host listsItems data2: ' + data)
			result = json.loads(data)
			try:
				for item in result["models"]:
					ID = str(item["id"])
					Name = item["username"]
					BroadcastServer = item["broadcastServer"]
					swf_url = 'https://xhamsterlive.com/assets/cams/components/ui/Player/player.swf?bgColor=2829099&isModel=false&version=1.5.892&bufferTime=1&camFPS=30&camKeyframe=15&camQuality=85&camWidth=640&camHeight=480'
					Url = 'rtmp://b-eu10.stripcdn.com:1935/%s?sessionHash=%s&domain=xhamsterlive.com playpath=%s swfUrl=%s pageUrl=https://xhamsterlive.com/cams/%s live=1 ' % (BroadcastServer, sessionHash, ID, swf_url, Name)
					Url = 'rtmp://b-eu10.stripcdn.com:1935/%s?sessionHash=%s&domain=xhamsterlive.com playpath=%s swfVfy=%s pageUrl=https://xhamsterlive.com/cams/%s live=1 ' % (BroadcastServer, sessionHash, ID, swf_url, Name)
					if ID == url:
						return urlparser.decorateUrl(Url, {'Referer': 'https://xhamsterlive.com/cams/' + Name, 'iptv_livestream': True})
			except Exception:
				printExc()
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
				printDBG('HLS DATA: ' + data)
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
			printDBG('Links for the video: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''videoUrl.+?['"]([^"^']+?)['"]''')[0].replace('%3D', '=').replace(r"\/", "/")
			printDBG('Ready link: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.4tube.com':
			COOKIEFILE = join(GetCookieDir(), '4tube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			if url.startswith('https://www.porntube.com'):
				self.HTTP_HEADER['Origin'] = 'https://www.porntube.com'
			self.HTTP_HEADER['Referer'] = url

			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + data)
			domena = url.split('/')[2].replace('www.', '')
			printDBG('Host domain: ' + domena)

			videoID = re.findall(r'data-id="(\d+)".*?data-quality="(\d+)"', data, re.S)
			try:
				init = self.cm.ph.getSearchGroups(data, r'''window.INITIALSTATE\s*?=\s*?['"]([^"^']+?)['"]''', 1, True)[0]
				init = unquote(base64.b64decode(init))
				try:
					result = byteify(json.loads(init)["page"])
				except Exception:
					printExc()
					result = byteify(json.loads(data))
				videoID = result["video"]["mediaId"]
				res = ''
				for item in result["video"]["encodings"]:
					res += str(item["height"]) + "+"
				res.strip('+')
				posturl = "https://token.%s/0000000%s/desktop/%s" % (domena, videoID, res)
				printDBG('Host getResolvedURL posturl: ' + posturl)
				sts, data = self.get_Page(posturl)
				if not sts:
					return ''
				printDBG('Host getResolvedURL posturl data1: ' + data)
				videoUrl = re.findall('token":"(.*?)"', data, re.S)
				if videoUrl:
					return videoUrl[-2]
			except Exception:
				printExc()
			if videoID:
				res = ''
				for x in videoID:
					res += x[1] + "+"
				res.strip('+')
				posturl = "https://token.%s/0000000%s/desktop/%s" % (domena, videoID[-1][0], res)
				printDBG('Host getResolvedURL posturl: ' + posturl)
				sts, data = self.get_Page(posturl)
				if not sts:
					return ''
				printDBG('Host getResolvedURL posturl data2: ' + data)
				videoUrl = re.findall('token":"(.*?)"', data, re.S)
				if videoUrl:
					return videoUrl[-2]
				else:
					return ''
			return ''

		if parser == 'https://zbporn.com':
			COOKIEFILE = join(GetCookieDir(), 'zbporn.cookie')
			header = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
			try:
				data = self.cm.getURLRequestData({'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True})
			except Exception:
				printDBG('Host getResolvedURL query error url: ' + url)
				return ''
			# printDBG('Host getResolvedURL data: ' + data)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, "video_url: '", "',", False)[1]
			return videoUrl

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

		if parser == 'https://yourporn.sexy':
			def ssut51(str):
				str = re.sub(r'\D', '', str)
				sut = 0
				for i in range(0, len(str)):
					sut += int(str[i])
				return sut

			for x in range(1, 99):
				COOKIEFILE = join(GetCookieDir(), 'yourporn.cookie')
				self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
				self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
				self.defaultParams['header']['Origin'] = 'https://sxyprn.com'
				sts, data = self.getPage(url, 'yourporn.cookie', 'sxyprn.com', self.defaultParams)
				if not sts:
					return ''
				videoUrl = self.cm.ph.getSearchGroups(data, '''data-vnfo=['"].*?:['"]([^"^']+?)['"]''')[0].replace(r"\/", r"/")
				if videoUrl:
					printDBG('Host listsItems videoUrl: ' + videoUrl)
					videoUrl = checkhttp(videoUrl)
					if videoUrl.startswith('/'):
						videoUrl = 'https://sxyprn.com' + videoUrl
					try:
						match = re.search('src="(/js/main[^"]+)"', data, re.DOTALL | re.IGNORECASE)
						if match.group(1).startswith('/'):
							result = 'https://sxyprn.com' + match.group(1)
						sts, jsscript = self.getPage(result, 'yourporn.cookie', 'sxyprn.com', self.defaultParams)
						replaceint = re.search(r'tmp\[1\]\+= "(\d+)";', jsscript, re.DOTALL | re.IGNORECASE).group(1)
						videoUrl = videoUrl.replace('/cdn/', '/cdn%s/' % replaceint)
					except Exception:
						if '/cdn/' in videoUrl:
							videoUrl = videoUrl.replace('/cdn/', '/cdn' + str(self.yourporn) + '/')
					videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'Origin': 'https://sxyprn.com'})
					tmp = videoUrl.split('/')
					a = str(int(tmp[-3]) - ssut51(re.sub(r'\D', '', tmp[-2])) - ssut51(re.sub(r'\D', '', tmp[-1])))
					if int(a) > 0:
						tmp[-3] = a
					else:
						tmp[-3] = str(int(tmp[-3]) - 101)
					videoUrl = '/'.join(tmp)
				self.defaultParams['max_data_size'] = 0
				sts, data = self.getPage(videoUrl, 'yourporn.cookie', 'sxyprn.com', self.defaultParams)
				if not sts:
					return ''
				if 'sxyprn' not in data.meta['url']:
					return data.meta['url']
			return ''

		if parser == 'https://streamvid.net':
			COOKIEFILE = join(GetCookieDir(), 'streamvid.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			url = url.replace('https://streamvid.net/', 'https://streamvid.net/embed-')
			printDBG('Streamvid cim: ' + url)
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
			printDBG('Szerver: ' + server)
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
					tmp = getDirectM3U8Playlist(videoUrl)
					for item in tmp:
						printDBG('Host listsItems valtab: ' + str(item))
						return item['url']
			printDBG('Final URL: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.amdahost.com':
			COOKIEFILE = join(GetCookieDir(), 'amdahost.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			printDBG('AMDAHOST cim: ' + url)
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
							newUrl = urlparser.decorateUrl(newUrl, {'Referer': baseUrl, 'external_sub_tracks': subTracks})
						else:
							newUrl = urlparser.decorateUrl(newUrl, {'Referer': baseUrl})
						params = {'name': 'link', 'url': newUrl}
						urlsTab.append(params)
			return urlsTab

		if parser == 'https://www.playvids.com':
			COOKIEFILE = join(GetCookieDir(), 'playvids.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'playvids.cookie', 'playvids.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + str(data))
			videoUrl = self.cm.ph.getSearchGroups(data, '''hls-src720=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if '' == videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''hls-src480=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if '' == videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''hls-src360=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				return self.FullUrl(videoUrl)

			videoUrl = self.cm.ph.getSearchGroups(data, '''src720=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				return self.FullUrl(videoUrl)
			videoUrl = self.cm.ph.getSearchGroups(data, '''src480=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				return self.FullUrl(videoUrl)
			videoUrl = self.cm.ph.getSearchGroups(data, '''src360=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			return self.FullUrl(videoUrl) if videoUrl else ''

		if parser == 'https://www.tubewolf.com':
			COOKIEFILE = join(GetCookieDir(), 'tubewolf.cookie')
			for x in range(1, 10):
				self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
				self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
				sts, data = self.get_Page(url)
				if not sts:
					return ''
				# printDBG('Host listsItems data: ' + data)
				data = self.cm.ph.getDataBeetwenMarkers(data, '<video id', '</video>', False)[1]
				videoUrl = re.findall(r'<source\ssrc="(.*?)"', data, re.S)
				if videoUrl:
					return videoUrl[-1]

		if parser == 'https://streamate.com':
			COOKIEFILE = join(GetCookieDir(), 'streamate.cookie')
			url = 'https://streamate.com/blacklabel/hybrid/?name={}&lang=en&manifestUrlRoot=https://sea1c-ls.naiadsystems.com/sea1c-edge-ls/80/live/s:'.format(url)
			query_data = {'url': url, 'use_host': False, 'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True}
			try:
				data = self.cm.getURLRequestData(query_data)
			except Exception:
				printExc()
				printDBG('Host listsItems query error url:' + url)
				return ''
			# printDBG('Host listsItems data: ' + data)
			url = self.cm.ph.getSearchGroups(data, '''data-manifesturl=['"]([^"^']+?)['"]''')[0]
			header = {'Referer': 'https://streamate.com', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
			query_data = {'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True}
			try:
				data = self.cm.getURLRequestData(query_data)
			except Exception:
				printExc()
				printDBG('Host listsItems query error url:' + url)
				return ''
			printDBG('Host listsItems data2: ' + data)
			try:
				videoinfo = json.loads(data)
				videoUrl = videoinfo['formats']['mp4-hls']['manifest']
				videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': 'https://streamate.com', 'iptv_livestream': True})
				if '.m3u8' in videoUrl and self.cm.isValidUrl(videoUrl):
					for item in getDirectM3U8Playlist(videoUrl):
						printDBG('Host listsItems valtab: ' + str(item))
						return item['url']
				return videoUrl
			except Exception:
				printExc()
			return ''

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

		if parser == 'https://www.ashemaletube.com':
			COOKIEFILE = join(GetCookieDir(), 'ASHEMALETUBE.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'ASHEMALETUBE.cookie', 'ashemaletube.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + data)
			if 'sources: ' in data:
				try:
					sources = self.cm.ph.getDataBeetwenMarkers(data, 'sources: ', ']', False)[1]
					result = byteify(json.loads(sources + ']'))
					for item in result:
						if str(item["desc"]) == '720p' and str(item["active"]) == 'true':
							return str(item["src"])
						if str(item["desc"]) == '480p' and str(item["active"]) == 'true':
							return str(item["src"])
						if str(item["desc"]) == '360p' and str(item["active"]) == 'true':
							return str(item["src"])
				except Exception:
					printExc()
			videoUrl = self.cm.ph.getSearchGroups(data, '''source src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return videoUrl

			if 'To watch this video please' in data:
				SetIPTVPlayerLastHostError(_(' Login Protected.'))
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

		if parser == 'https://www.pornburst.xxx/':
			COOKIEFILE = join(GetCookieDir(), 'pornburst.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self._getPage(url, self.defaultParams)
			if not sts:
				return
			printDBG('Host listItems data: ' + str(data))
			videoUrl = self.cm.ph.getSearchGroups(data, r'''src=['"]([^"^']+?)['"].type="video\/mp4''')[0]
			return videoUrl if videoUrl else ''

		if parser == 'https://www.xxxbule.com/':
			COOKIEFILE = join(GetCookieDir(), 'xxxbule.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self._getPage(url, self.defaultParams)
			if not sts:
				return
			printDBG('Host listItems data: ' + str(data))
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_src".href=['"]([^"^']+?)['"]./>''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''contentUrl":.['"]([^"^']+?)['"]''')[0]
			return videoUrl if videoUrl else ''

		if parser == 'https://www.filmyporno.tv':
			COOKIEFILE = join(GetCookieDir(), 'filmyporno.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			printDBG('FILMYPORNO PARSERDATA: ' + data)
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
			videoLinks = self.cm.ph.getDataBeetwenMarkers(data, '<div class="video_actions_wrapper', 'full video', False)[1]
			printDBG('Total data: ' + str(videoLinks))
			videoLinks = self.cm.ph.getAllItemsBeetwenMarkers(videoLinks, 'href="', '" class', False)
			self.cm.ph.getAllItemsBeetwenMarkers
			printDBG('Links: ' + str(videoLinks))
			videoUrl = videoLinks[-2]
			printDBG('Kesz link: ' + str(videoUrl))
			return videoUrl if videoUrl else ''

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
			# printDBG('Host listsItems data: ' + str(data))
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
			# printDBG('Host listsItems data: ' + str(data))
			xml = self.cm.ph.getSearchGroups(data, '''flashvars.config.*?//([^"^']+?)['"]''')[0]
			if not xml:
				xml = self.cm.ph.getSearchGroups(data, '''name="config".*?//([^"^']+?)['"]''')[0]
			if xml:
				videoUrl = "https://" + xml
				sts, data = self.get_Page(videoUrl, self.defaultParams)
				if not sts:
					return
				printDBG('Host listsItems data2: ' + str(data))
				url = re.findall('<videoLink>.*?//(.*?)(?:]]>|</videoLink>)', data, re.S)
				if url:
					return "https://" + url[-1].replace('&amp;', '&')
			return ''

		if parser == 'https://www.pinflix.com':
			COOKIEFILE = join(GetCookieDir(), 'pinflix.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pinflix.cookie', 'pinflix.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + str(data))
			videoUrl = self.cm.ph.getSearchGroups(data, '''preload".href=['"]([^"^']+?)['"].as="fetch" crossorigin>''')[0]
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://www.pornhd.com':
			COOKIEFILE = join(GetCookieDir(), 'pornhd.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornhd.cookie', 'pornhd.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + str(data))
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

		if parser == 'https://www.adulttvlive.net':
			COOKIEFILE = join(GetCookieDir(), 'adulttv.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'adulttv.cookie', 'adulttv.net', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data1: ' + data)

			videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"](https://adult-channels.com/channels/[^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"](https://www.adulttvlive.net[^"^']+?embed/)['"]''')[0]

			sts, data = self.getPage(videoUrl, 'adulttv.cookie', 'adulttv.net', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data2: ' + data)
			if 'porndig' in data:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''')[0]
				return self.getResolvedURL(videoUrl)

			if 'unescape' in data:
				data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'eval(', ');', False)
				try:
					ddata = ''
					for idx in range(len(data)):
						tmp = data[idx].split('+')
						for item in tmp:
							item = item.strip()
							if item.startswith("'") or item.startswith('"'):
								ddata += self.cm.ph.getSearchGroups(item, '''['"]([^'^"]+?)['"]''')[0]
							else:
								tmp2 = self.RE_UNESCAPE.findall(item)
								for item2 in tmp2:
									ddata += unquote(item2)
					printDBG('Host listsItems ddata2: ' + ddata)
					sp = self.cm.ph.getSearchGroups(ddata, r'''split\(\s*['"]([^'^"]+?)['"]''')[0]
					modStr = self.cm.ph.getSearchGroups(ddata, r'''\+\s*['"]([^'^"]+?)['"]''')[0]
					modInt = int(self.cm.ph.getSearchGroups(ddata, r'''\+\s*(-?[0-9]+?)[^0-9]''')[0])
					ddata = self.cm.ph.getSearchGroups(ddata, r'''document\.write[^'^"]+?['"]([^'^"]+?)['"]''')[0]
					data = ''
					tmp = ddata.split(sp)
					ddata = unquote(tmp[0])
					k = unquote(tmp[1] + modStr)
					for idx in range(len(ddata)):
						data += chr((int(k[idx % len(k)]) ^ ord(ddata[idx])) + modInt)
					# printDBG('host data2: ' + data)
					if 'rtmp://' in data:
						rtmpUrl = self.cm.ph.getDataBeetwenMarkers(data, '&source=', '&', False)[1]
						if rtmpUrl == '':
							rtmpUrl = self.cm.ph.getSearchGroups(data, r'''['"](rtmp[^"^']+?)['"]''')[0]
						return rtmpUrl
					elif '.m3u8' in data:
						file = self.cm.ph.getSearchGroups(data, r'''['"](http[^"^']+?\.m3u8[^"^']*?)['"]''')[0]
						if file == '':
							file = self.cm.ph.getDataBeetwenMarkers(data, 'src=', '&amp;', False)[1]
						return file
				except Exception:
					printExc()
			videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				link = self.cm.ph.getSearchGroups(data, '''streamer":['"]([^"^']+?)['"]''')[0].replace(r"\/", r"/")
				return 'https://www.filmon.com' + link
			if not videoUrl:
				return ''
			sts, data = self.getPage(videoUrl, 'adulttv.cookie', 'adulttv.net', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data3: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, r'''sources:\[\{file:['"]([^"^']+?)['"]''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''source:['"]([^"^']+?)['"]''', 1, True)[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''file:['"]([^"^']+?)['"]''', 1, True)[0]
			return videoUrl

		if parser == 'https://www.balkanjizz.com':
			COOKIEFILE = join(GetCookieDir(), 'balkanjizz.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''', 1, True)[0]
			if videoUrl.startswith('/'):
				data = 'https://www.balkanjizz.com' + videoUrl
			return data

		if parser == 'https://pornorussia.mobi':
			COOKIEFILE = join(GetCookieDir(), 'pornorussia.cookie')
			for x in range(1, 10):
				sts, data = self.getPage(url, 'pornorussia.cookie', 'pornorussia.mobi', self.defaultParams)
				if not sts:
					return ''
				# printDBG('data: ' + data)
				videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'file:"', '"', False)[1]
				printDBG('Link: ' + videoUrl)
				if videoUrl:
					return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})
			return ''

		if parser == 'https://www.gotporn.com':
			COOKIEFILE = join(GetCookieDir(), 'gotporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.cm.getPage(url)
			baseUrl = self.cm.meta['url']
			printDBG('Shared: ' + baseUrl)
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
			if 'eporner' in baseUrl:
				videoID = self.cm.ph.getSearchGroups(data, '''720p.HD:<a href=['"]([^"^']+?)['"]''')[0]
				videoUrl = "https://www.eporner.com" + videoID
			if 'txxx' in baseUrl:
				videoUrl = re.search('video_url":"([^"]+)', data).group(1)
				replacemap = {'M': '\\u041c', 'A': '\\u0410', 'B': '\\u0412', 'C': '\\u0421', 'E': '\\u0415', '=': '~', '+': '.', '/': ','}
				for key in replacemap:
					videoUrl = videoUrl.replace(replacemap[key], key)
				videoUrl = base64.b64decode(videoUrl)
				videoUrl = checkhttps(videoUrl)
				if videoUrl.startswith('/'):
					videoUrl = 'https://txxx.com' + videoUrl
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			if 'sunporno' in baseUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video.src=['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''href=['"]([^"^']+?)['"].class="video-download.+''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''source src=['"]([^"^']+?)['"]''')[0].replace(r'\/', '/').replace('&amp;', '&')
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''.src=['"]([^"^']+?)['"].?type="video.+''')[0]

			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0].replace(r'\/', '/').replace('&amp;', '&').strip()
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''url":['"]([^"^']+?)['"]}}}''')[0].replace('&amp;', '&').replace(r"\/", r"/")
			if '.m3u8' in videoUrl:
				if self.cm.isValidUrl(videoUrl):
					tmp = getDirectM3U8Playlist(videoUrl)
					for item in tmp:
						printDBG('Host listsItems valtab: ' + str(item))
					return item['url']
			printDBG('Videolink: ' + videoUrl)
			videoUrl = checkhttps(videoUrl)
			return videoUrl

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
			return videoUrl

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

		if parser == 'https://www.beautymovies.com':
			COOKIEFILE = join(GetCookieDir(), 'beautymovies.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'beautymovies.cookie', 'beautymovies.com', self.defaultParams)
			videoUrl = re.findall('source.src=["]([^@]+?)["]', data, re.S)[0]
			printDBG('Videolink first: ' + videoUrl)
			if not videoUrl:
				videoUrl = re.findall('data-res.{,15}href=["]([^@]+?)["]', data, re.S)[0]
				printDBG('Videolink second: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.xxbrits.com':
			COOKIEFILE = join(GetCookieDir(), 'xxbrits.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'xxbrits.cookie', 'xxbrits.com', self.defaultParams)
			if 'This video is a private video' in data:
				self.sessionEx.open(MessageBox, _("This video is a private video."), type=MessageBox.TYPE_INFO, timeout=10)
				return ''
			else:
				license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0].strip()
				videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)['],", data, re.S)[-1]
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
			try:
				videoUrl = re.findall('source.src=["]([^@]+?)["].{,14}/mp4', data, re.S)[0]
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
				urls = re.findall('source.src=["]([^@]+?)["].{,14}/mp4', data, re.S)[0]
				videoUrl = '%s/%s' % (self.MAIN_URL, urls)
				printDBG('Videolink: ' + videoUrl)
			except Exception:
				self.sessionEx.open(MessageBox, _("This video has been deleted."), type=MessageBox.TYPE_INFO, timeout=10)
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
			printDBG('Fetched: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"]''')[0]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://www.terk.nl':
			sts, data = self.get_Page(url)
			printDBG('Fetched: ' + data)
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
			printDBG('EMBED DATA: ' + data2)
			videoUrl = self.cm.ph.getSearchGroups(data2, '''source.src=['"]([^"^']+?)['"]''')[0]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://pornvideosbest.com':
			printDBG('PORNVIDEOSBEST PARSER')
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, "video_url'].=.[']([^']+?)[']")[0]
			printDBG('Videolink: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT}) if videoUrl else ''

		if parser == 'https://www.mature-girls.com':
			printDBG('MATUREGIRLS PARSER')
			sts, data = self.getPage(url, 'mature-girls.cookie', 'mature-girls.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, 'contentURL".content=["]([^"]+?)["]')[0]
			printDBG('Videolink: ' + videoUrl)
			return videoUrl

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

		if parser == 'http://www.wifevideos.net':
			printDBG('WIFEVIDEOS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'wifevideos.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.get_Page(url)
			videoUrl = self.cm.ph.getSearchGroups(data, r"video_url:\s[']([^@]+?)[']")[0]
			if videoUrl:
				printDBG('VideoURL: ' + videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			return ''

		if parser == 'https://www.milffox.com':
			printDBG('MILF FOX PARSER')
			COOKIEFILE = join(GetCookieDir(), 'milffox.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'milffox.cookie', 'milffox.com', self.defaultParams)
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
			printDBG('9VIDS PARSER')
			COOKIEFILE = join(GetCookieDir(), '9vids.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, '9vids.cookie', '9vids.com', self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, r'iframe\ssrc=["]([^"]+?)["]\sframe')[0]
			printDBG('embedUrl: ' + embedUrl)
			sts, data2 = self.getPage(embedUrl, '9vids.cookie', '9vids.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data2, r'controls\ssrc=["]([^"]+?)["]\sposter')[0]
			printDBG('Videolink: ' + videoUrl)
			return videoUrl

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
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=[']([^"^']+?)[']''')[0]
			printDBG('Videolink: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url})

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
			printDBG('Final DATA: ' + data)
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
			printDBG('Final DATA: ' + data)
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
			printDBG('ENGORGEDTITS PARSER')
			COOKIEFILE = join(GetCookieDir(), 'engorgedtits.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'engorgedtits.cookie', 'engorgedtits.com', self.defaultParams)
			data2 = self.cm.ph.getDataBeetwenMarkers(data, 'embed-inner', 'embed-->', False)[1]
			printDBG('ENGORGEDTITS PARSERDATA 2: ' + data2)
			videoUrl = re.findall('quot[;]([^;^]+?.mp4)[&]quot.{,10}type', data2, re.S)
			if videoUrl:
				printDBG('Video links: ' + str(videoUrl))
				videoUrl = videoUrl[0]
				videoUrl = videoUrl.replace(r'\/', '/')
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

			if not videoUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, 'fullscreen".src=["]([^"]+?)["]')[0]
				sts, data3 = self.get_Page(embedUrl)
				if not sts or data3 is None:
						SetIPTVPlayerLastHostError(_('THIS IS A PREMIUM VIDEO.\nLOGIN OR PREMIUM REQUIRED.'))
						return []
				videoUrl = self.cm.ph.getSearchGroups(data3, "urlPlaylistUrl = [']([^']+?)[']")[0]
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})
			else:
				SetIPTVPlayerLastHostError(_('THIS IS A PREMIUM VIDEO. \nLOGIN OR PREMIUM REQUIRED.'))
				return []

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
			printDBG('LIMITED DATA: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source src=["]([^"]+?)["]''')[0]
			if videoUrl:
				printDBG('READY LINK: ' + str(videoUrl))
				# videoUrl = videoUrl[0]
				return videoUrl
			return ''

		if parser == 'https://voyeurhit.com':
			printDBG('VOYEURHIT PARSER')
			COOKIEFILE = join(GetCookieDir(), 'voyeurhit.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'voyeurhit.cookie', 'voyeurhit.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG( 'Host listsItems data: '+data )
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

		if parser == 'https://www.real-mature-porn.com':
			printDBG('REAL-MATURE-PORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'realmatureporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'realmatureporn.cookie', 'real-mature-porn.com', self.defaultParams)
			EmbedUrl = self.cm.ph.getSearchGroups(data, 'iframe.src=["]([^"]+?)["]', 1, True)[0]
			printDBG('Embed URL: ' + EmbedUrl)
			sts, data = self.getPage(EmbedUrl, 'realmatureporn.cookie', EmbedUrl, self.defaultParams)
			if not sts:
				return ''
			printDBG('Final DATA: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, 'source.src=["]([^"]+?)["].type="video/mp4')[0]
			printDBG('Videolink: ' + videoUrl)
			if videoUrl:
				return videoUrl

		if parser == 'https://www.sexetag.com':
			printDBG('SEXETAG PARSER')
			COOKIEFILE = join(GetCookieDir(), 'sexetag.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'sexetag.cookie', 'sexetag.com', self.defaultParams)
			printDBG('Final DATA: ' + data)
			videoUrl = re.findall(r"source\ssrc=[']([^']+?)[']\stype='video/mp4", data, re.S)
			printDBG('Videolink: ' + str(videoUrl))
			if videoUrl:
				return videoUrl[0]

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
				for item in getDirectM3U8Playlist(videoUrl):
					printDBG('Host listsItems valtab: ' + str(item))
					return item['url']
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
			# printDBG( 'YESPORNPLEASE PARSERDATA: '+ str(data))
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
				# return strwithmeta(videoUrl, {'Referer': url})
			return ''

		if parser == 'https://xhamster.com':
			COOKIEFILE = join(GetCookieDir(), 'xhamster.cookie')
			sts, data = self.getPageWithCFBypass(url)
			if not sts:
				return ''
			printDBG('Host listsItems data: ' + data)
			videoUrl = re.search('preload"\\shref=["]([^"]+?m3u8)["]', data).group(1)
			printDBG("M3U8 URL: " + videoUrl)
			sts, m3u8data = self.cm.getPage(videoUrl)
			if not sts:
				return strwithmeta(videoUrl, {'Referer': url})  # fallback
			streams = re.findall('#EXT-X-STREAM-INF.*?\n(.*)', m3u8data)
			printDBG("STREAMS: " + str(streams))
			valid_streams = [s for s in streams if ".av1" not in s]
			if not valid_streams:
				printDBG("NINCS H264 STREAM, fallback AV1-re")
				return strwithmeta(videoUrl, {'Referer': url})

			def get_res(x):
				m = re.search(r'(\d{3,4})p', x)
				return int(m.group(1)) if m else 0

			best_url = sorted(valid_streams, key=get_res)[-1]
			printDBG("BEST H264 STREAM: " + best_url)
			return strwithmeta(best_url, {'Referer': url})

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
				printDBG('EMBED ADATOK: ' + str(data2))
				videoUrls = data2.split('X-STREAM-INF')
				printDBG('Video links: ' + str(videoUrls))
				lastUrl = videoUrls[-1]
				printDBG('Last video link: ' + lastUrl)
				videoUrl = self.cm.ph.getSearchGroups(lastUrl, '["]([^"]+?)[#]', 1, True)[0].strip()
				printDBG('Last URL: ' + str(videoUrl))
				return videoUrl
			else:
				printDBG('SELECTED RESOLUTION:\n' + url)
				return url

		if parser == 'https://www.realgfporn.com':
			printDBG('REALGFPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'realgfporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'realgfporn.cookie', 'realgfporn.com', self.defaultParams)
			# printDBG('Video link page: ' + data)
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
			sts, data2 = self.getPageWithCFBypass(EmbedUrl)
			if not sts or data2 is None or 'code":"2200' in data2:
				SetIPTVPlayerLastHostError(_('THIS VIDEO IS UNAVAILABLE.\nTRY AGAIN LATER!'))
				return []
			printDBG('EMBED DATA: ' + str(data2))
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
			videoUrl = re.search('contentUrl":.["]([^"]+)["]', data).group(1)
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
			videoUrl = re.search('webkit-playsinline.+\n.+href=["]([^"]+?mp4)["]', data).group(1)
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

		if parser == 'https://w1mp.com':
			printDBG('W1MP PARSER')
			COOKIEFILE = join(GetCookieDir(), 'w1mp.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'w1mp.cookie', 'w1mp.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search("rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall("video.{1,6}url.{2,4}[']([^@]+?)[']", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
				printDBG('Videolink second: ' + videoUrl)
			videoUrl = videoUrl.split('/?br')[0]
			printDBG('Videolink third: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
				return videoUrl

		if parser == 'https://bigbuttholes.com':
			printDBG('BIGBUTTHOLES PARSER')
			COOKIEFILE = join(GetCookieDir(), 'bigbuttholes.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'bigbuttholes.cookie', 'bigbuttholes.com', self.defaultParams)
			printDBG('videoOldal: ' + data)
			embedUrl = self.cm.ph.getSearchGroups(data, r'<source\ssrc="(.*?)"\stype="video/mp4')[0]
			printDBG('EMBEDURL: ' + embedUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = embedUrl
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(embedUrl, params)
			if not sts or response is None:
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			videoUrl = str(real_url)
			printDBG('Videolink: ' + str(videoUrl))
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://bigbuttholes.com':
			printDBG('BIGBUTTHOLES PARSER')
			COOKIEFILE = join(GetCookieDir(), 'bigbuttholes.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'bigbuttholes.cookie', 'bigbuttholes.com', self.defaultParams)
			printDBG('video page: ' + data)
			stream_url = self.cm.ph.getSearchGroups(data, r'contentUrl":\s["]([^"]+?)["]')[0]
			printDBG('Embed URL: ' + stream_url)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(stream_url, params)
			if not sts or response is None:
				printDBG("BIGBUTTHOLES: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			if not real_url.startswith('http'):
				printDBG("BIGBUTTHOLES: incorrect redirect URL")
				return []
			videoUrl = str(real_url)
			printDBG('Videolink second: ' + str(videoUrl))
			if videoUrl:
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

		if parser == 'https://letsporn.com':
			printDBG('LETSPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'letsporn.cookie')
			self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'letsporn.cookie', 'letsporn.com', self.defaultParams)
			videoUrl = self.cm.ph.getSearchGroups(data, r'contentUrl":\s["]([^"]+?)["]')[0]
			printDBG('Videolink: ' + videoUrl)
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
				printDBG('EMBED DATA: ' + data2)
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
				printDBG('EMBED DATA: ' + data2)
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
			videoUrl = re.findall(r'source\ssrc=["]([^@]+?)["]\stype="video/mp4', data, re.S)[0]
			if videoUrl:
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
					# printDBG('M3U8 ANALMEDIA: ' + item['url'])
					return item['url']
			# printDBG('ANALMEDIA URL: ' + videoUrl)
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
					# printDBG('M3U8 LUSTYSEXTUBE: ' + item['url'])
					return item['url']
			# printDBG('LUSTYSEXTUBE URL: ' + videoUrl)
			return videoUrl

		if parser == 'https://porndreamz.com':
			printDBG('PORNDREAMZ PARSER')
			COOKIEFILE = join(GetCookieDir(), 'porndreamz.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'porndreamz.cookie', 'porndreamz.com', self.defaultParams)
			embedUrl = self.cm.ph.getSearchGroups(data, r'embedUrl":\s["]([a-z:/0-9.?_=]+?)["]')[0]
			if not embedUrl:
				embedUrl = re.search(r'og:video"\scontent=["]([a-z:/0-9.?_=]+?)["]', data).group(1)
			printDBG('PORNDREAMZ EMBEDURL: ' + embedUrl)
			sts, data2 = self.get_Page(embedUrl)

			videoUrl = self.cm.ph.getSearchGroups(data2, r'source\ssrc=["]([^"]+?)["]')[0]
			printDBG('Videolink third: ' + videoUrl)
			try:
				return urlparser.decorateUrl(videoUrl, {'Referer': url})
			except Exception:
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
			# printDBG('BIGBOOBS REALURL: ' + str(real_url))
			response.close()
			tmp = getDirectM3U8Playlist(real_url, checkContent=True, sortWithMaxBitrate=999999999)
			for item in tmp:
				# printDBG('M3U8 BIGBOOBS: ' + item['url'])
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
			printDBG('Final DATA: ' + data)
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
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})
			tmp = getDirectM3U8Playlist(real_url, checkContent=True, sortWithMaxBitrate=999999999)
			for item in tmp:
				printDBG('M3U8 END: ' + item['url'])
				return item['url']
			return videoUrl

		if parser == 'https://hardporno.tube':
			printDBG('HARDPORNO PARSER')
			COOKIEFILE = join(GetCookieDir(), 'hardporno.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'hardporno.cookie', 'hardporno.tube', self.defaultParams)
			stream_url = self.cm.ph.getSearchGroups(data, r'source\ssrc=["]([^"]+?)["]')[0]
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
			printDBG('EMBED DATA: ' + data2)
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
			COOKIEFILE = join(GetCookieDir(), 'hogtv.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'hogtv.cookie', 'hog.tv', self.defaultParams)
			if not sts:
				return ''
			videoUrl = re.search('content=["]([^"]+?mp4)["]', data).group(1)
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
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search(r"rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = self.cm.ph.getSearchGroups(data, r"video_url:\s[']([^']+\.mp4[^']*)[']")[-1]
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
			videoUrl = re.findall("video.{1,6}url.{2,4}['](f[^@]+?)[']", data2, re.S)[-1]
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

		if parser == 'https://www.cuckoldsporn.porn':
			printDBG('CUCKOLDSPORN PARSER')
			COOKIEFILE = join(GetCookieDir(), 'cuckoldsporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'cuckoldsporn.cookie', 'cuckoldsporn.porn', self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			videoUrl = re.findall(r"video.{,6}url.{,4}:\s[']([^']+?/)[']", data, re.S)[-1]
			printDBG('Videolink first: ' + videoUrl)
			if not videoUrl:
				videoUrl = re.search(r'"contentUrl":\s["]([^"]+?mp4/)["]', data).group(1)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('LINK: ' + videoUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(videoUrl, params)
			if not sts or response is None:
				printDBG("CUCKOLDSPORN: failed to retrieve the stream URL")
				return []
			real_url = response.geturl()
			printDBG('REALURL: ' + str(real_url))
			response.close()
			return urlparser.decorateUrl(real_url, {'Referer': url})

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
			printDBG('Final DATA: ' + data)
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
			# printDBG('ADATOK: ' + data)
			data = self.cm.ph.getDataBeetwenMarkers(data, 'VIDEO CONTENT', 'layoutControls', False)[1]
			videoUrl = self.cm.ph.getSearchGroups(data, 'src=["]([^"]+?mp4)["]')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'source\ssrc=["]([^"]+?)["]', 1, True)[0]
			if not videoUrl:
				videoUrl = videoUrl = self.cm.ph.getSearchGroups(data, 'src=["]([^"]+?mp4)["]', 1, True)[0]
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})

		if parser == 'https://xdporner.com':
			printDBG('XDPORNER PARSER')
			COOKIEFILE = join(GetCookieDir(), 'xdporner.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'xdporner.cookie', 'xdporner.com', self.defaultParams)
			printDBG('XDPORNER ADATOK: ' + data)
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
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			rnd = re.search(r"rnd:.[']([0-9]+)[']", data).group(1)
			videoUrl = re.findall(r"video.{,5}url.{0,1}:\s[']([^']+?mp4/)[']", data, re.S)
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
			printDBG('EROTICMV PARSER')
			COOKIEFILE = join(GetCookieDir(), 'eroticmv.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPageWithCFBypass(url)
			if not sts:
				return ''
			# printDBG('ADATOK: ' + data[:1000])
			videoUrl = self.cm.ph.getSearchGroups(data, r'video:url"\scontent="([^"]+m3u8)["]')[0]
			printDBG('URL 1: ' + str(videoUrl))
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'source\ssrc=["]([^$]+?)["]')[0]
				printDBG('URL 2: ' + str(videoUrl))
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'"contentUrl"\s*:\s*"([^"]+)"')[0]
				printDBG('URL 3: ' + str(videoUrl))
			videoUrl = videoUrl.replace(r'\/', '/')
			printDBG('MAIN URL: ' + videoUrl)
			tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
			printDBG('PLAYLIST: ' + str(tmp))
			for item in tmp:
				printDBG('M3U8 END: ' + item['url'])
				return item['url']
			return videoUrl

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
			if not videoUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, r'const\sSERVER\d_URL\s=\s["]([^"]+)["];')[0]
			if not videoUrl:
				embedUrl = self.cm.ph.getSearchGroups(data, r'embedUrl":\s["]([^"]+)["]')[0]
			printDBG('EMBEDURL: ' + embedUrl)
			if 'openload' in embedUrl:
				msg = 'THIS VIDEO HAS BEEN REMOVED DUE TO COPYRIGHT INFRINGEMENT.\n PLEASE CHOOSE ANOTHER ONE!'
				self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_INFO)
				return self.listsItems(-1, self.MAIN_URL, 'PORN4DAYS')
			sts, data2 = self.get_Page(embedUrl)
			if not sts:
				return ''
			# printDBG('ADATOK: ' + data2)
			videoUrl = self.cm.ph.getSearchGroups(data2, r'source\ssrc=["]([^"]+?)["]')[0]
			if videoUrl:
				printDBG('videoURL: ' + videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': url})

		if parser == 'https://8kporner.com':
			printDBG('8KPORNER PARSER')
			COOKIEFILE = join(GetCookieDir(), 'porn4days.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			if 'html' in url:
				printDBG('VideoPage: ' + url)
				sts, data = self.getPageWithCFBypass(url)
				if not sts:
					return ''
				# printDBG('ADATOK: ' + data)
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

		if parser == 'https://smutr.com':
			printDBG('SMUTR PARSER')
			COOKIEFILE = join(GetCookieDir(), 'smutr.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'smutr.cookie', 'smutr.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
			printDBG('LICENSE CODE: ' + str(license_code))
			if not license_code:
				embedUrl = self.cm.ph.getSearchGroups(data, 'iframe.{,35}src=["]([^"]+?)["].{,35}/iframe')[0]
				embedUrl = embedUrl.split('&')[0]
				embedUrl = embedUrl.replace('/?a=', '?a=')
				printDBG('EMBEDURL: ' + embedUrl)
				params = dict(self.defaultParams)
				params['header'] = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html', 'Referer': 'https://clips4sale.com/', 'Origin': 'https://clips4sale.com'}
				HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
				HTTP_HEADER['Referer'] = url
				params = {'header': HTTP_HEADER, 'return_data': True}
				sts, data2 = self.cm.getPage(embedUrl, params)
				videoUrl = self.cm.ph.getSearchGroups(data2, 'preview.":.["]([^"]+?mp4)')[0]
				videoUrl = str(videoUrl)
				printDBG('VIDEOURL DATA2: ' + videoUrl)
				return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.USER_AGENT})
			newUrl = re.findall(r"video.{,5}url.{0,1}:\s[']([^']+?)[']", data, re.S)
			if newUrl:
				printDBG('Video links: ' + str(newUrl))
				newUrl = newUrl[-1]
			if 'function/0/' in newUrl:
				newUrl = decryptHash(newUrl, license_code, '16')
			printDBG('videoURL: ' + newUrl)
			HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			HTTP_HEADER['Referer'] = url
			params = {'header': HTTP_HEADER, 'return_data': False}
			sts, response = self.cm.getPage(newUrl, params)
			if not sts or response is None:
				printDBG("SMUTR: failed to retrieve the stream URL")
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
				sts, data = self.getPageWithCFBypass(url)
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
				msg = 'THIS LINK CONTAINS PHOTOS ONLY.\n PLEASE CHOOSE ANOTHER ONE!'
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
			videoUrl = re.findall(r'<source\ssrc="(.*?)"', data, re.S)[-1]
			if videoUrl:
				printDBG('videoURL: ' + str(videoUrl))
				return videoUrl

		if parser == 'https://faplane.com':
			printDBG('FAPLANE PARSER')
			COOKIEFILE = join(GetCookieDir(), 'faplane.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'faplane.cookie', 'faplane.com', self.defaultParams)
			license_code = self.cm.ph.getSearchGroups(data, r"license_code:\s[']([^']+?)[']")[0].strip()
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
				printDBG("FAPLANE: failed to retrieve the stream URL")
				return []
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
			videoUrl = videoUrl.replace('mp4/', 'mp4?rnd=') + rnd
			printDBG('Videolink third: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.whoreshub.com':
			COOKIEFILE = join(GetCookieDir(), 'whoreshub.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'whoreshub.cookie', 'whoreshub.com', self.defaultParams)
			printDBG('WHORESHUB PARSERDATA: ' + str(data))
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
			COOKIEFILE = join(GetCookieDir(), 'veporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'veporn.cookie', 'veporn.com', self.defaultParams)
			printDBG('VEPORN PARSERDATA: ' + str(data))
			try:
				videoUrl = re.search('source.src=["]([^ß]+?)["].{9,12}/mp4', data).group(1)
				return videoUrl
			except Exception:
				videoUrl = re.search('width="560.{9,15}src=["]([^ß]+?)["]', data).group(1)
				sts, data2 = self.getPage(videoUrl, 'veporn.cookie', 'veporn.com', self.defaultParams)
				if not sts:
					return ''
				videoUrl = re.findall('source.src=.["]([^"]+?)["]', data2, re.S)
				videoUrl = "https:" + videoUrl[-1].replace('\\', '')
				return videoUrl

		if parser == 'https://pornxp.org':
			COOKIEFILE = join(GetCookieDir(), 'pornxp.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornxp.cookie', 'pornxp.org', self.defaultParams)
			printDBG('PORNXP PARSERDATA: ' + str(data))
			videoUrl = re.findall('source.src=["]([^"]+?)["].title', data, re.S)
			printDBG('Links: ' + str(videoUrl))
			videoUrl = "https:" + videoUrl[-1]
			printDBG('LEGJOBB LINK: ' + str(videoUrl))
			return videoUrl

		if parser == 'https://pornoflix.com':
			COOKIEFILE = join(GetCookieDir(), 'pornoflix.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'pornoflix.cookie', 'pornoflix.com', self.defaultParams)
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
			printDBG('Related links: ' + str(videoUrls))
			videoUrl = videoUrls[-1]
			printDBG('Last link: ' + videoUrl)
			videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': 'https://ok.xxx'})
			printDBG('End: ' + videoUrl)
			return videoUrl if videoUrl else ''

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

		if parser == 'https://ad69.com':
			COOKIEFILE = join(GetCookieDir(), 'ad69.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			videoUrls = re.findall('''source.{0,20}src=['"](.*?)['"]''', data, re.S)
			printDBG('Videolink: ' + str(videoUrls))
			return videoUrls[-1] if videoUrls else ''

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
			# printDBG('Host listsItems data: ' + str(data))
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
			# printDBG( 'PerfectGirls Links: ' +data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].+1080p''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].+720p''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].+480p''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].+360p''')[0]
			# printDBG( 'Primary address: ' +videoUrl)
			sts, data = self.getPage(videoUrl, 'perfectgirls.cookie', 'perfectgirls.com', self.defaultParams)
			# printDBG( 'PerfectGirls M3U: ' +data)
			videoUrl = self.cm.ph.getSearchGroups(data, r'''1280.+\s[h](.+)''')[0]
			videoUrl = 'h' + videoUrl
			# printDBG( 'Ready link ' +videoUrl)
			return videoUrl

		if parser == 'https://jizzbunker.com':
			COOKIEFILE = join(GetCookieDir(), 'jizzbunker.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + data)
			embedUrl = self.cm.ph.getSearchGroups(data, '''embedUrl":['"]([^"^']+?)['"]''', 1, True)[0].replace(r"\/", "/")
			printDBG('Lekerve: ' + data)
			sts, data = self.get_Page(embedUrl)
			if not sts:
				return ''
			printDBG('Final page: ' + data)
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
			# printDBG('LULUSTREAM PARSER data: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''sources.{2,5}file:['"]([^"^']+?)['"]}''', 1, True)[0]
			printDBG('Fetched link: ' + videoUrl)
			if 'm3u8' in videoUrl:
				videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': "https://1fo1ndyf09qz.tnmr.org", "Origin": "https://lulustream.com"})
				tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			printDBG('This is the end: ' + videoUrl)
			return videoUrl

		if parser == 'https://voe.sx':
			COOKIEFILE = join(GetCookieDir(), 'voe.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			# printDBG('VOE PARSER data: ' + data)
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
			# printDBG('Host listsItems data: ' + data)
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
			# printDBG('Host listsItems data: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			videoUrl = checkhttp(videoUrl)
			return unquote(videoUrl)

		if parser == 'https://dato.porn':
			COOKIEFILE = join(GetCookieDir(), 'datoporn.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'datoporn.cookie', 'datoporn.co', self.defaultParams)
			if not sts:
				return ''
			# license_code = self.cm.ph.getSearchGroups(data, '''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			allUrl = self.cm.ph.getDataBeetwenMarkers(data, 'Download:', '<div class="block-flagging">', False)[1]
			printDBG('Videok: ' + allUrl)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(allUrl, '<a href="', '" data', False)[1]
			printDBG('Link: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://sinparty.com':
			COOKIEFILE = join(GetCookieDir(), 'sinparty.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'sinparty.cookie', 'sinparty.com,', self.defaultParams)
			if not sts:
				return ''
			videoUrl = self.cm.ph.getSearchGroups(data, '''file_url.+?[:]&quot[;]([^"^]+?)[&]quot''')[0].replace(r'\/', '/')
			printDBG('Link: ' + videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': USER_AGENT})

		if parser == 'https://porn720.net':
			COOKIEFILE = join(GetCookieDir(), 'porn720.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'porn720.cookie', 'porn720.org', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + str(data))
			videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0]
			if videoUrl:
				return self.getResolvedURL(self.FullUrl(videoUrl))
			videoUrl = self.RE_SOURCE_SRC.findall(data)
			if videoUrl:
				videoUrl = urlparser.decorateUrl(videoUrl[-1], {'User-Agent': USER_AGENT, 'Referer': url})
				self.defaultParams['max_data_size'] = 0
				sts, data = self.getPage(videoUrl, 'porn720.cookie', 'porn720.org', self.defaultParams)
				return '' if not sts else data.meta['url']

			videoUrl = self.cm.ph.getSearchGroups(data, '''720p['"]:['"]([^"^']+?)['"]''')[0]
			if videoUrl:
				return urlparser.decorateUrl(videoUrl, {'User-Agent': USER_AGENT, 'Referer': url})
			videoUrl = self.cm.ph.getSearchGroups(data, '''480p['"]:['"]([^"^']+?)['"]''')[0]
			return urlparser.decorateUrl(videoUrl, {'User-Agent': USER_AGENT, 'Referer': url}) if videoUrl else ''

		if parser == 'https://fapset.com':
			COOKIEFILE = join(GetCookieDir(), 'fapset.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			# printDBG('Host data: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''screen.src=['"]([^"^']+?)['"]''')[0]
			videoUrl = checkhttp(videoUrl)
			videoUrl = urlparser.decorateUrl(videoUrl, {'User-Agent': USER_AGENT, 'Referer': url})
			return self.getResolvedURL(videoUrl)

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
			# printDBG('Host data: %s' % data)
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
			# printDBG('Host data: ' + data)
			id = self.cm.ph.getSearchGroups(data, r'''video_id\s*=\s*['"]([^"^']+?)['"]''')[0]
			videoUrl = "https://lovehomeporn.com/media/nuevo/config.php?key=%s" % id
			sts, data = self.get_Page(videoUrl)
			if not sts:
				return ''
			# printDBG('Host data2: ' + data)
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
			if not sts:
				return ''
			# printDBG('Linkekhez: ' + data)
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_alt_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''embedUrl":.['"]([^"^']+?)['"]''')[0]
				sts, data = self.get_Page(videoUrl)
				if not sts:
					return ''
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''')[0]
				sts, data = self.get_Page(videoUrl)
				if not sts:
					return ''
				# printDBG('Xhamsterhez: ' + data)
				videoUrl = self.cm.ph.getSearchGroups(data, r'''HD[0-9A-Za-z,:{}"\]]+url":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
				printDBG('Xhamster Multi: ' + videoUrl)
				if not videoUrl:
					videoUrl = self.cm.ph.getSearchGroups(data, '''true[a-z":,]+videoUrl":['"]([^"^']+?)['"]''')[0].replace(r'\/', '/')
					printDBG('Lekert link: ' + videoUrl)
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
			# return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER['User-Agent']})
			return videoUrl

		if parser == 'https://www.eroprofile.com':
			COOKIEFILE = join(GetCookieDir(), 'eroprofile.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + data)
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
			# printDBG('Host listsItems data: ' + data)
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
			# printDBG('Host listsItems data: ' + data)
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			return urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent': self.HTTP_HEADER['User-Agent']})

		if parser == 'https://anybunny.com':
			COOKIEFILE = join(GetCookieDir(), 'anybunny.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'anybunny.cookie', 'anybunny.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('ANYBUNNY PARSERDATA: ' + data)
			# videoUrls = re.search('file:"[ ]([^"^>]+?)[?]', data, re.S)
			videoUrls = self.cm.ph.getSearchGroups(data, '''file:"[ ]([^"^>]+?)[?]''')[0]
			printDBG('ANYBUNNY Links: ' + str(videoUrls))
			if '.m3u8' in videoUrls:
				if self.cm.isValidUrl(videoUrls):
					tmp = getDirectM3U8Playlist(videoUrls, checkContent=True, sortWithMaxBitrate=999999999)
					printDBG('ready list: ' + str(tmp))
					if not tmp:
						videoUrl = self.cm.ph.getSearchGroups(data, '''or[ ]([^"^>]+?)[ ]:cast''')[0]
						printDBG('Direkt link: ' + videoUrl)
						return videoUrl
					for item in tmp:
						return item['url']
			printDBG('Fetched link: ' + videoUrl)
			return videoUrl

		if parser == 'https://hqporner.com':
			# printDBG( 'Selected Resolution: '+url )
			videoUrl = urlparser.decorateUrl(url, {'Referer': url})
			return videoUrl if videoUrl else ''

		if parser == 'https://www.eporner.com':
			printDBG('Selected Resolution: ' + url)
			if url.startswith('http'):
				videoUrl = url
			else:
				videoUrl = "https://www.eporner.com" + url
			printDBG('Last link: ' + videoUrl)
			videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': videoUrl})
			return videoUrl if videoUrl else ''

		if parser == 'https://hello.porn':
			printDBG('Selected Resolution: ' + url)
			videoUrl = urlparser.decorateUrl(url, {'Referer': url})
			return videoUrl if videoUrl else ''

		if parser == 'https://dansmovies.com':
			COOKIEFILE = join(GetCookieDir(), 'dansmovies.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			# printDBG('Fetched link page: ' + data)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'source src="', '" type=', False)[1]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttps(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://www.naked.com':
			COOKIEFILE = join(GetCookieDir(), 'naked.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': False, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'naked.cookie', 'naked.com', self.defaultParams)
			if not sts:
				return ''
			modelname = self.cm.meta['url'].split('=')[-1]
			id = ''
			host = ''
			data = data.replace('\\', '')
			# printDBG('Host listsItems data: ' + data)
			data = data.split('<div class="live clearfix')
			if len(data):
				del data[0]
			for item in data:
				id = self.cm.ph.getSearchGroups(item, '''data-model-id=['"]([^"^']+?)['"]''')[0]
				host = self.cm.ph.getSearchGroups(item, '''data-video-host=['"]([^"^']+?)['"]''')[0]
				if modelname == self.cm.ph.getSearchGroups(item, '''data-model-seo-name=['"]([^"^']+?)['"]''', 1, True)[0]:
					if 'multi-user-private' in item:
						SetIPTVPlayerLastHostError(_(' Private Show.'))
						return []
					break
			videoUrl = 'https://manifest.vscdns.com/manifest.m3u8?key=nil&provider=highwinds&host=' + host + '&model_id=' + id + '&secure=true&prefix=amlst&youbora-debug=1'
			PHPSESSID = self.cm.getCookieItem(COOKIEFILE, 'PHPSESSID')
			videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': self.cm.meta['url'], 'Cookie': 'PHPSESSID=%s' % PHPSESSID, 'User-Agent': USER_AGENT, 'iptv_livestream': True, 'Origin': 'https://www.naked.com'})
			tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
			for item in tmp:
				return item['url']
			return ''

		if parser == 'https://www.pornrewind.com':
			COOKIEFILE = join(GetCookieDir(), 'pornrewind.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].type="video''')[0]
			return videoUrl

		if parser == 'https://shooshtime.com':
			self.MAIN_URL = 'https://shooshtime.com'
			COOKIEFILE = join(GetCookieDir(), 'shooshtime.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE, 'return_data': True}
			sts, data = self.getPage(url, 'shooshtime.cookie', 'shooshtime.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + str(data))
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
			# printDBG('Host listsItems data: ' + str(data))
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
			# printDBG('Host listsItems data: ' + data)
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
			# printDBG('Host listsItems data: ' + data)
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

		if parser == 'https://www.amateurporn.me':
			COOKIEFILE = join(GetCookieDir(), 'amateurporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			# printDBG('AmateurPorn Download: ' + data)
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)["].*\n<''')[0]
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''src=["]([^j]+?)["].*\n.*s''')[0]
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if videoUrl else ''

		if parser == 'https://www.hdporn.net':
			COOKIEFILE = join(GetCookieDir(), 'hdporn.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return
			# printDBG('Host listsItems data: ' + data)
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
			# printDBG( 'Host data:%s' % data )
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
			# printDBG('Host listsItems data: ' + data)
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
			# printDBG('Host listsItems data: ' + data)
			videoUrl = self.FullUrl(self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"]([^"^']+?)['"]''')[0])
			return urlparser.decorateUrl(videoUrl, {'Referer': url}) if videoUrl else ''

		if parser == 'https://glavmatures.com':
			COOKIEFILE = join(GetCookieDir(), 'glavmatures.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='iphone_3_0')
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'glavmatures.cookie', 'glavmatures.com', self.defaultParams)
			if not sts:
				return ''
			data = self.cm.ph.getDataBeetwenMarkers(data, 'votes)</span></span>', 'PHPSESSID', False)[1]
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, '<a href="', '" data', False)[1]
			printDBG('Ready link: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.pornheed.com':
			COOKIEFILE = join(GetCookieDir(), 'pornheed.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'pornheed.cookie', 'pornheed.com', self.defaultParams)
			if not sts:
				return ''
			# printDBG('Links page: ' + data)
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
			# printDBG('Video page: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''contentURL".content=['"]([^"^']+?)['"] /><meta''', 1, True)[0]
			if not videoUrl:
				phUrl = self.cm.ph.getSearchGroups(data, '''<iframe.src=['"]([^"^']+?)['"].frame''', 1, True)[0]
				sts, data = self.get_Page(phUrl)
				if not sts:
					return ''
				embedUrl = self.cm.ph.getSearchGroups(data, '''<iframe.src=['"]([^"^']+?)['"].frame''', 1, True)[0]
				printDBG('Embedded page: ' + embedUrl)
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
			# printDBG('Host listsItems data: ' + data)
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
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, '<source src="', '"', False)[1]
			printDBG('Final Url: ' + videoUrl)
			return videoUrl

		if parser == 'https://www.megatube.xxx':
			COOKIEFILE = join(GetCookieDir(), 'megatube.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			printDBG('VideoPage Data: ' + data)
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

		if parser == 'https://www.bigtitslust.com/':
			COOKIEFILE = join(GetCookieDir(), 'bigtitslust.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'bigtitslust.cookie', 'bigtitslust.com', self.defaultParams)
			if not sts:
				return ''
			license_code = self.cm.ph.getSearchGroups(data, r'''license_code\s*?:\s*?['"]([^"^']+?)['"]''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, r'''video_url\s*?:\s*?['"]([^"^']+?)['"],''')[0]
			printDBG('Host license_code: %s' % license_code)
			printDBG('Host video_url: %s' % videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			videoUrl = self.cm.ph.getSearchGroups(videoUrl, r'''([^"^']+?)[/]\?br''')[0].strip()
			printDBG('Ready link: ' + videoUrl)
			return unquote(videoUrl) if videoUrl else ''

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
			# printDBG('Host listsItems data: ' + data)
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
			self.defaultParams = {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.getPage(url, 'freeones.cookie', 'freeones.com', self.defaultParams)
			if not sts:
				return ''
			printDBG('FreeOnes Parser data: ' + data)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'contentUrl":"', '"', False)[1].replace(r'\/', '/')
			return videoUrl

		if parser == 'https://www.youx.xxx':
			COOKIEFILE = join(GetCookieDir(), 'youx.cookie')
			self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
			self.HTTP_HEADER['Referer'] = url
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url, self.defaultParams)
			if not sts:
				return ''
			# printDBG('Host listsItems data: ' + data)
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
			# printDBG('Host listsItems data: ' + data)
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
			# printDBG('data: ' + data)
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
			# printDBG('Host listsItems data: ' + data)
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
		query_data = {'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
		try:
			data = self.cm.getURLRequestData(query_data)
			# printDBG('Host getResolvedURL data: ' + data)
		except Exception:
			printDBG('Host getResolvedURL query error')
			return videoUrl

		if parser == 'file: ':
			return self.cm.ph.getSearchGroups(data, '''file: ['"]([^"^']+?)['"]''')[0]

		if parser == "0p'  : '":
			videoPage = re.findall("0p'  : '(http.*?)'", data, re.S)
			return videoPage[-1] if videoPage else ''

		if parser == 'source src="':
			videoPage = re.findall('source src="(http.*?)"', data, re.S)
			return videoPage[-1] if videoPage else ''

		if parser == "video_url: '":
			videoPage = re.findall("video_url: '(.*?).'", data, re.S)
			if videoPage:
				printDBG('Host videoPage:' + videoPage[0])
				return videoPage[0]
			return ''

		if parser == 'videoFile="':
			videoPage = re.findall('videoFile="(.*?)"', data, re.S)
			if videoPage:
				printDBG('Host videoPage:' + videoPage[0])
				return videoPage[0]
			return ''

		if parser == 'https://www.ah-me.com':
			license_code = self.cm.ph.getSearchGroups(data, '''license_code:.['"]([^"^']+?)['"],''')[0]
			videoUrl = self.cm.ph.getSearchGroups(data, '''video_url:.['"]([^"^']+?)['"]''')[0]
			printDBG('Videolink first: ' + videoUrl)
			if 'function/0/' in videoUrl:
				videoUrl = decryptHash(videoUrl, license_code, '16')
			printDBG('Videolink second: ' + videoUrl)
			# if videoUrl:urlparser.decorateUrl(videoUrl, {'Referer': url})
			return videoUrl

		if parser == 'https://www.yuvutu.com':
			videoUrl = self.cm.ph.getSearchGroups(data, r'''\s*?{\s*?file:.['"]([^"^']+?)['"],''')[0]
			# printDBG( 'Fetched link:: '+videoUrl )
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
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://www.homepornking.com':
			printDBG('data: ' + data)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, 'source type="video/mp4" src="', '" /></video></div>', False)[1]
			printDBG('VideoLink: ' + videoUrl)
			return videoUrl

		if parser == 'https://motherless.com':
			sts, data = self.get_Page(url)
			printDBG('Fetched: ' + data)
			videoUrl = self.cm.ph.getDataBeetwenMarkers(data, "fileurl = '", "';", False)[1]
			printDBG('VideoLink: ' + videoUrl)
			if videoUrl:
				videoUrl = checkhttp(videoUrl)
				return videoUrl
			return ''

		if parser == 'https://mustjav.com':
			sts, data = self.get_Page(url)
			printDBG('Fetched: ' + data)
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
			printDBG('Fetched: ' + data)
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
			printDBG('Fetched: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''source.src=['"]([^"^']+?)['"].type''')[0]
			printDBG('VideoLink: ' + videoUrl)
			return videoUrl if videoUrl else ''

		if parser == 'https://videosection.com':
			sts, data = self.get_Page(url)
			printDBG('Fetched: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''contentUrl.+['"]([^"^']+?)['"]>''')[0]
			videoUrl = videoUrl.replace('&amp;', '&')
			printDBG('VideoLink: ' + videoUrl)
			if '.m3u8' in videoUrl:
				if self.cm.isValidUrl(videoUrl):
					tmp = getDirectM3U8Playlist(videoUrl)
					for item in tmp:
						printDBG('Host listsItems valtab: ' + str(item))
						return item['url']
			return videoUrl if videoUrl else ''

		if parser == 'https://everycamgirl.com':
			COOKIEFILE = join(GetCookieDir(), 'chaturbate.cookie')
			self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			printDBG('PAGE TITLE: ' + url)
			if 'chaturbate' in url:
				printDBG('CHATURBATE VideoPage data: ' + data)
				linkUrl = 'https://chaturbate.com/' + url.split('/')[-2]
				printDBG('Original title: ' + linkUrl)
				sts, data = self.get_Page(linkUrl, self.defaultParams)
				mainUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{,15}[2]([^"^']+?)[,]''')[0]
				printDBG('HLS address: ' + mainUrl)
				videoUrl = mainUrl.replace('\\u002D', '-').replace(r'\-', '-').replace('\\u0022', '')
				videoUrl = videoUrl.replace('m3u8\\', 'm3u8')
				printDBG('Corrected address: ' + videoUrl)
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''autoplay.+?['"]([^"^']+?)['"]''')[0]
				printDBG('Primary address: ' + videoUrl)
			if not videoUrl:
				videoUrl = self.cm.ph.getSearchGroups(data, '''data-src=['"]([^"^']+?)['"]''')[0]
				videoUrl = videoUrl.replace('&amp;', '&')
				videoUrl = videoUrl.replace('%3A', ':').replace('%2B', '+').replace('%2F', '/')
				printDBG('STRIPCHAT AND STREAMATE LINK: ' + videoUrl)
			if not videoUrl:
				printDBG('#--- Chaturbate Parser ---#')
				videoUrl = self.cm.ph.getSearchGroups(data, '''iframe.src=['"]([^"^']+?)['"]''')[0]
				videoUrl = videoUrl.replace('com/in', 'com/embed')
				printDBG('video link: ' + videoUrl)
				mainUrl = self.cm.ph.getSearchGroups(videoUrl, '''([^"^']+?)[e]mbed/''')[0]
				printDBG('MAIN URL: ' + mainUrl)
				room = self.cm.ph.getSearchGroups(videoUrl, '''&b[=]([^"^']+?)[&]''')[0]
				printDBG('Room data: ' + room)
				campaign = self.cm.ph.getSearchGroups(videoUrl, '''campaign[=]([^"^']+?)[&]''')[0]
				printDBG('Campaign data: ' + campaign)
				settings = self.cm.ph.getSearchGroups(videoUrl, '''&b=.{,20}[&](.+)''')[0]
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
				printDBG('VideoPage data: ' + data)
				linkUrl = self.cm.ph.getSearchGroups(data, '''rel="canonical" href=["]([^"^']+?)["]''')[0]
				printDBG('Original title: ' + linkUrl)
				sts, data = self.get_Page(linkUrl, self.defaultParams)
				mainUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{,15}[2]([^"^']+?)[,]''')[0]
				printDBG('Original title: ' + mainUrl)
				videoUrl = mainUrl.replace('\\u002D', '-').replace(r'\-', '-').replace('\\u0022', '')
				videoUrl = videoUrl.replace('m3u8\\', 'm3u8')
				printDBG('Corrected address: ' + videoUrl)
			if self.cm.isValidUrl(videoUrl):
				tmp = getDirectM3U8Playlist(videoUrl)
				# if not tmp: return ''
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
			printDBG('VideoPage data: ' + data)
			linkUrl = self.cm.ph.getSearchGroups(data, '''rel="canonical" href=["]([^"^']+?)["]''')[0]
			printDBG('Original title: ' + linkUrl)
			sts, data = self.get_Page(linkUrl, self.defaultParams)
			mainUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{,15}[2]([^"^']+?)[,]''')[0]
			printDBG('Original title: ' + mainUrl)
			videoUrl = mainUrl.replace('\\u002D', '-').replace(r'\-', '-').replace('\\u0022', '')
			videoUrl = videoUrl.replace('m3u8\\', 'm3u8')
			printDBG('Corrected address: ' + videoUrl)
			if self.cm.isValidUrl(videoUrl):
				tmp = getDirectM3U8Playlist(videoUrl)
				# if not tmp: return ''
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
			printDBG('Chaturbate data: ' + data)
			videoUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{8,15}[2]([^"^']+?)[,]''')[0].replace('\\u002D', '-').replace('\\u0022', '')
			printDBG('ANACAMS linklista: ' + videoUrl)
			if not videoUrl:
				self.sessionEx.waitForFinishOpen(MessageBox, 'HIDDEN CAM SHOW IN PROGRESS. TRY AGAIN LATER!', type=MessageBox.TYPE_INFO, timeout=30)
				return ''
			if self.cm.isValidUrl(videoUrl):
				tmp = getDirectM3U8Playlist(videoUrl)
				# if not tmp: return ''
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
			printDBG('Fetched: ' + data)
			printDBG('#--- Parser for Chaturbate Cams ---#')
			headUrl = self.cm.ph.getSearchGroups(data, '''chaturbate.+src=['"]([^"^']+?)['"]''')[0]
			sts, data = self.get_Page(headUrl)
			printDBG('video page data: ' + data)
			try:
				mainUrl = self.cm.ph.getSearchGroups(data, '''hls_source.{13}[2]([^"^']+?)[u]0022''')[0]
			except Exception:
				self.sessionEx.open(MessageBox, _("This show is private. Try again later!"), type=MessageBox.TYPE_INFO, timeout=10)
			printDBG('Original title: ' + mainUrl)
			if mainUrl:
				videoUrl = mainUrl.replace('\\u002D', '-').replace(r'\-', '-')
				videoUrl = videoUrl.replace('m3u8\\', 'm3u8')
				if self.cm.isValidUrl(videoUrl):
					tmp = getDirectM3U8Playlist(videoUrl)
					# if not tmp: return ''
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
			printDBG('Original title: ' + mainUrl)
			if not mainUrl:
				self.sessionEx.open(MessageBox, _("This room is offline. Try again later!"), type=MessageBox.TYPE_INFO, timeout=10)
			if mainUrl:
				videoUrl = mainUrl.replace('\\u002D', '-').replace('\\-', '-')
				videoUrl = videoUrl.replace('m3u8\\', 'm3u8')
				printDBG('Fixed address ' + videoUrl)
				videoUrl2 = strwithmeta(videoUrl)
				if sts and videoUrl2.meta.get('status_code', 0) in [410, 404]:
					self.sessionEx.waitForFinishOpen(MessageBox, 'HIDDEN CAM SHOW IN PROGRESS. TRY AGAIN LATER!', type=MessageBox.TYPE_INFO, timeout=30)
					return ''
				if self.cm.isValidUrl(videoUrl):
					try:
						tmp = getDirectM3U8Playlist(videoUrl)
					except Exception:
						self.sessionEx.open(MessageBox, _("This model is offline."), type=MessageBox.TYPE_INFO, timeout=10)
						return ''
					tmp = sorted(tmp, key=lambda item: int(item.get('bitrate', '0')))
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
			videoUrl = checkhttps(videoUrl)
			return videoUrl

		if parser == 'https://rusporn.tv':
			sts, data = self.getPage(url, 'rusporn.cookie', 'rusporn.tv', self.defaultParams)
			printDBG('Parser data: ' + data)
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
			# return ''

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
				tmp = getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999)
				for item in tmp:
					return item['url']
			else:
				COOKIEFILE = join(GetCookieDir(), 'xnxx.cookie')
				self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
				sts, data = self._getPage(url, self.defaultParams)
				videoUrl = self.cm.ph.getSearchGroups(data, r'''VideoHLS\(['"]([^ ^#]+?)['"].;''', 1, True)[0]
				printDBG('Videolink: ' + videoUrl)
				url = videoUrl
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
			printDBG('Fetched new URL:\n' + data2)
			match = re.findall('[\n]([^"]+?)[\n]', data2, re.S)
			if match:
				videoUrl = match[-1]
				printDBG('Fetched new VIDEOURL:\n' + videoUrl)
			else:
				match = re.findall('"[\n]([^"]+?)[\n]', data2, re.S)
				videoUrl = match[-1]
				printDBG('Fetched new VIDEOURL 2:\n' + videoUrl)
			return videoUrl

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
					printDBG('Host listsItems parserdata: ' + data)
					url = re.findall(r'video_file>.*?(http.*?)\]\]><\/video_file>', data, re.S)
					if url:
						url = str(url[0])
						url = url.replace("&amp;", "&")
						printDBG('Host listsItems url: ' + url)
						return url
			return ''

		if parser == 'https://www.el-ladies.com':
			videoUrl = self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"]([^"^']+?)['"]''')[0].replace('&amp;', '&')
			if videoUrl:
				return self.FullUrl(videoUrl)
			videoPage = re.findall(',file:\'(.*?)\'', data, re.S)
			return videoPage[0] if videoPage else ''

		if parser == 'https://sexylies.com':
			videoPage = re.search(r'source\stype="video/mp4"\ssrc="(.*?)"', data, re.S)
			return videoPage.group(1) if videoPage else ''

		if parser == 'https://www.eskimotube.com':
			videoPage = re.search('color=black.*?href=(.*?)>', data, re.S)
			return videoPage.group(1) if videoPage else ''

		if parser == 'https://www.porn5.com':
			videoPage = re.findall('p",url:"(.*?)"', data, re.S)
			return videoPage[-1] if videoPage else ''

		if parser == 'https://www.pornyeah.com':
			videoPage = re.findall('settings=(.*?)"', data, re.S)
			if not videoPage:
				return ''
			xml = videoPage[0]
			printDBG('Host getResolvedURL xml: ' + xml)
			try:
				data = self.cm.getURLRequestData({'url': xml, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
			except Exception:
				printDBG('Host getResolvedURL query error xml')
				return videoUrl
			videoPage = re.findall('defaultVideo:(.*?);', data, re.S)
			return videoPage[0] if videoPage else ''

		if parser == 'https://www.pornpillow.com':
			videoPage = re.findall("'file': '(.*?)'", data, re.S)
			return videoPage[0] if videoPage else ''

		if parser == 'https://www.thumbzilla.com':

			fetchurl = self.cm.ph.getDataBeetwenMarkers(data, 'defaultQuality":false,"format":"hls","videoUrl":"', '","quality"', False)[1]
			fetchurl = fetchurl.replace(r"\/", r"/")
			fetchurl = checkhttp(fetchurl)
			printDBG('Ezt talaltam: ' + fetchurl)
			return fetchurl

		if parser == 'https://vidlox.tv':
			parse = re.search('sources.*?"(http.*?)"', data, re.S)
			return parse.group(1).replace(r'\/', '/') if parse else ''

		if parser == 'https://xxxkingtube.com':
			parse = re.search("File = '(http.*?)'", data, re.S)
			return parse.group(1).replace(r'\/', '/') if parse else ''

		if parser == 'https://pornsharing.com':
			parse = re.search(r'btoa\("(http.*?)"', data, re.S)
			return parse.group(1).replace(r'\/', '/') if parse else ''

		if parser == 'https://pornxs.com':
			parse = re.search('config-final-url="(http.*?)"', data, re.S)
			return parse.group(1).replace(r'\/', '/') if parse else ''

		if parser == 'https://www.flyflv.com':
			parse = re.search('fileUrl="(http.*?)"', data, re.S)
			return parse.group(1).replace(r'\/', '/') if parse else ''

		if parser == 'https://www.yeptube.com':
			videoUrl = re.search('video_id = "(.*?)"', data, re.S)
			if videoUrl:
				xml = 'https://www.yeptube.com/player_config_json/?vid=%s&aid=0&domain_id=0&embed=0&ref=&check_speed=0' % videoUrl.group(1)
				try:
					data = self.cm.getURLRequestData({'url': xml, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
				except Exception:
					printDBG('Host getResolvedURL query error xml')
					return ''
				# printDBG( 'Host data json: '+data )
				videoPage = re.search('"hq":"(http.*?)"', data, re.S)
				if videoPage:
					return videoPage.group(1).replace(r'\/', '/')
				videoPage = re.search('"lq":"(http.*?)"', data, re.S)
				if videoPage:
					return videoPage.group(1).replace(r'\/', '/')
			return ''

		if parser == 'https://vivatube.com':
			videoUrl = re.search('video_id = "(.*?)"', data, re.S)
			if videoUrl:
				xml = 'https://vivatube.com/player_config_json/?vid=%s&aid=0&domain_id=0&embed=0&ref=&check_speed=0' % videoUrl.group(1)
				try:
					data = self.cm.getURLRequestData({'url': xml, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
				except Exception:
					printDBG('Host getResolvedURL query error xml')
					return ''
				# printDBG( 'Host data json: '+data )
				videoPage = re.search('"hq":"(http.*?)"', data, re.S)
				if videoPage:
					return videoPage.group(1).replace(r'\/', '/')
				videoPage = re.search('"lq":"(http.*?)"', data, re.S)
				if videoPage:
					return videoPage.group(1).replace(r'\/', '/')
			return ''

		if parser == 'https://www.tubeon.com':
			videoUrl = re.search('video_id = "(.*?)"', data, re.S)
			if videoUrl:
				xml = 'https://www.tubeon.com/player_config_json/?vid=%s&aid=0&domain_id=0&embed=0&ref=&check_speed=0' % videoUrl.group(1)
				try:
					data = self.cm.getURLRequestData({'url': xml, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
				except Exception:
					printDBG('Host getResolvedURL query error xml')
					return ''
				# printDBG( 'Host data json: '+data )
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
				for item in getDirectM3U8Playlist(videoUrl):
					printDBG('Host listsItems valtab: ' + str(item))
					return item['url']
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
			self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
			sts, data = self.get_Page(url)
			if not sts:
				return ''
			hlsUrl = re.findall('src":["]([^"]+?mp4)["]', data, re.S)[0].replace(r"\/", "/")
			if hlsUrl:
				printDBG('HLSURL: ' + str(hlsUrl))
				HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
				HTTP_HEADER['Referer'] = url
				params = {'header': HTTP_HEADER, 'return_data': False}
				sts, response = self.cm.getPage(hlsUrl, params)
				if not sts or response is None:
					return []
				real_url = response.geturl()
				printDBG('REALURL: ' + str(real_url))
				response.close()
				return urlparser.decorateUrl(real_url, {'Referer': url, 'User-Agent': self.USER_AGENT})
			return ''

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


############################################

def decrypt(ciphertext, password, nBits):
	printDBG('decrypt begin ')
	blockSize = 16
	if nBits not in (128, 192, 256):
		return ""
	ciphertext = base64.b64decode(ciphertext)

	nBytes = nBits // 8
	pwBytes = [0] * nBytes
	for i in range(nBytes):
		pwBytes[i] = 0 if i >= len(password) else ord(password[i])
	key = Cipher(pwBytes, KeyExpansion(pwBytes))
	key += key[:nBytes - 16]

	counterBlock = [0] * blockSize
	ctrTxt = ciphertext[:8]
	for i in range(8):
		counterBlock[i] = ord(ctrTxt[i])

	keySchedule = KeyExpansion(key)

	nBlocks = int(math.ceil(float(len(ciphertext) - 8) / float(blockSize)))
	ct = [0] * nBlocks
	for b in range(nBlocks):
		ct[b] = ciphertext[8 + b * blockSize: 8 + b * blockSize + blockSize]
	ciphertext = ct

	plaintxt = [0] * len(ciphertext)

	for b in range(nBlocks):
		for c in range(4):
			counterBlock[15 - c] = urs(b, c * 8) & 0xff
		for c in range(4):
			counterBlock[15 - c - 4] = urs(int(float(b + 1) / 0x100000000 - 1), c * 8) & 0xff

		cipherCntr = Cipher(counterBlock, keySchedule)

		plaintxtByte = [0] * len(ciphertext[b])
		for i in range(len(ciphertext[b])):
			plaintxtByte[i] = cipherCntr[i] ^ ord(ciphertext[b][i])
			plaintxtByte[i] = chr(plaintxtByte[i])
		plaintxt[b] = "".join(plaintxtByte)

	plaintext = "".join(plaintxt)
	return plaintext


Sbox = [
	0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
	0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
	0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
	0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
	0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
	0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
	0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
	0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
	0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
	0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
	0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
	0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
	0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
	0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
	0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
	0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
]

Rcon = [
	[0x00, 0x00, 0x00, 0x00],
	[0x01, 0x00, 0x00, 0x00],
	[0x02, 0x00, 0x00, 0x00],
	[0x04, 0x00, 0x00, 0x00],
	[0x08, 0x00, 0x00, 0x00],
	[0x10, 0x00, 0x00, 0x00],
	[0x20, 0x00, 0x00, 0x00],
	[0x40, 0x00, 0x00, 0x00],
	[0x80, 0x00, 0x00, 0x00],
	[0x1b, 0x00, 0x00, 0x00],
	[0x36, 0x00, 0x00, 0x00]
]


def Cipher(input, w):
	printDBG('cipher begin ')
	Nb = 4
	Nr = len(w) / Nb - 1

	state = [[0] * Nb, [0] * Nb, [0] * Nb, [0] * Nb]
	for i in range(0, 4 * Nb):
		state[i % 4][i // 4] = input[i]

	state = AddRoundKey(state, w, 0, Nb)

	for round in range(1, Nr):
		state = SubBytes(state, Nb)
		state = ShiftRows(state, Nb)
		state = MixColumns(state, Nb)
		state = AddRoundKey(state, w, round, Nb)

	state = SubBytes(state, Nb)
	state = ShiftRows(state, Nb)
	state = AddRoundKey(state, w, Nr, Nb)

	output = [0] * 4 * Nb
	for i in range(4 * Nb):
		output[i] = state[i % 4][i // 4]
	return output


def SubBytes(s, Nb):
	printDBG('subbytes begin ')
	for r in range(4):
		for c in range(Nb):
			s[r][c] = Sbox[s[r][c]]
	return s


def ShiftRows(s, Nb):
	printDBG('shiftrows begin ')
	t = [0] * 4
	for r in range(1, 4):
		for c in range(4):
			t[c] = s[r][(c + r) % Nb]
		for c in range(4):
			s[r][c] = t[c]
	return s


def MixColumns(s, Nb):
	printDBG('mixcolumns begin ')
	for c in range(4):
		a = [0] * 4
		b = [0] * 4
		for i in range(4):
			a[i] = s[i][c]
			b[i] = s[i][c] << 1 ^ 0x011b if s[i][c] & 0x80 else s[i][c] << 1
		s[0][c] = b[0] ^ a[1] ^ b[1] ^ a[2] ^ a[3]
		s[1][c] = a[0] ^ b[1] ^ a[2] ^ b[2] ^ a[3]
		s[2][c] = a[0] ^ a[1] ^ b[2] ^ a[3] ^ b[3]
		s[3][c] = a[0] ^ b[0] ^ a[1] ^ a[2] ^ b[3]
	return s


def AddRoundKey(state, w, rnd, Nb):
	printDBG('addroundkey begin ')
	for r in range(4):
		for c in range(Nb):
			state[r][c] ^= w[rnd * 4 + c][r]
	return state


def KeyExpansion(key):
	printDBG('keyexpansion begin ')
	Nb = 4
	Nk = len(key) / 4
	Nr = Nk + 6

	w = [0] * Nb * (Nr + 1)
	temp = [0] * 4

	for i in range(Nk):
		r = [key[4 * i], key[4 * i + 1], key[4 * i + 2], key[4 * i + 3]]
		w[i] = r

	for i in range(Nk, Nb * (Nr + 1)):
		w[i] = [0] * 4
		for t in range(4):
			temp[t] = w[i - 1][t]
		if i % Nk == 0:
			temp = SubWord(RotWord(temp))
			for t in range(4):
				temp[t] ^= Rcon[i / Nk][t]
		elif Nk > 6 and i % Nk == 4:
			temp = SubWord(temp)
		for t in range(4):
			w[i][t] = w[i - Nk][t] ^ temp[t]
	return w


def SubWord(w):
	printDBG('subword begin ')
	for i in range(4):
		w[i] = Sbox[w[i]]
	return w


def RotWord(w):
	printDBG('rotword begin ')
	tmp = w[0]
	for i in range(3):
		w[i] = w[i + 1]
	w[3] = tmp
	return w


def encrypt(plaintext, password, nBits):
	printDBG('encrypt begin ')
	blockSize = 16
	if nBits not in (128, 192, 256):
		return ""
# plaintext = plaintext.encode("utf-8")
# password  = password.encode("utf-8")
	nBytes = nBits // 8
	pwBytes = [0] * nBytes
	for i in range(nBytes):
		pwBytes[i] = 0 if i >= len(password) else ord(password[i])
	key = Cipher(pwBytes, KeyExpansion(pwBytes))
	key += key[:nBytes - 16]

	counterBlock = [0] * blockSize
	now = datetime.datetime.now()
	nonce = time.mktime(now.timetuple()) * 1000 + now.microsecond // 1000
	nonceSec = int(nonce // 1000)
	nonceMs = int(nonce % 1000)

	for i in range(4):
		counterBlock[i] = urs(nonceSec, i * 8) & 0xff
	for i in range(4):
		counterBlock[i + 4] = nonceMs & 0xff

	ctrTxt = ""
	for i in range(8):
		ctrTxt += chr(counterBlock[i])

	keySchedule = KeyExpansion(key)

	blockCount = int(math.ceil(float(len(plaintext)) / float(blockSize)))
	ciphertxt = [0] * blockCount

	for b in range(blockCount):
		for c in range(4):
			counterBlock[15 - c] = urs(b, c * 8) & 0xff
		for c in range(4):
			counterBlock[15 - c - 4] = urs(b / 0x100000000, c * 8)

		cipherCntr = Cipher(counterBlock, keySchedule)

		blockLength = blockSize if b < blockCount - 1 else (len(plaintext) - 1) % blockSize + 1
		cipherChar = [0] * blockLength

		for i in range(blockLength):
			cipherChar[i] = cipherCntr[i] ^ ord(plaintext[b * blockSize + i])
			cipherChar[i] = chr(cipherChar[i])
		ciphertxt[b] = ''.join(cipherChar)

	ciphertext = ctrTxt + ''.join(ciphertxt)
	ciphertext = base64.b64encode(ciphertext)

	return ciphertext


def urs(a, b):
	printDBG('urs begin ')
	a &= 0xffffffff
	b &= 0x1f
	if a & 0x80000000 and b > 0:
		a = (a >> 1) & 0x7fffffff
		a = a >> (b - 1)
	else:
		a = (a >> b)
	return a


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
