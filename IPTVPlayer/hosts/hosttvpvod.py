# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.components.recaptcha_v2helper import CaptchaHelper
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
from datetime import datetime, timedelta, date
import re
import urllib
import time
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################
config.plugins.iptvplayer.tvpvod_premium  = ConfigYesNo(default = False)
config.plugins.iptvplayer.tvpvod_login    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.tvpvod_password = ConfigText(default = "", fixed_size = False)

config.plugins.iptvplayer.tvpVodProxyEnable = ConfigYesNo(default = False)
config.plugins.iptvplayer.tvpVodDefaultformat = ConfigSelection(default = "590000", choices = [("360000",  "320x180"),
                                                                                               ("590000",  "398x224"),
                                                                                               ("820000",  "480x270"),
                                                                                               ("1250000", "640x360"),
                                                                                               ("1750000", "800x450"),
                                                                                               ("2850000", "960x540"),
                                                                                               ("5420000", "1280x720"),
                                                                                               ("6500000", "1600x900"),
                                                                                               ("9100000", "1920x1080") ])
config.plugins.iptvplayer.tvpVodUseDF    = ConfigYesNo(default = True)
config.plugins.iptvplayer.tvpVodNextPage = ConfigYesNo(default = True)
config.plugins.iptvplayer.tvpVodPreferedformat = ConfigSelection(default = "mp4", choices = [("mp4",  "MP4"), ("m3u8",  "HLS/m3u8")])

###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Strefa Widza", config.plugins.iptvplayer.tvpvod_premium))
    if config.plugins.iptvplayer.tvpvod_premium.value:
        optionList.append(getConfigListEntry("  email:", config.plugins.iptvplayer.tvpvod_login))
        optionList.append(getConfigListEntry("  hasło:", config.plugins.iptvplayer.tvpvod_password))
    optionList.append(getConfigListEntry("Peferowany format wideo",               config.plugins.iptvplayer.tvpVodPreferedformat))
    optionList.append(getConfigListEntry("Domyślna jakość wideo",           config.plugins.iptvplayer.tvpVodDefaultformat))
    optionList.append(getConfigListEntry("Używaj domyślnej jakości wideo:", config.plugins.iptvplayer.tvpVodUseDF))
    optionList.append(getConfigListEntry("Korzystaj z proxy?",              config.plugins.iptvplayer.tvpVodProxyEnable))
    return optionList
###################################################

def gettytul():
    return 'https://vod.tvp.pl/'

