# -*- coding: utf-8 -*-
#
import urllib
try:
    import json
except Exception:
    import simplejson as json

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang


class SuggestionsProvider:

    def __init__(self, forYouyube=False):
        self.cm = common()
        self.forYouyube = forYouyube

    def getName(self):
        return _("Youtube Suggestions") if self.forYouyube else _("Google Suggestions")

    def getSuggestions(self, text, locale):
        lang = locale.split('-', 1)[0]
        url = 'http://suggestqueries.google.com/complete/search?output=firefox&hl=%s&gl=%s%s&q=%s' % (lang, lang, '&ds=yt' if self.forYouyube else '', urllib.quote(text))
        sts, data = self.cm.getPage(url)
        if sts:
            retList = []
            for item in json.loads(data)[1]:
                retList.append(item.encode('UTF-8'))

            return retList
        return None
