# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
from copy import deepcopy
import urllib
try:
    import simplejson as json
except Exception:
    import json
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ardmediathek_iconquality = ConfigSelection(default="medium", choices=[("large", _("high")), ("medium", _("medium")), ("small", _("low"))])
config.plugins.iptvplayer.ardmediathek_prefformat = ConfigSelection(default="mp4,m3u8", choices=[
("mp4,m3u8", "mp4,m3u8"), ("m3u8,mp4", "m3u8,mp4")])
config.plugins.iptvplayer.ardmediathek_prefquality = ConfigSelection(default="4", choices=[("0", _("low")), ("1", _("medium")), ("2", _("high")), ("3", _("very high")), ("4", _("hd"))])
config.plugins.iptvplayer.ardmediathek_prefmoreimportant = ConfigSelection(default="quality", choices=[("quality", _("quality")), ("format", _("format"))])
config.plugins.iptvplayer.ardmediathek_onelinkmode = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Icons quality"), config.plugins.iptvplayer.ardmediathek_iconquality))
    optionList.append(getConfigListEntry(_("Prefered format"), config.plugins.iptvplayer.ardmediathek_prefformat))
    optionList.append(getConfigListEntry(_("Prefered quality"), config.plugins.iptvplayer.ardmediathek_prefquality))
    optionList.append(getConfigListEntry(_("More important"), config.plugins.iptvplayer.ardmediathek_prefmoreimportant))
    optionList.append(getConfigListEntry(_("One link mode"), config.plugins.iptvplayer.ardmediathek_onelinkmode))
    return optionList
###################################################


def gettytul():
    return 'ARDmediathek'


