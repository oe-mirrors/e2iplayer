# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - Hotmix Radio (hotmixradio.com), new host
#   ~70 themed web radio stations (Icecast MP3) from the Next.js home page data (one request, cached):
#   all stations, categories (Chill out, Party Time, Time Travel, ...), search (station name, description,
#   categories).
#   Live radio: audio rows, no watched flag. INFO = description + categories.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc


def GetConfigList():
    return []


def gettytul():
    return "https://hotmixradio.com/"


class HotmixRadio(CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "live", "desc")
    IMG_BASE = "https://checkout.hotmixradio.com"

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "hotmixradio", "cookie": "hotmixradio.cookie"})
        self.MAIN_URL = "https://hotmixradio.com/"
        self.DEFAULT_ICON_URL = "https://hotmixradio.com/favicon.ico"
        self.HEADER = {"User-Agent": self.cm.getDefaultUserAgent('chrome'),
                       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Accept-Language": "en-US,en;q=0.9"}
        self.defaultParams = {"header": self.HEADER}
        self.cacheRadios = []
        self.MENU = [{"category": "list_radios", "title": _("All stations")},
                     {"category": "list_categories", "title": _("Categories")}] + self.searchItems()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    ###################################################
    # data
    ###################################################
    @staticmethod
    def _objectAt(text, start):
        # the balanced {...} starting at text[start]
        depth = 0
        inStr = False
        esc = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if inStr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    inStr = False
            elif ch == '"':
                inStr = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:idx + 1]
        return ""

    def _loadRadios(self):
        if self.cacheRadios:
            return self.cacheRadios
        sts, data = self.getPage(self.getFullUrl("/en"))
        if not sts or not data:
            return []
        flight = []
        for chunk in re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', data):
            try:
                flight.append(json_loads('"%s"' % chunk))
            except Exception:
                printExc()
        flight = "".join(flight)
        radios = []
        seen = set()
        for match in re.finditer(r'\{"id":\d+,"name":', flight):
            try:
                obj = ensure_str_deep(json_loads(self._objectAt(flight, match.start())))
            except Exception:
                continue
            url = obj.get("url") if isinstance(obj, dict) else ""
            if not url or not self.cm.isValidUrl(url) or obj["id"] in seen or obj.get("active") is False:
                continue
            seen.add(obj["id"])
            cats = []
            for cat in (obj.get("categories") or []):
                if isinstance(cat, dict) and cat.get("name"):
                    cats.append((cat.get("slug") or cat["name"], self.cleanHtmlStr(cat["name"]), cat.get("image_url") or ""))
            desc = obj.get("description")
            radios.append({"id": obj["id"], "title": self.cleanHtmlStr(obj.get("name") or ""), "url": url,
                           "icon": self._img(obj.get("image_large") or obj.get("image_small") or ""),
                           "desc": self.cleanHtmlStr(desc) if desc and not isinstance(desc, bool) else "", "cats": cats})
        radios.sort(key=lambda r: r["title"].lower())
        self.cacheRadios = radios
        return radios

    def _img(self, path):
        if not path:
            return ""
        return path if path.startswith("http") else self.IMG_BASE + path

    def _addRadio(self, radio):
        catNames = ", ".join([c[1] for c in radio["cats"]])
        desc = radio["desc"]
        if catNames:
            desc = (desc + "[/br]" if desc else "") + catNames
        self.addAudio({"good_for_fav": True, "live": True, "title": radio["title"], "url": radio["url"],
                       "icon": radio["icon"], "desc": desc})

    ###################################################
    # lists
    ###################################################
    def listRadios(self, cItem):
        slug = cItem.get("cat_slug", "")
        for radio in self._loadRadios():
            if slug and slug not in [c[0] for c in radio["cats"]]:
                continue
            self._addRadio(radio)

    def listCategories(self, cItem):
        cats = {}
        for radio in self._loadRadios():
            for slug, name, img in radio["cats"]:
                if slug not in cats:
                    cats[slug] = [name, img, 0]
                cats[slug][2] += 1
        for slug in sorted(cats, key=lambda s: cats[s][0].lower()):
            name, img, count = cats[slug]
            params = dict(cItem)
            params.update({"category": "list_radios", "title": "%s (%d)" % (name, count), "cat_slug": slug,
                           "icon": self._img(img), "good_for_fav": True})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = (searchPattern or "").strip().lower()
        if not pattern:
            return
        for radio in self._loadRadios():
            text = " ".join([radio["title"], radio["desc"]] + [c[1] for c in radio["cats"]]).lower()
            if pattern in text:
                self._addRadio(radio)

    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("HotmixRadio.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if not self.cm.isValidUrl(url):
            return []
        return [{"name": "MP3", "url": self.up.decorateUrl(url, {"iptv_livestream": True}), "need_resolve": 0}]

    def getArticleContent(self, cItem):
        otherInfo = {}
        for radio in self._loadRadios():
            if radio["url"] == cItem.get("url"):
                if radio["cats"]:
                    otherInfo["genres"] = ", ".join([c[1] for c in radio["cats"]])
                break
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": cItem.get("desc", ""),
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "audio":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("HotmixRadio.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_radios":
            self.listRadios(self.currItem)
        elif category == "list_categories":
            self.listCategories(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, HotmixRadio(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("type") == "audio"
