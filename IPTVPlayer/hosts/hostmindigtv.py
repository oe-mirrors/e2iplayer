# -*- coding: utf-8 -*-
###################################################
# 2019-03-03 Celeburdi
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
#from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import os
#import datetime
from datetime import datetime, timedelta
import time
import zlib
import urllib
import base64
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

def gettytul():
    return 'https://www.mindigtv.hu/'

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
   
def _getMindigChannelDefs():
    return [
        {"title": "M1 HD", "icon": _gh("m1hd.jpg"), "group" : "main" },
        {"title": "M2 HD", "icon": _gh("m2hd.jpg"), "group" : "child" },
        {"title": "Duna HD", "icon": _gh("dunahd.jpg"), "group" : "main" },
        {"title": "Duna World", "icon": _gh("dunaworld.jpg"), "group" : "main" },
        {"title": "RTL Klub", "icon": _gh("rtlklub-wapadedrud.jpg"), "group" : "main" },
        {"title": "TV2", "icon": _gh("tv2-wapadedrud.jpg"), "group" : "main" },

        {"title": "Kossuth rádió", "icon": _gh("kossuthradio.jpg"), "group" : "main" },
        {"title": "Petőfi rádió", "icon": _gh("petofiradio.jpg"), "group" : "main" },
        {"title": "Bartók rádió", "icon": _gh("bartokradio.jpg"), "group" : "main" },

        {"title": "AXN", "icon": _gh("axn.jpg"), "group" : "movie", "force": True },
        {"title": "Cool", "icon": _gh("cool-wapadedrud.jpg"), "group" : "movie" },
        {"title": "film+", "icon": _gh("filmcafe.jpg"), "group" : "movie" },
        {"title": "National Geographic", "icon": _gh("nationalgeographic.jpg"), "group" : "docu" },
        {"title": "Disney Channel", "icon": _gh("disneychannel.jpg"), "group" : "child" },
        {"title": "Hír TV", "icon": _gh("hirtv.jpg"), "group" : "news" },
        {"title": "ATV", "icon": _gh("atv-wapadedrud.jpg"), "group" : "news" },
        {"title": "VIASAT3", "icon": _gh("viasat3.jpg"), "group" : "movie" },
        {"title": "Comedy Central", "icon": _gh("comedycentral.jpg"), "group" : "movie" },
        {"title": "Spektrum", "icon": _gh("spektrum.jpg"), "group" : "docu" },
        {"title": "Cartoon Network", "icon": _gh("cartoonnetwork.jpg"), "group" : "child" },
        {"title": "Da Vinci TV", "icon": _gh("davincilearning.jpg"), "group" : "docu" },

        {"title": "Dankó rádió", "icon": _gh("dankoradio.jpg"), "group" : "main" },

        {"title": "Fit csomag", "rename": "Fit HD", "icon": _gh("fithd.jpg"), "group" : "sport", "force": True },
        {"title": "M3", "icon": _gh("m3.jpg"), "group" : "movie", "force": True },

        {"title": "D1 TV", "icon": _gh(""), "group" : "movie"},
        {"title": "RTLII", "icon": _gh("rtl2-wapadedrud.jpg"), "group" : "main" },
        {"title": "Super TV2", "icon": _gh("supertv2.jpg"), "group" : "main" },
        {"title": "RTL+", "icon": _gh("rtlplus.jpg"), "group" : "main" },
        {"title": "Paramount Channel", "icon": _gh("paramountchannel.jpg"), "group" : "movie" },
        {"title": "Sláger TV", "icon": _gh("slagertv.jpg"), "group" : "music", "force": True },
        {"title": "Discovery Channel", "icon": _gh("discoverychannel.jpg"), "group" : "docu" },
        {"title": "TLC", "icon": _gh("tlc.jpg"), "group" : "docu" },
        {"title": "Viasat History", "icon": _gh("viasathistory.jpg"), "group" : "docu" },
        {"title": "VIASAT6", "icon": _gh("viasat6.jpg"), "group" : "movie", "force": True },
        {"title": "Filmbox", "icon": _gh("filmbox.jpg"), "group" : "movie" },
        {"title": "Echo TV", "icon": _gh("echotv.jpg"), "group" : "news" },
        {"title": "Animal Planet", "icon": _gh("animalplanet.jpg"), "group" : "docu" },
        {"title": "Discovery Science", "icon": _gh("discoveryscience-clivebesle.jpg"), "group" : "docu" },
        {"title": "NatGeo Wild", "icon": _gh("natgeowild.jpg"), "group" : "docu" },
        {"title": "Fishing & Hunting", "icon": _gh("fishingandhunting.jpg"), "group" : "sport" },
        {"title": "Brazzers", "icon": _gh("brazzerstv.jpg"), "group" : "porno" },
        {"title": "Filmbox Premium", "icon": _gh("filmboxpremium.jpg"), "group" : "movie" },
        {"title": "Ozone Network", "icon": _gh("ozonetv.jpg"), "group" : "docu" },
        {"title": "Bonum TV", "icon": _gh(""), "group" : "religious" },
        {"title": "M4 Sport HD", "icon": _gh("m4sport.jpg"), "group" : "sport" },
        {"title": "Nickelodeon", "icon": _gh("nickelodeon.jpg"), "group" : "child" },
        {"title": "PAX TV", "icon": _gh("paxtv.jpg"), "group" : "religious" },
        {"title": "Balaton TV", "icon": _gh("balatontv.jpg"), "group" : "regional" },
        {"title": "Smile of a Child / Juce TV", "icon": _gh("smileofachild.jpg"), "group" : "child" },
        {"title": "M5 HD", "icon": _gh("m5.jpg"), "group" : "main" },
        {"title": "Izaura TV", "icon": _gh("izauratv.jpg"), "group" : "movie" },
        {"title": "Zenebutik", "icon": _gh("zenebutik.jpg"), "group" : "music" },
        {"title": "Mozi+", "icon": _gh("moziplus.jpg"), "group" : "movie" },
        {"title": "Prime", "icon": _gh("prime.jpg"), "group" : "main"},
        {"title": "FEM3", "icon": _gh("fem3.jpg"), "group" : "movie" },
        {"title": "Spiler", "icon": _gh("spiler1tv.jpg"), "group" : "sport" },
        {"title": "RTL Spike", "icon": _gh("rtlspike.jpg"), "group" : "movie" },
        {"title": "Heti TV", "icon": _gh("hetitv.jpg"), "group" : "regional" },
        {"title": "Fix TV HD", "icon": _gh("fixtv.jpg"), "group" : "regional" },
        {"title": "Humor+", "icon": _gh("humorplusz.jpg"), "group" : "movie" },
        {"title": "Kiwi TV", "icon": _gh("kiwitv.jpg"), "group" : "child" },
        {"title": "LiChi TV", "icon": _gh("lichitv.jpg"), "group" : "docu" },
        {"title": "AMC", "icon": _gh("amc.jpg"), "group" : "movie" },
        {"title": "Spektrum Home", "icon": _gh("spektrumhome.jpg"), "group" : "docu" },
        {"title": "Sport1", "icon": _gh("sport1-duslelaslu.jpg"), "group" : "sport" },
        {"title": "TV Paprika", "icon": _gh("tvpaprika-wapadedrud.jpg"), "group" : "docu" },
        {"title": "RTL GOLD", "icon": _gh("rtlgold.jpg"), "group" : "main" },
        {"title": "SuperOne", "icon": _gh("superonehd.jpg"), "group" : "porno" },
        {"title": "FILM4", "icon": _gh("film4.jpg"), "group" : "movie" },
        {"title": "TV4", "icon": _gh("tv4-wapadedrud.jpg"), "group" : "movie" },
        {"title": "STORY4", "icon": _gh("story4.jpg"), "group" : "movie" },

        {"title": "FixTV", "rename": "Fix TV HD", "icon": _gh("fixtv.jpg"), "group" : "regional" },
        {"title": "The Fishing & Hunting Channel", "icon": _gh("fishingandhunting.jpg"), "group" : "sport" },
        {"title": "Fit HD", "icon": _gh("fithd.jpg"), "group" : "sport", "force": True },
        {"title": "C Music TV", "icon": _gh("cmusictv.jpg"), "group" : "music" },
        {"title": "iConcerts HD", "icon": _gh("iconcerts.jpg"), "group" : "music" },
        {"title": "DOQ TV", "icon": _gh("doq.jpg"), "group" : "docu" },
        {"title": "National Geographic Wild", "rename": "NatGeo Wild", "icon": _gh("natgeowild.jpg"), "group" : "docu" },
        {"title": "Dankó Rádió", "rename": "Dankó rádió", "icon": _gh("dankoradio.jpg"), "group" : "main" },
        {"title": "Duna World Rádió", "icon": _gh("dunaworldradio.jpg"), "group" : "main" },
        {"title": "Nemzetiségi adások", "icon": _gh("nemzetisegiadasok.jpg"), "group" : "main" },
        {"title": "Parlamenti adások", "icon": _gh("parlamentiadasok.jpg"), "group" : "main" },
        {"title": "Radio Swiss Classic (fr)", "icon": _gh("swissclassic.jpg"), "group" : "music" },
        {"title": "Radio Swiss Classic (ger)", "icon": _gh("swissclassic.jpg"), "group" : "music" },
        {"title": "Radio Swiss Jazz", "icon": _gh("swissjazz.jpg"), "group" : "music" },
        {"title": "Radio Swiss Pop", "icon": _gh("swisspop.jpg"), "group" : "music" },

    ]

