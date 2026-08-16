# -*- coding: utf-8 -*-
# Last modified: 01/12/2025
# HwnaTurkya Host (Modified By Mohamed Elsafty)
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Components.config import ConfigText, config, getConfigListEntry
import re
import time

config.plugins.iptvplayer.hwnaturkya_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.hwnaturkya_alt_domain))
    return optionList


def gettytul():
    return "HwnaTurkya"


class HwnaTurkya(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "hwnaturkya", "cookie": "hwnaturkya.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "https://hwnaturkya.com/assets/themes/3arbserv/images/logo.png"
        self.HEADER = self.cm.getDefaultHeader()
        self.AJAX_HEADER = self.HEADER
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote_plus(baseUrl, safe="://")
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        if post_data is None:
            addParams["load_cookie"] = False
            addParams["save_cookie"] = True
        max_retries = 3
        for attempt in range(max_retries):
            try:
                sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
                if sts and data:
                    return sts, data
            except Exception as e:
                printDBG("hwnaturkya.getPage retry %d failed: %s" % (attempt + 1, str(e)))
            time.sleep(1.5)
        printDBG("[hwnaturkya] Retrying {} failed after {} attempts.".format(baseUrl, max_retries))
        return False, ""

    def selectDomain(self):
        domains = ["https://hwnaturkya.com/"]
        alt_domain = config.plugins.iptvplayer.hwnaturkya_alt_domain.value.strip()
        if self.cm.isValidUrl(alt_domain):
            if not alt_domain.endswith("/"):
                alt_domain += "/"
            domains.insert(0, alt_domain)
        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and "هنا تركيا" in data:
                self.setMainUrl(self.cm.meta["url"])
                return
        self.MAIN_URL = domains[0]

    def getFullIconUrl(self, url):
        iconUrl = CBaseHostClass.getFullIconUrl(self, url.strip())
        return iconUrl if iconUrl else ""

    def listMainMenu(self, cItem):
        printDBG("HwnaTurkya.listMainMenu")
        menuItems = [{"category": "movies", "title": "الأفـــلام", "icon": self.DEFAULT_ICON_URL, "name": "movies"}, {"category": "series", "title": "مســلـســلات", "icon": self.DEFAULT_ICON_URL, "name": "series"}, {"category": "search", "title": _("Search"), "search_item": True}, {"category": "search_history", "title": _("Search history")}]
        self.listsTab(menuItems, cItem)

    def listCatItems(self, cItem, nextCategory):
        printDBG("HwnaTurkya.listCatItems cItem[%s]" % str(cItem))
        current_category = self.currItem.get("category", "")
        items = []
        if current_category == "movies":
            items = [{"category": nextCategory, "name": current_category, "title": "أفــلام متــرجـمـة", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/افلام-تركية-مترجمة.html/")}, {"category": nextCategory, "name": current_category, "title": "أفــلام مــدبـلجـة", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/افلام-تركية-مدبلجة.html/")}]
        elif current_category == "series":
            items = [{"category": nextCategory, "name": current_category, "title": "مسـلـسـلات متــرجـمـة", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/مسلسلات-تركية-مترجمة.html/")}, {"category": nextCategory, "name": current_category, "title": "مسـلـسـلات مــدبـلجـة", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/مسلسلات-تركية-مدبلجة.html/")}]
        self.listsTab(items, cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("HwnaTurkya.listItems cItem[%s]" % str(cItem))
        current_page = cItem.get("page", 1)
        item_type = cItem.get("name", "")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        YELLOW = E2ColoR("yellow")
        WHITE = E2ColoR("white")
        pagination_data = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "pagination"), ("</ul", ">"), True)[1]
        next_page_url = self.getFullUrl(self.cm.ph.getSearchGroups(pagination_data, r"href=['\"]([^\"^']+/page%s?)['\"]" % (current_page + 1))[0])
        added_titles = []
        content_data = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "main-content bg1"), ("<footer", ">", "bg1"), True)[1]
        articles = self.cm.ph.getAllItemsBeetwenMarkers(content_data, ("<article", ">", "post"), ("</article", ">"))
        for article in articles:
            icon_url = self.getFullIconUrl(self.cm.ph.getSearchGroups(article, r"data-original=['\"]([^\"^']+?)['\"]")[0])
            item_url = self.getFullUrl(self.cm.ph.getSearchGroups(article, r"href=['\"]([^\"^']+?)['\"]")[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(article, r"title=['\"]([^\"^']+?)['\"]")[0]).split("الحلقة")[0]
            description_parts = []
            quality_match = self.cm.ph.getSearchGroups(article, r"quality[^>]*>([^<]+?)<")
            if quality_match and quality_match[0]:
                quality = quality_match[0].strip()
                if quality:
                    description_parts.append("%sQuality:%s %s" % (YELLOW, WHITE, quality))
            rating_match = self.cm.ph.getSearchGroups(article, r"icon-star-full2[^>]*></i>([^<]+?)<")
            if rating_match and rating_match[0]:
                rating = rating_match[0].strip()
                if rating:
                    description_parts.append("%sIMDB Rating:%s %s" % (YELLOW, WHITE, rating))
            views_match = self.cm.ph.getSearchGroups(article, r"icon-eye2[^>]*></i>([^<]+?)<")
            if views_match and views_match[0]:
                views = views_match[0].strip()
                if views:
                    description_parts.append("%sViews:%s %s" % (YELLOW, WHITE, views))
            description = "\n".join(description_parts)
            cItem["EPG"] = title
            cleaned_title = self.CleanTitleName(title, sDesc=description)
            title = cleaned_title["title_display"] if title else ""
            full_description = cleaned_title["desc"]
            if item_type == "movies" or "FILM" in full_description:
                params = dict(cItem)
                params.update({"media_type": True, "good_for_fav": True, "title": title, "url": item_url, "prev_url": item_url, "icon": icon_url, "desc": full_description})
                self.addVideo(params)
            else:
                if title not in added_titles:
                    added_titles.append(title)
                    params = dict(cItem)
                    params.update({"category": nextCategory, "media_type": True, "good_for_fav": True, "title": title, "url": item_url, "icon": icon_url, "desc": full_description})
                    self.addDir(params)
        if next_page_url:
            params = dict(cItem)
            params.update({"title": "%s%s%s" % (E2ColoR("yellow"), _("Next page"), E2ColoR("white")), "url": next_page_url, "page": current_page + 1})
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("HwnaTurkya.exploreItems cItem[%s]" % str(cItem))
        item_url = cItem["url"]
        sts, data = self.getPage(item_url)
        if not sts:
            return
        cItem["prev_url"] = item_url
        description = ""
        desc_data = self.cm.ph.getDataBeetwenNodes(data, ("<h3", ">", "story"), ("</h3>", ">"), False)[1]
        if desc_data:
            description = self.cleanHtmlStr(desc_data).strip()
        series_name = cItem.get("title", "").strip()
        if series_name.startswith("مسلسل "):
            series_name = series_name.replace("مسلسل ", "")
        seasons_data = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "getSeasonsBySeries"), ("<div", ">", "owl-nav"), False)[1]
        if not seasons_data:
            seasons_data = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "getSeasonsBySeries"), ("<div", ">", "getPostRand"), True)[1]
        if seasons_data:
            seasons = self.cm.ph.getAllItemsBeetwenMarkers(seasons_data, ("<div", ">", "block-post"), ("</a", ">"))
            if seasons:
                self.addMarker({"title": "%sمـــواســم%s" % (E2ColoR("yellow"), E2ColoR("white")), "icon": cItem["icon"], "desc": ""})
                for season in seasons:
                    season_url = self.getFullUrl(self.cm.ph.getSearchGroups(season, r"href=['\"]([^\"^']+?)['\"]")[0])
                    if not season_url:
                        continue
                    season_title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(season, ("<div", ">", "seasonNum"), ("</div>", ">"), False)[1])
                    if not season_title:
                        season_title = self.cm.ph.getSearchGroups(season, r"title=['\"]([^\"^']+?)['\"]")[0]
                    if season_title:
                        cleaned_season = self.CleanTitleName(season_title, showEP=True)
                        season_title_display = cleaned_season["title_display"]
                    else:
                        season_title_display = "موسم آخر"
                    season_icon = self.cm.ph.getSearchGroups(season, r"src=['\"]([^\"^']+?)['\"]")[0]
                    if season_icon:
                        season_icon = self.getFullUrl(season_icon)
                    else:
                        season_icon = cItem["icon"]
                    season_desc = "%s" % description
                    params = dict(cItem)
                    params.update({"category": "list_series_episodes", "media_type": True, "good_for_fav": True, "title": season_title_display, "url": season_url, "icon": season_icon, "desc": season_desc})
                    self.addDir(params)
        episodes_main_data = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "list-episodes"), ("</ul>", ">"), False)[1]
        if not episodes_main_data:
            episodes_main_data = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", ">", "list-episodes"), ("</ul>", ">"), True)[1]
        if episodes_main_data:
            printDBG("Found list-episodes section")
            li_pattern = r"<li[^>]*>(.*?)</li>"
            episodes = re.findall(li_pattern, episodes_main_data, re.DOTALL)
            if episodes:
                self.addMarker({"title": "%sجميع الـحـلـقـات (%d)%s" % (E2ColoR("yellow"), len(episodes), E2ColoR("white")), "icon": cItem["icon"], "desc": ""})
                episodes_list = []
                for episode in episodes:
                    episode_url = self.getFullUrl(self.cm.ph.getSearchGroups(episode, r"href=['\"]([^\"^']+?)['\"]")[0])
                    if not episode_url or episode_url == self.MAIN_URL:
                        continue
                    ep_num = 0
                    num_ep_data = self.cm.ph.getDataBeetwenNodes(episode, ("<span", ">", "numEp"), ("</span>", ">"), False)[1]
                    if num_ep_data:
                        ep_num_match = re.search(r"(\d+)", num_ep_data)
                        if ep_num_match:
                            ep_num = int(ep_num_match.group(1))
                    episode_title_from_html = self.cm.ph.getSearchGroups(episode, r"title=['\"]([^\"^']+?)['\"]")[0]
                    if episode_title_from_html:
                        title_parts = re.split(r"\s+الحلقة\s+", episode_title_from_html, 1)
                        if len(title_parts) > 1:
                            episode_title = "الحلقة %s" % title_parts[1]
                        else:
                            if series_name:
                                clean_title = re.sub(r"^%s\s*" % re.escape(series_name), "", episode_title_from_html)
                                episode_title = clean_title.strip()
                            else:
                                episode_title = episode_title_from_html
                    else:
                        episode_title = "الحلقة %d" % ep_num if ep_num > 0 else "حلقة"
                    episodes_list.append({"url": episode_url, "title": episode_title, "num": ep_num})
                episodes_list = sorted(episodes_list, key=lambda x: x["num"])
                for ep in episodes_list:
                    cleaned_episode = self.CleanTitleName(ep["title"], showEP=True)
                    episode_title = cleaned_episode["title_display"]
                    episode_desc = "%sEpisode:%s %d\n%s" % (E2ColoR("yellow"), E2ColoR("white"), ep["num"], description) if ep["num"] > 0 else description
                    params = dict(cItem)
                    params.update({"media_type": True, "good_for_fav": True, "title": episode_title, "url": ep["url"], "icon": cItem["icon"], "desc": episode_desc})
                    self.addVideo(params)
        elif not seasons_data and not episodes_main_data:
            params = dict(cItem)
            params.update({"media_type": True, "good_for_fav": True, "title": cItem["title"], "url": item_url, "icon": cItem["icon"], "desc": description})
            self.addVideo(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("HwnaTurkya.listSeriesEpisodes cItem[%s]" % str(cItem))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        cItem["prev_url"] = cItem["url"]
        description = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "story"), ("</div>", ">"), False)[1])
        series_name = cItem.get("title", "").strip()
        if "الموسم" in series_name:
            series_name = re.sub(r"\s*الموسم\s+\S+", "", series_name)
        episodes_data = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "list-episodes"), ("</ul>", ">"), False)[1]
        if not episodes_data:
            episodes_data = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", ">", "episodes"), ("</ul>", ">"), True)[1]
        if not episodes_data:
            printDBG("No episodes found")
            return
        episodes = []
        li_pattern = r"<li[^>]*>(.*?)</li>"
        li_matches = re.findall(li_pattern, episodes_data, re.DOTALL)
        if li_matches:
            episodes = li_matches
        else:
            episodes = self.cm.ph.getAllItemsBeetwenMarkers(episodes_data, ("<li", ">"), ("</li>", ">"))
        printDBG("Found %d episodes in listSeriesEpisodes" % len(episodes))
        episodes_list = []
        for episode in episodes:
            episode_url = self.getFullUrl(self.cm.ph.getSearchGroups(episode, r"href=['\"]([^\"^']+?)['\"]")[0])
            if not episode_url or episode_url == self.MAIN_URL:
                continue
            ep_num = 0
            num_ep_data = self.cm.ph.getDataBeetwenNodes(episode, ("<span", ">", "numEp"), ("</span>", ">"), False)[1]
            if num_ep_data:
                ep_num_match = re.search(r"(\d+)", num_ep_data)
                if ep_num_match:
                    ep_num = int(ep_num_match.group(1))
            episode_title_from_html = self.cm.ph.getSearchGroups(episode, r"title=['\"]([^\"^']+?)['\"]")[0]
            if episode_title_from_html:
                title_parts = re.split(r"\s+الحلقة\s+", episode_title_from_html, 1)
                if len(title_parts) > 1:
                    episode_title = "الحلقة %s" % title_parts[1]
                else:
                    if series_name:
                        clean_title = re.sub(r"^%s\s*" % re.escape(series_name), "", episode_title_from_html)
                        episode_title = clean_title.strip()
                    else:
                        episode_title = episode_title_from_html
            else:
                episode_title = "الحلقة %d" % ep_num if ep_num > 0 else "حلقة"
            episodes_list.append({"url": episode_url, "title": episode_title, "num": ep_num})
        episodes_list = sorted(episodes_list, key=lambda x: x["num"])
        printDBG("Final episodes list: %d episodes" % len(episodes_list))
        for ep in episodes_list:
            cleaned_episode = self.CleanTitleName(ep["title"], showEP=True)
            episode_title = cleaned_episode["title_display"]
            episode_desc = "%s\n%s" % (cleaned_episode["desc"], description)
            params = dict(cItem)
            params.update({"media_type": True, "good_for_fav": True, "title": episode_title, "url": ep["url"], "icon": cItem["icon"], "desc": episode_desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HwnaTurkya.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (str(cItem), searchPattern, searchType))
        search_url = self.getFullUrl("/search/%s" % urllib_quote_plus(searchPattern))
        params = {"name": "category", "title": "", "media_type": False, "url": search_url}
        self.listItems(params, "explore_item")

    def CleanTitleName(self, title, sDesc="", showEP=False):
        title_display = re.sub(r"\s+|\n|\t", " ", title).strip()
        desc = sDesc
        if showEP:
            ep_match = re.search(r"الحلقة\s*(\d+)", title_display)
            if ep_match:
                desc = "الحلقة %s - %s" % (ep_match.group(1), desc)
        return {"title_display": title_display, "desc": desc}

    def getLinksForVideo(self, cItem):
        printDBG("HwnaTurkya.getLinksForVideo [%s]" % str(cItem))
        urlTab = []
        baseUrl = cItem["url"].replace("movies", "watch_movies").replace("episodes", "watch_episodes")
        sts, data = self.getPage(baseUrl)
        if not sts:
            return []
        postID = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"postID\s*=\s*['\"]([^\"']+?)['\"]")[0])
        if not postID:
            printDBG("postID not found")
            return []
        srv_block = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", ">", "list-serv"), ("</ul", ">"), True)[1]
        srv_list = self.cm.ph.getAllItemsBeetwenMarkers(srv_block, ("<li", ">"), ("</li", ">"))
        for item in srv_list:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("</i", ">"), ("</a", ">"), False)[1])
            if not title:
                continue
            printDBG("Processing server: %s" % title)
            post_data = {"server": title, "postID": postID, "Ajax": "1"}
            sts, pdata = self.getPage(self.getFullUrl("/ajax/getPlayer"), post_data=post_data)
            if not sts:
                printDBG("Ajax failed for: %s" % title)
                continue
            url = self.cm.ph.getSearchGroups(pdata, r"SRC=['\"]([^\"']+?)['\"]", ignoreCase=True)[0]
            url = self.getFullUrl(url)
            if not url or url == self.getFullUrl("/"):
                printDBG("No valid URL for: %s" % title)
                continue
            if title:
                title_disp = E2ColoR("white") + cItem["title"] + " " + E2ColoR("yellow") + "[" + title + "]" + E2ColoR("white") + " - " + E2ColoR("yellow") + self.up.getHostName(url, True) + E2ColoR("white")
            else:
                title_disp = cItem["title"]
            urlTab.append({"name": title_disp, "url": url, "need_resolve": 1})
        self.cacheLinks[str(cItem["url"])] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("HwnaTurkya.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("HwnaTurkya.getArticleContent [%s]" % str(cItem))
        content_url = cItem.get("prev_url", cItem.get("url", ""))
        printDBG("Getting article content from: %s" % content_url)
        sts, data = self.getPage(content_url)
        if not sts:
            return []
        story_html = self.cm.ph.getDataBeetwenNodes(data, ("<h3", ">", "story"), ("</h3>", ">"), False)[1]
        story = self.cleanHtmlStr(story_html).replace("\n", " ").strip()
        info_dict = {"المسلسل": "", "المواسم": [], "الممثلين": [], "النوع": [], "القسم": "", "الجودة": "", "سنة الإنتاج": "", "اللغة": "", "الوقت": "", "IMDB": ""}
        imdb_match = re.search(r'<a[^>]*class="imdb"[^>]*>.*?IMDB\s*([0-9]+\.?[0-9]*)', data, re.IGNORECASE)
        if imdb_match:
            info_dict["IMDB"] = imdb_match.group(1).strip()
        all_info_sections = re.findall(r'<ul[^>]*class="single-info[^"]*"[^>]*>(.*?)</ul>', data, re.S)
        for section_html in all_info_sections:
            section_clean = self.cleanHtmlStr(section_html)
            if "سنة الإنتاج" in section_clean or "سنة الانتاج" in section_clean:
                year = self.cm.ph.getSearchGroups(section_html, r"title=['\"]([0-9]{4})['\"]")[0]
                if not year:
                    year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(section_html, r">( [0-9]{4} )<")[0])
                if year:
                    info_dict["سنة الإنتاج"] = year
            elif "الجودة" in section_clean:
                quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(section_html, r"title=['\"]([^'\"]+)['\"]")[0])
                if not quality:
                    quality = self.cleanHtmlStr(section_html)
                if quality and quality not in [",", ""]:
                    info_dict["الجودة"] = quality
            elif "النوع" in section_clean:
                genres = [self.cleanHtmlStr(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", section_html, re.S)]
                info_dict["النوع"] = [g for g in genres if g and g != ","]
            elif "القسم" in section_clean:
                category = self.cleanHtmlStr(self.cm.ph.getSearchGroups(section_html, r"title=['\"]([^'\"]+)['\"]")[0])
                if not category:
                    matches = re.findall(r"<a[^>]*>(.*?)</a>", section_html, re.S)
                    if matches:
                        category = self.cleanHtmlStr(matches[0])
                if category:
                    info_dict["القسم"] = category
            elif "المسلسل" in section_clean:
                series = self.cleanHtmlStr(self.cm.ph.getSearchGroups(section_html, r"title=['\"]([^'\"]+)['\"]")[0])
                if not series:
                    matches = re.findall(r"<a[^>]*>(.*?)</a>", section_html, re.S)
                    if matches:
                        series = self.cleanHtmlStr(matches[0])
                if series:
                    info_dict["المسلسل"] = series
            elif "المواسم" in section_clean:
                seasons = [self.cleanHtmlStr(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", section_html, re.S)]
                info_dict["المواسم"] = [s for s in seasons if s and s != ","]
            elif "الممثلين" in section_clean:
                actors = [self.cleanHtmlStr(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", section_html, re.S)]
                info_dict["الممثلين"] = [a for a in actors if a and a != ","]
            elif "اللغة" in section_clean:
                lang_match = re.search(r"<a[^>]*>([^<]+)</a>", section_html)
                if lang_match:
                    lang = self.cleanHtmlStr(lang_match.group(1))
                    if lang:
                        info_dict["اللغة"] = lang
            elif "الوقت" in section_clean:
                time_match = re.search(r"<a[^>]*>([^<]+)</a>", section_html)
                if time_match:
                    duration = self.cleanHtmlStr(time_match.group(1))
                    if duration:
                        info_dict["الوقت"] = duration
        lines = []
        if info_dict["المسلسل"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "المسلسل", E2ColoR("white")) + ": %s" % info_dict["المسلسل"])
        if info_dict["المواسم"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "المواسم", E2ColoR("white")) + ": %s" % ", ".join(info_dict["المواسم"]))
        if info_dict["الممثلين"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "الممثلين", E2ColoR("white")) + ": %s" % ", ".join(info_dict["الممثلين"]))
        if info_dict["سنة الإنتاج"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "سنة الإنتاج", E2ColoR("white")) + ": %s" % info_dict["سنة الإنتاج"])
        if info_dict["الجودة"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "الجودة", E2ColoR("white")) + ": %s" % info_dict["الجودة"])
        if info_dict["النوع"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "النوع", E2ColoR("white")) + ": %s" % ", ".join(info_dict["النوع"]))
        if info_dict["القسم"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "القسم", E2ColoR("white")) + ": %s" % info_dict["القسم"])
        if info_dict["اللغة"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "اللغة", E2ColoR("white")) + ": %s" % info_dict["اللغة"])
        if info_dict["الوقت"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "المدة", E2ColoR("white")) + ": %s" % info_dict["الوقت"])
        if info_dict["IMDB"]:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "IMDB", E2ColoR("white")) + ": %s/10" % info_dict["IMDB"])
        if story:
            lines.append("%s%s%s" % (E2ColoR("yellow"), "القصة", E2ColoR("white")) + ": %s" % story)
        full_text = "\n".join(lines)
        return [{"title": cItem.get("title", ""), "text": full_text, "images": [{"title": "", "url": cItem.get("icon", "")}], "other_info": {}}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None and (not category):
            self.listMainMenu({"name": "category", "type": "category"})
        elif category in ("movies", "series"):
            self.listCatItems(self.currItem, "listItems")
        elif category == "listItems":
            self.listItems(self.currItem, "explore_item")
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        elif category == "list_series_episodes":
            self.listSeriesEpisodes(self.currItem)
        elif category in ("search", "search_next_page"):
            params = dict(self.currItem)
            params.update({"search_item": False, "name": "category"})
            self.listSearchResult(params, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, HwnaTurkya(), True, [])

    def withArticleContent(self, cItem):
        return "prev_url" in cItem or cItem.get("category") == "explore_item"
