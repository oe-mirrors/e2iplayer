#!/usr/bin/env python
# -*- coding: utf-8 -*-
import urllib, urllib2, re, time
from urlparse import urlparse, urlunparse
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import *
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import _unquote
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, byteify, GetCookieDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph

from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute_ext, is_js_cached

class CYTSignAlgoExtractor:
    # MAX RECURSION Depth for security
    MAX_REC_DEPTH = 5
    RE_FUNCTION_NAMES = re.compile('[ =(,]([a-zA-Z$]+?)\([a-z0-9,]*?\)')
    RE_OBJECTS = re.compile('[ =(,;]([a-zA-Z$]+?)\.([a-zA-Z$]+?)\(')
    RE_MAIN = re.compile('([a-zA-Z0-9$]+)\(')

    def __init__(self, cm):
        self.cm = cm

    def _getAllLocalSubFunNames(self, mainFunBody):
        match = self.RE_FUNCTION_NAMES.findall( mainFunBody )
        if len(match):
            funNameTab = set( match[1:] )
            return funNameTab
        return set()

    def _getAllObjectsWithMethods(self, mainFunBody):
        objects = {}
        data = self.RE_OBJECTS.findall( mainFunBody )
        for item in data:
            if item[1] not in ['split', 'length', 'slice', 'join']:
                if item[0] not in objects:
                    objects[item[0]] = []
                objects[item[0]].append('%s:' % item[1])
        return objects

    def _findMainFunctionName(self):
        data = self.playerData

        name = ph.find(data, '"signature",', '}', 0)[1].split('(', 1)[0].strip()
        if name and not any((c in name) for c in ''', '"'''):
            return name.strip()

        name = ph.find(data, '.sig||', '}', 0)[1].split('(', 1)[0].strip()
        if name and not any((c in name) for c in ''', '"'''):
            return name.strip()

        tmp = ph.find(data, 'yt.akamaized.net', '}', 0)[1]
        if tmp:
            printDBG("DATA: %s" % tmp)
            tmp = ph.rfindall(tmp, 'return', '.set(', flags=0)
            for name in tmp:
                name = name.replace('decodeURIComponent(', '').replace('encodeURIComponent(', '')
                printDBG("ITEM: %s" % name)
                name = ph.search(name, self.RE_MAIN)[0]
                if name: return name

        tmp = ph.findall(data, ('.set(', '));', lambda d, l, s, e: not ph.any(')-";', l, s, e)))
        for name in tmp:
            name = name.split(',', 1)[-1].split('(', 1)[0].strip()
            if name and not any((c in name) for c in ''', '";()'''):
                return name

        name = ph.search(data, r'(?P<sig>[a-zA-Z0-9$]+)\s*=\s*function\(\s*a\s*\)\s*{\s*a\s*=\s*a\.split\(\s*""\s*\)')[0]
        if name and not any((c in name) for c in ''', '"'''):
            return name.strip()

        return ''

    def _findFunctionByMarker(self, marker):
        data = self.playerData
        idxStart = 0
        while idxStart < len(data):
            idxStart = data.find(marker, idxStart)
            if idxStart > 1:
                if data[idxStart-1] in (' ', ',', ';', '\n', '\r', '\t'):
                    idxEnd = data.find('}', idxStart)
                    if idxEnd > 0:
                        return data[idxStart:idxEnd+1]
            else:
                return ''
            idxStart += len(marker)
        return ''

    def _findFunction(self, funcname):
        data = self._findFunctionByMarker('function %s(' % funcname)
        if data: return data
        return self._findFunctionByMarker('%s=function(' % funcname)

    def _findObject(self, objname, methods):
        data = self.playerData
        marker = '%s={' % objname
        idxStart = 0
        while idxStart < len(data):
            idxStart = data.find(marker, idxStart)
            if idxStart > 1:
                if data[idxStart-1] in (' ', ',', ';', '\n', '\r', '\t'):
                    idxEnd = data.find('};', idxStart)
                    if idxEnd > 0:
                        if ph.all(methods, data, idxStart, idxEnd):
                            return data[idxStart:idxEnd+2]
            else:
                return ''
            idxStart += len(marker)
        return ''

    def decryptSignatures(self, encSignatures, playerUrl):
        decSignatures = []
        code = ''
        jsname = 'ytsigndec'
        jshash = 'hash7_' + playerUrl.split('://', 1)[-1]
        if not is_js_cached(jsname, jshash):
        
            # get main function
            sts, self.playerData = self.cm.getPage(playerUrl)
            if not sts: return []

            t1 = time.time()
            code = []
            mainFunctionName = self._findMainFunctionName()
            if not mainFunctionName:
                SetIPTVPlayerLastHostError(_('Encryption function name extraction failed!\nPlease report the problem to %s') % 'iptvplayere2@gmail.com')
                return []
            printDBG("mainFunctionName >> %s" % mainFunctionName)

            mainFunction = self._findFunction(mainFunctionName)
            if not mainFunction:
                SetIPTVPlayerLastHostError(_('Encryption function body extraction failed!\nPlease report the problem to %s') % 'iptvplayere2@gmail.com')
                return []
            code.append(mainFunction)

            funNames = self._getAllLocalSubFunNames(mainFunction)
            for funName in funNames:
                fun = self._findFunction(funName)
                code.insert(0, fun)

            objects = self._getAllObjectsWithMethods(mainFunction)
            for objName, methods in objects.iteritems():
                obj = self._findObject(objName, methods)
                code.insert(0, obj)

            code.append('e2i_dec=[];for (var idx in e2i_enc){e2i_dec.push(%s(e2i_enc[idx]));};print(JSON.stringify(e2i_dec));' % mainFunctionName)
            code = '\n'.join(code)
            printDBG( "---------------------------------------" )
            printDBG( "|    ALGO FOR SIGNATURE DECRYPTION    |" )
            printDBG( "---------------------------------------" )
            printDBG( code )
            printDBG( "---------------------------------------" )
        else:
            printDBG("USE ALGO FROM CACHE: %s" % jshash)

        js_params = [{'code':'e2i_enc = %s;' % json_dumps(encSignatures)}]
        js_params.append({'name':jsname, 'code':code, 'hash':jshash})
        ret = js_execute_ext( js_params )
        if ret['sts'] and 0 == ret['code']:
            try:
                decSignatures = json_loads(ret['data'])
            except Exception:
                printExc()
        return decSignatures

