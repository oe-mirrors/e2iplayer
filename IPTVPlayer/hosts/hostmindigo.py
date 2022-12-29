# -*- coding: utf-8 -*-
###################################################
# 2022-07-31 Blindspot (Modified Celeburdi's version)
###################################################
HOST_VERSION = "2.9"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import os
from datetime import datetime
from time import time

import zlib
import urllib
import base64
from hashlib import sha1,sha256
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.mindigohu_login    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.mindigohu_password = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("e-mail")+":", config.plugins.iptvplayer.mindigohu_login))
    optionList.append(getConfigListEntry(_("password")+":", config.plugins.iptvplayer.mindigohu_password))
    return optionList
###################################################

def gettytul():
    return "https://tv.mindigo.hu"

def _gh(url):
    if not url: return ""
    return "https://celeburdi.github.io/static/icons/"+url

def _addepg(epgs,id,item):
    x = next((x for x, epg in enumerate(epgs) if epg["id"] == id),None)
    if x:
        epgs[x]["items"].append(item)
    else:
        epgs.append({"id": id, "items": [item]})
        x = len(epgs)-1
    return x

def _getChannelDefs():
    return [
        {"title": "M1 HD", "icon": "m1hd.jpg", "group" : "main", "selres": True },
        {"title": "M2 HD", "icon": "m2hd.jpg", "group" : "child", "selres": True },
        {"title": "Duna HD", "icon": "dunahd.jpg", "group" : "main", "selres": True },
        {"title": "M4 Sport HD", "icon": "m4sport.jpg", "group" : "sport", "selres": True },
        {"title": "M5 HD", "icon": "m5.jpg", "group" : "main", "selres": True },
        {"title": "Duna World", "icon": "dunaworld.jpg", "group" : "main" },
        {"title": "Izaura TV", "icon": "izauratv.jpg", "group" : "movie", "selres": True },
        {"title": "Zenebutik", "icon": "zenebutik.jpg", "group" : "music", "selres": True },
        {"title": "FEM3", "icon": "fem3.jpg", "group" : "movie", "selres": True },
        {"title": "Hír TV", "icon": "hirtv.jpg", "group" : "news", "selres": True },
        {"title": "Balaton TV", "icon": "balatontv.jpg", "group" : "regional", "selres": True },
        {"title": "JUCE-Smile", "icon": "smileofachild.jpg", "group" : "child", "selres": True },
        {"title": "Fix TV", "icon": "fixtv.jpg", "group" : "regional", "selres": True },
        {"title": "D1 TV", "icon": "d1tv.jpg", "group" : "regional", "selres": True },
        {"title": "Bonum TV", "icon": "bonumtv.jpg", "group" : "religious", "selres": True },
        {"title": "Heti TV", "icon": "hetitv.jpg", "group" : "regional", "selres": True },
        {"title": "PAX TV", "icon": "paxtv.jpg", "group" : "religious", "selres": True },
        {"title": "Film+", "icon": "filmplus-velirajeha.jpg", "group" : "movie", "selres": True },
        {"title": "Cool", "icon": "cool-wapadedrud.jpg", "group" : "movie", "selres": True },
        {"title": "Mozi+", "icon": "moziplus.jpg", "group" : "movie", "selres": True },
        {"title": "AXN", "icon": "axn.jpg", "group" : "movie" },
        {"title": "Prime", "icon": "prime.jpg", "group" : "main", "selres": True},
        {"title": "RTL II", "icon": "rtl2-wapadedrud.jpg", "group" : "main", "selres": True },
        {"title": "Super TV2", "icon": "supertv2.jpg", "group" : "main", "selres": True },
        {"title": "Paramount Channel", "icon": "paramountchannel.jpg", "group" : "movie" },
        {"title": "TV 4", "icon": "tv4-wapadedrud.jpg", "group" : "movie", "selres": True },
        {"title": "M3", "icon": "m3.jpg", "group" : "movie" },
        {"title": "National Geographic", "icon": "nationalgeographic.jpg", "group" : "docu" },
        {"title": "Spiler TV", "icon": "spiler1tv.jpg", "group" : "sport", "selres": True },
        {"title": "Sláger TV", "icon": "slagertv.jpg", "group" : "music", "selres": True},
        {"title": "Ozone Network", "icon": "ozonetv.jpg", "group" : "docu" },
        {"title": "Discovery Channel", "icon": "discoverychannel.jpg", "group" : "docu" },
        {"title": "TLC", "icon": "tlc.jpg", "group" : "docu" },
        {"title": "Viasat3", "icon": "viasat3.jpg", "group" : "movie" },
        {"title": "Viasat6", "icon": "viasat6.jpg", "group" : "movie" },
        {"title": "Comedy Central", "icon": "comedycentral.jpg", "group" : "movie", "selres": True },
        {"title": "RTL+", "icon": "rtlplus.jpg", "group" : "main", "selres": True },
        {"title": "Film 4", "icon": "film4.jpg", "group" : "movie", "selres": True },
        {"title": "Story 4", "icon": "story4.jpg", "group" : "movie", "selres": True },
        {"title": "FilmBox", "icon": "filmbox.jpg", "group" : "movie" },
        {"title": "Humor+", "icon": "humorplusz.jpg", "group" : "movie", "selres": True },
        {"title": "RTL Gold", "icon": "rtlgold.jpg", "group" : "main", "selres": True },
        {"title": "Kiwi TV", "icon": "kiwitv.jpg", "group" : "child", "selres": True },
        {"title": "Da Vinci TV", "icon": "davincilearning.jpg", "group" : "docu" },
        {"title": "Nickelodeon", "icon": "nickelodeon.jpg", "group" : "child" },
        {"title": "Cartoon Network", "icon": "cartoonnetwork.jpg", "group" : "child" },
        {"title": "LiChi TV", "icon": "lichitv.jpg", "group" : "docu", "selres": True },
        {"title": "Sony Max", "icon": "sonymax-wapadedrud.jpg", "group" : "movie" },
        {"title": "Sony Movie", "icon": "sonymoviechannel-wapadedrud.jpg", "group" : "movie" },
        {"title": "DOQ Channel", "icon": "doq.jpg", "group" : "docu", "selres": True },
        {"title": "Galaxy 4", "icon": "galaxy4.jpg", "group" : "movie", "selres": True },
        {"title": "NAT GEO Wild", "icon": "natgeowild.jpg", "group" : "docu" },
        {"title": "Viasat History", "icon": "viasathistory.jpg", "group" : "docu" },
        {"title": "Fishing&Hunting", "icon": "fishingandhunting.jpg", "group" : "sport" },
        {"title": "FilmBox Premium", "icon": "filmboxpremium.jpg", "group" : "movie" },
        {"title": "RTL Spike", "icon": "rtlspike.jpg", "group" : "movie" },
        {"title": "Viasat Explore", "icon": "viasatexplore.jpg", "group" : "docu" },
        {"title": "Viasat Nature", "icon": "viasatnature.jpg", "group" : "docu" },
        {"title": "Epic Drama HD", "icon": "epicdrama.jpg", "group" : "movie" },
        {"title": "Nautical HD", "icon": "nauticalchannel.jpg", "group" : "sport" },
        {"title": "GameToon HD", "icon": "gametoon.jpg", "group" : "sport" },
        {"title": "Class Horse", "icon": "classhorsetv.jpg", "group" : "sport" },

        {"title": "FixTV", "rename": "Fix TV", "icon": "fixtv.jpg", "group" : "regional" },
        {"title": "The Fishing & Hunting Channel", "rename": "Fishing&Hunting", "icon": "fishingandhunting.jpg", "group" : "sport" },
        {"title": "Fit HD", "icon": "fithd.jpg", "group" : "sport"},
        {"title": "C Music TV", "icon": "cmusictv.jpg", "group" : "music" },
        {"title": "iConcerts HD", "icon": "iconcerts.jpg", "group" : "music" },
        {"title": "DOQ TV", "rename": "DOQ Channel", "icon": "doq.jpg", "group" : "docu" },
        {"title": "National Geographic Wild", "rename": "NAT GEO Wild", "icon": "natgeowild.jpg", "group" : "docu" },

        {"title": "Dankó Rádió", "icon": "dankoradio.jpg", "group" : "main", "epg_id": "dankoradio.hu", "epg_prov_id": "porthu" },
        {"title": "Duna World Rádió", "icon": "dunaworldradio.jpg", "group" : "main" },
        {"title": "Nemzetiségi adások", "icon": "nemzetisegiadasok.jpg", "group" : "main", "epg_id": "nemzetisegiadasok.hu", "epg_prov_id": "porthu" },
        {"title": "Parlamenti adások", "icon": "parlamentiadasok.jpg", "group" : "main" },
        {"title": "Radio Swiss Classic (fr)", "icon": "swissclassic.jpg", "group" : "music" },
        {"title": "Radio Swiss Classic (ger)", "icon": "swissclassic.jpg", "group" : "music" },
        {"title": "Radio Swiss Jazz", "icon": "swissjazz.jpg", "group" : "music" },
        {"title": "Radio Swiss Pop", "icon": "swisspop.jpg", "group" : "music" },

        {"title": "Kossuth rádió", "icon": "kossuthradio.jpg", "group" : "main", "epg_id": "kossuthradio.hu", "epg_prov_id": "porthu" },
        {"title": "Petőfi rádió", "icon": "petofiradio.jpg", "group" : "main", "epg_id": "petofiradio.hu", "epg_prov_id": "porthu" },
        {"title": "Bartók rádió", "icon": "bartokradio.jpg", "group" : "main", "epg_id": "bartokradio.hu", "epg_prov_id": "porthu" },
        {"title": "Manna FM", "icon": "mannafm.jpg", "group" : "regional" },
        {"title": "River FM", "icon": "riverfm.jpg", "group" : "religious" },

        {"title": "Euronews", "icon": "euronews.jpg", "group" : "news" },
        {"title": "Erdély TV", "icon": "erdelytv.jpg", "group" : "regional" },

        ]


