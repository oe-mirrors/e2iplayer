# -*- coding: utf-8 -*-
# Allgoals (archiwum.allgoals.in) - archive of Polish sports TV recordings 1991-today (football, F1, MotoGP,
#   ski jumping, volleyball, ...) of the allgoals.in forum (the forum itself is login-only)
# Site: one static page per year, dates as <h3>, each recording is a button with "Link 1..N" (= parts) to
#   multiup.io; the multiup mirror page lists the file hosters -> the streamable ones go to urlparser
#   (streamtape, mixdrop, filemoon, ...). Pure download hosters (mega, nitroflare, send.now, ...) are skipped.
# Last Modified: 03.10.2026 - new host: watched flag, name normalisation, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
###################################################
# FOREIGN import
###################################################
import re
###################################################

MULTIUP_MIRROR = 'https://multiup.io/en/mirror/%s'
PAGE_SIZE = 100
# streaming hosters first, file hosters with waiting time last
HOSTER_ORDER = ('streamtape', 'mixdrop', 'filemoon', 'voe', 'dood', 'vidoza', 'uqload', '1fichier')
# release tags at the end of the scene style names ("...25.01.2026.1080i.PL.HDTV.maraarab")
TAIL_TAGS = r'(?:\d{3,4}[ip]|PL|EN|IT|DE|FR|ES|ENG|HDTV|SDTV|WEB|WEB-DL|WEBRip|x264|h264|maraarab)'


def GetConfigList():
    return []


def gettytul():
    return 'https://archiwum.allgoals.in/'


