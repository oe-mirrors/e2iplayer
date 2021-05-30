# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
#from Plugins.Extensions.IPTVPlayer.components.recaptcha_v2helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, GetPluginDir, GetCacheSubDir, ReadTextFile, WriteTextFile
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
import base64
import hashlib
from binascii import unhexlify
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.api_key_9kweu = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_2captcha = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.bsto_linkcache = ConfigYesNo(default=True)
config.plugins.iptvplayer.bsto_bypassrecaptcha = ConfigSelection(default="", choices=[("", _("None")),
                                                                                          ("9kw.eu", "https://9kw.eu/"),
                                                                                          ("2captcha.com", "http://2captcha.com/")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use links cache"), config.plugins.iptvplayer.bsto_linkcache))
    optionList.append(getConfigListEntry(_("Captcha solving service"), config.plugins.iptvplayer.bsto_bypassrecaptcha))
    if config.plugins.iptvplayer.bsto_bypassrecaptcha.value == '9kw.eu':
        optionList.append(getConfigListEntry(_("%s API KEY") % '    ', config.plugins.iptvplayer.api_key_9kweu))
    elif config.plugins.iptvplayer.bsto_bypassrecaptcha.value == '2captcha.com':
        optionList.append(getConfigListEntry(_("%s API KEY") % '    ', config.plugins.iptvplayer.api_key_2captcha))
    return optionList
###################################################


def gettytul():
    return 'https://bs.to/'


class BSTO(CBaseHostClass, CaptchaHelper):
    LINKS_CACHE = {}

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'bs.to', 'cookie': 'bsto.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.DEFAULT_ICON_URL = 'https://bs.to/opengraph.jpg'
        self.MAIN_URL = None
        self.cacheSeries = []
        self.cacheGenres = {}
        self.cacheLinks = {}
        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._getHeaders = None

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        return CBaseHostClass.getFullIconUrl(self, url)

    def selectDomain(self):
        self.MAIN_URL = 'https://bs.to/'
        self.MAIN_CAT_TAB = [{'category': 'list_genres', 'title': _('Genres'), 'url': self.getFullUrl('/serie-genre')},
                             {'category': 'list_genres', 'title': _('Alphabet'), 'url': self.getFullUrl('/serie-alphabet')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def listGenres(self, cItem, nextCategory):
        printDBG("BSTO.listGenres")
        self.cacheGenres = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="genre">', '</ul>', False)
        for genreItem in data:
            genreTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(genreItem, '<strong>', '</strong>', False)[1])
            genreItem = self.cm.ph.getAllItemsBeetwenMarkers(genreItem, '<li>', '</li>', False)
            self.cacheGenres[genreTitle] = []
            for item in genreItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                if title == '':
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                self.cacheGenres[genreTitle].append({'title': title, 'url': url})
            params = dict(cItem)
            params.update({'title': genreTitle, 'category': nextCategory})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("BSTO.listItems")
        tab = self.cacheGenres.get(cItem['title'], [])
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav': True, 'category': nextCategory, 'icon': item['url'] + '?fake=need_resolve.jpeg'})
            self.addDir(params)

    def listSeasons(self, cItem, nextCategory):
        printDBG("BSTO.listSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        descData = self.cm.ph.getDataBeetwenMarkers(data, '<div id="sp_left">', '<script', False)[1]
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descData, '<p', '</p>')[1])

        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(descData, '''src=['"]([^'^"]+?)['"]''')[0])
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="seasons">', '</ul>')[1]

        seasonLabel = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<strong>', '</strong>', False)[1])
        printDBG(seasonLabel)

        items = ph.findall(data, ('<li', '>'), '</li>')

        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': '%s %s' % (seasonLabel, title), 's_num': title, 'series_title': cItem['title'], 'url': url, 'icon': icon, 'desc': desc})
            printDBG(str(params))
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("BSTO.listEpisodes")
        self.cacheLinks = {}
        sNum = cItem['s_num']

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<table class="episodes">', '</table>')[1]
        items = ph.findall(data, ('<tr', '>'), '</tr>')

        for item in items:
            item = ph.findall(item, ('<td', '>'), '</td>')
            if len(item) < 3:
                continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item[0], '''href=['"]([^'^"]+?)['"]''')[0])
            eNum = self.cleanHtmlStr(item[0])

            title1 = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item[1], '<strong>', '</strong>', False)[1])
            title2 = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item[1], '<i>', '</i>', False)[1])

            key = 's%se%s' % (sNum.zfill(2), eNum.zfill(2))
            self.cacheLinks[key] = []
            title = cItem['series_title'] + ', ' + key + ' ' + title1
            if title2 != '':
                title += ' (%s)' % title2

            item = self.cm.ph.getAllItemsBeetwenMarkers(item[2], '<a', '</a>')
            for link in item:
                name = self.cleanHtmlStr(link)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(link, '''href=['"]([^'^"]+?)['"]''')[0])
                if name == '':
                    name = url.rsplit('/', 1)[-1]
                self.cacheLinks[key].append({'name': name, 'url': strwithmeta(url, {'links_key': key}), 'need_resolve': 1})
            if len(self.cacheLinks[key]):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': title, 'url': url, 'links_key': key})
                printDBG("--->" + str(params))
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("BSTO.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        if len(self.cacheSeries) == 0:
            url = self.getFullUrl('andere-serien')
            sts, data = self.getPage(url)
            if not sts:
                return []
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="seriesContainer"', '<script', False)[1]

            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>', '</li>', False)
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                if title == '':
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                self.cacheSeries.append({'title': title, 'url': url})

        searchResults = []
        words = ' '.join(searchPattern.lower().split())
        words = words.split(' ')
        for idx in range(len(self.cacheSeries)):
            title = self.cacheSeries[idx]['title'].lower()
            score = 0
            for word in words:
                if word in title:
                    score += 1
            if score > 0:
                searchResults.append({'idx': idx, 'score': score})

        searchResults.sort(key=lambda k: k['score'], reverse=True)
        for item in searchResults:
            item = self.cacheSeries[item['idx']]
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav': True, 'category': 'list_seasons', 'icon': item['url'] + '?fake=need_resolve.jpeg'})
            self.addDir(params)

    def getLinksForVideo(self, cItem, forEpisodes=False):
        printDBG("BSTO.getLinksForVideo [%s]" % cItem)
        key = cItem.get('links_key', '')
        return self.cacheLinks.get(key, [])

    def _cryptoJS_AES_decrypt(self, encrypted, password):
        def derive_key_and_iv(password, key_length, iv_length):
            d = d_i = ''
            while len(d) < key_length + iv_length:
                d_i = hashlib.md5(d_i + password).digest()
                d += d_i
            return d[:key_length], d[key_length:key_length + iv_length]
        bs = 16
        key, iv = derive_key_and_iv(password, 32, 16)
        cipher = AES_CBC(key=key, keySize=32)
        return cipher.decrypt(encrypted, iv)

    def getHeaders(self, url):
        headers = {}
        if self._getHeaders == None:
            try:
                import hmac
                tmp = '89aac45129123590486772c958b0efc9074993ad1ffddc7fecfec3755806ca1d51a76813a3fbf891ee09081e10ea4f74681823b1443295b8b4ee2f14d8f209194fe5db528cbbf29117101f346dc7b4dd1474dff6face052de50948157720f1fd9d162c4068f329ca732336edd335ae93e29d3515f32b9c1963255b979da52f52bede1bfa1f505581bd8a92a4d43ce162ebe4efe19303d3a3b141305610bfe8257fa70af3c548003c3b5a216e2e5204566e2bf8fb2471468c016a74fcdbaa3926ad203810d120c5997014717abb01e7036bea34a336384d25bd3d7807d7f4e8efe3ee2393044dddca3b6e48d364b61135e1b71582b81578d394946c18f2a8e2c40a07c6ecd6bcce821876bfd0ca302aa33aef190ad5bcd2dd11caf38c7bf651d4dc96d34abd5781744a75a09cebb88933bbee4ab9d753f746e7da84e0fadf1cffe902ec710f91ba973d6b333eb52680f0497571ba1e6f20946f05956f73b901e482ba8cf7c74c6359608ab00f6aade9a203aa038e4d64a6036417063b2b11e4101bb9305699f0704a0378836fae0b1f5709c2cc79ff57aaa9f4da32c5827c5cbfedcc3ee9e82a23384c0c623e22e05935f236bbc374a304347414083c4ca10d19ec7a9d1ce5c2d9b9d37145df37d61c623a0930b991eea514a0565dac2226022a0cda6d6e77e41b5da5ad3a809f8d4fc31061b7fa040189f24f1c4fea3e908020335174e2dd66e59d2a6cd60e1781dafcfb770dcd77c605613795d6b7a9625f02bfed25661350f77cb54250c01cbf1a5707c394b10efeea54bb075d6cbb0f10e93c9744674c7f107ea892d947a2c57214ec6a68004508d5be2c203cabbd4fe247fcdabd5aaf816270b6b6c43fbe10d4e5f1ad1579ab25dcb9460672aa43fca504403f3e2d3422f7d8fec33439c73bd4336320e3cdb14dee681fb17313e36ee3792769ce192cb688f5a00bee4fc566eb859172b7993b70ce1222a55c9e94d5bae32de1525c8bbb86b54fa27215fa0d21f8'
                tmp = self._cryptoJS_AES_decrypt(unhexlify(tmp), ''.join(GetPluginDir().split('/')[-5:]))
                tmp = base64.b64decode(tmp.split('\r')[-1]).replace('\r', '')
                _getHeaders = compile(tmp, '', 'exec')
                vGlobals = {"__builtins__": None, 'len': len, 'list': list, 'dict': dict, 'time': time, 'base64': base64, 'hashlib': hashlib, 'hmac': hmac, 'json': json, 'int': int, 'str': str}
                vLocals = {'_getHeaders': ''}
                exec _getHeaders in vGlobals, vLocals
                self._getHeaders = vLocals['_getHeaders']
            except Exception:
                printExc()
        if self._getHeaders != None:
            try:
                headers = self._getHeaders(url)
            except Exception:
                printExc()
        return headers

    def getVideoLinks(self, videoUrl):
        printDBG("BSTO.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        key = strwithmeta(videoUrl).meta.get('links_key', '')
        if key in self.cacheLinks:
            for idx in range(len(self.cacheLinks[key])):
                if self.cacheLinks[key][idx]['url'] == videoUrl and not self.cacheLinks[key][idx]['name'].startswith('*'):
                    self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        sts, data = self.getPage(videoUrl)
        if not sts:
            return []

        #printDBG("---------------------------")
        #printDBG(data)
        #printDBG("---------------------------")

        errorMsgTab = []

        # LID
        #<div class="hoster-player" data-lid="4778534">
        # token
        #<meta name="security_token" content="edfafd7a9fa9a7d005f88c96" />
        # ticket <- token from recaptcha
        # recaptcha sitekey
        #series.init (1, 1, '6LeiZSYUAAAAAI3JZXrRnrsBzAdrZ40PmD57v_fs')

        lid = self.cm.ph.getSearchGroups(data, "data-lid=['\"]([^'^\"]+?)['\"]")[0]
        printDBG("Data LID : %s " % lid)

        token = self.cm.ph.getSearchGroups(data, "<meta.*security_token.*content=\"(.*?)\"")[0]
        printDBG("Security token : %s " % token)

        if not lid or not token:
            return []

        sitekey = self.cm.ph.getSearchGroups(data, "'([0-9a-zA-Z_]{38,}?)'\)")[0]

        if sitekey != '':
            ticket, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta['url'], bypassCaptchaService=config.plugins.iptvplayer.bsto_bypassrecaptcha.value)
            if not ticket:
                SetIPTVPlayerLastHostError(errorMsgTab)
                return []

        printDBG("ticket: %s" % ticket)

        # post data
        postData = {'token': token, 'LID': lid, 'ticket': ticket}
        ajaxUrl = self.MAIN_URL + "ajax/embed.php"
        ajaxParams = self.defaultParams
        ajaxParams['header'] = self.AJAX_HEADER
        ajaxParams['header']['Referer'] = videoUrl

        sts, ajaxData = self.cm.getPage(ajaxUrl, ajaxParams, post_data=postData)
        if not sts:
            return []

        printDBG("----------- ajax data ----------")
        printDBG(ajaxData)
        printDBG("--------------------------------")
        # {"success":true,"link":"https:\/\/vivo.sx\/2eaf981402","embed":"0"}

        jsonData = json_loads(ajaxData)

        hostUrl = jsonData.get('link', '')

        if hostUrl:
            if 1 != self.up.checkHostSupport(hostUrl):
                SetIPTVPlayerLastHostError('\n'.join(errorMsgTab))
            elif self.cm.isValidUrl(hostUrl):
                BSTO.LINKS_CACHE[lid] = hostUrl
                if config.plugins.iptvplayer.bsto_linkcache.value:
                    WriteTextFile(GetCacheSubDir('bs.to', lid), hostUrl)
                urlTab = self.up.getVideoLinkExt(hostUrl)

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("SeriesOnlineIO.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.getPage(cItem.get('url', ''))
        if not sts:
            return retTab

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="justify" id="desc_spoiler">', '</div>')[1])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="sp_left">', '<script', False)[1]
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h2', '</h2>')[1].split('<small>')[0])
        if desc == '':
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p ', '</p>')[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''src=['"]([^'^"]+?)['"]''')[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', '')

        data = data.split('<div class="infos">')[-1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<span>', '</p>')
        printDBG(data)
        descTabMap = {"Genres": "genre",
                      "Produktionsjahre": "year",
                      "Hauptdarsteller": "actors",
                      "Regisseure": "director",
                      "Produzenten": "production",
                      "Autoren": "writer"}
        otherInfo = {}
        for item in data:
            key = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span', '</span>')[1])
            tmp = self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1]
            val = self.cleanHtmlStr(' '.join(self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>')))
            if val == '':
                val = self.cleanHtmlStr(tmp)

            if key in descTabMap:
                try:
                    otherInfo[descTabMap[key]] = val
                except Exception:
                    continue

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullIconUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            #rm(self.COOKIE_FILE)
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_genres':
            self.listGenres(self.currItem, 'list_items')
        if category == 'list_items':
            self.listItems(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, BSTO(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video' and cItem['category'] != 'list_episodes' and cItem['category'] != 'list_seasons':
            return False
        return True
