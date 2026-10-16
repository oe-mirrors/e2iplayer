# -*- coding: utf-8 -*-
# Coding: BY Angel_heart (Mohamed Elsafty)
LAST_MODIFIED = "13.10.2026"
# 13.10.2026 - new host: Qutuf al-Marjan (m.qoranway.com, Quran recitation / maqamat / nasheed lessons) and the
#   adhan page of www.qoranway.com. MP3 plays directly; RealMedia (.rm/.ram, cook audio) is converted to WMA and
#   WMV (WMV2 video, no hardware decoder on the boxes) to MPEG-TS with ffmpeg (gst-launch-1.0 fallback for audio)
#   in the temp folder; only the last converted file is kept and reused when it is played again, the original file
#   is the second link (downloads). Watched flag (page -> file), favourites, sidecar, "Page - Title" naming, INFO with
#   section path, format and size, local icons, default user agent. The site has no search and no paging.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, GetTmpDir, IsExecutable, FreeSpace, formatBytes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
###################################################
# FOREIGN import
###################################################
import os
import re
import subprocess
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://m.qoranway.com/'


AUDIO_EXT = ('.mp3', '.m4a', '.ogg', '.wav', '.flac', '.wma')
REALMEDIA_EXT = ('.rm', '.ram', '.ra')
VIDEO_DIRECT_EXT = ('.mp4', '.ts')
VIDEO_CONVERT_EXT = ('.wmv', '.avi', '.mkv', '.flv', '.mov')
MEDIA_RE = r'\.(?:mp3|m4a|ogg|wav|flac|wma|rm|ram|ra|mp4|ts|wmv|avi|mkv|flv|mov)$'
GST_LOCATION = 'location='
TMP_PREFIX = 'qoranway_'
TMP_MAX_AGE = 24 * 3600  # leftovers of an earlier session (crash, box restart)


def _ext(url):
    return os.path.splitext(url.split('?', 1)[0].lower())[1]