class MindigTVHU(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history":"mindigtv.hu", "cookie":"mindigtvhu.cookie"})

        self.DEFAULT_ICON_URL = _gh("mindigtvdefault.jpg")
        self.HEADER = self.cm.getDefaultHeader()
        self.MAIN_URL = "https://www.mindigtv.hu/"

        self.MINDIG_URL = zlib.decompress(base64.b64decode(
            "eJzLKCkpsNLXTyzI1MvNzEvJTC8p00ssKCguSS0q1stN1S8z0jfUzyjVT87PK0nNK9EHAK6lEV8="))
        self.MINDIG_CHANNEL_URL = self.MINDIG_URL+zlib.decompress(base64.b64decode(
            "eJxLqoxPzs8rSc0r0XfOSMzLS83RyyrOzwMAbS4JBg=="))
        self.MINDIG_MEDIA_URL = self.MINDIG_URL+zlib.decompress(base64.b64decode(
            "eJwrLilKTcwtjk+qjE/OSMzLS83Rr67Vz8gp1ssqzs8DALz9C/c="))
        self.MINDIG_EPG_URL = self.MINDIG_URL+zlib.decompress(base64.b64decode(
            "eJwrzsgvL45PqoxPzkjMy0vN0a+uBSK9rOL8PACamArd"))

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

        self.MINDIG_HEADER = dict(self.HEADER)
        self.HBBTV_HEADER = dict(self.HEADER)
        self.HBBTV_HEADER.update( {"User-Agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 2.3) AppleWebkit/538.1 (KHTML, like Gecko) SamsungBrowser/1.0 TV Safari/538.1"} )

        self.mindigiParams = {"header":self.MINDIG_HEADER}
        self.hbbtvParams = {"header":self.HBBTV_HEADER}

        self.loggedIn = False

        self.defaultParams = {"header":self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        self.tvChannels = None
        self.radioChannels = None
        self.videos = None
        
        self.tvEpgs = None
        self.radioEpgs = None

 
    def getFullIconUrl(self, url):
        if not url: return self.DEFAULT_ICON_URL
        return url

    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getEpg(self, epg):
        data = epg.get("data")
        t = int(time.time())
        d = datetime.now()
        date = d.strftime('%Y%m%d')
        try:
            if not data or epg.get("date") != date:
                id =  epg["id"]
                sts, data = self.cm.getPage(self.MINDIG_EPG_URL.format( id, date ), self.mindigiParams)
                if not sts: raise Exception("Can't get EPG page")
                data = json_loads(data)
                data = data["data"]["channels"][id]
                if len(data) == 0:
                    epg["data"] = []
                    return
                if data[0]["timestamp"] > t:
                    d = d - timedelta(1)
                    sts, prevdata = self.cm.getPage(self.MINDIG_EPG_URL.format( id , d.strftime('%Y%m%d') ), self.mindigiParams)
                    if not sts: raise Exception("Can't get EPG page")             
                    prevdata = json_loads(data)
                    prevdata = data["data"]["channels"][id]
                    prevdata.extend(data)
                    data = prevdata
                epg.update( {"data": data, "date": date} )

            if len(data) == 0: return
            
            i=next((i for i in data if i["timestamp"] <= t and i["next_timestamp"] > t), None)
            if not i: return
            for item in epg["items"]:
                item["desc"] = i["title"]+" "+i["time"]+"-"+i["next_time"] + "\n"+i["description"]
        except Exception: printExc()

    def getChannels(self):
        printDBG('MindigTVHU.getChannels')
        self.tvChannels = []
        self.radioChannels = []
        self.videos = []
        self.epgs = []
        tvChannels = []
        radioChannels = []
        videos = []
        tvEpgs = []
        radioEpgs = []
        groups = ["","main","movie","news","docu","child","sport","music","regional","religious","porno","info"]
        chdefs = _getMindigChannelDefs()

        # get MinDigTV TV/radio channels
        mindigChannels = []
        try:
            sts, data = self.cm.getPage(self.MINDIG_CHANNEL_URL, self.mindigiParams)
            if not sts: raise Exception("Can't get MinDig TV channels")
            mindigChannels = json_loads(data)
            for i in mindigChannels:
                title = i['title']
                chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)
                if chdef:
                    if "rename" in chdef:
                        title = chdef["rename"]
                        i["title"] = title
                    icon = chdef.get("icon")
                    order = groups.index(chdef.get("group",""))
                    force = chdef.get("force",False)
                else:
                    icon = ""
                    order = 0
                    force = False
                if not icon:
                    icon = i["thumbnail"]

                if not i["has_live"] and not force: continue

                params = {'good_for_fav': True, "title": title, "desc": "", "order": order }
                if icon:
                    params['icon']= icon
                if i["is_radio"]:
                    if i["has_epg"]:
                        radioEpgs.append({"id": str(i["id"]), "items": [params]})
                        params["epg"] = len(radioEpgs)-1
                    params["url"] = "D"+ i["streams"][0]["url"]
                    radioChannels.append(params)
                else:
                    if i["has_epg"]:
                        tvEpgs.append({"id": str(i["id"]), "items": [params]})
                        params["epg"] = len(tvEpgs)-1
                    params["url"] = "M"+str(i['id'])
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
                    order = groups.index(chdef.get("group",""))
                else:
                    icon = ""
                    order = 0
                params = {'good_for_fav': True, "title": title + " (HbbTV)", "desc": "", "order": order, "url": "H"+url }
                if icon:
                    params['icon']= icon
                ch = next((ch for ch in mindigChannels if ch["title"] == title), None)
                if ch and ch["has_epg"]:
                    params["epg"]=_addepg(tvEpgs,str(ch["id"]),params)
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
                        order = groups.index(chdef.get("group",""))
                    else:
                        icon = ""
                        order = 0
                    params = {'good_for_fav': True, "title": title + " (HbbTV)", "desc": "", "order": order, "url": url }
                    if icon:
                        params['icon']= icon
                    ch = next((ch for ch in mindigChannels if ch["title"] == title), None)
                    if ch and ch["has_epg"]:
                        params["epg"]=_addepg(tvEpgs,str(ch["id"]),params)
                    tvChannels.append(params)
        except Exception: printExc()

        # get HbbTV radio channels
        try:
            sts, data = self.cm.getPage(self.HBBTV_RADIO_URL, self.hbbtvParams)
            if not sts: raise Exception("Can't get HbbTV radio channels")
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, "videos[", ";", False)
            for i in data:
                v = self.cm.ph.getAllItemsBeetwenMarkers(i, '"', '"', False)
                if len(v) < 3: continue
                title = v[2]
                url = "D"+v[0]
                               
                chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)
                if chdef:
                    title = chdef.get("rename",title)
                    icon = chdef.get("icon")
                    order = groups.index(chdef.get("group",""))
                else:
                    icon = ""
                    order = 0

                if next((x for x in radioChannels if x["title"] == title), None): continue
                   
                params = {'good_for_fav': True, "title": title, "desc": "", "order": order, "url": url }
                if icon:
                    params['icon']= icon
                ch = next((ch for ch in mindigChannels if ch["title"] == title), None)
                if ch and ch["has_epg"]:
                    params["epg"]=_addepg(radioEpgs,str(ch["id"]),params)
                radioChannels.append(params)
        except Exception: printExc()

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
                videos.append(params)
                
        except Exception: printExc()
            
        if len(tvChannels) > 0:
            tvChannels.sort(key=lambda k: (k["order"], k["title"]))
            self.tvChannels.extend(tvChannels)

        if len(radioChannels) > 0:
            radioChannels.sort(key=lambda k: (k["order"], k["title"]))
            self.radioChannels.extend(radioChannels)

        self.videos = videos
        
        self.tvEpgs = tvEpgs
        self.radioEpgs = radioEpgs
        
    
    def listMainMenu(self, cItem):
        printDBG("MindigTVHU.listMainMenu")
        MAIN_CAT_TAB = [{"category":"list_tvChannels", "title": _("TV channels") },
                        {"category":"list_radioChannels", "title": _("Radio stations") },
                        {"category":"list_videos", "title": _("Videos") }]

        self.listsTab(MAIN_CAT_TAB, cItem)
        self.tryTologin()

    def listTVChannels(self, cItem):
        printDBG("MindigTVHU.listTVChannels")
        for i in self.tvEpgs:
            self.getEpg(i)
        for i in self.tvChannels:
            self.addVideo(i)

    def listRadioChannels(self, cItem):
        printDBG("MindigTVHU.listRadioChannels")
        for i in self.radioEpgs:
            self.getEpg(i)
        for i in self.radioChannels:
            self.addAudio(i)

    def listVideos(self, cItem):
        printDBG("MindigTVHU.listVideos")
        for i in self.videos:
            self.addVideo(i)

    def getLinksForVideo(self, cItem):
        url = cItem['url']
        printDBG("MindigTVHU.getLinksForVideo url[%s]" % url)
        videoUrls = []
        self.tryTologin()
        try:
            if url[:1] == "D":
                if not url.endswith(".m3u"):
                   videoUrls.append({'name':'direct link', 'url':url[1:]})
                   return videoUrls
                sts, data = self.cm.getPage(url[1:], self.mindigiParams)
                if not sts: return videoUrls
                data = data.replace("\r\n", "\n").split("\n")
                for i in data:
                    if not i.startswith("http"): continue
                    if i.endswith('.mp3'):
                        videoUrls.append({'name': "mp3", 'url':i})
                    if i.endswith('.aac'):
                        videoUrls.append({'name': "aac", 'url':i})
                return videoUrls
            
            link = cItem.get("link")
            expires = cItem.get("expires",0)
            if not link or expires < time.time():
                cItem.pop("link",None)
                cItem.pop("expires",None)
                if url[:1] == "M":
                    sts, data = self.cm.getPage(self.MINDIG_MEDIA_URL.format( url[1:] ), self.mindigiParams)
                    if not sts: return videoUrls
                    data = json_loads(data)
                    link = data["url"]
                elif url[:1] == "H":
                    sts, link = self.cm.getPage(self.HBBTV_MEDIA_URL.format( url[1:] ), self.hbbtvParams)
                    if not sts: return videoUrls
                else: return videoUrls 
                expires = int(time.time())+21600 
                cItem["link"] = link
                cItem["expires"] = expires
                   
            uri = urlparser.decorateParamsFromUrl(link)
            protocol = uri.meta.get('iptv_proto', '')
            printDBG("PROTOCOL [%s] " % protocol)
            if protocol == 'm3u8':
                retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({'name':'direct link', 'url':link})
        except Exception(): printExc()
        return videoUrls

    def getFavouriteData(self, cItem):
        printDBG('MindigTVHU.getFavouriteData')
        params = {'type':cItem['type'], 'category':cItem.get('category', ''), 'title':cItem['title'], 'url':cItem['url'], 'icon':cItem['icon']}
        return json_dumps(params)


    def getArticleContent(self, cItem):
        printDBG("MindigTVHU.getArticleContent [%s]" % cItem)
        if cItem["type"] == "video":
            if "epg" in cItem: self.getEpg(self.tvEpgs[cItem["epg"]])
        elif cItem["type"] == "audio":
            if "epg" in cItem: self.getEpg(self.radioEpgs[cItem["epg"]])
        retTab = {'title':cItem['title'], 'text': cItem['desc'], 'images':[{'title':'', 'url':self.getFullIconUrl(cItem.get('icon'))}]}
        return [retTab]


    def tryTologin(self):
        printDBG("MindigTVHU.tryTologin")

        if not self.tvChannels: self.getChannels()


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
            self.listMainMenu({'name':'category'})
        elif category == 'list_tvChannels':
            self.listTVChannels(self.currItem) 
        elif category == 'list_radioChannels':
            self.listRadioChannels(self.currItem) 
        elif category == 'list_videos':
            self.listVideos(self.currItem) 
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MindigTVHU(), True, [])

    def withArticleContent(self, cItem):
        return cItem['type'] == 'video' or cItem['type'] == "audio"

