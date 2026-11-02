# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetM3uAttribs(txt, firstKeyAsLength=False):
    attribs = {}
    type = 0  # 0 - key, 1 - start val, 2 - end val, 3 - end of a val without quotes
    key = ''
    val = ''
    quote = '"'
    if firstKeyAsLength:
        txt = txt.strip()
    for idx in range(len(txt)):
        if type == 0:
            if txt[idx] == ' ' and attribs == {} and firstKeyAsLength:
                attribs['length'] = key.strip()
                key = ''
            elif txt[idx] == '=':
                type = 1
            else:
                key += txt[idx]
        elif type == 1:
            if txt[idx] == ' ':
                continue
            elif txt[idx] in '"\'':
                quote = txt[idx]
                type = 2
            else:
                val = txt[idx]
                type = 3
        elif type == 2:
            if txt[idx] != quote:
                val += txt[idx]
            else:
                attribs[key.strip()] = val
                key = ''
                val = ''
                type = 0
        elif type == 3:
            if txt[idx] != ' ':
                val += txt[idx]
            else:
                attribs[key.strip()] = val
                key = ''
                val = ''
                type = 0
    if type == 3:
        attribs[key.strip()] = val
    elif type == 0 and attribs == {} and firstKeyAsLength and key.strip():
        attribs['length'] = key.strip()
    return attribs


def SplitExtInf(txt):
    # attributes, title: the title starts behind the first comma outside a quoted attribute value
    quote = ''
    for idx in range(len(txt)):
        if quote:
            if txt[idx] == quote:
                quote = ''
        elif txt[idx] == '"' or (txt[idx] == "'" and txt[idx - 1:idx] == '='):
            quote = txt[idx]
        elif txt[idx] == ',':
            return txt[:idx], txt[idx + 1:]
    # a stray quote
    tmp = txt.split(',', 1)
    return tmp[0], tmp[-1]


def TitleFromUri(uri):
    name = uri.split('|')[0].split('?')[0].replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]
    return name.replace('%20', ' ') or uri


def ParseM3u(data, allowPlain=False):
    # allowPlain: a list without the #EXTM3U header is accepted too (own files, a web page must not become a list)
    printDBG('ParseM3u')
    list = []
    data = data.lstrip().replace("\r", "\n").replace('\n\n', '\n').split('\n')
    printDBG("ParseM3u: data0[%s]" % data[0])
    if '#EXT' not in data[0] and not allowPlain:
        return list
    params = {'f_type': 'inf', 'title': '', 'length': '', 'uri': ''}
    for line in data:
        line = line.strip()
        printDBG(line)
        if not line:
            continue
        if line.startswith('#EXTINF:'):
            attribs, title = SplitExtInf(line[8:])
            params = {'f_type': 'inf', 'title': title.strip(), 'length': '', 'uri': ''}
            params.update(GetM3uAttribs(attribs, True))
        elif line.startswith('#EXTIMPORT:'):
            attribs, title = SplitExtInf(line[11:])
            params = {'f_type': 'import', 'title': title.strip(), 'length': '', 'uri': ''}
            params.update(GetM3uAttribs(attribs, True))
        elif line.startswith('#EXTGRP:'):
            params['group-title'] = line[8:].strip()
        elif line.startswith('#EXTVLCOPT:'):
            # the whole rest is the value: a User-Agent holds commas and = signs
            it = line[11:].split('=', 1)
            key = it[0].strip().lower()
            if len(it) == 2 and key in ('http-user-agent', 'http-referrer'):
                params['user_agent' if key == 'http-user-agent' else 'referer'] = it[1].strip().strip('"')
                continue
            tmp = line[11:].split(',')
            for it in tmp:
                it = it.split('=')
                if len(it) != 2:
                    continue
                if it[0].lower() == 'program':
                    params['program-id'] = it[1]
        elif not line.startswith('#'):
            line = line.replace('rtmp://$OPT:rtmp-raw=', '')
            if '' == params['title']:
                params['title'] = TitleFromUri(line)
            cTitle = re.sub(r'\[[^\]]*?\]', '', params['title'])
            if len(cTitle):
                params['title'] = cTitle
            params['uri'] = urlparser.decorateParamsFromUrl(line)
            list.append(params)
            params = {'f_type': 'inf', 'title': '', 'length': '', 'uri': ''}
    return list
