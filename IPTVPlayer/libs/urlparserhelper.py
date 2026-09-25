# -*- coding: utf-8 -*-
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper, common
from Plugins.Extensions.IPTVPlayer.libs import m3u8
from binascii import hexlify
import ast
import re
import time
import string
import codecs
import six
from urllib.parse import unquote, urljoin

try:
    from hashlib import md5

    def hex_md5(e):
        return md5(six.ensure_binary(e)).hexdigest()
except Exception:
    from Plugins.Extensions.IPTVPlayer.libs.crypto.hash.md5Hash import MD5

    def hex_md5(e):
        hashAlg = MD5()
        return hexlify(hashAlg(e))


def int2base(x, base):
    digs = string.digits + string.ascii_lowercase
    if x < 0:
        sign = -1
    elif x == 0:
        return '0'
    else:
        sign = 1
    x *= sign
    digits = []
    while x:
        digits.append(digs[int(x) % base])
        x = x // base  # // pushes PY3 to use int arithmetic
    if sign < 0:
        digits.append('-')
    digits.reverse()
    return ''.join(digits)


def JS_toString(x, base):
    return int2base(x, base)


def JS_DateValueOf():
    return time.time() * 1000


def JS_FromCharCode(*args):
    return ''.join(map(chr, args))


def unicode_escape(s):
    decoder = codecs.getdecoder('unicode_escape')
    return re.sub(r'\\u[0-9a-fA-F]{4,}', lambda m: decoder(m.group(0))[0], s).encode('utf-8')


def drdX_fx(e):
    t = {}
    n = 0
    r = 0
    i = []
    s = ""
    o = JS_FromCharCode
    u = [[65, 91], [97, 123], [48, 58], [43, 44], [47, 48]]

    for z in range(len(u)):
        n = u[z][0]
        while n < u[z][1]:
            i.append(o(n))
            n += 1
    n = 0
    while n < 64:
        t[i[n]] = n
        n += 1
    n = 0
    while n < len(e):
        a = 0
        f = 0
        l = 0
        c = 0
        h = e[n:n + 72]
        while l < len(h):
            f = t[h[l]]
            a = (a << 6) + f
            c += 6
            while c >= 8:
                c -= 8
                s += o((a >> c) % 256)
            l += 1
        n += 72
    return s


def VIDEOMEGA_decryptPlayerParams(p, a, c, k, e, d):
    def e1(c):
        return JS_toString(c, 36)

    def k1(matchobj):
        return d[matchobj.group(0)]

    def e2(t=None):
        return '\\w+'

    e = e1
    if True:
        while c != 0:
            c -= 1
            tmp1 = e(c)
            d[tmp1] = k[c]
            if '' == d[tmp1]:
                d[tmp1] = e(c)
        c = 1
        k = [k1]
        e = e2
    while c != 0:
        c -= 1
        if k[c]:
            reg = '\\b' + e(c) + '\\b'
            p = re.sub(reg, k[c], p)
    return p


def SAWLIVETV_decryptPlayerParams(p, a, c, k, e, d):
    def e1(c):
        if c < a:
            ret = ''
        else:
            ret = e(c / a)
        c = c % a
        if c > 35:
            ret += chr(c + 29)
        else:
            ret += JS_toString(c, 36)
        return ret

    def k1(matchobj):
        return d[matchobj.group(0)]

    def e2(t=None):
        return '\\w+'

    e = e1
    if True:
        while c != 0:
            c -= 1
            tmp1 = e(c)
            d[tmp1] = k[c]
            if '' == d[tmp1]:
                d[tmp1] = e(c)
        c = 1
        k = [k1]
        e = e2
    while c != 0:
        c -= 1
        if k[c]:
            reg = '\\b' + e(c) + '\\b'
            p = re.sub(reg, k[c], p)
    return p


def TEAMCASTPL_decryptPlayerParams(p, a, c, k, e=None, d=None):
    def e1(c):
        if c < a:
            ret = ''
        else:
            ret = e(c / a)
        c = c % a
        if c > 35:
            ret += chr(c + 29)
        else:
            ret += JS_toString(c, 36)
        return ret

    e = e1
    while c != 0:
        c -= 1
        if k[c]:
            reg = '\\b' + e(c) + '\\b'
            p = re.sub(reg, k[c], p)
    return p