class QoranWay(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'qoranway', 'cookie': 'qoranway.cookie'})
        self.MAIN_URL = 'https://m.qoranway.com/'
        self.OLD_URL = 'https://www.qoranway.com/'
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/qoranway135.png')
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HTTP_HEADER.update({'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'ar,en;q=0.5'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('qoranway')
        self.wfInitFolderCache()
        self.lastConverted = {}  # media url -> converted local file
        self._removeTmpFiles(TMP_MAX_AGE)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _mediaUrl(self, url, curUrl):
        url = self.getFullUrl(url.replace('&amp;', '&'), curUrl).replace(' ', '%20')
        # the http links of the pages only answer with a redirect to https
        return re.sub(r'^http://(www\.)?qoranway\.com/', self.OLD_URL, url)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            path = re.sub(r'^https?://[^/]+', '', cItem.get('url', '')).rstrip('/')
            if not path:
                return ''
            if cItem.get('type') in ('audio', 'video'):
                return 'video:%s' % path
            if cItem.get('category') == 'list_items':
                return 'folder:%s' % path
            if cItem.get('category') == 'alathaan_group':
                return 'folder:%s#%s' % (path, cItem.get('group_index', 0))
        except Exception:
            printExc()
        return ''

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        # section names as on the site (Arabic only)
        tab = [('مقامات القرآن', 'maqamat_qoran.html'),
               ('مقامات النشيد', 'maqamat_nasheed.html'),
               ('المقرئين', 'muqrieen.html'),
               ('المنشدين', 'munshideen.html'),
               ('الدروس العلمية', 'lessons.html'),
               ('البرامج العلمية', 'baramij.html')]
        for title, path in tab:
            self.addDir({'name': 'category', 'category': 'list_items', 'title': title, 'url': self.MAIN_URL + path, 'path': title, 'icon': self.DEFAULT_ICON_URL, 'good_for_fav': True})
        self.addDir({'name': 'category', 'category': 'alathaan', 'title': 'الأذان والمقامات', 'url': self.OLD_URL + 'alathaan.html', 'path': 'الأذان والمقامات', 'icon': self.DEFAULT_ICON_URL, 'good_for_fav': True})

    @staticmethod
    def _path(cItem, title):
        # "section / reciter / ..." for the INFO text of the files
        return ' / '.join(t for t in (cItem.get('path', ''), title) if t)

    def _addMedia(self, title, url, cItem):
        ext = _ext(url)
        # many pages share file titles (sura names, maqam keys): "<page> - <title>" keeps download names apart
        fullTitle = ' - '.join(t for t in (cItem.get('title', ''), title) if t) if IsMediaNamingNormalized() else title
        params = {'name': 'category', 'title': fullTitle, 'raw_title': title, 'url': url, 'icon': self.DEFAULT_ICON_URL, 'desc': cItem.get('path', ''), 'path': cItem.get('path', ''), 'good_for_fav': True}
        if ext in VIDEO_DIRECT_EXT or ext in VIDEO_CONVERT_EXT:
            self.addVideo(params)
        else:
            self.addAudio(params)

    def listItems(self, cItem):
        # one list per page: sub pages (reciters, lessons) and/or media files
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        for item in re.findall(r'<li[\s>].*?</li>', data, re.S | re.I):
            if 'list-divider' in item:
                continue
            url = self.cm.ph.getSearchGroups(item, r'''href=['"]([^"']+)['"]''')[0]
            title = self.cleanHtmlStr(item)
            if not url or not title:
                continue
            if re.search(MEDIA_RE, url.split('?', 1)[0], re.I):
                self._addMedia(title, self._mediaUrl(url, cItem['url']), cItem)
                continue
            url = self.getFullUrl(url, cItem['url'])
            if not url.startswith(self.MAIN_URL) or not url.endswith('.html'):
                continue  # link to the desktop site, home, forums of other sites
            self.addDir({'name': 'category', 'category': 'list_items', 'title': title, 'url': url, 'path': self._path(cItem, title), 'icon': self.DEFAULT_ICON_URL, 'good_for_fav': True})

    def _alathaanParts(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        return re.split(r'<h3[^>]*>(.*?)</h3>', data, flags=re.S | re.I)

    def listAlathaan(self, cItem):
        # one folder per maqam (h3 heading of the page)
        parts = self._alathaanParts(cItem)
        for i in range(1, len(parts) - 1, 2):
            title = self.cleanHtmlStr(parts[i])
            if not title or not re.search(r'''href=['"][^'"]+?\.(?:mp3|rm|ram|ra|m4a|ogg|wav|wma)['"]''', parts[i + 1], re.I):
                continue
            self.addDir({'name': 'category', 'category': 'alathaan_group', 'title': title, 'url': cItem['url'], 'group_index': i, 'path': self._path(cItem, title), 'icon': self.DEFAULT_ICON_URL, 'good_for_fav': True})

    def listAlathaanGroup(self, cItem):
        parts = self._alathaanParts(cItem)
        idx = cItem.get('group_index', 0)
        if 0 < idx < len(parts) - 1:
            # <a href="...rm">link text</a> text after the link
            for item in re.split(r'<a\s', parts[idx + 1], flags=re.I)[1:]:
                url = self.cm.ph.getSearchGroups(item, r'''href=['"]([^"']+)['"]''')[0]
                if not re.search(MEDIA_RE, url.split('?', 1)[0], re.I) or '>' not in item:
                    continue
                linkText, _sep, afterText = item.split('>', 1)[1].partition('</a>')
                afterText = self.cleanHtmlStr(afterText.split('<', 1)[0]).strip(' -')  # the page writes "link - reciter"
                title = ' - '.join(t for t in (self.cleanHtmlStr(linkText), afterText) if t)
                if title:
                    self._addMedia(title, self._mediaUrl(url, cItem['url']), cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get('url', '')
        printDBG('QoranWay.getLinksForVideo [%s]' % url)
        ext = _ext(url)
        meta = {'User-Agent': self.HTTP_HEADER['User-Agent'], 'Referer': self.MAIN_URL}
        if ext == '.mp3' and self._probe(url)[0]:
            ext = '.rm'  # some .mp3 files of the site are RealMedia (e.g. the maqam keys)
            meta['iptv_format'] = 'rm'  # file name of a download
        if ext in AUDIO_EXT or ext in VIDEO_DIRECT_EXT:
            linksTab = [{'name': ext[1:].upper(), 'url': strwithmeta(url, meta), 'need_resolve': 0}]
        elif ext in REALMEDIA_EXT or ext in VIDEO_CONVERT_EXT:
            # the box players can not decode RealAudio (cook) and WMV2: getVideoLinks converts the file when
            # the first link is chosen; the download manager can not copy that local file -> original as 2nd link
            isVideo = ext in VIDEO_CONVERT_EXT
            linksTab = [{'name': '%s (converted, play only)' % ('TS' if isVideo else 'Audio'), 'url': strwithmeta(url, {'qoranway_convert': 'video' if isVideo else 'audio'}), 'need_resolve': 1},
                        {'name': '%s (original file, for download)' % ('WMV' if isVideo else 'RealMedia'), 'url': strwithmeta(url, meta), 'need_resolve': 0}]
        else:
            linksTab = []
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        # only the "converted" link needs this
        printDBG('QoranWay.getVideoLinks [%s]' % url)
        isVideo = strwithmeta(url).meta.get('qoranway_convert') == 'video' or _ext(url) in VIDEO_CONVERT_EXT
        return decorateResolvedLinkItems(self._getConvertedLinks(str(url), isVideo), sidecarFromUrlMeta(url, IsSidecarEnabled()))

    def _probe(self, url):
        # (is RealMedia, file size or 0) from the first 4 bytes of the file
        params = dict(self.defaultParams)
        params.update({'header': dict(self.HTTP_HEADER, Range='bytes=0-3'), 'ignore_http_code_ranges': [(206, 206)], 'collect_all_headers': True})
        sts, data = self.getPage(url, params)
        if not sts or not data:
            return False, 0
        size = self.cm.meta.get('content-range', '').rsplit('/', 1)[-1]
        return data[:4] in ('.RMF', b'.RMF'), int(size) if size.isdigit() else 0

    def _getConvertedLinks(self, url, isVideo):
        # converts the whole (small) file; the last result is reused when it is played again
        outFile = self.lastConverted.get(url, '')
        if not (outFile and os.path.isfile(outFile) and os.path.getsize(outFile) > 0):
            self._removeTmpFiles()
            self.lastConverted = {}
            outFile = self._convert(url, isVideo)
            if not outFile:
                return []
            self.lastConverted[url] = outFile
        return [{'name': '%s (converted, play only)' % os.path.splitext(outFile)[1][1:].upper(), 'url': strwithmeta(outFile, {'iptv_proto': 'file'}), 'need_resolve': 0}]

    def _convert(self, url, isVideo):
        tmpDir = GetTmpDir()
        if not FreeSpace(tmpDir, 100):
            SetIPTVPlayerLastHostError('Not enough free space in the folder for temporary data (%s) to convert this file.' % tmpDir)
            return ''
        ffmpeg = DMHelper.GET_FFMPEG_PATH()
        if isVideo and not IsExecutable(ffmpeg):
            SetIPTVPlayerLastHostError('ffmpeg is not installed on the receiver (%s), this video can not be converted.' % ffmpeg)
            return ''
        baseName = TMP_PREFIX + (re.sub(r'[^A-Za-z0-9_.-]', '_', os.path.basename(url.split('?', 1)[0])) or 'media')
        srcFile = os.path.join(tmpDir, baseName)
        ret = self.cm.saveWebFile(srcFile, url, dict(self.defaultParams))
        if not ret.get('sts') or not os.path.isfile(srcFile) or os.path.getsize(srcFile) < 100:
            self._remove(srcFile)
            SetIPTVPlayerLastHostError('Download of the file failed.')
            return ''
        for cmd, target in self._convertCmds(ffmpeg, srcFile, isVideo):
            if self._run(cmd) and os.path.isfile(target) and os.path.getsize(target) > 0:
                self._remove(srcFile)
                return target
            self._remove(target)
        self._remove(srcFile)
        SetIPTVPlayerLastHostError('Converting the file failed (ffmpeg / gst-launch-1.0).')
        return ''

    @staticmethod
    def _convertCmds(ffmpeg, srcFile, isVideo):
        # [(command, output file)], tried in this order
        stem = os.path.splitext(srcFile)[0]
        ffIn = [ffmpeg, '-nostdin', '-y', '-i', srcFile]
        if isVideo:
            ts = stem + '.ts'
            # libx264 is missing in some ffmpeg builds, mpeg2video is always there and every box decodes it
            return [(ffIn + ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', '-c:a', 'mp2', '-b:a', '64k', '-f', 'mpegts', ts], ts),
                    (ffIn + ['-c:v', 'mpeg2video', '-q:v', '5', '-c:a', 'mp2', '-b:a', '64k', '-f', 'mpegts', ts], ts)]
        wma = stem + '.wma'
        wav = stem + '.wav'
        gstIn = ['gst-launch-1.0', '-e', 'filesrc', GST_LOCATION + srcFile, '!', 'decodebin', '!', 'audioconvert', '!', 'audioresample', '!']
        return [(ffIn + ['-c:a', 'wmav2', '-b:a', '64k', '-f', 'asf', wma], wma),
                (gstIn + ['avenc_wmav2', '!', 'asfmux', '!', 'filesink', GST_LOCATION + wma], wma),
                (gstIn + ['wavenc', '!', 'filesink', GST_LOCATION + wav], wav)]

    def _run(self, cmd):
        printDBG('QoranWay._run %s' % ' '.join(cmd))
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            err = proc.communicate()[1]
            if proc.returncode != 0:
                printDBG('QoranWay._run exit %s: %s' % (proc.returncode, err[-500:]))
            return proc.returncode == 0
        except Exception:
            printExc()
            return False

    def _remove(self, path):
        try:
            if path and os.path.isfile(path):
                os.remove(path)
        except Exception:
            printExc()

    def _removeTmpFiles(self, minAge=0):
        try:
            tmpDir = GetTmpDir()
            now = time.time()
            for fileName in os.listdir(tmpDir):
                path = os.path.join(tmpDir, fileName)
                if fileName.startswith(TMP_PREFIX) and os.path.isfile(path) and now - os.path.getmtime(path) >= minAge:
                    self._remove(path)
        except Exception:
            printExc()

    ###################################################
    # info
    ###################################################
    def getArticleContent(self, cItem):
        title = cItem.get('raw_title', cItem.get('title', ''))
        text = cItem.get('desc', '')
        otherInfo = {'language': 'Arabic', 'source': 'qoranway.com'}
        if cItem.get('path'):
            otherInfo['category'] = cItem['path']
        url = cItem.get('url', '')
        if cItem.get('type') in ('audio', 'video'):
            ext = _ext(url)
            isRealMedia, size = self._probe(url)
            if isRealMedia or ext in REALMEDIA_EXT:
                fmt = 'RealMedia, converted before playback'
            elif ext in VIDEO_CONVERT_EXT:
                fmt = '%s, converted before playback' % ext[1:].upper()
            else:
                fmt = ext[1:].upper()
            otherInfo['type'] = '%s (%s)' % (fmt, formatBytes(size, 1)) if size else fmt
        elif cItem.get('category') == 'alathaan':
            sts, data = self.getPage(url)
            if sts:
                m = re.search(r'<p[^>]*>(.*?)</p>', data, re.S | re.I)
                text = (self.cleanHtmlStr(m.group(1)) if m else '') or text
        return [{'title': title, 'text': text or title, 'images': [{'title': '', 'url': cItem.get('icon') or self.DEFAULT_ICON_URL}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('QoranWay.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG('QoranWay.handleService: name[%s], category[%s]' % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'alathaan':
            self.listAlathaan(self.currItem)
        elif category == 'alathaan_group':
            self.listAlathaanGroup(self.currItem)
        else:
            printExc()
        if name is not None and not self.currList:
            SetIPTVPlayerLastHostError(_('No items found'))

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, QoranWay(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('qoranway')

    def withArticleContent(self, cItem):
        return cItem.get('type', '') in ('video', 'audio') or cItem.get('category', '') == 'alathaan'
