# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
import base64
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse
from Components.config import config, ConfigYesNo, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tv3player_use_web_proxy = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use web-proxy for VODs (it may be illegal):"), config.plugins.iptvplayer.tv3player_use_web_proxy))
    return optionList
###################################################


def gettytul():
    return 'https://virginmediatelevision.ie/player'


class C3player(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'C3player.tv', 'cookie': 'rte.ie.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'http://compass.xboxlive.com/assets/58/73/58738a5d-013b-4bf1-ac89-cdb72477dae9.png'
        self.MAIN_URL = 'https://virginmediatelevision.ie/player'
        self.cacheLinks = {}

    def listMainMenu(self, cItem):
        printDBG("C3player.listMainMenu")
        MAIN_CAT_TAB = [{'category': 'list_live', 'title': _('LIVE'), 'url': self.getFullUrl('/player/assets/ajax/live_drop_down.php?layout=top_nav')},
                        {'category': 'list_by_day', 'title': _('BY DAY'), 'url': self.getFullUrl('/3player/byday')},
                        {'category': 'list_az', 'title': _('A-Z'), 'url': self.getFullUrl('/3player/a-z')},

                        {'category': 'search', 'title': _('Search'), 'search_item': True, },
                        {'category': 'search_history', 'title': _('Search history'), }
                       ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listLiveChannels(self, cItem):
        printDBG("C3player.listLiveChannels")

        descMap = {}
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = re.sub("<!--[\s\S]*?-->", "", data)
        data = re.compile('''<div[^>]+?class=['"]live_[^>]+?>''').split(data)
        if len(data):
            del data[0]

        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h4', '</h4>')[1])

            item = item.split('top_bar_up_next', 1)

            descTab = []
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item[0], ('<div', '>', 'progress'), ('</div', '>'))[1])
            if tmp != '':
                descTab.append(tmp)
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item[0], ('<div', '>', 'time'), ('</div', '>'))[1])
            if tmp != '':
                descTab.append(tmp)
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item[0], '<p', '</p>')[1].split('<span', 1)[0])
            if tmp != '':
                descTab.append(tmp)
            descTab.append("")
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item[-1], '<span', '</span>')[1])
            if tmp != '':
                descTab.append(tmp)
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item[-1], '<p', '</p>')[1])
            if tmp != '':
                descTab.append(tmp)

            params = dict(cItem)
            params.update({'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(descTab)})
            self.addVideo(params)

    def listSubItems(self, cItem):
        printDBG("C3player.listSubItems")
        self.currList = cItem['sub_items']

    def _listItems(self, data, nextCategory='explore_show', baseTitle='%s'):
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h4', '</h4>')[1])
            date = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'list_date'), ('</p', '>'))[1])
            time = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'list_time'), ('</span', '>'))[1])

            descTab = []

            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<p', '>'), ('</p', '>'))
            for t in tmp:
                t = t.split('<span', 1)
                for idx in range(len(t)):
                    if idx == 1:
                        t[idx] = '<span' + t[idx]
                    txt = self.cleanHtmlStr(t[idx])
                    if txt != '' and txt != date:
                        descTab.append(txt)

            if time != '' and len(descTab):
                descTab.insert(1, time)

            params = {'good_for_fav': True, 'title': baseTitle % title, 'url': url, 'icon': icon, }
            if '/videos/' in icon:
                if date not in params['title']:
                    params['title'] = params['title'] + ': ' + date
                if len(descTab):
                    params['desc'] = ' | '.join(descTab[1:]) + '[/br]' + descTab[0]
                self.addVideo(params)
            else:
                params.update({'name': 'category', 'type': 'category', 'category': nextCategory, 'desc': '[/br]'.join(descTab)})
                self.addDir(params)

    def exploreShow(self, cItem, nextCategory):
        printDBG("C3player.exploreShow cItem[%s]" % (cItem))

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'data-type'), ('</a', '>'))
        for item in data:
            showId = self.cm.ph.getSearchGroups(item, '''data\-showID=['"]([0-9]+?)['"]''')[0]
            dataType = self.cm.ph.getSearchGroups(item, '''data\-type=['"]([^'^"]+?)['"]''')[0]
            videoID = self.cm.ph.getSearchGroups(item, '''data\-videoID=['"]([0-9]+?)['"]''')[0]
            if '' in [showId, dataType]:
                continue
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl('/player/assets/ajax/filter_tiles.php?showID={0}&videoID=&type={1}'.format(showId, dataType))
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title.title(), 'f_show_title': cItem['title'], 'url': url, 'f_show_id': showId, 'f_data_type': dataType})
            self.addDir(params)

        if 0 == len(self.currList):
            dataType = 'all'
            showId = self.cm.ph.getSearchGroups(cItem['url'] + '/', '''/show/([0-9]+?)[^0-9]''')[0]
            if showId != '':
                url = self.getFullUrl('/player/assets/ajax/filter_tiles.php?showID={0}&videoID=&type={1}'.format(showId, dataType))
                cItem = dict(cItem)
                cItem.update({'good_for_fav': True, 'category': nextCategory, 'title': _('All'), 'f_show_title': cItem['title'], 'url': url, 'f_show_id': showId, 'f_data_type': dataType})
                self.listItems(cItem, 'explore_show')

    def listItems(self, cItem, nextCategory):
        printDBG("C3player.listItems cItem[%s]" % (cItem))
        page = cItem.get('page', 0)
        showTitle = cItem['f_show_title']

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        items = re.compile('''<div[^>]+?class=['"]clear['"][^>]*?>''').split(data)
        if len(items):
            del items[-1]
        self._listItems(items, baseTitle='{0}: %s'.format(showTitle))

        data = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'load_more'), ('</a', '>'))[1]
        if data != '':
            showId = self.cm.ph.getSearchGroups(data, '''data\-showID=['"]([0-9]+?)['"]''')[0]
            offset = self.cm.ph.getSearchGroups(data, '''data\-offset=['"]([0-9]+?)['"]''')[0]
            id = self.cm.ph.getSearchGroups(data, '''\sid=['"]([^'^"]+?)['"]''')[0]
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> [%s] [%s] [%s]" % (showId, offset, id))
            if '' not in (showId, offset, id):
                url = self.getFullUrl('/player/assets/ajax/{0}.php?showID={1}&videoID=&offset={2}&type={3}'.format(id, showId, offset, cItem['f_data_type']))
                params = dict(cItem)
                params.update({'good_for_fav': False, 'url': url, 'title': _('Next page'), 'page': page + 1})
                self.addDir(params)

    def listByDay(self, cItem, nextCategory1, nextCategory2):
        printDBG("C3player.listByDay cItem[%s]" % (cItem))

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        filters = []
        filterData = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'data-pageType'), ('</a', '>'))
        for item in filterData:
            showId = self.cm.ph.getSearchGroups(item, '''data\-showID=['"]([^'^"]+?)['"]''')[0]
            if showId == '':
                continue
            title = showId.upper()
            filters.append({'title': title, 'f_filter_id': showId})

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'byday_bxslider'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            date = self.cm.ph.getSearchGroups(item, '''([0-9]{2}\-[0-9]{2}\-[0-9]{4})''')[0]
            if date == '':
                continue
            subItems = []
            for it in filters:
                url = self.getFullUrl('/player/assets/ajax/ajax_site.php?pageType=byday&showID=%s&videoID=%s' % (it['f_filter_id'], date))
                params = dict(it)
                params.update({'good_for_fav': True, 'name': 'category', 'type': 'category', 'category': nextCategory2, 'url': url})
                subItems.append(params)

            if len(subItems):
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'category': nextCategory1, 'sub_items': subItems})
                self.addDir(params)

    def listByDayItems(self, cItem, nextCategory):
        printDBG("C3player.listByDayItems cItem[%s]" % (cItem))

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        try:
            data = json_loads(data)['content']
            data = re.sub("<!--[\s\S]*?-->", "", data).split('<footer', 1)[0]
            data = re.compile('''<div[^>]+?list_row[^>]+?>''').split(data)
            if len(data):
                del data[0]
            self._listItems(data)
        except Exception:
            printExc()

    def listAZ(self, cItem, nextCategory):
        printDBG("C3player.listAZ cItem[%s]" % (cItem))

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'btn_az'), ('</section', '>'))[1]
        data = re.sub("<!--[\s\S]*?-->", "", data)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            if 'disabled' in item:
                continue
            showId = self.cm.ph.getSearchGroups(item, '''data\-showID=['"]([^'^"]+?)['"]''')[0]
            pageType = self.cm.ph.getSearchGroups(item, '''data\-pageType=['"]([^'^"]+?)['"]''')[0]
            if pageType == '':
                continue

            title = self.cleanHtmlStr(item).upper()
            url = self.getFullUrl('/player/assets/ajax/ajax_site.php?pageType=%s') % pageType
            if showId != '':
                url += '&showID=%s' % showId

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'category': nextCategory, 'url': url})
            self.addDir(params)

    def listAZItems(self, cItem, nextCategory):
        printDBG("C3player.listAZItems cItem[%s]" % (cItem))

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        try:
            data = json_loads(data)['content']
            data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'az_list'), ('</section', '>'))[1]

            data = re.sub("<!--[\s\S]*?-->", "", data)
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                item = item.split('</a>', 1)
                title = self.cleanHtmlStr(item[0])
                desc = self.cleanHtmlStr(item[-1])
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'category': nextCategory, 'url': url, 'desc': desc})
                self.addDir(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("C3player.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        url = self.getFullUrl('/player/assets/ajax/search.php')
        post_data = {'queryString': searchPattern, 'limit': 100}

        sts, data = self.cm.getPage(url, post_data=post_data)
        if not sts:
            return

        printDBG(data)

        itemsReObj = re.compile('''<div[^>]+?list_row[^>]+?>''')

        data = re.compile('''<div[^>]+?list_title[^>]+?>''').split(data)
        if len(data):
            del data[0]

        for section in data:
            sTtile = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<h2', '</h2>')[1])
            section = itemsReObj.split(section)
            if len(section):
                del section[0]
            self._listItems(section)

    def getLinksForVideo(self, cItem):
        printDBG("C3player.getLinksForVideo [%s]" % cItem)
        linksTab = []
        hlsLinksTab = []
        hdsLinksTab = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        hlsUrl = self.cm.ph.getSearchGroups(data, '''['"]?file['"]?\s*?:\s*?['"](https?://[^'^"]+?\.m3u8(?:\?[^'^"]+?)?)['"]''')[0]
        if hlsUrl != '':
            hlsLinksTab = getDirectM3U8Playlist(hlsUrl, checkExt=True, checkContent=True, sortWithMaxBitrate=999999999)
        else:
            embedToken = self.cm.ph.getSearchGroups(data, '''['"]?embedToken['"]?\s*?:\s*?['"](https?://[^'^"]+?)['"]''')[0]
            if embedToken == '':
                errorMsg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'geo_block'), ('</div', '>'))[1])
                SetIPTVPlayerLastHostError(errorMsg)
            if embedToken == '' and config.plugins.iptvplayer.tv3player_use_web_proxy.value:
                # http://getproxi.es/IE-proxies/
                proxy = 'http://ruproxy.herokuapp.com/index.php?q={0}&hl=2e1'.format(urllib_quote_plus(cItem['url']))
                params = {'header': dict(self.HEADER)}
                params['header']['Referer'] = proxy
                params.update({'cookie_items': {'flags': '2e1'}, 'use_cookie': True})
                sts, data = self.cm.getPage(proxy, params)
                if not sts:
                    return []
                printDBG("+++++++++++++++++++++++++++++++++++++++")
                printDBG(data)
                printDBG("+++++++++++++++++++++++++++++++++++++++")
                embedToken = self.cm.ph.getSearchGroups(data, '''['"]?embedToken['"]?\s*?:\s*?['"](https?://[^'^"]+?)['"]''')[0]
            drmProtection = False
            if embedToken != '':
                parsedUri = urlparse(embedToken)
                auth = parsedUri.path.split('/embed_token/', 1)[-1].split('/')
                if len(auth) > 1:
                    url = 'https://player.ooyala.com/sas/player_api/v2/authorization/embed_code/%s/%s?embedToken=%s&device=html5&domain=www.tv3.ie&auth_token=' % (auth[0], auth[1], urllib_quote_plus(embedToken))
                    sts, data = self.cm.getPage(url)
                    if not sts:
                        return []
                    try:
                        drmProtection = False
                        #printDBG(data)
                        data = json_loads(data)
                        for item in data['authorization_data'][auth[1]]['streams']:
                            if item['url']['format'] == 'encoded':
                                url = base64.b64decode(item['url']['data'])
                            else:
                                url = item['url']['data']
                            if item['delivery_type'] == 'hls':
                                if item.get('drm'):
                                    drmProtection = True
                                hlsLinksTab = getDirectM3U8Playlist(url, checkExt=True, checkContent=True, sortWithMaxBitrate=999999999)
                            elif item['delivery_type'] == 'hds':
                                hdsLinksTab = getF4MLinksWithMeta(url, checkExt=False, sortWithMaxBitrate=999999999)
                    except Exception:
                        printExc()

            printDBG(hlsLinksTab)
            if drmProtection:
                SetIPTVPlayerLastHostError(_('Link protected with DRM.'))
                return []
        for idx in range(len(hlsLinksTab)):
            hlsLinksTab[idx]['url'] = strwithmeta(hlsLinksTab[idx]['url'], {'iptv_proto': 'm3u8'})

        for idx in range(len(hdsLinksTab)):
            hdsLinksTab[idx]['url'] = strwithmeta(hdsLinksTab[idx]['url'], {'iptv_proto': 'f4m'})

        linksTab.extend(hlsLinksTab)
        linksTab.extend(hdsLinksTab)
        return linksTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('IE')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_live':
            self.listLiveChannels(self.currItem)
        elif category == 'explore_show':
            self.exploreShow(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_show')
        elif category == 'list_by_day':
            self.listByDay(self.currItem, 'sub_items', 'list_by_day_items')
        elif category == 'list_by_day_items':
            self.listByDayItems(self.currItem, 'explore_show')
        elif category == 'list_az':
            self.listAZ(self.currItem, 'list_az_items')
        elif category == 'list_az_items':
            self.listAZItems(self.currItem, 'explore_show')
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

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, C3player(), True, [])