def getParamsTouple(code, type=1, r1=False, r2=False):
    mark1Tab = ["}(", "}\r\n(", "}\n(", "}\r("]
    mark2 = "))"

    for mark1 in mark1Tab:
        if r1:
            idx1 = code.rfind(mark1)
        else:
            idx1 = code.find(mark1)
        if idx1 > -1:
            break
    if -1 == idx1:
        return ''
    idx1 += len(mark1)
    if r2:
        idx2 = code.rfind(mark2, idx1)
    else:
        idx2 = code.find(mark2, idx1)
    if -1 == idx2:
        return ''
    idx2 += type
    return code[idx1:idx2]


def _astConstant(node):
    # constant node -> (True, value); Python 3.8+ uses ast.Constant, older versions Str/Num/NameConstant
    for name, attr in (('Constant', 'value'), ('Str', 's'), ('Num', 'n'), ('NameConstant', 'value')):
        cls = getattr(ast, name, None)
        if cls is not None and isinstance(node, cls):
            value = getattr(node, attr)
            if value is None or isinstance(value, (str, int, float, bool)):
                return True, value
    return False, None


def safeEvalExpression(expr, functions=None, maxLen=1048576):
    """Value of a small expression taken from a web page, WITHOUT running it as code.
    Allowed: string/number constants, tuples/lists/dicts of them, + - * / on numbers,
    + on strings, [index] and [a:b] slices, 'text'.split(sep) and the plain functions
    passed in `functions` (name -> callable). Anything else raises ValueError."""
    functions = functions or {}

    def ev(node):
        isConst, value = _astConstant(node)
        if isConst:
            return value
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, (ast.Tuple, ast.List)):
            values = [ev(item) for item in node.elts]
            return tuple(values) if isinstance(node, ast.Tuple) else values
        if isinstance(node, ast.Dict):
            if None in node.keys:
                raise ValueError('dict unpacking not allowed')
            return dict((ev(k), ev(v)) for k, v in zip(node.keys, node.values))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = ev(node.operand)
            if not isinstance(value, (int, float)):
                raise ValueError('unary operator on non-number')
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = ev(node.left), ev(node.right)
            numbers = isinstance(left, (int, float)) and isinstance(right, (int, float))
            if isinstance(node.op, ast.Add) and isinstance(left, str) and isinstance(right, str):
                if len(left) + len(right) > maxLen:
                    raise ValueError('string too long')
                return left + right
            if not numbers:
                raise ValueError('operator only allowed on numbers')
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            return left / right
        if isinstance(node, ast.Subscript):
            value = ev(node.value)
            if not isinstance(value, (str, list, tuple)):
                raise ValueError('subscript only on strings/lists')
            sliceNode = node.slice
            if hasattr(ast, 'Index') and isinstance(sliceNode, getattr(ast, 'Index')):  # Python < 3.9
                sliceNode = sliceNode.value
            if isinstance(sliceNode, ast.Slice):
                parts = [None if item is None else ev(item) for item in (sliceNode.lower, sliceNode.upper, sliceNode.step)]
                for item in parts:
                    if item is not None and not isinstance(item, int):
                        raise ValueError('slice bounds must be integers')
                return value[parts[0]:parts[1]:parts[2]]
            index = ev(sliceNode)
            if not isinstance(index, int):
                raise ValueError('index must be an integer')
            return value[index]
        if isinstance(node, ast.Call) and not node.keywords and not getattr(node, 'starargs', None) and not getattr(node, 'kwargs', None):
            args = [ev(item) for item in node.args]
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'split':
                target = ev(node.func.value)
                if isinstance(target, str) and len(args) <= 1 and all(isinstance(item, str) for item in args):
                    return target.split(*args)
            elif isinstance(node.func, ast.Name) and node.func.id in functions:
                return functions[node.func.id](*args)
        raise ValueError('unsupported expression element: %s' % type(node).__name__)

    return ev(ast.parse(expr.strip(), mode='eval'))


