# -*- coding: utf-8 -*-
# date of last change: 09-08-2025 by Lululla
# 20250807 fix from lululla for getThumbnailUrl2 (icons) - sport page - events recoded
# 20250809 fix from lululla for increase getThumbnailUrl2 - sport page show poster - events theatre added
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import parse_qs, urlparse, urlunparse
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
###################################################

###################################################
# FOREIGN import
###################################################
import re
import datetime

###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://raiplay.it/'


class Raiplay(CBaseHostClass):

    def __init__(self):

        CBaseHostClass.__init__(self, {'history': 'raiplay', 'cookie': 'raiplay.it.cookie'})
        self.cm = common()
        self.MAIN_URL = 'https://raiplay.it/'
        self.MENU_URL = "https://www.rai.it/dl/RaiPlay/2016/menu/PublishingBlock-20b274b1-23ae-414f-b3bf-4bdc13b86af2.html?homejson"
        self.DEFAULT_ICON_URL = "https://img.tuttoandroid.net/wp-content/uploads/2019/10/Raiplay-logo.jpg"
        self.DEFAULT_ICON_URL2 = "https://images-eu.ssl-images-amazon.com/images/I/41%2B5P94pGPL.png"
        self.NOTHUMB_URL = "https://img.tuttoandroid.net/wp-content/uploads/2019/10/Raiplay-logo.jpg"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.RELINKER_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36"
        # self.LOCALIZEURL = "http://mediapolisgs.rai.it/relinker/relinkerServlet.htm?cont=201342"

        self.CHANNELS_URL = "https://www.rai.it/dl/RaiPlay/2016/PublishingBlock-9a2ff311-fcf0-4539-8f8f-c4fee2a71d58.html?json"

        # self.EPG_URL = "https://www.raiplay.it/guidatv/lista?canale=[nomeCanale]&giorno=[dd-mm-yyyy]"
        self.EPG_URL = 'https://www.raiplay.it/palinsesto/guidatv/lista/[idCanale]/[dd-mm-yyyy].html'
        self.EPG_URL_JSON = "https://www.raiplay.it/palinsesto/app/old/[idCanale]/[dd-mm-yyyy].json"  # this actual work updated

        # Raiplay RADIO
        # self.BASEURL = "http://www.raiplayradio.it/"
        self.CHANNELS_RADIO_URL = "https://rai.it/dl/portaleRadio/popup/ContentSet-003728e4-db46-4df8-83ff-606426c0b3f5-json.html"
        self.CHANNELS_RADIO_URL2 = "http://www.raiplaysound.it/dirette.json"
        # self.NOTHUMB_RADIO_URL = "http://www.raiplayradio.it/dl/components/img/radio/player/placeholder_img.png"

        self.TG_URL = "http://www.tgr.rai.it/dl/tgr/mhp/home.xml"
        self.TG1_URL = "https://www.rainews.it/notiziari/tg1/archivio"
        # https://www.raiplay.it/programmi/specialetg1.json
        self.TG2_URL = "https://www.rainews.it/notiziari/tg2/archivio"
        self.TG3_URL = "https://www.rainews.it/notiziari/tg3/archivio"

        # Rai Sport urls Update Rai Sport URL Lululla
        self.RAISPORT_MAIN_URL = 'https://www.raisport.rai.it'
        self.RAISPORT_LIVE_URL = self.RAISPORT_MAIN_URL + '/dirette.html'
        self.RAISPORT_ARCHIVIO_URL = self.RAISPORT_MAIN_URL + '/archivio.html'
        self.RAISPORTDOMINIO = "RaiNews|Category-6dd7493b-f116-45de-af11-7d28a3f33dd2"
        self.RAISPORT_CATEGORIES_URL = "https://www.rainews.it/category/6dd7493b-f116-45de-af11-7d28a3f33dd2.json"
        self.RAISPORT_SEARCH_URL = "https://www.rainews.it/atomatic/news-search-service/api/v3/search"

        # # future work
        # PALINSESTO_URL_HTML = "https://www.raiplay.it/palinsesto/guidatv/lista/[idCanale]/[dd-mm-yyyy].html"
        # ON_AIR_URL = "https://www.raiplay.it/palinsesto/onAir.json"
        # RAIPLAY_AZ_TV_SHOW_PATH = "https://www.raiplay.it/dl/RaiTV/RaiPlayMobile/Prod/Config/programmiAZ-elenco.json"
        # RAIPLAY_AZ_RADIO_SHOW_PATH = "https://www.raiplay.it/dl/RaiTV/RaiRadioMobile/Prod/Config/programmiAZ-elenco.json"
        # PALINSESTO_URL = "http://www.raiplaysound.it/dl/palinsesti/Page-a47ba852-d24f-44c2-8abb-0c9f90187a3e-json.html?canale=[nomeCanale]&giorno=[dd-mm-yyyy]&mode=light"

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.RaiSportKeys = []

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getThumbnailUrl(self, pathId):
        if pathId == "":
            url = self.NOTHUMB_URL
        else:
            url = self.getFullUrl(pathId)
            url = url.replace("[RESOLUTION]", "256x-")
        print(">>> getThumbnailUrl - fullUrl:", url)
        return url

    def getThumbnailUrl2(self, item):
        print(">>> getThumbnailUrl2 - item keys:", item.keys())

        # Check for 'transparent-icon' first
        if "transparent-icon" in item:
            icon_url = item["transparent-icon"]
            if "[an error occurred" not in icon_url:  # filtro anti-errore
                print(">>> Using transparent-icon:", icon_url)
                return self.getThumbnailUrl(icon_url)
            else:
                print(">>> Skipping invalid transparent-icon:", icon_url)

        if "audio" in item:
            ch_image_url = item["poster"]
            print(">>> Using poster:", ch_image_url)
            return self.getThumbnailUrl(ch_image_url)

        if "chImage" in item:
            ch_image_url = item["chImage"]
            print(">>> Using chImage:", ch_image_url)
            return self.getThumbnailUrl(ch_image_url)

        # Fallback: check standard images
        if "images" in item and isinstance(item["images"], dict):
            images = item["images"]
            print(">>> Available image keys:", images.keys())

            if "landscape" in images:
                print(">>> Using landscape:", images["landscape"])
                return self.getThumbnailUrl(images["landscape"])
            elif "landscape43" in images:
                print(">>> Using landscape43:", images["landscape43"])
                return self.getThumbnailUrl(images["landscape43"])
            elif "portrait" in images:
                print(">>> Using portrait:", images["portrait"])
                return self.getThumbnailUrl(images["portrait"])
            elif "portrait43" in images:
                print(">>> Using portrait43:", images["portrait43"])
                return self.getThumbnailUrl(images["portrait43"])
            elif "portrait_logo" in images:
                print(">>> Using portrait_logo:", images["portrait_logo"])
                return self.getThumbnailUrl(images["portrait_logo"])
            elif "square" in images:
                print(">>> Using square:", images["square"])
                return self.getThumbnailUrl(images["square"])
            elif "default" in images:
                print(">>> Using default:", images["default"])
                return self.getThumbnailUrl(images["default"])

        print(">>> No valid thumbnail found, using DEFAULT_ICON_URL")
        return self.DEFAULT_ICON_URL

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
        # url = urllib_quote(url, safe="%/:=&?~#+!$,;'@()*[]")

        # fix old format of url for json
        if url.endswith(".html?json"):
            url = url.replace(".html?json", ".json")
        elif url.endswith("/?json"):
            url = url.replace("/?json", "/index.json")
        elif url.endswith("?json"):
            url = url.replace("?json", ".json")

        return url

    def getIndexFromJSON(self, pathId):
        url = self.getFullUrl(pathId)
        sts, data = self.getPage(url)
        if not sts:
            return []
        else:
            response = json_loads(data)

        index = []
        for i in response["contents"]:
            if len(response["contents"][i]) > 0:
                index.append(i)

        index.sort()
        return index

    def getRelinkerURL(self, url):
        scheme, netloc, path, params, query, fragment = urlparse(url)
        qs = parse_qs(query)

        # output=20 url in body
        # output=23 HTTP 302 redirect
        # output=25 url and other parameters in body, space separated
        # output=44 XML (not well formatted) in body
        # output=47 json in body
        # pl=native,flash,silverlight
        # A stream will be returned depending on the UA (and pl parameter?)

        if "output" in qs:
            del (qs['output'])

        # qs['output'] = "20" # only url
        qs['output'] = "56"  # xml stream data

        query = urllib_urlencode(qs, True)
        url = urlunparse((scheme, netloc, path, params, query, fragment))

        try:
            sts, response = self.getPage(url)

            # mediaUrl = response.strip()
            # xbmc.log(response)

            # find real url
            content = re.findall("<url type=\"content\">(.*?)</url>", response)
            if content:
                # <![CDATA[https://dashaz-dc-euwe.akamaized.net/subtl_proxy/6ed6fac0-ae71-4dd7-b4be-d8921d4948b9/20200713102433_12778339.ism/manifest(format=mpd-time-csf,filter=medium_1200-2400).mpd?hdnea=st=1599391792~exp=1599391942~acl=/*~hmac=27e952b0f784662684fe65fb4717152d8644e2a9f3ad575ece21738dfbe88263]]>
                url = re.findall(r"<!\[CDATA\[(.*?)\]\]>", content[0])
                if url:
                    # find type of stream
                    ct = re.findall("<ct>(.*?)</ct>", response)
                    if ct:
                        """
                        # # DRM license URL find license key
                        license_url = '''{"drmLicenseUrlValues":[
                            {"drm":"WIDEVINE","licenceUrl":"https://mediaservicerainet02.keydelivery.northeurope.media.azure.net/Widevine/?kid=5ca7736f-7e27-49fc-80b2-bde49c8c0259&token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...","name":"Widevine Token...","audience":"urn:raiplay_hdcp_v1_sl1_sd"},
                            {"drm":"PLAYREADY","licenceUrl":"https://mediaservicerainet02.keydelivery.northeurope.media.azure.net/PlayReady/?kid=5ca7736f-7e27-49fc-80b2-bde49c8c0259&token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...","name":"Playready Token...","audience":"urn:raiplay"}
                        ]}'''
                        # end license_url
                        """
                        licenseUrl = re.findall("<license_url>(.*?)</license_url>", response)
                        if licenseUrl:
                            # xbmc.log(licenseUrl[0])
                            licenseJson = re.findall(r"<!\[CDATA\[(.*?)\]\]>", licenseUrl[0])
                            if licenseJson:
                                # xbmc.log(licenseJson[0])
                                try:
                                    licenseJson = json_loads(licenseJson[0])

                                    # xbmc.log(str(licenseJson))
                                    licenseData = licenseJson.get('drmLicenseUrlValues', [])
                                    key = ''
                                    for ls in licenseData:
                                        if "WIDEVINE" in ls.get("drm", ""):
                                            key = ls.get("licenceUrl", '')

                                    return {'url': url[0], 'ct': ct[0], 'key': key}

                                except:
                                    return {'url': url[0], 'ct': ct[0], 'key': ''}
                        else:
                            return {'url': url[0], 'ct': ct[0], 'key': ''}

                    else:
                        return {'url': url[0], 'ct': '', 'key': ''}

                else:
                    return {'url': '', 'ct': '', 'key': ''}
            else:
                return {'url': '', 'ct': '', 'key': ''}

            # Workaround to normalize URL if the relinker doesn't
            # try:
            #    mediaUrl = urllib_quote(mediaUrl, safe="%/:=&?~#+!$,;'@()*[]")
            # except:
            #    printExc()
            # return mediaUrl

        except:
            return {'url': '', 'type': '', 'key': ''}

    def getLinksForVideo(self, cItem):
        printDBG("Raiplay.getLinksForVideo [%s]" % cItem)

        linksTab = []

        url = self.getRelinkerURL(cItem['url'])
        url = url.get("url", "")
        printDBG("----> Url from relinker: %s" % url)

        if (cItem["category"] == "live_tv") or (cItem["category"] == "live_radio") or (cItem["category"] == "video_link") or (cItem["category"] == "raisport_video"):

            linksTab.append({'name': 'hls', 'url': url})

            url = strwithmeta(url, {'User-Agent': self.RELINKER_USER_AGENT})
            linksTab.extend(getDirectM3U8Playlist(url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))

        elif (cItem["category"] == "program"):
            # read relinker page
            program_url = self.getFullUrl(cItem["url"])

            sts, data = self.getPage(program_url)
            if sts:
                response = json_loads(data)
                video_url = response["video"]["content_url"]
                printDBG(video_url)
                video_url = strwithmeta(video_url, {'User-Agent': self.RELINKER_USER_AGENT})
                links = getDirectM3U8Playlist(video_url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999)
                if links:
                    linksTab.append({'name': 'hls', 'url': video_url})
                    linksTab.extend(links)
                else:
                    # for some wrong links opening another mpd link instead of index.m3u8
                    sts, data = self.getPage(video_url, {'User-Agent': self.RELINKER_USER_AGENT})
                    if sts:
                        printDBG(data)
                        if self.cm.isValidUrl(data.strip()):
                            linksTab.append({'name': 'mpd', 'url': data.strip()})
        else:
            printDBG("Raiplay: video form category %s with url %s not handled" % (cItem["category"], cItem["url"]))
            linksTab.append({'url': cItem["url"], 'name': 'link1'})

        return linksTab

    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [{'category': 'live_tv', 'title': 'Dirette tv', 'icon': self.DEFAULT_ICON_URL},
                        {'category': 'live_radio', 'title': 'Dirette radio', 'icon': self.DEFAULT_ICON_URL},
                        {'category': 'replay', 'title': 'Replay', 'icon': self.DEFAULT_ICON_URL},
                        {'category': 'ondemand', 'title': 'Programmi on demand', 'icon': self.DEFAULT_ICON_URL},
                        {'category': 'tg', 'title': 'Archivio Telegiornali', 'icon': self.DEFAULT_ICON_URL},
                        {'category': 'raisport_main', 'title': 'Archivio Rai Sport', 'icon': self.DEFAULT_ICON_URL}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listLiveTvChannels(self, cItem):
        printDBG("Raiplay - start live channel list")

        sts, data = self.getPage(self.CHANNELS_URL)
        if not sts:
            return

        try:
            response = json_loads(data)
            tv_stations = response["dirette"]
        except:
            printExc()
            return

        for station in tv_stations:
            title = station["channel"]
            desc = station["description"]

            icon = self.getThumbnailUrl(station["transparent-icon"]) + '|webpToPng'
            url = station["video"]["contentUrl"]

            params = {
                'title': title,
                'url': url,
                'icon': icon,
                'category': 'live_tv',
                'desc': desc
            }
            self.addVideo(params)

        # # Canali Rai Sport add
        # printDBG("Raiplay - getting Rai Sport channels")
        # sts, data = self.getPage(self.RAISPORT_LIVE_URL)
        # if not sts:
            # printDBG("Raiplay - failed to get Rai Sport page")
            # return

        container = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'canali-container'), '</div>', False)[1]
        if not container:
            printDBG("Raiplay - no canali-container found")
            return

        channels_block = self.cm.ph.getDataBeetwenNodes(container, ('<ul', '>', 'canali'), '</ul>', False)[1]
        if not channels_block:
            printDBG("Raiplay - no canali list found")
            return

        items = self.cm.ph.getAllItemsBeetwenMarkers(channels_block, '<li', '</li>')
        printDBG(f"Raiplay - found {len(items)} sport channels")

        for i in items:
            url = self.cm.ph.getSearchGroups(i, '''data-video-url=['"]([^'^"]+?)['"]''')[0]
            if not url:
                continue

            icon = self.cm.ph.getSearchGroups(i, '''<img[^>]+src=['"]([^'^"]+?)['"]''')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(i, '''stillframe=['"]([^'^"]+?)['"]''')[0]

            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(i, ('<div', '>', 'canale-title'), '</div>', False)[1])
            if not title:
                title = self.cleanHtmlStr(i)

            params = {
                'title': f"Rai Sport: {title}",
                'url': url,
                'icon': icon,
                'category': 'live_tv',
                'desc': ''
            }
            self.addVideo(params)

    def listLiveRadioChannels(self, cItem):
        printDBG("Raiplay - start live radio list")
        sts, data = self.getPage(self.CHANNELS_RADIO_URL)
        if not sts:
            return

        response = json_loads(data)
        radio_stations = response["dati"]
        # printDBG(data)

        for station in radio_stations:
            title = station["nome"]
            desc = station["chText"]
            icon = "https://www.rai.it" + station["chImage"]
            if not icon:
                icon = self.getThumbnailUrl2(station)
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
            params = MergeDicts(cItem, {'category': 'replay_date', 'title': day_str, 'name': day.strftime("%d-%m-%Y"), 'icon': self.DEFAULT_ICON_URL})
            printDBG(str(params))
            self.addDir(params)

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
            icon = self.getThumbnailUrl2(station)
            params = MergeDicts(cItem, {'category': 'replay_channel', 'title': title, 'name': name, 'icon': icon})
            printDBG(str(params))
            self.addDir(params)

    def listEPG(self, cItem):
        str1 = cItem['name']
        epgDate = str1[:10]
        channelName = str1[11:]
        print(">>> listEPG called with cItem name:", cItem['name'])
        print(">>> epgDate:", epgDate, "channelName:", channelName)
        channel_id = channelName.replace(" ", "-").lower()
        url = self.EPG_URL
        url = url.replace("[idCanale]", channel_id)
        url = url.replace("[dd-mm-yyyy]", epgDate)

        sts, data = self.getPage(url)
        if not sts:
            print(">>> Failed to get page data")
            return

        items = self.cm.ph.getAllItemsBeetwenMarkers(data, ('<li', '>', 'eventSpan'), '</li>')

        for idx, i in enumerate(items):
            videoUrl = self.cm.ph.getSearchGroups(i, '''data-href=['"]([^'^"]+?)['"]''')[0]
            videoUrl = self.getFullUrl(videoUrl)
            print(">>> item #", idx, "videoUrl:", videoUrl)

            icon = self.cm.ph.getSearchGroups(i, '''data-img=['"]([^'^"]+?)['"]''')[0]
            print(">>> item #", idx, "raw icon data-img:", icon)
            if icon:
                icon = self.getFullUrl(icon)
                print(">>> item #", idx, "full icon URL:", icon)
            else:
                icon = self.DEFAULT_ICON_URL
                print(">>> item #", idx, "no icon found")
            title = re.findall("<p class=\"info\">([^<]+?)</p>", i)
            title = title[0] if title else ''
            startTime = re.findall("<p class=\"time\">([^<]+?)</p>", i)
            if startTime:
                title = startTime[0] + " " + title

            desc = re.findall("<p class=\"descProgram\">([^<]+?)</p>", i, re.S)
            desc = desc[0] if desc else ""
            params = {}
            if videoUrl:
                if not videoUrl.endswith('json'):
                    videoUrl = videoUrl + "?json"
                params = {'title': title, 'url': videoUrl, 'icon': icon, 'category': 'program', 'desc': desc}
            else:
                title = title + r"\c00??8800 [not available]"
                params = {'title': title, 'url': '', 'icon': icon, 'desc': desc, 'category': 'nop'}
            self.addVideo(params)

    def listOnDemandMain(self, cItem):
        printDBG("Raiplay - start on demand main list")
        sts, data = self.getPage(self.MENU_URL)
        if not sts:
            return

        response = json_loads(data)
        items = response["menu"]

        for item in items:
            if item["sub-type"] in ("RaiPlay Tipologia Page", "RaiPlay Genere Page", "RaiPlay Tipologia Editoriale Page"):

                if item["name"] not in ("Teatro", "Musica"):

                    # new urls
                    # i.e. change "/raiplay/programmi/?json" to "/raiplay/tipologia/programmi/index.json"
                    m = re.findall("raiplay/(.*?)/[?]json", item["PathID"])
                    if m:
                        # add new item not in old json
                        params = MergeDicts(cItem, {'category': 'ondemand_items', 'title': "Teatro e musica", 'name': "Teatro e musica", 'url': "/raiplay/tipologia/musica-e-teatro/index.json", 'icon': self.getThumbnailUrl("/dl/img/2018/06/04/1528115285089_ico-teatro.png"), 'sub-type': item["sub-type"]})
                        printDBG(str(params))
                        self.addDir(params)

                        # new append example: aggiungo "Documentari"
                        params = MergeDicts(cItem, {'category': 'ondemand_items', 'title': "Documentari", 'name': "Documentari", 'url': "/raiplay/tipologia/documentari/index.json", 'icon': self.getThumbnailUrl("/dl/img/2018/06/04/1528115285089_ico-documentari.png"), 'sub-type': item["sub-type"]})
                        printDBG(str(params))
                        self.addDir(params)
                        # add new item not in old json
                        params = MergeDicts(cItem, {'category': 'ondemand_items', 'title': "Teatro e musica", 'name': "Teatro e musica", 'url': "/raiplay/tipologia/musica-e-teatro/index.json", 'icon': self.getThumbnailUrl("/dl/img/2018/06/04/1528115285089_ico-teatro.png"), 'sub-type': item["sub-type"]})
                        printDBG(str(params))
                        self.addDir(params)

                        if m[0] == "fiction":
                            params = MergeDicts(cItem, {'category': 'ondemand_items', 'title': "Serie italiane", 'name': "Serie italiane", 'url': "/raiplay/tipologia/serieitaliane/index.json", 'icon': "https://www.rai.it/dl/img/2018/06/04/1528107006058_ico-fiction.png", 'sub-type': item["sub-type"]})
                            printDBG(str(params))
                            self.addDir(params)

                            params = MergeDicts(cItem, {'category': 'ondemand_subhome', 'title': "Original", 'name': "Original", 'url': "/raiplay/tipologia/original/index.json", 'icon': "https://www.rai.it/dl/img/2018/06/04/1528107006058_ico-fiction.png", 'sub-type': item["sub-type"]})
                            printDBG(str(params))
                            self.addDir(params)

                        elif m[0] == "serietv":

                            params = MergeDicts(cItem, {'category': 'ondemand_items', 'title': "Serie internazionali", 'name': "Serie internazionali", 'url': "/raiplay/tipologia/serieinternazionali/index.json", 'icon': "https://www.rai.it/dl/img/2018/06/04/1528107006058_ico-fiction.png", 'sub-type': item["sub-type"]})
                            printDBG(str(params))
                            self.addDir(params)

                        elif m[0] == "bambini" or m[0] == "bambini/":
                            icon = self.getThumbnailUrl2(item)
                            params = MergeDicts(cItem, {'category': 'ondemand_subhome', 'title': "Bambini", 'name': "Bambini", 'url': "/raiplay/tipologia/bambini/index.json", 'icon': icon, 'sub-type': item["sub-type"]})
                            printDBG(str(params))
                            self.addDir(params)

                            params = MergeDicts(cItem, {'category': 'ondemand_subhome', 'title': "Teen", 'name': "Teen", 'url': "/raiplay/tipologia/teen/index.json", 'icon': icon, 'sub-type': item["sub-type"]})
                            printDBG(str(params))
                            self.addDir(params)

                        else:
                            # icon_url = self.MAIN_URL + item["image"]
                            icon_url = self.getThumbnailUrl2(item)
                            params = MergeDicts(cItem, {'category': 'ondemand_items', 'title': item["name"], 'name': item["name"], 'url': item["PathID"], 'icon': icon_url, 'sub-type': item["sub-type"]})
                            # new urls
                            # i.e. change "/raiplay/programmi/?json" to "/raiplay/tipologia/programmi/index.json"
                            m = re.findall("raiplay/(.*?)/[?]json", params["url"])
                            if m:
                                params["url"] = "/raiplay/tipologia/%s/index.json" % m[0]
                            printDBG(str(params))
                            self.addDir(params)

    def listOnDemandCategory(self, cItem):
        pathId = cItem["url"]
        pathId = self.getFullUrl(pathId)
        printDBG("Raiplay - processing item %s of sub-type %s with pathId %s" % (cItem["title"], cItem["sub-type"], pathId))

        sts, data = self.getPage(pathId)
        if not sts:
            return

        response = json_loads(data)

        for b in response["contents"]:
            if b["type"] == "RaiPlay Slider Generi Block":
                for item in b["contents"]:
                    icon = self.getThumbnailUrl2(item)
                    params = MergeDicts(cItem, {'category': 'ondemand_items', 'title': item["name"], 'name': item["name"], 'url': item["path_id"], 'sub-type': item["sub_type"], 'icon': icon})
                    printDBG(str(params))
                    self.addDir(params)

    def listOnDemandAZ(self, cItem):
        pathId = self.getFullUrl(cItem["url"])
        printDBG("Raiplay - processing list with pathId %s" % pathId)

        index = self.getIndexFromJSON(pathId)

        for i in index:
            self.addDir(MergeDicts(cItem, {'category': 'ondemand_list', 'title': i, 'name': i, 'url': pathId}))

    def listOnDemandIndex(self, cItem):
        pathId = self.getFullUrl(cItem["url"])
        printDBG("Raiplay.listOnDemandIndex with index %s and url %s" % (cItem["name"], pathId))

        sts, data = self.getPage(pathId)
        if not sts:
            return

        response = json_loads(data)
        items = response["contents"][cItem["name"]]
        for item in items:
            name = item["name"]
            url = item["path_id"]
            icon = self.getThumbnailUrl2(item)
            sub_type = item["type"]
            params = MergeDicts(cItem, {'category': 'ondemand_items', 'title': name, 'name': name, 'url': url, 'icon': icon, 'sub-type': sub_type})
            printDBG(str(params))
            self.addDir(params)

    def listOnDemandProgram(self, cItem):
        pathId = self.getFullUrl(cItem["url"])
        printDBG("Raiplay.listOnDemandProgram with url %s" % pathId)

        sts, data = self.getPage(pathId)
        if not sts:
            return

        response = json_loads(data)
        blocks = response["blocks"]

        for block in blocks:
            for set in block["sets"]:
                name = set["name"]
                url = set["path_id"]
                self.addDir(MergeDicts(cItem, {'category': 'ondemand_program', 'title': name, 'name': name, 'url': url}))

    def listOnDemandProgramItems(self, cItem):
        pathId = self.getFullUrl(cItem["url"])
        printDBG("Raiplay.listOnDemandProgram with url %s" % pathId)

        sts, data = self.getPage(pathId)
        if not sts:
            return

        response = json_loads(data)
        items = response["items"]

        for item in items:
            title = item["name"]
            if "subtitle" in item and item["subtitle"] != "" and item["subtitle"] != item["name"]:
                title = title + " (" + item["subtitle"] + ")"

            videoUrl = item["path_id"]
            icon_url = self.getThumbnailUrl2(item)
            if not icon_url:
                images = item.get("images", {})
                portrait = images.get("portrait", "")
                landscape = images.get("landscape", "")
                if portrait:
                    icon_url = self.getThumbnailUrl(portrait)
                elif landscape:
                    icon_url = self.getThumbnailUrl(landscape)
                else:
                    icon_url = self.NOTHUMB_URL
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
        if items is None:
            return

        for item in items:
            title = item["name"]
            icon_url = self.getThumbnailUrl2(item)
            if not icon_url:
                images = item.get("images", {})
                portrait = images.get("portrait", "")
                landscape = images.get("landscape", "")
                if portrait:
                    icon_url = self.getThumbnailUrl(portrait)
                elif landscape:
                    icon_url = self.getThumbnailUrl(landscape)
                else:
                    icon_url = self.NOTHUMB_URL
            videoUrl = item.get("Url", "")
            params = {'title': title, 'url': videoUrl, 'icon': icon_url, 'category': 'video_link'}
            printDBG("add video '%s' with pathId '%s'" % (title, videoUrl))

            self.addVideo(params)

    def getLastContentByTag(self, tags="", numContents=16):
        tags = urllib_quote(tags)
        domain = "RaiTv"
        xsl = "rai_tv-statistiche-raiplay-json"

        url = "https://www.rai.it/StatisticheProxy/proxyPost.jsp?action=getLastContentByTag&numContents=%s&tags=%s&domain=%s&xsl=%s" % (str(numContents), tags, domain, xsl)
        sts, data = self.getPage(url)
        if not sts:
            return

        if data == "":
            return
        response = json_loads(data)
        return response["list"]

    def fillRaiSportKeys(self):
        printDBG("Raiplay.fillRaiSportKeys")
        self.RaiSportKeys = []

        try:
            sts, data = self.getPage(self.RAISPORT_CATEGORIES_URL)
            if not sts:
                return
            response = json_loads(data)
        except:
            return

        dominio = "RaiNews|Category-6dd7493b-f116-45de-af11-7d28a3f33dd2"

        for c in response.get('children', []):
            categName = c.get("name", "")
            categCode = c.get("uniqueName", "")
            categChildren = c.get("children", [])

            if categName:
                sub_keys = []
                for c2 in categChildren:
                    subcategName = c2.get("name", "")
                    subcategCode = c2.get("uniqueName", "")
                    if subcategName:
                        sub_keys.append({
                            'title': subcategName,
                            "dominio": dominio,
                            "key": subcategName + "|" + subcategCode
                        })

                self.RaiSportKeys.append({
                    'title': categName,
                    "dominio": dominio,
                    "key": categName + "|" + categCode,
                    'sub_keys': sub_keys
                })

    def listRaiSportMain(self, cItem):
        printDBG("Raiplay.listRaiSportMain")

        if not self.RaiSportKeys:
            self.fillRaiSportKeys()

        for k in self.RaiSportKeys:
            params = dict(cItem)
            params.update({
                'category': 'raisport_item',
                'title': k['title'],
                'dominio': k['dominio'],
                'key': k['key'],
                'sub_keys': k['sub_keys']
            })
            self.addDir(params)

    def listRaiSportItems(self, cItem):
        printDBG("Raiplay.listRaiSportItem %s" % cItem['title'])
        dominio = cItem.get('dominio', '')
        main_key = cItem.get('key', '')
        sub_keys = cItem.get('sub_keys', [])

        # Add "All Videos" option
        params = {
            'category': 'raisport_subitem',
            'title': "Tutti i video",
            'dominio': dominio,
            'key': main_key
        }
        self.addDir(params)

        # Add subcategories
        for k in sub_keys:
            params = {
                'category': 'raisport_subitem',
                'title': k['title'],
                'dominio': k['dominio'],
                'key': k['key']
            }
            self.addDir(params)

    def listRaiSportVideos(self, cItem):
        printDBG("Raiplay.listRaiSportVideos %s" % cItem['title'])
        key = cItem.get('key', '')
        dominio = cItem.get('dominio', '')
        page = int(cItem.get('page', 0))

        header = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/json; charset=UTF-8',
            'Origin': 'https://www.raisport.rai.it',
            'Referer': 'https://www.raisport.rai.it/archivio.html',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
        }
        pageSize = 50

        payload = {
            "page": page,
            "pageSize": pageSize,
            "mode": "archive",
            "filters": {
                "tematica": [key],
                "dominio": dominio
            }
        }
        postData = json_dumps(payload)

        sts, data = self.getPage(self.RAISPORT_SEARCH_URL, {'header': header, 'raw_post_data': True}, post_data=postData)
        if not sts:
            return

        try:
            j = json_loads(data)
        except:
            return

        videos = j.get("hits", [])

        for video in videos:
            title = video.get("title", "")
            data_type = video.get("data_type", "")

            if data_type == "video":
                media = video.get('media', {})
                relinker_url = media.get('mediapolis', "")
                duration = 0
                if 'durata' in media:
                    d = media['durata'].split(":")
                    if len(d) == 3:
                        duration = int(d[0]) * 3600 + int(d[1]) * 60 + int(d[2])

                images = video.get('images', {})
                if images:
                    icon = self.getThumbnailUrl2(video)

                creation_date = video.get('create_date', "")
                desc = video.get('summary', "")
                if creation_date and desc:
                    desc = f"{creation_date}\n{desc}"
                elif creation_date:
                    desc = creation_date

                params = {
                    'category': 'raisport_video',
                    'title': title,
                    'desc': desc,
                    'url': relinker_url,
                    'icon': icon,
                    'duration': duration
                }
                self.addVideo(params)

        # Add next page if available
        total = j.get('total', 0)
        if total > (page + 1) * pageSize:
            params = dict(cItem)
            params['title'] = _("Next page")
            params['page'] = page + 1
            self.addDir(params)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Raiplay - handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('IT')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        # mode = self.currItem.get("mode", '')
        subtype = self.currItem.get("sub-type", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
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
            if subtype == "RaiPlay Tipologia Page" or subtype == "RaiPlay Genere Page" or subtype == "RaiPlay Tipologia Editoriale Page":
                self.listOnDemandCategory(self.currItem)
            elif subtype in ("Raiplay Tipologia Item", "RaiPlay V2 Genere Page"):
                self.listOnDemandAZ(self.currItem)
            elif subtype in ("PLR programma Page", "RaiPlay Programma Item"):
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
            printDBG('raiplay no link')
        elif category == 'raisport_main':
            self.listRaiSportMain(self.currItem)
        elif category == 'raisport_item':
            self.listRaiSportItems(self.currItem)
        elif category == 'raisport_subitem':
            self.listRaiSportVideos(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Raiplay(), True, [])