def _mr(url):
    return "http://icast.connectmedia.hu/"+url


def _getDirectRadios():
    return [
        {"title": "Kossuth rádió", "url": "D" + _mr("4734/mr1.aac")+","+_mr("4736/mr1.mp3")+","+_mr("4764/mr1.ogg") },
        {"title": "Petőfi rádió", "url": "D" + _mr("4737/mr2.aac")+","+_mr("4738/mr2.mp3")+","+_mr("4765/mr2.ogg") },
        {"title": "Bartók rádió", "url": "D" + _mr("4739/mr3.aac")+","+_mr("4741/mr3.mp3")+","+_mr("4766/mr3.ogg") },

        {"title": "Dankó Rádió",  "url": "D" + _mr("4747/mr7.aac")+","+_mr("4748/mr7.mp3")+","+_mr("4770/mr7.ogg") },
        {"title": "Duna World Rádió",  "url": "D" + _mr("4760/dwr.aac")+","+_mr("4761/dwr.mp3")+","+_mr("4776/dwr.ogg") },
        {"title": "Nemzetiségi adások", "url": "D" + _mr("4743/mr4.aac")+","+_mr("4744/mr4.mp3")+","+_mr("4768/mr4.ogg") },
        {"title": "Parlamenti adások",  "url": "D" + _mr("4745/mr5.aac")+","+_mr("4746/mr5.mp3")+","+_mr("4769/mr5.ogg") },

        {"title": "Radio Swiss Classic (fr)", "url": "D" + _mr("4786/live.mp3") },
        {"title": "Radio Swiss Classic (ger)", "url": "D" + _mr("4785/live.mp3") },
        {"title": "Radio Swiss Jazz", "url": "D" + _mr("4787/live.mp3") },
        {"title": "Radio Swiss Pop", "url": "D" + _mr("4788/live.mp3") },

        {"title": "Manna FM", "url": "D" + _mr("4780/live.mp3") },
        {"title": "River FM", "url": "D" + _mr("4711/live.mp3") },

        ]