def unpackJSPlayerParams(code, decryptionFun, type=1, r1=False, r2=False):
    printDBG('unpackJSPlayerParams')
    code = getParamsTouple(code, type, r1, r2)
    data = unpackJS(code, decryptionFun)
    if data == '' and code.endswith('))'):
        data = unpackJS(code[:-1], decryptionFun)
    return data


def unpackJS(data, decryptionFun, addCode=''):
    # the parameter list of a packed player script ('p',36,12,'k|e|y'.split('|'),0,{}) - parsed,
    # never executed: it comes straight from the web page
    if addCode:
        printDBG('unpackJS: addCode is not supported')
        return ''
    try:
        paramsTouple = safeEvalExpression('(' + data + ')', {'decodeURIComponent': unquote, 'unescape': unquote})
        if not isinstance(paramsTouple, tuple):
            paramsTouple = (paramsTouple,)
    except Exception:
        printExc('unpackJS parse EXCEPTION')
        return ''
    try:
        return decryptionFun(*paramsTouple)
    except Exception:
        printExc('decryptPlayerParams EXCEPTION')
    return ''


def VIDUPME_decryptPlayerParams(p=None, a=None, c=None, k=None, e=None, d=None):
    while c > 0:
        c -= 1
        if k[c]:
            p = re.sub('\\b' + int2base(c, a) + '\\b', k[c], p)
    return p


def VIDEOWEED_decryptPlayerParams(w, i, s=None, e=None):
    lIll = 0
    ll1I = 0
    Il1l = 0
    ll1l = []
    l1lI = []
    while True:
        if lIll < 5:
            l1lI.append(w[lIll])
        elif lIll < len(w):
            ll1l.append(w[lIll])
        lIll += 1
        if ll1I < 5:
            l1lI.append(i[ll1I])
        elif ll1I < len(i):
            ll1l.append(i[ll1I])
        ll1I += 1
        if Il1l < 5:
            l1lI.append(s[Il1l])
        elif Il1l < len(s):
            ll1l.append(s[Il1l])
        Il1l += 1
        if len(w) + len(i) + len(s) + len(e) == len(ll1l) + len(l1lI) + len(e):
            break
    lI1l = ''.join(ll1l)
    I1lI = ''.join(l1lI)
    ll1I = 0
    l1ll = []

    lIll = 0
    while lIll < len(ll1l):
        ll11 = -1
        if ord(I1lI[ll1I]) % 2:
            ll11 = 1
        l1ll.append(JS_FromCharCode(int(lI1l[lIll:lIll + 2], 36) - ll11))
        ll1I += 1
        if ll1I >= len(l1lI):
            ll1I = 0

        lIll += 2
    return ''.join(l1ll)


def VIDEOWEED_decryptPlayerParams2(w, i, s=None, e=None):
    s = 0
    while s < len(w):
        i += JS_FromCharCode(int(w[s:s + 2], 36))
        s += 2
    return i


class captchaParser:
    def __init__(self):
        pass

    def textCaptcha(self, data):
        strTab = []
        valTab = []
        match = re.compile("padding-(.+?):(.+?)px;padding-top:.+?px;'>(.+?)<").findall(data)
        if len(match) > 0:
            for i in range(len(match)):
                value = match[i]
                strTab.append(value[2])
                strTab.append(int(value[1]))
                valTab.append(strTab)
                strTab = []
                if match[i][0] == 'left':
                    valTab.sort(key=lambda x: x[1], reverse=False)
                else:
                    valTab.sort(key=lambda x: x[1], reverse=True)
        return valTab

    def reCaptcha(self, data):
        pass


