# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG,
    printExc,
    GetDefaultLang,
    GetSubtitlesDir,
)
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps

###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


# InnerTube client used only for the caption listing. The timedtext URLs in
# the watch page / WEB player response carry "exp=xpe" and need a PO token
# ("pot"), without it YouTube answers 200 with an empty body. The ANDROID_VR
# and ANDROID clients' captionTracks have no such requirement.
YT_VR_CLIENT_VERSION = '1.62.27'
YT_VR_USER_AGENT = 'com.google.android.apps.youtube.vr.oculus/%s (Linux; U; Android 12L; eureka-user Build/SQ3A.220605.009.A1) gzip' % YT_VR_CLIENT_VERSION
YT_PLAYER_URL = 'https://www.youtube.com/youtubei/v1/player?prettyPrint=false'


class YoutubeComProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'https://youtube.com/'
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        params = dict(params)
        params['cookie'] = 'youtubecom.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        if 'youtube_id' in self.params['url_params'] and '' != self.params['url_params']['youtube_id']:
            self.youtubeId = self.params['url_params']['youtube_id']
        else:
            self.youtubeId = ''

    def _getInnerTubeCaptionTracks(self):
        # captionTracks from an InnerTube player request, [] on failure.
        # ANDROID_VR first; YouTube bot-walls it for some videos where the
        # ANDROID client (the one the YouTube host plays with) still answers.
        from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.youtube import YT_ANDROID_CLIENT_VERSION, YT_ANDROID_SDK_VERSION, YT_ANDROID_OS_VERSION
        clients = [
            ('ANDROID_VR', '28', YT_VR_CLIENT_VERSION, YT_VR_USER_AGENT,
             {'deviceMake': 'Oculus', 'deviceModel': 'Quest 3', 'androidSdkVersion': 32, 'osName': 'Android', 'osVersion': '12L'}),
            ('ANDROID', '3', YT_ANDROID_CLIENT_VERSION, 'com.google.android.youtube/%s(Linux; U; Android %s) gzip' % (YT_ANDROID_CLIENT_VERSION, YT_ANDROID_OS_VERSION),
             {'androidSdkVersion': YT_ANDROID_SDK_VERSION, 'osName': 'Android', 'osVersion': YT_ANDROID_OS_VERSION}),
        ]
        lang = GetDefaultLang() or 'en'
        for clientName, clientId, clientVersion, userAgent, extra in clients:
            header = {'User-Agent': userAgent, 'Content-Type': 'application/json', 'Origin': 'https://www.youtube.com',
                      'X-YouTube-Client-Name': clientId, 'X-YouTube-Client-Version': clientVersion}
            client = {'clientName': clientName, 'clientVersion': clientVersion, 'hl': lang}
            client.update(extra)
            post = {'videoId': self.youtubeId, 'context': {'client': client}}
            sts, data = self.cm.getPage(YT_PLAYER_URL, {'header': header, 'raw_post_data': True}, json_dumps(post))
            if not sts:
                continue
            try:
                data = json_loads(data)
                printDBG("YoutubeComProvider %s playability: %s" % (clientName, data.get('playabilityStatus', {}).get('status', '')))
                tracks = data['captions']['playerCaptionsTracklistRenderer']['captionTracks']
                if tracks:
                    return tracks
            except Exception:
                printDBG("YoutubeComProvider %s: no captionTracks" % clientName)
        return []

    @staticmethod
    def _vttUrl(baseUrl):
        # request WebVTT, which the player's subtitle parser reads
        if re.search(r'[?&]fmt=', baseUrl):
            return re.sub(r'([?&]fmt=)[^&]*', r'\g<1>vtt', baseUrl)
        return baseUrl + ('&' if '?' in baseUrl else '?') + 'fmt=vtt'

    def getSubtitles(self, cItem):
        printDBG("YoutubeComProvider.getSubtitles")
        if '' == self.youtubeId:
            SetIPTVPlayerLastHostError(_('The YouTube video ID is invalid.'))
            return
        from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.youtube import YoutubeIE

        ytExtractor = YoutubeIE()
        tracks = self._getInnerTubeCaptionTracks()
        if tracks:
            manual, asr = [], []
            for track in tracks:
                try:
                    item = {'title': ytExtractor._caption_track_name(track) or track['languageCode'], 'url': self._vttUrl(track['baseUrl']),
                            'lang': track['languageCode'], 'format': 'vtt'}
                except Exception:
                    printExc()
                    continue
                (asr if track.get('kind') == 'asr' else manual).append(item)
            tab = manual + asr
            for idx, item in enumerate(tab):
                item['ytid'] = idx
        else:
            # fallback: watch-page listing (its URLs may need a PO token)
            tracks = ytExtractor._extract_caption_tracks(self.youtubeId)
            manual = ytExtractor._caption_tracks_to_subs(tracks, want_asr=False)
            asr = ytExtractor._caption_tracks_to_subs(tracks, want_asr=True, start_idx=len(manual))
            tab = manual + asr
        if not tab:
            SetIPTVPlayerLastHostError(_('No subtitles found.'))
            return
        for item in asr:
            item['title'] = '[%s] %s' % (_('Auto-generated'), item['title'])

        # user's language first: manual track before the auto-generated one
        defaultLang = GetDefaultLang()
        promoted = [item for item in tab if item['lang'].split('-')[0].lower() == defaultLang]
        for item in promoted + [item for item in tab if item not in promoted]:
            params = dict(item)
            params['lang'] = params['lang'].split('-')[0].lower()  # 2-letter code ("pt-BR" -> "pt")
            self.addSubtitle(params)

    def downloadSubtitleFile(self, cItem):
        printDBG("YoutubeComProvider.downloadSubtitleFile")
        retData = {}
        title = cItem['title']
        lang = cItem['lang']
        subId = cItem.get('ytid', '0')
        fileName = GetSubtitlesDir(self.subtitleFileName(title, lang, subId, self.youtubeId, 'vtt'))

        urlParams = dict(self.defaultParams)
        urlParams['max_data_size'] = self.getMaxFileSize()
        sts, data = self.cm.getPage(cItem['url'], urlParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return retData
        if isinstance(data, bytes):
            data = data.decode('utf-8', 'replace')
        data = data.lstrip(u'\ufeff')
        # an empty body (PO-token gated URL) or an error page is no subtitle
        if ' --> ' not in data:
            printDBG("YoutubeComProvider: no cues in response (%d bytes)" % len(data))
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return retData

        if not self.writeFile(fileName, data.encode('utf-8')):
            return retData

        printDBG(">>")
        printDBG(fileName)
        printDBG("<<")
        retData = {'title': title, 'path': fileName, 'lang': lang, 'imdbid': '', 'sub_id': subId}

        return retData

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.getSubtitles({'name': 'category', })

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, YoutubeComProvider(params))
