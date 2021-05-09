# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

import re
import urllib


class BeinmatchApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://www.beinmatch.com/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/assets/images/bim/logo.png')
        self.HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader(browser='chrome'), {'Referer': self.getMainUrl()})
        self.http_params = {'header': self.HTTP_HEADER}
        self.getLinkJS = ''

        self.TRANSLATED_NAMES = {
        'أستون فيلا': 'Aston Villa F.C.',
        'أنغولا': 'Angola',
        'أوروجواي': 'Uruguay',
        'أوغندا': 'Uganda',
        'الأرجنتين': 'Argentina',
        'الإكوادور': 'Ecuador',
        'البرازيل': 'Brazil',
        'الجزائر': 'Algeria',
        'الجزيرة - الأردن': 'Al Jazeera',
        'الجيش': 'Army',
        'السنغال': 'Senegal',
        'العهد': '',
        'الكاميرون': 'Cameroon',
        'المغرب': 'Morocco',
        'الوحدات': 'Al-Wehdat',
        'اليابان': 'Japan',
        'انتر ميلان': 'Internazionale',
        'باراجواي': 'Paraguay',
        'برادفورد سيتي': 'Bradford City A.F.C.',
        'برشلونة': 'Barcelona',
        'بنين': 'Benin',
        'بوروندي': 'Burundi',
        'بوليفيا': 'Bolivia',
        'بيرو': 'Peru',
        'تشيلسي': 'Chelsea F.C.',
        'تشيلي': 'Chile',
        'تنزانيا': 'Tanzania',
        'توتنهام هوتسبير': 'Tottenham Hotspur F.C.',
        'تورنتو رابترز': 'Toronto Raptors',
        'تونس': 'Tunisia',
        'جمهورية الكونغو الديموقراطية': 'Democratic Republic of the Congo',
        'جنوب أفريقيا': 'South Africa',
        'رافاييل نادال': 'Rafael Nadal',
        'روبرتو باوتيستا أغوت': 'Roberto Bautista Agut',
        'روجر فيدرر': 'Roger Federer',
        'زامبيا': 'Zambia',
        'زيمبابوي': 'Zimbabwe',
        'ساحل العاج': 'Ivory Coast',
        'سيرينا ويليامز': 'Serena Williams',
        'سيمونا هاليب': 'Simona Halep',
        'غانا': 'Ghana',
        'غولدن ستيت واريورز': '',
        'غينيا': 'Guinea',
        'غينيا بيساو': 'Guinea-Bissau',
        'فنزويلا': 'Venezuela',
        'قطر': 'Qatar',
        'كولومبيا': 'Colombia',
        'كينيا': 'Kenya',
        'لوغانو': 'Lugano',
        'ليستر سيتي': 'Leicester City F.C.',
        'ليفربول': 'Liverpool',
        'مالي': 'Mali',
        'مانشستر سيتي': 'Manchester City F.C.',
        'مانشستر يونايتد': 'Manchester United F.C.',
        'مدغشقر': 'Madagascar',
        'مصر': 'Egypt',
        'موريتانيا': 'Mauritania',
        'نامبيا': 'Namibia',
        'نوريتش سيتي': 'Norwich City F.C.',
        'نوفاك جوكوفيتش': 'Novak Djokovic',
        'نيجيريا': 'Nigeria',
        'نيوكاسل يونايتد': 'Newcastle United F.C.',
        'وست هام يونايتد': 'West Ham United F.C.',
        'وولفرهامبتون': 'Wolverhampton',
        'آرسنال': 'Arsenal F.C.',
        'أتلتيك بيلباو': 'Athletic Bilbao',
        'الأهلي المصري': 'Al Ahly SC',
        'الدوري الألماني': 'Bundesliga',
        'الدوري الإسباني': 'La Liga',
        'الدوري الإنجليزي الممتاز': 'Premier League',
        'بايرن ميونيخ': 'FC Bayern Munich',
        'بطولة ويمبلدون للتنس': 'Wimbledon',
        'ريال مدريد': 'Real Madrid CF',
        'سيلتا فيغو': 'RC Celta de Vigo',
        'كأس الأمم الأفريقية': 'Africa Cup of Nations',
        'كأس السوبر الأوروبي': 'UEFA Super Cup',
        'كأس جوهان غامبر': '',
        'كأس مصر': 'Egypt Cup',
        'بيرنلي': 'Burnley',
        'ساوثهامتون': 'Southampton FC',
        'بيراميدز': 'Pyramids F.C.'
        }

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.http_params)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def translateTeamNames(self, name):
        name2 = ''
        if name in self.TRANSLATED_NAMES:
            name2 = self.TRANSLATED_NAMES[name]
            printDBG("found in list")
        else:
            # try wikipedia for translation
            url = "https://ar.wikipedia.org/wiki/" + name.replace(" ", "_")

            sts, data = self.cm.getPage(url)
            if sts:
                text = re.findall("(<a[^>]+>English</a>)", data)
                if text:
                    #printDBG(text[0])
                    name2 = re.findall("wiki/(.*?)\"", text[0])
                    if name2:
                        #printDBG(name2[0])
                        name2 = urllib.unquote(name2[0].replace("_", " "))

            self.TRANSLATED_NAMES[name] = name2
        return name2

    def getList(self, cItem):
        printDBG("BeinmatchApi.getChannelsList")

        channelsTab = []
        for v in range(0, 50, 5):
            url = "http://www.beinmatch.com/home/videos/{0}".format(v)

            sts, data = self.getPage(url, self.http_params)
            if not sts:
                continue
            self.setMainUrl(self.cm.meta['url'])

            tmp = ph.findall(data, ('<script', '>', ph.check(ph.none, ('src=',))), '</script>', flags=0)
            for item in tmp:
                if 'goToMatch' in item:
                    self.getLinkJS = item
                    break

            if not self.getLinkJS:
                self.sessionEx.waitForFinishOpen(MessageBox, _('Data for link generation could not be found.\nPlease report this problem to %s') % 'iptvplayere2@gmail.com', type=MessageBox.TYPE_ERROR, timeout=10)

            data = ph.find(data, ('<table', '>', 'tabIndex'), ('<div', '>', 'Side'))[1]
            data = ph.rfindall(data, '</tr>', ('<table', '>', 'tabIndex'))
            for item in data:
                #printDBG("+++++++++++++++++++++++++++++++++++++++++")
                #printDBG(item)
                #printDBG("+++++++++++++++++++++++++++++++++++++++++")
                icon = self.getFullIconUrl(ph.find(item, 'url(', ')', flags=0)[1].strip())
                teams_ar = ph.findall(item, ('<td', '>', 'tdTeam'), '</td>', flags=0)
                teams_en = []
                for n in teams_ar:
                    team_en = self.translateTeamNames(n)
                    teams_en.append(team_en)
                    printDBG("translated {'%s': '%s'}" % (n, team_en))
                if len(teams_en) == 2:
                    title = ph.clean_html(' vs '.join(teams_ar)) + " [ %s vs %s ] " % (_(teams_en[0]), _(teams_en[1]))
                else:
                    title = ph.clean_html(' vs '.join(teams_ar))
                url = ph.getattr(item, 'onclick')
                desc = ph.clean_html(ph.find(item, ('<td', '>', 'compStl'), '</td>', flags=0)[1])
                desc_en = self.translateTeamNames(desc)
                printDBG("translated {'%s': '%s'}" % (desc, desc_en))
                if desc_en:
                    desc = desc + "  -  " + desc_en
                channelsTab.append(MergeDicts(cItem, {'type': 'video', 'title': title, 'url': url, 'icon': icon, 'desc': desc}))

        return channelsTab

    def getVideoLink(self, cItem):
        printDBG("BeinmatchApi.getVideoLink")
        urlsTab = []

        jscode = ['window={open:function(){print(JSON.stringify(arguments));}};', self.getLinkJS, cItem['url']]
        ret = js_execute('\n'.join(jscode))
        try:
            data = json_loads(ret['data'])
            url = self.getFullUrl(data['0'])
        except Exception:
            printExc()
            return urlsTab

        sts, data = self.getPage(url, self.http_params)
        if not sts:
            return urlsTab
        cUrl = self.cm.meta['url']
        printDBG(data)
        url = self.getFullUrl(ph.search(data, '''['"]([^'^"]+?\.m3u8(?:\?[^'^"]*?)?)['"]''')[0], cUrl)
        if url:
            url = strwithmeta(url, {'Referer': cUrl, 'Origin': self.cm.getBaseUrl(cUrl)[:-1], 'User-Agent': self.HTTP_HEADER['User-Agent']})
            return getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999)
        data = ph.find(data, ('<div', '>', 'video-container'), '</div>', flags=0)[1]
        url = self.getFullUrl(ph.search(data, ph.IFRAME)[1])
        if 0 == self.up.checkHostSupport(url):
            sts, data = self.getPage(url, self.http_params)
            if not sts:
                return urlsTab
            url = self.getFullUrl(ph.search(data, ph.IFRAME)[1])
        return self.up.getVideoLinkExt(url)