def decorateUrl(url, metaParams={}):
    retUrl = strwithmeta(url)
    retUrl.meta.update(metaParams)
    urlLower = url.lower()
    if 'iptv_proto' not in retUrl.meta:
        protocols = {
            'merge://': 'merge',
            '.m3u8': 'm3u8',
            '.f4m': 'f4m',
            'protocol=hls': 'm3u8',
            '.mpd': 'mpd',
            'rtmp': 'rtmp',
            'https': 'https',
            'http': 'http',
            'file': 'file',
            'rtsp': 'rtsp',
            'mms': 'mms',
            'mmsh': 'mmsh'
        }

        for key, value in protocols.items():
            if urlLower.startswith(key) or urlLower.split('?')[0].endswith(key):
                retUrl.meta['iptv_proto'] = value
                break
    return retUrl


def _hlsChannelsLabel(channels):
    # CHANNELS first value is the count, e.g. "2" or "6/JOC" (Atmos)
    try:
        n = int(str(channels).split('/')[0].strip())
    except Exception:
        return ''
    return {6: '5.1', 8: '7.1'}.get(n, '%dch' % n if n > 2 else '')


def _hlsCharacteristicsLabel(characteristics, forSubtitles=False):
    c = (characteristics or '').lower()
    tags = []
    if 'public.accessibility.describes-video' in c:
        tags.append('AD')
    if forSubtitles and ('transcribes-spoken-dialog' in c or 'describes-music-and-sound' in c):
        tags.append('SDH')
    return ' '.join(tags)


def _appendLabelTag(base, tag):
    # skip a tag the stream name already spells out (e.g. NAME="Deutsch AD")
    if tag and tag.lower() not in base.lower().split():
        return (base + ' ' + tag).strip()
    return base


def _hlsAudioLabel(audioStream):
    label = audioStream.name or getattr(audioStream, 'language', '') or 'audio'
    label = _appendLabelTag(label, _hlsChannelsLabel(getattr(audioStream, 'channels', None)))
    for tag in _hlsCharacteristicsLabel(getattr(audioStream, 'characteristics', None)).split():
        label = _appendLabelTag(label, tag)
    return label


