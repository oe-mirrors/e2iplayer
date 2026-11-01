# -*- coding: utf-8 -*-
LAST_MODIFIED = "01.11.2026"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, ReadTextFile, formatBytes, GetTmpDir, mkdirs
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.m3uparser import ParseM3u
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import parseTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
if not isPY2():
    basestring = str
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from os import path as os_path, remove as os_remove, rename as os_rename, symlink as os_symlink
from hashlib import md5
import codecs
import re
import unicodedata
from Components.config import config, ConfigSelection, ConfigInteger, ConfigYesNo, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import iptv_execute
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import shellQuote
try:
    from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import subtitleSidecarFiles
except ImportError:
    subtitleSidecarFiles = None
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.local_alphasort = ConfigSelection(default="alphabetically", choices=[("alphabetically", _("Alphabetically")), ("none", _("None"))])
config.plugins.iptvplayer.local_showfilesize = ConfigYesNo(default=True)
config.plugins.iptvplayer.local_showhiddensdir = ConfigYesNo(default=False)
config.plugins.iptvplayer.local_showhiddensfiles = ConfigYesNo(default=False)
config.plugins.iptvplayer.local_maxitems = ConfigInteger(100, (10, 1000000))


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Sort alphabetically"), config.plugins.iptvplayer.local_alphasort))
    optionList.append(getConfigListEntry(_("Show file size"), config.plugins.iptvplayer.local_showfilesize))
    optionList.append(getConfigListEntry(_("Show hiddens files"), config.plugins.iptvplayer.local_showhiddensfiles))
    optionList.append(getConfigListEntry(_("Show hiddens catalogs"), config.plugins.iptvplayer.local_showhiddensdir))
    optionList.append(getConfigListEntry(_("Max items per page"), config.plugins.iptvplayer.local_maxitems))
    return optionList
###################################################


def gettytul():
    return _('LocalMedia')


def iptv_execute_wrapper(cmd):
    printDBG("LocalMedia.iptv_execute_wrapper cmd[%r]" % cmd)
    obj = iptv_execute()
    obj.outErrors = 'surrogateescape'  # file names that are not UTF-8 stay restorable
    ret = obj(cmd)
    printDBG("LocalMedia.iptv_execute_wrapper ret[%r]" % ret)
    return ret


# A file name that is not valid UTF-8 comes from the system with its bad bytes as lone surrogates. The Python file
# functions take such a path as it is, everything handed over to Enigma2 (screens, player, console) can not.
def isRawByte(char):
    return 0xdc80 <= ord(char) <= 0xdcff


def hasRawBytes(text):
    return not isPY2() and any(isRawByte(char) for char in text)


def displayName(text, encoding='utf-8'):
    if not hasRawBytes(text):
        return text
    if encoding.lower().replace('-', '') != 'utf8':
        try:
            return text.encode('utf-8', 'surrogateescape').decode(encoding)
        except Exception:
            printExc()
    return ''.join(chr(ord(char) - 0xdc00) if isRawByte(char) else char for char in text)


def shellPath(path):
    # for inside "...": the bytes that are not UTF-8 come from printf
    path = ensure_str(shellQuote(path))
    if hasRawBytes(path):
        path = ''.join("$(printf '\\%03o')" % (ord(char) - 0xdc00) if isRawByte(char) else char for char in path)
    return path