def ExtractorError(text):
    printDBG(text)
    SetIPTVPlayerLastHostError(_(text))
    

class YoutubeIE(object):
    """Information extractor for youtube.com."""

    _VALID_URL = r"""^
                     (
                         (?:https?://)?                                       # http(s):// (optional)
                         (?:youtu\.be/|(?:\w+\.)?youtube(?:-nocookie)?\.com/|
                            tube\.majestyc\.net/)                             # the various hostnames, with wildcard subdomains
                         (?:.*?\#/)?                                          # handle anchor (#/) redirect urls
                         (?:                                                  # the various things that can precede the ID:
                             (?:(?:v|embed|e)/)                               # v/ or embed/ or e/
                             |(?:                                             # or the v= param in all its forms
                                 (?:watch(?:_popup)?(?:\.php)?)?              # preceding watch(_popup|.php) or nothing (like /?v=xxxx)
                                 (?:\?|\#!?)                                  # the params delimiter ? or # or #!
                                 (?:.*?&)?                                    # any other preceding param (like /?s=tuff&v=xxxx)
                                 v=
                             )
                         )?                                                   # optional -> youtube.com/xxxx is OK
                     )?                                                       # all until now is optional -> you can pass the naked ID
                     ([0-9A-Za-z_-]+)                                         # here is it! the YouTube video ID
                     (?(1).+)?                                                # if we found the ID, everything can follow
                     $"""
    _LANG_URL = r'https://www.youtube.com/?hl=en&persist_hl=1&gl=US&persist_gl=1&opt_out_ackd=1'
    _LOGIN_URL = 'https://accounts.google.com/ServiceLogin'
    _AGE_URL = 'http://www.youtube.com/verify_age?next_url=/&gl=US&hl=en'
    _NEXT_URL_RE = r'[\?&]next_url=([^&]+)'
    _NETRC_MACHINE = 'youtube'
    # Listed in order of quality
    _available_formats = ['38', '37', '46', '22', '45', '35', '44', '34', '18', '43', '6', '5', '36', '17', '13',
                          # Apple HTTP Live Streaming
                          '96', '95', '94', '93', '92', '132', '151',
                          # 3D
                          '85', '84', '102', '83', '101', '82', '100',
                          # Dash video
                          '138', '137', '248', '136', '247', '135', '246',
                          '245', '244', '134', '243', '133', '242', '160','298','299',
                          '313', '271',
                          # Dash audio
                          '141', '172', '140', '171', '139',
                          ]
    _available_formats_prefer_free = ['38', '46', '37', '45', '22', '44', '35', '43', '34', '18', '6', '5', '36', '17', '13',
                                      # Apple HTTP Live Streaming
                                      '96', '95', '94', '93', '92', '132', '151',
                                      # 3D
                                      '85', '102', '84', '101', '83', '100', '82',
                                      # Dash video
                                      '138', '248', '137', '247', '136', '246', '245',
                                      '244', '135', '243', '134', '242', '133', '160','298','299',
                                      # Dash audio
                                      '172', '141', '171', '140', '139'
                                      ]
                                      
    _supported_formats = ['18', '22', '37', '38', # mp4
                          '82', '83', '84', '85', # mp4 3D
                          '92', '93', '94', '95', '96', '132', '151', # Apple HTTP Live Streaming
                          '133', '134', '135', '136', '137', '138', '160','298','299', # Dash mp4
                          '139', '140', '141', # Dash mp4 audio
                          ]
    
    _video_formats_map = {
        'flv': ['35', '34', '6', '5'],
        '3gp': ['36', '17', '13'],
        'mp4': ['38', '37', '22', '18'],
        'webm': ['46', '45', '44', '43'],
    }
    _video_extensions = {
        '13': '3gp',
        '17': '3gp',
        '18': 'mp4',
        '22': 'mp4',
        '36': '3gp',
        '37': 'mp4',
        '38': 'mp4',
        '43': 'webm',
        '44': 'webm',
        '45': 'webm',
        '46': 'webm',

        # 3d videos
        '82': 'mp4',
        '83': 'mp4',
        '84': 'mp4',
        '85': 'mp4',
        '100': 'webm',
        '101': 'webm',
        '102': 'webm',

        # Apple HTTP Live Streaming
        '92': 'mp4',
        '93': 'mp4',
        '94': 'mp4',
        '95': 'mp4',
        '96': 'mp4',
        '132': 'mp4',
        '151': 'mp4',

        # Dash mp4
        '133': 'mp4v',
        '134': 'mp4v',
        '135': 'mp4v',
        '136': 'mp4v',
        '137': 'mp4v',
        '138': 'mp4v',
        '160': 'mp4v',
        '298': 'mp4v',
        '299': 'mp4v',

        # Dash mp4 audio
        '139': 'mp4a',
        '140': 'mp4a',
        '141': 'mp4a',

        # Dash webm
        '171': 'webm',
        '172': 'webm',
        '242': 'webm',
        '243': 'webm',
        '244': 'webm',
        '245': 'webm',
        '246': 'webm',
        '247': 'webm',
        '248': 'webm',
        '271': 'webmv', 
        '313': 'webmv', 

        'mpd': 'mpd'
    }
    _video_dimensions = {
        '5': '240x400',
        '6': '???',
        '13': '???',
        '17': '144x176',
        '18': '360x640',
        '22': '720x1280',
        '34': '360x640',
        '35': '480x854',
        '36': '240x320',
        '37': '1080x1920',
        '38': '3072x4096',
        '43': '360x640',
        '44': '480x854',
        '45': '720x1280',
        '46': '1080x1920',
        '82': '360p',
        '83': '480p',
        '84': '720p',
        '85': '1080p',
        '92': '240p',
        '93': '360p',
        '94': '480p',
        '95': '720p',
        '96': '1080p',
        '100': '360p',
        '101': '480p',
        '102': '720p',
        '132': '240p',
        '151': '72p',
        '133': '240p',
        '134': '360p',
        '135': '480p',
        '136': '720p',
        '137': '1080p',
        '138': '>1080p',
        '139': '48k',
        '140': '128k',
        '141': '256k',
        '160': '192p',
        '171': '128k',
        '172': '256k',
        '242': '240p',
        '243': '360p',
        '244': '480p',
        '245': '480p',
        '246': '480p',
        '247': '720p',
        '248': '1080p',
        '298': '720p60',
        '299': '1080p60',
        '271': '1440p', 
        '313': '2160p',
    }

    _special_itags = {
        '82': '3D',
        '83': '3D',
        '84': '3D',
        '85': '3D',
        '100': '3D',
        '101': '3D',
        '102': '3D',
        '133': 'DASH Video',
        '134': 'DASH Video',
        '135': 'DASH Video',
        '136': 'DASH Video',
        '137': 'DASH Video',
        '138': 'DASH Video',
        '139': 'DASH Audio',
        '140': 'DASH Audio',
        '141': 'DASH Audio',
        '160': 'DASH Video',
        '171': 'DASH Audio',
        '172': 'DASH Audio',
        '242': 'DASH Video',
        '243': 'DASH Video',
        '244': 'DASH Video',
        '245': 'DASH Video',
        '246': 'DASH Video',
        '247': 'DASH Video',
        '248': 'DASH Video',
        '298': 'DASH Video',
        '299': 'DASH Video',
        '271': 'DASH Video', 
        '313': 'DASH Video',
    }
    IE_NAME = u'youtube'

    def __init__(self, params={}):
        proxyURL = params.get('proxyURL', '')
        useProxy = params.get('useProxy', False)
        self.cm = common(proxyURL, useProxy)
        self.cm.HOST = 'Mozilla/5.0 (X11; Linux x86_64; rv:59.0) Gecko/20100101 Firefox/59.0' #'Mpython-urllib/2.7'

    def _extract_id(self, url):
        video_id = ''
        mobj = re.match(self._VALID_URL, url, re.VERBOSE)
        if mobj != None:
            video_id = mobj.group(2)
        
        return video_id

    def _get_automatic_captions(self, video_id, webpage=None):
        sub_tracks = []
        if None == webpage:
            url = 'http://www.youtube.com/watch?v=%s&hl=%s&has_verified=1' % (video_id, GetDefaultLang())
            sts, data = self.cm.getPage(url)
            if not sts: return sub_tracks
        
        sts, data = self.cm.ph.getDataBeetwenMarkers(data, ';ytplayer.config =', '};', False)
        if not sts: return sub_tracks
        try:
            player_config = json_loads(data.strip()+'}')
            args = player_config['args']
            caption_url = args.get('ttsurl')
            if caption_url:
                timestamp = args['timestamp']
                # We get the available subtitles
                list_params = urllib.urlencode({
                    'type': 'list',
                    'tlangs': 1,
                    'asrs': 1,
                })
                list_url = caption_url + '&' + list_params
                caption_list = self.cm.getPage(list_url)
                printDBG(caption_list)
                return sub_lang_list
                
                original_lang_node = caption_list.find('track')
                if original_lang_node is None:
                    return []
                original_lang = original_lang_node.attrib['lang_code']
                caption_kind = original_lang_node.attrib.get('kind', '')

                sub_lang_list = {}
                for lang_node in caption_list.findall('target'):
                    sub_lang = lang_node.attrib['lang_code']
                    sub_formats = []
                    for ext in self._SUBTITLE_FORMATS:
                        params = urllib.urlencode({
                            'lang': original_lang,
                            'tlang': sub_lang,
                            'fmt': ext,
                            'ts': timestamp,
                            'kind': caption_kind,
                        })
                        sub_formats.append({
                            'url': caption_url + '&' + params,
                            'ext': ext,
                        })
                    sub_lang_list[sub_lang] = sub_formats
                return sub_lang_list
            
            # Some videos don't provide ttsurl but rather caption_tracks and
            # caption_translation_languages (e.g. 20LmZk1hakA)
            caption_tracks = args['caption_tracks']
            caption_translation_languages = args['caption_translation_languages']
            caption_url = compat_parse_qs(caption_tracks.split(',')[0])['u'][0]
            parsed_caption_url = urlparse(caption_url)
            caption_qs = compat_parse_qs(parsed_caption_url.query)

            sub_lang_list = {}
            for lang in caption_translation_languages.split(','):
                lang_qs = compat_parse_qs(urllib.unquote_plus(lang))
                sub_lang = lang_qs.get('lc', [None])[0]
                if not sub_lang: continue
                caption_qs.update({
                    'tlang': [sub_lang],
                    'fmt': ['vtt'],
                })
                sub_url = urlunparse(parsed_caption_url._replace(
                    query=urllib.urlencode(caption_qs, True)))
                sub_tracks.append({'title':lang_qs['n'][0].encode('utf-8'), 'url':sub_url, 'lang':sub_lang.encode('utf-8'), 'ytid':len(sub_tracks), 'format':'vtt'})
        except Exception:
            printExc()
        return sub_tracks
        
    def _get_subtitles(self, video_id):
        sub_tracks = []
        try:
            url = 'https://www.youtube.com/api/timedtext?hl=%s&type=list&v=%s' % (GetDefaultLang(), video_id)
            sts, data = self.cm.getPage(url)
            if not sts: return sub_tracks
            
            encoding = self.cm.ph.getDataBeetwenMarkers(data, 'encoding="', '"', False)[1]
            
            def getArg(item, name):
                val = self.cm.ph.getDataBeetwenMarkers(item, '%s="' % name, '"', False)[1]
                return val.decode(encoding).encode(encoding)
            
            data = data.split('/>')
            for item in data:
                if 'lang_code' not in item: continue
                id = getArg(item, 'id')
                name = getArg(item, 'name')
                lang_code = getArg(item, 'lang_code')
                lang_original = getArg(item, 'lang_original')
                lang_translated = getArg(item, 'lang_translated')

                title = (name + ' ' + lang_translated).strip()
                params = {'lang':lang_code, 'v':video_id, 'fmt':'vtt', 'name':name}
                url = 'https://www.youtube.com/api/timedtext?' + urllib.urlencode(params)
                sub_tracks.append({'title':title, 'url':url, 'lang':lang_code, 'ytid':id, 'format':'vtt'})
        except Exception:
            printExc()
        printDBG(sub_tracks)
        return sub_tracks

    def _real_extract(self, url, allowVP9 = False, allowAgeGate = False):
        # Extract original video URL from URL with redirection, like age verification, using next_url parameter
        mobj = re.search(self._NEXT_URL_RE, url)
        if mobj:
            #https
            url = 'http://www.youtube.com/' + compat_urllib_parse.unquote(mobj.group(1)).lstrip('/')
        video_id = self._extract_id(url)
        if 'yt-video-id' == video_id:
            video_id = self.cm.ph.getSearchGroups(url+'&', '[\?&]docid=([^\?^&]+)[\?&]')[0]
            isGoogleDoc = True
            url = url
            videoKey = 'docid'
            videoInfoBase = 'https://docs.google.com/get_video_info?docid=%s' % video_id
            COOKIE_FILE = GetCookieDir('docs.google.com.cookie')
            videoInfoparams = {'cookiefile':COOKIE_FILE, 'use_cookie': True, 'load_cookie':False, 'save_cookie':True}
        else:
            url = 'http://www.youtube.com/watch?v=%s&' % video_id
            isGoogleDoc = False
            videoKey = 'video_id'
            videoInfoBase = 'https://www.youtube.com/get_video_info?video_id=%s&' % video_id
            videoInfoparams = {}

        sts, video_webpage = self.cm.getPage(url)
        if not sts: raise ExtractorError('Unable to download video webpage')

        # Get video info
        #if re.search(r'player-age-gate-content">', video_webpage) is not None:
        if allowAgeGate and re.search(r'"LOGIN_REQUIRED"', video_webpage) is not None:
            #self.report_age_confirmation()
            age_gate = True
            # We simulate the access to the video from www.youtube.com/v/{video_id}
            # this can be viewed without login into Youtube
            data = compat_urllib_parse.urlencode({'el': 'embedded',
                                                  'gl': 'US',
                                                  'hl': 'en',
                                                  'eurl': 'https://youtube.googleapis.com/v/' + video_id,
                                                  'asv': 3,
                                                  'sts':'1588',
                                                  })
            video_info_url = videoInfoBase + data
            sts, video_info = self.cm.getPage(video_info_url, videoInfoparams)
            if not sts: raise ExtractorError('Faile to get "%s"' % video_info_url)
        else:
            age_gate = False
            for el_type in ['&el=detailpage', '&el=embedded', '&el=vevo', '']:
                #https
                video_info_url = videoInfoBase + ('%s&ps=default&eurl=&gl=US&hl=en'% ( el_type))
                sts, video_info = self.cm.getPage(video_info_url, videoInfoparams)
                if not sts: continue
                if '&token=' in video_info or '&account_playback_token=' in video_info:
                    break
        if '&token=' not in video_info and '&account_playback_token=' not in video_info:
            raise ExtractorError('"token" parameter not in video info')
        
        # Check for "rental" videos
        if 'ypc_video_rental_bar_text' in video_info and 'author' not in video_info:
            raise ExtractorError('"rental" videos not supported')

        # Start extracting information
        
        video_info = video_info.split('&')
        video_info2 = {}
        for item in video_info:
            item = item.split('=')
            if len(item) < 2: continue
            video_info2[item[0].strip()] = item[1].strip()
        video_info = video_info2
        del video_info2
        dashmpd = str(_unquote(str(video_info.get('dashmpd', '')), None))
        # subtitles
        if 'length_seconds' not in video_info:
            video_duration = ''
        else:
            video_duration = video_info['length_seconds']
        
        if 'url_encoded_fmt_stream_map' in video_info:
            video_info['url_encoded_fmt_stream_map'] = [_unquote(video_info['url_encoded_fmt_stream_map'], None)]
        if 'adaptive_fmts' in video_info:
            video_info['adaptive_fmts'] = [_unquote(video_info['adaptive_fmts'], None)]

        try:
            mobj = re.search(r';ytplayer.config = ({.*?});', video_webpage)
            if not mobj:
                raise ValueError('Could not find vevo ID')
            ytplayer_config = json_loads(mobj.group(1))
            args = ytplayer_config['args']
            # Easy way to know if the 's' value is in url_encoded_fmt_stream_map
            # this signatures are encrypted
            if 'url_encoded_fmt_stream_map' not in args:
                raise ValueError('No stream_map present') # caught below
            re_signature = re.compile(r'[&,]s=')
            m_s = re_signature.search(args['url_encoded_fmt_stream_map'])
            if m_s is not None:
                printDBG('%s: Encrypted signatures detected.' % video_id)
                video_info['url_encoded_fmt_stream_map'] = [args['url_encoded_fmt_stream_map']]
            m_s = re_signature.search(args.get('adaptive_fmts', ''))
        except ValueError:
            pass

        # Decide which formats to download

        is_m3u8 = 'no'
        url_map = {}
        if len(video_info.get('url_encoded_fmt_stream_map', [])) >= 1 or len(video_info.get('adaptive_fmts', [])) >= 1:
            encoded_url_map = video_info.get('url_encoded_fmt_stream_map', [''])[0] + ',' + video_info.get('adaptive_fmts',[''])[0]
            _supported_formats = self._supported_formats
            if allowVP9:
                _supported_formats.extend(['313', '271'])
            for url_data_str in encoded_url_map.split(','):
                if 'index=' in url_data_str and 'index=0-0&' in url_data_str: continue
                if 'itag=' in url_data_str and 'url=' in url_data_str:
                    url_data_str = url_data_str.split('&')
                    url_data = {}
                    
                    supported = False
                    for item in url_data_str:
                        item = item.split('=')
                        if len(item) < 2: continue
                        key = item[1].strip()
                        if item[0] == 'itag':
                            if key in self._supported_formats:
                                supported = True
                            else:
                                break
                        url_data[item[0]] = key
                            
                    if not supported:
                        continue

                    url_item = {'url':_unquote(url_data['url'], None)}
                    if 'sig' in url_data:
                        signature = url_data['sig']
                        url_item['url'] += '&signature=' + signature
                    elif 's' in url_data:
                        url_item['esign'] = _unquote(url_data['s'])
                        if 'sp' in url_data: 
                            url_item['url'] += '&%s={0}' % url_data['sp']
                        else:
                            url_item['url'] += '&signature={0}'
                    if not 'ratebypass' in url_item['url']:
                        url_item['url'] += '&ratebypass=yes'
                    url_map[url_data['itag']] = url_item
                video_url_list = self._get_video_url_list(url_map, allowVP9)
   
        if video_info.get('hlsvp') and not video_url_list:
            is_m3u8 = 'yes'
            manifest_url = _unquote(video_info['hlsvp'], None)
            url_map = self._extract_from_m3u8(manifest_url, video_id)
            video_url_list = self._get_video_url_list(url_map, allowVP9)

        if video_info.get('player_response') and not video_url_list:
            is_m3u8 = 'yes'
            manifest_url = _unquote(video_info['player_response'], None)
            manifest = re.search('"hlsManifestUrl":"(.*?)"', manifest_url)
            if manifest: manifest_url = manifest.group(1)
            url_map = self._extract_from_m3u8(manifest_url, video_id)
            video_url_list = self._get_video_url_list(url_map, allowVP9)

        if not video_url_list:
            return []

        if self.cm.isValidUrl(dashmpd):
            sign = ph.search(dashmpd, r'/s/([a-fA-F0-9\.]+)')[0]
            if sign: dashmpd = dashmpd.replace(sign, '{0}')
            video_url_list.append(('mpd', {'url':dashmpd}))
            if sign: video_url_list[-1][1]['esign'] = sign

        signItems = []
        signatures = []
        for idx in range(len(video_url_list)):
            if 'esign' in video_url_list[idx][1]:
                signItems.append(video_url_list[idx][1])
                signatures.append(video_url_list[idx][1]['esign'])

        if len(signatures):
            # decrypt signatures
            printDBG("signatures: %s" % signatures)
            playerUrl = ''
            tmp = ph.find(video_webpage, ('<script', '>', 'player/base'))[1]
            playerUrl = ph.getattr(tmp, 'src')
            if not playerUrl:
                for reObj in ['"assets"\:[^\}]+?"js"\s*:\s*"([^"]+?)"', 'src="([^"]+?)"[^>]+?name="player/base"']:
                    playerUrl = ph.search(video_webpage, reObj)[0]
                    if playerUrl:
                        break
            playerUrl = self.cm.getFullUrl(playerUrl.replace('\\', ''), self.cm.meta['url'])
            if playerUrl:
                decSignatures = CYTSignAlgoExtractor(self.cm).decryptSignatures(signatures, playerUrl)
                if len(signatures) == len(signItems):
                    try:
                        for idx in range(len(signItems)):
                            signItems[idx]['url'] = signItems[idx]['url'].format(decSignatures[idx])
                    except Exception:
                        printExc()
                        SetIPTVPlayerLastHostError(_('Decrypt Signatures Error'))
                        return []
                else:
                    return []

        if isGoogleDoc:
            cookieHeader = self.cm.getCookieHeader(COOKIE_FILE)
        
        sub_tracks = self._get_subtitles(video_id)
        results = []
        for format_param, url_item in video_url_list:
            # Extension
            video_extension = self._video_extensions.get(format_param, 'flv')

            #video_format = '{0} - {1}'.format(format_param if format_param else video_extension,
            #                                  self._video_dimensions.get(format_param, '???'))
            video_format = self._video_dimensions.get(format_param, '???')
            video_real_url = url_item['url']
            if len(sub_tracks):
                video_real_url = strwithmeta(video_real_url, {'external_sub_tracks':sub_tracks})
            if isGoogleDoc:
                video_real_url = strwithmeta(video_real_url, {'Cookie':cookieHeader})

            results.append({
                'id':       video_id,
                'url':      video_real_url,
                'uploader': '',
                'title':    '',
                'ext':      video_extension,
                'format':   video_format,
                'thumbnail':    '',
                'duration':     video_duration,
                'player_url':   '',
                'm3u8'      :   is_m3u8,
            })
            
        return results

    def _extract_from_m3u8(self, manifest_url, video_id):
        url_map = {}
        def _get_urls(_manifest):
            lines = _manifest.split('\n')
            urls = filter(lambda l: l and not l.startswith('#'),
                            lines)
            return urls
        sts, manifest = self.cm.getPage(manifest_url)
        formats_urls = _get_urls(manifest)
        for format_url in formats_urls:
            itag = self._search_regex(r'itag/(\d+?)/', format_url, 'itag')
            url_map[itag] = {'url':format_url}
        return url_map

    def _search_regex(self, pattern, string, name, default=None, fatal=True, flags=0):
        compiled_regex_type = type(re.compile(''))
        if isinstance(pattern, (str, compat_str, compiled_regex_type)):
            mobj = re.search(pattern, string, flags)
        else:
            for p in pattern:
                mobj = re.search(p, string, flags)
                if mobj: break

        if mobj:
            # return the first matching group
            return next(g for g in mobj.groups() if g is not None)
        elif default is not None:
            return default
        elif fatal:
            printDBG('Unable to extract %s' % name)
            raise
        else:
            printDBG('unable to extract %s; please report this issue on http://yt-dl.org/bug' % name)
            return None
            
    def _get_video_url_list(self, url_map, allowVP9 = False):
        format_list = list(self._available_formats_prefer_free) # available_formats
        if allowVP9:
            format_list.extend(['313', '271'])
        existing_formats = [x for x in format_list if x in url_map]
        
        return [(f, url_map[f]) for f in existing_formats] # All formats

        