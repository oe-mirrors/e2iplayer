# Embedded file name: /IPTVPlayer/hosts/hostseriesblanco.py
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, CSelOneLink, MergeDicts, GetCookieDir, GetTmpDir, WriteTextFile, ReadTextFile, rm
from Plugins.Extensions.IPTVPlayer.components.recaptcha_v2helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
import urllib
import re
import base64
from binascii import hexlify
from hashlib import md5
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
config.plugins.iptvplayer.seriesblanco_login = ConfigText(default='', fixed_size=False)
config.plugins.iptvplayer.seriesblanco_password = ConfigText(default='', fixed_size=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_('login') + ':', config.plugins.iptvplayer.seriesblanco_login))
    optionList.append(getConfigListEntry(_('password') + ':', config.plugins.iptvplayer.seriesblanco_password))
    return optionList


def gettytul():
    return 'https://seriesblanco.org/'


class SuggestionsProvider():
    MAIN_URL = 'https://seriesblanco.org/'

    def __init__(self):
        self.cm = common()
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultHeader(browser='chrome')['User-Agent'],
         'X-Requested-With': 'XMLHttpRequest'}
        self.defaultParams = {'header': self.HTTP_HEADER}
        self.reObj = re.compile('<span>([^<]+?)<')

    def getName(self):
        return _('Suggestions')

    def getSuggestions(self, text, locale):
        url = self.MAIN_URL + 'wp-admin/admin-ajax.php'
        sts, data = self.cm.getPage(url, self.defaultParams, {'action': 'melyric_ajax_search',
         'term': text})
        if sts:
            retList = []
            for item in self.reObj.findall(data):
                retList.append(ph.clean_html(item))

            return retList
        else:
            return None


