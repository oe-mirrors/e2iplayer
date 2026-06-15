# -*- coding: utf-8 -*-
# Last Modified: 16.06.2026 - damagic
###################################################
import re
import json
import base64
import time
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Components.config import config, ConfigText, getConfigListEntry

try:
    import json
except Exception:
    import simplejson as json


def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return "https://zaluknij.cc/"


class Zaluknij(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(
            self, {"history": "Zaluknij", "cookie": "Zaluknij.cookie"}
        )
        config.plugins.iptvplayer.cloudflare_user = ConfigText(
            default="Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
            fixed_size=False
        )
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["User-Agent"] = config.plugins.iptvplayer.cloudflare_user.value
        self.defaultParams = {
            "header": self.HEADER,
            "use_cookie": True,
            "load_cookie": True,
            "save_cookie": True,
            "cookiefile": self.COOKIE_FILE,
            "with_metadata": True,
        }
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.fixIconUrl(
            self.MAIN_URL + "public/dist/images/lgbt.png", self.MAIN_URL
        )
        self.cacheLinks = {}
        self.cacheDescriptions = {}
        self.cacheDetails = {}
        self.cacheQuickDescs = {}
        self.MENU = [
            {
                "category": "list_items",
                "title": "Filmy Premiery",
                "url": self.getFullUrl("filmy-online/sort:premiere/"),
            },
            {
                "category": "list_items",
                "title": "Filmy Nowe Linki",
                "url": self.getFullUrl("filmy-online/sort:link/"),
            },
            {
                "category": "list_items",
                "title": "Filmy Oceny na Zaluknij",
                "url": self.getFullUrl("filmy-online/sort:rate/"),
            },
            {
                "category": "list_items",
                "title": "Seriale",
                "url": self.getFullUrl(
                    "seriale-online/index?url=seriale-online%2Findex&sort=recent_series&page=1"
                ),
            },
            {
                "category": "list_episodes_direct",
                "title": "Seriale Nowe Odcinki",
                "url": self.getFullUrl(
                    "seriale-online/index?url=seriale-online%2Findex&sort=latest_episodes&page=1"
                ),
            },
            {
                "category": "list_items",
                "title": "Dla dzieci",
                "url": self.getFullUrl("dla-dzieci/"),
            },
        ] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(baseUrl)
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if data.meta.get("cf_user", self.HEADER["User-Agent"]) != self.HEADER["User-Agent"]:
            self.__init__()
        return sts, data

    def fixIconUrl(self, icon_url, referer=None):
        if not icon_url:
            return ""
        if "thumb" in icon_url:
            icon_url = icon_url.replace("thumb", "big")
        icon_url = self.getFullUrl(icon_url)
        cf = self.cm.getCookieItem(self.COOKIE_FILE, "cf_clearance")
        return strwithmeta(
            icon_url,
            {
                "Referer": referer if referer else self.MAIN_URL,
                "User-Agent": self.HEADER["User-Agent"],
                "Cookie": "cf_clearance=%s" % cf if cf else "",
            },
        )

    def getQuickDescription(self, url):
        if url in self.cacheQuickDescs:
            return self.cacheQuickDescs[url]
        try:
            sts, data = self.getPage(url)
            if not sts:
                self.cacheQuickDescs[url] = ""
                return ""
            desc = self.cm.ph.getSearchGroups(
                data, r'<p\s+class="description">([^<]+)'
            )
            if not desc:
                desc = self.cm.ph.getSearchGroups(
                    data, r'<meta\s+name="description"\s+content="([^"]+)'
                )
            if desc:
                desc_text = self.cleanHtmlStr(desc[0]).strip()
                if len(desc_text) > 200:
                    desc_text = desc_text[:200] + "..."
            else:
                desc_text = ""
            self.cacheQuickDescs[url] = desc_text
            self.cacheDescriptions[url] = desc_text
            return desc_text
        except Exception as e:
            printDBG("getQuickDescription error: %s" % str(e))
            self.cacheQuickDescs[url] = ""
            return ""

    def extractMovieDetails(self, data):
        details = {"categories": [], "version": "", "quality": "", "year": ""}
        year = self.cm.ph.getSearchGroups(
            data, r'<sup><a href="[^"]+">(\d{4})</a></sup>'
        )
        if year:
            details["year"] = year[0]
        cat_pattern = r'<li itemprop="genre"><a href="[^"]+">([^<]+)</a></li>'
        categories = re.findall(cat_pattern, data)
        if categories:
            details["categories"] = categories
        table_parts = self.cm.ph.getDataBeetwenNodes(
            data, ("<table", ">"), ("</table", ">")
        )
        if table_parts and len(table_parts) > 1:
            table = table_parts[1]
            rows = self.cm.ph.getAllItemsBeetwenNodes(
                table, ("<tr", ">"), ("</tr", ">")
            )
            versions = set()
            qualities = set()
            for row in rows:
                if "<th" in row:
                    continue
                cells = self.cm.ph.getAllItemsBeetwenNodes(
                    row, ("<td", ">"), ("</td", ">")
                )
                if len(cells) >= 4:
                    if "link-to-video" in cells[1]:
                        if len(cells) > 2:
                            version = self.cleanHtmlStr(cells[2])
                            if version and version not in ["", "Wersja"]:
                                versions.add(version)
                        if len(cells) > 3:
                            quality = self.cleanHtmlStr(cells[3])
                            if quality and quality not in ["", "Jakość"]:
                                qualities.add(quality)
            if versions:
                details["version"] = ", ".join(sorted(versions))
            if qualities:
                details["quality"] = ", ".join(sorted(qualities))
        return details

    def getArticleContent(self, cItem):
        printDBG("Zaluknij.getArticleContent [%s]" % cItem)
        url = cItem.get("url", "")
        title = cItem.get("title", "")
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        if not url:
            return []
        details = {}
        if url in self.cacheDetails:
            details = self.cacheDetails[url]
            desc = self.cacheDescriptions.get(url, "")
        else:
            sts, data = self.getPage(url)
            if sts:
                desc = self.cm.ph.getSearchGroups(
                    data, r'<p\s+class="description">([^<]+)'
                )
                if not desc:
                    desc = self.cm.ph.getSearchGroups(
                        data, r'<meta\s+name="description"\s+content="([^"]+)'
                    )
                if desc:
                    desc_text = self.cleanHtmlStr(desc[0])
                    self.cacheDescriptions[url] = desc_text
                else:
                    desc_text = ""
                details = self.extractMovieDetails(data)
                self.cacheDetails[url] = details
            else:
                desc_text = ""
        text_parts = []
        text_parts.append(title)
        text_parts.append("")
        if details.get("year"):
            text_parts.append("Rok: %s" % details["year"])
        if details.get("categories"):
            text_parts.append("Kategoria: %s" % ", ".join(details["categories"]))
        if details.get("version"):
            text_parts.append("Wersja: %s" % details["version"])
        if details.get("quality"):
            text_parts.append("Jakość: %s" % details["quality"])
        desc_text = self.cacheDescriptions.get(url, "")
        if desc_text:
            text_parts.append("")
            text_parts.append("Opis:")
            text_parts.append(desc_text)
        if not desc_text and not details:
            text_parts.append("")
            text_parts.append("Brak opisu i szczegółów")
        final_text = "\n".join(text_parts)
        return [
            {
                "title": title,
                "text": final_text,
                "images": [{"title": "", "url": icon}],
                "other_info": {"custom_items_list": []},
            }
        ]

    def listItems(self, cItem, isSearch=False):
        printDBG("Zaluknij.listItems |%s| isSearch=%s" % (cItem, isSearch))
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            printDBG("Zaluknij.listItems - failed to get page after retries")
            return
        nextPage = self.cm.ph.getSearchGroups(
            htm, r"""href=['"]([^"']+)["'](?: data-pagenumber='\d+'>|>)Nast"""
        )
        if nextPage:
            nextPage = nextPage[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(
            htm, 'role="listitem', "</a>"
        ) or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')
            if not url:
                continue
            url = url[0]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+)')
            if icon:
                icon = self.fixIconUrl(icon[0], cItem["url"])
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
                meta_line = self.cm.ph.getSearchGroups(
                    item, r'<span class="meta-line">(S\d+\s*E\d+)</span>'
                )
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
            quick_desc = self.getQuickDescription(url)
            params = dict(cItem)
            params.update(
                {
                    "good_for_fav": True,
                    "category": "video",
                    "title": title.replace("amp;", ""),
                    "url": url,
                    "icon": icon,
                    "desc": quick_desc,
                }
            )
            if is_serial:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            next_url = cItem["url"].split("?")[0] + nextPage.replace("amp;", "")
            params.update(
                {"good_for_fav": False, "title": _("Next page"), "url": next_url}
            )
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
        episodes = re.findall(r'href="([^"]+)">\W(s\d+e\d+)', data, re.DOTALL)
        for url, episode_num in episodes:
            params = dict(cItem)
            title = cItem["title"]
            title = re.sub(r"\s*\[\]\s*", "", title)
            title = title.strip()
            params.update(
                {
                    "good_for_fav": True,
                    "title": "%s [%s]" % (title, episode_num.upper()),
                    "url": self.getFullUrl(url),
                    "icon": icon,
                    "desc": desc,
                }
            )
            self.addVideo(params)

    def listEpisodesDirect(self, cItem):
        printDBG("Zaluknij.listEpisodesDirect |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(
            htm, r"""href=['"]([^"']+)["'](?: data-pagenumber='\d+'>|>)Nast"""
        )
        if nextPage:
            nextPage = nextPage[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(
            htm, 'role="listitem', "</a>"
        ) or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')
            if not url:
                continue
            url = url[0]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+)')
            if icon:
                icon = self.fixIconUrl(icon[0], cItem["url"])
            else:
                icon = self.DEFAULT_ICON_URL
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')
            if title:
                title = self.cleanHtmlStr(title[0])
            else:
                title = "Brak tytułu"
            title = re.sub(r"\s*\[\]\s*", "", title)
            meta_line = self.cm.ph.getSearchGroups(
                item, r'<span class="meta-line">(S\d+\s*E\d+)</span>'
            )
            if meta_line:
                meta_line = self.cleanHtmlStr(meta_line[0])
                title = "%s [%s]" % (title, meta_line)
            title = re.sub(r"\s*\[\]\s*", "", title)
            title = title.strip()
            quick_desc = self.getQuickDescription(url)
            params = dict(cItem)
            params.update(
                {
                    "good_for_fav": True,
                    "category": "video",
                    "title": title.replace("amp;", ""),
                    "url": url,
                    "icon": icon,
                    "desc": quick_desc,
                }
            )
            self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            next_url = cItem["url"].split("?")[0] + nextPage.replace("amp;", "")
            params.update(
                {"good_for_fav": False, "title": _("Next page"), "url": next_url}
            )
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG(
            "Zaluknij.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]"
            % (cItem, searchPattern, searchType)
        )
        cItem = dict(cItem)
        search_url = "%sszukaj" % gettytul()
        post_data = "phrase=%s" % urllib_quote(searchPattern)
        printDBG("Zaluknij.listSearchResult - using POST to: %s" % search_url)
        sts, htm = self.getPage(search_url, post_data=post_data)
        if not sts:
            printDBG("Zaluknij.listSearchResult - POST failed, trying GET fallback")
            cItem["url"] = "%swyszukiwarka?phrase=%s" % (
                gettytul(),
                urllib_quote(searchPattern),
            )
            self.listItems(cItem, isSearch=True)
            return
        nextPage = self.cm.ph.getSearchGroups(
            htm, r"""href=['"]([^"']+)["'](?: data-pagenumber='\d+'>|>)Nast"""
        )
        if nextPage:
            nextPage = nextPage[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(
            htm, 'role="listitem', "</a>"
        ) or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')
            if not url:
                continue
            url = url[0]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+)')
            if icon:
                icon = self.fixIconUrl(icon[0], cItem["url"])
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
                meta_line = self.cm.ph.getSearchGroups(
                    item, r'<span class="meta-line">(S\d+\s*E\d+)</span>'
                )
                if meta_line:
                    meta_line = self.cleanHtmlStr(meta_line[0])
                    title = "%s [%s]" % (title, meta_line)
            title = re.sub(r"\s*\[\]\s*", "", title)
            title = title.strip()
            quick_desc = self.getQuickDescription(url)
            params = dict(cItem)
            params.update(
                {
                    "good_for_fav": True,
                    "category": "video",
                    "title": title.replace("amp;", ""),
                    "url": url,
                    "icon": icon,
                    "desc": quick_desc,
                }
            )
            if is_serial:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            next_url = "%sszukaj?page=%s" % (gettytul(), nextPage)
            params.update(
                {"good_for_fav": False, "title": _("Next page"), "url": next_url}
            )
            self.addDir(params)

    def getLinksForVideo(self, cItem):
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
        desc = self.cm.ph.getSearchGroups(data, r'<p\s+class="description">([^<]+)')
        if desc:
            self.cacheDescriptions[url] = self.cleanHtmlStr(desc[0])
        link_list_div = ""
        link_list_parts = self.cm.ph.getDataBeetwenNodes(
            data, ("<div", ">", "link-list"), ("</div", ">")
        )
        if link_list_parts and len(link_list_parts) > 1:
            link_list_div = link_list_parts[1]
        if not link_list_div:
            link_list_div = data
        table_parts = self.cm.ph.getDataBeetwenNodes(
            link_list_div, ("<table", ">"), ("</table", ">")
        )
        if table_parts and len(table_parts) > 1:
            table = table_parts[1]
            rows = self.cm.ph.getAllItemsBeetwenNodes(
                table, ("<tr", ">"), ("</tr", ">")
            )
            for row in rows:
                if "<th" in row:
                    continue
                cells = self.cm.ph.getAllItemsBeetwenNodes(
                    row, ("<td", ">"), ("</td", ">")
                )
                if len(cells) < 2:
                    continue
                player_url = ""
                version = ""
                quality = ""
                for idx, cell in enumerate(cells):
                    if "link-to-video" in cell:
                        iframe_match = re.search(
                            r"""data-iframe=['"]([^"^']+?)['"]""", cell
                        )
                        if iframe_match:
                            try:
                                decoded = base64.b64decode(
                                    iframe_match.group(1)
                                ).decode("utf-8")
                                iframe_data = json.loads(decoded)
                                player_url = iframe_data.get("src", "")
                            except Exception as e:
                                printDBG("iframe decode error: %s" % str(e))
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
                hostname = self.up.getHostName(player_url)
                name = hostname.split(".")[0] if "." in hostname else hostname
                if version and version not in ["", "Wersja"]:
                    name += " [%s" % version
                    if quality and quality not in ["", "Jakość"]:
                        name += " / %s" % quality
                    name += "]"
                elif quality and quality not in ["", "Jakość"]:
                    name += " [%s]" % quality
                retTab.append(
                    {
                        "name": name,
                        "url": strwithmeta(player_url, {"Referer": url}),
                        "need_resolve": 1,
                    }
                )
        if not retTab:
            data_links = self.cm.ph.getAllItemsBeetwenMarkers(
                data, 'link-to-video">', "None"
            )
            for item in data_links:
                url_match = re.search(r'href="([^"]+)', item)
                if url_match:
                    video_url = url_match.group(1)
                    hostname = self.up.getHostName(video_url)
                    short_name = hostname.split(".")[0] if "." in hostname else hostname
                    retTab.append(
                        {
                            "name": short_name.capitalize(),
                            "url": strwithmeta(video_url, {"Referer": gettytul()}),
                            "need_resolve": 1,
                        }
                    )
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
                            self.cacheLinks[key][idx]["name"] = (
                                "*" + self.cacheLinks[key][idx]["name"] + "*"
                            )
                        break
        return self.up.getVideoLinkExt(url)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG(
            "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] "
            % (name, category)
        )
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
            self.listsHistory(
                {"name": "history", "category": "search"}, "desc", _("Type: ")
            )
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Zaluknij(), True, [])

    def withArticleContent(self, cItem):
        return True
