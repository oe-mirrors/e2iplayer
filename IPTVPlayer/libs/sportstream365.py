# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
from datetime import datetime, timedelta
############################################

###################################################
# Config options for HOST
###################################################

config.plugins.iptvplayer.sportstream365_language = ConfigSelection(default="", choices=[("", _("Default")), ("de", "Deutsch"), ("en", "English"), ("es", "Español"), ("fr", "Français"), ("it", "Italiano"),
                                                                                             ("pt", "Português"), ("ru", "Русский"), ("tr", "Türkçe"), ("cn", "汉语")])
config.plugins.iptvplayer.sportstream365_cyrillic2latin = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_('Preferred language') + ": ", config.plugins.iptvplayer.sportstream365_language))
    optionList.append(getConfigListEntry(_('Cyrillic Latin Converter') + ": ", config.plugins.iptvplayer.sportstream365_cyrillic2latin))
    return optionList
###################################################

###################################################


class SportStream365Api(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'cookie': 'sportstream365.com.cookie'})
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='iphone_3_0')
        self.AJAX_HEADER = MergeDicts(self.HTTP_HEADER, {'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'ignore_http_code_ranges': [], 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_URL = 'http://sportstream365.com/'
        self.DEFAULT_ICON_URL = self.getFullUrl('/img/logo.png')
        self.lang = None

        OFFSET = datetime.now() - datetime.utcnow()
        seconds = OFFSET.seconds + OFFSET.days * 24 * 3600
        if ((seconds + 1) % 10) == 0:
            seconds += 1
        elif ((seconds - 1) % 10) == 0:
            seconds -= 1
        if seconds > 0:
            GMTOffset = '+' + str(timedelta(seconds=seconds))
        elif seconds < 0:
            GMTOffset = '-' + str(timedelta(seconds=seconds * -1))
        else:
            GMTOffset = ''

        while GMTOffset.endswith(':00'):
            GMTOffset = GMTOffset.rsplit(':', 1)[0]
        self.GMTOffset = GMTOffset
        # https://en.wikipedia.org/wiki/Cyrillic_alphabets#Common_letters
        cyrillicAlphabets = [(u'а', 'a'), (u'б', 'b'), (u'в', 'v'), (u'г', 'ɡ'), (u'д', 'd'), (u'е', 'je'), (u'ж', 'ʒ'), (u'з', 'z'), (u'и', 'i'), (u'й', 'j'), (u'к', 'k'), (u'л', 'l'), (u'м', 'm'), (u'н', 'n'), (u'о', 'o'), (u'п', 'p'), (u'с', 's'), (u'т', 't'), (u'у', 'u'), (u'ф', 'f'), (u'х', 'x'), (u'ц', 'ts'), (u'ч', 'tʃ'), (u'ш', 'ʃ'), (u'щ', 'ʃtʃ'), (u'ь', 'ʲ'), (u'ю', 'ju'), (u'я', 'ja')]
        self.cyrillic2LatinMap = {}
        for item in cyrillicAlphabets:
            self.cyrillic2LatinMap[item[0]] = item[1]
        for item in cyrillicAlphabets:
            self.cyrillic2LatinMap[item[0].upper()] = item[1].upper()

    def cleanHtmlStr(self, text):
        text = CBaseHostClass.cleanHtmlStr(text)
        if config.plugins.iptvplayer.sportstream365_cyrillic2latin.value:
            tmp = text.decode('utf-8')
            text = ''
            for letter in tmp:
                text += self.cyrillic2LatinMap.get(letter, letter)
            text = text.encode('utf-8')
        return text

    def getList(self, cItem):
        printDBG("SportStream365Api.getList cItem[%s]" % cItem)
        channelsList = []

        if self.lang != config.plugins.iptvplayer.sportstream365_language.value:
            self.lang = config.plugins.iptvplayer.sportstream365_language.value
            lang = self.lang
            if lang == '':
                userLang = GetDefaultLang()
                if userLang in ['de', 'en', 'es', 'fr', 'it', 'pt', 'ru', 'tr', 'cn']:
                    lang = userLang
            if lang != '':
                self.defaultParams['cookie_items'] = {'lng': lang}
            else:
                self.defaultParams['cookie_items'] = {'lng': 'en'} #self.defaultParams.pop('cookie_items', None)

        category = cItem.get('priv_cat')
        if category == None:
            sts, data = self.cm.getPage(self.getMainUrl(), self.defaultParams)
            if not sts:
                return []
            self.setMainUrl(self.cm.meta['url'])
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'modal_menu_filter'), ('</div', '>'))[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0]
                icon = url.rsplit('/', 1)[-1]
                if icon == '':
                    icon = 'all'
                elif 'tennis' in icon:
                    icon = 'footballtennis'
                elif 'formula' in icon:
                    icon = 'f1'
                icon = self.getFullIconUrl('/img/%s.jpg' % icon)
                title = self.cleanHtmlStr(item)
                channelsList.append({'name': 'sportstream365.com', 'type': 'dir', 'priv_cat': 'list_items', 'title': title, 'url': self.getFullUrl(url), 'icon': icon})
        else:
            iconsMap = {0: 'other', 1: 'football', 2: 'hockey', 3: 'basketball', 6: 'volleyball', 26: 'f1', 4: 'footballtennis', 9: 'boxing'}
            sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
            if not sts:
                return []

            allowSports = self.cm.ph.getSearchGroups(data, '''var\s+?allow_sports\s*=\s*['"]([^'^"]+?)['"]''')[0]
            tagz = self.cm.ph.getSearchGroups(data, '''var\s+?tagz\s*=\s*['"]([^'^"]+?)['"]''')[0]

            try:
                from Plugins.Extensions.IPTVPlayer.libs import websocket

                lang = self.defaultParams['cookie_items']['lng']
                for i in range(3):
                    url = self.getFullUrl('/signcon/negotiate')
                    sts, data = self.cm.getPage(url, MergeDicts(self.defaultParams, {'header': self.AJAX_HEADER, 'raw_post_data': True}), post_data='')
                    if not sts:
                        return []

                    data = json_loads(data)
                    uri = 'ws:' + self.getFullUrl('/signcon?id=').split(':', 1)[-1] + data['connectionId']

                    printDBG("URI: %s" % uri)

                    ws1 = websocket.create_connection(uri)
                    ws1.send('{"protocol":"json","version":1}\x1E')
                    ws1.send('{"arguments":[{"partner":2,"lng":"%s","typegame":3}],"invocationId":"0","target":"ConnectClient","type":1}\x1E' % lang) # 
                    ws1.send('{"arguments":["%s","en",24],"invocationId":"1","target":"GetFeed","type":1}\x1E' % allowSports)
                    ws1.send('{"arguments":["%s","en",24],"invocationId":"2","target":"GetFeed","type":1}\x1E' % allowSports)

                    for j in range(4):
                        data = ws1.recv()
                        printDBG(data)
                        if 'updateFeed' in data:
                            break
                    ws1.close()
                    try:
                        data = json_loads(data.split('\x1E', 1)[0])
                    except Exception:
                        printExc()
                        continue
                    break

                parseInt = lambda sin: int(''.join([c for c in str(sin).replace(',', '.').split('.')[0] if c.isdigit()])) if sum(map(int, [s.isdigit() for s in str(sin)])) and not callable(sin) and str(sin)[0].isdigit() else 0

                def parseInt2(string):
                    try:
                        return int(''.join([x for x in string if x.isdigit()]))
                    except Exception:
                        return 0

                def cmp(x, y):
                    if x['SportId'] != y['SportId']:
                        return parseInt(x['SportId']) - parseInt(y['SportId'])
                    elif x['Liga'] != y['Liga']:
                        try:
                            int(x['Liga']) - int(y['Liga'])
                        except Exception:
                            return 0
                    else:
                        return parseInt(x['FirstGameId']) - parseInt(y['FirstGameId'])

                data = json_loads(data['arguments'][0])['Value']
                data.sort(cmp=cmp) #key = lambda item: (parseInt(item['SportId']), item['Liga'], parseInt(item['FirstGameId']))
                printDBG(data)
                for item in data:
                    if None == item.get('VI'):
                        continue
                    url = self.getFullUrl('/viewer?sport=%s&game=%s&tagz=%s' % (item['SportId'], item['FirstGameId'], tagz))
                    icon = self.getFullIconUrl('/img/flag_%s.png' % iconsMap.get(item['SportId'], 'other'))
                    title = []
                    if item['Opp1'] != '':
                        title.append(item['Opp1'])
                    if item['Opp2'] != '':
                        title.append(item['Opp2'])
                    title = ' - '.join(title)
                    if title == '':
                        title = item['Liga']
                    desc = item['Liga']
                    desc += '[/br]' + datetime.fromtimestamp(int(item['Start'] / 1000)).strftime('%A, %-d %B %H:%M')
                    if self.GMTOffset != '':
                        desc += ' (GMT %s)' % self.GMTOffset
                    channelsList.append({'name': 'sportstream365.com', 'type': 'video', 'title': self.cleanHtmlStr(title), 'url': url, 'icon': icon, 'desc': self.cleanHtmlStr(desc)})
            except Exception:
                printExc()

        return channelsList

    def getVideoLink(self, cItem):
        printDBG("SportStream365Api.getVideoLink cItem[%s]" % cItem)
        return self.up.getVideoLinkExt(cItem.get('url', ''))
