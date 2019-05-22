# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVSleep, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetJSScriptFile, PrevDay
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

from Screens.MessageBox import MessageBox

###################################################
# FOREIGN import
###################################################
import urllib
import re
import uuid
import time
import datetime
import math
import cookielib
import datetime
from datetime import timedelta
###################################################


def gettytul():
    return 'https://mediasetplay.it/'

class MediasetPlay(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'mediasetplay.it', 'cookie':'mediasetplay.it.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='firefox')
        self.HTTP_HEADER.update({'Referer':'https://www.mediasetplay.mediaset.it/', 'Accept':'application/json', 'Content-Type':'application/json'})
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL    = 'https://www.mediasetplay.mediaset.it/'
        self.API_BASE_URL = 'https://api-ott-prod-fe.mediaset.net/PROD/play'
        self.API_LIVE_URL = self.API_BASE_URL + '/alive/nownext/v1.0?channelId={0}' 
        self.API_EPG_URL = self.API_BASE_URL + '/alive/allListingFeedFilter/v1.0?byListingTime=%interval%&byVod=true&byCallSign=%cs%'
        self.FEED_URL = 'https://feed.entertainment.tv.theplatform.eu/f/PR1GhC'
        self.FEED_CHANNELS_URL = self.FEED_URL + '/mediaset-prod-all-stations?sort=mediasetstation$comscoreVodChId'
        self.FEED_SHOW_URL = self.FEED_URL + '/mediaset-prod-all-brands?byCustomValue={brandId}{%brandId%}&sort=mediasetprogram$order'
        self.FEED_SHOW_SUBITEM_URL = self.FEED_URL + '/mediaset-prod-all-programs?byCustomValue={brandId}{%brandId%},{subBrandId}{%subBrandId%}&sort=mediasetprogram$publishInfo_lastPublished|desc&count=true&entries=true&range=0-200'
        self.FEED_EPISODE_URL = self.FEED_URL + '/mediaset-prod-all-programs?byGuid={0}'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/originals/34/67/9b/34679b83e426516b478ba9d63dcebfa2.png' #'http://www.digitaleterrestrefacile.it/wp-content/uploads/2018/07/mediaset-play.jpg' #'https://cdn.one.accedo.tv/files/5b0d3b6e23eec6000dd56c7f'

        self.cacheLinks = {}
        self.initData = {}
        
    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}: addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getVideoLinks(self, videoUrl):
        printDBG("MediasetPlay.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
        
        type = strwithmeta(videoUrl).meta.get('priv_type', '')
        if type == 'DASH/MPD':
            return getMPDLinksWithMeta(videoUrl, checkExt=False, sortWithMaxBandwidth=999999999)
        elif type == 'HLS/M3U8':
            return getDirectM3U8Playlist(videoUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=999999999)

        return []
    
    def getLinksForVideo(self, cItem):
        printDBG(": %s" % cItem)
        self.initApi()

        linksTab=[]

        if cItem['category'] == 'onair':
            channelId = cItem.get('call_sign')
            url = self.API_LIVE_URL.format(channelId)
            sts, data = self.getPage(url)
            if not sts: return

            data = json_loads(data)
            for tuningInstructions in data['response']['tuningInstruction'].itervalues():
                for item in tuningInstructions:
                    printDBG(" ------------>>>>>> " + str(item))
                    url = item['publicUrls'][0]
                    if 'mpegurl' in item['format'].lower():
                        f = 'HLS/M3U8'
                    
                    linksTab.append({'name':f, 'url': url})
        elif cItem['category'] == 'epg_video':
            url = self.FEED_EPISODE_URL.format(cItem["guid"])
            sts, data = self.getPage(url)
            if not sts: return
            url = json_loads(data)['entries'][0]['media'][0]['publicUrl']
            linksTab.append({'name': 'link', 'url': url})
       
        else:
            linksTab.append({'name': 'link', 'url': cItem["url"]})

        printDBG(str(linksTab))
        return linksTab
    
    def initApi(self):
        if self.initData: return 
        url = self.API_BASE_URL + '/idm/anonymous/login/v1.0'
        params = MergeDicts(self.defaultParams, {'raw_post_data':True, 'collect_all_headers':True})
        cid = str(uuid.uuid4())
        post_data = '{"cid":"%s","platform":"pc","appName":"web/mediasetplay-web/2e96f80"}' % cid

        sts, data = self.getPage(url, params, post_data=post_data)
        if not sts: return
        printDBG(data)
        printDBG(self.cm.meta)
        try:
            headers = {'t-apigw':self.cm.meta['t-apigw'], 't-cts':self.cm.meta['t-cts']}
            data = json_loads(data)
            if data['isOk']:
                tmp = data['response']
                self.initData.update({'traceCid':tmp['traceCid'], 'cwId':tmp['cwId'], 'cid':cid})
                self.HTTP_HEADER.update(headers)
        except Exception:
            printExc()
        
        if not self.initData: self.sessionEx.waitForFinishOpen(MessageBox, _("API initialization failed!"), type=MessageBox.TYPE_ERROR, timeout=20)
    
    def listMain(self, cItem):
        printDBG("MediasetPlay.listMain")
        MAIN_CAT_TAB = [{'category':'ondemand', 'title': 'Programmi on demand'},
                        {'category':'onair', 'title': 'Dirette tv'},
                        {'category':'channels', 'title': 'Canali'}]
        self.listsTab(MAIN_CAT_TAB, cItem)  

    def getChannelList(self):
        
        sts, data = self.getPage(self.FEED_CHANNELS_URL)
        if not sts: return
        channels=[]

        data = json_loads(data)
        for item in data['entries']:
            if 'vip' in item['mediasetstation$pageUrl']: continue
            icon = self.getFullIconUrl( item['thumbnails']['channel_logo-100x100']['url']) #next(iter(item['thumbnails']))['url'] )
            title = item['title']
            url = self.getFullIconUrl( item['mediasetstation$pageUrl'] )
            chNum = item ["mediasetstation$comscoreVodChId"]
            channels.append ( {'title':title, 'url':url, 'icon':icon, 'call_sign':item['callSign']})
            
        return channels
    
    def listOnAir(self, cItem):
        printDBG("MediasetPlay.listOnAir")

        channels=self.getChannelList()
        for item in channels:
            self.addVideo(MergeDicts(cItem, {'category': 'onair', 'good_for_fav':True, 'title': item["title"] , 'url': item["url"], 'icon': item["icon"], 'call_sign': item['call_sign']}))

    def listChannels(self,cItem):
        printDBG("MediasetPlay.listChannels")
        channels=self.getChannelList()
        for item in channels:
            self.addDir(MergeDicts(cItem, {'category': 'channel', 'title': item["title"] , 'icon': item["icon"], 'call_sign': item['call_sign']}))

    def listChannelItems(self, cItem):
        printDBG("MediasetPlay.listChannelItems")
        call_sign = cItem['call_sign']

        days = ["Domenica", "Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]
        months = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    
        for i in range(7):
            day = datetime.date.today() - datetime.timedelta(days = i)
            start = datetime.datetime(day.year,day.month,day.day,0,0,0) 
            end = start + datetime.timedelta(days=1, hours=2)
            s = int (time.mktime(start.timetuple())* 1000)
            e = int(time.mktime(end.timetuple()) * 1000)
            interval = "%s~%s" % (s, e)
            printDBG("Ricerca fra i tempi unix : " + interval)
            day_str = days[int(day.strftime("%w"))] + " " + day.strftime("%d") + " " + months[int(day.strftime("%m"))-1]
            self.addDir(MergeDicts(cItem, {'good_for_fav':False, 'category':'list_time', 'title': day_str , 'name': day.strftime("%d-%m-%Y"), 'interval': interval}))              
   
    def getDateTimeFromStr(self,s):
        sec=int(s)/1000
        t=time.localtime(sec)
        return t
    
    def listEPG(self,cItem):
        printDBG("MediasetPlay.listEPG")
        url = self.API_EPG_URL.replace('%interval%',cItem['interval']).replace('%cs%',cItem['call_sign'])
        
        sts, data = self.getPage(url)
        if not sts: return
        
        data = json_loads(data)['response']
        for item2 in data['entries'][0]['listings']:
            d1 = self.getDateTimeFromStr(item2["startTime"])
            d2 = self.getDateTimeFromStr(item2["endTime"])
            title = "%02d:%02d-%02d:%02d     " % (d1[3],d1[4],d2[3],d2[4]) + item2["mediasetlisting$epgTitle"] 

            item = item2['program']
            guid = item['guid']
            icon = item['thumbnails']['image_keyframe_poster-292x165']['url']

            desc = []
            desc.append(item['mediasetprogram$publishInfo']['last_published'].split('T', 1)[0]) 
            desc.append(item['mediasetprogram$publishInfo']['description']) 
            desc.append(str(timedelta(seconds=int(item['mediasetprogram$duration']))))
            desc.append(_('%s views') % item['mediasetprogram$numberOfViews'] )
            desc = [' | '.join(desc)]
            desc.append(item['title'])
            desc.append(item.get('description', ''))
            
            self.addVideo( {'good_for_fav':True, 'category': 'epg_video', 'title':title, 'icon':icon, 'desc':'\n'.join(desc), 'guid':guid})
    
    def listOnDemand(self, cItem):
        printDBG("MediasetPlay.listMain")
        
        MAIN_CAT_TAB = [{'category':'az', 'title': 'Programmi on demand'},
                        {'category':'onair', 'title': 'Dirette tv'},
                        {'category':'channels', 'title': 'Canali'}]
        self.listsTab(MAIN_CAT_TAB, cItem)  

    def listAZFilters(self, cItem, nextCategory):
        printDBG('MediasetPlay.listAZFilters')
        idx = cItem.get('az_filter_idx', 0)
        cItem = MergeDicts(cItem, {'az_filter_idx':idx + 1})
        if idx == 0:
            filtersTab = [{'title': 'Tutti generi'},
                          {'title': 'Programmi Tv', 'f_category':'Programmi Tv'},
                          {'title': 'Cinema',       'f_category':'Cinema'},
                          {'title': 'Fiction',      'f_category':'Fiction'},
                          {'title': 'Documentari',  'f_category':'Documentari'},
                          {'title': 'Kids',         'f_category':'Kids'}]
        elif idx == 1:
            filtersTab = [{'title': 'Tutti'},
                          {'title': 'In onda',      'f_onair':True},]
        elif idx == 2:
            cItem['category'] = nextCategory
            filtersTab = []
            #filtersTab.append({'title': 'Tutti',  'f_query':'*:*'})
            for i in range(0, 26): 
                filtersTab.append({'title':chr(ord('A')+i),      'f_query':'TitleFullSearch:%s*' % chr(ord('a')+i)})
            #filtersTab.append({'title': '#',      'f_query':'-(TitleFullSearch:{A TO *})'})
        self.listsTab(filtersTab, cItem)

    def listAZItems(self, cItem, page=0):
        printDBG('MediasetPlay.listAZItems')

        query = {'hitsPerPage':200}
        if 'f_onair' in cItem: 
            query['inOnda'] = 'true'
        url = self.API_BASE_URL + 'rec/azlisting/v1.0?' + urllib.urlencode(query)
        if 'f_query' in cItem: 
            url += '&query=%s' % cItem['f_query'] #query['query'] = cItem['f_query']
        if 'f_category' in cItem: 
            url += '&categories=%s' % cItem['f_category'] #query['categories'] = cItem['f_category']
        if page>0 :
            url += '&page=%s' % page
        
        sts, data = self.getPage(url)
        if not sts: return
        try:
            data = json_loads(data)['response']
            for item in data['entries']:
                title = item['title']
                desc = []
                videoUrl = item.get('mediasetprogram$videoPageUrl', '')
                if videoUrl:
                    desc.append(item['mediasetprogram$publishInfo']['last_published'].split('T', 1)[0]) 
                    desc.append(item['mediasetprogram$publishInfo']['description']) 
                    desc.append(str(timedelta(seconds=int(item['mediasetprogram$duration']))))
                    desc.append(_('%s views') % item['mediasetprogram$numberOfViews'] )
                    desc = [' | '.join(desc)]
                    icon = item['thumbnails']['image_keyframe_poster-292x165']['url']
                    url = item["media"][0]["publicUrl"]
                    guid = item['guid']
                else:
                    icon = item['thumbnails']['image_vertical-264x396']['url']
                    brandId = item["mediasetprogram$brandId"]
                desc.append(item.get('description', ''))
                params = {'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':'[/br]'.join(desc)}
                
                if videoUrl: 
                    self.addVideo(MergeDicts(cItem, params, {'guid':guid, 'category': 'program_video'}))
                else: 
                    self.addDir(MergeDicts(cItem, params, {'category': 'program', 'brandId': brandId}))

            if data.get('hasMore'):
                page = page + 1
                self.addMore(MergeDicts(cItem, {'category': 'program_next', 'title': _('Next page'), 'page_number': page}))              
        except Exception:
            printExc()

    def listProgramItems(self, cItem):
        brandId=cItem["brandId"]    
        url = self.FEED_SHOW_URL.replace('%brandId%',brandId)
        sts, data = self.getPage(url)
        if not sts: return
        
        data = json_loads(data)
        for entry in data['entries']:
            if 'mediasetprogram$subBrandId' in entry:
                desc = entry['description']
                subBrandId=entry['mediasetprogram$subBrandId']
                self.addDir(MergeDicts(cItem, {"title": desc, "subBrandId": subBrandId, "category": "program_item"}))

    
    def listProgramSubItems(self, cItem):

        brandId = cItem["brandId"]
        subBrandId = cItem["subBrandId"]
        url = self.FEED_SHOW_SUBITEM_URL.replace('%brandId%', brandId).replace('%subBrandId%', subBrandId)
    
        sts, data = self.getPage(url)
        if not sts: return
        
        data = json_loads(data)
        for item in data['entries']:
            desc = []
            desc.append(item['mediasetprogram$publishInfo']['last_published'].split('T', 1)[0]) 
            if 'description' in item['mediasetprogram$publishInfo']:
                desc.append(item['mediasetprogram$publishInfo']['description']) 
            desc.append(str(timedelta(seconds=int(item['mediasetprogram$duration']))))
            desc.append(_('%s views') % item['mediasetprogram$numberOfViews'] )
            
            desc = [' | '.join(desc)]
            desc.append(item.get('description', ''))
            icon = item['thumbnails']['image_keyframe_poster-292x165']['url']
            url = item['media'][0]['publicUrl']
            title = item ["title"]
            self.addVideo ({'category': 'program_video', 'title' : title , 'desc': '\n'.join(desc) , 'url' : url, 'icon' : icon})                
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "handleService: ||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        self.initApi()

    #MAIN MENU
        if name == None:
            self.listMain(self.currItem)
        elif category == 'onair':
            self.listOnAir(self.currItem)
        elif category == 'ondemand':
            self.listAZFilters(self.currItem, 'list_az_item')
        elif category == 'list_az_item':
            self.listAZItems(self.currItem)
        elif category == 'list_az_item_next':
            self.listAZItems(self.currItem, self.currItem["page_number"])
        elif category == 'channels':
            self.listChannels(self.currItem)
        elif category == 'channel':
            self.listChannelItems(self.currItem)
        elif category == 'list_time':
            self.listEPG(self.currItem)
        elif category == 'program':
            self.listProgramItems(self.currItem)
        elif category == 'program_item':
            self.listProgramSubItems(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, MediasetPlay(), True, [])

