# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, GetTmpDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin, urlparse
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_urlencode, urllib_unquote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
from copy import deepcopy
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.filmezzeu_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.filmezzeu_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.filmezzeu_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.filmezzeu_password))
    return optionList
###################################################


def gettytul():
    return 'http://filmezz.eu/'


class FilmezzEU(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'filmezz.eu', 'cookie': 'filmezzeu.cookie'})
        self.DEFAULT_ICON_URL = 'http://plugins.movian.tv/data/3c3f8bf962820103af9e474604a0c83ca3b470f3'
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'http://filmezz.eu/'
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.loggedIn = None
        self.login = ''
        self.password = ''
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('Home'), 'url': self.getFullUrl('kereses.php')},
                             {'category': 'list_items', 'title': _('Movies'), 'url': self.getFullUrl('kereses.php?q=0&l=0&e=0&c=0&t=1&h=0&o=feltoltve')},
                             {'category': 'list_items', 'title': _('Series'), 'url': self.getFullUrl('kereses.php?q=0&l=0&e=0&c=0&t=2&h=0&o=feltoltve')},
                             {'category': 'list_items', 'title': _('Top movies'), 'url': self.getFullUrl('kereses.php?q=0&l=0&e=0&c=0&t=1&h=0&o=nezettseg')},
                             {'category': 'list_items', 'title': _('Top series'), 'url': self.getFullUrl('kereses.php?q=0&l=0&e=0&c=0&t=2&h=0&o=nezettseg')},
                             {'category': 'list_items', 'title': _('Latest added'), 'url': self.getFullUrl('kereses.php?q=0&l=0&e=0&c=0&t=0&h=0&o=feltoltve')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def getFullIconUrl(self, url):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullIconUrl(self, url)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def fillCacheFilters(self, cItem):
        printDBG("FilmezzEU.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        def addFilter(data, marker, baseKey, addAll=True, titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                if title in ['Összes']:
                    addAll = False
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="row form-group">', '</select>')
        for tmp in data:
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
            addFilter(tmp, 'value', key, False)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("FilmezzEU.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if 0 == len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("FilmezzEU.listItems")
        url = cItem['url']
        page = cItem.get('page', 0)

        query = {}
        if page > 0:
            query['p'] = page

        for key in self.cacheFiltersKeys:
            baseKey = key[2:] # "f_"
            if key in cItem:
                query[baseKey] = urllib_quote(cItem[key])

        query = urllib_urlencode(query)
        if '?' in url:
            url += '&' + query
        else:
            url += '?' + query

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'pagination', '</ul>')[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, 'p=(%s)[^0-9]' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, 'movie-list', '<footer class="footer">')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</a>')
        reDescObj = re.compile('title="([^"]+?)"')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue
            if 'kereses.php' in url:
                continue

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="title">', '</span>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])

            # desc start
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<li>', '</li>')
            descTab = []
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t == '':
                    continue
                descTab.append(t)
            tmp = self.cm.ph.getDataBeetwenMarkers(item, 'movie-icons">', '</ul>', False)[1]
            t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="cover-element imdb"', '</span>')[1])
            tmp = reDescObj.findall(tmp)
            if t != '':
                tmp.insert(0, t)
            descTab.insert(0, ' | '.join(tmp))
            ######

            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': '[/br]'.join(descTab), 'icon': icon}
            params['category'] = nextCategory
            self.addDir(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("FilmezzEU.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="text"', '</div>')[1])

        # trailer
        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<a[^>]+?class="venobox"'), re.compile('>'))[1]
        url = self.cm.ph.getSearchGroups(tmp, '''href=['"]([^'^"]+?)['"]''')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, '''title=['"]([^'^"]+?)['"]''')[0])
        if 1 == self.up.checkHostSupport(url):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'prev_title': cItem['title'], 'url': url, 'prev_url': cItem['url'], 'prev_desc': cItem.get('desc', ''), 'desc': desc})
            self.addVideo(params)

        reDescObj = re.compile('title="([^"]+?)"')
        titlesTab = []
        self.cacheLinks = {}
        data = self.cm.ph.getDataBeetwenMarkers(data, 'url-list', '</section>')[1]
        data = data.split('<div class="col-sm-4 col-xs-12 host">')
        if len(data):
            del data[0]
        for tmp in data:
            dTab = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div', '</div>')
            if len(dTab) < 2:
                continue
            title = self.cleanHtmlStr(dTab[1])

            # serverName
            t = self.cm.ph.getDataBeetwenMarkers(tmp, 'movie-icons">', '<div', False)[1]
            serverName = reDescObj.findall(t)
            if t != '':
                serverName.append(self.cleanHtmlStr(t))
            serverName = ' | '.join(serverName)
            #if 'letöltés' in serverName: continue

            t = self.cm.ph.getDataBeetwenReMarkers(tmp, re.compile('<a[^>]+?class="url-btn play"'), re.compile('>'))[1]
            url = self.cm.ph.getSearchGroups(t, '''href=['"]([^'^"]+?)['"]''')[0]
            if url == '':
                continue

            if url.startswith('http://adf.ly/'):
                url = urllib_unquote(url.rpartition('/')[2])
                if url == '':
                    continue

            if title not in titlesTab:
                titlesTab.append(title)
                self.cacheLinks[title] = []
            self.cacheLinks[title].append({'name': serverName, 'url': url, 'need_resolve': 1})

        for item in titlesTab:
            params = dict(cItem)
            title = cItem['title']
            if item != '':
                title += ' : ' + item
            params.update({'good_for_fav': False, 'title': title, 'links_key': item, 'prev_desc': cItem.get('desc', ''), 'desc': desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmezzEU.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('kereses.php?s=' + urllib_quote_plus(searchPattern))
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("FilmezzEU.getLinksForVideo [%s]" % cItem)
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        key = cItem.get('links_key', '')
        return self.cacheLinks.get(key, [])

    def getVideoLinks(self, videoUrl):
        printDBG("FilmezzEU.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        url = videoUrl
        post_data = None
        while True:
            httpParams = dict(self.defaultParams)
            httpParams['max_data_size'] = 0
            self.cm.getPage(url, httpParams, post_data)
            if 'url' in self.cm.meta:
                videoUrl = self.cm.meta['url']
            else:
                return []

            if self.up.getDomain(self.getMainUrl()) in videoUrl:
                sts, data = self.getPage(videoUrl)
                if not sts:
                    return []

                if 'captcha' in data:
                    data = re.sub("<!--[\s\S]*?-->", "", data)

                if 'google.com/recaptcha/' in data and 'sitekey' in data:
                    message = _('Link protected with google recaptcha v2.')
                    if True != self.loggedIn:
                        message += '\n' + _('Please fill your login and password in the host configuration (available under blue button) and try again.')
                    SetIPTVPlayerLastHostError(message)
                    break
                elif '<input name="captcha"' in data:
                    data = self.cm.ph.getDataBeetwenMarkers(data, '<div align="center">', '</form>')[1]
                    captchaTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h3', '</h3>')[1])
                    captchaDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '</h3>', '</span>')[1])

                    # parse form data
                    data = self.cm.ph.getDataBeetwenMarkers(data, '<form', '</form>')[1]

                    imgUrl = self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"')[0]
                    if imgUrl != '':
                        imgUrl = '/' + imgUrl
                    if imgUrl.startswith('/'):
                        imgUrl = urljoin(videoUrl, imgUrl)

                    printDBG("img URL [%s]" % imgUrl)

                    actionUrl = self.cm.ph.getSearchGroups(data, 'action="([^"]+?)"')[0]
                    if actionUrl != '':
                        actionUrl = '/' + actionUrl
                    if actionUrl.startswith('/'):
                        actionUrl = urljoin(videoUrl, actionUrl)
                    elif actionUrl == '':
                        actionUrl = videoUrl

                    captcha_post_data = dict(re.findall(r'''<input[^>]+?name=["']([^"^']*)["'][^>]+?value=["']([^"^']*)["'][^>]*>''', data))

                    if self.cm.isValidUrl(imgUrl):
                        params = dict(self.defaultParams)
                        params['header'] = dict(params['header'])
                        params['header']['Accept'] = 'image/png,image/*;q=0.8,*/*;q=0.5'
                        params = dict(self.defaultParams)
                        params.update({'maintype': 'image', 'subtypes': ['jpeg', 'png'], 'check_first_bytes': [b'\xFF\xD8', b'\xFF\xD9', b'\x89\x50\x4E\x47'], 'header': params['header']})
                        filePath = GetTmpDir('.iptvplayer_captcha.jpg')
                        ret = self.cm.saveWebFile(filePath, imgUrl.replace('&amp;', '&'), params)
                        if not ret.get('sts'):
                            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
                            return urlTab

                        params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
                        params['accep_label'] = _('Send')
                        params['title'] = captchaTitle
                        params['status_text'] = captchaDesc
                        params['with_accept_button'] = True
                        params['list'] = []
                        item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
                        item['label_size'] = (160, 75)
                        item['input_size'] = (480, 25)
                        item['icon_path'] = filePath
                        item['title'] = _('Answer')
                        item['input']['text'] = ''
                        params['list'].append(item)

                        ret = 0
                        retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
                        printDBG(retArg)
                        if retArg and len(retArg) and retArg[0]:
                            printDBG(retArg[0])
                            captcha_post_data['captcha'] = retArg[0][0]
                            post_data = captcha_post_data
                            url = actionUrl

                        if not sts:
                            return urlTab
                        else:
                            continue

                tmp = re.compile('''<iframe[^>]+?src=['"]([^"^']+?)['"]''', re.IGNORECASE).findall(data)
                for url in tmp:
                    if 1 == self.up.checkHostSupport(url):
                        videoUrl = url
                        break
            break

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('FilmezzEU.getFavouriteData')
        params = {'type': cItem['type'], 'category': cItem.get('category', ''), 'title': cItem['title'], 'url': cItem['url'], 'desc': cItem['desc'], 'icon': cItem['icon']}
        return json.dumps(params)

    def getLinksForFavourite(self, fav_data):
        printDBG('FilmezzEU.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('FilmezzEU.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def getArticleContent(self, cItem):
        printDBG("FilmezzEU.getArticleContent [%s]" % cItem)
        retTab = []

        url = cItem.get('prev_url', '')
        if url == '':
            url = cItem.get('url', '')

        sts, data = self.getPage(url)
        if not sts:
            return retTab

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="text"', '</div>')[1])
        if desc == '':
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta[^>]+?name="description"[^>]+?content="([^"]+?)"')[0])
        titleData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="title"', '</div>')[1]

        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(titleData, '<h1', '</h1>')[1])
        altTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(titleData, '<h2', '</h2>')[1])
        if title != '':
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta[^>]+?name="title"[^>]+?content="([^"]+?)"')[0])
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<link[^>]+?rel="image_src"[^>]+?href="([^"]+?)"')[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            title = cItem['desc']
        if icon == '':
            title = cItem['icon']

        descTabMap = {"Kategória": "genre",
                      "Rendező": "director",
                      "Hossz": "duration"}

        otherInfo = {}
        descData = cItem.get('prev_desc', '')
        if descData == '':
            descData = cItem.get('desc', '')
        descData = descData.split('[/br]')
        for item in descData:
            item = item.split(':')
            key = item[0]
            if key in descTabMap:
                try:
                    otherInfo[descTabMap[key]] = self.cleanHtmlStr(item[-1])
                except Exception:
                    continue

        imdb_rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="score">', '</span>', False)[1])
        if imdb_rating != '':
            otherInfo['imdb_rating'] = imdb_rating

        if altTitle != '':
            otherInfo['alternate_title'] = altTitle
        year = self.cm.ph.getSearchGroups(cItem.get('prev_title', ''), '\(([0-9]{4})\)')[0]
        if year == '':
            year = self.cm.ph.getSearchGroups(cItem['title'], '\(([0-9]{4})\)')[0]
        if year != '':
            otherInfo['year'] = year

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def tryTologin(self):
        printDBG('tryTologin start')

        rm(self.COOKIE_FILE)

        self.login = config.plugins.iptvplayer.filmezzeu_login.value
        self.password = config.plugins.iptvplayer.filmezzeu_password.value

        if '' == self.login.strip() or '' == self.password.strip():
            printDBG('tryTologin wrong login data')
            #self.sessionEx.open(MessageBox, _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.' % self.getMainUrl()), type = MessageBox.TYPE_ERROR, timeout = 10 )
            return False

        url = self.getFullUrl('/bejelentkezes.php')

        post_data = {'logname': self.login, 'logpass': self.password, 'ref': self.getFullUrl('/index.php')}
        httpParams = dict(self.defaultParams)
        httpParams['header'] = dict(httpParams['header'])
        httpParams['header']['Referer'] = url
        sts, data = self.cm.getPage(url, httpParams, post_data)
        if sts and 'kijelentkezes.php' in data:
            printDBG('tryTologin OK')
            return True

        self.sessionEx.open(MessageBox, _('Login failed.'), type=MessageBox.TYPE_ERROR, timeout=10)
        printDBG('tryTologin failed')
        return False

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.filmezzeu_login.value or\
            self.password != config.plugins.iptvplayer.filmezzeu_password.value:
            self.loggedIn = self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.cacheLinks = {}
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
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
        CHostBase.__init__(self, FilmezzEU(), True, [])

    def withArticleContent(self, cItem):
        if (cItem['type'] != 'video' and cItem['category'] != 'explore_item'):
            return False
        return True
