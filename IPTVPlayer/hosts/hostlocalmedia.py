# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, ReadTextFile, GetBinDir, \
                                                          formatBytes, GetTmpDir, mkdirs
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.m3uparser import ParseM3u
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
from os import path as os_path, chmod as os_chmod, remove as os_remove, rename as os_rename
from Components.config import config, ConfigSelection, ConfigInteger, ConfigYesNo, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import iptv_execute
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
config.plugins.iptvplayer.local_maxitems = ConfigInteger(1000, (10, 1000000))


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
    ret = obj(cmd)
    obj = None
    printDBG("LocalMedia.iptv_execute_wrapper ret[%r]" % ret)
    return ret


class LocalMedia(CBaseHostClass):
    ISO_MOUNT_POINT_NAME = '.iptvplayer_iso'
    FILE_SYSTEMS = ['ext2', 'ext3', 'ext4', 'vfat', 'msdos', 'iso9660', 'nfs', 'jffs2', 'autofs', 'fuseblk', 'udf', 'cifs', 'ntfs']
    VIDEO_FILE_EXTENSIONS = ['avi', 'flv', 'mp4', 'ts', 'mov', 'wmv', 'mpeg', 'mpg', 'mkv', 'vob', 'divx', 'm2ts', 'evo']
    AUDIO_FILES_EXTENSIONS = ['mp3', 'm4a', 'ogg', 'wma', 'fla', 'wav', 'flac']
    PICTURE_FILES_EXTENSIONS = ['jpg', 'jpeg', 'png']
    M3U_FILES_EXTENSIONS = ['m3u']
    ISO_FILES_EXTENSIONS = ['iso']

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'LocalMedia'})
        self.currDir = ''

    def getCurrDir(self):
        return self.currDir

    def setCurrDir(self, currDir):
        self.currDir = currDir

    def getExtension(self, path):
        ext = ''
        try:
            path, ext = os_path.splitext(path)
            ext = ext[1:]
        except Exception:
            pass
        return ext.lower()

    def prepareCmd(self, path, start, end):
        lsdirPath = GetBinDir("lsdir")
        try:
            os_chmod(lsdirPath, 0777)
        except Exception:
            printExc()
        if config.plugins.iptvplayer.local_showhiddensdir.value:
            dWildcards = '[^.]*|.[^.]*|..[^.]*'
        else:
            dWildcards = '[^.]*'

        fWildcards = []
        extensions = self.VIDEO_FILE_EXTENSIONS + self.AUDIO_FILES_EXTENSIONS + self.PICTURE_FILES_EXTENSIONS + self.M3U_FILES_EXTENSIONS + self.ISO_FILES_EXTENSIONS
        for ext in extensions:
            if config.plugins.iptvplayer.local_showhiddensfiles.value:
                wilcard = '*'
            else:
                wilcard = '[^.]*'
            insensitiveExt = ''
            for l in ext:
                insensitiveExt += '[%s%s]' % (l.upper(), l.lower())
            wilcard += '.' + insensitiveExt
            fWildcards.append(wilcard)
        cmd = '%s "%s" rdl rd %d %d "%s" "%s"' % (lsdirPath, path, start, end, '|'.join(fWildcards), dWildcards)
        if config.plugins.iptvplayer.local_showfilesize.value:
            cmd += " 1 "
        return cmd

    def listsMainMenu(self, cItem):
        printDBG("LocalMedia.listsMainMenu [%s]" % cItem)
        # list mount points
        predefined = [{'title': _('Downloads'), 'path': config.plugins.iptvplayer.NaszaSciezka.value}, {'title': _('rootfs'), 'path': '/'}]
        for item in predefined:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

        table = self.getMountsTable()
        for item in table:
            if config.plugins.iptvplayer.local_showhiddensdir.value:
                path, name = os_path.split(item['node'])
                if name.startswith('.'):
                    continue

            if '/' != item['node'] and item['filesystem'] in self.FILE_SYSTEMS:
                params = dict(cItem)
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

    def _getM3uPlayableUrl(self, baseUrl, url, item):
        need_resolve = 1
        if url.startswith('/'):
            if baseUrl == '':
                url = 'file://' + url
                need_resolve = 0
            elif url.startswith('//'):
                url = 'http:' + url
            else:
                url = self.cm.getBaseUrl(baseUrl) + url[1:]
        if '' != item.get('program-id', ''):
            url = strwithmeta(url, {'PROGRAM-ID': item['program-id']})
        return need_resolve, url

    def listM3u(self, cItem, nextCategory):
        printDBG("LocalMedia.listM3u [%s]" % cItem)
        baseUrl = ''
        data = ''
        if not self.cm.isValidUrl(cItem['path']):
            sts, data = ReadTextFile(cItem['path'])
            if not sts:
                return
            if '#EXT' not in data:
                baseUrl = data.strip()
        else:
            baseUrl = cItem['path']

        if self.cm.isValidUrl(baseUrl):
            baseUrl = self.up.decorateParamsFromUrl(baseUrl)
            httpParams, postData = self.cm.getParamsFromUrlWithMeta(baseUrl)
            sts, data = self.cm.getPage(baseUrl, httpParams, postData)
            if not sts:
                return

        data = ParseM3u(data)
        groups = {}
        for item in data:
            params = dict(cItem)
            group = item.get('group-title', '')
            url = item['uri']
            icon = self._getM3uIcon(item, cItem)

            if item['f_type'] == 'inf':
                if group == '':
                    need_resolve, url = self._getM3uPlayableUrl(baseUrl, url, item)
                    params.update({'good_for_fav': True, 'title': item['title'], 'category': 'm3u_item', 'url': url, 'desc': item.get('tvg-name', ''), 'icon': icon, 'need_resolve': need_resolve})
                    self.addVideo(params)
                else:
                    if group not in groups:
                        groupIcon = item.get('group-logo', '')
                        if not self.cm.isValidUrl(groupIcon):
                            groupIcon = item.get('group-art', '')
                        if not self.cm.isValidUrl(groupIcon):
                            groupIcon = icon
                        groups[group] = []
                        params.update({'good_for_fav': False, 'title': group, 'category': nextCategory, 'f_group': group, 'url': baseUrl, 'desc': '', 'icon': groupIcon})
                        if 'parent-code' in item:
                            params.update({'pin_locked': True, 'pin_code': item['parent-code']})
                        self.addDir(params)
                    groups[group].append(item)
            elif item['f_type'] == 'import' and self.cm.isValidUrl(url):
                params.update({'good_for_fav': True, 'title': item['title'], 'path': url, 'desc': '', 'icon': icon})
                self.addDir(params)

        if groups != {}:
            for idx in range(len(self.currList)):
                if 'f_group' in self.currList[idx]:
                    self.currList[idx]['f_group_items'] = groups.get(self.currList[idx]['f_group'], [])

    def listM3uGroups(self, cItem):
        printDBG("LocalMedia.listM3uGroups [%s]" % cItem)
        baseUrl = cItem['url']
        data = cItem['f_group_items']
        for item in data:
            params = dict(cItem)
            url = item['uri']
            icon = self._getM3uIcon(item, cItem)
            need_resolve, url = self._getM3uPlayableUrl(baseUrl, url, item)
            params.update({'good_for_fav': True, 'title': item['title'], 'category': 'm3u_item', 'url': url, 'desc': item.get('tvg-name', ''), 'icon': icon, 'need_resolve': need_resolve})
            self.addVideo(params)

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
                    item = self.cm.ph.getSearchGroups(line, '(.+?) on (.+?) type ([^ ]+?) (\([^\)]+?\))', 4)
                    if len(item) < 4:
                        continue
                    table.append({'device': item[0], 'node': item[1], 'filesystem': item[2], 'options': item[3]})
            else:
                message = _('Can not get mount points - cmd mount failed.\nReturn code[%s].\nReturn data[%s].') % (ret['code'], data)
        return table

    def getMountPoint(self, device, table=[], silen=False):
        printDBG("LocalMedia.getMountPoint")
        if [] == table:
            table = self.getMountsTable(silen)
        for item in table:
            if device == item['device']:
                return item['node']
        return ''

    def isMountPoint(self, path, table=[], silen=False):
        printDBG("LocalMedia.isMountPoint")
        if [] == table:
            table = self.getMountsTable(silen)
        for item in table:
            if path == item['node']:
                return True
        return False

    def getCharsetEncodingOfMountPoint(self, mountPoint):
        printDBG("getCharsetEncodingOfMountPoint mountPoint[%s]" % mountPoint)
        encoding = 'utf-8'
        table = self.getMountsTable(True)
        for item in table:
            if mountPoint == item['node']:
                encoding = self.cm.ph.getSearchGroups(item['options'], 'iocharset=([^\,^\)]+?)[\,\)]')[0]
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

        if '' == mountPoint:
            # umount if different image already mounted
            if self.isMountPoint(defaultMountPoint):
                cmd = 'umount "{0}"'.format(defaultMountPoint) + ' 2>&1'
                ret = iptv_execute_wrapper(cmd)
                if ret['sts'] and 0 != ret['code']:
                    # normal umount failed, so detach filesystem only
                    cmd = 'umount -l "{0}"'.format(defaultMountPoint) + ' 2>&1'
                    ret = iptv_execute_wrapper(cmd)

            # now mount the iso file
            if not mkdirs(defaultMountPoint):
                message = _('Make directory [%s]') % (defaultMountPoint)
                self.showErrorMessage(message)
                return
            else:
                cmd = 'mount -r "{0}" "{1}"'.format(path, defaultMountPoint) + ' 2>&1'
                ret = iptv_execute_wrapper(cmd)
                if ret['sts']:
                    if 0 != ret['code']:
                        message = _('Mount ISO file [%s] on [%s] failed.\nReturn code[%s].\nReturn data[%s].') % (path, defaultMountPoint, ret['code'], ret['data'])
                        self.showErrorMessage(message)
                        return
                    else:
                        mountPoint = defaultMountPoint

        if '' != mountPoint:
            params = dict(cItem)
            params.update({'next_good_for_fav': False, 'path': mountPoint, 'category': 'dir'})
            self.listDir(params)

    def listDir(self, cItem):
        printDBG("LocalMedia.listDir [%s]" % cItem)
        page = cItem.get('page', 0)

        start = cItem.get('start', 0)
        end = start + config.plugins.iptvplayer.local_maxitems.value

        cItem = dict(cItem)
        cItem['start'] = 0

        path = cItem['path']
        cmd = self.prepareCmd(path, start, end + 1) + ' 2>&1'
        printDBG("cmd [%s]" % cmd)
        ret = iptv_execute_wrapper(cmd)
        printDBG(ret)

        if ret['sts'] and 0 == ret['code']:
            self.setCurrDir(path)
            data = ret['data'].split('\n')
            if len(data) and '//' not in data[0] and len(data[0]):
                encoding = self.getCharsetEncodingOfMountPoint(data[0])
            else:
                encoding = 'utf-8'

            dirTab = []
            m3uTab = []
            isoTab = []
            vidTab = []
            audTab = []
            picTab = []
            for item in data:
                start += 1
                if start > end:
                    break
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
                try:
                    title = item[0].decode(encoding).encode('utf-8')
                except Exception:
                    title = item[0]
                    printExc()
                params = {'title': title, 'raw_name': item[0]}
                if 'd' == item[1]:
                    dirTab.append(params)
                elif 'r' == item[1]:
                    params['size'] = fileSize
                    ext = self.getExtension(item[0])
                    if ext in self.M3U_FILES_EXTENSIONS:
                        m3uTab.append(params)
                    elif ext in self.ISO_FILES_EXTENSIONS:
                        isoTab.append(params)
                    elif ext in self.VIDEO_FILE_EXTENSIONS:
                        vidTab.append(params)
                    elif ext in self.AUDIO_FILES_EXTENSIONS:
                        audTab.append(params)
                    elif ext in self.PICTURE_FILES_EXTENSIONS:
                        picTab.append(params)

            self.addFromTab(cItem, dirTab, path, 'dir')
            self.addFromTab(cItem, isoTab, path, 'iso')
            self.addFromTab(cItem, m3uTab, path, 'm3u', 1)
            self.addFromTab(cItem, vidTab, path, 'video')
            self.addFromTab(cItem, audTab, path, 'audio')
            self.addFromTab(cItem, picTab, path, 'picture')

            if start > end:
                params = dict(cItem)
                params.pop('good_for_fav', None)
                params.update({'category': 'more', 'title': _('More'), 'start': end})
                self.addMore(params)

    def addFromTab(self, params, tab, path, category='', need_resolve=0):
        table = []
        if category == 'iso':
            table = self.getMountsTable(True)

        if config.plugins.iptvplayer.local_alphasort.value == 'alphabetically':
            try:
                tab.sort(key=lambda item: item['title'])
            except Exception:
                printExc()
        for item in tab:
            params = dict(params)
            params.update({'good_for_fav': params.get('next_good_for_fav', True), 'title': item['title'], 'category': category, 'desc': ''})
            if category in ['m3u', 'dir', 'iso']:
                fullPath = os_path.join(path, item['raw_name'])
                params['path'] = fullPath
                if category != 'dir':
                    descTab = []
                    if item.get('size', -1) >= 0:
                        descTab.append(_("Total size: ") + formatBytes(item['size']))

                    #if len(table):
                    #    params['iso_mount_path']  = self.getMountPoint(fullPath, table)
                    #    if params['iso_mount_path']:
                    #        descTab.append( _('Mounted on %s') % params['iso_mount_path'] )

                    if len(descTab):
                        params['desc'] = '[/br]'.join(descTab)
                self.addDir(params)
            else:
                fullPath = 'file://' + os_path.join(path, item['raw_name'])
                params['url'] = fullPath
                params['type'] = category
                if 'picture' == category:
                    params['icon'] = fullPath
                params['need_resolve'] = need_resolve
                if item.get('size', -1) >= 0:
                    params['desc'] = _("Total size: ") + formatBytes(item['size'])
                self.currList.append(params)

    def getArticleContent(self, cItem):
        printDBG("LocalMedia.getArticleContent [%s]" % cItem)
        retTab = []

        return []

    def _uriIsValid(self, url):
        if '://' in url:
            return True
        return False

    def getResolvedURL(self, url):
        printDBG("LocalMedia.getResolvedURL [%s]" % url)
        videoUrls = []

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
            if uri.split('?')[0].endswith('.m3u8'):
                retTab = getDirectM3U8Playlist(uri)
                videoUrls.extend(retTab)
            elif uri.split('?')[0].endswith('.f4m'):
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({'name': 'direct link', 'url': uri})
        return videoUrls

    def getFavouriteData(self, cItem):
        try:
            params = dict(cItem)
            if 'url' in params:
                params['fav_url_meta'] = strwithmeta(params['url']).meta
            data = json_dumps(cItem)
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

    #MAIN MENU
        if name == None:
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


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, LocalMedia(), False, [])
        self.cFilePath = ''
        self.cType = ''
        self.needRefresh = ''
        self.DEFAULT_ICON = 'http://www.ngonb.ru/files/res_media.png'

    def getPrevList(self, refresh=0):
        self.host.setCurrDir('')
        if(len(self.listOfprevList) > 0):
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
            if None == convList:
                convList = self.convertList(hostList)
            return RetHost(RetHost.OK, value=convList)
        else:
            return RetHost(RetHost.ERROR, value=[])

    def getCustomActions(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []

        def addPasteAction(path):
            if os_path.isdir(path):
                if '' != self.cFilePath:
                    cutPath, cutFileName = os_path.split(self.cFilePath)
                    params = IPTVChoiceBoxItem(_('Paste "%s"') % cutFileName, "", {'action': 'paste_file', 'path': path})
                    retlist.append(params)

        ok = False
        if not self.isValidIndex(Index):
            path = self.host.getCurrDir()
            addPasteAction(path)
            retCode = RetHost.OK
            return RetHost(retCode, value=retlist)

        if self.host.currList[Index]['type'] in ['video', 'audio', 'picture'] and \
           self.host.currList[Index].get('url', '').startswith('file://'):
            fullPath = self.host.currList[Index]['url'][7:]
            ok = True
        elif self.host.currList[Index].get("category", '') == 'm3u':
            fullPath = self.host.currList[Index]['path']
            ok = True
        elif self.host.currList[Index].get("category", '') == 'dir':
            fullPath = self.host.currList[Index]['path']
            ok = True
        elif self.host.currList[Index].get("category", '') == 'iso':
            fullPath = self.host.currList[Index]['path']
            ok = True
        if ok:
            path, fileName = os_path.split(fullPath)
            name, ext = os_path.splitext(fileName)

            if '' != self.host.currList[Index].get("iso_mount_path", ''):
                params = IPTVChoiceBoxItem(_('Umount iso file'), "", {'action': 'umount_iso_file', 'file_path': fullPath, 'iso_mount_path': self.host.currList[Index]['iso_mount_path']})
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

    def performCustomAction(self, privateData):
        retCode = RetHost.ERROR
        retlist = []
        if privateData['action'] == 'remove_file':
            try:
                ret = self.host.sessionEx.waitForFinishOpen(MessageBox, text=_('Are you sure you want to remove file "%s"?') % privateData['file_path'], type=MessageBox.TYPE_YESNO, default=False)
                if ret[0]:
                    os_remove(privateData['file_path'])
                    retlist = ['refresh']
                    retCode = RetHost.OK
            except Exception:
                printExc()
        if privateData['action'] == 'rename_file':
            try:
                path, fileName = os_path.split(privateData['file_path'])
                name, ext = os_path.splitext(fileName)
                ret = self.host.sessionEx.waitForFinishOpen(GetVirtualKeyboard(), title=_('Set file name'), text=name)
                printDBG('rename_file new name[%s]' % ret)
                if isinstance(ret[0], basestring):
                    newPath = os_path.join(path, ret[0] + ext)
                    printDBG('rename_file new path[%s]' % newPath)
                    if not os_path.isfile(newPath) and not os_path.islink(newPath):
                        os_rename(privateData['file_path'], newPath)
                        retlist = ['refresh']
                        retCode = RetHost.OK
                    else:
                        retlist = [_('File "%s" already exists!') % newPath]
            except Exception:
                printExc()
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
                ok = True
                cutPath, cutFileName = os_path.split(self.cFilePath)
                newPath = os_path.join(privateData['path'], cutFileName)
                if os_path.isfile(newPath):
                    retlist = [_('File "%s" already exists') % newPath]
                    ok = False
                else:
                    ret = {'sts': True, 'code': 0, 'data': ''}
                    if self.cType == 'cut':
                        try:
                            os_rename(self.cFilePath, newPath)
                            self.needRefresh = cutPath
                        except Exception:
                            printExc()
                            cmd = 'mv -f "%s" "%s"' % (self.cFilePath, newPath)
                            ret = iptv_execute_wrapper(cmd)
                    elif self.cType == 'copy':
                        cmd = 'cp "%s" "%s"' % (self.cFilePath, newPath)
                        ret = iptv_execute_wrapper(cmd)

                if ret['sts'] and 0 != ret['code']:
                    retlist = [(_('Moving file from "%s" to "%s" failed.\n') % (self.cFilePath, newPath)) + (_('Error code: %s\n') % ret['code']) + (_('Error message: %s\n') % ret['data'])]
                    ok = False

                if ok:
                    self.cType = ''
                    self.cFilePath = ''
                    retlist = ['refresh']
                    retCode = RetHost.OK
            except Exception:
                printExc()
        elif privateData['action'] == 'umount_iso_file':
            cmd = 'umount "{0}"'.format(privateData['iso_mount_path']) + ' 2>&1'
            ret = iptv_execute_wrapper(cmd)
            if ret['sts'] and 0 != ret['code']:
                # normal umount failed, so detach filesystem only
                cmd = 'umount -l "{0}"'.format(privateData['iso_mount_path']) + ' 2>&1'
                ret = iptv_execute_wrapper(cmd)

        return RetHost(retCode, value=retlist)

    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getResolvedURL(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)

    def getArticleContent(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        hList = self.host.getArticleContent(self.host.currList[Index])
        for item in hList:
            title = item.get('title', '')
            text = item.get('text', '')
            images = item.get("images", [])
            othersInfo = item.get('other_info', '')
            retlist.append(ArticleContent(title=title, text=text, images=images, richDescParams=othersInfo))
        return RetHost(RetHost.OK, value=retlist)

    def getFullIconUrl(self, url):
        return url

    def getDefaulIcon(self, cItem):
        return self.DEFAULT_ICON

    def converItem(self, cItem):
        needUrlResolve = cItem.get('need_resolve', 0)
        needUrlSeparateRequest = 0
        return CHostBase.converItem(self, cItem, needUrlResolve, needUrlSeparateRequest)