def _getMTVATVs():
    return [
        {"title": "Duna HD", "url": "dunalive" },
        {"title": "Duna World", "url": "dunaworldlive" },
        {"title": "M1 HD", "url": "mtv1live" },
        {"title": "M2 HD", "url": "mtv2live" },
        {"title": "M4 Sport HD", "url": "mtv4live" },
        {"title": "M5 HD", "url": "mtv5live" },

        ]


def _getYTTVs():
    return [
        {"title": "Euronews", "url": "https://www.youtube.com/watch?v=xddy7-kDdkE" },
#        {"title": "Erdély TV", "url": "https://www.youtube.com/channel//live" },
        ]


class EPGProviderNone:
    def getName(self):
        return ("EPGProviderNone")

    def getEPGItem(self, chId):
        return None

    def getEPG(self, epgId, epgType):
        printDBG("EPGProviderNone.getEPG %r : %r, %r" % (epgId.provId, epgId.itemId, epgType))
        return None,""


class EPGProvider:
    def __init__(self,hostmindigo):
        self.cache = {}
        self.mg = hostmindigo

    def getName(self):
        return ("mindigo")

    def getEPGItem(self, chId):
        timenow = round(time())
        item = self.cache.get(chId)
        if item and item.get("expires",0) > timenow: return item
        if chId[:1] == "E": sts, data = self.mg.getApiPage( self.mg.LIVEINFO_URL + chId[1:] )
        elif chId[:1] == "V": sts, data = self.mg.getApiPage( self.mg.VODINFO_URL + chId[1:] )
        else: return None
        if not sts:
            if item: self.cache.pop(chId,None)
            return None
        try:
            data = json_loads(data)["data"]["detail"]
            if chId[:1] == "E":
                expires = data["endTimeStamp"]
                start = datetime.fromtimestamp(data["startTimeStamp"]).strftime("%H:%M")
                end = datetime.fromtimestamp(expires).strftime("-%H:%M ")
                title = start + end + data["title"]
            else:
                expires = 2147483647
                title = ""

            data = data["movieData"]
            item = {
                "expires": expires,
                "title": title,
                "desc": data.get("description","") or ""
                }

            other_info = {}
            if data["ageRating"]:
                other_info['age_limit'] = str(data["ageRating"])
            if data["genre"]:
                other_info['genre'] = data["genre"]
            if data["year"]:
                other_info["year"] = str(data["year"])

            item["other_info"] = other_info

            if len(self.cache) > 100: self.cache.popitem()
            self.cache[chId] = item
        except:
            printExc()
            return None
        return item

    def getEPG(self, epgId, epgType):
        printDBG("MindiGo.getEPG %r : %r, %r" % (epgId.provId, epgId.itemId, epgType))

        item = self.getEPGItem(epgId.itemId)
        if not item: return None,""

        title = item["title"]
        if title:
            title = title + "[/br]"
        ret = title + item["desc"]

        timeout = item["expires"] - round(time())
        if timeout < 3: timeout = 3

        printDBG(">> timeout: %s" % timeout)
        return timeout, ret

