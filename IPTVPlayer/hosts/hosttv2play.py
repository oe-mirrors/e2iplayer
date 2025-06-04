# -*- coding: utf-8 -*-
# 2025.04.17. Blindspot
###################################################
HOST_VERSION = "1.2"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.hosts import hosturllist as urllist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
###################################################
# FOREIGN import
###################################################
import re
import time
from urllib.parse import unquote
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, ConfigInteger, getConfigListEntry
try:
    from urllib import quote
except:
    from urllib.parse import quote
###################################################
# E2 GUI COMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################
###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tv2play_quality = ConfigYesNo(default=True)
###################################################


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Elérhető legjobb minőség beállítása"), config.plugins.iptvplayer.tv2play_quality))
    return optionList


def gettytul():
    return 'https://tv2play.hu/'


class TV2Play(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tv2play', 'cookie': 'tv2play.cookie'})
        self.MAIN_URL = 'https://tv2play.hu/'
        self.DEFAULT_ICON_URL = "http://www.blindspot.nhely.hu/Thumbnails/tv2play.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("TV2Play.getLinksForVideo")
        sts, r = self.getPage("%s/search/%s" % ("https://tv2play.hu/api", cItem['slug']), {'with_metadata': True})
        if r.meta['status_code'] == 404:
            sts, r = self.getPage(cItem['url'], {'with_metadata': True})
        data = json_loads(r)
        playerId = data["playerId"]
        title = data["title"]
        plot = data["lead"] if "lead" in data else ""
        thumb = "%s/%s" % (self.MAIN_URL, data["imageUrl"]) if "https://" not in data["imageUrl"] else data["imageUrl"]
        sts, r = self.getPage("%s/streaming-url?playerId=%s&stream=undefined" % ("https://tv2play.hu/api", playerId))
        data = json_loads(r)
        if (data["geoBlocked"] is not False):
            return
        sts, r = self.getPage(data["url"])
        json_data = json_loads(r)
        m3u_url = json_data['bitrates']['hls']
        m3u_url = re.sub('^//', 'https://', m3u_url)
        sts, data = self.getPage(m3u_url)
        if not sts:
            return
        videoUrls = []
        uri = urlparser.decorateParamsFromUrl(m3u_url)
        protocol = uri.meta.get('iptv_proto', '')

        printDBG("PROTOCOL [%s] " % protocol)

        urlSupport = self.up.checkHostSupport(uri)
        if 1 == urlSupport:
            retTab = self.up.getVideoLinkExt(uri)
            videoUrls.extend(retTab)
        elif 0 == urlSupport and self._uriIsValid(uri):
            if protocol == 'm3u8':
                use_best = config.plugins.iptvplayer.tv2play_quality.value
                printDBG("Legjobb minőség használata: " + str(use_best))
                retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                printDBG("Lejátszási linkek vége: " + str(retTab[-1]))
                if config.plugins.iptvplayer.tv2play_quality.value:
                   BestLink = str(retTab[-1])
                   url = self.cm.ph.getSearchGroups(BestLink, '''url.+?['"]([^"^']+?)['"]''', 1, True)[0]
                   printDBG("Kész link: " + url)
                   videoUrls.append({'name': 'direct link', 'url': url})
                   return videoUrls
                else:
                   videoUrls.extend(retTab)
                   printDBG("Utolsó best nélkül: " + str(videoUrls))
            elif protocol == 'f4m':
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
            elif protocol == 'mpd':
                retTab = getMPDLinksWithMeta(uri, False)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({'name': 'direct link', 'url': uri})
        return videoUrls

    def _uriIsValid(self, url):
        return '://' in url

    def listMainMenu(self, cItem):
        printDBG('TV2Play.listMainMenu')
        MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('Műsorok'), 'page': 0},
                        {'category': 'search', 'title': _('Keresés'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def exploreItems(self, cItem):
        printDBG('TV2Play.exploreItems')
        sts, data = self.getPage(cItem['url'])
        data = json_loads(data)
        ribbons = []
        index = 0
        plot = ''
        thumb = ''
        if data["contentType"] == "channel":
            ribbons = data["ribbonIds"]
        else:
            if "seasonNumbers" in data and len(data["seasonNumbers"]) > 0:
                for page in data["pages"]:
                    if page["seasonNr"] == cItem['season']:
                        break
                    index += 1
            for tab in data["pages"][index]["tabs"]:
                if tab["tabType"] == "RIBBON":
                    ribbons += tab["ribbonIds"]
                if tab["tabType"] == 'SHOW_INFO':
                    if plot == '' and "description" in tab["showData"]:
                        plot = tab["showData"]["description"]
                        plot = str(plot)
                    if thumb == '' and "imageUrl" in tab["showData"]:
                        thumb = "%s/%s" % (self.MAIN_URL, tab["showData"]["imageUrl"]) if "https://" not in tab["showData"]["imageUrl"] else tab["showData"]["imageUrl"]
        for ribbon in ribbons:
            sts, r = self.getPage("%s/ribbons/%s" % ("https://tv2play.hu/api", ribbon))
            if r:
                data = json_loads(r)
                params = {'category': 'ribbons', 'title': unquote(data['title']), 'id': data['id'], 'icon': thumb if thumb != '' else None, 'desc': plot, 'page': 0}
                self.addDir(params)

    def apiRibbons(self, cItem):
        printDBG('TV2Play.apiRibbons')
        sts, data = self.getPage("%s/ribbons/%s/%s" % ("https://tv2play.hu/api", cItem['id'], cItem['page']))
        data = json_loads(data)
        dirType = 'videos'
        for card in data["cards"]:
            thumb = "%s/%s" % (self.MAIN_URL, card["imageUrl"]) if "https://" not in card["imageUrl"] else card["imageUrl"]
            title = unquote(card["title"])
            if "contentLength" in card:
                plot = ""
                try:
                    sts, r = self.getPage("%s%s/search/%s" % ("https://tv2play.hu/api", "/premium" if card["isPremium"] else "", card["slug"]))
                    episode = json_loads(r)
                    plot = episode["lead"] if "lead" in episode else ""
                    if plot.startswith("<p>"):
                        plot = plot[3:]
                    if plot.endswith("</p>"):
                        plot = plot[:-4]
                except:
                   pass
                if 'EPISODE' in card['cardType']:
                    dirType = 'episodes'
                if 'MOVIE' in card['cardType']:
                    dirType = 'movies'
                params = {'title': title,
                            'slug': card["slug"],
                            'icon': thumb,
                            'desc': plot}
                self.addVideo(params)
        url = "%s/ribbons/%s/%d" % ("https://tv2play.hu/api", cItem['id'], int(cItem['page']) + 1)
        sts, r = self.getPage(url)
        if r != '':
            params = {'category': 'ribbons', 'title': 'Következő oldal', 'url': url, 'icon': None, 'id': cItem['id'], 'page': int(cItem['page']) + 1}
            self.addDir(params)

    def listItems(self, cItem):
        printDBG('TV2Play.listItems')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = json_loads(data)
        if "seasonNumbers" in data and len(data["seasonNumbers"]) > 0:
            if "seo" in data and "description" in data["seo"] and data["seo"]["description"] is not None:
                plot = unquote(data["seo"]["description"])
            else:
                plot = ""
            plot = str(plot)
            for season in data["seasonNumbers"]:
                params = {'category': 'explore_items',
                                'title': "%s. évad" % season,
                                'url': cItem['url'],
                                'season': season,
                                'icon': None,
                                'desc': plot}
                self.addDir(params)
        else:
            cItem.update({'category': 'explore_items', 'season': 0})
            self.exploreItems(cItem)

    def listFilters(self, cItem):
        printDBG('TV2Play.listFilters')
        pageoffset = cItem['page']
        length = 0
        items = []
        if 'url' not in cItem:
            url = "https://tv2-prod.d-saas.com/grrec-tv2-prod-war/JSServlet4?&rn=&cid=&ts=%d&rd=0,TV2_W_CONTENT_LISTING,800,[*platform:web;*domain:tv2play;*currentContent:SHOW;*country:HU;*userAge:18;*pagingOffset:%d],[displayType;channel;title;itemId;duration;isExtra;ageLimit;showId;genre;availableFrom;director;isExclusive;lead;url;contentType;seriesTitle;availableUntil;showSlug;videoType;series;availableEpisode;imageUrl;totalEpisode;category;playerId;currentSeasonNumber;currentEpisodeNumber;part;isPremium]" % (int(time.time()), pageoffset)
        else:
            url = cItem['url'] % (int(time.time()), pageoffset)
        sts, data = self.getPage(url)
        data = re.search(r'(.*)var data = (.*)};(.*)', data, re.S)
        data = json_loads('%s}' % data.group(2))
        items.extend(data["recommendationWrappers"][0]["recommendation"]["items"])
        onv = list(data["recommendationWrappers"][0]["recommendation"]["outputNameValues"])
        for var in onv:
            if var["name"] == "allItemCount":
                length = int(var["value"])
                break
        cItem['page'] += int(len(items))
        for i in items:
            try:
                if i["isPremium"] == "false":
                    if "imageUrl" in i:
                        icon = i["imageUrl"]
                    else:
                        icon = None
                    if 'SEARCH_RESULT' in url:
                        if i['contentType'] == 'VIDEO':
                            vidurl = "https://tv2play.hu/api/search/" + i['url']
                            sts, vidata = self.getPage(vidurl)
                            vidata = json_loads(vidata)
                            slug = vidata['slug']
                            params = {'title': unquote(i['title']), 'slug': slug, 'icon': icon, 'desc': unquote(i['lead']), 'url': "https://tv2play.hu/api/search/" + i['url']}
                            self.addVideo(params)
                        elif i['contentType'] != 'ARTICLE':
                            params = {'category': 'list_items', 'title': unquote(i['title']), 'url': "https://tv2play.hu/api/search/" + i['url'], 'icon': icon, 'desc': unquote(i['lead'])}
                            self.addDir(params)
                    elif i['contentType'] != 'ARTICLE':
                        params = {'category': 'list_items', 'title': unquote(i['title']), 'url': "https://tv2play.hu/api/search/" + i['url'], 'icon': icon, 'desc': unquote(i['lead'])}
                        self.addDir(params)
            except:
               pass
        if cItem['page'] != length:
            params = {'title': "Következő oldal", 'icon': None, 'page': cItem['page'], 'category': 'list_filters'}
            self.addDir(params)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TV2Play.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        title = self.currItem.get("title", '')
        icon = self.currItem.get("icon", '')
        url = self.currItem.get("url", '')

        printDBG("handleService: >> name[%s], category[%s], title[%s], icon[%s] " % (name, category, title, icon))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'explore_items':
            self.exploreItems(self.currItem)
        elif category == 'ribbons':
            self.apiRibbons(self.currItem)
        elif category == 'search':
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'page': 0})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TV2Play.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        searchPattern = quote(searchPattern).replace("%", "%%")
        searchURL = "https://tv2-prod.d-saas.com/grrec-tv2-prod-war/JSServlet4?rn=&cid=&ts=%d&rd=0,TV2_W_SEARCH_RESULT,80,[*platform:web;*domain:tv2play;*query:#SEARCHSTRING#;*country:HU;*userAge:18;*pagingOffset:%d],[displayType;channel;title;itemId;duration;isExtra;ageLimit;showId;genre;availableFrom;director;isExclusive;lead;url;contentType;seriesTitle;availableUntil;showSlug;videoType;series;availableEpisode;imageUrl;totalEpisode;category;playerId;currentSeasonNumber;currentEpisodeNumber;part;isPremium]".replace("#SEARCHSTRING#", searchPattern)
        cItem['url'] = searchURL
        self.listFilters(cItem)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TV2Play(), True, [])
