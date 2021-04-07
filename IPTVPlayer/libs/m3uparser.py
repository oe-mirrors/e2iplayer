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
    type = 0 # 0 - key, 1 - start val, 2 - end val
    key = ''
    val = ''
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
            elif txt[idx] == '"':
                type = 2
            else:
                printDBG("ERROR parsing VALUE txt[%s]\n" % txt)
                break
        elif type == 2:
            if txt[idx] != '"':
                val += txt[idx]
            else:
                attribs[key.strip()] = val
                key = ''
                val = ''
                type = 0
    return attribs

def ParseM3u(data):
    printDBG('ParseM3u')
    list = []
    data = data.replace("\r", "\n").replace('\n\n', '\n').split('\n')
    printDBG("ParseM3u: data0[%s]" % data[0])
    if '#EXT' not in data[0]:
        return list
    params = {'title': '', 'length': '', 'uri': ''}
    for line in data:
        line = line.strip()
        printDBG(line)
        if line.startswith('#EXTINF:'):
            tmp = line[8:].split(',', 1)
            params = {'f_type': 'inf', 'title': tmp[-1].strip(), 'length': '', 'uri': ''}
            params.update(GetM3uAttribs(tmp[0], True))
        elif line.startswith('#EXTIMPORT:'):
            tmp = line[11:].split(',', 1)
            params = {'f_type': 'import', 'title': tmp[-1].strip(), 'length': '', 'uri': ''}
            params.update(GetM3uAttribs(tmp[0], True))
        elif line.startswith('#EXTGRP:'):
            params['group-title'] = line[8:].strip()
        elif line.startswith('#EXTVLCOPT:'):
            tmp = line[11:].split(',')
            for it in tmp:
                it = it.split('=')
                if len(it) != 2:
                    continue
                it[0] = it[0].lower() # key
                for m in [("program", 'program-id'), ('http-user-agent', 'user_agent')]:
                    if it[0] == m[0]:
                        params[m[1]] = it[1]
        elif not line.startswith('#'):
            if '' != params['title']:
                line = line.replace('rtmp://$OPT:rtmp-raw=', '')
                cTitle = re.sub('\[[^\]]*?\]', '', params['title'])
                if len(cTitle):
                    params['title'] = cTitle
                params['uri'] = urlparser.decorateParamsFromUrl(line)
                list.append(params)
            params = {'title': '', 'length': '', 'uri': ''}
    return list