class TvpVod(CBaseHostClass, CaptchaHelper):
    DEFAULT_ICON_URL = 'https://s.tvp.pl/files/vod.tvp.pl/img/menu/logo_vod.png' #'http://sd-xbmc.org/repository/xbmc-addons/tvpvod.png'
    PAGE_SIZE = 12
    SPORT_PAGE_SIZE = 20
    ALL_FORMATS = [{"video/mp4":"mp4"}, {"application/x-mpegurl":"m3u8"}, {"video/x-ms-wmv":"wmv"}] 
    REAL_FORMATS = {'m3u8':'ts', 'mp4':'mp4', 'wmv':'wmv'}
    MAIN_VOD_URL = "https://vod.tvp.pl/"
    LOGIN_URL    = "https://www.tvp.pl/sess/user-2.0/login.php?ref="
    ACCOUNT_URL  = "https://www.tvp.pl/sess/user-2.0/account.php"
    STREAMS_URL_TEMPLATE = 'http://www.api.v3.tvp.pl/shared/tvpstream/listing.php?parent_id=13010508&type=epg_item&direct=false&filter={%22release_date_dt%22:%22[iptv_date]%22,%22epg_play_mode%22:{%22$in%22:[0,1,3]}}&count=-1&dump=json'
    SEARCH_VOD_URL = MAIN_VOD_URL + 'szukaj?query=%s'
    IMAGE_URL = 'http://s.v3.tvp.pl/images/%s/%s/%s/uid_%s_width_500_gs_0.%s'
    HTTP_HEADERS = {}
    
    RIGI_DEFAULT_ICON_URL = 'https://pbs.twimg.com/profile_images/999586990650638337/YHEsWRTs_400x400.jpg'
    
    VOD_CAT_TAB  = [{'category':'tvp_sport',           'title':'TVP Sport',                 'url':'http://sport.tvp.pl/wideo'},
                    {'category':'streams',             'title':'TVP na żywo',               'url':'http://tvpstream.tvp.pl/'},
                    {'category':'vods_explore_item',   'title':'Przegapiłeś w TV?',         'url':MAIN_VOD_URL + 'przegapiles-w-tv'},
                    {'category':'vods_list_cats',      'title':'Katalog',                   'url':MAIN_VOD_URL},
                    {'category':'digi_menu',           'title':'Rekonstrukcja cyfrowa TVP', 'url':'https://cyfrowa.tvp.pl/', 'icon':RIGI_DEFAULT_ICON_URL},
                    
                    #{'category':'vods_list_items1',    'title':'Polecamy',                  'url':MAIN_VOD_URL},
                    #{'category':'vods_sub_categories', 'title':'Polecane',                  'marker':'Polecane'},
                    #{'category':'vods_sub_categories', 'title':'VOD',                       'marker':'VOD'},
                    #{'category':'vods_sub_categories', 'title':'Programy',                  'marker':'Programy'},
                    #{'category':'vods_sub_categories', 'title':'Informacje i publicystyka', 'marker':'Informacje i publicystyka'},
                    {'category':'search',          'title':_('Search'), 'search_item':True},
                    {'category':'search_history',  'title':_('Search history')} ]
                    
    STREAMS_CAT_TAB = [{'category':'tvp3_streams',     'title':'TVP 3',                   'url':'http://tvpstream.tvp.pl/',       'icon':'http://ncplus.pl/~/media/n/npl/kanaly/logo%20na%20strony%20kanalow/tvp3.png?bc=white&w=480'},
                       {'category':'week_epg',         'title':'TVP SPORT',               'url':STREAMS_URL_TEMPLATE,             'icon':'https://upload.wikimedia.org/wikipedia/commons/9/9d/TVP_Sport_HD_Logo.png'},
                       {'category':'tvpsport_streams', 'title':'Transmisje sport.tvp.pl', 'url':'http://sport.tvp.pl/transmisje', 'icon':'https://upload.wikimedia.org/wikipedia/commons/9/9d/TVP_Sport_HD_Logo.png'},
                      ]
    
    def __init__(self):
        printDBG("TvpVod.__init__")
        CBaseHostClass.__init__(self, {'history':'TvpVod', 'cookie':'tvpvod.cookie', 'proxyURL': config.plugins.iptvplayer.proxyurl.value, 'useProxy': config.plugins.iptvplayer.tvpVodProxyEnable.value})
        self.defaultParams = {'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'header':TvpVod.HTTP_HEADERS}
        self.loggedIn = None
        self.fixUrlMap = {'nadobre.tvp.pl':        'http://vod.tvp.pl/8514270/na-dobre-i-na-zle',
                          'mjakmilosc.tvp.pl':     'http://vod.tvp.pl/1654521/m-jak-milosc',
                          'barwyszczescia.tvp.pl': 'http://vod.tvp.pl/8514286/barwy-szczescia',
                          'nasygnale.tvp.pl':      'http://vod.tvp.pl/13883615/na-sygnale'}
        self.FormatBitrateMap = [ ("360000",  "320x180"), ("590000",  "398x224"), ("820000",  "480x270"), ("1250000", "640x360"),
                                  ("1750000", "800x450"), ("2850000", "960x540"), ("5420000", "1280x720"), ("6500000", "1600x900"), ("9100000", "1920x1080") ]
        self.MAIN_URL = 'https://vod.tvp.pl/'
        self.loginMessage = ''
    
    def getJItemStr(self, item, key, default=''):
        v = item.get(key, None)
        if None == v:
            return default
        return str(v)
    
    def getImageUrl(self, item):
        keys = ['logo_4x3', 'image_16x9', 'image_4x3', 'image_ns954', 'image_ns644', 'image']
        iconFile = ""
        for key in keys:
            if None != item.get(key, None):
                iconFile = self.getJItemStr( item[key][0], 'file_name')
            if len(iconFile):
                tmp = iconFile.split('.')
                return self.IMAGE_URL % (iconFile[0], iconFile[1], iconFile[2], tmp[0], tmp[1])
        return ''
        
    def _getPage(self, url, addParams = {}, post_data = None):
        
        try:
            import httplib
            def patch_http_response_read(func):
                def inner(*args):
                    try:
                        return func(*args)
                    except httplib.IncompleteRead, e:
                        return e.partial
                return inner
            prev_read = httplib.HTTPResponse.read
            httplib.HTTPResponse.read = patch_http_response_read(httplib.HTTPResponse.read)
        except Exception: printExc()
        sts, data = self.cm.getPage(url, addParams, post_data)
        try: httplib.HTTPResponse.read = prev_read
        except Exception: printExc()
        return sts, data
        
    def _getStr(self, v, default=''):
        return self.cleanHtmlStr(self._encodeStr(v, default))
        
    def _encodeStr(self, v, default=''):
        if type(v) == type(u''): return v.encode('utf-8')
        elif type(v) == type(''): return v
        else: return default
        
    def _getNum(self, v, default=0):
        try: return int(v)
        except Exception:
            try: return float(v)
            except Exception: return default
            
    def _getFullUrl(self, url, baseUrl=None):
        if None == baseUrl: baseUrl = TvpVod.MAIN_VOD_URL
        if 0 < len(url) and not url.startswith('http'):
            if url.startswith('//'):
                url = 'http:' + url
            else:
                if not baseUrl.endswith('/'):
                    baseUrl += '/'
                if url.startswith('/'):
                    url = url[1:]
                url =  baseUrl + url
        return url
        
    def getFormatFromBitrate(self, bitrate):
        ret = ''
        for item in self.FormatBitrateMap:
            if int(bitrate) == int(item[0]):
                ret = item[1]
        if '' == ret: ret = 'Bitrate[%s]' % bitrate
        return ret
        
    def getBitrateFromFormat(self, format):
        ret = 0
        for item in self.FormatBitrateMap:
            if format == item[1]:
                ret = int(item[0])
        return ret
     
    def tryTologin(self):
        self.loginMessage = ''
        email = config.plugins.iptvplayer.tvpvod_login.value
        password = config.plugins.iptvplayer.tvpvod_password.value
        msg = 'Wystąpił problem z zalogowaniem użytkownika "%s"!' % email
        params = dict(self.defaultParams)
        sts, data = self._getPage(TvpVod.ACCOUNT_URL, params)
        if not sts or 'action=sign-out' not in data:
            params.update({'load_cookie': False})
            sts, data = self._getPage(TvpVod.LOGIN_URL, params)
            if sts:
                ref = self.cm.ph.getSearchGroups(data, 'name="ref".+?value="([^"]+?)"')[0]
                post_data = {'ref':ref, 'email':email, 'password':password, 'action':'login'}
                sitekey = self.cm.ph.getSearchGroups(data, '''sitekey=['"]([^'^"]+?)['"]''')[0]
                if sitekey != '':
                    token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta['url'])
                    if token == '':
                        msg = _('Link protected with google recaptcha v2.') + '\n' + msg
                        sts = False
                    else:
                        post_data['g-recaptcha-response'] = token
                sts, data = self._getPage(TvpVod.LOGIN_URL + ref, self.defaultParams, post_data)
        if sts and 'action=sign-out' in data:
            printDBG(">>>\n%s\n<<<" % data)
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'abo__section'), ('</section', '>'), False)[1]
            if tmp == '':
                tmp = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'abo-inactive'), ('</section', '>'), False)[1]
            data = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(tmp, ('<p', '>'), ('</p', '>'), False)[1] )
            msg = ['Użytkownik "%s"' % email]
            msg.append('Strefa Abo %s' % data)
            self.loginMessage = '[/br]'.join(msg)
            msg = self.loginMessage.replace('[/br]', '\n')
        else: 
            sts = False
        return sts, msg
        
    def _addNavCategories(self, data, cItem, category):
        data = re.findall('href="([^"]+?)"[^>]*?>([^<]+?)<', data)
        for item in data:
            params = dict(cItem)
            params.update({'category':category, 'title':self.cleanHtmlStr(item[1]), 'url':item[0]})
            self.addDir(params)
            
    def _getAjaxUrl(self, parent_id, location):
        if location == 'directory_series':
            order='';
            type='website'
            template ='listing_series.html'
            direct='&direct=false'
        elif location == 'directory_stats':
            order=''
            type='video'
            template ='listing_stats.html'
            direct='&filter=%7B%22playable%22%3Atrue%7D&direct=false'
        elif location == 'directory_video':
            order='&order=position,1'
            type='video'
            template ='listing.html'
            direct='&filter=%7B%22playable%22%3Atrue%7D&direct=false'
        elif location == 'website':
            order='&order=release_date_long,-1'
            type='video'
            template ='listing.html'
            direct='&filter=%7B%22playable%22%3Atrue%7D&direct=false'
        else:
            order='&order=release_date_long,-1'
            type='video'
            template ='listing.html'
            direct='&filter=%7B%22playable%22%3Atrue%7D&direct=true'
            
        url = '/shared/listing.php?parent_id=' + parent_id + '&type=' + type + order + direct + '&template=directory/' + template + '&count=' + str(TvpVod.PAGE_SIZE) 
                    
        return self._getFullUrl(url)
        
    def listTVP3Streams(self, cItem):
        printDBG("TvpVod.listTVP3Streams")
        sts, data = self._getPage(cItem['url'], self.defaultParams)
        if not sts: return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="button', '</div>', withMarkers=True, caseSensitive=False)
        for item in data:
            id    = self.cm.ph.getSearchGroups(item, 'data-video[_\-]id="([0-9]+?)"')[0]
            if id != '':
                desc  = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'titlte="([^"]+?)"')[0])
                icon  = self.cm.ph.getSearchGroups(item, 'src="(http[^"]+?)"')[0]
                title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0].replace('-', ' ').title()
                params = dict(cItem)
                params.update({'title':title, 'url':'http://tvpstream.tvp.pl/sess/tvplayer.php?object_id=%s&autoplay=true' % id, 'icon':icon, 'desc':desc})
                self.addVideo(params)
                
    def listTVPSportStreams(self, cItem, nextCategory):
        printDBG("TvpVod.listTVPSportStreams")
        sts, data = self._getPage(cItem['url'], self.defaultParams)
        if not sts: return
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'epg-broadcasts'), ('</section', '>'), False)[1]
        data = re.compile('''<div[^>]*?class=['"]date['"][^>]*?>''').split(data)
        for idx in range(1, len(data), 1):
            dateTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data[idx], '<span', '</span>')[1])
            subItems = []
            tmp = re.compile('''<div[^>]+?class=['"]item(?:\s*playing)?['"][^>]*?>''').split(data[idx])
            for i in range(1, len(tmp), 1):
                time = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp[i], ('<span', '>', 'time'), ('</span', '>'), False)[1])
                desc = []
                t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp[i], ('<div', '>', 'category'), ('</div', '>'), False)[1])
                if t != '': desc.append(t)
                t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp[i], ('<div', '>', 'meta'), ('</div', '>'), False)[1])
                if t != '': desc.append(t)
                desc = '[/br]'.join(desc)
                t = self.cm.ph.getDataBeetwenNodes(tmp[i], ('<div', '>', 'title'), ('</div', '>'), False)[1]
                url = self._getFullUrl(self.cm.ph.getSearchGroups(t, '''<a[^>]+?href=['"]([^'^"]+?)['"]''')[0], cUrl)
                title = '%s - %s' % (time, self.cleanHtmlStr(t))
                
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title':title, 'url':url, 'desc':desc})
                if url == '': params['type'] = 'article'
                else: params['type'] = 'video'
                subItems.append(params)
            if len(subItems):
                params = dict(cItem)
                params.update({'category':nextCategory, 'good_for_fav':True, 'title':dateTitle, 'sub_items':subItems})
                self.addDir(params)
        
    def listWeekEPG(self, cItem, nextCategory):
        printDBG("TvpVod.listWeekEPG")
        urlTemplate = cItem['url']
        
        d = datetime.today()
        for i in range(7):
            url    = urlTemplate.replace('[iptv_date]', d.strftime('%Y-%m-%d'))
            title  = d.strftime('%a %d.%m.%Y')
            params = dict(cItem)
            params.update({'category':nextCategory, 'title':title, 'url':url})
            self.addDir(params)
            d += timedelta(days=1)
            
    def listEPGItems(self, cItem):
        printDBG("TvpVod.listEPGItems")
        sts, data = self._getPage(cItem['url'], self.defaultParams)
        if not sts: return
        try:
            #date.fromtimestamp(item['release_date']['sec']).strftime('%H:%M')
            data = json_loads(data)
            data['items'].sort(key=lambda item: item['release_date_hour'])
            for item in data['items']:
                if not item.get('is_live', False): continue 
                title = str(item['title'])
                desc  = str(item['lead'])
                asset_id  = str(item['asset_id'])
                asset_id  = str(item['video_id'])
                icon  = self.getImageUrl(item)
                desc  = item['release_date_hour'] + ' - ' + item['broadcast_end_date_hour'] + '[/br]' + desc 
                self.addVideo({'title':title, 'url':'', 'object_id':asset_id, 'icon':icon, 'desc':desc})
            printDBG(data)
        except Exception:
            printExc()
        
    def listTVPSportCategories(self, cItem, nextCategory):
        printDBG("TvpVod.listTVPSportCategories")
        sts, data = self._getPage(cItem['url'], self.defaultParams)
        if not sts: return
        data = self.cm.ph.getDataBeetwenMarkers(data, '__directoryData ', '</script>', False)[1]
        data = self.cm.ph.getDataBeetwenMarkers(data, '[', ']', True)[1]
        printDBG(">>> %s" % data)
        try:
            data = json_loads(data)
            for item in data:
                if item['url'].startswith('?'):
                    url = cItem['url'] + item['url']
                sts, tmp = self._getPage(url, self.defaultParams)
                if not sts: continue
                tmp = self.cm.ph.getDataBeetwenMarkers(tmp, '__blockList[0]', '"items":', False)[1]
                url = self.cm.ph.getSearchGroups(tmp, '''['"]urlShowMore['"]\s*:\s*['"]([^'^"]+?)['"]''')[0]
                url = self._getFullUrl(url.replace('\\', ''), 'http://sport.tvp.pl')
                params = dict(cItem)
                params.update({'category':nextCategory, 'good_for_fav':True, 'title':item['title'], 'url':url})
                self.addDir(params)
        except Exception:
            printExc()

    def listTVPSportVideos(self, cItem):
        printDBG("TvpVod.listTVPSportVideos")
        
        page = cItem.get('page', 1)
        videosNum = 0

        url  = cItem['url']
        url += '?page=%d' %(page)
        
        sts, data = self._getPage(url, self.defaultParams)
        if not sts: return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'window.__directoryData =', '</script>', False)[1]
        try:
            data = json_loads(data.replace(';', ''))
            for item in data['items']:
                url   = self._getFullUrl(item['url'], 'http://sport.tvp.pl')
                desc  = item['lead']
                title = item['title']
                icon  = item['image']['url'].format(width = '480', height = '360')
                if url.startswith('http'):
                    videosNum += 1
                    params = dict(cItem)
                    params.update({'title':title, 'icon':icon, 'url':url, 'desc':desc})
                    self.addVideo(params)
        except Exception:
            printExc()
                
        if videosNum >= self.SPORT_PAGE_SIZE:
            params = dict(cItem)
            params.update({'page':page+1})
            if config.plugins.iptvplayer.tvpVodNextPage.value:
                params['title'] = _('Next page')
                self.addDir(params)
            else:
                params['title'] = _('More')
                self.addMore(params)
                
    def listCatalog(self, cItem, nextCategory):
        printDBG("TvpVod.listCatalog")
        sts, data = self._getPage(cItem['url'], self.defaultParams)
        if not sts: return []

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="subMenu">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''<a[^>]+?href\s*=\s*['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url): continue
            if 'cyfrowa.tvp.pl' in url: continue
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category':nextCategory, 'title':self.cleanHtmlStr(item).title(), 'url':url, 'desc':''})
            self.addDir(params)
            
    def mapHoeverItem(self, cItem, item, rawItem, nextCategory):
        try:
            item = json_loads(item)
            title = self.getJItemStr(item, 'title')
            icon = self._getFullUrl(self.getJItemStr(item, 'image'))
            tmp = []
            labelMap = {'age':'Wiek: %s'}
            for key in ['transmision', 'antena', 'age']:
                val = self.getJItemStr(item, key)
                if val != '': tmp.append(labelMap.get(key, '%s') % val)
                
            paymentTag = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(rawItem, ('<div', '>', 'showPaymentTag'), ('</div', '>'))[1])
            if paymentTag != '': tmp.append(paymentTag)
            desc = ' | '.join(tmp)
            desc += '[/br]' + self.getJItemStr(item, 'description')
            
            params = {'good_for_fav': True, 'icon':icon, 'desc':self.cleanHtmlStr(desc)}
            seriesLink = self._getFullUrl(self.getJItemStr(item, 'seriesLink'))
            episodeUrl = self._getFullUrl(self.getJItemStr(item, 'episodeLink'))
            
            if self.cm.isValidUrl(episodeUrl) and  '/video/' in episodeUrl:
                title += ' ' + self.getJItemStr(item, 'episodeCount')
                params.update({'title':title, 'url':episodeUrl})
                self.addVideo(params)
            else:
                params.update({'category':nextCategory, 'title':title, 'url':seriesLink})
                self.addDir(params)
            
            printDBG("======================")
            printDBG(item)
        except Exception:
            printExc()
                
    def exploreVODItem(self, cItem, nextCategory):
        printDBG("TvpVod.exploreVODItem")
        
        sts, data = self._getPage(cItem['url'], self.defaultParams)
        if not sts: return []
        
        if '/szukaj?query=' in cItem['url']:
            isSearch = True
        else:
            isSearch = False
            
        printDBG(">>>>>>>>>>>>. isSearch [%s]" % isSearch)
        
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="episodes"', '</h1>')[1]
        if self.cleanHtmlStr(tmp) == "Odcinki":
            url = self._getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<a[^>]+?href\s*=\s*['"]([^'^"]+?)['"]''')[0])
            if self.cm.isValidUrl(url):
                cItem = dict(cItem)
                cItem['url'] = url
                sts, data = self._getPage(cItem['url'], self.defaultParams)
                if not sts: return []
        
        data = re.sub("<!--[\s\S]*?-->", "", data)
        
        page = cItem.get('page', 1)
        lastPage = self.cm.ph.getDataBeetwenMarkers(data, '<li class="lastItem"', '</li>')[1]
        lastPage = self.cm.ph.getSearchGroups(lastPage, '''<a[^>]+?href\s*=\s*['"][^'^"]*?page=([0-9]+?)[^0-9]''')[0]
        if lastPage != '' and page < int(lastPage):
            nextPageUrl = self.cm.ph.getDataBeetwenMarkers(data, '<li class="next"', '</li>')[1]
            nextPageUrl = self._getFullUrl(self.cm.ph.getSearchGroups(nextPageUrl, '''<a[^>]+?href\s*=\s*['"]([^'^"]+?)['"]''')[0])
        else: nextPageUrl = ''
        
        sectionsData = self.cm.ph.getDataBeetwenMarkers(data, '<section', '<footer>')[1]
        sectionsData = sectionsData.split('<section')
        if len(sectionsData): del sectionsData[0]
        
        subFiltersData = self.cm.ph.getAllItemsBeetwenNodes(data[data.rfind('</header>'):], ('<ul', '>', '"dropdown-menu'), ('</ul', '>'))
        #subFiltersData.reverse()
        allSubFiltersTab = []
        for idx in range(len(subFiltersData)):
            subFilterData = self.cm.ph.getAllItemsBeetwenMarkers(subFiltersData[idx], '<li', '</li>')
            subFiltersTab = []
            for item in subFilterData:
                url = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''<a[^>]+?href\s*=\s*['"]([^'^"]+?)['"]''')[0])
                if not self.cm.isValidUrl(url): continue
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category':nextCategory, 'title':self.cleanHtmlStr(item), 'url':url, 'desc':''})
                subFiltersTab.append(params)
            if len(subFiltersTab):
                allSubFiltersTab.append(subFiltersTab)
        
        subFiltersTab = []
        subFiltersNames = []
        for subFiltersTab in allSubFiltersTab:
            subFiltersNames = list(cItem.get('sub_filters_names', []))
            for params in subFiltersTab:
                if params['title'] in subFiltersNames:
                    subFiltersTab = []
                    break
                subFiltersNames.append(params['title'])
            if len(subFiltersTab):
                break
            
        for params in subFiltersTab:
            params['sub_filters_names'] = subFiltersNames
            self.addDir(params)
        
        if len(self.currList):
            return
                
        if isSearch:
            data = self.cm.ph.getDataBeetwenMarkers(data, 'serachContent', '</section>')[1]
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="contentList', '</section>')[1]
        if data != '':
            if isSearch:
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="item', '</a>')
            else:
                data = data.split('<div class="subCategoryMobile">')[0]
                data = data.split('<div class="col-md') #re.split('<div class="col-md[^>]+?>', data)
                if len(data): del data[0]
            for item in data:
                jsItem = ph.clean_html(self.cm.ph.getSearchGroups(item, '''data-hover\s*=\s*['"]([^'^"]+?)['"]''')[0])
                self.mapHoeverItem(cItem, jsItem, item, nextCategory)
        else:
            sectionItems = []
            for section in sectionsData:
                sectionHeader = self.cm.ph.getDataBeetwenMarkers(section, '<h1', '</h1>')[1]
                if sectionHeader == '': sectionHeader = self.cm.ph.getDataBeetwenMarkers(section, '<h2>', '</h2>')[1]
                sectionUrl    = self._getFullUrl(self.cm.ph.getSearchGroups(sectionHeader, '''<a[^>]+?href\s*=\s*['"]([^'^"]+?)['"]''')[0])
                sectionIcon   = self._getFullUrl(self.cm.ph.getSearchGroups(section, '''<img[^>]+?data-lazy\s*=\s*['"]([^'^"]+?)['"]''')[0])
                sectionTitle  = self.cleanHtmlStr(sectionHeader)
                
                if self.cm.isValidUrl(sectionUrl):
                    if '>Oglądaj<' in section: continue
                    if sectionTitle.startswith('Zobacz także:'): continue
                
                itemsTab = []
                tmp = self.cm.ph.getAllItemsBeetwenNodes(section, ('<div', '>', 'item'), ('</a', '>'))
                for item in tmp:
                    icon = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?data-lazy\s*=\s*['"]([^'^"]+?)['"]''')[0])
                    if icon == '': icon = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src\s*=\s*['"]([^'^"]+?\.jpg)['"]''')[0])
                    url  = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''<a[^>]+?href\s*=\s*['"]([^'^"]+?)['"]''')[0])
                    
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', 'title'), ('</h', '>'))[1])
                    desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', 'sub-title'), ('</h', '>'))[1])
                    if '/' not in desc: 
                        title += ' ' + desc
                        desc = ''
                    if title == '': title = self.cleanHtmlStr(item)
                    title = title.strip()
                    if self.cm.isValidUrl(url) and title != '':
                        if title.startswith('odc.'): 
                            title = cItem['title'] + ' ' + title
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':''})
                        if '/video/' in url:
                            params.update({'good_for_fav':True, 'type':'video'})
                            itemsTab.append(params)
                        else:
                            params.update({'category':nextCategory,})
                            itemsTab.append(params)
                            
                if self.cm.isValidUrl(sectionUrl) and (len(itemsTab) > 1 or 0 == len(itemsTab)):
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category':nextCategory, 'title':sectionTitle, 'url':sectionUrl, 'icon':sectionIcon, 'desc':''})
                    sectionItems.append({'title':sectionTitle, 'items':[params]})
                elif len(itemsTab):
                    sectionItems.append({'title':sectionTitle, 'items':itemsTab})
            
            allItems = []
            for sectionItem in sectionItems:
                if sectionItem['title'] in ['Przeglądaj', 'Wideo', 'Oglądaj'] and not isSearch:
                    self.currList = sectionItem['items']
                    break
                else:
                    allItems.extend(sectionItem['items'])
            
            if 0 == len(self.currList):
                self.currList = allItems
        
        if self.cm.isValidUrl(nextPageUrl):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category':nextCategory, 'title':_("Next page"), 'url':nextPageUrl, 'page':page+1})
            self.addDir(params)
            
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TvpVod.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = TvpVod.SEARCH_VOD_URL % urllib.quote(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = url
        
        self.exploreVODItem(cItem, 'vods_explore_item')
        
    def listsMenuGroups(self, cItem, category):
        printDBG("TvpVod.listsGroupsType1")
        url = self._getFullUrl(cItem['url'])
        sts, data = self._getPage(url, self.defaultParams)
        if sts:
            # check if 
            data = self.cm.ph.getDataBeetwenMarkers(data, '<section id="menu"', '</section>', False)[1]
            self._addNavCategories(data, cItem, category)
        
                
    def listItems2(self, cItem, category, data):
        printDBG("TvpVod.listItems2")
        itemMarker = '<div class="'
        sectionMarker = '<section id="emisje">'

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'class="siteNewscast">', '</section>', False)[1]
        icon = self.cm.ph.getSearchGroups(tmp, 'src="([^"]+?)"')[0]
        desc = self.cm.ph.getDataBeetwenMarkers(tmp, '<p>', '</div>', False)[1]
        data = self.cm.ph.getDataBeetwenMarkers(data, sectionMarker, '</section>', True)[1]
        
        printDBG("TvpVod.listItems2 start parse")
        data = data.split(itemMarker)
        if len(data): del data[0]
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            title = self.cleanHtmlStr('<' + item)
            params = dict(cItem)
            params.update({'category':category, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'page':0})
            self.addVideo(params)
            
    def getObjectID(self, url):
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts: return ''
        
        sess_player_url = self.cm.ph.getSearchGroups(data, '''(https?://[^'^"]+?/sess/player/video/[^'^"]+?)['"]''')[0]
        if sess_player_url != '':
            sts, tmp = self.cm.getPage(sess_player_url, self.defaultParams)
            if sts: data = tmp
        
        asset_id = self.cm.ph.getSearchGroups(data, '''id=['"]tvplayer\-[0-9]+\-([0-9]+)''')[0]
        
        if asset_id == '': asset_id = self.cm.ph.getSearchGroups(data, 'object_id=([0-9]+?)[^0-9]')[0]
        if asset_id == '': asset_id = self.cm.ph.getSearchGroups(data, 'class="playerContainer"[^>]+?data-id="([0-9]+?)"')[0]
        if '' == asset_id: asset_id = self.cm.ph.getSearchGroups(data, 'data\-video-\id="([0-9]+?)"')[0]
        if '' == asset_id: asset_id = self.cm.ph.getSearchGroups(data, "object_id:'([0-9]+?)'")[0]
        if '' == asset_id: asset_id = self.cm.ph.getSearchGroups(data, 'data\-object\-id="([0-9]+?)"')[0]
        
        return asset_id
                
    def getLinksForVideo(self, cItem):
        asset_id = str(cItem.get('object_id', ''))
        url = self._getFullUrl(cItem.get('url', ''))
        
        if 'tvpstream.tvp.pl' in url:
            sts, data = self.cm.getPage(url)
            if not sts: return []
            
            hlsUrl = self.cm.ph.getSearchGroups(data, '''['"](http[^'^"]*?\.m3u8[^'^"]*?)['"]''')[0]
            if '' != hlsUrl:
                videoTab = getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=False)
                if 1 < len(videoTab):
                    max_bitrate = int(config.plugins.iptvplayer.tvpVodDefaultformat.value)
                    def __getLinkQuality( itemLink ):
                        if 'width' in itemLink and 'height' in itemLink:
                            bitrate = self.getBitrateFromFormat('%sx%s' % (itemLink['width'], itemLink['height']))
                            if bitrate != 0: return bitrate
                        return int(itemLink['bitrate'])
                    oneLink = CSelOneLink(videoTab, __getLinkQuality, max_bitrate)
                    if config.plugins.iptvplayer.tvpVodUseDF.value:
                        videoTab = oneLink.getOneLink()
                    else:
                        videoTab = oneLink.getSortedLinks()
                if 1 <= len(videoTab):
                    return videoTab
            
        if '' == asset_id:
            asset_id = self.getObjectID(url)

        return self.getVideoLink(asset_id)
        
    def isVideoData(self, asset_id):
        sts, data = self.cm.getPage( 'http://www.tvp.pl/shared/cdn/tokenizer_v2.php?mime_type=video%2Fmp4&object_id=' + asset_id, self.defaultParams)
        if not sts:
            return False
        return not 'NOT_FOUND' in data
        
    def getVideoLink(self, asset_id):
        printDBG("getVideoLink asset_id [%s]" % asset_id)
        videoTab = []
        
        if '' == asset_id: return  videoTab
        
        def _sortVideoLinks(videoTab):
            if 1 < len(videoTab):
                max_bitrate = int(config.plugins.iptvplayer.tvpVodDefaultformat.value)
                def __getLinkQuality( itemLink ):
                    if 'width' in itemLink and 'height' in itemLink:
                        bitrate = self.getBitrateFromFormat('%sx%s' % (itemLink['width'], itemLink['height']))
                        if bitrate != 0: return bitrate
                    try: return int(itemLink['bitrate'])
                    except Exception: return 0
                oneLink = CSelOneLink(videoTab, __getLinkQuality, max_bitrate)
                videoTab = oneLink.getSortedLinks()
            return videoTab
        
        # main routine
        if len(videoTab) == 0: 
            sts, data = self.cm.getPage( 'http://www.tvp.pl/shared/cdn/tokenizer_v2.php?mime_type=video%2Fmp4&object_id=' + asset_id, self.defaultParams)
            printDBG("%s -> [%s]" % (sts, data))
            try:
                data = json_loads( data )
                
                def _getVideoLink(data, FORMATS):
                    videoTab = []
                    for item in data['formats']:
                        if item['mimeType'] in FORMATS.keys():
                            formatType = FORMATS[item['mimeType']]
                            format = self.REAL_FORMATS.get(formatType, '')
                            name = self.getFormatFromBitrate( str(item['totalBitrate']) ) + '\t ' + formatType
                            url = item['url']
                            if 'm3u8' == formatType:
                                videoTab.extend( getDirectM3U8Playlist(url, checkExt=False, variantCheck=False) )
                            else:
                                meta = {'iptv_format':format}
                                if config.plugins.iptvplayer.tvpVodProxyEnable.value:
                                    meta['http_proxy'] = config.plugins.iptvplayer.proxyurl.value
                                videoTab.append( {'name' : name, 'bitrate': str(item['totalBitrate']), 'url' : self.up.decorateUrl(url, meta) })
                    return videoTab
                
                preferedFormats  = []
                if config.plugins.iptvplayer.tvpVodPreferedformat.value == 'm3u8':
                    preferedFormats = [TvpVod.ALL_FORMATS[1], TvpVod.ALL_FORMATS[0], TvpVod.ALL_FORMATS[2]]
                else:
                    preferedFormats = TvpVod.ALL_FORMATS
                
                for item in preferedFormats:
                    videoTab.extend(_sortVideoLinks(_getVideoLink(data, item )))
                
            except Exception:
                printExc("getVideoLink exception")
        
        # fallback routine
        if len(videoTab) == 0: 
            formatMap = {'1':("320x180", 360000), '2':('398x224', 590000), '3':('480x270', 820000), '4':('640x360', 1250000), '5':('800x450', 1750000), '6':('960x540', 2850000), '7':('1280x720', 5420000), '8':("1600x900", 6500000), '9':('1920x1080', 9100000)}
            
            params = dict(self.defaultParams)
            params['header'] = {'User-Agent':'okhttp/3.8.1', 'Authorization':'Basic YXBpOnZvZA==', 'Accept-Encoding':'gzip'}
