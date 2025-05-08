# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import re
import datetime
###################################################


def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'http://raiplay.it/'


class Raiplay(CBaseHostClass):

    def __init__(self):

        CBaseHostClass.__init__(self)

        self.MAIN_URL = 'http://raiplay.it/'
        self.MENU_URL = "http://www.rai.it/dl/RaiPlay/2016/menu/PublishingBlock-20b274b1-23ae-414f-b3bf-4bdc13b86af2.html?homejson"
        self.CHANNELS_URL = "http://www.rai.it/dl/RaiPlay/2016/PublishingBlock-9a2ff311-fcf0-4539-8f8f-c4fee2a71d58.html?json"
        self.CHANNELS_RADIO_URL = "http://rai.it/dl/portaleRadio/popup/ContentSet-003728e4-db46-4df8-83ff-606426c0b3f5-json.html"
        self.EPG_URL = "http://www.rai.it/dl/palinsesti/Page-e120a813-1b92-4057-a214-15943d95aa68-json.html?canale=[nomeCanale]&giorno=[dd-mm-yyyy]"
        self.TG_URL = "http://www.tgr.rai.it/dl/tgr/mhp/home.xml"
        self.RELINKER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2956.0 Safari/537.36"

        self.DEFAULT_ICON_URL = "https://images-eu.ssl-images-amazon.com/images/I/41%2B5P94pGPL.png"
        self.NOTHUMB_URL = "http://www.rai.it/cropgd/256x144/dl/components/img/imgPlaceholder.png"

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER}
        #self.defaultParams = { 'header': {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:17.0) Gecko/20100101 Firefox/17.0'}}
        self.defaultParams = {'header': {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2956.0 Safari/537.36"}}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        #printDBG(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getThumbnailUrl(self, pathId):
        if pathId == "":
            url = self.NOTHUMB_URL
        else:
            url = self.getFullUrl(pathId)
            url = url.replace("[RESOLUTION]", "256x-")
        return url

    def getFullUrl(self, url):
        if url == "":
            return

        if url[:9] == "/raiplay/":
            url = url.replace("/raiplay/", self.MAIN_URL)

        while url[:1] == "/":
            url = url[1:]

        # Add the server to the URL if missing
        if url.find("://") == -1:
            url = self.MAIN_URL + url

        url = url.replace(" ", "%20")
        #url = urllib_quote(url, safe="%/:=&?~#+!$,;'@()*[]")

        #printDBG("PathID: " + url)

        return url

    def getLinksForVideo(self, cItem):
        printDBG("Raiplay.getLinksForVideo [%s]" % cItem)
        #sts, data=self.getPage(cItem["url"])
        #if not sts: return

        #printDBG(data)

        linksTab = []
        if (cItem["category"] == "live_tv") or (cItem["category"] == "live_radio") or (cItem["category"] == "video_link"):

            url = strwithmeta(cItem["url"], {'User-Agent': self.RELINKER_USER_AGENT})
            linksTab.extend(getDirectM3U8Playlist(url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))

        elif (cItem["category"] == "program"):
            # read relinker page
            program_url = cItem["url"]
            program_url = program_url.replace("/raiplay/", self.MAIN_URL)

            sts, data = self.getPage(program_url)
            response = json_loads(data)
            video_url = response["video"]["contentUrl"]
            printDBG(video_url)
            video_url = strwithmeta(video_url, {'User-Agent': self.RELINKER_USER_AGENT})
            linksTab.extend(getDirectM3U8Playlist(video_url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))

        else:
            printDBG("Raiplay: video form category %s with url %s not handled" % (cItem["category"], cItem["url"]))
            linksTab.append({'url': cItem["url"], 'name': 'link1'})

        return linksTab

    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [{'category': 'live_tv', 'title': 'Dirette tv'},
                        {'category': 'live_radio', 'title': 'Dirette radio'},
                        {'category': 'replay', 'title': 'Replay'},
                        {'category': 'ondemand', 'title': 'Programmi on demand'},
                        {'category': 'tg', 'title': 'Archivio Telegiornali'}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listLiveTvChannels(self, cItem):
        printDBG("Raiplay - start live channel list")
        sts, data = self.getPage(self.CHANNELS_URL)
        if not sts:
            return

        response = json_loads(data)
        tv_stations = response["dirette"]
        #printDBG(data)

        for station in tv_stations:
            title = station["channel"]
            desc = station["description"]
            icon = self.MAIN_URL + station["icon"]
            url = station["video"]["contentUrl"]
            params = dict(cItem)
            params = {'title': title, 'url': url, 'icon': icon, 'category': 'live_tv', 'desc': desc}
            self.addVideo(params)

    def listLiveRadioChannels(self, cItem):
        printDBG("Raiplay - start live radio list")
        sts, data = self.getPage(self.CHANNELS_RADIO_URL)
        if not sts:
            return

        response = json_loads(data)
        radio_stations = response["dati"]
        #printDBG(data)

        for station in radio_stations:
            title = station["nome"]
            desc = station["chText"]
            icon = "http://www.rai.it" + station["chImage"]
            if station["flussi"]["liveAndroid"] != "":
                url = station["flussi"]["liveAndroid"]
            params = dict(cItem)
            params = {'title': title, 'url': url, 'icon': icon, 'category': 'live_radio', 'desc': desc}

            self.addVideo(params)

    def daterange(self, start_date, end_date):
        for n in range((end_date - start_date).days + 1):
            yield end_date - datetime.timedelta(n)

    def listReplayDate(self, cItem):
        printDBG("Raiplay - start replay/EPG section")

        days = ["Domenica", "Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]
        months = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

        epgEndDate = datetime.date.today()
        epgStartDate = datetime.date.today() - datetime.timedelta(days=7)

        for day in self.daterange(epgStartDate, epgEndDate):
            day_str = days[int(day.strftime("%w"))] + " " + day.strftime("%d") + " " + months[int(day.strftime("%m")) - 1]
            self.addDir(MergeDicts(cItem, {'category': 'replay_date', 'title': day_str, 'name': day.strftime("%d-%m-%Y")}))

    def listReplayChannels(self, cItem):
        day = cItem['name']
        printDBG("Raiplay - start replay/EPG section - channels list for %s " % day)

        sts, data = self.getPage(self.CHANNELS_URL)
        if not sts:
            return

        response = json_loads(data)
        tv_stations = response["dirette"]

        for station in tv_stations:
            title = station["channel"]
            name = day + "|" + station["channel"]
            icon = self.MAIN_URL + station["icon"]
            self.addDir(MergeDicts(cItem, {'category': 'replay_channel', 'title': title, 'name': name}))

    def listEPG(self, cItem):
        str = cItem['name']
        epgDate = str[:10]
        channelName = str[11:]
        printDBG("Raiplay - start EPG for channel %s and day %s" % (channelName, epgDate))

        channel_id = channelName.replace(" ", "")
        url = self.EPG_URL
        url = url.replace("[nomeCanale]", channel_id)
        url = url.replace("[dd-mm-yyyy]", epgDate)

        sts, data = self.getPage(url)
        if not sts:
            return

        response = json_loads(data)
        programmes = response[channelName][0]["palinsesto"][0]["programmi"]

        for programme in programmes:
            if not programme:
                    continue

            startTime = programme["timePublished"]
            title = programme["name"]

            if programme["images"]["portrait"] != "":
                    thumb = self.getThumbnailUrl(programme["images"]["portrait"])
            elif programme["images"]["landscape"] != "":
                    thumb = self.getThumbnailUrl(programme["images"]["landscape"])
            elif programme["isPartOf"] and programme["isPartOf"]["images"]["portrait"] != "":
                    thumb = self.getThumbnailUrl(programme["isPartOf"]["images"]["portrait"])
            elif programme["isPartOf"] and programme["isPartOf"]["images"]["landscape"] != "":
                    thumb = self.getThumbnailUrl(programme["isPartOf"]["images"]["landscape"])
            else:
                    thumb = self.NOTHUMB_URL

            if programme["testoBreve"] != "":
                desc = programme["testoBreve"]
            else:
                desc = programme["description"]

            if programme["hasVideo"]:
                    videoUrl = programme["pathID"]
            else:
                    videoUrl = None

            params = dict(cItem)

            if videoUrl is None:
                # programme is not available
                title = startTime + " <I>" + title + "</I>"
                thumbnailImage = thumb
                params = {'title': title, 'url': '', 'icon': thumb, 'desc': desc, 'category': 'nop'}

            else:
                title = startTime + " " + title
                thumbnailImage = thumb
                params = {'title': title, 'url': videoUrl, 'icon': thumb, 'category': 'program', 'desc': desc}
                printDBG("add program %s with pathId %s" % (title, videoUrl))

            self.addVideo(params)

    def listOnDemandMain(self, cItem):
        printDBG("Raiplay - start on demand main list")
        sts, data = self.getPage(self.MENU_URL)
        if not sts:
            return

        response = json_loads(data)
        items = response["menu"]

        for item in items:
            if item["sub-type"] in ("RaiPlay Tipologia Page", "RaiPlay Genere Page"):
                icon_url = self.MAIN_URL + item["image"]
                self.addDir(MergeDicts(cItem, {'category': 'ondemand_items', 'title': item["name"], 'name': item["name"], 'url': item["PathID"], 'icon': icon_url, 'sub-type': item["sub-type"]}))

    def listOnDemandCategory(self, cItem):
        pathId = cItem["url"]
        pathId = self.getFullUrl(pathId)
        printDBG("Raiplay - processing item %s of sub-type %s with pathId %s" % (cItem["title"], cItem["sub-type"], pathId))

        sts, data = self.getPage(pathId)
        if not sts:
            return

        response = json_loads(data)
        blocks = response["blocchi"]

        if len(blocks) > 1:
            printDBG("Blocchi: " + str(len(blocks)))

        for item in blocks[0]["lanci"]:
            if item["images"]["portrait"] != "":
                icon_url = self.getThumbnailUrl(item["images"]["portrait"])
            else:
                icon_url = self.getThumbnailUrl(item["images"]["landscape"])

            self.addDir(MergeDicts(cItem, {'category': 'ondemand_items', 'title': item["name"], 'name': item["name"], 'url': item["PathID"], 'sub-type': item["sub-type"], 'icon': icon_url}))

    def listOnDemandAZ(self, cItem):
        pathId = cItem["url"]
        pathId = self.getFullUrl(pathId)
        printDBG("Raiplay - processing list with pathId %s" % pathId)

        # 0-9
        self.addDir(MergeDicts(cItem, {'category': 'ondemand_list', 'title': "0-9", 'name': "0-9", 'url': pathId}))

        #a-z
        for i in range(26):
            self.addDir(MergeDicts(cItem, {'category': 'ondemand_list', 'title': chr(ord('A') + i), 'name': chr(ord('A') + i), 'url': pathId}))

    def listOnDemandIndex(self, cItem):
        pathId = cItem["url"]
        pathId = self.getFullUrl(pathId)

        sts, data = self.getPage(pathId)
        if not sts:
            return

        response = json_loads(data)
        items = response[cItem["name"]]
        for item in items:
            name = item["name"]
            url = item["PathID"]
            self.addDir(MergeDicts(cItem, {'category': 'ondemand_items', 'title': name, 'name': name, 'url': url, 'sub-type': 'PLR programma Page'}))

    def listOnDemandProgram(self, cItem):
        pathId = cItem["url"]
        pathId = self.getFullUrl(pathId)

        sts, data = self.getPage(pathId)
        if not sts:
            return

        response = json_loads(data)
        blocks = response["Blocks"]

        for block in blocks:
            for set in block["Sets"]:
                name = set["Name"]
                url = set["url"]
                self.addDir(MergeDicts(cItem, {'category': 'ondemand_program', 'title': name, 'name': name, 'url': url}))

    def listOnDemandProgramItems(self, cItem):
        pathId = cItem["url"]
        pathId = self.getFullUrl(pathId)

        sts, data = self.getPage(pathId)
        if not sts:
            return

        response = json_loads(data)
        items = response["items"]

        for item in items:
            title = item["name"]
            if "subtitle" in item and item["subtitle"] != "" and item["subtitle"] != item["name"]:
                title = title + " (" + item["subtitle"] + ")"

            videoUrl = item["pathID"]
            if item["images"]["portrait"] != "":
                icon_url = self.getThumbnailUrl(item["images"]["portrait"])
            else:
                icon_url = self.getThumbnailUrl(item["images"]["landscape"])

            params = {'title': title, 'url': videoUrl, 'icon': icon_url, 'category': 'program'}
            printDBG("add video '%s' with pathId '%s'" % (title, videoUrl))

            self.addVideo(params)

    def listTg(self, cItem):
        printDBG("Raiplay start tg list")
        TG_TAB = [{'category': 'tg1', 'title': 'TG 1'}, {'category': 'tg2', 'title': 'TG 2'},
                  {'category': 'tg3', 'title': 'TG 3'}, {'category': 'tgr-root', 'title': 'TG Regionali'}]
        self.listsTab(TG_TAB, cItem)

    def listTgr(self, cItem):
        printDBG("Raiplay. start tgr list")
        if cItem["category"] != "tgr-root":
            url = cItem["url"]
        else:
            url = self.TG_URL

        sts, data = self.getPage(url)
        if not sts:
            return

        # search for dirs
        items = ph.findall(data, '<item behaviour="region">', '</item>', flags=0)
        items.extend(ph.findall(data, '<item behaviour="list">', '</item>', flags=0))

        for item in items:
            r_title = ph.find(item, '<label>', '</label>', flags=0)
            r_url = ph.find(item, '<url type="list">', '</url>', flags=0)
            r_image = ph.find(item, '<url type="image">', '</url>', flags=0)
            if r_title[0] and r_url[0]:
                if r_image[0]:
                    icon = self.MAIN_URL + r_image[1]
                else:
                    icon = self.NOTHUMB_URL

                title = r_title[1]
                url = self.MAIN_URL + r_url[1]
                self.addDir(MergeDicts(cItem, {'category': 'tgr', 'title': title, 'url': url, 'icon': icon}))

        # search for video links
        items = ph.findall(data, '<item behaviour="video">', '</item>', flags=0)
        for item in items:
            r_title = ph.find(item, '<label>', '</label>', flags=0)
            r_url = ph.find(item, '<url type="video">', '</url>', flags=0)
            r_image = ph.find(item, '<url type="image">', '</url>', flags=0)
            if r_title[0] and r_url[0]:
                if r_image[0]:
                    icon = self.MAIN_URL + r_image[1]
                else:
                    icon = self.NOTHUMB_URL

                title = r_title[1]
                videoUrl = r_url[1]
                params = {'title': title, 'url': videoUrl, 'icon': icon, 'category': 'video_link'}
                printDBG("add video '%s' with pathId '%s'" % (title, videoUrl))
                self.addVideo(params)

    def searchLastTg(self, cItem):
        category = cItem['category']
        if category == 'tg1':
            tag = "NomeProgramma:TG1^Tematica:Edizioni integrali"
        elif category == 'tg2':
            tag = "NomeProgramma:TG2^Tematica:Edizione integrale"
        elif category == 'tg3':
            tag = "NomeProgramma:TG3^Tematica:Edizioni del TG3"
        else:
            printDBG("Raiplay unhandled tg category %s" % category)
            return

        items = self.getLastContentByTag(tag)
        if items == None:
            return

        for item in items:
            title = item["name"]
            if item["images"]["portrait"] != "":
                icon_url = self.getThumbnailUrl(item["images"]["portrait"])
            else:
                icon_url = self.getThumbnailUrl(item["images"]["landscape"])

            videoUrl = item["Url"]
            params = {'title': title, 'url': videoUrl, 'icon': icon_url, 'category': 'video_link'}
            printDBG("add video '%s' with pathId '%s'" % (title, videoUrl))

            self.addVideo(params)

    def getLastContentByTag(self, tags="", numContents=16):
        tags = urllib_quote(tags)
        domain = "RaiTv"
        xsl = "rai_tv-statistiche-raiplay-json"

        url = "http://www.rai.it/StatisticheProxy/proxyPost.jsp?action=getLastContentByTag&numContents=%s&tags=%s&domain=%s&xsl=%s" % (str(numContents), tags, domain, xsl)
        sts, data = self.getPage(url)
        if not sts:
            return

        if data == "":
            return
        response = json_loads(data)
        return response["list"]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Raiplay - handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('IT')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')
        subtype = self.currItem.get("sub-type", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'live_tv':
            self.listLiveTvChannels(self.currItem)
        elif category == 'live_radio':
            self.listLiveRadioChannels(self.currItem)
        elif category == 'replay':
            self.listReplayDate(self.currItem)
        elif category == 'replay_date':
            self.listReplayChannels(self.currItem)
        elif category == 'replay_channel':
            self.listEPG(self.currItem)
        elif category == 'ondemand':
            self.listOnDemandMain(self.currItem)
        elif category == 'ondemand_items':
            if subtype == "RaiPlay Tipologia Page" or subtype == "RaiPlay Genere Page":
                self.listOnDemandCategory(self.currItem)
            elif subtype == "Raiplay Tipologia Item":
                self.listOnDemandAZ(self.currItem)
            elif subtype == "PLR programma Page":
                self.listOnDemandProgram(self.currItem)
            else:
                printDBG("Raiplay - item '%s' - Sub-type not handled '%s' " % (name, subtype))
        elif category == 'ondemand_list':
            self.listOnDemandIndex(self.currItem)
        elif category == 'ondemand_program':
            self.listOnDemandProgramItems(self.currItem)
        elif category == 'tg':
            self.listTg(self.currItem)
        elif category == 'tgr' or category == 'tgr-root':
            self.listTgr(self.currItem)
        elif category in ['tg1', 'tg2', 'tg3']:
            self.searchLastTg(self.currItem)
        elif category == 'nop':
            printDGB('raiplay no link')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Raiplay(), True, [])