class Allgoals(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'raw_title', 'parts', 'date')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'allgoals', 'cookie': 'allgoals.cookie'})
        self.MAIN_URL = 'https://archiwum.allgoals.in/'
        self.DEFAULT_ICON_URL = 'https://archiwum.allgoals.in/logo-archiwum.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.yearCache = {}
        self.watchedHelper = IPTVWatchedHelper('allgoals')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            category = cItem.get('category', '')
            if cItem.get('type') == 'video' or category == 'video':
                parts = cItem.get('parts') or []
                return 'video:%s' % parts[0] if parts else ''
            year = self.cm.ph.getSearchGroups(cItem.get('url', ''), r'/(\d{4})\.html')[0]
            if category == 'list_months' and year:
                return 'folder:%s' % year
            if category == 'list_events' and year:
                return 'folder:%s:%s' % (year, cItem.get('month', ''))
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # naming
    ###################################################
    def _normTitle(self, title, date):
        if not IsMediaNamingNormalized():
            return title
        try:
            out = title
            m = re.match(r'^(\d{4})(\d{2})(\d{2})\s+(\d{2})(\d{2})\s+-\s+([^-]+?)\s+-\s+(.+)$', out)
            if m:
                # EPG recordings: "20260111 1438 - Polsat Sport Extra 2 - Siatkowka mezczyzn_ TAURON Puchar Polski"
                # ("_" stands for a ":" / "." of the EPG title, which is often cut off)
                out = m.group(7).replace('_ ', ' - ', 1)
                out = re.sub(r'\s{2,}', ' ', re.sub(r'_(?=\s|$)', '', out)).strip(' -_')
                if len(out) < 12:
                    out = '%s - %s' % (out, m.group(6).replace('CANAL_', 'CANAL+').replace('_', ''))
                # the time keeps two recordings of one event apart; no ":" (not allowed in DM file names)
                return '%s (%s-%s-%s %s.%s)' % (out, m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
            if ' ' not in out and out.count('.') > 2:
                out = re.sub(r'(?:\.' + TAIL_TAGS + r')+$', '', out, flags=re.I)
                out = re.sub(r'\.\d{2}\.\d{2}\.\d{4}$', '', out)
                out = out.replace('.', ' ')
            else:
                out = re.sub(r'\s+maraarab$', '', out, flags=re.I)
                out = re.sub(r'\s+\d{2}\.\d{2}\.\d{4}$', '', out)
                out = re.sub(r'^(?:\[[^\]]*\]\s*)+', '', out)
            out = re.sub(r'\s{2,}', ' ', out).strip(' -') or title
            if date:
                out = '%s (%s)' % (out, date)
            return out
        except Exception:
            printExc()
        return title

    @staticmethod
    def _isoDate(text):
        m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text or '')
        return '%s-%s-%s' % (m.group(3), m.group(2), m.group(1)) if m else ''

    ###################################################
    # listing
    ###################################################
    def listYears(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="year-tile">', '</div>'):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h1>([^<]+)</h1>')[0])
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            if not url or not title:
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_months', 'title': title,
                           'url': self.getFullUrl(url).replace('http://', 'https://'), 'icon': self.getFullIconUrl(icon).replace('http://', 'https://')})
            self.addDir(params)

    def _yearSections(self, url):
        # [(h3 label, [(title, [multiup ids])...])...] of a year page, cached (2023 is 1.3 MB)
        url = url.split('#', 1)[0]  # the pager rows carry "#<month>-<page>"
        if url in self.yearCache:
            return self.yearCache[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        sections = []
        for chunk in re.split(r'<h3[^>]*>', data)[1:]:
            label = self.cleanHtmlStr(chunk.split('</h3>', 1)[0])
            events = []
            for item in chunk.split('<div class="dropdown">')[1:]:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="dropbtn">([^<]*)<')[0])
                ids = re.findall(r'multiup\.[a-z]+/(?:[a-z]{2}/)?(?:download|mirror)/([0-9a-f]{32})', item)
                if title and ids:
                    events.append((title, ids))
            if events:
                sections.append((label, events))
        if len(self.yearCache) > 2:
            self.yearCache = {}
        self.yearCache[url] = sections
        return sections

    def listMonths(self, cItem):
        sections = self._yearSections(cItem['url'])
        months = []
        counts = {}
        for label, events in sections:
            iso = self._isoDate(label)
            month = iso[:7] if iso else 'other'
            if month not in counts:
                months.append(month)
                counts[month] = 0
            counts[month] += len(events)
        # newest month first, the undated "Inne" section last
        dated = sorted([m for m in months if m != 'other'], reverse=True)
        for month in dated + [m for m in months if m == 'other']:
            title = _('Other') if month == 'other' else '%s/%s' % (month[5:7], month[:4])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': 'list_events', 'title': '%s (%d)' % (title, counts[month]), 'month': month})
            self.addDir(params)

    def listEvents(self, cItem):
        month = cItem.get('month', '')
        rows = []
        for label, events in self._yearSections(cItem['url']):
            iso = self._isoDate(label)
            if (iso[:7] if iso else 'other') != month:
                continue
            if not iso:
                label = _('Other')
            for title, ids in events:
                rows.append((iso or self._isoDate(title), label, title, ids))
        rows.reverse()  # the page lists oldest first
        # busy months hold up to ~500 recordings: PAGE_SIZE at a time
        page = max(1, int(cItem.get('page', 1) or 1))
        lastPage = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, lastPage)
        for date, label, title, ids in rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]:
            channel = ''
            m = re.match(r'^\d{8}\s+\d{4}\s+-\s+([^-]+?)\s+-\s+', title)
            if m:
                channel = m.group(1).replace('CANAL_', 'CANAL+')
            desc = [date or label]
            if channel:
                desc.append(channel)
            if len(ids) > 1:
                desc.append(_('%d parts') % len(ids))
            params = stripPagerKeys(dict(cItem), ('month',))
            params.update({'good_for_fav': True, 'category': 'video', 'title': self._normTitle(title, date), 'raw_title': title,
                           'url': MULTIUP_MIRROR % ids[0], 'parts': ids, 'date': date, 'desc': ' | '.join(desc)})
            self.addVideo(params)
        if lastPage > 1:
            # the url template only serves "Jump" - the list is cut by cItem['page']
            addPagingItems(self, cItem, page, page < lastPage, lastPage, '%s#%s-{page}' % (cItem['url'], cItem.get('month', '')))

    ###################################################
    # links
    ###################################################
    def _hosterRank(self, host):
        for idx, key in enumerate(HOSTER_ORDER):
            if key in host:
                return idx
        return len(HOSTER_ORDER)

    def getLinksForVideo(self, cItem):
        printDBG("Allgoals.getLinksForVideo [%s]" % cItem.get('parts'))
        parts = cItem.get('parts') or []
        urlTab = []
        skipped = []
        for idx, mid in enumerate(parts):
            sts, data = self.getPage(MULTIUP_MIRROR % mid)
            if not sts:
                continue
            found = []
            for tag in re.findall(r'<a\s[^>]*nameHost=[^>]*>', data):
                host = self.cm.ph.getSearchGroups(tag, r'nameHost="([^"]+)"')[0]
                link = self.cm.ph.getSearchGroups(tag, r'\slink="([^"]+)"')[0].replace('&amp;', '&')
                validity = self.cm.ph.getSearchGroups(tag, r'validity="([^"]*)"')[0]
                if not link or not self.cm.isValidUrl(link) or validity == 'invalid':
                    continue
                if 1 != self.up.checkHostSupport(link):
                    if host not in skipped:
                        skipped.append(host)
                    continue
                found.append((self._hosterRank(host), host, link))
            for _rank, host, link in sorted(found):
                name = '%s %d - %s' % (_('Part'), idx + 1, host) if len(parts) > 1 else host
                urlTab.append({'name': name, 'url': strwithmeta(link, {'Referer': 'https://multiup.io/'}), 'need_resolve': 1})
        if not urlTab:
            if skipped:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ', '.join(skipped))
            else:
                SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get('raw_title', '')))

    def getVideoLinks(self, videoUrl):
        printDBG("Allgoals.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        other = {}
        if cItem.get('date'):
            other['released'] = cItem['date']
        if len(cItem.get('parts') or []) > 1:
            other['episodes'] = str(len(cItem['parts']))
        text = '%s[/br]%s' % (cItem.get('raw_title', ''), cItem.get('desc', ''))
        icon = cItem.get('icon', '')
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("Allgoals.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listYears({'name': 'category'})
        elif category == 'list_months':
            self.listMonths(self.currItem)
        elif category == 'list_events':
            self.listEvents(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Allgoals(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('allgoals')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