#            sts, data = self.cm.getPage( 'https://apivod.tvp.pl/tv/video/%s/default/default?device=android' % asset_id, params)
            sts, data = self.cm.getPage( 'https://apivod.tvp.pl/tv/video/%s/' % asset_id, params)
            printDBG("%s -> [%s]" % (sts, data))
            try:
                data = json_loads(data, '', True)
                for item in data['data']:
                    if 'formats' in item:
                        data = item
                        break
                hlsTab = []
                mp4Tab = []
                for item in data['formats']:
                    if not self.cm.isValidUrl(item.get('url', '')):
                        continue
                    if item.get('mimeType', '').lower() == "application/x-mpegurl":
                        hlsTab = getDirectM3U8Playlist(item['url'])
                    elif item.get('mimeType', '').lower() == "video/mp4":
                        id = self.cm.ph.getSearchGroups(item['url'], '''/video\-([1-9])\.mp4$''')[0]
                        fItem = formatMap.get(id, ('0x0', 0))
                        mp4Tab.append({'name':'%s \t mp4' % fItem[0], 'url':item['url'], 'bitrate':fItem[1], 'id':id})
                
                if len(hlsTab) > 0 and 1 == len(mp4Tab) and mp4Tab[0]['id'] != '':
                    for item in hlsTab:
                        res = '%sx%s' % (item['width'], item['height'])
                        for key in formatMap.keys():
                            if key == mp4Tab[0]['id']: continue
                            if formatMap[key][0] != res: continue
                            url = mp4Tab[0]['url']
                            url = url[:url.rfind('/')] + ('/video-%s.mp4' % key)
                            mp4Tab.append({'name':'%s \t mp4' % formatMap[key][0], 'url':url, 'bitrate':formatMap[key][1], 'id':key})
               
                hlsTab = _sortVideoLinks(hlsTab)
                mp4Tab = _sortVideoLinks(mp4Tab)
                if config.plugins.iptvplayer.tvpVodPreferedformat.value == 'm3u8':
                    videoTab.extend(hlsTab)
                    videoTab.extend(mp4Tab)
                else:
                    videoTab.extend(mp4Tab)
                    videoTab.extend(hlsTab)
            except Exception:
                printExc("getVideoLink exception")
        
        if config.plugins.iptvplayer.tvpVodUseDF.value and len(videoTab):
            videoTab = [videoTab[0]]
        
        return videoTab
        
    def getLinksForFavourite(self, fav_data):
        if None == self.loggedIn:
            premium = config.plugins.iptvplayer.tvpvod_premium.value
            if premium: self.loggedIn, msg = self.tryTologin()
        
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            cItem = {'url':fav_data}
            try:
                ok = int(cItem['url'])
                if ok: return self.getVideoLink(cItem['url'])
            except Exception: pass
        return self.getLinksForVideo(cItem)
        
    def getFavouriteData(self, cItem):
        printDBG('TvpVod.getFavouriteData')
        params = {'type':cItem['type'], 'category':cItem.get('category', ''), 'title':cItem['title'], 'url':cItem['url'], 'desc':cItem.get('desc', ''), 'icon':cItem.get('icon', '')}
        if 'list_episodes' in cItem:
            params['list_episodes'] = cItem['list_episodes']
        return json_dumps(params) 
        
    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('TvpVod.setInitListFromFavouriteItem')
        try:
            params = json_loads(fav_data)
        except Exception: 
            params = {}
            printExc()
        self.addDir(params)
        return True

    def listDigiMenu(self, cItem, nextCategory):
        printDBG("listDigiMenu")
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: return
        cUrl = self.cm.meta['url']

        tmp = ph.find(data, ('<nav', '>'), '</nav>', flags=0)[1]
        tmp = ph.rfindall(tmp, '</li>', ('<li', '>', ph.check(ph.none, ('item--submenu',))), flags=0)
        for item in tmp:
            item = item.split('<ul', 1)
            sTitle = ph.find(item[0], ('<a', '>'), '</a>')[1]
            sUrl = self.getFullUrl(ph.getattr(sTitle, 'href'), cUrl)
            sTitle = ph.clean_html(sTitle)

            subItems = []
            if len(item) > 1:
                item = ph.findall(item[-1], ('<li', '>'), '</li>', flags=0)
                for it in item:
                    title = ph.clean_html(ph.find(it, ('<a', '>'), '</a>', flags=0)[1])
                    url = self.getFullUrl(ph.getattr(it, 'href'),  cUrl)
                    subItems.append(MergeDicts(cItem, {'category':nextCategory, 'title':title, 'url':url}))
            if len(subItems):
                self.addDir(MergeDicts(cItem, {'good_for_fav':False, 'category':'sub_items', 'title':sTitle, 'sub_items':subItems}))
            else:
                self.addDir(MergeDicts(cItem, {'good_for_fav':True, 'category':nextCategory, 'title':sTitle, 'url':sUrl}))

    def exploreDigiSite(self, cItem):
        printDBG("exploreDigiSite")
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: return
        cUrl = self.cm.meta['url']
        page = cItem.get('page', 1)

        if cItem.get('allow_sort', True):
            tmp = ph.find(data, ('<ul', '>', 'dropdown-menu'), '</ul>', flags=0)[1]
            tmp = ph.findall(tmp, ('<a', '>'), '</a>')
            for item in tmp:
                title = ph.clean_html(item)
                url = self.getFullUrl(ph.getattr(item, 'href'),  cUrl)
                self.addDir(MergeDicts(cItem, {'good_for_fav':False, 'allow_sort':False, 'title':title, 'url':url}))

            if self.currList:
                return

        sections = ph.findall(data, ('<section', '>'), '</section>', flags=0)
        for section in sections:
            tmp = ph.find(section, ('<', '>', 'grid-links'), '</ul>', flags=0)[1]
            if not tmp: tmp = ph.find(section, ('<div', '>', 'custom-grid row'), '</ul>', flags=0)[1]
            if tmp:
                tmp2 = section.split('<ul', 1)[0]
                url = self.getFullUrl(ph.search(tmp2, ph.A_HREF_URI_RE)[1],  cUrl)
                if url.endswith('/video'):
                    self.exploreDigiSite(MergeDicts(cItem, {'url':url}))

                if self.currList:
                    return

            tmp = ph.findall(tmp, ('<li', '>'), '</li>', flags=0)
            printDBG(tmp)
            for item in tmp:
                title = ph.clean_html(ph.find(item, ('<h3', '>'), '</h3>', flags=0)[1])
                item = item.split('</div>', 1)
                url = self.getFullUrl(ph.search(item[0], ph.A_HREF_URI_RE)[1],  cUrl)
                icon = self.getFullUrl(ph.search(item[0], ph.IMAGE_SRC_URI_RE)[1],  cUrl)

                descData = ph.findall(item[0], ('<p', '>'), '</p>', flags=0)
                descData.extend(ph.findall(item[0], ('<span', '>'), '</span>', flags=0))
                if not descData and not title: continue
                if not title: title = self.cleanHtmlStr(descData[0])
                desc = []
                for idx in range(1, len(descData)):
                    t = ph.clean_html(descData[idx])
                    if t: desc.append(t)
                desc = ' | '.join(desc) + '[/br]' + ph.clean_html(item[-1])
                params = MergeDicts(cItem, {'good_for_fav':True, 'allow_sort':True, 'url':url, 'desc':desc, 'icon':icon})
                if '/video/' in url:
                    if title.startswith('odc.') and cItem.get('prev_title'):
                        title = '%s: %s' % (cItem['prev_title'], title)
                    params.update({'title':title})
                    self.addVideo(params)
                else:
                    params.update({'title':title, 'prev_title':title})
                    self.addDir(params)

            if self.currList:
                nextPage = ph.find(section, ('<ul', '>', 'pagination'), '</ul>', flags=0)[1]
                nextPage = ph.find(nextPage, ('<li', '>', 'page="%s"' % (page + 1)), '</li>', flags=0)[1]
                nextPage = self.getFullUrl(ph.search(nextPage, ph.A_HREF_URI_RE)[1], cUrl)
                if nextPage:
                    self.addDir(MergeDicts(cItem, {'good_for_fav':False, 'title':_('Next page'), 'url':nextPage}))
                return

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TvpVod.handleService start')
        if None == self.loggedIn:
            premium = config.plugins.iptvplayer.tvpvod_premium.value
            if premium:
                self.loggedIn, msg = self.tryTologin()
                if self.loggedIn != True: self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 10 )

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        
        self.informAboutGeoBlockingIfNeeded('PL')
        
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "TvpVod.handleService: ---------> name[%s], category[%s] " % (name, category) )
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []
        currItem = dict(self.currItem)
        currItem.pop('good_for_fav', None)
        
        if None != name and  self.currItem.get('desc', '').startswith('Użytkownik'):
            currItem.pop('desc', None)
        
        if None == name:
            self.listsTab(TvpVod.VOD_CAT_TAB, {'name':'category', 'desc':self.loginMessage})
    # STREAMS
        elif category == 'streams':
            self.listsTab(TvpVod.STREAMS_CAT_TAB, currItem)
        elif category == 'tvp3_streams':
            self.listTVP3Streams(currItem)
        elif category == 'week_epg':
            self.listWeekEPG(currItem, 'epg_items')
        elif category == 'epg_items':
            self.listEPGItems(currItem)

        elif category == 'tvpsport_streams':
            self.listTVPSportStreams(currItem, 'sub_items')
        elif category == 'sub_items':
            self.currList = currItem.get('sub_items', [])
    # TVP SPORT
        elif category == 'tvp_sport':    
            self.listTVPSportCategories(currItem, 'tvp_sport_list_items')
    # LIST TVP SPORT VIDEOS
        elif category == 'tvp_sport_list_items':
            self.listTVPSportVideos(currItem)
        elif category == 'vods_list_cats':
            self.listCatalog(currItem, 'vods_explore_item')
        elif category == 'vods_explore_item':
            self.exploreVODItem(currItem, 'vods_explore_item')

    # Reconstruction
        elif category == 'digi_menu':
            self.listDigiMenu(currItem, 'digi_explore_site')
        elif category == 'digi_explore_site':
            self.exploreDigiSite(currItem)

    #WYSZUKAJ
        elif category == "search":
            cItem = dict(currItem)
            cItem.update({'category':'list_search', 'searchPattern':searchPattern, 'searchType':searchType, 'search_item':False})            
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "list_search":
            cItem = dict(currItem)
            searchPattern = cItem.get('searchPattern', '')
            searchType    = cItem.get('searchType', '')
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TvpVod(), True, [])