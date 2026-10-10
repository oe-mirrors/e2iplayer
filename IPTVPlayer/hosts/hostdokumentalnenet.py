# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - rewrite for the new WordPress theme (twentytwentythree, the old "post-item" cards and the
#   categories sidebar are gone): lists, categories and search from the site's REST API (wp-json/wp/v2,
#   last page from X-WP-TotalPages), the player is the ok.ru iframe of the post page (many old posts lost
#   their video - "no stream" then); First / Jump / Next page, watched flag, downloaded marker on the post
#   url, favourites, sidecar, INFO with the site's data (full description, date, categories),
#   "Title (Year)" names when the title or the address has the year; the login / password options of
#   another host (plusdede) it declared are gone, default user agent
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://dokumentalne.net/"


class DokumentalneNET(GenericFolderWatchedScraperMixin, CBaseHostClass):
    PER_PAGE = 30
    POST_FIELDS = "id,date,link,title,excerpt,categories,featured_media,_links,_embedded"
    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "desc", "post_id", "date", "cat_id", "search_pattern")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "dokumentalne.net", "cookie": "dokumentalne.net.cookie"})
        self.MAIN_URL = gettytul()
        self.API = self.MAIN_URL + "wp-json/wp/v2/"
        self.DEFAULT_ICON_URL = "https://dokumentalne.net/wp-content/uploads/2016/11/dokumentalne_logo_1.png"
        self.HEADER = self.cm.getDefaultHeader()
        self.HEADER["Referer"] = self.MAIN_URL
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.catNames = None
        self.MENU = [{"category": "list_items", "title": _("Latest"), "good_for_fav": True},
                     {"category": "list_cats", "title": _("Categories")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("dokumentalnenet")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self.cm.iriToUri(url), addParams, post_data)

    def _json(self, url):
        # (json, X-WP-TotalPages)
        params = dict(self.defaultParams)
        params.update({"with_metadata": True, "collect_all_headers": True})
        sts, data = self.getPage(url, params)
        if not sts:
            return None, 0
        try:
            total = int((getattr(data, "meta", None) or {}).get("x-wp-totalpages", 0) or 0)
        except (TypeError, ValueError):
            total = 0
        try:
            return json_loads(data), total
        except Exception:
            printExc()
        return None, 0

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("type") == "video":
                url = str(cItem.get("url", "") or "").strip()
                return "video:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def _categoryNames(self):
        if self.catNames is None:
            self.catNames = {}
            data, _total = self._json(self.API + "categories?per_page=100&hide_empty=true&_fields=id,name,count")
            for cat in data if isinstance(data, list) else []:
                if isinstance(cat, dict) and cat.get("id"):
                    self.catNames[cat["id"]] = {"name": self.cleanHtmlStr(cat.get("name", "")), "count": cat.get("count", 0)}
        return self.catNames

    @staticmethod
    def _icon(post):
        try:
            media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
            media = media[0] if media and isinstance(media[0], dict) else {}
            sizes = (media.get("media_details") or {}).get("sizes") or {}
            for size in ("medium_large", "medium", "full"):
                if isinstance(sizes.get(size), dict) and sizes[size].get("source_url"):
                    return sizes[size]["source_url"]
            return media.get("source_url", "") or ""
        except Exception:
            printExc()
        return ""

    def _displayTitle(self, title, url):
        # "Ostatnie dni Hitlera [HD]" / "Dlaczego psy nas kochają (2020)" - the year from the title or the address
        if not IsMediaNamingNormalized():
            return title
        year = (re.findall(r"\(((?:19|20)\d\d)\)", title) or [""])[-1]
        if not year:
            # "...-2019/" - unless the year is part of the title ("Powstanie 1944")
            year = (re.findall(r"-((?:19|20)\d\d)$", url.rstrip("/")) or [""])[-1]
            if year in title:
                year = ""
        clean = re.sub(r"\s*\[HD\]\s*", " ", title).strip()
        return normalizeMediathekTitle(clean, year=year, isMovie=True) if year else clean

    def _postsUrl(self, cItem):
        url = "%sposts?per_page=%d&_embed=wp:featuredmedia&_fields=%s" % (self.API, self.PER_PAGE, self.POST_FIELDS)
        if cItem.get("cat_id"):
            url += "&categories=%s" % cItem["cat_id"]
        if cItem.get("search_pattern"):
            url += "&search=%s" % urllib_quote_plus(cItem["search_pattern"])
        return url

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        printDBG("DokumentalneNET.listCategories")
        cats = self._categoryNames()
        for cid, cat in sorted(cats.items(), key=lambda c: c[1]["name"].lower()):
            if not cat["count"]:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": cat["name"], "cat_id": cid, "desc": "%s: %s" % (_("Videos"), cat["count"])})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("DokumentalneNET.listItems [%s]" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        url = self._postsUrl(cItem)
        data, totalPages = self._json(url + "&page=%d" % page)
        if not isinstance(data, list):
            data = []
        cats = self._categoryNames()
        for post in data:
            try:
                link = post.get("link", "")
                title = self.cleanHtmlStr((post.get("title") or {}).get("rendered", ""))
                if not link or not title:
                    continue
                date = (post.get("date") or "")[:10]
                catTxt = ", ".join(cats[c]["name"] for c in post.get("categories") or [] if c in cats)
                excerpt = self.cleanHtmlStr((post.get("excerpt") or {}).get("rendered", ""))
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "category": "video", "title": self._displayTitle(title, link), "raw_title": title, "url": link,
                               "post_id": post.get("id", ""), "date": date, "icon": self._icon(post) or self.DEFAULT_ICON_URL,
                               "desc": " | ".join(x for x in (date, catTxt) if x) + ("[/br]" + excerpt if excerpt else "")})
                self.addVideo(params)
            except Exception:
                printExc()
        if cItem.get("search_pattern") and not data and page == 1:
            SetIPTVPlayerLastHostError(_("No matching entries found."))
        hasNext = page < totalPages if totalPages else len(data) >= self.PER_PAGE
        # the page number drives the request; the template (the same API url) only gives Jump its target
        addPagingItems(self, cItem, page, bool(data) and hasNext, totalPages, url.replace("{", "{{").replace("}", "}}") + "&page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("DokumentalneNET.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "search_pattern": searchPattern, "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _playerUrls(self, data):
        # <div class="dokumentalne-video-embed"><iframe src="https://ok.ru/videoembed/..."> inside the post content
        content = data.split('class="entry-content', 1)[-1] if 'class="entry-content' in data else ""
        content = content.split('<div class="wp-block-template-part', 1)[0]
        urls = []
        for url in re.findall(r'<iframe[^>]+?src=["\']([^"\']+)["\']', content) + re.findall(r'<(?:source|video)[^>]+?src=["\']([^"\']+)["\']', content):
            url = self.cleanHtmlStr(url)
            url = "https:" + url if url.startswith("//") else url
            if self.cm.isValidUrl(url) and url not in urls:
                urls.append(url)
        return urls

    def getLinksForVideo(self, cItem):
        printDBG("DokumentalneNET.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        urltab = []
        for url in self._playerUrls(data):
            if re.search(r"\.mp4(?:$|\?)", url):
                urltab.append({"name": "MP4", "url": strwithmeta(url, {"Referer": cItem["url"], "User-Agent": self.HEADER["User-Agent"]}), "need_resolve": 0})
            else:
                urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            # many posts of the old theme lost their player when the site moved to the new one
            SetIPTVPlayerLastHostError(_("The video has been removed."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("DokumentalneNET.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("DokumentalneNET.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title", "") or cItem.get("title", "")
        text, otherInfo = cItem.get("desc", ""), {}
        fields = "&_fields=id,date,title,content,categories,tags,_links,_embedded&_embed=wp:term"
        if cItem.get("post_id"):
            post, _total = self._json("%sposts/%s?%s" % (self.API, cItem["post_id"], fields[1:]))
        else:
            # favourites of the old version: only the post url
            slug = cItem.get("url", "").rstrip("/").rsplit("/", 1)[-1]
            post, _total = self._json("%sposts?slug=%s%s" % (self.API, urllib_quote_plus(slug), fields))
            post = post[0] if isinstance(post, list) and post else None
        if isinstance(post, dict):
            title = self.cleanHtmlStr((post.get("title") or {}).get("rendered", "")) or title
            content = (post.get("content") or {}).get("rendered", "") or ""
            text = self.cleanHtmlStr(content.replace("</p>", "[/br]").replace("<br />", "[/br]")).strip() or text
            if post.get("date"):
                otherInfo["released"] = post["date"][:10]
            terms = (post.get("_embedded") or {}).get("wp:term") or []
            for group in terms:
                for term in group if isinstance(group, list) else []:
                    if not isinstance(term, dict) or not term.get("name"):
                        continue
                    key = "categories" if term.get("taxonomy") == "category" else "genres"
                    name = self.cleanHtmlStr(term["name"])
                    otherInfo[key] = "%s, %s" % (otherInfo[key], name) if otherInfo.get(key) else name
        icon = cItem.get("icon", "") or self.DEFAULT_ICON_URL
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("DokumentalneNET.handleService name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_cats":
            self.listCategories(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, DokumentalneNET(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("dokumentalnenet")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video"