def getDirectM3U8Playlist(M3U8Url, checkExt=True, variantCheck=True, cookieParams={}, checkContent=False, sortWithMaxBitrate=-1, mergeAltAudio=True):
    if checkExt and not M3U8Url.split('?', 1)[0].endswith('.m3u8'):
        return []
    cm = common()
    meta = strwithmeta(M3U8Url).meta
    params, postData = cm.getParamsFromUrlWithMeta(M3U8Url)
    params.update(cookieParams)
    retPlaylists = []
    try:
        finallM3U8Url = meta.get('iptv_m3u8_custom_base_link', '')
        if '' == finallM3U8Url:
            params['with_metadata'] = True
            sts, data = cm.getPage(M3U8Url, params, postData)
            finallM3U8Url = data.meta['url']
        else:
            sts, data = cm.getPage(M3U8Url, params, postData)
            data = data.strip()
        m3u8Obj = m3u8.inits(data, finallM3U8Url)
        if m3u8Obj.is_variant:
            # Merge SUBTITLES renditions declared in the master playlist into
            # external_sub_tracks (kept alongside any the caller already
            # passed). The player exposes them as "Download suggested".
            hlsSubTracks = []
            seenSubUrls = set()
            subMeta = dict((k, v) for k, v in meta.items() if k not in ('external_sub_tracks', 'iptv_proto', 'iptv_bitrate', 'iptv_m3u8_custom_base_link'))
            for playlist in m3u8Obj.playlists:
                for subStream in getattr(playlist, 'subtitle_streams', []):
                    try:
                        subUrl = subStream.absolute_uri
                    except Exception:
                        subUrl = ''
                    if not subUrl or subUrl in seenSubUrls:
                        continue
                    seenSubUrls.add(subUrl)
                    subTitle = subStream.name or subStream.language or 'HLS'
                    subTags = []
                    if getattr(subStream, 'forced', False) and 'forced' not in subTitle.lower():
                        subTags.append('forced')
                    for tag in _hlsCharacteristicsLabel(getattr(subStream, 'characteristics', None), forSubtitles=True).split():
                        if tag.lower() not in subTitle.lower():
                            subTags.append(tag)
                    if subTags:
                        subTitle = '%s (%s)' % (subTitle, ' '.join(subTags))
                    hlsSubTracks.append({'title': subTitle,
                                         'lang': subStream.language or '',
                                         'url': strwithmeta(subUrl, subMeta),
                                         'format': 'vtt'})
            if hlsSubTracks:
                meta['external_sub_tracks'] = list(meta.get('external_sub_tracks', [])) + hlsSubTracks
            for playlist in m3u8Obj.playlists:
                item = {}
                if not variantCheck or playlist.absolute_uri.split('?', 1)[0].endswith('.m3u8'):
                    meta.update({'iptv_proto': 'm3u8', 'iptv_bitrate': playlist.stream_info.bandwidth})
                    item['url'] = strwithmeta(playlist.absolute_uri, meta)
                else:
                    meta.pop('iptv_proto', None)
                    item['url'] = decorateUrl(playlist.absolute_uri, meta)

                item['bitrate'] = playlist.stream_info.bandwidth
                if None is not playlist.stream_info.resolution:
                    item['with'] = playlist.stream_info.resolution[0]
                    item['heigth'] = playlist.stream_info.resolution[1]
                else:
                    item['with'] = 0
                    item['heigth'] = 0

                item['width'] = item['with']
                item['height'] = item['heigth']
                try:
                    tmpCodecs = playlist.stream_info.codecs.split(',')
                    codecs = []
                    for c in tmpCodecs[::-1]:
                        codecs.append(c.split('.')[0].strip())
                        item['codecs'] = ','.join(codecs)
                except Exception:
                    item['codecs'] = ''
                item['name'] = "bitrate: %s res: %dx%d" % (item['bitrate'], item['width'], item['height'])
                if item['codecs']:
                    item['name'] += ' ' + item['codecs']
                try:
                    videoRange = playlist.stream_info.video_range
                    if videoRange and videoRange.upper() not in ('SDR', ''):
                        item['name'] += ' ' + videoRange
                    if playlist.stream_info.frame_rate:
                        item['name'] += ' %gfps' % float(playlist.stream_info.frame_rate)
                except Exception:
                    pass
                if mergeAltAudio and playlist.alt_audio_streams and item['url'].meta.get('iptv_proto') == 'm3u8':
                    for audio_stream in playlist.alt_audio_streams:
                        audioUrl = strwithmeta(audio_stream.absolute_uri, item['url'].meta)
                        altItem = dict(item)
                        altItem['name'] = '[%s] %s' % (_hlsAudioLabel(audio_stream), altItem['name'])
                        metaItem = dict(item['url'].meta)
                        metaItem.update({'audio_url': audioUrl, 'video_url': altItem['url'], 'ff_out_container': 'mpegts'})
                        altItem['url'] = decorateUrl("merge://audio_url|video_url", metaItem)
                        retPlaylists.append(altItem)
                else:
                    item['alt_audio_streams'] = playlist.alt_audio_streams
                    retPlaylists.append(item)
            if sortWithMaxBitrate > -1:
                def __getLinkQuality(itemLink):
                    try:
                        return int(itemLink['bitrate'])
                    except Exception:
                        printExc()
                        return 0

                retPlaylists = CSelOneLink(retPlaylists, __getLinkQuality, sortWithMaxBitrate).getSortedLinks()
        else:
            if checkContent and 0 == len(m3u8Obj.segments):
                return []
            # a media playlist that really has segments is HLS even when
            # its URL doesn't end in .m3u8 (e.g. .../master.txt, .../playlist?token=)
            # - without iptv_proto it would be buffered with wget as a plain file
            if len(m3u8Obj.segments) and meta.get('iptv_proto') not in ('m3u8', 'em3u8'):
                M3U8Url = strwithmeta(M3U8Url, dict(meta, iptv_proto='m3u8'))
            item = {'name': 'm3u8', 'url': M3U8Url, 'codec': 'unknown', 'with': 0, 'heigth': 0, 'width': 0, 'height': 0, 'bitrate': 'unknown'}
            retPlaylists.append(item)
    except Exception:
        printExc()
    return retPlaylists


