# -*- coding: utf-8 -*-
LAST_MODIFIED = "01.11.2026"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify, GetIPTVPlayerLastHostError, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir
from Plugins.Extensions.IPTVPlayer.tools.iptvfilehost import IPTVFileHost
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.linklisteditor import openLinkListFileEditor
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem, openChoiceBox
from Plugins.Extensions.IPTVPlayer.components import skinchrome
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, ConfigDirectory, getConfigListEntry
from datetime import timedelta
from os.path import basename, normpath
import re
import time
###################################################

FILE_PER_PAGE = 100
DM_API_URL = 'https://api.dailymotion.com/'
DM_PER_PAGE = 100
DM_MAX_PAGE = 10  # the API answers nothing beyond page * limit = 1000
DM_VIDEO_FIELDS = 'id,mode,title,duration,views_total,created_time,thumbnail_240_url,owner.screenname'
# /user/{name} or /{name}, each optionally with /videos or /playlists
DM_OWNER_RE = re.compile(r'^https?://(?:www\.)?dailymotion\.com/(?:user/)?([^/?#|.]+)(/videos|/playlists)?/?(?:[?#].*)?$')
DM_PLAYLIST_RE = re.compile(r'^https?://(?:www\.)?dailymotion\.com/playlist/([A-Za-z0-9]+)')
DM_VIDEO_RE = re.compile(r'^https?://(?:www\.)?dailymotion\.com/(?:embed/)?video/([A-Za-z0-9]+)')
DM_FOLDERS = ('dailymotion_channel', 'dailymotion_playlists_list', 'dailymotion_playlist')
PICTURE_EXTENSIONS = ('.jpeg', '.jpg', '.png', '.webp', '.gif', '.bmp', '.avif')
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wma', '.wav', '.flac')

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.Sciezkaurllist = ConfigDirectory(default="/hdd/")
config.plugins.iptvplayer.grupujurllist = ConfigYesNo(default=True)
config.plugins.iptvplayer.sortuj = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_('Text files ytlist and urllist are in:'), config.plugins.iptvplayer.Sciezkaurllist))
    optionList.append(getConfigListEntry(_('Sort the list:'), config.plugins.iptvplayer.sortuj))
    optionList.append(getConfigListEntry(_('Group links into categories:'), config.plugins.iptvplayer.grupujurllist))
    return optionList
###################################################


def gettytul():
    return _('Urllists player')


def _urlHasExtension(url, extensions):
    url = url.lower()
    return url.endswith(extensions) or url.split('|')[0].endswith(extensions) or url.split('?')[0].endswith(extensions)


def isPictureUrl(url):
    return _urlHasExtension(url, PICTURE_EXTENSIONS)


def isAudioUrl(url):
    return _urlHasExtension(url, AUDIO_EXTENSIONS)


def getFileUrl(url):
    # a local path plays like the file:// link the player knows
    return 'file://' + url if url.startswith('/') else url


def getTitleFromUrl(url):
    # the title of a line with only a link: "dailymotion.com x8dll6k", the file name of a local file, "" when it is no link
    if url.startswith(('/', 'file://')):
        return basename(url.split('|')[0])
    match = DM_OWNER_RE.search(url)
    if match:
        return 'dailymotion.com %s%s' % (match.group(1), (match.group(2) or '').replace('/', ' '))
    match = re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*://(?:www\.)?([^/?#|]+)([^?#|]*)(?:\?([^#|]*))?', url)
    if not match:
        return ''
    videoId = re.search(r'(?:^|&)v=([^&]+)', match.group(3) or '')
    segments = [x for x in match.group(2).split('/') if x]
    return ('%s %s' % (match.group(1), videoId.group(1) if videoId else (segments[-1] if segments else ''))).strip()


def getFilePath(name):
    return normpath(config.plugins.iptvplayer.Sciezkaurllist.value + '/' + name)


