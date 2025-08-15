# -*- coding: utf-8 -*-
###################################################
# 2019-04-10 Celeburdi
###################################################
HOST_VERSION = "1.1"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
import os
import datetime
import time
import zlib
import cookielib
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
config.plugins.iptvplayer.mytvtelenorhu_login    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.mytvtelenorhu_password = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Login")+":", config.plugins.iptvplayer.mytvtelenorhu_login))
    optionList.append(getConfigListEntry(_("password")+":", config.plugins.iptvplayer.mytvtelenorhu_password))
    return optionList
###################################################

def gettytul():
    return 'https://mytv.telenor.hu/'

def _gh(url):
    if not url: return ""
    return "https://celeburdi.github.io/static/icons/"+url
   
def _getChannelDefs():
    return [
        {"title": "Spíler1 TV", "icon": _gh("spiler1tv.jpg"), "group" : "sport" },
        {"title": "Sport1", "icon": _gh("sport1hd-duslelaslu.jpg"), "group" : "sport" },
        {"title": "Sport2", "icon": _gh("sport2hd-duslelaslu.jpg"), "group" : "sport" },
        {"title": "M4 Sport", "icon": _gh("m4sport.jpg"), "group" : "sport" },
        {"title": "RTL KLUB", "icon": _gh("rtlklub-wapadedrud.jpg"), "group" : "main" },
        {"title": "TV2", "icon": _gh("tv2-wapadedrud.jpg"), "group" : "main" },
        {"title": "RTL II", "icon": _gh("rtl2-wapadedrud.jpg"), "group" : "main" },
        {"title": "Super TV2", "icon": _gh("supertv2.jpg"), "group" : "main" },
        {"title": "RTL Spike", "icon": _gh("rtlspike.jpg"), "group" : "movie" },
        {"title": "Cool", "icon": _gh("cool-wapadedrud.jpg"), "group" : "movie" },
        {"title": "Investigation Discovery", "icon": _gh("investigationdiscovery.jpg"), "group" : "docu" },
        {"title": "Mozi+", "icon": _gh("moziplus.jpg"), "group" : "movie" },
        {"title": "AMC", "icon": _gh("amc.jpg"), "group" : "movie" },
        {"title": "Film+", "icon": _gh("filmplus.jpg"), "group" : "movie" },
        {"title": "Paramount Channel", "icon": _gh("paramountchannel.jpg"), "group" : "movie" },
        {"title": "RTL+", "icon": _gh("rtlplus.jpg"), "group" : "main" },
        {"title": "Prime", "icon": _gh("prime.jpg"), "group" : "main"},
        {"title": "RTL Gold", "icon": _gh("rtlgold.jpg"), "group" : "main" },
        {"title": "Izaura TV", "icon": _gh("izauratv.jpg"), "group" : "movie" },
        {"title": "Sorozat+", "icon": _gh("sorozatplusz.jpg"), "group" : "movie" },
        {"title": "Comedy Central", "icon": _gh("comedycentral.jpg"), "group" : "movie" },
        {"title": "Humor+", "icon": _gh("humorplusz.jpg"), "group" : "movie" },
        {"title": "Comedy Central Family", "icon": _gh("comedycentralfamily.jpg"), "group" : "movie" },
        {"title": "FilmCafe", "icon": _gh("filmcafe.jpg"), "group" : "movie" },
        {"title": "Minimax", "icon": _gh("minimax.jpg"), "group" : "child" },
        {"title": "Nickelodeon", "icon": _gh("nickelodeon.jpg"), "group" : "child" },
        {"title": "Euronews", "icon": _gh("euronews.jpg"), "group" : "news" },
        {"title": "Disney Channel", "icon": _gh("disneychannel.jpg"), "group" : "child" },
        {"title": "Cartoon Network", "icon": _gh("cartoonnetwork.jpg"), "group" : "child" },
        {"title": "Boomerang", "icon": _gh("boomerang.jpg"), "group" : "child" },
        {"title": "Nick Junior", "icon": _gh("nickjr.jpg"), "group" : "child" },
        {"title": "M2", "icon": _gh("m2.jpg"), "group" : "child" },
        {"title": "Kiwi TV", "icon": _gh("kiwitv.jpg"), "group" : "child" },
        {"title": "JimJam", "icon": _gh("jimjam.jpg"), "group" : "child" },
        {"title": "Discovery Channel", "icon": _gh("discoverychannel.jpg"), "group" : "docu" },
        {"title": "Spektrum", "icon": _gh("spektrum.jpg"), "group" : "docu" },
        {"title": "Viasat History", "icon": _gh("viasathistory.jpg"), "group" : "docu" },
        {"title": "Discovery Science", "icon": _gh("discoveryscience-clivebesle.jpg"), "group" : "docu" },
        {"title": "Spektrum Home", "icon": _gh("spektrumhome.jpg"), "group" : "docu" },
        {"title": "National Geographic", "icon": _gh("nationalgeographic.jpg"), "group" : "docu" },
        {"title": "Animal Planet", "icon": _gh("animalplanet.jpg"), "group" : "docu" },
        {"title": "National Geographic Wild", "icon": _gh("natgeowild.jpg"), "group" : "docu" },
        {"title": "BBC Earth", "icon": _gh("bbcearth.jpg"), "group" : "docu" },
        {"title": "Viasat Nature", "icon": _gh("viasatnature.jpg"), "group" : "docu" },
        {"title": "OzoneTv", "icon": _gh("ozonetv.jpg"), "group" : "docu" },
        {"title": "Travel Channel", "icon": _gh("travelchannel.jpg"), "group" : "docu" },
        {"title": "Viasat Explore", "icon": _gh("viasatexplore.jpg"), "group" : "docu" },
        {"title": "Fine Living", "icon": _gh("fineliving.jpg"), "group" : "docu" },
        {"title": "Viasat History/Nature HD", "icon": _gh("viasatnaturehd_viasathistoryhd.jpg"), "group" : "docu" },
        {"title": "TLC", "icon": _gh("tlc.jpg"), "group" : "docu" },
        {"title": "E! Entertainment", "icon": _gh("eentertainment.jpg"), "group" : "docu" },
        {"title": "DTX", "icon": _gh("dtx.jpg"), "group" : "docu" },
        {"title": "Lichi TV", "icon": _gh("lichitv.jpg"), "group" : "docu" },
        {"title": "LifeTv", "icon": _gh("life.jpg"), "group" : "docu" },
        {"title": "TV Paprika", "icon": _gh("tvpaprika-wapadedrud.jpg"), "group" : "docu" },
        {"title": "Food Network", "icon": _gh("foodnetwork.jpg"), "group" : "docu" },
        {"title": "FEM3", "icon": _gh("fem3.jpg"), "group" : "movie" },
        {"title": "M5", "icon": _gh("m5.jpg"), "group" : "main" },
        {"title": "M1", "icon": _gh("m1.jpg"), "group" : "main" },
        {"title": "CNN", "icon": _gh("cnn.jpg"), "group" : "news" },
        {"title": "BBC World News", "icon": _gh("bbcworldnews.jpg"), "group" : "news" },
        {"title": "VH1 Classic", "icon": _gh("vh1classic.jpg"), "group" : "music" },
        {"title": "MTV Hungary", "icon": _gh("mtv.jpg"), "group" : "music" },
        {"title": "MTV Hits", "icon": _gh("mtvhits.jpg"), "group" : "music" },
        {"title": "MTV Rocks", "icon": _gh("mtvrocks.jpg"), "group" : "music" },
        {"title": "VH1", "icon": _gh("vh1.jpg"), "group" : "music" },
        {"title": "Zenebutik", "icon": _gh("zenebutik.jpg"), "group" : "music" },
        {"title": "Muzsika TV", "icon": _gh("muzsikatv.jpg"), "group" : "music" },
        {"title": "Duna", "icon": _gh("duna.jpg"), "group" : "main" },
        {"title": "Duna World", "icon": _gh("dunaworld.jpg"), "group" : "main" },
        {"title": "MyTV Ajánló", "icon": _gh("mytvtelenordefault.jpg"), "group" : "info" },
    ]