class ARDmediathek(CBaseHostClass):

    def __init__(self):
        printDBG("ARDmediathek.__init__")
        CBaseHostClass.__init__(self, {'history': 'ARDmediathek.tv', 'cookie': 'zdfde.cookie'})
        self.HOST = 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.18) Gecko/20110621 Mandriva Linux/1.9.2.18-0.1mdv2010.2 (2010.2) Firefox/3.6.18'
        self.HEADER = {'User-Agent': self.HOST, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Cache-Control': 'no-cache'})

        self.MAIN_URL = 'http://www.ardmediathek.de/'
        self.MAIN_API_URL = 'http://www.ardmediathek.de/'
        self.DEFAULT_ICON_URL = 'http://www.fluentu.com/german/blog/wp-content/uploads/sites/5/2014/12/how-to-hack-through-geoblocking-and-watch-german-tv-online1.png' # 'http://www.ardmediathek.de/ard/static/img/base/icon/ardlogo_weiss.png'
        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Start'), 'url': self.getFullUrl('appdata/servlet/tv?json')},
                             {'category': 'list_items', 'title': _('Missed the show?'), 'url': self.getFullUrl('appdata/servlet/tv/sendungVerpasst?json')},
                             {'category': 'list_items', 'title': _('Program A-Z'), 'url': self.getFullUrl('appdata/servlet/tv/sendungAbisZ?json')},
                             {'category': 'list_items', 'title': _('Live TV'), 'url': self.getFullUrl('appdata/servlet/tv/live?json')},
                             {'category': 'list_items', 'title': _('Live Radio'), 'url': self.getFullUrl('appdata/servlet/radio/live?json')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}]

        self.ICON_QUALITY_MAP = {'large': 1080, 'medium': 640, 'small': 240}
        self.STREAM_QUALITY_MAP = {'hd': 4, 'veryhigh': 3, 'high': 2, 'med': 1, 'low': 0}

    def _getQualityName(self, qualityValue):
        for key in self.STREAM_QUALITY_MAP:
            value = self.STREAM_QUALITY_MAP[key]
            if value == qualityValue:
                return key
        return 'auto'

    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER = dict(self.HEADER)
        return self.cm.getPage(url, params, post_data)

    def getIconUrl(self, url):
        marker = '##width##'
        if marker in url:
            iconQuality = config.plugins.iptvplayer.ardmediathek_iconquality.value
            iconWidth = self.ICON_QUALITY_MAP.get(iconQuality, 240)
            url = url.replace(marker, str(iconWidth))
        return self.getFullUrl(url)

    def getFullUrl(self, url):
        return CBaseHostClass.getFullUrl(self, url).replace(' ', '%20')

    def _getNum(self, v, default=0):
        try:
            return int(v)
        except Exception:
            try:
                return float(v)
            except Exception:
                return default

    def _getList(self, data, key, default=[]):
        try:
            if isinstance(data[key], list):
                return data[key]
        except Exception:
            printExc()
        return default

    def _mapClip(self, data):
        printDBG('_mapClip [%s]' % data)
        item = {}
        for type in ['audio', 'video', 'none']:
            if type in data['kennzeichen']:
                break
        if type != 'none':
            item['typ'] = type

        # title
        item['title'] = self.cleanHtmlStr(data['ueberschrift'])

        # icon and alt title
        try:
            tmp = data['bilder'][0]
            item['icon'] = self.getIconUrl(tmp.get('schemaUrl', ''))
            if item['title'] == '':
                item['title'] = self.cleanHtmlStr(tmp.get('title', ''))
            if item['title'] == '':
                item['title'] = self.cleanHtmlStr(tmp.get('alt', ''))
        except Exception:
            printExc()
            item['icon'] = ''

        # desc
        descTab = []
        if len(data.get('dachzeile', '')):
            descTab.append(data['dachzeile'])
        if len(data.get('unterzeile', '')):
            descTab.append(data['unterzeile'])
        if len(data.get('teaserText', '')):
            descTab.append(data['teaserText'])
        item['desc'] = self.cleanHtmlStr('[/br]'.join(descTab).replace('<br>', '[/br]'))
        # url
        item['url'] = self.getFullUrl(data['link']['url'])

        item['good_for_fav'] = True
        return item

    def _copy(self, params, addParams={}):
        params = dict(params)
        params.pop('page', None)
        params.update(addParams)
        return params

    def listItem(self, cItem, data, sectionIdx):
        printDBG('listItem')
        if data['typ'] not in ["Section"]:
            return
        skipButtons = list(cItem.get('skip_buttons', []))

        modCons = self._getList(data, 'modCons')
        for modCon in modCons:
            if modCon['typ'] not in ["ModCon"]:
                continue
            mods = self._getList(modCon, 'mods')
            for mod in mods:
                if mod['typ'] not in ["Mod"]:
                    continue
                filters = []
                if sectionIdx not in skipButtons:
                    mainButtons = self._getList(mod, 'buttons')
                    for mainButton in mainButtons:
                        if mainButton['typ'] not in ['ButtonGroup']:
                            continue
                        try:
                            mainTitle = self.cleanHtmlStr(mainButton['label']['text']) + ' '
                        except Exception:
                            mainTitle = ''
                        buttons = self._getList(mainButton, 'buttons')
                        for button in buttons:
                            if button['typ'] in ['buttonTyp']:
                                continue
                            if button['buttonTyp'] == 'paging':
                                continue # paging is handled in diffrent way
                            #if button.get('disabled', False): continue
                            title = self.cleanHtmlStr(button['label']['text'])
                            try:
                                desc = self.cleanHtmlStr(button['label']['altText'])
                            except Exception:
                                desc = ''
                            url = button['buttonLink']['url']
                            if not self.cm.isValidUrl(url):
                                continue
                            if len(filters) and (url.endswith('quelle.radio') or url.endswith('quelle.tv')):
                                continue # some workaround
                            filters.append({'good_for_fav': True, 'title': mainTitle + title, 'url': self.getFullUrl(url), 'desc': desc, 'skip_buttons': skipButtons})

                # if there are filter buttons add them as subcategories
                if len(filters) > 1:
                    skipButtons.append(sectionIdx)
                    for filter in filters:
                        params = self._copy(cItem, filter)
                        params['skip_buttons'] = skipButtons
                        self.addDir(params)
                    return True
                else:
                    inhalte = self._getList(mod, 'inhalte')
                    for teaser in inhalte:
                        if teaser['typ'] not in ['Teaser']:
                            continue
                        if 'Gruppe' in teaser['teaserTyp']: # in ['TabGruppe']:
                            mainTitle = self.cleanHtmlStr(teaser['ueberschrift'])
                            tab = []
                            interInhalte = self._getList(teaser, 'inhalte')
                            for interTeaser in interInhalte:
                                if interTeaser['typ'] not in ['Teaser']:
                                    continue
                                inter2Inhalte = self._getList(interTeaser, 'inhalte')
                                if 0 == len(inter2Inhalte):
                                    inter2Inhalte = [interTeaser]
                                for item in inter2Inhalte:
                                    printDBG("************************************************")
                                    params = self._mapClip(item)
                                    tab.append(params)
                            if len(tab):
                                params = {'good_for_fav': False, 'title': mainTitle, 'category': 'list_tab', 'clips_tab': tab}
                                params = self._copy(cItem, params)
                                self.addDir(params)
                        elif teaser['teaserTyp'].endswith('Clip'):
                            printDBG("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                            params = self._mapClip(teaser)
                            if params['typ'] == 'video':
                                self.addVideo(params)
                            if params['typ'] == 'audio':
                                self.addAudio(params)
                        else:
                            printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++")
                            params = self._mapClip(teaser)
                            params = self._copy(cItem, params)
                            self.addDir(params)
        return False

    def listItems(self, cItem):
        printDBG('listItems')
        url = cItem['url']
        page = cItem.get('page', 1)

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getSearchGroups(data, '"(http[^"]+?page\.%s[^0-9][^"]*?)"' % (page + 1))[0].split('"')[0]

        skipSections = []
        if '/search?' in url:
            if '&sort=date' in url or 'sort=score' in url:
                skipSections = [0, 2]
            else:
                nextPage = ''

        try:
            sectionIdx = 0
            data = byteify(json.loads(data))
            if 1 == len(data['sections']):
                self.listItem(cItem, data['sections'][0], sectionIdx)
            else:
                sectionIdx = -1
                for section in data['sections']:
                    sectionIdx += 1
                    if sectionIdx in skipSections:
                        continue
                    if section['typ'] not in ["Section"]:
                        continue
                    processed = False
                    modCons = self._getList(section, 'modCons')
                    for modCon in modCons:
                        if modCon['typ'] not in ["ModCon"]:
                            continue
                        mods = self._getList(modCon, 'mods')
                        for mod in mods:
                            if mod['typ'] not in ["Mod"]:
                                continue

                            try:
                                url = mod['allesLink']['url']
                            except Exception:
                                printExc()
                                continue
                            if not self.cm.isValidUrl(url):
                                continue

                            title = self.cleanHtmlStr(mod['titel'])
                            try:
                                if title == '':
                                    title = url.split('/')[6].split('?')[0].title()
                            except Exception:
                                printExc()

                            params = self._copy(cItem, {'good_for_fav': True, 'title': title, 'url': url})
                            self.addDir(params)
                            processed = True
                    if not processed:
                        if self.listItem(cItem, section, sectionIdx):
                            break
        except Exception:
            printExc()

        if nextPage != '':
            params = deepcopy(cItem)
            params.update({'good_for_fav': False, 'url': nextPage, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listTab(self, cItem):
        printDBG('listTab')
        tab = cItem.get('clips_tab', [])
        for item in tab:
            if 'typ' not in item:
                params = self._copy(cItem, item)
                params.update({'category': 'list_items'})
                self.addDir(params)
            elif item['typ'] == 'video':
                self.addVideo(item)
            elif item['typ'] == 'audio':
                self.addAudio(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ARDmediathek.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        if 'url' not in cItem:
            cItem['url'] = self.getFullUrl('appdata/servlet/-/search?json&searchText={0}'.format(urllib.quote_plus(searchPattern)))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("ARDmediathek.getLinksForVideo url[%s]" % cItem['url'])

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        try:
            data = byteify(json.loads(data))
            url = data['sections'][0]['modCons'][0]['mods'][0]['inhalte'][0]['mediaCollection']['url']
        except Exception:
            printExc()
            return []

        sts, data = self.getPage(url)
        if not sts:
            return []

        preferedQuality = int(config.plugins.iptvplayer.ardmediathek_prefquality.value)
        preferedFormat = config.plugins.iptvplayer.ardmediathek_prefformat.value
        tmp = preferedFormat.split(',')
        formatMap = {}
        for i in range(len(tmp)):
            formatMap[tmp[i]] = i

        try:
            urlTab = []
            tmpUrlTab = []
            data = byteify(json.loads(data))
            live = data['_isLive']
            subtitleUrl = data.get('_subtitleUrl', '')
            itemType = data['_type']
            try:
                data = data['_mediaArray']
                for media in data:
                    mediaTab = media['_mediaStreamArray']
                    for item in mediaTab:
                        quality = item['_quality']
                        urls = item['_stream']
                        if isinstance(urls, list):
                            url = urls[-1]
                        else:
                            url = urls

                        if url.startswith('https://'):
                            url = 'http' + url[5:]
                        for type in [{'pattern': '.m3u8', 'name': 'm3u8'}, {'pattern': '.mp4', 'name': 'mp4'}]:
                            if itemType == 'audio':
                                typeName = 'mp4'
                            elif not url.endswith(type['pattern']):
                                continue
                            else:
                                typeName = type['name']
                            if typeName == 'mp4':
                                quality = self._getQualityName(int(quality))
                                qualityVal = self.STREAM_QUALITY_MAP.get(quality, 10)
                                qualityPref = abs(qualityVal - preferedQuality)
                                formatPref = formatMap.get(typeName, 10)
                                tmpUrlTab.append({'url': url, 'quality_name': quality, 'quality': qualityVal, 'quality_pref': qualityPref, 'format_name': typeName, 'format_pref': formatPref})
                            elif typeName == 'm3u8':
                                if quality != 'auto':
                                    break
                                tmpList = getDirectM3U8Playlist(url, checkExt=False)
                                for tmpItem in tmpList:
                                    res = tmpItem['with']
                                    if res == 0:
                                        continue
                                    if res > 300:
                                        quality = 'low'
                                    if res > 600:
                                        quality = 'med'
                                    if res > 800:
                                        quality = 'high'
                                    if res > 950:
                                        quality = 'veryhigh'
                                    if res > 1200:
                                        quality = 'hd'
                                    qualityVal = self.STREAM_QUALITY_MAP.get(quality, 10)
                                    qualityPref = abs(qualityVal - preferedQuality)
                                    formatPref = formatMap.get(typeName, 10)
                                    tmpUrlTab.append({'url': tmpItem['url'], 'quality_name': quality + ' {0}x{1}'.format(tmpItem['with'], tmpItem['heigth']), 'quality': qualityVal, 'quality_pref': qualityPref, 'format_name': type['name'], 'format_pref': formatPref})
            except Exception:
                printExc()

            def _cmpLinks(it1, it2):
                prefmoreimportantly = config.plugins.iptvplayer.ardmediathek_prefmoreimportant.value
                if 'quality' == prefmoreimportantly:
                    if it1['quality_pref'] < it2['quality_pref']:
                        return -1
                    elif it1['quality_pref'] > it2['quality_pref']:
                        return 1
                    else:
                        if it1['quality'] < it2['quality']:
                            return -1
                        elif it1['quality'] > it2['quality']:
                            return 1
                        else:
                            if it1['format_pref'] < it2['format_pref']:
                                return -1
                            elif it1['format_pref'] > it2['format_pref']:
                                return 1
                            else:
                                return 0
                else:
                    if it1['format_pref'] < it2['format_pref']:
                        return -1
                    elif it1['format_pref'] > it2['format_pref']:
                        return 1
                    else:
                        if it1['quality_pref'] < it2['quality_pref']:
                            return -1
                        elif it1['quality_pref'] > it2['quality_pref']:
                            return 1
                        else:
                            if it1['quality'] < it2['quality']:
                                return -1
                            elif it1['quality'] > it2['quality']:
                                return 1
                            else:
                                return 0
            tmpUrlTab.sort(_cmpLinks)
            onelinkmode = config.plugins.iptvplayer.ardmediathek_onelinkmode.value
            for item in tmpUrlTab:
                url = item['url']
                name = item['quality_name'] + ' ' + item['format_name']
                if self.cm.isValidUrl(url):
                    decorateParams = {'iptv_livestream': live}
                    if self.cm.isValidUrl(subtitleUrl):
                        decorateParams['external_sub_tracks'] = [{'title': _('German'), 'url': subtitleUrl, 'lang': _('de'), 'format': 'ttml'}]
                    urlTab.append({'need_resolve': 0, 'name': name, 'url': self.up.decorateUrl(url, decorateParams)})
                    if onelinkmode:
                        break
            printDBG(tmpUrlTab)
        except Exception:
            printExc()

        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ARDmediathek.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("ARDmediathek.handleService: ---------> name[%s], category[%s] " % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if None == name:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif 'list_items' == category:
            self.listItems(self.currItem)
        elif 'list_tab' == category:
            self.listTab(self.currItem)

        elif 'missed_date' == category:
            self.listMissedDate(self.currItem)
        elif 'list_missed' == category:
            self.listSendungverpasst(self.currItem)
        elif 'list_cluster' == category:
            self.listCluster(self.currItem)
        elif 'list_content' == category:
            self.listContent(self.currItem)
    #WYSZUKAJ
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ARDmediathek(), True)
