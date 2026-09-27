# -*- coding: utf-8 -*-
# Last Modified: 14.06.2026 - Mr.X
# 27.09.2026 - domain topstreamfilm.best; meinecloud.click embeds via its token API (libs/meinecloud.py),
# series seasons/episodes from it too; items keep their page url (INFO), links live in their own key.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://topstreamfilm.best/"


class TopStreamFilm(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "TopStreamFilm", "cookie": "TopStreamFilm.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "templates/topstreamfilm/images/logo-1.png"
        self.MAIN_URL = "https://topstreamfilm.best"
        self.MENU = [{"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("kinofilme")}, {"category": "list_items", "title": _("New"), "url": self.getFullUrl("filme-online-sehen")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serien")}, {"category": "list_value", "title": _("Genres"), "s": ">KATEGORIEN<"}, {"category": "list_value", "title": _("A-Z"), "s": "AZList"}, {"category": "list_value", "title": _("Year"), "s": ">YAHRE<"}, {"category": "list_value", "title": _("Country"), "s": ">LAND<"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("TopStreamFilm.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'href="([^"]+)">Next')[0]
        con = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="TPostMv">', "</article>")
        if not con:
            con = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="Num">', "</tr>")
        for item in con:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)')[0])
            title = self.cm.ph.getSearchGroups(item, 'Title">([^<]+)')[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, "<strong>(.*?)</strong>")[0]
            title = title.split(" &#8211;")[0]
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'Description">([^"]+)</div>')[0])
            dur = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'access_time">([\d]+)m')[0])
            if dur:
                desc = "Spielzeit: %sMin\n%s" % (dur, desc)
            dat = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'"Year">(\d+)<')[0])
            if dat:
                desc = "Jahr: %s\n%s" % (dat, desc)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": desc})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def _meineCloud(self):
        return MeineCloud(self.cm, self.defaultParams, gettytul())

    def listSeasons(self, cItem):
        printDBG("TopStreamFilm.listSeasons")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
        movieUrl = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="(https://meinecloud\.click/movie/[^"]+)"')[0]
        if movieUrl:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": cItem["title"], "desc": desc, "mc_movie": MeineCloud.imdbFromUrl(movieUrl)})
            self.addVideo(params)
            return
        imdb = self.cm.ph.getSearchGroups(data, r"imdb\s*=\s*'(tt\d+)'")[0]
        if imdb:
            seasons = self._meineCloud().seriesEpisodes(imdb)
            for seasonNum, episodes in seasons:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_episodes", "title": "Staffel %d" % seasonNum, "desc": desc, "mc_imdb": imdb, "mc_season": seasonNum, "mc_episodes": episodes})
                self.addDir(params)
            if not seasons:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        serieold = re.findall(r'<div class="tt_season">.*?</ul>', data, re.DOTALL)
        if serieold:
            season = re.findall(r'"#season-(\d+)', serieold[0], re.DOTALL)
            for s in season:
                se = re.findall(r'id="season-%s">.*?</ul>' % s, data, re.DOTALL)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_episodes", "title": "Staffel " + s, "serieold": se, "desc": desc})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("TopStreamFilm.listEpisodes")
        if cItem.get("mc_episodes"):
            seasonNum = cItem["mc_season"]
            for ep in cItem["mc_episodes"]:
                name = self.cleanHtmlStr(ep["title"])
                title = "S%d E%d – %s" % (seasonNum, ep["episode"], name) if name else "S%d E%d" % (seasonNum, ep["episode"])
                params = dict(cItem)
                params.pop("mc_episodes", None)
                params.update({"good_for_fav": True, "title": title, "desc": self.cleanHtmlStr(ep["desc"]) or cItem.get("desc", ""), "mc_episode": "%s/%d/%d" % (cItem["mc_imdb"], seasonNum, ep["episode"]), "mc_url": ep["url"]})
                self.addVideo(params)
        if cItem.get("serieold"):
            seasons = cItem["serieold"]
            ep = re.findall(r'data-title="([^"]+)(.*?</div>)', seasons[0], re.DOTALL)
            for title, d in ep:
                links = re.findall(r'data-link="([^"]+)', d, re.DOTALL)
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": title, "links": links})
                self.addVideo(params)

    def listValue(self, cItem):
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")
        if data:
            data = re.findall("""href=["']([^"']+).*?>([^<]+)""", data[0])
            for url, title in data:
                if any(k in title for k in ("kino", "Dem", "Seri")):
                    continue
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TopStreamFilm.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("index.php?do=search&subaction=search&story=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("TopStreamFilm.getLinksForVideo [%s]" % cItem)
        urltab = []
        if cItem.get("mc_movie"):
            links = self._meineCloud().movieLinks(cItem["mc_movie"])
        elif cItem.get("mc_episode"):
            imdb, season, episode = cItem["mc_episode"].split("/")
            links = self._meineCloud().episodeLinks(imdb, season, episode) or [cItem.get("mc_url", "")]
        else:
            # favourites saved before 27.09.2026 carry the link list in "url"
            links = cItem.get("links") or (cItem["url"] if isinstance(cItem.get("url"), list) else [])
        for url in links:
            if not url or "meinec" in url:
                continue
            if url.startswith("//"):
                url = "https:" + url
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        if not urltab and (cItem.get("mc_movie") or cItem.get("mc_episode")):
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
        return urltab

    def getVideoLinks(self, url):
        printDBG("TopStreamFilm.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def getArticleContent(self, cItem):
        printDBG("TopStreamFilm.getArticleContent [%s]" % cItem)
        if not cItem.get("url") or isinstance(cItem["url"], list):
            return []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0]
        desc = desc if desc else cItem.get("desc", "")
        meta_data = {"director": r'temprop="director" content="([^"]+)"', "released": r'date_range">([^<]+)', "duration": r'access_time">([^<]+)'}
        meta = {}
        for key, pat in meta_data.items():
            value = self.cm.ph.getSearchGroups(data, pat)
            if value:
                meta[key] = value[0]
        return [{"title": cItem["title"], "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": cItem.get("icon", self.DEFAULT_ICON_URL)}], "other_info": meta}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, TopStreamFilm(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes"]