class MyTvTelenorHU(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history":"mytvtelenor.hu", "cookie":"mytvtelenorhu.cookie"})

        self.DEFAULT_ICON_URL = _gh("mytvtelenordefault.jpg")
        self.HEADER = self.cm.getDefaultHeader()
        self.MAIN_URL = "https://mytv.telenor.hu/"
        self.API_URL = zlib.decompress(base64.b64decode(
            "eJzLKCkpKLbS109JLdPLrSwpS0pMztZLzs/VTyzI1De0BIqnJZbmlOhnlOp6hOoDAIhlECI="))
        self.API_HEADER = dict(self.HEADER)
        self.MENU_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJxLzs8rSc0r0Xf2cIz38QxzjfeNDAkzivcI1U/OyMxJKUrNs8/MS84pTUn1zE1MTy22Tc4vSy2y"
            "MjIysDI0MbDKKkhXg8onlpQUZSaVloDUJMYXFOWnlCaXAABLMyJ6"))
        self.SCHEDULES_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJw1xsEJgDAMBdBtetYBiriDC8T2lwZikCYWpHR3T77Ts1SRH4Ftwh2pkirk5mxxLDMUFkfbO7HQ"
            "ycL+xkJiCObU/OALcawzQPP/D/7zHwg="))
        self.LOGIN_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJxLTE5OLS4uyc9OzbPPyU/PzLOtrlUrSCwuLs8vSgGxi1JzU3OTUouci1JTUvNKMhNzim3TgEQq"
            "AKvFFxo="))
        self.REFRESH_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJxLTE5OLS4Oyc9OzbMvSk0rSi3OAHNsAYGhCeA="))
        self.USERPRODUCTS_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJwrLU4tKijKTylNLim2L8nPTs2zBQBQ7QfR"))
        self.USERCONTENTS_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJwrLU4tSs7PK0nNKym2L8hMKbatrlUryc9OzQMyALO1C84="))
        self.MEDIA_URL = self.API_URL+zlib.decompress(base64.b64decode(
            "eJzLTU3JTCwtytGvrrUvyc9OzbOtrgUAVFcIEA=="))

        self.apiParams = {"header":self.API_HEADER}

        self.loggedIn = False

        self.login = config.plugins.iptvplayer.mytvtelenorhu_login.value
        self.password = config.plugins.iptvplayer.mytvtelenorhu_password.value
        self.defaultParams = {"header":self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        self.channels = None
        self.userProducts = set()
        self.token = ""
        self.tokenExpires = 0
 
    def getFullIconUrl(self, url):
        if not url: return self.DEFAULT_ICON_URL
        return url

    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getChannels(self,cj):
        printDBG('MyTvTelenorHU.getChannels')
        channels = []
        chdefs = _getChannelDefs()
        groups = ["","main","movie","news","docu","child","sport","music","info"]
        sts, data = self.cm.getPage(self.MENU_URL, self.apiParams)
        if not sts: return
        try:
            data = json_loads(data)
            content = data['Content']
            list = content['List']
            for i in list:
                title = i['Title']
                url = i['Pid']
                ca_products = set(i["Attributes"]["ca_product"])
                chdef = next((chdef for chdef in chdefs if chdef["title"] == title), None)
                if chdef:
                    icon = chdef.get("icon")
                    order = groups.index(chdef.get("group",""))
                else:
                    icon = ""
                    order = 0
                if not icon:
                    icon = i['Images']['Cover'][0]['Url']

                params = {'good_for_fav': True, "title": title, "url": url, "order": order, "ca_products": ca_products}
                if icon:
                    params['icon']= icon
                channels.append(params)

        except Exception: printExc()
        self.channels = channels

    def getSchedules(self,channels):
        printDBG('MyTvTelenorHU.getSchedules')
        t = int(time.time())
        sts, data = self.cm.getPage(self.SCHEDULES_URL.format(",".join(list(map(lambda x : x['url'], channels))), t), self.apiParams)
        if not sts: return
        try:
            data = json_loads(data)
            for i in data["Content"]:
                pid = i["LiveChannelPid"]
                channel = next((channel for channel in channels if channel["url"] == pid),None)
                if channel:
                    channel.update({"desc": i.get("Title","")+"\n"+i.get("Description","") })
        except Exception: printExc()

    def getUserProducts(self):
        printDBG("MyTvTelenorHU.getUserProducts")
        self.userProducts = set()
        sts, data = self.cm.getPage(self.USERPRODUCTS_URL+self.token, self.apiParams)
        if not sts: return
        try:
            data = json_loads(data)
            for i in data["Content"]["List"]:
                self.userProducts.add(i["ProductPid"])                
        except Exception: printExc()

    def listMainMenu(self, cItem):
        printDBG("MyTvTelenorHU.listMainMenu")
        self.tryTologin()
        try:
            userproducts = self.userProducts.union(set(["PRO_SUB_TELENOR_HU_FREE","SUB_TELENOR_HU_FREEPLAYBACK"]))
            userchannels= [i for i in self.channels if i["ca_products"].intersection(userproducts) != set() ]

            if len(userchannels) == 0: return
            
            self.getSchedules(userchannels)

            userchannels.sort(key=lambda k: (k["order"], k["title"]))

            for i in userchannels:
                self.addVideo(i)
        except Exception: printExc()

    def getLinksForVideo(self, cItem):
        url = cItem['url']
        printDBG("MyTvTelenorHU.getLinksForVideo url[%s]" % url)
        videoUrls = []

        try:
            link = cItem.get("link")
            expires = cItem.get("expires",0)
            if not link or expires < time.time():
                cItem.pop("link",None)
                cItem.pop("expires",None)
                med = cItem.get("med")
                if not med:
                    sts, data = self.cm.getPage(self.USERCONTENTS_URL.format( url, self.token ), self.apiParams)
                    if not sts: return videoUrls
                    data = json_loads(data)
                    meds = data["Content"][0]["PlaybackRights"]
                    for i in meds:
                        if i["StreamingType"] != "HLS": continue
                        if not med and i["Quality"] == "SD" or i["Quality"] == "HD": med = i["Pid"]
                    if not med: return videoUrls
                    cItem["med"] = med
                sts, data = self.cm.getPage(self.MEDIA_URL.format( med, self.token), self.apiParams)
                if not sts: return videoUrls
                data = json_loads(data)
                link = data["Content"]["Url"]
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
                videoUrls.append({'name':'direct link', 'url':uri})
        except Exception(): printExc()
        return videoUrls

    def getFavouriteData(self, cItem):
        printDBG('MyTvTelenorHU.getFavouriteData')
        params = {'type':cItem['type'], 'category':cItem.get('category', ''), 'title':cItem['title'], 'url':cItem['url'], 'icon':cItem['icon']}
        return json_dumps(params)

    def getLinksForFavourite(self, fav_data):
        printDBG('MyTvTelenorHU.getLinksForFavourite')
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception: printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('MyTvTelenorHU.setInitListFromFavouriteItem')
        try:
            params = json_loads(fav_data)
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def getArticleContent(self, cItem):
        printDBG("MyTvTelenorHU.getArticleContent [%s]" % cItem)
        self.getSchedules([cItem])
        retTab = {'title':cItem['title'], 'text': cItem['desc'], 'images':[{'title':'', 'url':self.getFullIconUrl(cItem.get('icon'))}]}
        return [retTab]

    def tryTologin(self):
        printDBG('tryTologin start')

        needLogin = False
        if self.login != config.plugins.iptvplayer.mytvtelenorhu_login.value or self.password != config.plugins.iptvplayer.mytvtelenorhu_password.value:
            needLogin = True
            self.login = config.plugins.iptvplayer.mytvtelenorhu_login.value
            self.password = config.plugins.iptvplayer.mytvtelenorhu_password.value

        if not needLogin and self.token and self.tokenExpires > time.time(): return

        if '' == self.login.strip() or '' == self.password.strip():
            printDBG('tryTologin wrong login data')
            self.sessionEx.open(MessageBox, _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.') % self.getMainUrl(), type = MessageBox.TYPE_ERROR, timeout = 10 )
            emptyLogin = True
        else: emptyLogin = False
        
        try:
            if os.path.exists(self.COOKIE_FILE): cj = self.cm.getCookie(self.COOKIE_FILE)
            else: cj = cookielib.MozillaCookieJar()

            if self.channels is None: self.getChannels(cj)

            if not emptyLogin:
                cookieNames = ["Token", "RefreshToken", "loginHash" ]
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
                    sts, data = self.cm.getPage(self.REFRESH_URL+refresh.value, self.apiParams)
                    if sts:
                        data = json_loads(data)
                    elif self.cm.meta.get('status_code') == 401: needLogin = True
                    else:  raise Exception('Can not Get Account page!')
                if needLogin:
                    sts, data = self.cm.getPage(self.LOGIN_URL.format( self.login, self.password), self.apiParams)
                    if not sts: raise Exception('Can not Get Login page!')
                    data = json_loads(data)
                content = data["Content"]
                expires = content["TokenExpiration"]
                token.value = content["Token"]
                token.expires = expires
                refresh.value = content["RefreshToken"]
                refresh.expires = expires
                hash.value = sha1(self.login+self.password+token.value+refresh.value).hexdigest()
                cj.save(self.COOKIE_FILE)
                self.loggedIn = True
                self.token = token.value
                self.tokenExpires = expires
                self.getUserProducts()
                return
        except:
            printExc()
            self.sessionEx.open(MessageBox, _('Login failed.'), type = MessageBox.TYPE_ERROR, timeout = 10)
        self.token = sha256(str(time.time())).hexdigest()
        self.tokenExpires = 2147483647
        self.loggedIn = False
        self.userProducts = set()

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
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MyTvTelenorHU(), True, [])

    def withArticleContent(self, cItem):
        if (cItem['type'] != 'video' and cItem['category'] not in ['list_playlist','list_episodes','list_subcategories']):
            return False
        return True

