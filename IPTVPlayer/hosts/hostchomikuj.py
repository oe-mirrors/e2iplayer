# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, formatBytes, byteify
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigText, getConfigListEntry
import urllib
from hashlib import md5
try:
    import simplejson as json
except Exception:
    import json


###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.Chomikuj_folder = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.Chomikuj_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.Chomikuj_login = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []

    optionList.append(getConfigListEntry("Folder startu", config.plugins.iptvplayer.Chomikuj_folder))
    optionList.append(getConfigListEntry("Nazwa chomika (login)", config.plugins.iptvplayer.Chomikuj_login))
    optionList.append(getConfigListEntry("Hasło do chomika", config.plugins.iptvplayer.Chomikuj_password))

    return optionList
###################################################


def gettytul():
    return 'http://chomikuj.pl/'


class Chomikuj(CBaseHostClass):

    def __init__(self):
        printDBG("Chomikuj.__init__")
        CBaseHostClass.__init__(self, {'history': 'Chomikuj'})
        self.DEFAULT_ICON_URL = 'https://superrepo.org/static/images/icons/original/plugin.audio.polish.CAP.png.pagespeed.ce.m3al56qs_A.png'
        self.MAINURL = 'http://mobile.chomikuj.pl/'
        self.LIST_FOLDER_URL = 'api/v3/folders?Parent=%s&Page=%s'
        self.LIST_FOREIGN_FOLDER_URL = 'api/v3/folders?AccountId=%s&Parent=%s&page=%s'

        self.FILE_REQUEST_URL = 'api/v3/files/download?fileId='
        self.SEARCH_URL = 'api/v3/files/search?Query=%s&PageNumber=%s&SizeMin=0&MediaType=%s'
        self.SEARCH_ACCOUNT_URL = 'api/v3/account/search?PageNumber=%s&Query=%s'
        self.HTTP_JSON_HEADER = {'User-Agent': "android/2.1.01 (a675e974-0def-4cbc-a955-ac6c6f99707b; unknown androVM for VirtualBox ('Tablet' version with phone caps))",
                                   'Content-Type': "application/json; charset=utf-8",
                                   'Accept-Encoding': 'gzip'
                                  }
        self.loginData = {}

    def _getJItemStr(self, item, key, default=''):
        try:
            v = item.get(key, None)
        except Exception:
            v = None
        if None == v:
            return default
        return clean_html(u'%s' % v).encode('utf-8')

    def _getJItemNum(self, item, key, default=0):
        try:
            v = item.get(key, None)
        except Exception:
            v = None
        if None != v:
            try:
                NumberTypes = (int, long, float, complex)
            except NameError:
                NumberTypes = (int, long, float)

            if isinstance(v, NumberTypes):
                return v
        return default

    def requestJsonData(self, url, postData=None, addToken=True):
        addParams = {'header': dict(self.HTTP_JSON_HEADER)}
        if None != postData:
            addParams['raw_post_data'] = True
            data = postData
        else:
            data = ''
        if addToken:
            token = "wzrwYua$.DSe8suk!`'2"
            token = md5(url + data + token).hexdigest()
            addParams['header']['Token'] = token
        if 'ApiKey' in self.loginData:
            addParams['header']['Api-Key'] = self.loginData['ApiKey']

        sts, data = self.cm.getPage(self.MAINURL + url, addParams, postData)
        #printDBG("=================================================")
        #printDBG(data)
        #printDBG("=================================================")
        if sts:
            try:
                data = json.loads(data)
            except Exception:
                printExc()
                sts = False
                data = {}
        else:
            data = {}
        return sts, data

    def listsMainMenu(self):
        printDBG("Chomikuj.listsMainMenu")
        data = self.loginData['AccountBalance']
        quota = formatBytes(1024 * (self._getJItemNum(data, 'QuotaAdditional', 0) + self._getJItemNum(data, 'QuotaLeft', 0)))
        account = self._getJItemStr(self.loginData, 'AccountName', '')
        title = 'Chomik "%s" (%s transferu)' % (account, quota)
        self.addDir({'name': 'category', 'title': title, 'category': 'account'})
        self.addDir({'name': 'category', 'title': 'Wyszukaj', 'category': 'search', 'search_item': True})
        self.addDir({'name': 'category', 'title': 'Historia wyszukiwania', 'category': 'search_history'})

    def requestLoginData(self):
        url = "api/v3/account/login"
        login = config.plugins.iptvplayer.Chomikuj_login.value
        password = config.plugins.iptvplayer.Chomikuj_password.value
        loginData = '{"AccountName":"%s","RefreshToken":"","Password":"%s"}' % (login, password)

        sts = False
        if '' == login or '' == password:
            self.sessionEx.open(MessageBox, 'Wprowadź dane do swojego konta Chomikuj.pl (Niebieski klawisz).', type=MessageBox.TYPE_INFO, timeout=10)
        else:
            sts, data = self.requestJsonData(url, loginData)
            if sts and 0 == self._getJItemNum(data, 'Code', -1):
                self.loginData = data
            else:
                sts = False
            if not sts:
                errorMessage = 'Problem z zalogowaniem użytkownika "%s".\n' % login
                if 404 == self._getJItemNum(data, 'Code', 0):
                    errorMessage += 'Konto nie istnieje.'
                elif 401 == self._getJItemNum(data, 'Code', 0):
                    errorMessage += 'Błędne hasło.'
                else:
                    errorMessage += 'Code="%d", message="%s".' % (self._getJItemNum(data, 'Code', 0), self._getJItemStr(data, 'Message', ''))
                self.sessionEx.open(MessageBox, errorMessage, type=MessageBox.TYPE_INFO, timeout=10)
        return sts

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Chomikuj.listSearchResult cItem[%s], searchPattern[%s], searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get('page', 1)

        if 'accounts' == searchType:
            url = self.SEARCH_ACCOUNT_URL % (page, urllib.quote_plus(searchPattern))
            sts, data = self.requestJsonData(url)
            if not sts:
                return
            printDBG(data)
            # list accounts
            for item in data.get('Results', []):
                params = dict(cItem)
                title = self._getJItemStr(item, 'AccountName', '')
                desc = 'Plików: %s' % self._getJItemNum(item, 'TotalFilesCount', -1)
                params.update({'category': 'foreign_folder',
                               'parent': 0,
                               'owner': self._getJItemNum(item, 'AccountId', -1),
                               'title': title,
                               'desc': desc,
                               'page': 1})
                self.addDir(params)

            if data.get('IsNextPageAvailable', False):
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': 'Następna strona', 'page': cItem.get('page', 1) + 1})
                self.addDir(params)
        else:
            map = {"images": "Image", "video": "Video", "music": "Music"}
            self.handleDataRequest(cItem, self.SEARCH_URL % (urllib.quote_plus(searchPattern), page, map[searchType]))

    def handleProfile(self, cItem):
        printDBG("Chomikuj.handleProfile cItem[%s]" % cItem)
        parent = cItem.get('parent', 0)
        page = cItem.get('page', 1)
        self.handleDataRequest(cItem, self.LIST_FOLDER_URL % (parent, page))

    def handleForeignFolder(self, cItem):
        printDBG("Chomikuj.handleForeignFolder cItem[%s]" % cItem)
        owner = cItem['owner']
        parent = cItem['parent']
        page = cItem.get('page', 1)
        self.handleDataRequest(cItem, self.LIST_FOREIGN_FOLDER_URL % (owner, parent, page))

    def handleDataRequest(self, cItem, url):
        sts, data = self.requestJsonData(url)
        if sts:
            printDBG(byteify(data))
            if 0 == self._getJItemNum(data, 'Code', -1):
                # Parent Folder
                if 'ParentId' in data and 'ParentName' in data and len(self._getJItemStr(data, 'ParentName')) and 'Owner' in data and 'Id' in data['Owner']:
                    if cItem.get('prev_parent', None) != self._getJItemNum(data, 'ParentId'):
                        params = dict(cItem)
                        params.update({'good_for_fav': True, 'category': 'foreign_folder', 'title': '\xe2\x86\x91 ' + self._getJItemStr(data, 'ParentName'), 'prev_parent': cItem.get('parent', None), 'parent': self._getJItemNum(data, 'ParentId'), 'owner': self._getJItemNum(data['Owner'], 'Id')})
                        self.addDir(params)

                # list folders
                for item in data.get('Folders', []):
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'title': self._getJItemStr(item, 'Name', ''), 'page': 1, 'prev_parent': cItem.get('parent', None), 'parent': self._getJItemNum(item, 'Id', 0)})
                    self.addDir(params)

                # list files
                if 'Files' in data:
                    key = 'Files'
                else:
                    key = 'Results'
                for item in data.get(key, []):
                    params = dict(cItem)
                    title = self._getJItemStr(item, 'FileName', '')
                    size = formatBytes(1024 * self._getJItemNum(item, 'Size', 0))
                    desc = '%s, %s, %s' % (size, self._getJItemStr(item, 'MediaType', ''), self._getJItemStr(item, 'FileType', ''))
                    if item.get('IsFileFreeForUser', False):
                        desc = 'Darmowy[/br]' + desc
                    params.update({'title': title,
                                   'file_id': self._getJItemNum(item, 'FileId', -1),
                                   'icon': self._getJItemStr(item, 'SmallThumbnailImg', ''),
                                   'desc': desc,
                                   'size': size,
                                   'is_free': item.get('IsFileFreeForUser', False),
                                   'page': 1})

                    if 'FolderId' in item and 'Owner' in item and 'Id' in item['Owner'] and 'Name' in item['Owner']:
                        params.update({'category': 'explore_item', 'raw_item': dict(item)})
                        self.addDir(params)
                    else:
                        self._addItem(item, params)

                if data.get('IsNextPageAvailable', False):
                    params = dict(cItem)
                    params.update({'title': 'Następna strona', 'page': cItem.get('page', 1) + 1})
                    self.addDir(params)

    def _addItem(self, item, params):
        printDBG("Chomikuj._addItem")
        params.pop('category', None)
        params.pop('raw_item', None)

        mediaType = self._getJItemStr(item, 'MediaType', '')
        if mediaType in ['Music', 'Video']:
            params.update({'url': self._getJItemStr(item, 'StreamingUrl', '')})
            if mediaType == 'Video':
                self.addVideo(params)
            else:
                self.addAudio(params)
        elif 'Image' == mediaType:
            params.update({'url': self._getJItemStr(item, 'ThumbnailImg', '')})
            self.addPicture(params)
        else:
            printDBG('Chomikuj list file: unknown mediaType [%s]' % mediaType)

    def exploreItem(self, cItem):
        printDBG("Chomikuj.exploreItem cItem[%s]" % cItem)

        cItem = dict(cItem)
        item = cItem.get('raw_item', {})
        cItem.pop('raw_item', None)

        owner = None
        parent = None
        if 'FolderId' in item and 'Owner' in item and 'Id' in item['Owner'] and 'Name' in item['Owner']:
            owner = self._getJItemNum(item['Owner'], 'Id')
            parent = self._getJItemNum(item, 'FolderId')
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'foreign_folder', 'title': 'do chomika: ' + self._getJItemStr(item['Owner'], 'Name'), 'parent': 0, 'owner': owner})
            self.addDir(params)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'foreign_folder', 'title': 'do folderu: ' + self._getJItemStr(item, 'FolderName'), 'parent': parent, 'owner': owner})
            self.addDir(params)

        params = dict(cItem)
        if owner:
            params['owner'] = owner
        if parent:
            params['parent'] = parent
        self._addItem(item, params)

    def getLinksForItem(self, cItem):
        printDBG("Chomikuj.getLinksForItem [%s]" % cItem)
        videoUrls = []

        if -1 != cItem['file_id']:
            # free
            url = strwithmeta(cItem['file_id'], {'priv_demo': True, 'priv_url': cItem['url'], 'priv_parent': cItem.get('parent', None), 'priv_page': cItem.get('page', 1), 'priv_owner': cItem.get('owner', None)})
            videoUrls.append({'name': 'Demo | darmowe', 'url': url, 'need_resolve': 1})

            # full
            name = 'Full (%s)' % cItem['size']
            if cItem.get('is_free', False):
                name += ' | darmowy'
            else:
                name += ' | odliczy transfer z konta'
            url = strwithmeta(cItem['file_id'], {'priv_type': cItem['type'], 'priv_download': True})
            videoUrls.append({'name': name, 'url': url, 'need_resolve': 1})

        return videoUrls

    def getVideoLinks(self, fileId):
        printDBG("Chomikuj.getLinkToFile [%s]" % fileId)
        urlTab = []
        try:
            if fileId.meta.get('priv_download', False):
                sts, data = self.requestJsonData(self.FILE_REQUEST_URL + fileId)
                if not sts:
                    return urlTab
                directUrl = self._getJItemStr(data, 'FileUrl', '')
                urlTab.append({'name': 'direct', 'url': directUrl})
            elif fileId.meta.get('priv_demo', False):
                url = fileId.meta['priv_url']
                owner = fileId.meta['priv_owner']
                parent = fileId.meta['priv_parent']
                page = fileId.meta['priv_page']

                if parent != None:
                    url = self.LIST_FOLDER_URL % (parent, page)
                    if owner != None:
                        url += '&AccountId=%s' % owner
                    sts, data = self.requestJsonData(url)
                else:
                    sts = False

                directUrl = ''
                if sts:
                    if 'Files' in data:
                        key = 'Files'
                    else:
                        key = 'Results'
                    for item in data.get(key, []):
                        if str(fileId) == str(self._getJItemNum(item, 'FileId', -1)):
                            mediaType = self._getJItemStr(item, 'MediaType', '')
                            if mediaType in ['Music', 'Video']:
                                directUrl = self._getJItemStr(item, 'StreamingUrl', '')
                            elif mediaType == 'Image':
                                directUrl = self._getJItemStr(item, 'ThumbnailImg', '')

                if directUrl == '':
                    directUrl = fileId.meta.get('priv_url', '')

                if self.cm.isValidUrl(directUrl):
                    urlTab.append({'name': 'direct', 'url': directUrl})
        except Exception:
            printExc()
        return urlTab

    def getLinksForFavourite(self, fav_data):
        printDBG('Chomikuj.getLinksForFavourite')
        if 'ApiKey' not in self.loginData:
            self.requestLoginData()
        return CBaseHostClass.getLinksForFavourite(self, fav_data)

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('Chomikuj.setInitListFromFavouriteItem')
        if 'ApiKey' not in self.loginData:
            self.requestLoginData()
        return CBaseHostClass.setInitListFromFavouriteItem(self, fav_data)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Chomikuj.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("Chomikuj.handleService: ---------> name[%s], category[%s] " % (name, category))
        self.currList = []

        if None == name:
            if self.requestLoginData():
                self.listsMainMenu()
        elif 'account' == category:
            self.handleProfile(self.currItem)
        elif 'foreign_folder' == category:
            self.handleForeignFolder(self.currItem)
        elif 'explore_item' == category:
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


class IPTVHost(CHostBase):

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(("Chomiki", "accounts"))
        searchTypesOptions.append(("Zdjęcia", "images"))
        searchTypesOptions.append(("Wideo", "video"))
        searchTypesOptions.append(("Audio", "music"))
        return searchTypesOptions

    def __init__(self):
        CHostBase.__init__(self, Chomikuj(), True)
