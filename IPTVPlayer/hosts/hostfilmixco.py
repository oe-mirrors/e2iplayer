# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetCookieDir, ReadTextFile, WriteTextFile
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
from binascii import hexlify
from hashlib import md5
import re
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.filmixco_alt_domain = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.filmixco_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.filmixco_password = ConfigText(default="", fixed_size=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.filmixco_alt_domain))
    optionList.append(getConfigListEntry(_("login"), config.plugins.iptvplayer.filmixco_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.filmixco_password))
    return optionList
###################################################


def gettytul():
    return 'https://filmix.co/'

class FilmixCO(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'filmix.co', 'cookie': 'filmix.co.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        self.MAIN_URL = 'https://filmix.co/'
        self.DEFAULT_ICON_URL = 'http://www.userlogos.org/files/logos/jumpordie/filmix.png'

        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = []
        self.domainSelected = False

        self.loggedIn = None
        self.login = ''
        self.password = ''

    def getUtf8Str(self, st):
        try:
            idx = 0
            st2 = ''
            while idx < len(st):
                st2 += '\\u0' + st[idx:idx + 3]
                idx += 3
            return st2.decode('unicode-escape').encode('UTF-8')
        except Exception:
            printExc()
        return ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def selectDomain(self):
        if self.domainSelected:
            return 
        self.domainSelected = True
        domains = ['http://filmix.cc/films', 'https://filmix.co/films']
        domain = config.plugins.iptvplayer.filmixco_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain + 'films')

        sts = False
        for domain in domains:
            sts, data = self.getPage(domain)
            if not sts:
                continue
            if '/films' in data:
                self.setMainUrl(data.meta['url'])
                break
            else:
                sts = False

    def listMainMenu(self, cItem):
        printDBG("FilmixCO.listMainMenu")
        sts, data = self.getPage(self.getFullUrl('/films'))
        self.cacheFilters = []
        if sts:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'filtersForm'), ('</form', '>'))[1]
            tmp = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'filter-category'),)
            for item in tmp:
                scope = self.cm.ph.getSearchGroups(item, '''\sdata\-scope=['"]([^'^"]+?)['"]''')[0]
                type = self.cm.ph.getSearchGroups(item, '''\sdata\-type=['"]([^'^"]+?)['"]''')[0]
                if type != '':
                    # need separate request, https://filmix.co/engine/ajax/get_filter.php, to get value of filters
                    self.cacheFilters.append({'scope': scope, 'type': type})
                else:
                    values = []
                    item = re.compile('''<(?:div|span)([^>]+?data\-scope=['"]%s['"][^>]*?)>([^>]+?)<''' % scope).findall(data)
                    for it in item:
                        title = self.cleanHtmlStr(it[1])
                        value = self.cm.ph.getSearchGroups(it[0], '''\sdata\-value=['"]([^'^"]+?)['"]''')[0]
                        if value == '':
                            continue
                        values.append({'title': title, ('f_%s' % scope): value})
                    if len(values):
                        self.cacheFilters.append({'scope': scope, 'values': values})
       
        MAIN_CAT_TAB = [{'category': 'top250', 'title': 'ТОП 250', 'url': self.getFullUrl('/top250')},
                        {'category': 'filters', 'title': _('Filters')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def top250Type(self, cItem, nextCategory):
        printDBG("FilmixCO.listMainMenu")
        
        for item in [('Фильмы', ''), ('Сериалы', 's'), ('Мультфильмы', 'm')]:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': item[0], 'url': cItem['url'] + item[1]})
            self.addDir(params)
    
    def listTop250(self, cItem, nextCategory):
        printDBG("FilmixCO.listTop250")
        
        for item in [('Топ 250 filmix.me', ''), ('Топ 250 Кинопоиск', '/kp'), ('Топ 250 IMDB', '/imdb')]:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': item[0], 'url': cItem['url'] + item[1]})
            self.addDir(params)
            
    def listTop250Sort(self, cItem, nextCategory):
        printDBG("FilmixCO.listTop250Sort")
        
        asc = '\xe2\x86\x91 '
        desc = '\xe2\x86\x93 '
        for item in [(desc + 'По убыванию', ''), (asc + 'По возрастанию', '/sup'), (desc + 'По годам', '/ydown'), (asc + 'По годам', '/yup')]:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': item[0], 'url': cItem['url'] + item[1]})
            self.addDir(params)
        
    def getFilterUrl(self, cItem):
        linkComp = []
        for item in self.cacheFilters:
            key = 'f_%s' % item['scope']
            if key in cItem:
                linkComp.append('%s%s' % (item['scope'], cItem[key]))
        linkComp.append('dd') # no premium
        return self.getFullUrl('/filters/' + '-'.join(linkComp))
        
    def listFilters(self, cItem, nextCategory):
        printDBG("FilmixCO.listFilters")
        idx = cItem.get('f_idx', 0)
        if idx < len(self.cacheFilters):
            filter = self.cacheFilters[idx]
            if 'values' not in filter and 'type' in filter:
                # separate request is needed to get filter values
                values = []
                if 'rating' == filter['type']:
                    for i in range(9, 0, -1):
                        values.append({'title': '%s-%s' % (str(i).zfill(2), str(i + 1).zfill(2)), ('f_%s' % filter['scope']): '%s%s' % (str(i).zfill(2), str(i + 1).zfill(2))})
                    if len(values):
                        values.insert(0, {'title': _('--Any--')})
                else:
                    url = self.getFullUrl('/engine/ajax/get_filter.php')
                    urlParams = dict(self.defaultParams)
                    urlParams['header'] = dict(self.AJAX_HEADER)
                    urlParams['Referer'] = self.getMainUrl()
                    sts, data = self.getPage(url, urlParams, {'scope': 'cat', 'type': filter['type']})
                    if not sts:
                        return
                    try:
                        printDBG(data)
                        data = json_loads('[%s]' % data.replace('":"', '","')[1:-1])
                        for i in range(0, len(data), 2):
                            title = self.cleanHtmlStr(data[i + 1])
                            value = data[i]
                            if value.startswith('f'):
                                value = value[1:]
                            values.append({'title': title, ('f_%s' % filter['scope']): value})
                        if len(values):
                            if 'years' == filter['type']:
                                values.reverse()
                            values.insert(0, {'title': _('--Any--')})
                            filter['values'] = values
                    except Exception:
                        printExc()
            elif 'values' in filter:
                values = filter['values']
            
            cItem = dict(cItem)
            idx += 1
            if idx < len(self.cacheFilters):
                cItem['f_idx'] = idx
            else:
                cItem['category'] = nextCategory
            
            for item in values:
                params = dict(cItem)
                params.update(item)
                params['url'] = self.getFilterUrl(params)
                self.addDir(params)
        else:
            printExc("Should not happen")
    
    def listSort(self, cItem, nextCategory):
        printDBG("FilmixCO.listSort")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        cItem = dict(cItem)
        cItem['url'] = data.meta['url']

        basePostData = {}
        data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'movie_sort'), ('</form', '>'), False)[1]
        tmp = re.compile('''<input([^>]+?)>''', re.I).findall(data)
        for item in tmp:
            name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
            value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
            basePostData[name] = value

        data = self.cm.ph.getAllItemsBeetwenMarkers(data.split('sort-items', 1)[-1], '<span', '</span>')
        for item in data:
            baseTitle = self.cleanHtmlStr(item)
            sortOrderBy = self.cm.ph.getSearchGroups(item, '''data\-type=['"]([^'^"]+?)['"]''')[0]

            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<i', '</i>')
            for it in item:
                direction = self.cm.ph.getSearchGroups(it, '''data\-type=['"]([^'^"]+?)['"]''')[0]
                desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(it, '''title=['"]([^'^"]+?)['"]''')[0])

                postData = dict(basePostData)
                postData.update({'dledirection': direction, 'dlenewssortby': sortOrderBy})

                if 'asc' == direction:
                    title = '\xe2\x86\x91 ' + baseTitle
                elif 'desc' == direction:
                    title = '\xe2\x86\x93 ' + baseTitle

                params = dict(cItem)
                params.update({'category': nextCategory, 'title': title, 'desc': desc, 'post_data': postData})
                self.addDir(params)
        
    def listItems(self, cItem, nextCategory):
        printDBG("FilmixCO.listItems")
        page = cItem.get('page', 1)

        postData = cItem.get('post_data')
        urlParams = dict(self.defaultParams)
        if '/ajax/' in cItem['url']:
            urlParams['header'] = dict(self.AJAX_HEADER)
            urlParams['Referer'] = self.getMainUrl()
        
        sts, data = self.getPage(cItem['url'], urlParams, postData)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'navigation'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>', 'itemtype'), ('</article', '>'), False)
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])

            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'name-block'), ('</div', '>'))[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<h2', '</h2>')[1])
            titleOrg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'origin-name'), ('</div', '>'))[1])
            if titleOrg != '':
                if title == '':
                    title = titleOrg
                else:
                    title += ' / %s' % titleOrg

            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<div', '>', '"item'), ('</div', '>'))
            tmp.append(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t.replace(' , ', ', '))

            if url != '':
                params = dict(cItem)
                params.update({'category': nextCategory, 'good_for_fav': True, 'title': title, 'url': url, 'desc': '[/br]'.join(desc), 'icon': icon})
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.pop('post_data', None)
            params.pop('desc', None)
            params.update({'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)
            
    def exploreItem(self, cItem, nextCategory):
        printDBG("FilmixCO.exploreItem")
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)
        
        trailerVideo = self.getUtf8Str(self.cm.ph.getSearchGroups(data, '''trailerVideoLink5\s*?=\s*?['"]#([^'^"]+?)['"]''')[0])
        if self.cm.isValidUrl(trailerVideo):
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'trailer-wrap'), ('</div', '>'), False)[1])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': trailerVideo, 'title': title + ' ' + cItem['title']})
            self.addVideo(params)
        
        postId = self.cm.ph.getSearchGroups(data, '''data\-player=['"]([^"^']+?)['"]''')[0]
        
        url = self.getFullUrl('/api/movies/player_data')
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.AJAX_HEADER)
        urlParams['Referer'] = cUrl
        sts, data = self.getPage(url, urlParams, {'post_id': postId, 'showfull': 'true'})
        if not sts:
            return
        
        try:
            data = json_loads(data)
            printDBG(">>>\n%s\n" % data)
            data = data['message']['translations']['html5']
            for key in data:
                url = self.getUtf8Str(data[key][1:])
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cleanHtmlStr(key)
                if url.split('?', 1)[-1].lower().endswith('.txt'):
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category': nextCategory, 'url': url, 'title': title, 'p_url': cUrl, 'p_title': cItem['title'], 'post_id': postId})
                    self.addDir(params)
                else:
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'url': url, 'title': title + ' ' + cItem['title']})
                    self.addVideo(params)
        except Exception:
            printExc()
        
    def listPlaylists(self, cItem, nextCategory):
        printDBG("FilmixCO.listPlaylists")
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.AJAX_HEADER)
        urlParams['Referer'] = cItem.get('p_url', self.getMainUrl())
        
        baseTitle = cItem['p_title']
        sts, data = self.getPage(cItem['url'], urlParams)
        if not sts:
            return
        
        try:
            data = self.getUtf8Str(data[1:])
            data = json_loads(data)
            for playlistItem in data['playlist']:
                subItems = []
                for item in playlistItem['playlist']:
                    url = item['file']
                    if not self.cm.isValidUrl(url):
                        continue
                    title = self.cleanHtmlStr(item['comment'])
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'type': 'video', 'url': url, 'title': baseTitle + ' ' + title})
                    subItems.append(params)
                
                if len(subItems):
                    title = self.cleanHtmlStr(playlistItem['comment'])
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category': nextCategory, 'url': url, 'title': title, 'sub_items': subItems})
                    self.addDir(params)
        except Exception:
            printExc()
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmixCO.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        #searchPattern = 'Шрэк Третий'
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/engine/ajax/sphinx_search.php')
        cItem['post_data'] = {'scf': 'fx', 'story': searchPattern, 'search_start': '0', 'do': 'search', 'subaction': 'search', 'years_ot': '1902', 'years_do': '3000', 'kpi_ot': '1', 'kpi_do': '10', 'imdb_ot': '1', 'imdb_do': '10', 'sort_name': '', 'undefined': 'asc', 'sort_date': '', 'sort_favorite': '', 'simple': '1'}
        self.listItems(cItem, 'explore_item')
    
    def getLinksForVideo(self, cItem):
        printDBG("FilmixCO.getLinksForVideo [%s]" % cItem)
        self.tryTologin()
        urlTab = []

        qualities = self.cm.ph.getSearchGroups(cItem['url'], '''\[([^\]]+?)\]''')[0].split(',')
        baseUrl = re.compile('''\[([^\]]+?)\]''').sub('%s', cItem['url'])
        printDBG("qualities: %s" % qualities)
        printDBG("baseUrl: %s" % baseUrl)
        try:
            for item in qualities:
                item = item.strip()
                if item != '':
                    urlTab.append({'name': item, 'url': baseUrl % item, 'need_resolve': 0})
        except Exception:
            printExc()
        
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("FilmixCO.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        return urlTab

    def tryTologin(self):
        printDBG('tryTologin start')
        self.selectDomain()

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.filmixco_login.value or\
            self.password != config.plugins.iptvplayer.filmixco_password.value:

            loginCookie = GetCookieDir('filmix.co.login')
            self.login = config.plugins.iptvplayer.filmixco_login.value
            self.password = config.plugins.iptvplayer.filmixco_password.value

            sts, data = self.getPage(self.getMainUrl())
            if sts:
                self.setMainUrl(self.cm.meta['url'])

            freshSession = False
            if sts and 'action=logout' in data:
                printDBG("Check hash")
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                prevHash = ReadTextFile(loginCookie)[1].strip()

                printDBG("$hash[%s] $prevHash[%s]" % (hash, prevHash))
                if hash == prevHash:
                    self.loggedIn = True
                    return
                else:
                    freshSession = True

            rm(loginCookie)
            rm(self.COOKIE_FILE)
            if freshSession:
                sts, data = self.getPage(self.getMainUrl(), MergeDicts(self.defaultParams, {'use_new_session': True}))

            self.loggedIn = False
            if '' == self.login.strip() or '' == self.password.strip():
                return False

            msgTab = [_('Login failed.')]
            if sts:
                actionUrl = self.getFullUrl('/engine/ajax/user_auth.php')
                post_data = {'login_name': self.login, 'login_password': self.password, 'login_not_save': '1', 'login': 'submit'}

                httpParams = dict(self.defaultParams)
                httpParams['header'] = MergeDicts(httpParams['header'], {'Referer': self.cm.meta['url'], 'Accept': '*/*', 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

                sts, data = self.getPage(actionUrl, httpParams, post_data)
                printDBG(data)
                if sts:
                    msgTab.append(ph.clean_html(data))
                sts, data = self.getPage(self.getMainUrl())

            if sts and 'action=logout' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                printDBG(data)
                self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(msgTab), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')

            if self.loggedIn:
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                WriteTextFile(loginCookie, hash)

        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.tryTologin()

        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
            
        elif category == 'top250':
            self.top250Type(self.currItem, 'list_top250')
        elif category == 'list_top250':
            self.listTop250(self.currItem, 'list_top250_sort')
        elif category == 'list_top250_sort':
            self.listTop250Sort(self.currItem, 'list_items')
        elif category == 'filters':
            self.listFilters(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_playlists')
        elif category == 'list_playlists':
            self.listPlaylists(self.currItem, 'sub_items')
        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
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
        CHostBase.__init__(self, FilmixCO(), True, favouriteTypes=[]) 
