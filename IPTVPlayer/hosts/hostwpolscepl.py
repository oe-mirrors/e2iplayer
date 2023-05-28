# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, NextDay, PrevDay
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
###################################################
# FOREIGN import
###################################################
from datetime import datetime, timedelta
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://wpolsce.pl/'


class WPolscePL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'wpolsce.pl', 'cookie': 'wpolsce.pl.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://wpolsce.pl/'
        self.DEFAULT_ICON_URL = 'http://satkurier.pl/uploads/52818.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("WPolscePL.listMainMenu")

        params = dict(cItem)
        params.update({'good_for_fav': True, 'title': 'Na żywo', 'category': 'list_live', 'url': self.getMainUrl()})
        self.addDir(params)

        params = dict(cItem)
        params.update({'good_for_fav': True, 'title': 'Ramówka', 'category': 'list_days', 'url': self.getMainUrl()})
        self.addDir(params)

        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'main-nav'), ('</ul', '>'))[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '' or '#' in url:
                    continue
                title = self.cleanHtmlStr(item)
                cat = url.split('/')[-1]
                if cat in ['gdzie-nas-ogladac']:
                    continue

                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'category': 'list_items', 'priv_cat': cat, 'url': self.getFullUrl(url)})
                self.addDir(params)

        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def delta2str(self, td):
        ret = []
        days = td.days
        hours = td.seconds / 3600
        minutes = (td.seconds / 60) % 60

        if days > 0:
            ret.append('%s d.' % days)
        if hours > 0:
            ret.append('%s godz.' % hours)
        if minutes > 0:
            ret.append('%s min.' % minutes)
        return ' '.join(ret)

    def str2date(self, txt):
        printDBG("str2date -> " + txt)
        tmp = txt.split('+', 1)
        date = datetime.strptime(tmp[0].replace('T', ' ').split('.', 1)[0], '%Y-%m-%d %H:%M:%S')
        if len(tmp) > 1 and ':' in tmp[1]:
            seconds = 0
            tmp = tmp[1].split(':')
            seconds += int(tmp[0].strip()) * 3600
            seconds += int(tmp[1].strip()) * 60
            date += timedelta(seconds=seconds)
        return date

    def listDays(self, cItem, nextCategory):
        printDBG("WPolscePL.listDays [%s]" % cItem)
        NOW = datetime.now()

        itemsList = []
        #NextDay, PrevDay
        day = NOW
        for idx in range(7):
            day = PrevDay(day)
            itemsList.append(day)

        itemsList.reverse()
        itemsList.append(NOW)
        itemsList.append(NextDay(NOW))

        for item in itemsList:
            date = item.strftime('%Y-%m-%d')
            if item == NOW:
                title = 'Dzisiaj'
            elif item > NOW:
                title = 'Jutro'
            else:
                title = date

            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'f_date': date})
            self.addDir(params)

    def listDay(self, cItem):
        printDBG("WPolscePL.listDay [%s]" % cItem)
        self._listItems(cItem, self.getFullUrl('/api/get_live_publications_for_day?day=') + cItem.get('f_date', ''), 'publications', False)

    def listLiveItems(self, cItem):
        printDBG("WPolscePL.listLiveItems [%s]" % cItem)
        self._listItems(cItem, self.getFullUrl('/api/get_live_publications'), 'live_publications_list', True)

    def _listItems(self, cItem, url, key, onlyLiveItems):
        sts, data = self.getPage(url)
        if not sts:
            return

        try:
            liveItem = None
            NOW = datetime.now()
            data = byteify(json.loads(data), '')
            for item in data[key]:
                if onlyLiveItems and not item.get('is_live', False):
                    continue

                url = self.getFullUrl(item['url'])
                icon = self.getFullIconUrl(item['picture_url'])
                if icon == '':
                    icon = self.getFullIconUrl(item['thumbnail_url'])

                title = self.cleanHtmlStr(item['title'])
                desc = []
                if item['is_future_publication']:
                    desc.append('Już za ' + self.delta2str(self.str2date(item['starts_at']) - NOW))
                desc.append(item['division_name'])
                if item['duration'] != '':
                    desc.append(self.delta2str(timedelta(seconds=item['duration'])))
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)})
                if item['is_future_publication']:
                    params['good_for_fav'] = False
                    self.addArticle(params)
                else:
                    if item.get('is_current_live', False) and liveItem == None:
                        liveItem = params
                    else:
                        self.addVideo(params)

            if liveItem != None:
                liveItem['type'] = 'video'
                self.currList.insert(0, liveItem)
            else:
                url = data['main_video']['video_url']
                if self.cm.isValidUrl(url) and onlyLiveItems:
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'type': 'video', 'title': 'Na żywo', 'url': url, 'icon': '', 'desc': ''})
                    self.currList.insert(0, params)
        except Exception:
            printExc()

    def listItems(self, cItem):
        printDBG("WPolscePL.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        cat = cItem.get('priv_cat', '')
        url = self.getFullUrl('/api/get_publications/%s?page=%s' % (cat, page))

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = False
        try:
            NOW = datetime.now()
            data = byteify(json.loads(data), '')
            if data.get('has_next', False):
                nextPage = True
            for item in data['publications']:
                url = self.getFullUrl(item['url'])
                icon = self.getFullIconUrl(item['thumbnail_url'])
                title = self.cleanHtmlStr(item['title'])
                desc = []
                if item['is_future_publication']:
                    desc.append('Już za ' + self.delta2str(self.str2date(item['starts_at']) - NOW))

                desc.append(item['division_name'])
                if item['duration'] != '':
                    desc.append(self.delta2str(timedelta(seconds=item['duration'])))
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)})
                if item['is_future_publication']:
                    params['good_for_fav'] = False
                    self.addArticle(params)
                else:
                    self.addVideo(params)
        except Exception:
            printExc()

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WPolscePL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        url = self.getFullUrl('/szukaj?q=' + urllib_quote_plus(searchPattern))
        sts, data = self.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'result__single'), ('</ul', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\stitle=['"]([^'^"]+?)['"]''')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\salt=['"]([^'^"]+?)['"]''')[0])

            desc = []
            date = None
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<li', '</li>')
            for t in item:
                if '<time' in t:
                    date = self.str2date(self.cleanHtmlStr(t))
                    desc.append(date.strftime('%Y-%m-%d %H:%M'))
                else:
                    desc.append(self.cleanHtmlStr(t))

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)})
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("WPolscePL.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, 'PlayerManager', '}')[1]
        videoId = self.cm.ph.getSearchGroups(data, '''['"]?videoId['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]
        if videoId == '':
            return

        videoUrl = 'https://www.youtube.com/watch?v=' + videoId
        return self.up.getVideoLinkExt(videoUrl)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_live':
            self.listLiveItems(self.currItem)
        elif category == 'list_days':
            self.listDays(self.currItem, 'list_day')
        elif category == 'list_day':
            self.listDay(self.currItem)
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
        CHostBase.__init__(self, WPolscePL(), True, [])