class MindiGoHU(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history":"mindigo.hu", "cookie":"mindigohu.cookie"})

        self.DEFAULT_ICON_URL = zlib.decompress(base64.b64decode(
            "eNrLKCkpsNLXT8rJzEspLsgv0cvLSM2p1Mso1Q/JKM1NykvMzCnWzwVKZqbnx6ekpiWW5pToZRWkAwBfDRWQ"))
        self.HEADER = self.cm.getDefaultHeader()
        self.MAIN_URL = "https://tv.mindigo.hu"

        self.API_URL = zlib.decompress(base64.b64decode(
            "eJzLKCkpKLbS108syNTLzcxLyUzP18soBQBdkggm"))
        self.API_HEADER = dict(self.HEADER)
        self.API_HEADER.update({'x-application-id': zlib.decompress(base64.b64decode(
            "eJxLzcuzzMzNTck1LKssNa8sLUjJy85MTUnOMC3PTc80SQYAz6EMcw=="))})
        self.EXTEND_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z1C8tTi3SL04tLs7Mz9NPrShJzUsBAIaKChg="))
        self.LOGIN_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0i8tTi3Sz8lPz8wDADovBnc="))
        self.LIVE_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0k/OSMzLS80p1s/JLEsFAE9mB5s="))
        self.STREAM_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0i8uKUpNzC3Wz8ksS7VPzs8rSc0ric9Msa2uVctJzEsvTUxPtc0oVSupLADSOcUA"
            "POsU2Q=="))
        self.BRANDS_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0k8qSsxLKQYAIrQE6g=="))
        self.GENRES_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0k9PzStKtc9ILI5Pzs8rSc0rsS0pKk0FAKY8C1M="))
        self.VIDEOS_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0i/LTEnNL7bPLEnNjS9ILYovSExPtTU0AgCyogsq"))
        self.VOD_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0i8uKUpNzC3WL8tPsU/OzytJzSuJz0yxra5Vg/FKKgtSbcsyU1Lz1cDMjJxiAMi9"
            "F4Q="))
        self.LIVEINFO_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0k/OSMzLS80p1gcAM34F6w=="))
        self.VODINFO_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzTTyzI1C8z0i/LTEnNL9YHACgvBSk="))
        self.HBBTV_URL = zlib.decompress(base64.b64decode(
            "eJzLKCkpsNLXz0hKKinTTSzWS87Py0tNLslNTclM1Mso1QcAwhsLwg=="))
        self.HBBTV_MEDIA_URL = self.HBBTV_URL+zlib.decompress(base64.b64decode(
            "eJxLzNBPTy0pLilKTcwtLcrRK8gosM9Msa2uBQB/MAnP"))
        self.HBBTV_CHANNEL_URL = self.HBBTV_URL+zlib.decompress(base64.b64decode(
            "eJxLzNDPSSzNS85ILdIHAB1SBHo="))
        self.HBBTV_HD_URL = self.HBBTV_URL+zlib.decompress(base64.b64decode(
            "eJxLzNDPyU+Pz0jRz8xLSa3QK8goAABGSAcj"))
        self.HBBTV_RADIO_URL = self.HBBTV_URL+zlib.decompress(base64.b64decode(
            "eJxLzNAvSkzJzNfPzEtJrdAryCgAAD8uBsU="))
        self.HBBTV_MTVA_URL = self.HBBTV_URL+zlib.decompress(base64.b64decode(
            "eJzLLSlL1M9JLM1Lzkgt0s/MS0mt0CvIKAAAbGkI9w=="))
        self.MTVA_CHANNEL_URL = zlib.decompress(base64.b64decode(
            "eJzLKCkpKLbS1y/ISaxMLdLLTU3JTMzOyczO1ssohQrmpZbDpAsyCuzLMlNS820BYd8Vcw=="))

        self.M3_URL = zlib.decompress(base64.b64decode(
            "eJzLKCkpKLbS108sSs7ILCvN1cstKUvUyyjVzzUGAI6qCes="))
        self.M3_PROGRAM_URL = self.M3_URL+zlib.decompress(base64.b64decode(
            "eJzTLyjKTy9KzAUADYgDKA=="))
        self.M3_DAILYPROGRAM_URL = self.M3_URL+zlib.decompress(base64.b64decode(
            "eJzTT0nMzKnULSjKTy9KzAUAJqwFaA=="))
        self.M3_OPEN_URL = self.M3_URL+zlib.decompress(base64.b64decode(
            "eJzTT08t0c0vSM2zT87PyUlNLsnMz7MFAFVWB/c="))
        self.M3_IMAGE_URL = zlib.decompress(base64.b64decode(
            "eJzLKCkpKLbS108sSs7ILCvN1cstKUvUyyjVz8xNTE8t1s811gcA7PIMvw=="))
        self.M3_STREAM_URL = "https://archivum.mtva.hu/api/m3/v3/stream?target="

        self.HBBTV_HEADER = dict(self.HEADER)
        self.HBBTV_HEADER.update( {"User-Agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 2.3) AppleWebkit/538.1 (KHTML, like Gecko) SamsungBrowser/1.0 TV Safari/538.1"} )

        self.hbbtvParams = {"header":self.HBBTV_HEADER}

        self.apiParams = {"header":self.API_HEADER}

        self.login = config.plugins.iptvplayer.mindigohu_login.value
        self.password = config.plugins.iptvplayer.mindigohu_password.value
        self.defaultParams = {"header":self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        self.tvChannels = None
        self.radioChannels = None

        self.tvEpgs = None
        self.radioEpgs = None

        self.token = ""

        self.epgProvider = EPGProvider(self)

        try:
            from Plugins.Extensions.IPTVPlayer.epgproviders.porthu import EPGProvider as EPGProvider_porthu
            self.epgProvider_porthu = EPGProvider_porthu()
        except:
            self.epgProvider_porthu = EPGProviderNone()



    def getFullIconUrl(self, url):
        if not url: return self.DEFAULT_ICON_URL
        return url

    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getApiPage(self, url):
        params = dict(self.apiParams)
        params["header"]["x-access-token"] = self.token
        return self.cm.getPage(url , params)

    def getChannels(self):
        printDBG('MindiGoHU.getChannels')

        self.tvChannels = []
        self.radioChannels = []
        self.epgs = []
        tvChannels = []
        radioChannels = []
        tvEpgs = []
        radioEpgs = []
        groups = ["","main","movie","news","docu","child","sport","music","regional","religious","porno","info"]
        chdefs = _getChannelDefs()

        # get MindiGo TV channels
        mindigChannels = []
        try:
            sts, data = self.getApiPage(self.LIVE_URL)
            if not sts: raise Exception("Can't get LIVE channels")
            data = json_loads(data)["data"]
            mindigChannels = data.get("available",[])
            liveCount = len(mindigChannels)
            mindigChannels.extend(data.get("unavailable",[]))
            for x,i in enumerate(mindigChannels):
                title = i['name'].strip()
                chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)
                if chdef:
                    if "rename" in chdef:
                        title = chdef["rename"]
                        i["title"] = title
                    icon = chdef.get("icon")
                    if icon: icon = _gh(icon)
                    order = groups.index(chdef.get("group",""))
                    selres = chdef.get("selres",False)
                    force = chdef.get("force",False)
                else:
                    icon = ""
                    order = 0
                    selres = True
                    force = False
                if not icon:
                    icon = i["logoLink"]

                if x >= liveCount and not force: continue

                if selres: url = "R"+i["id"]
                else: url = "M"+i["id"]

                epg_id = "E"+i["id"]

                params = {'good_for_fav': True, "title": title, "desc": "", "order": order, "url": url, "epg_id": epg_id, "epg_prov_id": "mindigo"  }
                if icon:
                    params['icon']= icon

                _addepg(tvEpgs,i["id"],params)
                tvChannels.append(params)
        except Exception: printExc()

        # get HbbTV TV channels
        try:
            sts, data = self.cm.getPage(self.HBBTV_CHANNEL_URL, self.hbbtvParams)
            if not sts: raise Exception("Can't get HbbTV channels")
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'href="token', '/span>', False)
            for i in data:
                url = self.cm.ph.getDataBeetwenMarkers(i, ':', '"', False)[1]
                if not url: continue
                title = clean_html(self.cm.ph.getDataBeetwenMarkers(i, '>', '<', False)[1])
                if not title: continue
                chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)
                if chdef:
                    title = chdef.get("rename",title)
                    icon = chdef.get("icon")
                    if icon: icon = _gh(icon)
                    order = groups.index(chdef.get("group",""))
                else:
                    icon = ""
                    order = 0
                params = {'good_for_fav': True, "title": title + " (HbbTV)", "desc": "", "order": order, "url": "H"+url }
                if icon:
                    params['icon']= icon
                ch = next((ch for ch in mindigChannels if ch["name"].strip() == title), None)
                if ch:
                    epg_id = "E"+ch["id"]
                    params.update( {"epg_id": epg_id, "epg_prov_id": "mindigo"} )
                    _addepg(tvEpgs,ch["id"],params)
                tvChannels.append(params)
        except Exception: printExc()

        # get HbbTV HD TV channels
        try:
            sts, data = self.cm.getPage(self.HBBTV_HD_URL, self.hbbtvParams)
            if not sts: raise Exception("Can't get HbbTV HD channels")
            data = self.cm.ph.getDataBeetwenMarkers(data, "streams = ", ";", False)[1]
            data = json_loads(data)
            for k,v in data.items():
                if k == "enabled" or  k == "fox": continue
                title = v.get("channel")
                url = v.get("url")
                if title and url and url.startswith("token:"):
                    url = "H"+url[6:]
                    chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)
                    if chdef:
                        title = chdef.get("rename",title)
                        icon = chdef.get("icon")
                        if icon: icon = _gh(icon)
                        order = groups.index(chdef.get("group",""))
                    else:
                        icon = ""
                        order = 0
                    params = {'good_for_fav': True, "title": title + " (HbbTV)", "desc": "", "order": order, "url": url }
                    if icon:
                        params['icon']= icon
                    ch = next((ch for ch in mindigChannels if ch["name"].strip() == title), None)
                    if ch:
                        epg_id = "E"+ch["id"]
                        params.update( {"epg_id": epg_id, "epg_prov_id": "mindigo"} )
                        _addepg(tvEpgs,ch["id"],params)
                    tvChannels.append(params)
        except Exception: printExc()


        # get MTVA TV channels
        for i in _getMTVATVs():
            title = i["title"]
            url = "K"+i["url"]
            chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)
            if chdef:
                title = chdef.get("rename",title)
                icon = chdef.get("icon")
                if icon: icon = _gh(icon)
                order = groups.index(chdef.get("group",""))
            else:
                icon = ""
                order = 0
            params = {'good_for_fav': True, "title": title + " (MTVA)", "desc": "", "order": order, "url": url }
            if icon:
                params['icon']= icon
            ch = next((ch for ch in mindigChannels if ch["name"].strip() == title), None)
            if ch:
                epg_id = "E"+ch["id"]
                params.update( {"epg_id": epg_id, "epg_prov_id": "mindigo"} )
                _addepg(tvEpgs,ch["id"],params)
            tvChannels.append(params)

        # get Youtube TV channels
        for i in _getYTTVs():
            title = i["title"]
            url = "Y"+i["url"]
            chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)
            if chdef:
                title = chdef.get("rename",title)
                icon = chdef.get("icon")
                if icon: icon = _gh(icon)
                order = groups.index(chdef.get("group",""))
            else:
                icon = ""
                order = 0
            params = {'good_for_fav': True, "title": title + " (YT)", "desc": "", "order": order, "url": url }
            if icon:
                params['icon']= icon
            ch = next((ch for ch in mindigChannels if ch["name"].strip() == title), None)
            if ch:
                epg_id = "E"+ch["id"]
                params.update( {"epg_id": epg_id, "epg_prov_id": "mindigo"} )
                _addepg(tvEpgs,ch["id"],params)
            tvChannels.append(params)

        # add nava m3
        params = {'good_for_fav': True, "title": "M3 (MTVA)", "desc": "", "order": 2, "url": "m"+"m3", "icon": _gh("m3.jpg") }
        tvChannels.append(params)

        # get direct radio
        for i in _getDirectRadios():
            title = i["title"]
            url = i["url"]
            chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)

            if chdef:
                title = chdef.get("rename",title)
                icon = chdef.get("icon")
                if icon: icon = _gh(icon)
                order = groups.index(chdef.get("group",""))
                epg_id = chdef.get("epg_id")
            else:
                if next((x for x in radioChannels if x["title"] == title), None): continue
                icon = ""
                order = 0
                epg_id = None

            params = {'good_for_fav': True, "title": title, "desc": "", "order": order, "url": url }
            if icon:
                params['icon']= icon
            ch = next((ch for ch in mindigChannels if ch["name"].strip() == title), None)
            if ch:
                params.update({"epg_id": "E"+ch["id"], "epg_prov_id": "mindigo" })
                _addepg(radioEpgs,ch["id"],params)
            elif epg_id:
                params.update({"epg_id": epg_id, "epg_prov_id": chdef["epg_prov_id"]})

            radioChannels.append(params)

        if len(tvChannels) > 0:
            tvChannels.sort(key=lambda k: (k["order"], k["title"]))
            self.tvChannels=tvChannels

        if len(radioChannels) > 0:
            radioChannels.sort(key=lambda k: (k["order"], k["title"]))
            self.radioChannels=radioChannels

        self.tvEpgs = tvEpgs
        self.radioEpgs = radioEpgs


    def getEpg(self,epgs):
        if len(epgs) == 0: return;
        try:
            sts, data = self.getApiPage(self.LIVE_URL)
            if not sts: raise Exception("Can't get LIVE channels")
            data = json_loads(data)["data"]
            mindigChannels = data.get("available",[])
            mindigChannels.extend(data.get("unavailable",[]))

            for epg in epgs:
                id = epg["id"]
                ch = next((ch for ch in mindigChannels if ch["id"] == id), None)
                if not ch: continue
                data = ch["epg"]
                start = datetime.fromtimestamp(data["startTimeStamp"]).strftime("%H:%M")
                end = datetime.fromtimestamp(data["endTimeStamp"]).strftime("-%H:%M ")
                desc = start + end + data["title"]
                for i in epg["items"]:
                    i["desc"] = desc

        except Exception: printExc()

    def listMainMenu(self, cItem):
        printDBG("MindiGoHU.listMainMenu")

        if not self.tryTologin(): return

        MAIN_CAT_TAB = [{"category":"list_tvChannels", "title": _("TV channels") },
                        {"category":"list_radioChannels", "title": _("Radio stations") },
                        {"category":"list_brands", "title": "MindiGo "+_("Videos") },
                        {"category":"list_mtvavideos", "title": "MTVA "+ _("Videos") },
                        {"category":"list_m3videos", "title": "M3 "+ _("Videos"), "url": "P" },
                        {"category":"list_m3videos", "title": "M3+ "+ _("Videos"), "url": "D" },
                        {"category":"list_mtvaarch", "title": "MTVA Archivum "+ _("Videos") } ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listTVChannels(self, cItem):
        printDBG("MindiGoHU.listTVChannels")
        self.getEpg(self.tvEpgs)
        for i in self.tvChannels:
            self.addVideo(i)

    def listRadioChannels(self, cItem):
        printDBG("MindiGoHU.listRadioChannels")
        for i in self.radioChannels:
            self.addAudio(i)

    def listBrands(self, cItem):
        printDBG("MindiGoHU.listBrands")

        params=dict(cItem)
        params.update( {"category":"list_genres", "title": _("All"), "url": "" } )
        self.addDir(params)

        try:
            sts, data = self.getApiPage(self.BRANDS_URL)
            if not sts: raise Exception("Can't get brands")

            data = json_loads(data)["data"]
            for i in data:
                params=dict(cItem)
                params.update( {"category":"list_genres", "title": i["name"], "desc": i["description"], "url": "&brand="+i["id"]} )
                self.addDir(params)
        except Exception: printExc()


    def listMtvaVideos(self, cItem):
        printDBG("MindiGoHU.listMtvaVideos")
        # get MTVA video channels
        try:
            sts, data = self.cm.getPage(self.HBBTV_MTVA_URL, self.hbbtvParams)
            if not sts: raise Exception("Can't get MTVA page")
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<span type="link" href=', '/span>', False)
            for i in data:
                url = self.cm.ph.getDataBeetwenMarkers(i, '"', '"', False)[1]
                if not url or not url.startswith("http"): continue
                title = self.cm.ph.getDataBeetwenMarkers(i, '>', '<', False)[1]
                if not title: continue
                params = {'good_for_fav': True, "title": title, "desc": "", "url": "D"+url }
                self.addVideo(params)

        except Exception: printExc()

    def listM3Videos(self, cItem):
        printDBG("MindiGoHU.listM3Videos")
        # get M3 videos
        url = cItem["url"] 
        kind = url[:1] 

        try:
            if kind == "P": 
                url = self.M3_PROGRAM_URL
            elif kind == "D":
                url = self.M3_DAILYPROGRAM_URL
            elif kind == "A":
                url = self.M3_OPEN_URL + url[1:]

            sts, data = self.getPage(url)
            if not sts: raise Exception("Can't get M3 program page")
            data = json_loads(data)["docs" if kind == "A" else "program" ]
            for i in data:
                url = "v"+i["id"]

                if next((x for x in self.currList if x["url"] == url), None): continue
                
                title = i["title"]
                subtitle = i["subtitle"]
                if subtitle:
                    title = title + " - " + subtitle
                desc = i["description"]
                params = {'good_for_fav': True, "title": title, "desc": desc, "url": url, "icon": self.M3_IMAGE_URL + i["id"]}
                self.addVideo(params)

        except Exception: printExc()

    def listMTVAArch(self, cItem):
        printDBG("MindiGoHU.listMTVAArch")
        try:
            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Tévéfilmek és sorozatok"), "url": "A" + "M3-VMOpdsOpZmlsbWVrIMOpcyBzb3JvemF0b2s" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Családi filmek"), "url": "A" + "M3-Q3NhbMOhZGkgZmlsbWVr" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Kabaré, vígjáték"), "url": "A" + "M3-S2FiYXLDqSwgdsOtZ2rDoXTDqWs" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Romantikus"), "url": "A" + "M3-Um9tYW50aWt1cw" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Bűnügyi filmek és sorozatok"), "url": "A" + "M3-QsWxbsO8Z3lpIGZpbG1layDDqXMgc29yb3phdG9r" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Játék és vetélkedő"), "url": "A" + "M3-SsOhdMOpayDDqXMgdmV0w6lsa2VkxZE" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Színház"), "url": "A" + "M3-U3rDrW5ow6F6" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Ismeretterjesztő"), "url": "A" + "M3-SXNtZXJldHRlcmplc3p0xZE" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Zene"), "url": "A" + "M3-WmVuZQ" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Mesék"), "url": "A" + "M3-TWVzw6lr" } )
            self.addDir(params)

            params=dict(cItem)
            params.update( {"category":"list_m3videos", "title": _("Sport"), "url": "A" + "M3-U3BvcnQ" } )
            self.addDir(params)

        except Exception: printExc()



    def listGenres(self, cItem):
        try:
            url = cItem["url"]
            sts, data = self.getApiPage(self.GENRES_URL+url)
            if not sts: raise Exception("Can't get GENRE page")

            params=dict(cItem)
            params.update( {"category":"list_types", "title": _("All") } )
            self.addDir(params)
            data = json_loads(data)["data"]
            for i in data:
                params=dict(cItem)
                params.update( {"category":"list_types", "title": i["title"], "url": url+"&genre="+i["id"]} )
                self.addDir(params)
        except Exception: printExc()

    def listTypes(self, cItem):
        params=dict(cItem)
        params.update( {"category":"list_videos", "title": _("All") } )
        self.addDir(params)

        url = cItem["url"]

        params=dict(cItem)
        params.update( {"category":"list_videos", "title": _("Film"), "url": url+"&type=film"  } )
        self.addDir(params)

        params=dict(cItem)
        params.update( {"category":"list_videos", "title": _("Series"), "url": url+"&type=series"  } )
        self.addDir(params)

    def listVideos(self, cItem):
        page=cItem.get("page",0)
        cItem.pop("page",None)
        url = cItem["url"]
        try:
            url = self.VIDEOS_URL+url
            if page == 0: url = url + "&hot_count=3&fresh_count=3"
            else: url = url + "&page="+str(page+1)
            sts, data = self.getApiPage(url)
            if not sts: raise Exception("Can't get GENRE page")

            data = json_loads(data)["data"]
            if page == 0:
                videos = data.get("fresh",[])
                videos.extend( data.get("hot",[]))
            else: videos = []

            count = data["other"]["count"]
            others = data["other"]["list"]
            videos.extend(others)
            for i in videos:
                params=dict(cItem)
                if "image" in i and len(i["image"]) > 0:
                    icon = i["image"][0].get("simple")

                params.update({'good_for_fav': True, "title": i["title"], "url": "V"+i["id"], "epg_id": "V"+i["id"], "epg_prov_id": "mindigo" } )
                if icon:
                    params["icon"] = icon

                self.addVideo(params)
            if page*12+len(others) < count:
                params = dict(cItem)
                params.update({'title':_("Next page"), 'page': page+1})
                self.addDir(params)

        except Exception: printExc()

    def getLinksForVideo(self, cItem):
        url = cItem['url']
        printDBG("MindiGoHU.getLinksForVideo url[%s]" % url)
        videoUrls = []
        self.tryTologin()
        try:
            if url[:1] == "Y":
                return self.up.getVideoLinkExt(url[1:])  
            
            
            if url == "mm3" or url[:1] == "v":
                if os.path.exists(self.COOKIE_FILE):
                    token = self.cm.getCookieItem(self.COOKIE_FILE, "MtvaArchivumToken")
                else:
                    token = ""
                if not token:
                    sts, data = self.getPage(self.M3_URL)
                    if not sts: return []
                    token = self.cm.getCookieItem(self.COOKIE_FILE, "MtvaArchivumToken")
                if url == "mm3":
                    url = self.M3_STREAM_URL + "live" 
                else:
                    url = self.M3_STREAM_URL + url[1:] 
     
                sts, data = self.getPage(url)
                if not sts: return []
                data = self.cm.ph.getDataBeetwenMarkers(data, '"url":"', '"', False)[1]
                data = data.replace('\/', '/').replace("HLS.smil", "nodrm.smil")
                uri = strwithmeta(data,{'User-Agent':self.HEADER ['User-Agent']} )
                return getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                
            if url[:1] == "D":
                if not url.endswith(".m3u"):
                    data = url[1:].split(",")
                else:
                    sts, data = self.cm.getPage(url[1:], self.hbbtvParams)
                    if not sts: return []
                    data = data.replace("\r\n", "\n").split("\n")
                if len(data) == 1:
                    return [{'name':'direct link', 'url': data[0]} ]
                for i in data:
                    if not i.startswith("http"): continue
                    if i.endswith('.mp3'):
                        videoUrls.append({'name': "mp3", 'url':i})
                        continue;
                    if i.endswith('.aac'):
                        videoUrls.append({'name': "aac", 'url':i})
                        continue;
                    if i.endswith('.ogg'):
                        videoUrls.append({'name': "ogg", 'url':i})
                return videoUrls
            if url[:1] == "V":
                sts, data = self.getApiPage(self.VOD_URL.format( url[1:] ))
                if not sts:
                    try:
                        data = json_loads(data)["errorMessage"]
                        if data: SetIPTVPlayerLastHostError( data )
                    except: pass
                    return []
                data = json_loads(data)
                link = data["data"]["url"]
            else:
                link = cItem.get("link")
                expires = cItem.get("expires",0)

                if not link or expires < time():
                    cItem.pop("link",None)
                    cItem.pop("expires",None)
                    if url[:1] in ["M","R"]:
                        sts, data = self.getApiPage(self.STREAM_URL.format( url[1:] ))
                        if not sts:
                            try:
                                data = json_loads(data)["errorMessage"]
                                if data: SetIPTVPlayerLastHostError( data )
                            except: pass
                            return []
                        data = json_loads(data)
                        link = data["data"]["url"]
                    elif url[:1] == "H":
                        sts, link = self.cm.getPage(self.HBBTV_MEDIA_URL.format( url[1:] ), self.hbbtvParams)
                        if not sts: return []
                    elif url[:1] == "K":
                        sts, link = self.cm.getPage(self.MTVA_CHANNEL_URL + url[1:], self.hbbtvParams)
                        if not sts: return []
                        link = self.cm.ph.getDataBeetwenMarkers(link, '"file": "', '"', False)[1]
                        link = "https:" + link.replace("\/","/")

                    else: return []
                    expires = int(time())+21600
                    cItem["link"] = link
                    cItem["expires"] = expires

            if url[:1] in  ["R","V","K"]:
                uri = urlparser.decorateParamsFromUrl(link)
                protocol = uri.meta.get('iptv_proto', '')
                printDBG("PROTOCOL [%s] " % protocol)
                if protocol == 'm3u8':
                    return getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
            return [{'name':'direct link', 'url': link} ]

        except Exception(): printExc()
        return []

    def getFavouriteData(self, cItem):
        printDBG('MindiGoHU.getFavouriteData')
        params = {'type':cItem['type'], 'category':cItem.get('category', ''), 'title':cItem['title'], 'url':cItem['url'], 'icon':cItem['icon']}
        return json_dumps(params)

    def getLinksForFavourite(self, fav_data):
        printDBG('MindiGoHU.getLinksForFavourite')
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception: printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('MindiGoHU.setInitListFromFavouriteItem')
        try:
            params = json_loads(fav_data)
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def getArticleContent(self, cItem):
        printDBG("MindiGoHU.getArticleContent [%s]" % cItem)
        url = cItem["url"]
        desc = cItem.get("desc","")
        other_info = {}
        if "epg_id" in cItem:
            epg_provider = self.getEPGProviderById( cItem["epg_prov_id"])
            item = epg_provider.getEPGItem( cItem["epg_id"] )
            if item:
                title = item["title"]
                if title:
                    title = title + "[/br]"
                desc = title + item["desc"]
                other_info = item["other_info"]

        retTab = {'title':cItem['title'], 'text': desc, 'images':[{'title':'', 'url':self.getFullIconUrl(cItem.get('icon'))}] }
        if other_info:
            retTab["other_info"] = other_info
        return [retTab]

    def tryTologin(self):
        printDBG('tryTologin start')

        needLogin = False
        if self.login != config.plugins.iptvplayer.mindigohu_login.value or self.password != config.plugins.iptvplayer.mindigohu_password.value:
            needLogin = True
            self.login = config.plugins.iptvplayer.mindigohu_login.value
            self.password = config.plugins.iptvplayer.mindigohu_password.value

        if not needLogin and self.token: return True

        if '' == self.login.strip() or '' == self.password.strip():
            printDBG('tryTologin wrong login data')
            self.sessionEx.open(MessageBox, _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.') % self.getMainUrl(), type = MessageBox.TYPE_ERROR, timeout = 10 )
            return False

        try:
            if os.path.exists(self.COOKIE_FILE): cj = self.cm.getCookie(self.COOKIE_FILE)
            else: cj = cookielib.MozillaCookieJar()

            cookieNames = ["token", "refreshToken", "loginHash" ]
            cookies = [None, None, None]

            for cookie in cj:
                if cookie.domain == 'vpv.jf7ekt7r6rbm2.hu':
                    try:
                        i = cookieNames.index(cookie.name)
                        if cookies[i]: cookie.discard = True
                        else: cookies[i] = cookie
                    except ValueError: pass
            for i, cookie in enumerate(cookies):
                if not cookie:
                    cookie = cookielib.Cookie(version=0, name=cookieNames[i], value=None, port=None, port_specified=False,
                        domain='vpv.jf7ekt7r6rbm2.hu', domain_specified=False, domain_initial_dot=False, path='/', path_specified=True, secure=True,
                        expires=2147483647, discard=False, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
                    cookies[i] = cookie
                    cj.set_cookie(cookie)
            token = cookies[0]
            refresh = cookies[1]
            hash = cookies[2]
            needLogin = needLogin or not(token.value and refresh.value and hash.value
                        and sha1(self.login+self.password+token.value+refresh.value).hexdigest() == hash.value)
            if not needLogin:
                printDBG("extend")
                data = {"app_version": "1.0.21",
                  "platform": "web",
                  "refreshToken": refresh.value}

                sts, data = self.cm.getPage(self.EXTEND_URL, self.apiParams, data )
                if sts:
                    data = json_loads(data)
                elif self.cm.meta.get('status_code') == 400: needLogin = True
                else:  raise Exception('Can not Get extend page!')
            if needLogin:
                printDBG('login')

                data = {"app_version": "1.0.21",
                        'email': self.login,
                        'password': self.password,
                        'platform': 'web'}
                sts, data = self.cm.getPage(self.LOGIN_URL, self.apiParams, data)
                if not sts: raise Exception('Can not Get Login page!')
                data = json_loads(data)
            token.value = data["token"]
            refresh.value = data["refreshToken"]
            hash.value = sha1(self.login+self.password+token.value+refresh.value).hexdigest()
            cj.save(self.COOKIE_FILE)
            self.loggedIn = True
            self.token = token.value
            self.getChannels()
            return True
        except:
            printExc()
            self.sessionEx.open(MessageBox, _('Login failed.'), type = MessageBox.TYPE_ERROR, timeout = 10)
        #self.userProducts = set()
        return False

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')

        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({"name":"category"})
        elif category == "list_tvChannels":
            self.listTVChannels(self.currItem)
        elif category == "list_radioChannels":
            self.listRadioChannels(self.currItem)
        elif category == "list_brands":
            self.listBrands(self.currItem)
        elif category == "list_mtvavideos":
            self.listMtvaVideos(self.currItem)
        elif category == "list_m3videos":
            self.listM3Videos(self.currItem)
        elif category == "list_mtvaarch":
            self.listMTVAArch(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_types":
            self.listTypes(self.currItem)
        elif category == "list_videos":
            self.listVideos(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


    def getEPGProviderById(self, provId):
        printDBG("MindiGoHU.getEPGProviderById")
        if provId == "mindigo":
            return self.epgProvider
        elif provId == "porthu":
            return self.epgProvider_porthu


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MindiGoHU(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] in ["video","radio"]:
            return True
        return False
##            != 'video' and cItem['category'] not in ['list_playlist','list_episodes','list_subcategories']):
##            return False
##        return True

