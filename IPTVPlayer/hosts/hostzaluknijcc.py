# -*- coding: utf-8 -*-
# Last Modified: 28.03.2026 - damagic
###################################################
import re
import json
import base64
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://zaluknij.cc/"


class Zaluknij(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Zaluknij", "cookie": "Zaluknij.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "public/dist/images/lgbt.png"
        self.MAIN_URL = gettytul()
        self.cacheLinks = {}

        self.MENU = [
            {"category": "list_items", "title": _("Filmy Premiery"), "url": self.getFullUrl("filmy-online/sort:premiere/")},
            {"category": "list_items", "title": _("Filmy Nowe Linki"), "url": self.getFullUrl("filmy-online/sort:link/")},
            {"category": "list_items", "title": _("Filmy Oceny na Zaluknij"), "url": self.getFullUrl("filmy-online/sort:rate/")},
            {"category": "list_items", "title": _("Seriale"), "url": self.getFullUrl("seriale-online/index?url=seriale-online%2Findex&sort=recent_series&page=1")},
            {"category": "list_episodes_direct", "title": _("Seriale Nowe Odcinki"), "url": self.getFullUrl("seriale-online/index?url=seriale-online%2Findex&sort=latest_episodes&page=1")},
            {"category": "list_items", "title": _("Dla dzieci"), "url": self.getFullUrl("dla-dzieci/")},
        ] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None, max_retries=3):
        """Pobiera stronę z obsługą Cloudflare i retry"""
        if addParams is None:
            addParams = dict(self.defaultParams)

        addParams["cloudflare_params"] = {"cookie_file": addParams["cookiefile"], "User-Agent": self.HEADER.get("User-Agent"), "max_retries": max_retries, "timeout": 30}

        for attempt in range(max_retries):
            if attempt > 0:
                time.sleep(2)
            sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
            if sts:
                return sts, data
            printDBG("Zaluknij.getPage - attempt %d failed for %s" % (attempt + 1, baseUrl))

        return False, ""

    def fixIconUrl(self, icon_url):
        """Zmienia URL ikony z thumb na big dla lepszej jakości"""
        if icon_url and "thumb" in icon_url:
            icon_url = icon_url.replace("thumb", "big")
        return icon_url

    def listItems(self, cItem, isSearch=False):
        printDBG("Zaluknij.listItems |%s| isSearch=%s" % (cItem, isSearch))

        sts, htm = self.getPage(cItem["url"], max_retries=3)
        if not sts:
            printDBG("Zaluknij.listItems - failed to get page after retries")
            return

        nextPage = self.cm.ph.getSearchGroups(htm, r"""href=['"]([^"']+)["'](?: data-pagenumber='\d+'>|>)Nast""")
        if nextPage:
            nextPage = nextPage[0]

        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'role="listitem', "</a>") or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")

        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')
            if not url:
                continue
            url = url[0]

            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+)')
            if icon:
                icon = self.getFullUrl(icon[0])
                if isSearch:
                    icon = self.fixIconUrl(icon)
            else:
                icon = self.DEFAULT_ICON_URL

            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')
            if title:
                title = self.cleanHtmlStr(title[0])
            else:
                title = "Brak tytułu"
            title = re.sub(r"\s*\[\]\s*", "", title)

            is_serial = "serial" in url.lower()

            if is_serial:
                meta_line = self.cm.ph.getSearchGroups(item, r'<span class="meta-line">(S\d+\s*E\d+)</span>')
                if meta_line:
                    meta_line = self.cleanHtmlStr(meta_line[0])
                    title = "%s [%s]" % (title, meta_line)
            else:
                year = self.cm.ph.getSearchGroups(item, r'class="year">(\d{4})')
                if year:
                    year = year[0]
                    if not isSearch:
                        title = "%s (%s)" % (title, year)
            title = re.sub(r"\s*\[\]\s*", "", title)
            title = title.strip()

            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title.replace("amp;", ""), "url": url, "icon": icon})

            if is_serial:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            next_url = cItem["url"].split("?")[0] + nextPage.replace("amp;", "")
            params.update({"good_for_fav": False, "title": _("Next page"), "url": next_url})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Zaluknij.listEpisodes")
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return

        desc = self.cm.ph.getSearchGroups(data, 'class="description">([^<]+)')
        if desc:
            desc = desc[0]
        else:
            desc = ""

        data = re.findall(r'href="([^"]+)">\W(s\d+e\d+)', data, re.DOTALL)
        for url, episode_num in data:
            params = dict(cItem)
            title = cItem["title"]
            title = re.sub(r"\s*\[\]\s*", "", title)
            title = title.strip()

            params.update({"good_for_fav": True, "title": "%s [%s]" % (title, episode_num.upper()), "url": self.getFullUrl(url), "icon": icon, "desc": desc})
            self.addVideo(params)

    def listEpisodesDirect(self, cItem):
        """Funkcja do wyświetlania najnowszych odcinków seriali"""
        printDBG("Zaluknij.listEpisodesDirect |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return

        nextPage = self.cm.ph.getSearchGroups(htm, r"""href=['"]([^"']+)["'](?: data-pagenumber='\d+'>|>)Nast""")
        if nextPage:
            nextPage = nextPage[0]

        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'role="listitem', "</a>") or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")

        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')
            if not url:
                continue
            url = url[0]

            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+)')
            if icon:
                icon = self.getFullUrl(icon[0])
            else:
                icon = self.DEFAULT_ICON_URL

            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')
            if title:
                title = self.cleanHtmlStr(title[0])
            else:
                title = "Brak tytułu"
            title = re.sub(r"\s*\[\]\s*", "", title)

            meta_line = self.cm.ph.getSearchGroups(item, r'<span class="meta-line">(S\d+\s*E\d+)</span>')
            if meta_line:
                meta_line = self.cleanHtmlStr(meta_line[0])
                title = "%s [%s]" % (title, meta_line)
            title = re.sub(r"\s*\[\]\s*", "", title)
            title = title.strip()

            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title.replace("amp;", ""), "url": url, "icon": icon})
            self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            next_url = cItem["url"].split("?")[0] + nextPage.replace("amp;", "")
            params.update({"good_for_fav": False, "title": _("Next page"), "url": next_url})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Zaluknij.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        search_url = "%sszukaj" % gettytul()
        post_data = "phrase=%s" % urllib_quote(searchPattern)

        printDBG("Zaluknij.listSearchResult - using POST to: %s" % search_url)

        sts, htm = self.getPage(search_url, post_data=post_data, max_retries=3)
        if not sts:
            printDBG("Zaluknij.listSearchResult - POST failed, trying GET fallback")
            cItem["url"] = "%swyszukiwarka?phrase=%s" % (gettytul(), urllib_quote(searchPattern))
            self.listItems(cItem, isSearch=True)
            return

        nextPage = self.cm.ph.getSearchGroups(htm, r"""href=['"]([^"']+)["'](?: data-pagenumber='\d+'>|>)Nast""")
        if nextPage:
            nextPage = nextPage[0]

        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'role="listitem', "</a>") or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")

        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')
            if not url:
                continue
            url = url[0]

            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+)')
            if icon:
                icon = self.getFullUrl(icon[0])
                icon = self.fixIconUrl(icon)
            else:
                icon = self.DEFAULT_ICON_URL

            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')
            if title:
                title = self.cleanHtmlStr(title[0])
            else:
                title = "Brak tytułu"
            title = re.sub(r"\s*\[\]\s*", "", title)

            is_serial = "serial" in url.lower()

            if is_serial:
                meta_line = self.cm.ph.getSearchGroups(item, r'<span class="meta-line">(S\d+\s*E\d+)</span>')
                if meta_line:
                    meta_line = self.cleanHtmlStr(meta_line[0])
                    title = "%s [%s]" % (title, meta_line)
            else:
                year = self.cm.ph.getSearchGroups(item, r'class="year">(\d{4})')
                if year:
                    year = year[0]
                    pass
            title = re.sub(r"\s*\[\]\s*", "", title)
            title = title.strip()

            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title.replace("amp;", ""), "url": url, "icon": icon})

            if is_serial:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            next_url = "%sszukaj?page=%s" % (gettytul(), nextPage)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": next_url})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        """Pobiera linki do wideo z dodatkowymi informacjami o wersji i jakości"""
        printDBG("Zaluknij.getLinksForVideo [%s]" % cItem)
        cacheKey = cItem["url"]
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        retTab = []

        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return []
        link_list_div = ""
        link_list_parts = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "link-list"), ("</div", ">"))
        if link_list_parts and len(link_list_parts) > 1:
            link_list_div = link_list_parts[1]

        if not link_list_div:
            link_list_div = data
        table_parts = self.cm.ph.getDataBeetwenNodes(link_list_div, ("<table", ">"), ("</table", ">"))
        if table_parts and len(table_parts) > 1:
            table = table_parts[1]
            rows = self.cm.ph.getAllItemsBeetwenNodes(table, ("<tr", ">"), ("</tr", ">"))
            printDBG("Zaluknij.getLinksForVideo - found %d rows" % len(rows))

            for row in rows:
                if "<th" in row:
                    continue
                cells = self.cm.ph.getAllItemsBeetwenNodes(row, ("<td", ">"), ("</td", ">"))

                if len(cells) < 2:
                    continue

                player_url = ""
                version = ""
                quality = ""

                for idx, cell in enumerate(cells):
                    if "link-to-video" in cell:
                        iframe_match = re.search(r"""data-iframe=['"]([^"^']+?)['"]""", cell)
                        if iframe_match:
                            try:
                                decoded = base64.b64decode(iframe_match.group(1)).decode("utf-8")
                                iframe_data = json.loads(decoded)
                                player_url = iframe_data.get("src", "")
                            except:
                                pass
                        if not player_url:
                            href_match = re.search(r"""href=['"]([^"^']+?)['"]""", cell)
                            if href_match:
                                player_url = href_match.group(1)
                    elif idx == 2:
                        version = self.cleanHtmlStr(cell)
                    elif idx == 3:
                        quality = self.cleanHtmlStr(cell)

                if not player_url:
                    continue

                if player_url and not player_url.startswith("http"):
                    player_url = self.getFullUrl(player_url)
                name = self.up.getHostName(player_url)
                if version and version not in ["", "Wersja"]:
                    name += " [%s" % version
                    if quality and quality not in ["", "Jakość"]:
                        name += " / %s" % quality
                    name += "]"
                elif quality and quality not in ["", "Jakość"]:
                    name += " [%s]" % quality

                retTab.append({"name": name, "url": strwithmeta(player_url, {"Referer": url}), "need_resolve": 1})
        if not retTab:
            printDBG("Zaluknij.getLinksForVideo - using fallback method")
            data_links = self.cm.ph.getAllItemsBeetwenMarkers(data, 'link-to-video">', "None")
            for item in data_links:
                url_match = re.search(r'href="([^"]+)', item)
                if url_match:
                    video_url = url_match.group(1)
                    retTab.append({"name": self.up.getHostName(video_url).capitalize(), "url": strwithmeta(video_url, {"Referer": gettytul()}), "need_resolve": 1})

        printDBG("Zaluknij.getLinksForVideo - found %d links" % len(retTab))
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, url):
        printDBG("Zaluknij.getVideourls [%s]" % url)
        url = strwithmeta(url)
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if url in self.cacheLinks[key][idx]["url"]:
                        if not self.cacheLinks[key][idx]["name"].startswith("*"):
                            self.cacheLinks[key][idx]["name"] = "*" + self.cacheLinks[key][idx]["name"] + "*"
                        break

        return self.up.getVideoLinkExt(url)

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
            self.listItems(self.currItem, isSearch=False)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_episodes_direct":
            self.listEpisodesDirect(self.currItem)
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
        CHostBase.__init__(self, Zaluknij(), True, [])
