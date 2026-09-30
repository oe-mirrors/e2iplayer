# -*- coding: utf-8 -*-
#
import json

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG

from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote


class SuggestionsProvider:

    def __init__(self):
        self.cm = common()

    def getName(self):
        return _("IMDb Suggestions")

    def getSuggestions(self, text, locale):
        text = text.strip().lower()
        if len(text) > 2:
            # v3 API: plain JSON and any text (umlauts, other scripts). The
            # text used to be cut down to its ASCII characters first, so
            # "münchen" was looked up as "mnchen". The first path part is
            # the query's first character ('x' works for everything else).
            first = text[0] if text[0] in 'abcdefghijklmnopqrstuvwxyz0123456789' else 'x'
            url = 'https://v3.sg.media-imdb.com/suggestion/%s/%s.json' % (first, urllib_quote(text))
            sts, data = self.cm.getPage(url)
            if sts:
                printDBG(data)
                retList = []
                for item in json.loads(data).get('d', []):
                    # titles only (ids tt...), no people - like the old
                    # "suggests/titles" API
                    if str(item.get('id', '')).startswith('tt') and item.get('l'):
                        retList.append(ensure_str(item['l']))
                return retList
        return None
