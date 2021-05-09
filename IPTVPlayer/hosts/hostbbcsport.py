# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm

# needed for option bbc_use_web_proxy definition
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.bbc import BBCCoUkIE
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
from datetime import datetime, timedelta
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.bbc_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.bbc_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use web-proxy (it may be illegal):"), config.plugins.iptvplayer.bbc_use_web_proxy))
    # there is no support to login when web-proxy option is used
    if not config.plugins.iptvplayer.bbc_use_web_proxy.value:
        optionList.append(getConfigListEntry(_("e-mail") + ":", config.plugins.iptvplayer.bbc_login))
        optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.bbc_password))

    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.bbc_default_quality))
    optionList.append(getConfigListEntry(_("Use default video quality:"), config.plugins.iptvplayer.bbc_use_default_quality))
    optionList.append(getConfigListEntry(_("Preferred format:"), config.plugins.iptvplayer.bbc_prefered_format))
    return optionList
###################################################


def gettytul():
    return 'https://www.bbc.co.uk/sport'


class BBCSport(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'bbc.com.sport', 'cookie': 'bbc.com.sport.cookie'})
        self.MAIN_URL = 'https://www.bbc.co.uk/'
        self.DEFAULT_ICON_URL = 'https://pbs.twimg.com/profile_images/878266143571443712/goIG59xP_400x400.jpg'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'with_metadata': True, 'ignore_http_code_ranges': [], 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.loggedIn = None
        self.login = ''
        self.password = ''

        self.sessionUrl = "https://session.bbc.com/session"
        self.liveGuideItemsCache = {}

        self.OFFSET = datetime.now() - datetime.utcnow()
        seconds = self.OFFSET.seconds + self.OFFSET.days * 24 * 3600
        if ((seconds + 1) % 10) == 0:
            seconds += 1
        elif ((seconds - 1) % 10) == 0:
            seconds -= 1
        self.OFFSET = timedelta(seconds=seconds)

        self.ABBREVIATED_DAYS_NAME_TAB = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    def _str2date(self, txt):
        txt = self.cm.ph.getSearchGroups(txt, '([0-9]+\-[0-9]+\-[0-9]+T[0-9]+\:[0-9]+:[0-9]+)')[0]
        return datetime.strptime(txt, '%Y-%m-%dT%H:%M:%S')

    def _gmt2local(self, txt):
        utc_date = self._str2date(txt)
        utc_date = utc_date + self.OFFSET
        if utc_date.time().second == 59:
            utc_date = utc_date + timedelta(0, 1)
        return utc_date

    def _absTimeDelta(self, d1, d2, div=60):
        if d1 > d2:
            td = d1 - d2
        else:
            td = d2 - d1
        return (td.seconds + td.days * 24 * 3600) / div

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def getFullIconUrl(self, icon, baseUrl=None):
        return CBaseHostClass.getFullIconUrl(self, icon, baseUrl).replace('/$recipe/', '/480x270_b/')

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        return self.cm.getPage(url, addParams, post_data)

    def listMainMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("BBCSport.listMainMenu")

        url = self.getFullUrl('/sport')
        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        liveguideData = self.cm.ph.getDataBeetwenNodes(data, ('<aside', '</aside>', 'liveguide'), ('<div', '</div>'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(liveguideData, '''\ssrc=['"]([^"^']+?\.(?:jpe?g|png)(?:\?[^"^']+?)?)['"]''')[0])
        url = self.getFullUrl(self.cm.ph.getSearchGroups(liveguideData, '''\shref=['"]([^"^']+?)['"]''')[0])
        if url != '':
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(liveguideData, 'alt="([^"]+?)"')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(liveguideData, ('<p', '>', 'summary'), ('</p', '>'), False)[1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'live_guide', 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'primary-nav'), ('</nav', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            if '/my-sport' in url:
                continue

            if '/all-sports' in url:
                category = nextCategory2
            else:
                category = nextCategory1

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': category, 'title': title, 'url': url})
            self.addDir(params)

        #MAIN_CAT_TAB = [{'category':'list_items', 'title': 'Start',    'url':self.getFullUrl('/sport')},
        #                {'category':'list_items', 'title': 'Golf',     'url':self.getFullUrl('/sport/golf')},]
        #self.listsTab(MAIN_CAT_TAB, cItem)

    def listAllItems(self, cItem, nextCategory):
        printDBG("BBCSport.listAllItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'list-item'), ('</li', '>'), False)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listLiveGuideMenu(self, cItem, nextCategory):
        printDBG("BBCSport.listLiveGuideMenu")
        self.liveGuideItemsCache = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        mediaDataTab = []

        mediaData = ''
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '.setPayload(', '</script>', False)
        for item in tmp:
            if '"promoted"' in item:
                mediaData = item
                break

        mediaData = self.cm.ph.getDataBeetwenMarkers(mediaData, '"body":{', '});', False)[1].strip()[:-1]
        try:
            mediaData = byteify(json.loads('{%s}' % mediaData), '', True)
            for item in [{'key': 'promoted', 'title': _('Promoted')}, {'key': 'live', 'title': _('Live')}, {'key': 'coming_up', 'title': _('Coming up')}, {'key': 'catch_up', 'title': _('Catch up')}]:
                try:
                    if isinstance(mediaData[item['key']], list) and len(mediaData[item['key']]):
                        self.liveGuideItemsCache[item['key']] = mediaData[item['key']]
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': item['title'], 'f_key': item['key']})
                        self.addDir(params)
                except Exception:
                    printExc()
        except Exception:
            printExc()

    def listLiveGuideItems(self, cItem, nextCategory):
        printDBG("BBCSport.listLiveGuideItems")
        try:
            NOW = datetime.now()
            for datItem in self.liveGuideItemsCache[cItem['f_key']]:
                sDate = self._gmt2local(datItem['scheduledStartTime'])

                if (datItem['hasAudio'] or datItem['hasVideo']) and (datItem['status'] != 'COMING_UP'):  #NOW > sDate or self._absTimeDelta(NOW, sDate, 60) < 6
                    for item in datItem['media']:
                        if 'identifiers' not in item or 'playablePid' not in item['identifiers']:
                            continue
                        vpid = item['identifiers']['playablePid']
                        if vpid == '':
                            continue
                        url = self.getFullUrl('/iplayer/vpid/%s/' % vpid)
                        icon = self.getFullIconUrl(item['coverImage'])
                        title = self.cleanHtmlStr(item['title'])
                        mediaType = item['mediaType']

                        if 'COMING_SOON' in item['status']:
                            continue

                        desc = [datItem['sectionName'], item['status']]
                        if 'schedule' in item and 'formattedStartTime' in item['schedule']:
                            desc.append('%s-%s' % (item['schedule']['formattedStartTime'], item['schedule']['formattedEndTime']))
                        h = self.cm.ph.getSearchGroups(item.get('duration', ''), '''([0-9]+)H''')[0]
                        if h == '':
                            h = '0'
                        m = self.cm.ph.getSearchGroups(item.get('duration', ''), '''([0-9]+)M''')[0]
                        if m == '':
                            m = '0'
                        if m != '0' or h != '0':
                            desc.append(str(timedelta(hours=int(h), minutes=int(m))))
                        desc = [' | '.join(desc)]
                        desc.append(self.cleanHtmlStr(item['summary']))

                        params = dict(cItem)
                        params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                        if mediaType == 'video':
                            self.addVideo(params)
                        elif mediaType == 'audio':
                            self.addAudio(params)
                        else:
                            printDBG("Unknown media type\n%s\n>>>>" % mediaType)
                else:
                    url = self.getFullUrl(datItem['url'])
                    title = self.cleanHtmlStr(datItem['shortTitle'])
                    icon = self.getFullIconUrl(datItem['image']['href'])

                    desc = [datItem['sectionName']]

                    #eDate = self._gmt2local(datItem['scheduledEndTime'])
                    #if sDate.year == NOW.year  and sDate.month == NOW.month:
                    diff = sDate.day - NOW.day
                    if diff >= 0 and diff < 7:
                        if NOW.day == sDate.day:
                            desc.append('%s:%s' % (str(sDate.hour).zfill(2), str(sDate.minute).zfill(2)))
                        elif diff == 1:
                            desc.append('Tomorrow at %s:%s' % (str(sDate.hour).zfill(2), str(sDate.minute).zfill(2)))
                        else:
                            desc.append('%s at %s:%s' % (self.ABBREVIATED_DAYS_NAME_TAB[sDate.weekday()], str(sDate.hour).zfill(2), str(sDate.minute).zfill(2)))
                    else:
                        desc.append('%s at %s:%s' % (sDate.strftime('%Y-%m-%d'), str(sDate.hour).zfill(2), str(sDate.minute).zfill(2)))
                    desc = [' | '.join(desc)]
                    desc.append(self.cleanHtmlStr(datItem['summary']))
                    params = dict(cItem)
                    params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                    self.addDir(params)
        except Exception:
            printExc()

    def listSubMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("BBCSport.listSubMenu")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cItem = dict(cItem)
        cItem.update({'category': nextCategory1})
        self.listItems(cItem, nextCategory2, data)

    def listItems(self, cItem, nextCategory, data=None):
        printDBG("BBCSport.listItems")

        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return

        liveItemList = []
        maediaList = []
        othersList = []

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<section', '</section>')
        for data in tmp:
            if 'id="audio-video"' in data:
                promote = True
            else:
                promote = False

            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>', 'has-media'), ('</article', '>'))
            for item in data:
                tmp = self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''\shref=['"]([^"^']+?)['"]''')[0])
                if not self.cm.isValidUrl(url):
                    continue

                title = self.cleanHtmlStr(tmp)
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?\.(?:jpe?g|png)(?:\?[^"^']+?)?)['"]''')[0])

                desc = []
                tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', '_meta'), ('</div', '>'), False)[1]
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
                for t in tmp:
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        desc.append(t)
                desc = ' | '.join(desc)
                if desc == '':
                    desc = []
                else:
                    desc = [desc]
                desc.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'summary'), ('</p', '>'), False)[1]))

                params = dict(cItem)
                params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                if 'gelicon--listen' in item:
                    params['type'] = 'audio'
                    maediaList.append(params)
                elif 'gelicon--play' in item:
                    params['type'] = 'video'
                    maediaList.append(params)
                else:
                    params.update({'type': 'category', 'category': nextCategory})
                    if 'gelicon--live' in item:
                        liveItemList.append(params)
                    else:
                        othersList.append(params)
                    printDBG("Unknown media type\n%s\n>>>>" % item)

        self.currList.extend(liveItemList)
        self.currList.extend(maediaList)
        self.currList.extend(othersList)

    def exploreItem(self, cItem):
        printDBG("BBCSport.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        mediaDataTab = []

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '.setPayload(', '</script>', False)
        for mediaData in tmp:
            mediaData = self.cm.ph.getDataBeetwenMarkers(mediaData, '"body":{', '});', False)[1].strip()[:-1]
            try:
                mediaData = byteify(json.loads('{%s}' % mediaData))
                if 'components' in mediaData:
                    for item in mediaData['components']:
                        try:
                            if item['props']['supportingMedia']:
                                mediaDataTab.extend(item['props']['supportingMedia'])
                            if item['props']['leadMedia']:
                                mediaDataTab.append(item['props']['leadMedia'])
                        except Exception:
                            printExc()
                if 'sessions' in mediaData:
                    for item in mediaData['sessions']:
                        try:
                            mediaDataTab.extend(item['media'])
                        except Exception:
                            printExc()
            except Exception:
                printExc()

        for item in mediaDataTab:
            try:
                if 'identifiers' not in item or 'playablePid' not in item['identifiers']:
                    continue
                vpid = item['identifiers']['playablePid']
                if vpid == '':
                    continue
                url = self.getFullUrl('/iplayer/vpid/%s/' % vpid)
                icon = self.getFullIconUrl(item['coverImage'])
                title = self.cleanHtmlStr(item['title'])
                mediaType = item['mediaType']

                if 'COMING_SOON' in item['status']:
                    continue

                desc = [item['status']]
                if 'schedule' in item and 'formattedStartTime' in item['schedule']:
                    desc.append('%s-%s' % (item['schedule']['formattedStartTime'], item['schedule']['formattedEndTime']))
                elif 'duration' in item and 'formattedDuration' in item['duration']:
                    desc.append(item['duration']['formattedDuration'])

                desc = [' | '.join(desc)]
                desc.append(self.cleanHtmlStr(item['summary']))

                params = dict(cItem)
                params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                if mediaType == 'video':
                    self.addVideo(params)
                elif mediaType == 'audio':
                    self.addAudio(params)
                else:
                    printDBG("Unknown media type\n%s\n>>>>" % mediaType)
            except Exception:
                printExc()

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'data-media-type'), ('</div', '>'))
        for item in tmp:
            mediaType = self.cm.ph.getSearchGroups(item, '\sdata\-media\-type=["]([^"]+?)["]')[0]
            mediaType = self.cm.ph.getSearchGroups(item, '\sdata\-content\-type=["]([^"]+?)["]')[0].lower()
            vpid = self.cm.ph.getSearchGroups(item, '\sdata\-media\-vpid=["]([^"]+?)["]')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '\sdata\-title=["]([^"]+?)["]')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '\sdata\-image\-url=["]([^"]+?)["]')[0])
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '\sdata\-media\-duration=["]([^"]+?)["]')[0])

            if vpid == '':
                continue
            url = self.getFullUrl('/iplayer/vpid/%s/' % vpid)

            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': duration}
            if mediaType == 'video':
                self.addVideo(params)
            elif mediaType == 'audio':
                self.addAudio(params)
            else:
                printDBG("Unknown media type\n%s\n>>>>" % mediaType)

    def listSubItems(self, cItem):
        printDBG("BBCSport.listSubItems")
        self.currList = cItem['sub_items']

    def tryTologin(self):
        printDBG('BBCSport.tryTologin start')
        netErrorMsg = _('Error communicating with the server.')
        datErrorMsg = _('Data mismatch.')

        if config.plugins.iptvplayer.bbc_use_web_proxy.value:
            if False != self.loggedIn:
                rm(self.COOKIE_FILE)
                self.loggedIn = False
            return False

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.bbc_login.value or\
            self.password != config.plugins.iptvplayer.bbc_password.value:

            self.login = config.plugins.iptvplayer.bbc_login.value
            self.password = config.plugins.iptvplayer.bbc_password.value

            rm(self.COOKIE_FILE)

            self.loggedIn = False
            self.loginMessage = ''

            if '' == self.login.strip() or '' == self.password.strip():
                #msg = _('You now need to sign in to watch.\nPlease fill your login and password in the host configuration - available under blue button.')
                #GetIPTVNotify().push(msg, 'info', 10)
                return False

            sts, data = self.getPage(self.getFullUrl('/sport'))
            if not sts:
                msg = _(netErrorMsg) + _('\nError[1].')
                GetIPTVNotify().push(msg, 'error', 10)
                return False

            cUrl = data.meta['url']
            self.setMainUrl(cUrl)

            try:
                url = self.sessionUrl + '?ptrt=' + urllib.quote(cUrl.split('?', 1)[0]) + '&userOrigin=sport&context=sport'
                sts, data = self.getPage(url)
                if not sts:
                    msg = _(netErrorMsg) + _('\nError[2].')
                    GetIPTVNotify().push(msg, 'error', 10)
                    return False

                cUrl = data.meta['url']

                sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>'), ('</form', '>'))
                if not sts:
                    msg = _(datErrorMsg) + _('\nError[3].')
                    GetIPTVNotify().push(msg, 'error', 10)
                    return False

                actionUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&'), self.cm.getBaseUrl(cUrl))
                if actionUrl == '':
                    actionUrl = cUrl
                formData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
                post_data = {}
                for item in formData:
                    name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                    value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                    post_data[name] = value

                post_data.update({'username': self.login, 'password': self.password})

                httpParams = dict(self.defaultParams)
                httpParams['header'] = dict(httpParams['header'])
                httpParams['header']['Referer'] = self.getMainUrl()
                sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
                if sts:
                    printDBG('tryTologin OK')

                    if '/signin' in data.meta['url']:
                        msg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'form-message'), ('</p', '>'))[1])
                        GetIPTVNotify().push(_('Login failed.') + '\n' + msg, 'error', 10)
                        return False

                    self.loggedIn = True
                    msg = _("A TV License is required to watch BBC iPlayer streams, see the BBC website for more information: https://www.bbc.co.uk/iplayer/help/tvlicence")
                    GetIPTVNotify().push(msg, 'info', 5)
                    self.loginMessage = msg
                else:
                    msg = _(netErrorMsg) + _('\nError[4].')
                    GetIPTVNotify().push(msg, 'error', 10)
                    return False
            except Exception:
                printExc()

            printDBG('EuroSportPlayer.tryTologin end loggedIn[%s]' % self.loggedIn)
            return self.loggedIn

    def getLinksForVideo(self, cItem):
        printDBG("BBCSport.getLinksForVideo [%s]" % cItem)
        self.tryTologin()
        urlTab = []

        if '/vpid/' in cItem['url']:
            urlTab.append({'name': cItem['title'], 'url': cItem['url'], 'need_resolve': 1})
        else:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return urlTab

            mediaData = self.cm.ph.getDataBeetwenMarkers(data, '.setPayload(', '</script>', False)[1]
            mediaData = self.cm.ph.getDataBeetwenMarkers(mediaData, '"body":{', '});', False)[1].strip()[:-1]
            if mediaData != '':
                try:
                    mediaData = byteify(json.loads('{%s}' % mediaData), '', True)
                    if mediaData['media'] and mediaData['media']['mediaType'].lower() == 'video' and '' != mediaData['media']['pid']:
                        url = self.getFullUrl('/iplayer/vpid/%s/' % mediaData['media']['pid'])
                        urlTab.append({'name': mediaData['media']['entityType'], 'url': url, 'need_resolve': 1})
                except Exception:
                    printExc()

            mediaData = self.cm.ph.getDataBeetwenMarkers(data, '"allAvailableVersions"', '"holdingImage"', False)[1].strip()[1:-1].strip()
            if mediaData != '':
                try:
                    uniqueTab = []
                    mediaData = byteify(json.loads(mediaData), '', True)
                    for tmp in mediaData:
                        title = self.cleanHtmlStr(tmp['smpConfig']['title'])
                        for item in tmp['smpConfig']['items']:
                            url = self.getFullUrl('/iplayer/vpid/%s/' % item['vpid'])
                            if url in uniqueTab:
                                continue
                            uniqueTab.append(url)
                            name = item['kind'].title()
                            urlTab.append({'name': '[%s] %s' % (name, title), 'url': url, 'need_resolve': 1})
                except Exception:
                    printExc()

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("BBCSport.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if 1 == self.up.checkHostSupport(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        self.informAboutGeoBlockingIfNeeded('GB')
        self.tryTologin()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'}, 'sub_menu', 'all_items')
        elif category == 'all_items':
            self.listAllItems(self.currItem, 'sub_menu')
        elif category == 'live_guide':
            self.listLiveGuideMenu(self.currItem, 'live_guide_items')
        elif category == 'live_guide_items':
            self.listLiveGuideItems(self.currItem, 'explore_item')
        elif category == 'sub_menu':
            self.listSubMenu(self.currItem, 'list_items', 'explore_item')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)

        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, BBCSport(), True, [])
