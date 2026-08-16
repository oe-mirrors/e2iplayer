# -*- coding: utf-8 -*-
# Last Modified: 22.01.2026
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, CSearchHistoryHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Components.config import config, ConfigText

###################################################
# FOREIGN import
###################################################
import re
import json
import os
import codecs
import requests

from urllib.parse import urlparse

###################################################
Y = E2ColoR("yellow")
W = E2ColoR("white")
DD = E2ColoR("dodgerblue")
CY = E2ColoR("cyan")
G = E2ColoR("green")
R = E2ColoR("red")


###################################################
def GetConfigList():
    return []


def gettytul():
    return "https://www.btolat.com/"


class BtolatCom(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "btolat.com", "cookie": "btolat.com.cookie"})
        config.plugins.iptvplayer.btolat_user = ConfigText(default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", fixed_size=False)
        self.USER_AGENT = config.plugins.iptvplayer.btolat_user.value
        self.MAIN_URL = "https://www.btolat.com/"
        self.DEFAULT_ICON_URL = "https://i.ibb.co/RkbWVvBZ/botolat.png"
        self.HTTP_HEADER = {"User-Agent": self.USER_AGENT, "DNT": "1", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Encoding": "gzip, deflate", "Accept-Language": "ar,en-US;q=0.7,en;q=0.3", "Referer": self.getMainUrl(), "Origin": self.getMainUrl()}
        self.history = CSearchHistoryHelper("btolat")
        self.defaultParams = {"header": self.HTTP_HEADER, "with_metadata": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLeagues = {}
        self.cacheVideos = {}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(baseUrl)
        sts, data = self.cm.getPage(baseUrl, addParams, post_data)
        return sts, data

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == "":
            return ""
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {"Cookie": cookieHeader, "User-Agent": self.USER_AGENT})

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("BtolatCom.listMainMenu")
        MAIN_CAT_TAB = [
            {"category": "list_videos", "title": "أحدث الفيديوهات", "url": self.getFullUrl("/video")},
            {"category": "list_leagues", "title": "البطولات والدوريات", "url": self.getFullUrl("/leagues")},
            {"category": "list_top_scorers", "title": "الهدافين", "url": self.getFullUrl("/leagues")},
            {"category": "list_professionals", "title": "المحترفين", "url": self.getFullUrl("/professionals/video")},
            {"category": "list_players", "title": "قائمة اللاعبين وأهدافهم", "url": self.getFullUrl("/leagues")},
            {"category": "search", "title": _("Search"), "search_item": True},
            {"category": "search_history", "title": _("Search history")},
            {"category": "delete_history", "title": _("Delete search history")},
        ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listLeagues(self, cItem):
        printDBG("BtolatCom.listLeagues")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # ===== Get all "mostLeagues" blocks =====
        blocks = re.findall(r'(<div\s+class="mostLeagues[^"]*"[^>]*>.*?</div>)', data, re.DOTALL | re.IGNORECASE)
        for b in blocks:
            title = self.cm.ph.getSearchGroups(b, r"<h[12][^>]*>(.*?)</h[12]>")[0]
            if not title:
                continue
            title_clean = self.cleanHtmlStr(title)
            # ===== Section marker =====
            if "أهم البطولات" in title_clean:
                self.addMarker({"title": Y + "========== *  أهم البطولات  * ==========" + W})
            elif "كل البطولات" in title_clean:
                self.addMarker({"title": CY + "========== *  كل البطولات  * ==========" + W})
            else:
                continue
            # ===== Extract leagues under each marker =====
            leagues = re.findall(r'<a[^>]+class="[^"]*leagueBox[^"]*"[^>]*>.*?</a>', b, re.DOTALL | re.IGNORECASE)
            printDBG("BtolatCom.listLeagues [%s] leagues found: %d" % (title_clean, len(leagues)))
            for item in leagues:
                url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
                icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
                title = self.cm.ph.getSearchGroups(item, r"<h3>(.*?)</h3>")[0]
                if not url or not title:
                    continue
                full_url = self.getFullUrl(url.replace("/league/", "/league/videos/"))
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_league_videos", "title": self.cleanHtmlStr(title), "url": full_url, "icon": self.getFullIconUrl(icon), "team_url": self.getFullUrl(url)})
                self.addDir(params)

    def listLeagueVideos(self, cItem):
        printDBG("BtolatCom.listLeagueVideos [%s]" % cItem)
        page = cItem.get("page", 1)
        url = cItem["url"]
        if page > 1:
            if "?" in url:
                url += "&p=" + str(page)
            else:
                url += "?p=" + str(page)
        sts, data = self.getPage(url)
        if not sts:
            return
        # ----- 1) Add "All videos" folder for the league -----
        params_all_videos = dict(cItem)
        params_all_videos.update({"category": "list_all_league_videos", "title": Y + "جميع الفيديوهات" + W, "url": url})  # all league videos
        self.addDir(params_all_videos)
        # ----- 2) Add a marker under "All videos" folder -----
        params_marker = dict(cItem)
        params_marker.update({"category": "none", "title": CY + "========== الأندية والفرق ==========" + W})
        self.addMarker(params_marker)
        # ----- 3) Add teams folders under the marker -----
        teams_block = re.search(r'<div class="importantTeams[^"]*">(.*?)</div>\s*</div>', data, re.DOTALL)
        if teams_block:
            teams = re.findall(r'<a href="([^"]+)" class="importantTeam">.*?<img src="([^"]+)"[^>]*>.*?<h3>(.*?)</h3>', teams_block.group(1), re.DOTALL)
            for team_url, team_icon, team_name in teams:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_league_team_videos", "title": self.cleanHtmlStr(team_name), "url": self.getFullUrl(team_url), "team_url": self.getFullUrl(team_url), "icon": self.getFullIconUrl(team_icon)})  # team videos handler
                self.addDir(params)

    def listLeagueTeamVideos(self, cItem):
        printDBG("BtolatCom.listLeagueTeamVideos [%s]" % cItem)
        page = cItem.get("page", 1)
        url = cItem["url"]
        # Convert team URL to its videos page
        videos_url = url.replace("/team/", "/team/videos/") if "/team/" in url else url
        if page > 1:
            videos_url += "&p=" + str(page) if "?" in videos_url else "?p=" + str(page)
        sts, data = self.getPage(videos_url)
        if not sts:
            return
        # ----- 1) Search for team videos -----
        blocks = re.findall(r'<div class="categoryNewsCard">.*?</div>', data, re.DOTALL)
        if blocks:
            for b in blocks:
                # Video URL
                video_url = self.cm.ph.getSearchGroups(b, r'<a[^>]+href=[\'"](/video/[^\'"]+)[\'"]')
                if not video_url:
                    continue
                video_url = video_url[0]
                # Video title
                title = self.cm.ph.getSearchGroups(b, r"<h3[^>]*>(.*?)</h3>")
                if not title:
                    continue
                title = self.cleanHtmlStr(title[0])
                # Video icon
                icon = self.cm.ph.getSearchGroups(b, r'data-original=[\'"]([^\'"]+)[\'"]')
                if not icon:
                    icon = self.cm.ph.getSearchGroups(b, r'src=[\'"]([^\'"]+)[\'"]')
                icon = icon[0] if icon else ""
                # League / category name
                cat = self.cm.ph.getSearchGroups(b, r'<a\s+class="categoryTag"[^>]*>(.*?)</a>')
                cat_name = self.cleanHtmlStr(cat[0]) if cat else ""
                # ---------- Extract image URL first ----------
                icon = self.cm.ph.getSearchGroups(b, r'data-original=[\'"]([^\'"]+)[\'"]')
                if not icon:
                    icon = self.cm.ph.getSearchGroups(b, r'src=[\'"]([^\'"]+)[\'"]')
                icon = icon[0] if icon else ""
                # ---------- Extract date from image URL ----------
                video_date = ""
                if icon:
                    date_m = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/video/", icon)
                    if date_m:
                        video_date = "%s-%s-%s" % (date_m.group(1), date_m.group(2), date_m.group(3))
                # Video description (category + date)
                if cat_name and video_date:
                    desc = cat_name + "\n" + CY + video_date + W
                elif video_date:
                    desc = CY + video_date + W
                else:
                    desc = cat_name or title
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": title, "url": self.getFullUrl(video_url), "icon": self.getFullIconUrl(icon), "desc": Y + desc + W})
                self.addVideo(params)
        else:
            # ----- 2) If no videos found, add a marker -----
            params_marker = dict(cItem)
            params_marker.update({"category": "none", "title": CY + "لا يوجد بيانات حاليا" + W})
            self.addMarker(params_marker)
        # ===== pagination =====
        if 'class="next-page"' in data:
            params = dict(cItem)
            params.update({"title": Y + "Next Page المزيد من الفيديوهات" + " ▶▶▶" + W, "page": page + 1, "url": cItem["url"], "category": "list_league_team_videos"})
            self.addDir(params)

    def listAllLeagueVideos(self, cItem):
        printDBG("BtolatCom.listAllLeagueVideos [%s]" % cItem)
        page = cItem.get("page", 1)
        url = cItem["url"]
        if page > 1:
            url += "&p=" + str(page) if "?" in url else "?p=" + str(page)
        sts, data = self.getPage(url)
        if not sts:
            return
        # ===== Extract all videos (same as listLeagueVideos) =====
        blocks = re.findall(r'<div class="categoryNewsCard">.*?</div>', data, re.DOTALL)
        printDBG("BtolatCom.listAllLeagueVideos found [%d] items" % len(blocks))
        for b in blocks:
            # Video URL
            video_url = self.cm.ph.getSearchGroups(b, r'<a[^>]+href=[\'"](/video/[^\'"]+)[\'"]')
            # Video title
            title = self.cm.ph.getSearchGroups(b, r"<h3[^>]*>(.*?)</h3>")
            # Video icon
            icon = self.cm.ph.getSearchGroups(b, r'data-original=[\'"]([^\'"]+)[\'"]')
            if not icon:
                icon = self.cm.ph.getSearchGroups(b, r'src=[\'"]([^\'"]+)[\'"]')
            if not video_url or not title:
                printDBG("BtolatCom.listAllLeagueVideos skip item (no data)")
                continue
            video_url = video_url[0]
            title = self.cleanHtmlStr(title[0])
            icon = icon[0] if icon else ""
            # League / category name
            cat = self.cm.ph.getSearchGroups(b, r'<a\s+class="categoryTag"[^>]*>(.*?)</a>')
            cat_name = self.cleanHtmlStr(cat[0]) if cat else ""
            # Extract date from image URL
            date_m = re.search(r"https://img\.btolat\.com/(\d+)/(\d+)/(\d+)/video/", b)
            video_date = "%s-%s-%s" % (date_m.group(1), date_m.group(2), date_m.group(3))
            # Video description: category + date
            if cat_name and video_date:
                desc = cat_name + "\n" + CY + video_date + W
            elif video_date:
                desc = CY + video_date + W
            else:
                desc = cat_name or title
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": self.getFullUrl(video_url), "icon": self.getFullIconUrl(icon), "desc": Y + desc + W})
            self.addVideo(params)
        # ===== pagination =====
        if 'class="next-page"' in data:
            params = dict(cItem)
            params.update({"title": Y + "Next Page المزيد من الفيديوهات" + " ▶▶▶" + W, "page": page + 1, "url": url, "category": "list_all_league_videos"})
            self.addDir(params)

    def listTopScorersMenu(self, cItem):
        printDBG("BtolatCom.listTopScorersMenu [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # Extract leagues / competitions
        leagues = re.findall(r'<a[^>]+class="[^"]*leagueBox[^"]*"[^>]*>.*?</a>', data, re.DOTALL | re.IGNORECASE)
        for item in leagues:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(item, r"<h3>(.*?)</h3>")[0]
            if not url or not title:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_league_top_scorers", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url.replace("/league/", "/league/topscores/")), "icon": self.getFullIconUrl(icon), "league_id": self.cm.ph.getSearchGroups(url, r"/league/(\d+)")[0]})  # Scorers page URL  # Extract league ID
            self.addDir(params)

    def listLeagueTopScorers(self, cItem):
        printDBG("BtolatCom.listLeagueTopScorers [%s]" % cItem)
        page = cItem.get("page", 1)
        last_pos = cItem.get("last_position", 0)
        league_id = cItem.get("league_id", "")
        if page == 1:
            url = cItem["url"]
            sts, data = self.getPage(url)
            if not sts:
                return
            # ====== No top scorers table ======
            if "لا يوجد جدول هدافين" in data:
                self.addMarker({"title": Y + "لا يوجد هدافين لهذه البطولة" + W, "icon": cItem.get("icon", "")})
                return
        else:
            # url = f'https://www.btolat.com/league/TopScoresLoadMore/{league_id}/aa'
            url = "https://www.btolat.com/league/TopScoresLoadMore/%s/aa" % league_id
            post_data = {"Id": league_id, "lastPosition": last_pos}
            sts, data = self.getPage(url, post_data=post_data)
            if not sts:
                return
            try:
                data_json = json.loads(data)
            except Exception:
                return
            if not data_json.get("success", True):
                printDBG("No more top scorers (success = false)")
                return
            data = data_json.get("html", "")
        # ===== Extract players + images =====
        players = re.findall(
            r'<tr\s+data-position="(\d+)">.*?'  # position / rank
            r'<a href="(/player/[^"]+)">.*?'  # player profile link
            r'<img[^>]+src="([^"]+)".*?'  # player image
            r"<b>([^<]+)</b>.*?"  # player name
            r"</a>.*?"
            r'<a href="(/team/[^"]+)">.*?'  # team link
            r'<img[^>]+src="([^"]+)".*?'  # team logo
            r"<b>([^<]+)</b>.*?"  # team name
            r"</a>.*?"
            r"<span>(\d+)</span>",  # goals count
            data,
            re.DOTALL | re.IGNORECASE,
        )
        if not players:
            if page == 1:
                self.addMarker({"title": Y + "لا يوجد هدافين لهذه البطولة" + W, "icon": cItem.get("icon", "")})
            return
        for pos, player_url, player_img, player_name, team_url, team_img, team_name, goals in players:
            player_url_full = self.getFullUrl(player_url)
            img_url = self.getFullIconUrl(player_img.strip())
            title = "%s- P| %s - %s - (%s %sهدف%s)" % (pos, player_name.strip(), team_name.strip(), goals, Y, W)
            params = {"good_for_fav": True, "category": "list_player_videos", "title": title, "url": player_url_full, "icon": img_url, "page": 1}
            self.addDir(params)
        # ===== Load more button =====
        last_position = int(players[-1][0])
        params = dict(cItem)
        params.update({"title": Y + "Next Page المزيد من الهدافين" + " ▶▶▶" + W, "page": page + 1, "last_position": last_position, "league_id": league_id, "url": cItem["url"], "category": "list_league_top_scorers"})
        self.addDir(params)

    def listProfessionals(self, cItem):
        printDBG("BtolatCom.listProfessionals")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        # Add professionals videos link
        params = dict(cItem)
        params.update(
            {
                "good_for_fav": True,
                "category": "list_player_videos",
                "title": Y + "فيديوهات كل المحترفين" + W,
                "url": self.getFullUrl("/professionals/video"),
            }
        )
        self.addDir(params)
        params = dict(cItem)
        params.update(
            {
                "category": "none",
                "title": CY + "========== المحترفين المصريين ==========" + W,
            }
        )
        self.addMarker(params)
        # Extract players
        player_links = re.findall(r'<a[^>]+href="(/player/\d+/[^"]+)"[^>]*class="importantTeam"[^>]*>.*?' r'<img[^>]+src="([^"]+)"[^>]*>.*?' r"<h3>(.*?)</h3>", data, re.DOTALL | re.IGNORECASE)
        for player_url, player_icon, player_name in player_links:
            player_url_full = self.getFullUrl(player_url)
            sts, player_data = self.getPage(player_url_full)
            if not sts:
                desc = ""
            else:
                info_block = re.search(r'<div class="info col-sm-12 col-md-6">(.*?)</div>', player_data, re.DOTALL)
                if info_block:
                    info_html = info_block.group(1)
                    job_title = re.search(r'<span itemprop="jobTitle"[^>]*>(.*?)</span>', info_html)
                    team = re.search(r'<li[^>]*itemprop="memberOf"[^>]*>.*?<span itemprop="name"><a[^>]*>(.*?)</a></span>', info_html, re.DOTALL)
                    birth_place = re.search(r'<li[^>]*itemprop="address"[^>]*>.*?<span itemprop="addressCountry">(.*?)</span>', info_html, re.DOTALL)
                    nationality = re.search(r'الجنسيه\s*:\s*<span itemprop="nationality">(.*?)</span>', info_html, re.DOTALL)
                    birth_date = re.search(r'<span><time itemprop="birthDate"[^>]*>(.*?)</time></span>', info_html, re.DOTALL)
                    age = re.search(r"السن\s*:\s*<span>(.*?)</span>", info_html, re.DOTALL)
                    height = re.search(r'<span itemprop="height">(.*?)</span>', info_html, re.DOTALL)
                    weight = re.search(r'<span itemprop="weight">(.*?)</span>', info_html, re.DOTALL)
                    # Build description with yellow color
                    desc = " {}المركز:{} {} | {}الفريق:{} {} | {}محل الميلاد:{} {} | {}الجنسية:{} {} | {}تاريخ الميلاد:{} {} | {}العمر:{} {} | {}الطول:{} {} | {}الوزن:{} {}".format(Y, W, job_title.group(1).strip() if job_title else "", Y, W, team.group(1).strip() if team else "", Y, W, birth_place.group(1).strip() if birth_place else "", Y, W, nationality.group(1).strip() if nationality else "", Y, W, birth_date.group(1).strip() if birth_date else "", Y, W, age.group(1).strip() if age else "", Y, W, height.group(1).strip() if height else "", Y, W, weight.group(1).strip() if weight else "")
                else:
                    desc = ""
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_player_videos", "title": self.cleanHtmlStr(player_name), "url": player_url_full, "icon": self.getFullIconUrl(player_icon), "desc": desc})
            self.addDir(params)

    def listPlayerVideos(self, cItem):
        printDBG("BtolatCom.listPlayerVideos")
        page = cItem.get("page", 1)
        base_url = cItem["url"]
        # ======================================================
        # ============ Professionals section ==================
        # ======================================================
        if "/professionals/video" in base_url:
            if page == 1:
                url = base_url
                sts, data = self.getPage(url)
                if not sts:
                    return
                blocks = re.findall(r'(<div\s+class="card xrow video"[^>]*>.*?</div>)', data, re.DOTALL | re.IGNORECASE)
                last_row_id = re.search(r'data-val="(\d+)"', blocks[-1]).group(1) if blocks else ""
                last_row_date = re.search(r'data-date="([^"]+)"', blocks[-1]).group(1) if blocks else ""
            else:
                url = "https://www.btolat.com/api/video/LoadMore/0"
                post_data = {"lastRowId": cItem.get("last_row_id", ""), "lasRowDate": cItem.get("last_row_date", "")}
                sts, data = self.getPage(url, post_data=post_data)
                if not sts:
                    return
                data = json.loads(data)
                blocks = re.findall(r'(<div\s+class="card xrow video"[^>]*>.*?</div>)', data["html"], re.DOTALL | re.IGNORECASE)
                last_row_id = re.search(r'data-val="(\d+)"', blocks[-1]).group(1) if blocks else ""
                last_row_date = re.search(r'data-date="([^"]+)"', blocks[-1]).group(1) if blocks else ""
            for block in blocks:
                vid = re.search(r'href=[\'"](/video/\d+)[\'"]', block)
                img = re.search(r'data-src="([^"]+)"', block)
                title = re.search(r"<h3>(.*?)</h3>", block, re.DOTALL)
                cat = re.search(r'<a\s+href="[^"]+"\s+class="category">(.*?)</a>', block, re.DOTALL)
                date_m = re.search(r'data-date="([^"]+)"', block)
                if not vid or not title:
                    continue
                video_href = vid.group(1)
                img_url = img.group(1) if img else ""
                name = self.cleanHtmlStr(title.group(1))
                cat_name = self.cleanHtmlStr(cat.group(1)) if cat else ""
                video_date = ""
                if date_m:
                    raw_date = date_m.group(1).strip()  # Raw date (example: 12/13/2025)
                    try:
                        m, d, y = raw_date.split("/")
                        video_date = "%s-%s-%s" % (d.zfill(2), m.zfill(2), y)
                    except:
                        video_date = raw_date
                # Description = league + date
                if cat_name and video_date:
                    desc = cat_name + "\n" + CY + video_date + W
                elif video_date:
                    desc = CY + video_date + W
                else:
                    desc = cat_name or name
                params = {"good_for_fav": True, "category": "video", "title": name, "url": self.getFullUrl(video_href), "icon": self.getFullIconUrl(img_url), "desc": Y + desc + W}
                self.addVideo(params)
            # ===== Manual load more button =====
            if len(blocks) > 0:
                params = dict(cItem)
                params.update({"title": Y + "Next Page المزيد من الفيديوهات" + " ▶▶▶" + W, "page": page + 1, "last_row_id": last_row_id, "last_row_date": last_row_date, "url": base_url, "category": "list_player_videos"})
                self.addDir(params)
        # ======================================================
        # ================== Other players ====================
        # ======================================================
        else:
            if page == 1:
                url = base_url
                sts, data = self.getPage(url)
                if not sts:
                    return
                # ===== Check if videos tab exists =====
                videos_tab = self.cm.ph.getSearchGroups(data, r'href="(/player/videos/[^"]+)"')[0]
                if not videos_tab:
                    params = {"title": Y + "لا يوجد فيديوهات متاحة لهذا اللاعب حاليا" + W, "type": "marker", "icon": cItem.get("icon", "")}
                    self.addMarker(params)
                    return
                # ===== Videos exist → auto redirect =====
                base_url = self.getFullUrl(videos_tab)
                url = base_url
            else:
                # Convert link to /player/videos/...
                if "/player/videos/" not in base_url:
                    base_url = base_url.replace("/player/", "/player/videos/")
                url = base_url + "?p=" + str(page)
            sts, data = self.getPage(url)
            if not sts:
                return
            printDBG("========== PLAYER VIDEOS PAGE ==========")
            printDBG("URL: %s" % url)
            printDBG("========== END PAGE ==========")
            blocks = re.findall(r'(<div\s+class="categoryNewsCard[^"]*"[^>]*>.*?</div>)', data, re.DOTALL | re.IGNORECASE)
            printDBG("BtolatCom.listPlayerVideos VIDEO blocks found: %d" % len(blocks))
            for block in blocks:
                vid = re.search(r'href=[\'"](/video/\d+)[\'"]', block)
                img = re.search(r'data-original="([^"]+)"', block)
                title = re.search(r"<h3>(.*?)</h3>", block, re.DOTALL)
                cat = re.search(r'<a\s+class="categoryTag"[^>]*>(.*?)</a>', block, re.DOTALL)
                if not vid or not title:
                    continue
                video_href = vid.group(1)
                img_url = img.group(1) if img else ""
                name = self.cleanHtmlStr(title.group(1))
                name = self.cleanHtmlStr(title.group(1))
                cat_name = self.cleanHtmlStr(cat.group(1)) if cat else ""
                # ===== Extract date from image URL =====
                video_date = ""
                if img:
                    m = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/video/", img.group(1))
                    if m:
                        video_date = "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
                # ===== Two-line description =====
                if cat_name and video_date:
                    desc = cat_name + "\n" + CY + video_date + W
                elif video_date:
                    desc = CY + video_date + W
                else:
                    desc = cat_name or name
                params = {"good_for_fav": True, "category": "video", "title": name, "url": self.getFullUrl(video_href), "icon": self.getFullIconUrl(img_url), "desc": Y + desc + W}
                self.addVideo(params)
            # ===== Manual load more button =====
            if len(blocks) > 0 and "التالى" in data:
                params = dict(cItem)
                params.update({"title": Y + "Next Page المزيد من الفيديوهات" + W, "page": page + 1, "url": base_url, "category": "list_player_videos"})
                self.addDir(params)

    def listVideos(self, cItem):
        printDBG("BtolatCom.listVideos [%s]" % cItem)
        page = cItem.get("page", 1)
        url = cItem["url"]
        if page == 1:
            sts, data = self.getPage(url)
            if not sts:
                return
            blocks = re.findall(r'(<div\s+class="card xrow video"[^>]*>.*?</div>)', data, re.DOTALL | re.IGNORECASE)
        else:
            url = "https://www.btolat.com/api/video/LoadMore/0"
            post_data = {"lastRowId": cItem.get("last_row_id", ""), "lasRowDate": cItem.get("last_row_date", "")}
            sts, data = self.getPage(url, post_data=post_data)
            if not sts:
                return
            data = json.loads(data)
            blocks = re.findall(r'(<div\s+class="card xrow video"[^>]*>.*?</div>)', data["html"], re.DOTALL | re.IGNORECASE)
        for block in blocks:
            vid = re.search(r'href=[\'"](/video/\d+)[\'"]', block)
            img = re.search(r'data-src="([^"]+)"', block)
            title = re.search(r"<h3>(.*?)</h3>", block, re.DOTALL)
            cat = re.search(r'<a\s+href="[^"]+"\s+class="category">(.*?)</a>', block, re.DOTALL)
            date_m = re.search(r'data-date="([^"]+)"', block)
            if not vid or not title:
                continue
            video_href = vid.group(1)
            img_url = img.group(1) if img else ""
            name = self.cleanHtmlStr(title.group(1))
            cat_name = self.cleanHtmlStr(cat.group(1)) if cat else ""
            video_date = date_m.group(1).replace("/", "-") if date_m else ""  # Convert 12/17/2025 → 12-17-2025
            # Description = league + date (two lines)
            if cat_name and video_date:
                desc = cat_name + "\n" + CY + video_date + W
            elif video_date:
                desc = CY + video_date + W
            else:
                desc = cat_name or name
            params = {"good_for_fav": True, "category": "video", "title": name, "url": self.getFullUrl(video_href), "icon": self.getFullIconUrl(img_url), "desc": Y + desc + W}
            self.addVideo(params)
        # ===== Manual load more button =====
        if len(blocks) > 0:
            params = dict(cItem)
            params.update({"title": Y + "Next Page المزيد من الفيديوهات" + W, "page": page + 1, "last_row_id": blocks[-1].split('data-val="')[1].split('"')[0], "last_row_date": blocks[-1].split('data-date="')[1].split('"')[0], "url": cItem.get("url", "/video"), "category": "list_videos"})
            self.addDir(params)

    def listPlayersMenu(self, cItem):
        """
        قائمة الدوريات (مدخل مسار: الدوريات → الفرق → اللاعبين → فيديوهات اللاعب)
        """
        printDBG("BtolatCom.listPlayersMenu [%s]" % cItem)
        cItem = dict(cItem)
        cItem["url"] = "https://www.btolat.com/leagues"
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # ----- Add marker under leagues / competitions folder -----
        params_marker = dict(cItem)
        params_marker.update({"category": "none", "title": CY + "========== البطولات والدوريات ==========" + W})
        self.addMarker(params_marker)
        leagues = re.findall(r'<a[^>]+class="[^"]*leagueBox[^"]*"[^>]*>.*?</a>', data, re.DOTALL | re.IGNORECASE)
        for item in leagues:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(item, r"<h3>(.*?)</h3>")[0]
            if not url or not title:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_league_teams", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url), "icon": self.getFullIconUrl(icon)})
            self.addDir(params)

    def listLeagueTeams(self, cItem):
        """
        جلب الفرق في الدوري
        """
        printDBG("BtolatCom.listLeagueTeams [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # ----- Add marker under teams / clubs folder -----
        params_marker = dict(cItem)
        params_marker.update({"category": "none", "title": Y + "========== الأندية والفرق ==========" + W})
        self.addMarker(params_marker)
        block = re.search(r'<div class="importantTeams row">(.*?)</div>\s*</div>', data, re.DOTALL)
        if not block:
            printDBG("importantTeams block not found")
            return
        teams = re.findall(r'<a[^>]+href="(/team/[^"]+)"[^>]*class="importantTeam"[^>]*>.*?<img[^>]+src="([^"]+)".*?>.*?<h3>(.*?)</h3>', block.group(1), re.DOTALL | re.IGNORECASE)
        if not teams:
            printDBG("No teams found inside importantTeams")
            return
        for team_url, team_icon, team_name in teams:
            params = dict(cItem)
            params.update({"category": "list_team_players", "title": self.cleanHtmlStr(team_name), "url": self.getFullUrl(team_url), "team_url": self.getFullUrl(team_url), "icon": self.getFullIconUrl(team_icon)})
            self.addDir(params)

    def listTeamPlayers(self, cItem):
        printDBG("BtolatCom.listTeamPlayers [%s]" % cItem)
        team_url = cItem.get("team_url") or cItem.get("url")
        if "/team/squad/" not in team_url:
            team_url = team_url.replace("/team/", "/team/squad/")
        sts, data = self.getPage(team_url)
        if not sts:
            return
        # Extract players table
        block = re.search(r"<table[^>]+squadTable[^>]*>(.*?)</table>", data, re.DOTALL | re.IGNORECASE)
        if not block:
            printDBG("squadTable not found")
            return
        players_rows = re.findall(r"<tr>(.*?)</tr>", block.group(1), re.DOTALL | re.IGNORECASE)
        for row in players_rows:
            # Link, image and name
            match = re.search(r'<a href="([^"]+)".*?<img src="([^"]+)".*?>([^<]+)</a>', row, re.DOTALL | re.IGNORECASE)
            if not match:
                continue
            player_url = match.group(1).strip()
            player_icon = match.group(2).strip()
            player_name = match.group(3).strip()
            # Shirt number
            match_number = re.search(r"<i.*?>([^<]+)</i>", row)
            player_number = match_number.group(1).strip() if match_number else ""
            # Position, nationality, birth date
            match_td = re.findall(r"<td>.*?<span>([^<]+)</span>", row, re.DOTALL)
            player_pos = match_td[0].strip() if len(match_td) > 0 else ""
            player_nat = match_td[1].strip() if len(match_td) > 1 else ""
            player_birth = match_td[2].strip() if len(match_td) > 2 else ""
            # Description shown on hover with colors
            desc = "{}الاسم:{} {} | {}رقم القميص:{} {} | {}المركز:{} {} | {}الجنسية:{} {} | {}تاريخ الميلاد:{} {}".format(Y, W, player_name, Y, W, player_number, Y, W, player_pos, Y, W, player_nat, Y, W, player_birth)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_player_videos", "title": self.cleanHtmlStr(player_name), "url": self.getFullUrl(player_url), "icon": self.getFullIconUrl(player_icon), "desc": desc})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("BtolatCom.getLinksForVideo [%s]" % cItem)
        videoLinks = []
        url = cItem.get("url", "").strip()
        if not url:
            return videoLinks
        # 1) Get page
        sts, data = self.getPage(url)
        if not sts:
            return videoLinks
        # ===============================
        # 2) YouTube
        # ===============================
        m = re.search(r'https?://(?:www\.)?youtube\.com/embed/([^\?&"\']+)', data)
        if m:
            youtube_id = m.group(1)
            # Use YouTube host to resolve multiple qualities
            videoLinks.append({"name": "YouTube", "url": "https://www.youtube.com/watch?v=%s" % youtube_id, "need_resolve": 1})
        # ===============================
        # 3) Twitter / X via JSON endpoint
        # ===============================
        tweet_id = None
        # Try to extract tweet_id from any format
        for pattern in [r"https?://(?:www\.)?(?:twitter|x)\.com/[^/]+/status/(\d+)", r'data-tweet-id=["\'](\d+)["\']', r'embed/Tweet\.html[^"\']+id=(\d+)']:
            m = re.search(pattern, data)
            if m:
                tweet_id = m.group(1)
                break
        if tweet_id:
            printDBG("BtolatCom.getLinksForVideo - Twitter id: %s" % tweet_id)
            tweet_features = "tfw_video_hls_dynamic_manifests_15082:true_bitrate"
            json_url = ("https://cdn.syndication.twimg.com/tweet-result?" "id=%s&lang=ar&token=4ufmaqlvqaj&features=%s") % (tweet_id, tweet_features)
            sts, jdata = self.getPage(json_url)
            if sts:
                try:
                    jres = json.loads(jdata)
                    temp_links = []
                    hls_link = None
                    for media in jres.get("mediaDetails", []):
                        if media.get("type") == "video":
                            variants = media.get("video_info", {}).get("variants", [])
                            used = set()
                            for v in variants:
                                url = v.get("url")
                                if not url or url in used:
                                    continue
                                used.add(url)
                                if "m3u8" in url:
                                    # Store HLS to be added last
                                    hls_link = {"name": "Twitter HLS", "url": url, "need_resolve": 0}
                                else:
                                    bitrate = v.get("bitrate", 0)
                                    if bitrate >= 8000000:
                                        name = "Twitter MP4 1080P"
                                    elif bitrate >= 2000000:
                                        name = "Twitter MP4 720P"
                                    elif bitrate >= 800000:
                                        name = "Twitter MP4 480P"
                                    else:
                                        name = "Twitter MP4 %d" % (bitrate // 1000)
                                    temp_links.append({"name": name, "url": url, "need_resolve": 0, "bitrate": bitrate})
                    # Sort MP4 from highest to lowest quality
                    temp_links.sort(key=lambda x: x.get("bitrate", 0), reverse=True)
                    # Remove bitrate key after sorting
                    for l in temp_links:
                        l.pop("bitrate", None)
                    videoLinks.extend(temp_links)
                    # Add HLS at the end
                    if hls_link:
                        videoLinks.append(hls_link)
                except Exception as e:
                    printDBG("BtolatCom.getLinksForVideo - Twitter JSON parse error: %s" % str(e))
        # ===============================
        # 4) vortexvisionworks / videohatkora via embed page
        # ===============================
        if not videoLinks:
            embed_url = None
            m = re.search(r'<iframe[^>]+src=["\']([^"\']+embed[^"\']+)["\']', data)
            if m:
                embed_url = m.group(1)
                if embed_url.startswith("//"):
                    embed_url = "https:" + embed_url
                elif embed_url.startswith("/"):
                    embed_url = self.MAIN_URL + embed_url
            if embed_url:
                printDBG("BtolatCom embed url: %s" % embed_url)
                # Define headers
                parsed = urlparse(embed_url)
                embed_headers = dict(self.defaultParams.get("header", {}))
                embed_headers["Referer"] = embed_url
                embed_headers["Origin"] = "%s://%s" % (parsed.scheme, parsed.netloc)
                sts, embed_data = self.getPage(embed_url, {"header": embed_headers})
                if sts:
                    try:
                        # Search only for the main HLS URL
                        hls_match = re.search(r"hls\s*:\s*['\"](//[^'\"]+\.m3u8[^'\"]*)['\"]", embed_data)
                        if hls_match:
                            link = hls_match.group(1)
                            if link.startswith("//"):
                                link = "https:" + link
                            elif link.startswith("/"):
                                link = self.MAIN_URL + link
                            # Base URL
                            base_link = link
                            # Modify URL for other qualities
                            link_360 = base_link.replace("0.m3u8", "360p.m3u8")
                            link_720 = base_link.replace("0.m3u8", "720p.m3u8")
                            videoLinks.append({"name": "720p - Vortexvisionworks", "url": link_720, "need_resolve": 0, "headers": {"User-Agent": self.USER_AGENT, "Referer": embed_url, "Origin": embed_headers["Origin"], "Accept": "*/*", "Accept-Language": "en-US,en;q=0.5", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"}})
                            videoLinks.append({"name": "360p - Vortexvisionworks", "url": link_360, "need_resolve": 0, "headers": {"User-Agent": self.USER_AGENT, "Referer": embed_url, "Origin": embed_headers["Origin"], "Accept": "*/*", "Accept-Language": "en-US,en;q=0.5", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"}})
                    except Exception as e:
                        printDBG("Btolat embed HLS parse error: %s" % str(e))
        # ===============================
        # 5) Auto-create empty metadata file to prevent FileNotFoundError
        # ===============================
        title_safe = cItem.get("title", "video").replace("/", "_")
        metadata_dir = "/hdd/IPTVCache/MovieMetaData"
        if not os.path.exists(metadata_dir):
            os.makedirs(metadata_dir)
        metadata_file = os.path.join(metadata_dir, "botolat_%s.iptv" % title_safe)
        if not os.path.exists(metadata_file):
            try:
                with codecs.open(metadata_file, "w", "utf-8", "replace") as fp:
                    fp.write("")  # ملف فارغ
                printDBG("Created IPTV metadata file: %s" % metadata_file)
            except Exception as e:
                printDBG("Failed to create IPTV metadata file: %s | %s" % (metadata_file, str(e)))
        if videoLinks:
            self.saveIPTVMeta(cItem.get("title", "video"), videoLinks)
        return videoLinks

    def saveIPTVMeta(self, title, videoLinks):
        # Take the first valid link
        if not videoLinks:
            return
        first_link = videoLinks[0]["url"]
        # File path
        safe_title = title.replace("/", "_").replace("\\", "_")
        file_path = os.path.join("/hdd/IPTVCache/MovieMetaData", "botolat_%s.iptv" % safe_title)
        try:
            if not os.path.exists(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
        except:
            pass
        meta = {"host": "botolat", "title": title, "file_path": first_link}
        try:
            with codecs.open(file_path, "w", "utf-8") as fp:
                json.dump(meta, fp, ensure_ascii=False)
            printDBG("Created IPTV metadata file: %s" % file_path)
        except Exception as e:
            printDBG("Error creating IPTV metadata file: %s" % str(e))

    def getTwitterVideoLinks(self, tweet_id):
        printDBG("BtolatCom.getTwitterVideoLinks id[%s]" % tweet_id)
        linksTab = []
        api = "https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ar" % tweet_id
        sts, data = self.getPage(api)
        if not sts:
            return linksTab
        try:
            j = json.loads(data)
        except Exception:
            printDBG("Twitter JSON load error")
            return linksTab
        videos = []

        def findVideos(obj):
            if isinstance(obj, dict):
                if obj.get("type") == "video" and "video_info" in obj:
                    variants = obj["video_info"].get("variants", [])
                    for v in variants:
                        url = v.get("url", "")
                        ctype = v.get("content_type", "")
                        bitrate = v.get("bitrate", 0)
                        if url.startswith("http"):
                            videos.append((url, ctype, bitrate))
                for v in obj.values():
                    findVideos(v)
            elif isinstance(obj, list):
                for i in obj:
                    findVideos(i)

        findVideos(j)
        used = set()
        for url, ctype, bitrate in videos:
            if url in used:
                continue
            used.add(url)
            if "mpegURL" in ctype or url.endswith(".m3u8"):
                name = "Twitter HLS"
            else:
                name = "Twitter %s" % (str(int(bitrate / 1000)) + "kbps" if bitrate else "MP4")
            linksTab.append({"name": name, "url": url, "need_resolve": 0})
        printDBG("BtolatCom.getTwitterVideoLinks found links: %d" % len(linksTab))
        return linksTab

    def getVideoLinks(self, baseUrl):
        printDBG("BtolatCom.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []
        # If YouTube link
        if "youtube.com" in baseUrl or "youtu.be" in baseUrl:
            printDBG("BtolatCom.getVideoLinks - YouTube link detected: %s" % baseUrl)
            return self.up.getVideoLinkExt(baseUrl)
        # If Twitter link
        elif "twitter.com" in baseUrl or "platform.twitter.com" in baseUrl:
            printDBG("BtolatCom.getVideoLinks - Twitter link detected: %s" % baseUrl)
            urlTab.append({"name": "Twitter", "url": baseUrl, "need_resolve": 1})
            return urlTab
        # If direct link
        elif baseUrl.endswith((".mp4", ".m3u8", ".webm", ".flv")):
            printDBG("BtolatCom.getVideoLinks - Direct video link detected: %s" % baseUrl)
            # Extract headers from baseUrl if present
            headers = {}
            if hasattr(baseUrl, "meta") and baseUrl.meta:
                headers = baseUrl.meta.get("headers", {})
            # Set link name based on source
            name = "مباشر"
            if "vortexvisionworks.com" in baseUrl:
                name = "Vortex Vision HLS"
            elif "videohatkora.com" in baseUrl:
                name = "Video Hatkora HLS"
            elif "gooforkoora.com" in baseUrl:
                name = "Goofor Koora HLS"
            elif "btolat.com" in baseUrl:
                name = "Btolat HLS"
            # Add default headers if missing
            headers = {}
            if hasattr(baseUrl, "meta") and baseUrl.meta:
                headers = dict(baseUrl.meta.get("headers", {}))
            if not headers:
                headers = {"User-Agent": self.USER_AGENT, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.5", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"}
            urlTab.append({"name": name, "url": str(baseUrl), "headers": headers})
            return urlTab
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("BtolatCom.listSearchResult")
        url = "https://www.btolat.com/news/Search"
        post_data = {"word": searchPattern}
        headers = {"User-Agent": self.USER_AGENT, "Content-Type": "application/json; charset=utf-8", "Accept": "*/*", "Origin": self.MAIN_URL, "Referer": self.MAIN_URL, "X-Requested-With": "XMLHttpRequest"}
        found = False
        try:
            response = requests.post(url, headers=headers, json=post_data, timeout=15)
            if response.status_code != 200:
                printDBG("Search HTTP Error: %s" % response.status_code)
                return
            data = response.json()
            for item in data:
                seName = item.get("SeName", "")
                if not seName.startswith("video/"):
                    continue
                found = True
                title = self.cleanHtmlStr(item.get("Title", ""))
                img = self.getFullIconUrl(item.get("FullSizeImageUrl", ""))
                video_url = self.getFullUrl(seName)
                post_since = self.cleanHtmlStr(item.get("PostSince", ""))
                desc = Y + "Published since (نُشر منذ): " + W + post_since if post_since else ""
                params = {"good_for_fav": True, "category": "video", "title": title, "url": video_url, "icon": img, "desc": desc}
                self.addVideo(params)
            # ✅ If no videos found
            if not found:
                params = dict(cItem)
                params.update({"category": "none", "title": Y + "لا توجد نتائج فيديو حاليا" + W})
                self.addMarker(params)
        except Exception as e:
            printDBG("Search Exception: %s" % str(e))

    def getArticleContent(self, cItem):
        printDBG("BtolatCom.getArticleContent [%s]" % cItem)
        retTab = []
        url = cItem.get("url", "")
        if not url:
            return retTab
        sts, data = self.getPage(url)
        if not sts:
            return retTab
        icon = cItem.get("icon", "")
        title = cItem.get("title", "")
        # ===== Video state =====
        if cItem.get("category") == "video":
            player_url = self.cm.ph.getSearchGroups(data, r'<a href="(/player/[^"]+)"[^>]*>')[0].strip() or ""
            if player_url:
                return self.getArticleContent({"url": self.getFullUrl(player_url), "icon": icon, "title": title})
        # ===== Team / club state =====
        if cItem.get("category") == "list_league_team_videos":
            team_url = cItem.get("team_url", "") or cItem.get("url", "")
            if team_url:
                sts, team_data = self.getPage(team_url)
                if sts and team_data:
                    team_block = self.cm.ph.getDataBeetwenMarkers(team_data, '<div class="teamCard"', "</div>", True)[1]
                    # Coach
                    coach = self.cm.ph.getSearchGroups(team_block, r'(?s)المدير الفني.*?<span[^>]*itemprop="name"[^>]*>([^<]+)</span>')
                    coach_name = coach[0].strip() if coach else ""
                    # Trophies
                    trophies_block = self.cm.ph.getDataBeetwenMarkers(team_data, "<h2>البطولات التي يشارك فيها", "</div>")[1] if "<h2>البطولات التي يشارك فيها" in team_data else ""
                    trophies = re.findall(r"(?s)<h3>.*?<span>([^<]+)</span>", trophies_block)
                    trophies_text = "\n".join([t.strip() for t in trophies]) if trophies else ""
                    fields = [("اسم الفريق", self.cm.ph.getSearchGroups(team_block, r'<h2[^>]*itemprop="name"[^>]*>([^<]+)</h2>')), ("تاريخ التأسيس", self.cm.ph.getSearchGroups(team_block, r'تاريخ التأسيس.*?<span[^>]*itemprop="foundingDate"[^>]*>([^<]+)</span>')), ("المدير الفني", [coach_name]), ("البلد", self.cm.ph.getSearchGroups(team_block, r'البلد.*?<span[^>]*itemprop="addressCountry"[^>]*>([^<]+)</span>')), ("الملعب", self.cm.ph.getSearchGroups(team_block, r'الملعب.*?<span[^>]*itemprop="name"[^>]*>([^<]+)</span>')), ("البطولات", [trophies_text])]  # trophies displayed one per line
                    final_text = ""
                    for label, match_list in fields:
                        value = match_list[0].strip() if match_list else ""
                        if value:
                            final_text += "{}{}: {}{}\n".format(Y, label, W, value)
                    if not final_text:
                        final_text = CY + "لم يتم العثور على معلومات الفريق." + W
                    retTab.append({"title": fields[0][1][0].strip() if fields[0][1] else title, "text": final_text.strip(), "images": [{"title": fields[0][1][0].strip() if fields[0][1] else title, "url": icon}], "other_info": {}})
                    return retTab
        # ===== Normal player state =====
        info_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="info', "</ul>")[1] if data else ""
        fields = [
            ("الاسم", self.cm.ph.getSearchGroups(data, r'<h2[^>]*itemprop="name"[^>]*>([^<]+)')),
            ("المركز", self.cm.ph.getSearchGroups(data, r'itemprop="jobTitle"[^>]*>([^<]+)')),
            ("الفريق", self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenMarkers(info_block, 'itemprop="memberOf"', "</li>")[1] if info_block else "", r"<a[^>]*>([^<]+)</a>")),
            ("الجنسية", self.cm.ph.getSearchGroups(info_block, r"الجنسيه.*?<span[^>]*>([^<]+)</span>") if info_block else []),
            ("محل الميلاد", self.cm.ph.getSearchGroups(info_block, r'itemprop="addressCountry"[^>]*>([^<]+)</') if info_block else []),
            ("تاريخ الميلاد", self.cm.ph.getSearchGroups(info_block, r'itemprop="birthDate"[^>]*>([^<]+)</time>') if info_block else []),
            ("العمر", self.cm.ph.getSearchGroups(info_block, r"السن.*?<span[^>]*>([^<]+)</span>") if info_block else []),
            ("الطول", self.cm.ph.getSearchGroups(info_block, r'itemprop="height"[^>]*>([^<]+)</span>') if info_block else []),
            ("الوزن", self.cm.ph.getSearchGroups(info_block, r'itemprop="weight"[^>]*>([^<]+)</span>') if info_block else []),
        ]
        final_text = ""
        for label, match_list in fields:
            value = match_list[0].strip() if match_list else ""
            if value:
                final_text += "{}{}: {}{}\n".format(Y, label, W, value)
        if not final_text:
            final_text = CY + "لم يتم العثور على معلومات اللاعب." + W
        retTab.append({"title": fields[0][1][0].strip() if fields[0][1] else title, "text": final_text.strip(), "images": [{"title": fields[0][1][0].strip() if fields[0][1] else title, "url": icon}], "other_info": {}})
        return retTab

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("BtolatCom.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        mode = self.currItem.get("mode", "")
        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.currList = []
        # MAIN MENU
        if name is None and category == "":
            self.listMainMenu({"name": "category"})
        # AllLeague PATH
        elif category == "list_videos":
            self.listVideos(self.currItem)
        elif category == "list_leagues":
            self.listLeagues(self.currItem)
        elif category == "list_league_videos":
            self.listLeagueVideos(self.currItem)
        elif category == "list_league_team_videos":
            self.listLeagueTeamVideos(self.currItem)
        elif category == "list_all_league_videos":
            self.listAllLeagueVideos(self.currItem)
        # TopScorers PATH
        elif category == "list_top_scorers":
            self.listTopScorersMenu(self.currItem)
        elif category == "list_league_top_scorers":
            self.listLeagueTopScorers(self.currItem)
        # Professionals PATH
        elif category == "list_professionals":
            self.listProfessionals(self.currItem)
        # PLAYERS PATH
        elif category == "list_players":
            self.listPlayersMenu(self.currItem)
        elif category == "list_league_teams":
            self.listLeagueTeams(self.currItem)
        elif category == "list_team_players":
            self.listTeamPlayers(self.currItem)
        elif category == "list_player_videos":
            self.listPlayerVideos(self.currItem)
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        # SEARCH HISTORY
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, BtolatCom(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get("type") == "video":
            return True
        url = cItem.get("url", "")
        if "/player/" in url:
            return True
        if "/team/" in url:
            return True
        if "/players/" in url:
            return True
        return False