class Urllist(GenericFolderWatchedScraperMixin, CBaseHostClass):
    URLLIST_FILE = 'urllist.txt'
    URRLIST_STREAMS = 'urllist.stream'
    URRLIST_USER = 'urllist.user'

    def __init__(self):
        printDBG("Urllist.__init__")

        self.MAIN_GROUPED_TAB = [{'category': 'all', 'title': _("All in one"), 'desc': _("Links from all files without categories"), 'icon': 'https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/hosturllist/all-one-neon.jpg'}]
        self.MAIN_GROUPED_TAB.extend([{'category': Urllist.URLLIST_FILE, 'title': _("Videos"), 'desc': _("Links from the file %s") % getFilePath(Urllist.URLLIST_FILE), 'icon': 'https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/hosturllist/video.jpg'},
                                       {'category': Urllist.URRLIST_STREAMS, 'title': _("Live streams"), 'desc': _("Links from the file %s") % getFilePath(Urllist.URRLIST_STREAMS), 'icon': 'https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/hosturllist/on-air-live.jpg'},
                                       {'category': Urllist.URRLIST_USER, 'title': _("User files"), 'desc': _("Links from the file %s") % getFilePath(Urllist.URRLIST_USER), 'icon': 'https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/hosturllist/my-style.jpg'}])
        CBaseHostClass.__init__(self)
        self.MAIN_URL = ''  # no site of its own; the favourites code asks for it
        self.watchedHelper = IPTVWatchedHelper('urllist')
        self.wfInitFolderCache()

    def _getHostingName(self, url):
        if 0 != self.up.checkHostSupport(url):
            return self.up.getHostName(url)
        elif self._uriIsValid(url):
            return (_('direct link'))
        else:
            return (_('unknown'))

    def _uriIsValid(self, url):
        return '://' in url

    @staticmethod
    def _getPage(cItem):
        try:
            return max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            return 1

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type') in ('video', 'audio'):
                url = cItem.get('url', '')
                return 'video:%s' % url if url and not cItem.get('is_live') and not isPictureUrl(url) else ''
            if cItem.get('category') == 'group':
                return 'folder:group:%s:%s' % (cItem.get('file_category', ''), cItem.get('group', ''))
            if cItem.get('category') in DM_FOLDERS and cItem.get('f_xid'):
                return 'folder:%s:%s' % (cItem['category'], cItem['f_xid'])
        except Exception:
            printExc()
        return ''

    def listCategory(self, cItem):
        printDBG("Urllist.listCategory cItem[%s]" % cItem)

        if cItem['category'] in ('dailymotion_channel', 'dailymotion_playlist'):
            self.listDailymotionVideos(cItem)
            return
        if cItem['category'] == 'dailymotion_playlists_list':
            self.listDailymotionPlaylists(cItem)
            return

        sortList = config.plugins.iptvplayer.sortuj.value
        groupList = config.plugins.iptvplayer.grupujurllist.value
        if cItem['category'] in ['all', Urllist.URLLIST_FILE, Urllist.URRLIST_STREAMS, Urllist.URRLIST_USER]:
            fileHost = self._loadFiles(cItem['category'], 1 == self._getPage(cItem))

            if 'all' != cItem['category'] and groupList:
                tmpList = fileHost.getGroups(sortList)
                for item in tmpList:
                    if '' == item:
                        title = (_("Other"))
                    else:
                        title = item
                    params = {'name': 'category', 'category': 'group', 'title': title, 'group': item, 'file_category': cItem['category']}
                    self.addDir(params)
            else:
                self._addFileItems(cItem, fileHost.getAllItems(sortList))
        elif 'group' in cItem:
            # read again: the file may have been edited since the group list was made
            self._addFileItems(cItem, self._loadFiles(cItem['file_category']).getItemsInGroup(cItem['group'], sortList))

    def _loadFiles(self, category, withHints=False):
        fileHost = IPTVFileHost()
        files = [name for name in (Urllist.URLLIST_FILE, Urllist.URRLIST_STREAMS, Urllist.URRLIST_USER) if category in ('all', name)]
        for name in files:
            fileHost.addFile(getFilePath(name), encoding='utf-8', addItemParams={'is_live': name == Urllist.URRLIST_STREAMS}, titleForUrl=getTitleFromUrl)
        if withHints:
            # with "All in one" only when none of the files is there: most boxes have just one of them
            if len(fileHost.missingFiles) == len(files):
                GetIPTVNotify().push(_("%s not found in %s") % (', '.join(files), normpath(config.plugins.iptvplayer.Sciezkaurllist.value)), 'info', 10)
            if fileHost.badLines:
                GetIPTVNotify().push(_("Lines that could not be read: %d (first: line %d of %s)") % (len(fileHost.badLines), fileHost.badLines[0][1], basename(fileHost.badLines[0][0])), 'info', 10)
        return fileHost

    def _addFileItems(self, cItem, items):
        page = self._getPage(cItem)
        inGroup = 'group' in cItem
        for item in items[(page - 1) * FILE_PER_PAGE:page * FILE_PER_PAGE]:
            self._addFileItem(item, (inGroup and item['title_in_group']) or item['full_title'])
        lastPage = (len(items) + FILE_PER_PAGE - 1) // FILE_PER_PAGE
        addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem['category'])

    def _addFileItem(self, item, title):
        url = getFileUrl(item['url'])
        params = {'title': title, 'url': url, 'desc': ph.clean_html(item.get('desc') or (_("Hosting: %s, %s")) % (self._getHostingName(url), url)), 'icon': item.get('icon', ''), 'good_for_fav': True}
        folder = self._getDailymotionFolder(url)
        if folder:
            params.update(folder)
            params['name'] = 'category'
            self.addDir(params)
        else:
            params['is_live'] = item.get('is_live', False)
            if isAudioUrl(url):
                self.addAudio(params)
            else:
                self.addVideo(params)

    ###################################################
    # Dailymotion owner pages and playlists
    ###################################################
    def _getDailymotionFolder(self, url):
        match = DM_PLAYLIST_RE.search(url)
        if match:
            return {'category': 'dailymotion_playlist', 'f_xid': match.group(1)}
        match = DM_OWNER_RE.search(url)
        if not match:
            return None
        if match.group(2) == '/playlists':
            return {'category': 'dailymotion_playlists_list', 'f_xid': match.group(1)}
        # the owner's page itself offers the videos and the playlists
        return {'category': 'dailymotion_channel', 'f_xid': match.group(1), 'with_playlists': not match.group(2)}

    def _getDailymotionApi(self, fun, args):
        sts, data = self.cm.getPage('%s%s?family_filter=false&%s' % (DM_API_URL, fun, args))
        if sts:
            try:
                data = json_loads(data)
                if isinstance(data, dict):
                    return data
            except Exception:
                printExc()
        return {}

    def _getDailymotionPage(self, cItem):
        return min(self._getPage(cItem), DM_MAX_PAGE)

    def _addDailymotionPaging(self, cItem, data, page):
        lastPage = min((int(data.get('total') or 0) + DM_PER_PAGE - 1) // DM_PER_PAGE, DM_MAX_PAGE)
        addPagingItems(self, cItem, page, bool(data.get('has_more')) and page < DM_MAX_PAGE, lastPage, cItem.get('url', ''))

    def _addDailymotionVideo(self, item):
        live = item.get('mode') == 'live'
        descTab = []
        if live:
            descTab.append(_('Live'))
        elif item.get('duration'):
            descTab.append(str(timedelta(seconds=int(item['duration']))))
        if item.get('views_total') is not None and not live:
            descTab.append(_('%s views') % item['views_total'])
        date = time.strftime('%Y-%m-%d', time.gmtime(int(item['created_time']))) if item.get('created_time') else ''
        if date and not live:
            descTab.append(date)
        desc = ' | '.join(descTab)
        if item.get('owner.screenname'):
            desc += '[/br]' + _('Channel: %s') % item['owner.screenname']
        title = ph.clean_html(item.get('title') or item['id'])
        self.addVideo({'title': title if live else normalizeMediathekTitle(title, date=date), 'raw_title': title, 'url': 'https://www.dailymotion.com/video/%s' % item['id'],
                       'desc': desc, 'icon': item.get('thumbnail_240_url', ''), 'is_live': live, 'good_for_fav': True})

    def listDailymotionVideos(self, cItem):
        printDBG("Urllist.listDailymotionVideos [%s]" % cItem)
        page = self._getDailymotionPage(cItem)
        args = 'limit=%d&page=%d&fields=%s' % (DM_PER_PAGE, page, DM_VIDEO_FIELDS)
        if cItem['category'] == 'dailymotion_playlist':
            fun = 'playlist/%s/videos' % cItem['f_xid']
        else:
            fun = 'user/%s/videos' % cItem['f_xid']
            args += '&sort=recent'
            if page == 1 and cItem.get('with_playlists'):
                total = self._getDailymotionApi('user/%s' % cItem['f_xid'], 'fields=playlists_total').get('playlists_total')
                if total:
                    self.addDir({'name': 'category', 'category': 'dailymotion_playlists_list', 'title': '%s (%s)' % (_('Playlists'), total), 'url': 'https://www.dailymotion.com/user/%s/playlists' % cItem['f_xid'],
                                 'f_xid': cItem['f_xid'], 'icon': cItem.get('icon', ''), 'good_for_fav': True})
        data = self._getDailymotionApi(fun, args)
        for item in data.get('list') or []:
            if item.get('id'):
                self._addDailymotionVideo(item)
        self._addDailymotionPaging(cItem, data, page)

    def listDailymotionPlaylists(self, cItem):
        printDBG("Urllist.listDailymotionPlaylists [%s]" % cItem)
        page = self._getDailymotionPage(cItem)
        data = self._getDailymotionApi('user/%s/playlists' % cItem['f_xid'], 'limit=%d&page=%d&fields=id,name,thumbnail_240_url,videos_total' % (DM_PER_PAGE, page))
        for item in data.get('list') or []:
            if not item.get('id') or not item.get('videos_total'):
                continue
            self.addDir({'name': 'category', 'category': 'dailymotion_playlist', 'title': '%s (%s)' % (ph.clean_html(item.get('name') or item['id']), item['videos_total']), 'url': 'https://www.dailymotion.com/playlist/%s' % item['id'],
                         'f_xid': item['id'], 'icon': item.get('thumbnail_240_url', ''), 'good_for_fav': True})
        self._addDailymotionPaging(cItem, data, page)

    def getLinksForVideo(self, cItem):
        printDBG("Urllist.getLinksForVideo url[%s]" % cItem['url'])
        if isPictureUrl(cItem['url']):
            return [{'name': _('Link'), 'url': urlparser.decorateParamsFromUrl(cItem['url'], True)}]
        videoUrls = []
        uri = urlparser.decorateParamsFromUrl(cItem['url'])
        protocol = uri.meta.get('iptv_proto', '')

        printDBG("PROTOCOL [%s] " % protocol)

        urlSupport = self.up.checkHostSupport(uri)
        if 1 == urlSupport:
            retTab = self.up.getVideoLinkExt(uri)
            videoUrls.extend(retTab)
        elif 0 == urlSupport and self._uriIsValid(uri):
            if protocol == 'm3u8':
                retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                videoUrls.extend(retTab)
            elif protocol == 'f4m':
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
            elif protocol == 'mpd':
                retTab = getMPDLinksWithMeta(uri, False)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({'name': _('direct link'), 'url': uri})
        # the parser's own message (private, removed ...) says more
        if not videoUrls and not GetIPTVPlayerLastHostError(False):
            SetIPTVPlayerLastHostError(_("Content not available"))
        return applySidecarToLinks(videoUrls, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        printDBG("Urllist.getArticleContent [%s]" % cItem)
        title = cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        other = {}
        category = cItem.get('category')
        videoId = DM_VIDEO_RE.search(cItem.get('url', '')) if cItem.get('type') == 'video' else None
        if videoId:
            data = self._getDailymotionApi('video/%s' % videoId.group(1), 'fields=title,description,duration,views_total,created_time,owner.screenname,channel.name,thumbnail_480_url,language,mode')
            if data.get('title'):
                title = data['title']
                text = self.cleanHtmlStr((data.get('description') or '').replace('<br />', '[/br]').replace('<br>', '[/br]')) or text
                icon = data.get('thumbnail_480_url') or icon
                if data.get('mode') == 'live':
                    other['status'] = _('Live')
                elif data.get('duration'):
                    other['duration'] = str(timedelta(seconds=int(data['duration'])))
                if data.get('views_total') is not None:
                    other['views'] = str(data['views_total'])
                if data.get('created_time'):
                    other['released'] = time.strftime('%Y-%m-%d %H:%M', time.gmtime(int(data['created_time'])))
                if data.get('owner.screenname'):
                    other['station'] = data['owner.screenname']
                if data.get('channel.name'):
                    other['category'] = data['channel.name']
                if data.get('language'):
                    other['language'] = data['language']
        elif category in ('dailymotion_channel', 'dailymotion_playlists_list'):
            data = self._getDailymotionApi('user/%s' % cItem['f_xid'], 'fields=screenname,description,avatar_720_url,videos_total,playlists_total,country')
            if data.get('screenname'):
                title = data['screenname']
                counts = '%s: %s | %s: %s' % (_('Videos'), data.get('videos_total') or 0, _('Playlists'), data.get('playlists_total') or 0)
                text = '[/br]'.join([x for x in (counts, self.cleanHtmlStr(data.get('description') or '')) if x])
                icon = data.get('avatar_720_url') or icon
                if data.get('country'):
                    other['country'] = data['country']
        elif category == 'dailymotion_playlist':
            data = self._getDailymotionApi('playlist/%s' % cItem['f_xid'], 'fields=name,description,videos_total,owner.screenname,thumbnail_480_url')
            if data.get('name'):
                title = data['name']
                counts = '%s: %s' % (_('Videos'), data.get('videos_total') or 0)
                text = '[/br]'.join([x for x in (counts, self.cleanHtmlStr(data.get('description') or '')) if x])
                icon = data.get('thumbnail_480_url') or icon
                if data.get('owner.screenname'):
                    other['station'] = data['owner.screenname']
        return [{'title': self.cleanHtmlStr(title), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Urllist.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("Urllist.handleService: ---------> name[%s], category[%s] " % (name, category))
        self.currList = []

        if None is name:
            self.listsTab(self.MAIN_GROUPED_TAB, self.currItem)
        else:
            self.listCategory(self.currItem)

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Urllist(), False)
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('urllist')

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('urllistlogo.png')])

    def withArticleContent(self, cItem):
        return (cItem.get('type') in ('video', 'audio') and not isPictureUrl(cItem.get('url', ''))) or cItem.get('category') in DM_FOLDERS

    def editUserLinks(self, session):
        # the host reads three files, so pick the one to edit first
        options = [IPTVChoiceBoxItem(name=_("Videos"), privateData=getFilePath(Urllist.URLLIST_FILE)),
                   IPTVChoiceBoxItem(name=_("Live streams"), privateData=getFilePath(Urllist.URRLIST_STREAMS)),
                   IPTVChoiceBoxItem(name=_("User files"), privateData=getFilePath(Urllist.URRLIST_USER))]
        openChoiceBox(session,
                      {'width': 600, 'height': skinchrome.choiceBoxHeight(len(options)), 'current_idx': 0, 'title': _("Edit User Links"), 'options': options, 'chrome': True},
                      lambda ret=None: self._fileSelected(session, ret))
        return True

    def _fileSelected(self, session, ret):
        if ret is not None:
            openLinkListFileEditor(session, ret.privateData, 'urllistlogo.png')

    def converItem(self, cItem, needUrlResolve=1, needUrlSeparateRequest=1):
        hostItem = CHostBase.converItem(self, cItem, needUrlResolve, needUrlSeparateRequest)
        if cItem['type'] == 'video' and isPictureUrl(cItem.get('url', '')):
            hostItem.type = hostItem.imageType = CDisplayListItem.TYPE_PICTURE
        # as written in the file, also a local path
        hostItem.iconimage = cItem.get('icon', '')
        return hostItem
