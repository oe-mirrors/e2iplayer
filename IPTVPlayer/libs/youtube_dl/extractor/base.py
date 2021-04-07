# -*- coding: utf-8 -*-

from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import *
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
import re

NO_DEFAULT = None
compiled_regex_type = type(re.compile(''))

class InfoExtractor():
    
    def __init__(self):
        self.cm = common()
    
    def _download_webpage(self, url, a=None, note='', errnote='', fatal=True, params={}, data=None):
        sts, data = self.cm.getPage(url, params, data)
        return data
            
    def _download_json(self, url, video_id, note='', errnote='', fatal=True, params={}):
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return None
        if fatal:
            data = json_loads(data)
        else:
            try:
                data = json_loads(data)
            except Exception:
                printExc()
                data = None
        return data
        
    def xmlGetArg(self, data, name):
        return self.cm.ph.getDataBeetwenMarkers(data, '%s="' % name, '"', False)[1]
        
    def xmlGetText(self, data, name, withMarkers=False):
        return self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<%s[^>]*?>' % name), re.compile('</%s>' % name), withMarkers)[1]
        
    def xmlGetAllNodes(self, data, name):
        nodes = self.cm.ph.getAllItemsBeetwenMarkers(data, '<' + name, '</%s>' % name)
        if 0 == len(nodes):
            nodes = self.cm.ph.getAllItemsBeetwenMarkers(data, '<' + name, '/>')
        return nodes
        
    def _search_regex(self, pattern, string, name, default=NO_DEFAULT, fatal=True, flags=0, group=None):
        """
        Perform a regex search on the given string, using a single or a list of
        patterns returning the first matching group.
        In case of failure return a default value or raise a WARNING or a
        RegexNotFoundError, depending on fatal, specifying the field name.
        """
        if isinstance(pattern, (str, compat_str, compiled_regex_type)):
            mobj = re.search(pattern, string, flags)
        else:
            for p in pattern:
                mobj = re.search(p, string, flags)
                if mobj:
                    break

        _name = name

        if mobj:
            if group is None:
                # return the first matching group
                return next(g for g in mobj.groups() if g is not None)
            else:
                return mobj.group(group)
        elif default is not NO_DEFAULT:
            return default
        elif fatal:
            raise RegexNotFoundError('Unable to extract %s' % _name)
        else:
            return None
            
    def _extract_m3u8_formats(self, m3u8_url, *args, **kwargs):
        formats = []
        tmpTab = getDirectM3U8Playlist(m3u8_url, False)
        for tmp in tmpTab:
            tmp['format_id'] = tmp['name']
            formats.append(tmp)
        return formats
    
