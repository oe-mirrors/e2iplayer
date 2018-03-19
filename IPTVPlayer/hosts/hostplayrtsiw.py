# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSearchHistoryHelper, GetPluginDir, byteify, rm, PrevDay
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
import Plugins.Extensions.IPTVPlayer.libs.urlparser as urlparser
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.asynccall import iptv_js_execute
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta

###################################################

###################################################
# FOREIGN import
###################################################
import time
import re
import urllib
import string
import random
import base64
from urlparse import urlparse
from binascii import hexlify, unhexlify
from hashlib import md5
try:    import json
except Exception: import simplejson as json
from datetime import datetime, timedelta
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tv3player_use_web_proxy = ConfigYesNo(default=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use web-proxy for VODs (it may be illegal):"), config.plugins.iptvplayer.tv3player_use_web_proxy))
    return optionList
###################################################


def gettytul():
    return 'https://srgssr.ch/'

class PlayRTSIW(CBaseHostClass): 
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'PlayRTSIW.tv', 'cookie':'rte.ie.cookie', 'cookie_type':'MozillaCookieJar'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.PORTALS_MAP = {'rtr':{'title':'RTR', 'url':'https://www.rtr.ch/play/tv',        'icon':'https://www.rtr.ch/play/static/img/srg/rtr/playrtr_logo.png'},
                            'srf':{'title':'SRF', 'url':'https://www.srf.ch/play/tv',        'icon':'https://www.srf.ch/play/static/img/srg/srf/playsrf_logo.png'},
                            'rsi':{'title':'RSI', 'url':'https://www.rsi.ch/play/tv',        'icon':'https://www.rsi.ch/play/static/img/srg/rsi/playrsi_logo.png'},
                            'swi':{'title':'SWI', 'url':'https://play.swissinfo.ch/play/tv', 'icon':'https://play.swissinfo.ch/play/static/img/srg/swi/playswi_logo.png'},
                            'rts':{'title':'RTS', 'url':'http://www.rts.ch/play/tv',         'icon':'http://www.rts.ch/play/static/img/srg/rts/playrts_logo.png'},}
        self.SEARCH_ICON_URL = 'https://www.srgssr.ch/fileadmin/dam/images/quicklinks/srgssr-auf-einen-blick.png'
        self.DEFAULT_ICON_URL = 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/SRG_SSR_2011_logo.svg/2000px-SRG_SSR_2011_logo.svg.png'
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.cacheShowsMap = []
        self.cacheShowsAZ = []
        
    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)
    
    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        lurl = url.lower()
        if url != '' and '/scale/' not in url and \
           not lurl.endswith('.png') and \
           not lurl.endswith('.jpg') and \
           not lurl.endswith('.jpeg'):
            url += '/scale/width/344'
        return url
        
    def listMainMenu(self, cItem):
        printDBG("PlayRTSIW.listMainMenu")
        for portal in ['rtr', 'rsi', 'srf', 'rts', 'swi']:
            params = dict(cItem)
            params.update(self.PORTALS_MAP[portal])
            params.update({'category':'portal', 'portal':portal, 'desc':params['url']})
            self.addDir(params)
        
        MAIN_CAT_TAB = [{'category':'search',          'title': _('Search'), 'search_item':True, 'icon':self.SEARCH_ICON_URL},
                        {'category':'search_history',  'title': _('Search history'),             'icon':self.SEARCH_ICON_URL}]
        #self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listPortalMain(self, cItem):
        printDBG("PlayRTSIW.listPortalMain")
        self.cacheShowsMap = []
        self.cacheShowsAZ = []
        
        self.setMainUrl(cItem['url'])
        self.DEFAULT_ICON_URL = cItem['icon']
        portal = cItem['portal']
        
        params = dict(cItem)
        params.update({'category':'list_teaser_items', 'title':_('Latest'), 'url':self.getFullUrl('/play/tv/videos/latest?numberOfVideos=100&moduleContext=homepage')})
        self.addDir(params)
        
        params = dict(cItem)
        params.update({'category':'list_teaser_items', 'title':_('Most popular'), 'url':self.getFullUrl('/play/tv/videos/trending?numberOfVideos=23&onlyEpisodes=true&includeEditorialPicks=true')})
        self.addDir(params)
        
        if portal != 'swi':
            params = dict(cItem)
            params.update({'category':'list_days', 'title':_('List by day'), 'icon':'http://icons.iconarchive.com/icons/paomedia/small-n-flat/1024/calendar-icon.png'})
            self.addDir(params)
        
        # chek if categories are available
        url = self.getFullUrl('/play/v2/tv/topicList?numberOfMostClicked=1&numberOfLatest=1&moduleContext=topicpaget')
        sts, data = self.cm.getPage(url)
        if not sts: return
        try:
            if len(json.loads(data)):
                params = dict(cItem)
                params.update({'category':'list_cats', 'title':_('Categories')})
                self.addDir(params)
        except Exception:
            printExc()
            
        # check AZ
        if portal != 'swi':
            url = self.getFullUrl('/play/v2/tv/shows/atoz/index')
            sts, data = self.cm.getPage(url)
            if not sts: return
            try:
                self.cacheShowsAZ = byteify(json.loads(data))
            except Exception:
                printExc()
            if len(self.cacheShowsAZ):
                params = dict(cItem)
                params.update({'category':'list_az', 'title':_('AZ')})
                self.addDir(params)
        
    def listCats(self, cItem, nextCategory1, nextCategory2):
        printDBG("PlayRTSIW.listCats")
        url = self.getFullUrl('/play/v2/tv/topicList?numberOfMostClicked=100&numberOfLatest=100&moduleContext=topicpaget')
        
        sts, data = self.cm.getPage(url)
        if not sts: return
        try:
            data = byteify(json.loads(data))
            for item in data:
                sTitle = self.cleanHtmlStr(item['title'])
                sUrl = self.getFullUrl(item['url'])
                
                latestSubItems = []
                mostSubItems = []
                
                for it in  item.get('subTopics', []):
                    title = self.cleanHtmlStr(it['title'])
                    url = self.getFullUrl(it['url'])
                    
                    if 'latestModuleUrl' in it: 
                        params = dict(cItem)
                        params.update({'category':nextCategory2, 'url':self.getFullUrl(it['latestModuleUrl']), 'title':title})
                        latestSubItems.append(params)
                        
                    if 'mostClickedModuleUrl' in it: 
                        params = dict(cItem)
                        params.update({'category':nextCategory2, 'url':self.getFullUrl(it['mostClickedModuleUrl']), 'title':title})
                        mostSubItems.append(params)
                
                subItems = []
                
                if len(latestSubItems):
                    if 'latestModuleUrl' in item:
                        params = dict(cItem)
                        params.update({'category':nextCategory2, 'url':self.getFullUrl(item['latestModuleUrl']), 'title':_('--All--')})
                        latestSubItems.insert(0, params)
                    params = dict(cItem)
                    params.update({'category':nextCategory1, 'title':_('Most recent'), 'sub_items':latestSubItems})
                    subItems.append(params)
                else:
                    if 'latestModuleUrl' in item:
                        params = dict(cItem)
                        params.update({'category':nextCategory2, 'url':self.getFullUrl(item['latestModuleUrl']), 'title':_('Most recent')})
                        subItems.append(params)
                
                if len(mostSubItems):
                    if 'mostClickedModuleUrl' in item:
                        params = dict(cItem)
                        params.update({'category':nextCategory2, 'url':self.getFullUrl(item['mostClickedModuleUrl']), 'title':_('--All--')})
                        mostSubItems.insert(0, params)
                    params = dict(cItem)
                    params.update({'category':nextCategory1, 'title':_('Most recent'), 'sub_items':mostSubItems})
                    subItems.append(params)
                else:
                    if 'mostClickedModuleUrl' in item:
                        params = dict(cItem)
                        params.update({'category':nextCategory2, 'url':self.getFullUrl(item['mostClickedModuleUrl']), 'title':_('Most recent')})
                        subItems.append(params)
                
                params = dict(cItem)
                if len(subItems) > 1:
                    params.update({'category':nextCategory1, 'url':sUrl, 'title':sTitle, 'sub_items':subItems})
                    self.addDir(params)
                elif len(subItems) == 1 and 'sub_items' not in subItems[0]:
                    params.update({'category':nextCategory2, 'url':subItems[0]['url'], 'title':sTitle})
                    self.addDir(params)
        except Exception:
            printExc()
            
    def listDays(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listDays [%s]" % cItem)
        if 'f_date' not in cItem: dt = datetime.now()
        else: dt = datetime.strptime(cItem['f_date'], '%d-%m-%Y').date()
        baseUrl = self.getFullUrl('/play/v2/tv/programDay/')
        for item in range(31):
            title = dt.strftime('%d-%m-%Y')
            url = baseUrl + title
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':url})
            self.addDir(params)
            dt = PrevDay(dt)
        
        params = dict(cItem)
        params.update({'good_for_fav':False, 'title':_('Older'), 'f_date':dt.strftime('%d-%m-%Y')})
        self.addDir(params)
        
    def _listVideosItems(self, cItem, data):
        printDBG("PlayRTSIW._listVideosItems")
        try:
            for item in data:
                title = item['title']
                url = item['absoluteDetailUrl']
                icon = self.getFullIconUrl(item['imageUrl'])
                desc = [item['duration'], item['date']]
                if item['isGeoblocked']: desc.append(_('geoblocked'))
                descTab = []
                descTab.append(item['showTitle'])
                descTab.append(', '.join(desc))
                descTab.append(item.get('description', ''))
                
                params = dict(cItem)
                params.update({'good_for_fav':True, 'title':title, 'url':url, 'video_id':item['id'], 'popup_url':self.getFullUrl(item['popupUrl']), 'detail_url':self.getFullUrl(item['detailUrl']), 'icon':icon, 'desc':'[/br]'.join(descTab)})
                if 'downloadHdUrl' in item: params['download_hd_url'] = item['downloadHdUrl']
                if 'downloadSdUrl' in item: params['download_sd_url'] = item['downloadSdUrl']
                self.addVideo(params)
        except Exception:
            printExc()
        
    def listTeaserItems(self, cItem):
        printDBG("PlayRTSIW.listTeaserItems")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, 'data-teaser="', '"', False)
        for data in tmp:
            data = clean_html(data)
            try:
                data = byteify(json.loads(data))
                self._listVideosItems(cItem, data)
            except Exception:
                printExc()
                
    def listAZ(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listAZ cItem[%s]" % (cItem))
        
        try:
            allLetters = []
            for item in self.cacheShowsAZ:
                if not item['hasShows']: continue
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title':item['id'], 'category':nextCategory, 'f_letters':[item['id']]})
                self.addDir(params)
                allLetters.append(item['id'])
        except Exception:
            printExc()
        
        if len(allLetters):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('All'), 'category':nextCategory, 'f_letters':allLetters})
            self.currList.insert(0, params)
            
    def listAZItems(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listAZItems cItem[%s]" % (cItem))
        if self.cacheShowsMap == []:
            url = self.getFullUrl('/play/v2/tv/shows')
            
            sts, data = self.cm.getPage(url)
            if not sts: return
            
            data = clean_html(self.cm.ph.getDataBeetwenMarkers(data, 'data-alphabetical-sections="',  '"', False)[1])
            try:
                self.cacheShowsMap = byteify(json.loads(data))
            except Exception:
                printExc()
        
        letters = cItem.get('f_letters', '')
        try:
            for section in self.cacheShowsMap:
                if section['id'] not in letters: continue
                for item in section['showTeaserList']:
                    title = self.cleanHtmlStr(item['title'])
                    icon = self.getFullIconUrl(item['imageUrl'])
                    url = item['absoluteOverviewUrl']
                    desc = []
                    if 'episodeCount' in item and item['episodeCount']['isDefined']: desc.append(_('%s episodes') % item['episodeCount']['formatted'])
                    desc.append(self.cleanHtmlStr(item.get('description', '')))
                    sUrl = self.getFullUrl('/play/tv/show/%s/latestEpisodes' % item['id'])
                    
                    params = dict(cItem)
                    params.update({'good_for_fav':True, 'title':title, 'category':nextCategory, 'url':url, 'f_show_url':sUrl, 'icon':icon, 'desc':'[/br]'.join(desc)})
                    self.addDir(params)
        except Exception:
            printExc()
            
    def listEpisodes(self, cItem):
        printDBG("PlayRTSIW.listEpisodes cItem[%s]" % (cItem))
        
        sts, data = self.cm.getPage(cItem['f_show_url'])
        if not sts: return
        try:
            data = byteify(json.loads(data))
            self._listVideosItems(cItem, data['episodes'])
            
            nextPage = self.getFullUrl(data['nextPageUrl'])
            if nextPage != '':
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title':_('Next page'), 'f_show_url':nextPage})
                self.addDir(params)
        except Exception:
            printExc()
    
    def listLiveChannels(self, cItem):
        printDBG("PlayRTSIW.listLiveChannels")
        
        descMap = {}
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        
        data = re.sub("<!--[\s\S]*?-->", "", data)
        data = re.compile('''<div[^>]+?class=['"]live_[^>]+?>''').split(data)
        if len(data): del data[0]
        
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+)['"]''')[0] )
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+)['"]''')[0] )
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h4', '</h4>')[1])
            
            item = item.split('top_bar_up_next', 1)
            
            descTab = []
            tmp = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item[0], ('<div', '>', 'progress'), ('</div', '>'))[1] )
            if tmp != '': descTab.append(tmp)
            tmp = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item[0], ('<div', '>', 'time'), ('</div', '>'))[1] )
            if tmp != '': descTab.append(tmp)
            tmp = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item[0], '<p', '</p>')[1].split('<span', 1)[0] )
            if tmp != '': descTab.append(tmp)
            descTab.append("")            
            tmp = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item[-1], '<span', '</span>')[1] )
            if tmp != '': descTab.append(tmp)
            tmp = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item[-1], '<p', '</p>')[1] )
            if tmp != '': descTab.append(tmp)
            
            params = dict(cItem)
            params.update({'title':title, 'url':url, 'icon':icon, 'desc':'[/br]'.join(descTab)})
            self.addVideo(params)
            
    def listSubItems(self, cItem):
        printDBG("PlayRTSIW.listSubItems")
        self.currList = cItem['sub_items']
            
    def _listItems(self, data, nextCategory='explore_show', baseTitle='%s'):
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+)['"]''')[0] )
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+)['"]''')[0] )
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h4', '</h4>')[1])
            date = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'list_date'), ('</p', '>'))[1])
            time = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'list_time'), ('</span', '>'))[1])
            
            descTab = []
            
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<p', '>'), ('</p', '>'))
            for t in tmp:
                t = t.split('<span', 1)
                for idx in range(len(t)):
                    if idx == 1: t[idx] = '<span' + t[idx]
                    txt = self.cleanHtmlStr(t[idx])
                    if txt != '' and txt != date: descTab.append(txt)
            
            if time != '' and len(descTab): descTab.insert(1, time)
            
            params = {'good_for_fav':True, 'title':baseTitle % title, 'url':url, 'icon':icon, }
            if '/videos/' in icon:
                if date not in params['title']: params['title'] = params['title'] + ': ' + date
                if len(descTab): params['desc'] = ' | '.join(descTab[1:]) + '[/br]' + descTab[0]
                self.addVideo(params)
            else: 
                params.update({'name':'category', 'type':'category', 'category':nextCategory, 'desc':'[/br]'.join(descTab)})
                self.addDir(params)
            
    def exploreShow(self, cItem, nextCategory):
        printDBG("PlayRTSIW.exploreShow cItem[%s]" % (cItem))
        
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'data-type'), ('</a', '>'))
        for item in data:
            showId = self.cm.ph.getSearchGroups(item, '''data\-showID=['"]([0-9]+?)['"]''')[0]
            dataType = self.cm.ph.getSearchGroups(item, '''data\-type=['"]([^'^"]+?)['"]''')[0]
            videoID = self.cm.ph.getSearchGroups(item, '''data\-videoID=['"]([0-9]+?)['"]''')[0]
            if '' in [showId, dataType]: continue
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl('/player_2015/assets/ajax/filter_tiles.php?showID={0}&videoID=&type={1}'.format(showId, dataType))
            params = dict(cItem)
            params.update({'good_for_fav':True, 'category':nextCategory, 'title':title.title(), 'f_show_title':cItem['title'], 'url':url, 'f_show_id':showId, 'f_data_type':dataType})
            self.addDir(params)
        
        if 0 == len(self.currList):
            dataType = 'all'
            showId = self.cm.ph.getSearchGroups(cItem['url'] + '/', '''/show/([0-9]+?)[^0-9]''')[0]
            if showId != '':
                url = self.getFullUrl('/player_2015/assets/ajax/filter_tiles.php?showID={0}&videoID=&type={1}'.format(showId, dataType))
                cItem = dict(cItem)
                cItem.update({'good_for_fav':True, 'category':nextCategory, 'title':_('All'), 'f_show_title':cItem['title'], 'url':url, 'f_show_id':showId, 'f_data_type':dataType})
                self.listItems(cItem, 'explore_show')
            
    def listItems(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listItems cItem[%s]" % (cItem))
        page = cItem.get('page', 0)
        showTitle = cItem['f_show_title']
        
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        
        items = re.compile('''<div[^>]+?class=['"]clear['"][^>]*?>''').split(data)
        if len(items): del items[-1]
        self._listItems(items, baseTitle='{0}: %s'.format(showTitle))
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'load_more'), ('</a', '>') )[1]
        if data != '':
            showId = self.cm.ph.getSearchGroups(data, '''data\-showID=['"]([0-9]+?)['"]''')[0]
            offset = self.cm.ph.getSearchGroups(data, '''data\-offset=['"]([0-9]+?)['"]''')[0]
            id = self.cm.ph.getSearchGroups(data, '''\sid=['"]([^'^"]+?)['"]''')[0]
            if '' not in [showId, offset, id]:
                url = self.getFullUrl('/player_2015/assets/ajax/{0}.php?showID={1}&videoID=&offset={2}&type={3}'.format(id, showId, offset, cItem['f_data_type']))
                params = dict(cItem)
                params.update({'good_for_fav':False, 'url':url, 'title':_('Next page'), 'page':page+1})
                self.addDir(params)
            

        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("PlayRTSIW.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        url = self.getFullUrl('/player_2015/assets/ajax/search.php')
        post_data = {'queryString':searchPattern, 'limit':100}
        
        sts, data = self.cm.getPage(url, post_data=post_data)
        if not sts: return
        
        printDBG(data)
        
        itemsReObj = re.compile('''<div[^>]+?list_row[^>]+?>''')
        
        data = re.compile('''<div[^>]+?list_title[^>]+?>''').split(data)
        if len(data): del data[0]
        
        for section in data:
            sTtile = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<h2', '</h2>')[1])
            section = itemsReObj.split(section)
            if len(section): del section[0]
            self._listItems(section)
        
    def getLinksForVideo(self, cItem):
        printDBG("PlayRTSIW.getLinksForVideo [%s]" % cItem)
        linksTab = []
        
        if 'download_sd_url' in cItem: linksTab.append({'url':cItem['download_sd_url'], 'name':_('Download %s') % 'SD', 'need_resolve':0})
        if 'download_hd_url' in cItem: linksTab.append({'url':cItem['download_hd_url'], 'name':_('Download %s') % 'HD', 'need_resolve':0})
        
        url = cItem['popup_url'].replace('/tv/popupvideoplayer?', '/v2/tv/popupvideoplayer/content?')
        sts, data = self.cm.getPage(url)
        if sts:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]).replace('&amp;', '&')
            baseUrl = self.cm.getBaseUrl(url)
            urn = self.cleanHtmlStr(self.cm.ph.getSearchGroups(url + '&', '''urn=([^&]+?)&''')[0])
            url = baseUrl.replace('/tp.', '/il.') + 'integrationlayer/2.0/mediaComposition/byUrn/{0}.json?onlyChapters=true&vector=portalplay'.format(urn)
            tokenUrl = baseUrl + 'akahd/token?acl='
            sts, data = self.cm.getPage(url)
            try:
                data = byteify(json.loads(data))
                for item in data['chapterList']:
                    if item['mediaType'] == 'VIDEO':
                        data = item['resourceList']
                        break
                for item in data:
                    mimeType = item['mimeType'].split('/', 1)[-1].lower()
                    if mimeType == 'x-mpegurl': mimeType = 'HLS'
                    elif mimeType == 'mp4': mimeType = 'MP4'
                    else: continue
                    n = item['url'].split('/')
                    url = strwithmeta(item['url'], {'priv_token_url':tokenUrl + '%2F{0}%2F{1}%2F*'.format(n[3], n[4]), 'priv_type':mimeType.lower()})
                    name = '[%s/%s] %s' % (mimeType, url.split('://', 1)[0].upper(), item['quality'])
                    params = {'name':name, 'url':url, 'need_resolve':1}
                    if item['quality'].upper() == 'HD': linksTab.append(params)
                    else: linksTab.insert(0, params)
            except Exception:
                printExc()
        
        return linksTab[::-1]
        
    def getVideoLinks(self, videoUrl):
        printDBG("PlayRTSIW.getVideoLinks [%s]" % videoUrl)
        meta = strwithmeta(videoUrl).meta
        tokenUrl = meta['priv_token_url']
        type = meta['priv_type']
        
        sts, data = self.cm.getPage(tokenUrl)
        try:
            data = byteify(json.loads(data))['token']['authparams']
            if '?' not in videoUrl: videoUrl += '?' + data
            else: videoUrl += '&' + data
        except Exception:
            printExc()
        
        urlTab = []
        if type == 'hls': urlTab = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
        else: urlTab.append({'name':'direct', 'url':videoUrl})
        return urlTab
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'portal':
            self.listPortalMain(self.currItem)
        elif category == 'list_cats':
            self.listCats(self.currItem, 'sub_items', 'list_teaser_items')
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_teaser_items':
            self.listTeaserItems(self.currItem)
        elif category == 'list_days':
            self.listDays(self.currItem, 'list_teaser_items')
        elif category == 'list_az':
            self.listAZ(self.currItem, 'list_az_items')
        elif category == 'list_az_items':
            self.listAZItems(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
            
        elif category == 'list_live':
            self.listLiveChannels(self.currItem)
        elif category == 'explore_show':
            self.exploreShow(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_show')
        elif category == 'list_by_day':
            self.listByDay(self.currItem, 'sub_items', 'list_by_day_items')
        elif category == 'list_by_day_items':
            self.listByDayItems(self.currItem, 'explore_show')

    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, PlayRTSIW(), True, [])
    