def getF4MLinksWithMeta(manifestUrl, checkExt=True, cookieParams={}, sortWithMaxBitrate=-1):
    if checkExt and not manifestUrl.split('?')[0].endswith('.f4m'):
        return []
    cm = common()
    headerParams, postData = cm.getParamsFromUrlWithMeta(manifestUrl)
    headerParams.update(cookieParams)
    retPlaylists = []
    sts, data = cm.getPage(manifestUrl, headerParams, postData)
    if sts:
        liveStreamDetected = False
        if 'live' == CParsingHelper.getDataBeetwenMarkers(data, '<streamType>', '</streamType>', False)[1].strip():
            liveStreamDetected = True
        tmp = cm.ph.getDataBeetwenMarkers(data, '<manifest', '</manifest>')[1]
        baseUrl = cm.ph.getDataBeetwenReMarkers(tmp, re.compile('<baseURL[^>]*?>'), re.compile('</baseURL>'), False)[1].strip()
        printDBG("|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||| " + baseUrl)
        if baseUrl == '':
            baseUrl = manifestUrl
        tmp = cm.ph.getAllItemsBeetwenMarkers(tmp, '<media', '>')
        for item in tmp:
            link = cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+)['"]''')[0]
            if link != '':
                link = urljoin(baseUrl, link)
            if cm.isValidUrl(link):
                try:
                    bitrate = int(cm.ph.getSearchGroups(item, '''bitrate=['"]([^'^"]+)['"]''')[0])
                except Exception:
                    bitrate = 0
                retPlaylists.append({'name': '[f4m/hds] bitrate[%s]' % bitrate, 'bitrate': bitrate, 'url': link})
        if 0 == len(retPlaylists):
            bitrates = re.compile('bitrate="([0-9]+?)"').findall(data)
            for item in bitrates:
                link = strwithmeta(manifestUrl, {'iptv_proto': 'f4m', 'iptv_bitrate': item})
                if liveStreamDetected:
                    link.meta['iptv_livestream'] = True
                try:
                    bitrate = int(item)
                except Exception:
                    bitrate = 0
                retPlaylists.append({'name': '[f4m/hds] bitrate[%s]' % item, 'bitrate': bitrate, 'url': link})
        if 0 == len(retPlaylists):
            link = strwithmeta(manifestUrl, {'iptv_proto': 'f4m'})
            if liveStreamDetected:
                link.meta['iptv_livestream'] = True
            retPlaylists.append({'name': '[f4m/hds]', 'bitrate': 0, 'url': link})
        if sortWithMaxBitrate > -1:
            def __getLinkQuality(itemLink):
                try:
                    return int(itemLink['bitrate'])
                except Exception:
                    printExc()
                    return 0

            retPlaylists = CSelOneLink(retPlaylists, __getLinkQuality, sortWithMaxBitrate).getSortedLinks()
    return retPlaylists