class LocalMedia(GenericFolderWatchedScraperMixin, CBaseHostClass):
    ISO_MOUNT_POINT_NAME = '.iptvplayer_iso'
    FILE_SYSTEMS = ['ext2', 'ext3', 'ext4', 'vfat', 'msdos', 'iso9660', 'nfs', 'jffs2', 'autofs', 'fuseblk', 'udf', 'cifs', 'ntfs', 'ntfs3', 'nfs4', 'smb3', 'exfat', 'xfs', 'btrfs', 'f2fs', 'hfs', 'hfsplus']
    VIDEO_FILE_EXTENSIONS = ['avi', 'flv', 'mp4', 'ts', 'mov', 'wmv', 'mpeg', 'mpg', 'mkv', 'vob', 'divx', 'm2ts', 'evo', 'webm', 'm4v', 'mts', '3gp', 'ogv', 'asf']
    AUDIO_FILES_EXTENSIONS = ['mp3', 'm4a', 'ogg', 'wma', 'fla', 'wav', 'flac', 'aac', 'opus', 'ac3', 'dts', 'mka', 'm4b', 'oga']
    # webp / avif: shown from a converted copy when the box's picture loader can't read them (IconMenager)
    PICTURE_FILES_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'avif']
    M3U_FILES_EXTENSIONS = ['m3u', 'm3u8']
    ISO_FILES_EXTENSIONS = ['iso']
    RAW_NAME_LINKS_DIR = '.iptvplayer_localmedia'
    LSDIR_NO_LIMIT = 4294967295
    PAGE_URL_TPL = 'local#page={page}'  # only so the pager offers "Jump", the lists read the page number

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'LocalMedia'})
        self.currDir = ''
        self.mountedIso = ''
        self.m3uCache = {}
        self.watchedHelper = IPTVWatchedHelper('localmedia')
        self.wfInitFolderCache()

    def getCurrDir(self):
        return self.currDir

    def setCurrDir(self, currDir):
        self.currDir = currDir

    def getExtension(self, path):
        return os_path.splitext(path)[1][1:].lower()

    def prepareCmd(self, path):
        if config.plugins.iptvplayer.local_showhiddensdir.value:
            dWildcards = '[^.]*|.[^.]*|..[^.]*'
        else:
            dWildcards = '[^.]*'

        if config.plugins.iptvplayer.local_showhiddensfiles.value:
            namePart = '*'
        else:
            namePart = '[^.]*'
        fWildcards = []
        extensions = self.VIDEO_FILE_EXTENSIONS + self.AUDIO_FILES_EXTENSIONS + self.PICTURE_FILES_EXTENSIONS + self.M3U_FILES_EXTENSIONS + self.ISO_FILES_EXTENSIONS
        for ext in extensions:
            fWildcards.append(namePart + '.' + ''.join('[%s%s]' % (char.upper(), char.lower()) for char in ext))
        cmd = '%s "%s" rdl rd 0 %d "%s" "%s"' % ("/usr/bin/lsdir", shellPath(path), self.LSDIR_NO_LIMIT, ensure_str(shellQuote('|'.join(fWildcards))), ensure_str(shellQuote(dWildcards)))
        if config.plugins.iptvplayer.local_showfilesize.value:
            cmd += " 1 "
        return cmd

    def _getPage(self, tab, page):
        # the rows of one page, the page (the last one when the list got shorter), the number of the last page
        maxItems = config.plugins.iptvplayer.local_maxitems.value
        lastPage = max(1, (len(tab) + maxItems - 1) // maxItems)
        page = min(max(1, page), lastPage)
        start = (page - 1) * maxItems
        return tab[start:start + maxItems], page, lastPage

    def _getChildItem(self, cItem):
        # the base of the rows listed from cItem, which may be a pager row
        return stripPagerKeys(dict(cItem), ('url',))

    def getLocalPath(self, cItem):
        # the real file of a row, '' for a stream
        url = cItem.get('url', '')
        return cItem.get('local_path') or (url[7:] if url.startswith('file://') else '')

    def getFileWatchedKey(self, path):
        return 'video:%s' % displayName(path)

    def _getWatchedKeyForItem(self, cItem):
        try:
            # the paths inside a mounted ISO are the same for every ISO
            if not isinstance(cItem, dict) or cItem.get('live') or cItem.get('next_good_for_fav') is False:
                return ''
            itemType = cItem.get('type', '')
            if itemType in ('video', 'audio'):
                path = self.getLocalPath(cItem)
                if path:
                    return self.getFileWatchedKey(path)
                url = self.wfNormalizeUrlKey(cItem.get('url', ''))
                return 'video:%s' % url if url else ''
            path = cItem.get('path', '')
            if itemType != 'picture' and path:
                # pager rows keep the path, so page 2+ keys like page 1
                group = cItem.get('f_group', '')
                return 'folder:%s' % displayName(path) + ('#%s' % group if group else '')
        except Exception:
            printExc()
        return ''

    def listsMainMenu(self, cItem):
        printDBG("LocalMedia.listsMainMenu [%s]" % cItem)
        # list mount points
        predefined = [{'title': _('Downloads'), 'path': config.plugins.iptvplayer.DownloadsDir.value}, {'title': _('rootfs'), 'path': '/'}]
        for item in predefined:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

        table = self.getMountsTable()
        seenNodes = set()
        for item in table:
            if not config.plugins.iptvplayer.local_showhiddensdir.value:
                if os_path.basename(item['node']).startswith('.'):
                    continue

            if '/' != item['node'] and item['filesystem'] in self.FILE_SYSTEMS and item['node'] not in seenNodes:
                seenNodes.add(item['node'])
                params = dict(cItem)
                if item['node'] in ('/boot',):
                    params.update({'title': item['node'], 'path': item['node'], 'image_type': 'MMC'})
                elif '/media/usb' in item['node']:
                    params.update({'title': item['node'], 'path': item['node'], 'image_type': 'USB'})
                else:
                    params.update({'title': item['node'], 'path': item['node']})
                self.addDir(params)

    def _getM3uIcon(self, item, cItem):
        icon = item.get('tvg-logo', '')
        if not self.cm.isValidUrl(icon):
            icon = item.get('logo', '')
        if not self.cm.isValidUrl(icon):
            icon = item.get('art', '')
        if not self.cm.isValidUrl(icon):
            icon = cItem.get('icon', '')
        return icon

    def _getM3uPlayableUrl(self, baseUrl, url, item, m3uPath=''):
        # need_resolve, the url, the local file (only when the url does not name it)
        need_resolve = 1
        localPath = ''
        meta = dict(strwithmeta(url).meta)
        if not re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*://', url):
            if baseUrl == '':
                # relative to the folder of the list
                url = os_path.normpath(os_path.join(os_path.dirname(m3uPath), url.replace('\\', '/')))
                playablePath = self.getPlayablePath(url)
                if playablePath != url:
                    localPath = url
                url = 'file://' + playablePath
                need_resolve = 0
            else:
                url = self.cm.getFullUrl(url, baseUrl)
        if '' != item.get('program-id', ''):
            meta['PROGRAM-ID'] = item['program-id']
        if need_resolve:
            if '' != item.get('user_agent', ''):
                meta.setdefault('User-Agent', item['user_agent'])
            if '' != item.get('referer', ''):
                meta.setdefault('Referer', item['referer'])
        if meta:
            url = strwithmeta(url, meta)
        return need_resolve, url, localPath

    def _addM3uItem(self, cItem, item, baseUrl):
        params = dict(cItem)
        need_resolve, url, localPath = self._getM3uPlayableUrl(baseUrl, item['uri'], item, cItem.get('path', ''))
        params.update({'good_for_fav': not localPath, 'title': item['title'], 'category': 'm3u_item', 'url': url, 'desc': item.get('tvg-name', ''), 'icon': self._getM3uIcon(item, cItem), 'need_resolve': need_resolve})
        if localPath:
            params['local_path'] = localPath
        if need_resolve:
            # a channel without a length is live: nothing to mark as watched
            params['live'] = str(item.get('length', '')).strip() in ('', '-1', '0')
            links = applySidecarToLinks([{'url': url}], buildSidecarFromItem(params, IsSidecarEnabled(), '', {}))
            params['url'] = links[0]['url']
        self.addVideo(params)

    def _readM3uFile(self, path):
        # .m3u files of other programs are often not UTF-8
        try:
            with open(path, 'rb') as f:
                data = f.read()
            if data.startswith(codecs.BOM_UTF8):
                data = data[3:]
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError:
                text = data.decode('latin-1')
            return True, text.encode('utf-8') if isPY2() else text
        except Exception:
            printExc()
        return False, ''

    def _loadM3u(self, cItem):
        # base url, [(entry, group)] with one entry per group, {group: entries}; None when there is nothing to list
        baseUrl = ''
        data = ''
        if not self.cm.isValidUrl(cItem['path']):
            sts, data = self._readM3uFile(cItem['path'])
            if not sts:
                SetIPTVPlayerLastHostError(_('Failed to open the file "%s".') % displayName(cItem['path']))
                return None
            if '#EXT' not in data and self.cm.isValidUrl(data.strip()) and 1 == len(data.strip().splitlines()):
                # the file only holds the address of the list
                baseUrl = data.strip()
        else:
            baseUrl = cItem['path']

        if self.cm.isValidUrl(baseUrl):
            baseUrl = self.up.decorateParamsFromUrl(baseUrl)
            httpParams, postData = self.cm.getParamsFromUrlWithMeta(baseUrl)
            sts, data = self.cm.getPage(baseUrl, httpParams, postData)
            if not sts:
                SetIPTVPlayerLastHostError(_('Failed to open the file "%s".') % baseUrl)
                return None

        if '#EXT-X-TARGETDURATION' in data or '#EXT-X-STREAM-INF' in data:
            # a stream of its own, not a list of channels
            params = self._getChildItem(cItem)
            params.update({'good_for_fav': True, 'category': 'm3u_item', 'desc': ''})
            if baseUrl == '':
                playablePath = self.getPlayablePath(cItem['path'])
                params.update({'url': 'file://' + playablePath, 'need_resolve': 0})
                if playablePath != cItem['path']:
                    params.update({'good_for_fav': False, 'local_path': cItem['path']})
            else:
                params.update({'url': baseUrl, 'need_resolve': 1, 'live': True})
            self.addVideo(params)
            return None

        entries = []
        groups = {}
        for item in ParseM3u(data, baseUrl == ''):
            group = item.get('group-title', '')
            if item['f_type'] == 'inf' and group != '':
                if group not in groups:
                    groups[group] = []
                    entries.append((item, group))
                groups[group].append(item)
            elif item['f_type'] == 'inf' or self.cm.isValidUrl(item['uri']):
                entries.append((item, ''))
        return baseUrl, entries, groups

    def listM3u(self, cItem, nextCategory):
        printDBG("LocalMedia.listM3u [%s]" % cItem)
        page = cItem.get('page', 1)
        # the pages of one list do not read it again
        if page > 1 and self.m3uCache.get('path') == cItem['path']:
            loaded = self.m3uCache['loaded']
        else:
            loaded = self._loadM3u(cItem)
            if loaded is None:
                return
            self.m3uCache = {'path': cItem['path'], 'loaded': loaded}
        baseUrl, entries, groups = loaded

        pageEntries, page, lastPage = self._getPage(entries, page)
        childItem = self._getChildItem(cItem)
        for item, group in pageEntries:
            if group != '':
                icon = self._getM3uIcon(item, childItem)
                groupIcon = item.get('group-logo', '')
                if not self.cm.isValidUrl(groupIcon):
                    groupIcon = item.get('group-art', '')
                if not self.cm.isValidUrl(groupIcon):
                    groupIcon = icon
                params = dict(childItem)
                params.update({'good_for_fav': False, 'title': group, 'category': nextCategory, 'f_group': group, 'f_group_items': groups[group], 'f_base_url': baseUrl, 'desc': '', 'icon': groupIcon})
                if 'parent-code' in item:
                    params.update({'pin_locked': True, 'pin_code': item['parent-code']})
                self.addDir(params)
            elif item['f_type'] == 'inf':
                self._addM3uItem(childItem, item, baseUrl)
            else:
                params = dict(childItem)
                params.update({'good_for_fav': True, 'title': item['title'], 'path': item['uri'], 'desc': '', 'icon': self._getM3uIcon(item, childItem)})
                self.addDir(params)

        if not self.currList:
            SetIPTVPlayerLastHostError(_('No items found'))
        addPagingItems(self, cItem, page, page < lastPage, lastPage, self.PAGE_URL_TPL)

    def listM3uGroups(self, cItem):
        printDBG("LocalMedia.listM3uGroups [%s]" % cItem)
        pageItems, page, lastPage = self._getPage(cItem['f_group_items'], cItem.get('page', 1))
        # the rows (and favourites made of them) do not need the whole group
        childItem = self._getChildItem(cItem)
        for key in ('f_group_items', 'f_group', 'f_base_url'):
            childItem.pop(key, None)
        for item in pageItems:
            self._addM3uItem(childItem, item, cItem['f_base_url'])
        addPagingItems(self, cItem, page, page < lastPage, lastPage, self.PAGE_URL_TPL)

    def showErrorMessage(self, message):
        printDBG(message)
        SetIPTVPlayerLastHostError(message)
        self.sessionEx.open(MessageBox, text=message, type=MessageBox.TYPE_ERROR)

    def getMountsTable(self, silen=False):
        table = []

        cmd = 'mount  2>&1'
        ret = iptv_execute_wrapper(cmd)
        if ret['sts']:
            data = ret.get('data', '')
            if 0 == ret['code']:
                data = data.split('\n')
                for line in data:
                    item = self.cm.ph.getSearchGroups(line, r'(.+?) on (.+?) type ([^ ]+?) (\([^\)]+?\))', 4)
                    if not item[1]:
                        continue
                    table.append({'device': item[0], 'node': item[1], 'filesystem': item[2], 'options': item[3]})
            elif not silen:
                self.showErrorMessage(_('Can not get mount points - cmd mount failed.\nReturn code[%s].\nReturn data[%s].') % (ret['code'], displayName(data)))
        return table

    def getMountPoint(self, device):
        printDBG("LocalMedia.getMountPoint")
        for item in self.getMountsTable():
            if device == item['device']:
                return item['node']
        return ''

    def isMountPoint(self, path):
        printDBG("LocalMedia.isMountPoint")
        for item in self.getMountsTable():
            if path == item['node']:
                return True
        return False

    def getCharsetEncodingOfMountPoint(self, mountPoint):
        printDBG("getCharsetEncodingOfMountPoint mountPoint[%s]" % mountPoint)
        encoding = 'utf-8'
        table = self.getMountsTable(True)
        for item in table:
            if mountPoint == item['node']:
                encoding = self.cm.ph.getSearchGroups(item['options'], r'iocharset=([^\,^\)]+?)[\,\)]')[0]
                printDBG("mountPoint[%s] encoding[%s]" % (mountPoint, encoding))
                break
        if encoding == '':
            encoding = 'utf-8'
        return encoding

    def listIso(self, cItem):
        printDBG("LocalMedia.listIso [%s]" % cItem)
        # check if iso file is mounted
        path = cItem['path']
        defaultMountPoint = GetTmpDir(self.ISO_MOUNT_POINT_NAME)
        defaultMountPoint = defaultMountPoint.replace('//', '/')

        mountPoint = self.getMountPoint(path)
        if '' == mountPoint and path == self.mountedIso and self.isMountPoint(defaultMountPoint):
            # the mount table only names the loop device
            mountPoint = defaultMountPoint

        if '' == mountPoint:
            # umount if different image already mounted
            if self.isMountPoint(defaultMountPoint):
                self.mountedIso = ''
                cmd = 'umount "{0}"'.format(shellPath(defaultMountPoint)) + ' 2>&1'
                ret = iptv_execute_wrapper(cmd)
                if ret['sts'] and 0 != ret['code']:
                    # normal umount failed, so detach filesystem only
                    cmd = 'umount -l "{0}"'.format(shellPath(defaultMountPoint)) + ' 2>&1'
                    ret = iptv_execute_wrapper(cmd)

            # now mount the iso file
            if not mkdirs(defaultMountPoint):
                self.showErrorMessage(_('Failed to create directory "%s".') % defaultMountPoint)
                return
            else:
                cmd = 'mount -r "{0}" "{1}"'.format(shellPath(path), shellPath(defaultMountPoint)) + ' 2>&1'
                ret = iptv_execute_wrapper(cmd)
                if ret['sts']:
                    if 0 != ret['code']:
                        message = _('Mount ISO file [%s] on [%s] failed.\nReturn code[%s].\nReturn data[%s].') % (displayName(path), defaultMountPoint, ret['code'], displayName(ret['data']))
                        self.showErrorMessage(message)
                        return
                    else:
                        mountPoint = defaultMountPoint
                        self.mountedIso = path

        if '' != mountPoint:
            params = dict(cItem)
            params.update({'next_good_for_fav': False, 'path': mountPoint, 'category': 'dir'})
            self.listDir(params)

    def getPlayablePath(self, fullPath):
        # the player can not get a path that is not UTF-8: it opens a link with a clean name
        if not hasRawBytes(fullPath):
            return fullPath
        try:
            linkDir = GetTmpDir(self.RAW_NAME_LINKS_DIR)
            mkdirs(linkDir)
            name = md5(fullPath.encode('utf-8', 'surrogateescape')).hexdigest() + os_path.splitext(displayName(fullPath))[1]
            linkPath = os_path.join(linkDir, name)
            if not os_path.lexists(linkPath):
                os_symlink(fullPath, linkPath)
            return linkPath
        except Exception:
            printExc()
        return displayName(fullPath)

    def _getSortKey(self, title):
        try:
            if isPY2():
                title = title.decode('utf-8', 'ignore')
            # umlauts and accents next to their base letter
            title = ''.join(char for char in unicodedata.normalize('NFKD', title) if not unicodedata.combining(char))
        except Exception:
            printExc()
        return title.lower()

    def listDir(self, cItem):
        printDBG("LocalMedia.listDir [%s]" % cItem)
        path = cItem['path']
        # lsdir does not sort: the pages are cut out of the whole folder here
        cmd = self.prepareCmd(path) + ' 2>&1'
        ret = iptv_execute_wrapper(cmd)

        if ret['sts'] and 0 != ret['code']:
            SetIPTVPlayerLastHostError(_('Failed to get the file list from %s.') % displayName(path) + ' ' + displayName(ret['data']).strip())
        elif ret['sts']:
            self.setCurrDir(path)
            data = ret['data'].split('\n')
            encoding = 'utf-8'
            if len(data) and '//' not in data[0] and len(data[0]) and (isPY2() or hasRawBytes(ret['data'])):
                encoding = self.getCharsetEncodingOfMountPoint(data[0])

            tabs = {'dir': [], 'iso': [], 'm3u': [], 'video': [], 'audio': [], 'picture': []}
            for item in data:
                # only "name//type//..." rows are entries: not the mount point line,
                # the trailing empty line and older lsdir builds' wildcard echo
                if '//' not in item:
                    continue
                item = item.split('//')
                if config.plugins.iptvplayer.local_showfilesize.value:
                    if 5 != len(item):
                        continue
                elif 4 != len(item):
                    continue

                fileSize = -1
                if 5 == len(item):
                    try:
                        fileSize = int(item[3])
                    except Exception:
                        printExc()
                        continue
                title = item[0]
                try:
                    if isPY2():
                        title = item[0].decode(encoding).encode('utf-8')
                    else:
                        title = displayName(item[0], encoding)
                except Exception:
                    printExc()
                params = {'title': title, 'raw_name': item[0]}
                if 'd' == item[1]:
                    tabs['dir'].append(params)
                elif 'r' == item[1]:
                    params['size'] = fileSize
                    ext = self.getExtension(item[0])
                    if ext in self.M3U_FILES_EXTENSIONS:
                        tabs['m3u'].append(params)
                    elif ext in self.ISO_FILES_EXTENSIONS:
                        tabs['iso'].append(params)
                    elif ext in self.VIDEO_FILE_EXTENSIONS:
                        tabs['video'].append(params)
                    elif ext in self.AUDIO_FILES_EXTENSIONS:
                        tabs['audio'].append(params)
                    elif ext in self.PICTURE_FILES_EXTENSIONS:
                        tabs['picture'].append(params)

            rows = []
            for category in ('dir', 'iso', 'm3u', 'video', 'audio', 'picture'):
                if config.plugins.iptvplayer.local_alphasort.value == 'alphabetically':
                    tabs[category].sort(key=lambda item: self._getSortKey(item['title']))
                rows.extend((category, item) for item in tabs[category])

            pageRows, page, lastPage = self._getPage(rows, cItem.get('page', 1))
            childItem = self._getChildItem(cItem)
            for category, item in pageRows:
                self._addFileRow(childItem, item, path, category)
            addPagingItems(self, cItem, page, page < lastPage, lastPage, self.PAGE_URL_TPL)

    def _addFileRow(self, cItem, item, path, category):
        params = dict(cItem)
        params.update({'good_for_fav': cItem.get('next_good_for_fav', True), 'title': item['title'], 'category': category, 'desc': ''})
        fullPath = os_path.join(path, item['raw_name'])
        if hasRawBytes(fullPath):
            # a favourite could not be opened again from the temporary link
            params['good_for_fav'] = False
        if item.get('size', -1) >= 0:
            params['desc'] = _("Total size:") + " " + formatBytes(item['size'])
        if category in ('m3u', 'dir', 'iso'):
            params['path'] = fullPath
            self.addDir(params)
            return
        playablePath = self.getPlayablePath(fullPath)
        if playablePath != fullPath:
            params['local_path'] = fullPath
        params['url'] = 'file://' + playablePath
        params['need_resolve'] = 0
        if 'video' == category:
            self.addVideo(params)
        elif 'audio' == category:
            self.addAudio(params)
        else:
            params['icon'] = params['url']
            self.addPicture(params)

    def getSidecarFiles(self, filePath):
        # what belongs to a download, as the download manager handles it - nothing when
        # another video or audio file has the same base name
        base, ext = os_path.splitext(filePath)
        ext = ext[1:].lower()
        mediaExtensions = self.VIDEO_FILE_EXTENSIONS + self.AUDIO_FILES_EXTENSIONS
        if ext not in mediaExtensions:
            return []
        for otherExt in mediaExtensions:
            if otherExt != ext and os_path.isfile(base + '.' + otherExt):
                return []
        files = [base + sidecarExt for sidecarExt in ('.txt', '.jpg', '.jpeg') if os_path.isfile(base + sidecarExt)]
        if subtitleSidecarFiles:
            files.extend(ensure_str(sidecar) for sidecar in subtitleSidecarFiles(base))
        return files

    def getArticleContent(self, cItem):
        printDBG("LocalMedia.getArticleContent [%s]" % cItem)
        title = cItem.get('title', '')
        desc = cItem.get('desc', '')
        text = desc
        icon = cItem.get('icon', '')
        otherInfo = {}
        localPath = self.getLocalPath(cItem)
        if localPath and cItem.get('type') in ('video', 'audio'):
            # what the download saved next to the file goes first
            base = os_path.splitext(localPath)[0]
            sidecarText = ''
            sidecarIcon = ''
            if os_path.isfile(base + '.txt'):
                sts, sidecarText = ReadTextFile(base + '.txt')
                sidecarText = sidecarText.strip().replace('\r', '').replace('\n', '[/br]') if sts else ''
            for ext in ('.jpg', '.jpeg'):
                if os_path.isfile(base + ext):
                    sidecarIcon = 'file://' + self.getPlayablePath(base + ext)
                    break
            meta = {}
            if cItem.get('type') == 'video':
                try:
                    name, year, season, episode = parseTitle(os_path.splitext(title)[0])
                    meta = getMeta('tv' if season is not None else 'movie', ensure_str(name), year or '') or {}
                except Exception:
                    printExc()
            otherInfo = dict(meta.get('info', {}) or {})
            text = '[/br][/br]'.join(part for part in (sidecarText or meta.get('plot', ''), desc) if part)
            icon = sidecarIcon or meta.get('poster') or icon
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def _uriIsValid(self, url):
        return '://' in url

    def getResolvedURL(self, url):
        printDBG("LocalMedia.getResolvedURL [%s]" % url)
        videoUrls = []
        sidecar = sidecarFromUrlMeta(url, IsSidecarEnabled())

        if url.startswith('/') and fileExists(url):
            url = 'file://' + url

        uri, params = DMHelper.getDownloaderParamFromUrl(url)
        printDBG(params)
        uri = urlparser.decorateUrl(uri, params)

        if uri.meta.get('iptv_proto', '') in ['http', 'https']:
            urlSupport = self.up.checkHostSupport(uri)
        else:
            urlSupport = 0
        if 1 == urlSupport:
            retTab = self.up.getVideoLinkExt(uri)
            videoUrls.extend(retTab)
        elif 0 == urlSupport and self._uriIsValid(uri):
            lowerPath = uri.split('?')[0].lower()
            if lowerPath.endswith('.m3u8'):
                retTab = getDirectM3U8Playlist(uri, checkExt=False)
                videoUrls.extend(retTab)
            elif lowerPath.endswith('.f4m'):
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
            elif lowerPath.endswith('.mpd'):
                retTab = getMPDLinksWithMeta(uri, checkExt=False)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({'name': _('direct link'), 'url': uri})
        return decorateResolvedLinkItems(videoUrls, sidecar)

    def getFavouriteData(self, cItem):
        try:
            params = dict(cItem)
            if 'url' in params:
                params['fav_url_meta'] = strwithmeta(params['url']).meta
            data = json_dumps(params)
        except Exception:
            printExc()
            data = ''
        return data

    def getLinksForFavourite(self, fav_data):
        try:
            cItem = json_loads(fav_data)
            fav_data = strwithmeta(cItem['url'], cItem.get('fav_url_meta', {}))
        except Exception:
            printExc()

        need_resolve = 0
        if not fav_data.startswith('file://'):
            need_resolve = 1
        return [{'name': '', 'url': fav_data, 'need_resolve': need_resolve}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    # MAIN MENU
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
            category = self.currItem.get("category", '')

        if name is None:
            self.listsMainMenu({'name': 'category', 'good_for_fav': True})
        elif category == 'm3u':
            self.listM3u(self.currItem, 'list_m3u_groups')
        elif category == 'list_m3u_groups':
            self.listM3uGroups(self.currItem)
        elif category == 'iso':
            self.listIso(self.currItem)
        else:
            self.listDir(self.currItem)

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, LocalMedia(), False, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('localmedia')
        self.cFilePath = ''
        self.cType = ''
        self.needRefresh = ''
        self.DEFAULT_ICON = 'https://raw.githubusercontent.com/oe-mirrors/e2iplayer/refs/heads/gh-pages/icons/localmedia.png'

    def getPrevList(self, refresh=0):
        self.host.setCurrDir('')
        if (len(self.listOfprevList) > 0):
            hostList = self.listOfprevList.pop()
            hostCurrItem = self.listOfprevItems.pop()
            self.host.setCurrList(hostList)
            self.host.setCurrItem(hostCurrItem)

            convList = None
            if '' != self.needRefresh:
                path = hostCurrItem.get('path', '')
                if '' != path and os_path.realpath(path) == os_path.realpath(self.needRefresh):
                    self.needRefresh = ''
                    self.host.handleService(self.currIndex, 1, self.searchPattern, self.searchType)
                    convList = self.convertList(self.host.getCurrList())
            if None is convList:
                convList = self.convertList(hostList)
            return self.fixWatchedFlag(RetHost(RetHost.OK, value=convList))
        else:
            return RetHost(RetHost.ERROR, value=[])

    def getCustomActions(self, Index=0):
        retCode = RetHost.ERROR
        retlist = list(GenericFolderWatchedHostMixin.getCustomActions(self, Index).value or [])

        def addPasteAction(path):
            if os_path.isdir(path):
                if '' != self.cFilePath:
                    cutPath, cutFileName = os_path.split(self.cFilePath)
                    params = IPTVChoiceBoxItem(_('Paste "%s"') % displayName(cutFileName), "", {'action': 'paste_file', 'path': path})
                    retlist.append(params)

        ok = False
        if not self.isValidIndex(Index):
            path = self.host.getCurrDir()
            addPasteAction(path)
            retCode = RetHost.OK
            return RetHost(retCode, value=retlist)

        cItem = self.host.currList[Index]
        if 'page' in cItem or cItem.get('image_type') in ('MENU', 'FIRST', 'JUMP'):
            # a pager row stands for the folder that is listed
            addPasteAction(cItem.get('path', ''))
            return RetHost(RetHost.OK, value=retlist)

        fullPath = ''
        if cItem['type'] in ['video', 'audio', 'picture']:
            fullPath = self.host.getLocalPath(cItem)
        elif cItem.get("category", '') in ('m3u', 'dir', 'iso'):
            fullPath = cItem['path']
        ok = '' != fullPath
        if ok:
            path = os_path.dirname(fullPath)

            if cItem.get("category", '') == 'iso' and fullPath == self.host.mountedIso:
                isoMountPath = GetTmpDir(LocalMedia.ISO_MOUNT_POINT_NAME).replace('//', '/')
                params = IPTVChoiceBoxItem(_('Umount iso file'), "", {'action': 'umount_iso_file', 'file_path': fullPath, 'iso_mount_path': isoMountPath})
                retlist.append(params)

            if os_path.isfile(fullPath):
                params = IPTVChoiceBoxItem(_('Rename'), "", {'action': 'rename_file', 'file_path': fullPath})
                retlist.append(params)
                params = IPTVChoiceBoxItem(_('Remove'), "", {'action': 'remove_file', 'file_path': fullPath})
                retlist.append(params)

                params = IPTVChoiceBoxItem(_('Copy'), "", {'action': 'copy_file', 'file_path': fullPath})
                retlist.append(params)

                params = IPTVChoiceBoxItem(_('Cut'), "", {'action': 'cut_file', 'file_path': fullPath})
                retlist.append(params)

            addPasteAction(path)
            retCode = RetHost.OK

        return RetHost(retCode, value=retlist)

    def _moveWatchedMarker(self, oldPath, newPath=None):
        # the watched state stays with the file, a removed file forgets it
        try:
            marker = self.watchedHelper.getWatchedFilePath(self.host.getFileWatchedKey(oldPath))
            if marker and os_path.isfile(marker):
                if newPath:
                    os_rename(marker, self.watchedHelper.getWatchedFilePath(self.host.getFileWatchedKey(newPath)))
                else:
                    os_remove(marker)
        except Exception:
            printExc()

    def _pasteFile(self, filePath, newPath):
        ret = {'sts': True, 'code': 0, 'data': ''}
        if self.cType == 'cut':
            try:
                os_rename(filePath, newPath)
            except Exception:
                printExc()
                ret = iptv_execute_wrapper('mv -f "%s" "%s" 2>&1' % (shellPath(filePath), shellPath(newPath)))
        elif self.cType == 'copy':
            ret = iptv_execute_wrapper('cp "%s" "%s" 2>&1' % (shellPath(filePath), shellPath(newPath)))
        return ret

    def performCustomAction(self, privateData):
        if privateData['action'] in ('set_watched_flag', 'unset_watched_flag'):
            return GenericFolderWatchedHostMixin.performCustomAction(self, privateData)
        # the refresh after a file action has to read the folder again
        self.refreshAfterWatchedFlagChange = False
        retCode = RetHost.ERROR
        retlist = []
        if privateData['action'] == 'remove_file':
            try:
                ret = self.host.sessionEx.waitForFinishOpen(MessageBox, text=_('Are you sure you want to remove file "%s"?') % displayName(privateData['file_path']), type=MessageBox.TYPE_YESNO, default=False)
                if ret[0]:
                    sidecars = self.host.getSidecarFiles(privateData['file_path'])
                    os_remove(privateData['file_path'])
                    self._moveWatchedMarker(privateData['file_path'])
                    for sidecar in sidecars:
                        try:
                            os_remove(sidecar)
                        except Exception:
                            printExc()
                    retlist = ['refresh']
                    retCode = RetHost.OK
            except Exception as e:
                printExc()
                retlist = [_('Error message: %s\n') % displayName(str(e))]
        elif privateData['action'] == 'rename_file':
            try:
                path, fileName = os_path.split(privateData['file_path'])
                name, ext = os_path.splitext(fileName)
                ret = self.host.sessionEx.waitForFinishOpen(GetVirtualKeyboard(), title=_('Set file name'), text=displayName(name))
                printDBG('rename_file new name[%s]' % ret)
                if isinstance(ret[0], basestring):
                    newName = ret[0].strip()
                    newPath = os_path.join(path, newName + ext)
                    printDBG('rename_file new path[%s]' % newPath)
                    if '' == newName or '/' in newName:
                        retlist = [_('Invalid name.')]
                    elif newName != name and os_path.lexists(newPath):
                        retlist = [_('File "%s" already exists!') % displayName(newPath)]
                    else:
                        sidecars = self.host.getSidecarFiles(privateData['file_path'])
                        os_rename(privateData['file_path'], newPath)
                        self._moveWatchedMarker(privateData['file_path'], newPath)
                        oldBase = os_path.join(path, name)
                        newBase = os_path.join(path, newName)
                        # the subtitles keep their language part: name.de.srt -> new name.de.srt
                        for sidecar in sidecars:
                            newSidecar = newBase + sidecar[len(oldBase):]
                            try:
                                if not os_path.lexists(newSidecar):
                                    os_rename(sidecar, newSidecar)
                            except Exception:
                                printExc()
                        retlist = ['refresh']
                        retCode = RetHost.OK
            except Exception as e:
                printExc()
                retlist = [_('Error message: %s\n') % displayName(str(e))]
        elif privateData['action'] == 'cut_file':
            self.cFilePath = privateData['file_path']
            self.cType = 'cut'
            retCode = RetHost.OK
        elif privateData['action'] == 'copy_file':
            self.cFilePath = privateData['file_path']
            self.cType = 'copy'
            retCode = RetHost.OK
        elif privateData['action'] == 'paste_file':
            try:
                cutPath, cutFileName = os_path.split(self.cFilePath)
                newPath = os_path.join(privateData['path'], cutFileName)
                if os_path.lexists(newPath):
                    retlist = [_('File "%s" already exists') % displayName(newPath)]
                else:
                    sidecars = self.host.getSidecarFiles(self.cFilePath)
                    ret = self._pasteFile(self.cFilePath, newPath)
                    if not ret['sts'] or 0 != ret['code']:
                        if self.cType == 'copy':
                            errMsg = _('Copying file from "%s" to "%s" failed.\n') % (displayName(self.cFilePath), displayName(newPath))
                        else:
                            errMsg = _('Moving file from "%s" to "%s" failed.\n') % (displayName(self.cFilePath), displayName(newPath))
                        retlist = [errMsg + (_('Error code: %s\n') % ret['code']) + (_('Error message: %s\n') % displayName(ret['data']))]
                    else:
                        for sidecar in sidecars:
                            newSidecar = os_path.join(privateData['path'], os_path.basename(sidecar))
                            if not os_path.lexists(newSidecar):
                                self._pasteFile(sidecar, newSidecar)
                        if self.cType == 'cut':
                            self.needRefresh = cutPath
                            self._moveWatchedMarker(self.cFilePath, newPath)
                        self.cType = ''
                        self.cFilePath = ''
                        retlist = ['refresh']
                        retCode = RetHost.OK
            except Exception as e:
                printExc()
                retlist = [_('Error message: %s\n') % displayName(str(e))]
        elif privateData['action'] == 'umount_iso_file':
            cmd = 'umount "{0}"'.format(shellPath(privateData['iso_mount_path'])) + ' 2>&1'
            ret = iptv_execute_wrapper(cmd)
            if ret['sts'] and 0 != ret['code']:
                # normal umount failed, so detach filesystem only
                cmd = 'umount -l "{0}"'.format(shellPath(privateData['iso_mount_path'])) + ' 2>&1'
                ret = iptv_execute_wrapper(cmd)
            if ret['sts'] and 0 == ret['code']:
                self.host.mountedIso = ''
                retCode = RetHost.OK
            else:
                retlist = [_('Error message: %s\n') % displayName(ret['data'])]

        return RetHost(retCode, value=retlist)

    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getResolvedURL(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)

    def withArticleContent(self, cItem):
        return cItem.get('type', '') in ('video', 'audio', 'picture')

    def getFullIconUrl(self, url):
        return url

    def getDefaulIcon(self, cItem):
        return self.DEFAULT_ICON

    def converItem(self, cItem):
        needUrlResolve = cItem.get('need_resolve', 0)
        needUrlSeparateRequest = 0
        return CHostBase.converItem(self, cItem, needUrlResolve, needUrlSeparateRequest)