class SeriesBlanco(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'seriesblanco.org',
         'cookie': 'seriesblanco.org.cookie'})
        self.MAIN_URL = SuggestionsProvider.MAIN_URL
        self.DEFAULT_ICON_URL = 'http://elrinconenigma2.hol.es/E2iplayericons/logoseriesblanco.png'
        self.HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader(browser='chrome'), {'Referer': self.getMainUrl(),
         'Origin': self.getMainUrl()})
        self.AJAX_HEADER = MergeDicts(self.HTTP_HEADER, {'X-Requested-With': 'XMLHttpRequest',
         'Accept': '*/*'})
        self.defaultParams = {'use_cookie': True,
         'load_cookie': True,
         'save_cookie': True,
         'cookiefile': self.COOKIE_FILE}
        self.cacheFiltersKeys = []
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.loggedIn = None
        self.login = ''
        self.password = ''
        self.inLogin = False
        return

    def getDefaultParams(self, forAjax = False):
        header = self.AJAX_HEADER if forAjax else self.HTTP_HEADER
        return MergeDicts(self.defaultParams, {'header': header})

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE,
         'User-Agent': self.HTTP_HEADER['User-Agent']}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMain(self, cItem, nextCategory1, nextCategory2):
        printDBG('SeriesBlanco.listMain')
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        data = ph.find(data, ('<ul', '>', 'sidebar-nav'), '</div>', flags=0)[1]
        item = ph.find(data, ('<a', '>'), '</a>')[1]
        url = self.getFullUrl(ph.search(item, ph.A)[1])
        title = ph.clean_html(item)
        if url:
            self.addDir(MergeDicts(cItem, {'category': nextCategory1,
             'title': title,
             'url': url}))
        item = ph.find(data, ('<a', '>', 'subnav-toggle'), '</ul>')[1]
        sTitle = ph.clean_html(ph.find(item, ('<a', '>'), '</a>', flags=0)[1])
        subItems = []
        item = ph.findall(item, ('<li', '>'), '</li>', flags=0)
        for it in item:
            title = ph.clean_html(it)
            url = self.getFullUrl(ph.search(it, ph.A)[1])
            subItems.append(MergeDicts(cItem, {'category': nextCategory2,
             'title': title,
             'url': url}))

        if subItems:
            self.addDir(MergeDicts(cItem, {'category': 'sub_items',
             'title': sTitle,
             'sub_items': subItems}))
        item = ph.find(data, ('<a', '>', 'ultimas-series-anadidas'), '</a>')[1]
        url = self.getFullUrl(ph.search(item, ph.A)[1])
        title = ph.clean_html(item)
        if url:
            self.addDir(MergeDicts(cItem, {'category': nextCategory2,
             'title': title,
             'url': url}))
        MAIN_CAT_TAB = [{'category': 'search',
          'title': _('Search'),
          'search_item': True}, {'category': 'search_history',
          'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listABC(self, cItem, nextCategory):
        printDBG('SeriesBlanco.listABC')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)
        self.addDir(MergeDicts(cItem, {'category': nextCategory,
         'url': cUrl,
         'title': _('--All--')}))
        data = ph.find(data, ('<div', '>', 'groupe-links'), '</div>')[1]
        data = ph.findall(data, ('<a', '>'), '</a>', flags=ph.START_S)
        for idx in range(1, len(data), 2):
            url = self.getFullUrl(ph.getattr(data[idx - 1], 'href'))
            title = ph.clean_html(data[idx])
            self.addDir(MergeDicts(cItem, {'category': nextCategory,
             'url': url,
             'title': title}))

    def listItems(self, cItem, nextCategory):
        printDBG('SeriesBlanco.listMoviesItems %s' % cItem)
        page = cItem.get('page', 1)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)
        nextPage = ph.find(data, ('<ul', '>', 'pagination'), '</ul>', flags=0)[1]
        nextPage = ph.rfind(nextPage, '>%s</a>' % (page + 1), '<a')[1]
        nextPage = self.getFullUrl(ph.getattr(nextPage, 'href'), cUrl)
        data = ph.find(data, ('<div', '>', 'panel-body'), '</ul>', flags=0)[1]
        data = ph.findall(data.rsplit('pagination-wrap', 1)[0], ('<li', '>'), '</li>', flags=0)
        for item in data:
            icon = ph.find(item, '<img', '>')[1]
            url = self.getFullUrl(ph.search(item, ph.A)[1], cUrl)
            title = ph.clean_html(ph.find(item, ('<p', '>'), '</p>', flags=0)[1])
            if not title:
                title = ph.clean_html(ph.getattr(icon, 'title'))
            if not title:
                title = ph.clean_html(ph.getattr(icon, 'alt'))
            icon = self.getFullIconUrl(ph.search(icon, ph.IMG)[1], cUrl)
            self.addDir({'good_for_fav': True,
             'category': nextCategory,
             'title': title,
             'url': url,
             'icon': icon})

        if nextPage:
            self.addDir(MergeDicts(cItem, {'title': _('Next page'),
             'url': nextPage,
             'page': page + 1}))

    def exploreItem(self, cItem):
        printDBG('SeriesBlanco.exploreItem')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)
        sDesc = []
        descObj = self.getArticleContent(cItem, data)[0]
        for item in descObj['other_info']['custom_items_list']:
            sDesc.append(item[1])

        sDesc = ' | '.join(sDesc) + '[/br]' + descObj['text']
        tmp = ph.find(data, ('<div', '>', 'trailer'), '</div>', flags=0)[1]
        url = self.getFullUrl(ph.search(tmp, ph.IFRAME)[1])
        title = ph.clean_html(tmp)
        if not title:
            title = _('Trailer')
        if url:
            self.addVideo(MergeDicts(cItem, {'good_for_fav': True,
             'url': url,
             'title': '%s (%s)' % (cItem['title'], title),
             'desc': sDesc,
             'prev_url': cItem['url']}))
        data = ph.findall(data, ('<span', '>', 'seasonNumber'), '</table>')
        for sItem in data:
            sTitle = ph.clean_html(sItem.split('</span>', 1)[0]).split(' Online ', 1)[0]
            sItem = ph.findall(sItem, ('<tr', '>'), '</tr>', flags=0)
            subItems = []
            for item in sItem:
                url = self.getFullUrl(ph.search(item, ph.A)[1])
                if not url:
                    continue
                title = ph.clean_html(item)
                tmp = ph.IMG.findall(item)
                desc = []
                for t in tmp:
                    t = t[1].rsplit('/', 1)[-1].split('.', 1)[0]
                    if t:
                        desc.append(t)

                subItems.append({'type': 'video',
                 'good_for_fav': True,
                 'title': '%s: %s' % (cItem['title'], title),
                 'url': url,
                 'icon': cItem.get('icon', ''),
                 'desc': ' | '.join(desc)})

            if subItems:
                self.addDir({'type': 'category',
                 'good_for_fav': False,
                 'title': sTitle,
                 'category': 'sub_items',
                 'sub_items': subItems,
                 'icon': cItem['icon'],
                 'desc': sDesc,
                 'prev_url': cItem['url']})

    def listSearch(self, cItem, searchPattern, searchType):
        self.tryTologin()
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)
        url = self.getFullUrl('?s=%s&post_type=ficha' % urllib.quote_plus(searchPattern))
        cItem = {'type': 'category',
         'name': 'category',
         'category': 'list_items',
         'title': '',
         'url': url}
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG('SeriesBlanco.getLinksForVideo [%s]' % cItem)
        self.tryTologin()
        if 1 == self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])
        urlsTab = []
        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab
        self.cacheLinks = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return urlsTab
        cUrl = self.cm.meta['url']
        url = self.getFullUrl(ph.search(data, ph.IFRAME)[1])
        if url:
            urlsTab.append({'url': strwithmeta(url, {'Referer': cUrl}),
             'name': self.cm.getBaseUrl(url, True),
             'need_resolve': 1})
        data = ph.findall(data, ('<tbody', '>'), '</tbody>', flags=0)
        for tItem in data:
            tItem = ph.findall(tItem, ('<tr', '>'), '</tr>', flags=0)
            for item in tItem:
                tmp = ph.findall(item, ('<td', '>'), '</td>', flags=0)
                if len(tmp) < 4:
                    printDBG('Wrong link item: %s -> ' % (item, tmp))
                    continue
                url = self.getFullUrl(ph.getattr(item, 'data-enlace'), cUrl)
                if not url:
                    continue
                name = ph.clean_html(tmp[0] + tmp[2] + tmp[3])
                tmp = ph.IMG.findall(tmp[1])
                lang = []
                for t in tmp:
                    t = t[1].rsplit('/', 1)[-1].split('.', 1)[0]
                    if t:
                        lang.append(t)

                name = '[%s] %s' % (' | '.join(lang), name)
                urlsTab.append({'url': strwithmeta(url, {'Referer': cUrl}),
                 'name': name,
                 'need_resolve': 1})

        if len(urlsTab):
            self.cacheLinks[cacheKey] = urlsTab
        return urlsTab

    def getVideoLinks(self, videoUrl):
        printDBG('SeriesBlanco.getVideoLinks [%s]' % videoUrl)
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem, data = None):
        printDBG('SeriesBlanco.getArticleContent [%s]' % cItem)
        self.tryTologin()
        retTab = []
        itemsList = []
        if not data:
            url = cItem.get('prev_url', cItem['url'])
            sts, data = self.getPage(url)
            if not sts:
                return []
            self.setMainUrl(self.cm.meta['url'])
            data = re.sub('<!--[\\s\\S]*?-->', '', data)
        title = ph.clean_html(ph.find(data, ('<div', '>', 'name-desg'), '</div>', flags=0)[1])
        data = ph.find(data, ('<ul', '>', 'primary-tabs'), ('<div', '>', 'panel-primar'), flags=0)[1]
        icon = self.getFullIconUrl(ph.search(data, ph.IMG)[1])
        desc = ph.clean_html(ph.find(data, ('<div', '>', 'profile'), '</div>', flags=0)[1])
        data = ph.findall(data, ('<b', '>'), ('<', '>', 'br'), flags=0)
        for item in data:
            item = item.split('</b>', 1)
            if len(item) == 2:
                label = ph.clean_html(item[0])
                value = ph.clean_html(item[-1])
                if label and value:
                    itemsList.append((label, value))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')
        return [{'title': ph.clean_html(title),
          'text': ph.clean_html(desc),
          'images': [{'title': '',
                      'url': self.getFullUrl(icon)}],
          'other_info': {'custom_items_list': itemsList}}]

    def tryTologin(self):
        printDBG('tryTologin start')
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.seriesblanco_login.value or self.password != config.plugins.iptvplayer.seriesblanco_password.value:
            self.cm.clearCookie(self.COOKIE_FILE, removeNames=['language'])
            loginCookie = GetCookieDir('seriesblanco.org.login')
            self.login = config.plugins.iptvplayer.seriesblanco_login.value
            self.password = config.plugins.iptvplayer.seriesblanco_password.value
            sts, data = self.getPage(self.getMainUrl())
            if sts:
                self.setMainUrl(self.cm.meta['url'])
            freshSession = False
            if sts and '/login' not in data:
                printDBG('Check hash')
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                prevHash = ReadTextFile(loginCookie)[1].strip()
                printDBG('$hash[%s] $prevHash[%s]' % (hash, prevHash))
                if hash == prevHash:
                    self.loggedIn = True
                    return True
                freshSession = True
            loginUrl = self.getFullUrl('/login/')
            rm(loginCookie)
            rm(self.COOKIE_FILE)
            if freshSession:
                sts, data = self.getPage(loginUrl, MergeDicts(self.defaultParams, {'use_new_session': True}))
            else:
                sts, data = self.getPage(loginUrl, self.defaultParams)
            self.loggedIn = False
            if '' == self.login.strip() or '' == self.password.strip():
                return False
            errorTab = [_('Problem with user "%s" login.') % self.login]
            loginUrl = self.getFullUrl('/wp-content/themes/ficseriesb/include/login_register/sistemaLogin.php')
            sts, data = self.getPage(loginUrl, self.getDefaultParams(forAjax=True), {'usernameya': self.login,
             'pwd1': self.password})
            if sts:
                try:
                    printDBG(data)
                    data = json_loads(data)
                    errorTab.append(ph.clean_html(str(data.get('mensaje', ''))))
                    if data.get('err', False):
                        sts, data = self.getPage(self.getFullUrl('/profil'))
                        if sts and '/login' not in data:
                            self.loggedIn = True
                except Exception:
                    printExc()

            if not self.loggedIn:
                self.sessionEx.open(MessageBox, '\n'.join(errorTab), type=MessageBox.TYPE_INFO, timeout=10)
            if self.loggedIn:
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                WriteTextFile(loginCookie, hash)
        return self.loggedIn

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        self.tryTologin()
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        category = self.currItem.get('category', '')
        printDBG('handleService: || category[%s] ' % category)
        self.currList = []
        if not category:
            self.listMain({'type': 'category',
             'name': 'category'}, 'abc', 'list_items')
        elif category == 'abc':
            self.listABC(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'search':
            self.listSearch(self.currItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history',
             'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)

    def getSuggestionsProvider(self, index):
        printDBG('FilmanCC.getSuggestionsProvider')
        return SuggestionsProvider()


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, SeriesBlanco(), True, [])

    def withArticleContent(self, cItem):
        return 'explore_item' == cItem.get('category') or cItem.get('prev_url')