def getMPDLinksWithMeta(manifestUrl, checkExt=True, cookieParams={}, sortWithMaxBandwidth=-1):
    if checkExt and not manifestUrl.split('?')[0].endswith('.mpd'):
        return []
    cm = common()

    def _getNumAttrib(data, name, default=0):
        try:
            return int(cm.ph.getSearchGroups(data, r'[\s]' + name + '''=['"]([^'^"]+?)['"]''')[0])
        except Exception:
            return default

    headerParams, postData = cm.getParamsFromUrlWithMeta(manifestUrl)
    headerParams.update(cookieParams)
    retPlaylists = []
    sts, data = cm.getPage(manifestUrl, headerParams, postData)
    if sts:
        liveStreamDetected = False
        if 'type="dynamic"' in data:
            liveStreamDetected = True
        representation = {'audio': [], 'video': []}
        tmp = cm.ph.getAllItemsBeetwenMarkers(data, "<Period", '</Period>', withMarkers=True)
        if len(tmp):
            data = tmp[-1]
        # TODO!!! select period based on duration
        data = cm.ph.getAllItemsBeetwenMarkers(data, "<AdaptationSet", '</AdaptationSet>', withMarkers=True)
        for item in data:
            type = ''
            if re.compile('''=['"]audio['"/]''').search(item):
                type = 'audio'
            elif re.compile('''=['"]video['"/]''').search(item):
                type = 'video'
            else:
                continue
            tmp = cm.ph.getAllItemsBeetwenMarkers(item, '<Representation', '>', withMarkers=True)
            for rep in tmp:
                repParam = {}
                repParam['bandwidth'] = _getNumAttrib(rep, 'bandwidth')
                repParam['codecs'] = cm.ph.getSearchGroups(rep, '''codecs=['"]([^'^"]+?)['"]''')[0]
                if '' == repParam['codecs']:
                    repParam['codecs'] = cm.ph.getSearchGroups(item, '''codecs=['"]([^'^"]+?)['"]''')[0]

                repParam['codecs'] = repParam['codecs'].split('.')[0]
                if 'vp9' in repParam['codecs']:
                    continue
                if type == 'video':
                    repParam['width'] = _getNumAttrib(rep, 'width')
                    if 0 == repParam['width']:
                        repParam['width'] = _getNumAttrib(item, 'width')

                    repParam['height'] = _getNumAttrib(rep, 'height')
                    if 0 == repParam['height']:
                        repParam['height'] = _getNumAttrib(item, 'height')

                    repParam['frame_rate'] = cm.ph.getSearchGroups(rep, '''frameRate=['"]([^'^"]+?)['"]''')[0]
                    if '' == repParam['frame_rate']:
                        repParam['frame_rate'] = cm.ph.getSearchGroups(item, '''frameRate=['"]([^'^"]+?)['"]''')[0]
                else:
                    repParam['lang'] = cm.ph.getSearchGroups(rep, '''lang=['"]([^'^"]+?)['"]''')[0]
                    if '' == repParam['lang']:
                        repParam['lang'] = cm.ph.getSearchGroups(item, '''lang=['"]([^'^"]+?)['"]''')[0]
                representation[type].append(repParam)
        audioIdx = 0
        for audio in representation['audio']:
            audioItem = {}
            audioItem['livestream'] = liveStreamDetected
            audioItem['codecs'] = audio['codecs']
            audioItem['bandwidth'] = audio['bandwidth']
            audioItem['lang'] = audio['lang']
            audioItem['audio_rep_idx'] = audioIdx
            if len(representation['video']):
                videoIdx = 0
                for video in representation['video']:
                    videoItem = dict(audioItem)
                    videoItem['codecs'] += ',' + video['codecs']
                    videoItem['bandwidth'] += video['bandwidth']
                    videoItem['width'] = video['width']
                    videoItem['height'] = video['height']
                    videoItem['frame_rate'] = video['frame_rate']
                    videoItem['name'] = "[%s] bitrate: %s %dx%d %s %sfps" % (videoItem['lang'],
                                                                             videoItem['bandwidth'],
                                                                             videoItem['width'],
                                                                             videoItem['height'],
                                                                             videoItem['codecs'],
                                                                             videoItem['frame_rate'])
                    videoItem['url'] = strwithmeta(manifestUrl, {'iptv_proto': 'mpd', 'iptv_audio_rep_idx': audioIdx, 'iptv_video_rep_idx': videoIdx, 'iptv_livestream': videoItem['livestream']})
                    retPlaylists.append(videoItem)
                    videoIdx += 1
            else:
                audioItem['name'] = "[%s] bandwidth: %s %s" % (audioItem['lang'],
                                                               audioItem['bandwidth'],
                                                               audioItem['codecs'])
                audioItem['url'] = strwithmeta(manifestUrl, {'iptv_proto': 'mpd', 'iptv_audio_rep_idx': audioIdx, 'iptv_livestream': audioItem['livestream']})
                retPlaylists.append(audioItem)
            audioIdx += 1
    if sortWithMaxBandwidth > -1:
        def __getLinkQuality(itemLink):
            try:
                return int(itemLink['bandwidth'])
            except Exception:
                printExc()
                return 0

        retPlaylists = CSelOneLink(retPlaylists, __getLinkQuality, sortWithMaxBandwidth).getSortedLinks()
    return retPlaylists
