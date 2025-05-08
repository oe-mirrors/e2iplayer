# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, getConfigListEntry
from datetime import datetime
import time
try:
    import simplejson as json
except Exception:
    import json
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.sportdeutschland_streamprotocol = ConfigSelection(default="hls", choices=[("rtmp", "rtmp"), ("hls", "HLS - m3u8")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Preferred streaming protocol"), config.plugins.iptvplayer.sportdeutschland_streamprotocol))
    return optionList
###################################################


def gettytul():
    return 'http://sportdeutschland.tv/'


class SportDeutschland(CBaseHostClass):

    def __init__(self):
        printDBG("SportDeutschland.__init__")

        CBaseHostClass.__init__(self, {'history': 'SportDeutschland'})

        self.DEFAULT_ICON_URL = 'https://www.sportdeutschland.de/typo3conf/ext/arx_template/Resources/Public/Images/WebSite/logo.png'
        self.MAINURL = 'http://sportdeutschland.tv/'
        self.MAIN_API_URL = 'http://proxy.vidibusdynamic.net/sportdeutschland.tv/api/'
        self.HTTP_JSON_HEADER = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:12.0) Gecko/20100101 Firefox/12.0',
                                  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                  'Accept-Encoding': 'gzip, deflate',
                                  'Referer': self.MAINURL,
                                  'Origin': self.MAINURL
                                 }
        self.cm.HEADER = dict(self.HTTP_JSON_HEADER)
        self.MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Categories'), },
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }]

    def _getJItemStr(self, item, key, default=''):
        v = item.get(key, None)
        if None == v:
            return default
        return ensure_str(clean_html(u'%s' % v))

    def _getJItemNum(self, item, key, default=0):
        v = item.get(key, None)
        if None != v:
            try:
                NumberTypes = (int, long, float, complex)
            except NameError:
                NumberTypes = (int, long, float)

            if isinstance(v, NumberTypes):
                return v
        return default

    def _getItemsListFromJson(self, url):
        sts, data = self.cm.getPage(url)
        if sts:
            try:
                data = json.loads(data)
                data = data['items']
                return data

            except Exception:
                printExc()
        return []

    def _utc2local(self, utc_datetime):
        now_timestamp = time.time()
        offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
        return utc_datetime + offset

    def listCategories(self, cItem):
        printDBG("SportDeutschland.listCategories")
        data = self._getItemsListFromJson(self.MAIN_API_URL + 'sections?access_token=true&per_page=9999')

        params = {'name': 'category', 'title': _('--All--'), 'category': 'category', 'permalink': '', 'uuid': '', 'page': 1}
        self.addDir(params)

        for item in data:
            icon = self._getJItemStr(item, 'image')
            try:
                if icon == '':
                    icon = ensure_str((u'%s' % item['images'][0]))
            except Exception:
                pass
            params = {'name': 'category', 'title': self._getJItemStr(item, 'title'), 'category': 'category', 'icon': icon, 'permalink': self._getJItemStr(item, 'permalink'), 'uuid': self._getJItemStr(item, 'uuid'), 'page': 1}
            self.addDir(params)

    def listCategory(self, cItem):
        printDBG("SportDeutschland.listCategory cItem[%s]" % cItem)
        baseUrl = self.MAIN_API_URL
        page = self._getJItemNum(cItem, 'page', 1)
        baseUuid = self._getJItemStr(cItem, 'uuid')
        pattern = cItem.get('pattern', '')
        if '' == pattern:
            if '' != baseUuid:
                baseUrl += 'sections/%s' % (baseUuid)
            baseUrl += '/assets?'
        else:
            baseUrl += 'search?q=%s&' % pattern
        data = self._getItemsListFromJson(baseUrl + 'access_token=true&page=%d&per_page=100' % page)
        for item in data:
            icon = self._getJItemStr(item, 'image')
            try:
                if icon == '':
                    icon = ensure_str((u'%s' % item['images'][0]))
            except Exception:
                pass

            desc = '%s[/br]%s' % (self._getJItemStr(item, 'duration'), self._getJItemStr(item, 'teaser'))

            params = {'name': 'category', 'title': self._getJItemStr(item, 'title'), 'category': 'category', 'icon': icon, 'desc': desc, 'player': self._getJItemStr(item, 'player')}
            printDBG(":::::::::::::::::::::::::::::::::::::\n%s\n:::::::::::::::::::::::::::::::" % item)
            planned = False
            #if 'LIVE' == self._getJItemStr(item, 'duration', ''):
            try:
                dateUTC = self._getJItemStr(item, 'date').replace('T', ' ').replace('Z', ' UTC')
                dateUTC = datetime.strptime(dateUTC, "%Y-%m-%d %H:%M:%S %Z")
                if dateUTC > datetime.utcnow():
                    params['title'] += _(" (planned %s)") % self._utc2local(dateUTC).strftime('%Y/%m/%d %H:%M:%S')
                    planned = True
            except Exception:
                printExc()

            sectionPermalink = self._getJItemStr(item.get('section', {}), 'permalink')
            permalink = self._getJItemStr(item, 'permalink')
            if '' != sectionPermalink and '' != permalink:
                params['url'] = 'http://proxy.vidibusdynamic.net/sportdeutschland.tv/api/permalinks/%s/%s?access_token=true' % (sectionPermalink, permalink)
            else:
                params['url'] = ''

            if '' != params['url'] or '' != params['player']:
                if None != item.get('duration', None) or item.get('live', False):
                    self.addVideo(params)
                else:
                    self.addArticle(params)
            else:
                printDBG('SportDeutschland.listCategory wrong item[%s]' % item)

        data = self._getItemsListFromJson(baseUrl + 'page=%d&per_page=100' % (page + 1))
        if 0 < len(data):
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("SportDeutschland.getLinksForVideo [%s]" % cItem)
        HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0) Gecko/20100101 Firefox/21.0',
                       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        videoUrls = []

        if self.cm.isValidUrl(cItem['url']):
            sts, data = self.cm.getPage(cItem['url'])
            if sts:
                try:
                    data = byteify(json.loads(data))
                    printDBG(data['asset']['videos'])
                    for item in data['asset']['videos']:
                        videoUrl = item['url']
                        if not self.cm.isValidUrl(videoUrl):
                            continue
                        if item.get('livestream', False):
                            if '.smil?' in videoUrl:
                                if 'rtmp' == config.plugins.iptvplayer.sportdeutschland_streamprotocol.value:
                                    sts, data = self.cm.getPage(videoUrl)
                                    if sts:
                                        #printDBG("+++++++++++++++++++++++++++++++++\n%s\n+++++++++++++++++++++++++++++++++" % data)
                                        videoUrl = self.cm.ph.getSearchGroups(data, 'meta base="(rtmp[^"]+?)"')[0]
                                        if '' != videoUrl and not videoUrl.startswith('/'):
                                            videoUrl += '/'
                                        videoUrl += self.cm.ph.getSearchGroups(data, 'video src="([^"]+?)"')[0]
                                        if videoUrl.startswith('rtmp'):
                                            videoUrls.append({'name': 'SportDeutschland rtmp', 'url': videoUrl.replace('&amp;', '&')})
                                else:
                                    videoUrl = videoUrl.replace('.smil?', '.m3u8?')
                                    videoUrls.extend(getDirectM3U8Playlist(videoUrl, checkExt=False))
                        elif 'mp4' in str(item.get('content_type', '')):
                            name = '%sx%s' % (item['width'], item['height'])
                            videoUrls.append({'name': name, 'url': videoUrl})
                except Exception:
                    printExc()

        for idx in range(len(videoUrls)):
            videoUrls[idx]['need_resolve'] = 0

        return videoUrls

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SportDeutschland.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['pattern'] = searchPattern
        self.listCategory(self.currItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('SportDeutschland.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("SportDeutschland.handleService: ---------> name[%s], category[%s] " % (name, category))
        self.currList = []

        if None == name:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif 'categories' == category:
            self.listCategories(self.currItem)
        elif 'category' == category:
            self.listCategory(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, SportDeutschland(), True, [])
