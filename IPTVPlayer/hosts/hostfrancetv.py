# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, NextDay, PrevDay, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps

###################################################

###################################################
# FOREIGN import
###################################################
import time, sys
import urllib
from datetime import date, datetime, timedelta
from Components.config import config, ConfigText, getConfigListEntry, ConfigYesNo
import re
###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.francetv_skip_geoblocked = ConfigYesNo(default = True)
#config.plugins.iptvplayer.francetv_use_x_forwarded_for = ConfigYesNo(default = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Skip geo-blocked links:"), config.plugins.iptvplayer.francetv_skip_geoblocked))
#    optionList.append(getConfigListEntry(_("Bypass geo-blocking for VODs (it may be illegal):"), config.plugins.iptvplayer.francetv_use_x_forwarded_for))

    return optionList
###################################################


def gettytul():
    return 'https://www.france.tv/'

class FranceTv(CBaseHostClass):

    def __init__(self):

        CBaseHostClass.__init__(self)

        self.MAIN_URL = 'https://www.france.tv'
        self.API_URL = 'http://api-front.yatta.francetv.fr'
        self.CHANNEL_URL = self.API_URL + '/standard/publish/channels'
        self.LIVE_URL = self.API_URL + '/standard/edito/directs'
        self.CATEGORIES_URL = self.API_URL +'/standard/publish/categories'
        self.PROGRAM_URL = self.API_URL + '/standard/publish/taxonomies'
        self.VIDEO_API_URL = 'http://sivideo.webservices.francetelevisions.fr/tools/getInfosOeuvre/v2/'
        self.GEOLOCATION_API_URL = 'http://geo.francetv.fr/ws/edgescape.json'
        self.VIDEO_TOKEN_URL = 'http://hdfauthftv-a.akamaihd.net/esi/TA'
        self.DEFAULT_ICON_URL = 'https://eige.europa.eu/sites/default/files/styles/eige_large/public/images/17.png?itok=Z_FsnSYD'
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER}
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def readDate(self,timestamp):
        # This regex removes all colons and all
        # dashes EXCEPT for the dash indicating + or - utc offset for the timezone
        conformed_timestamp = re.sub(r"[:]|([-](?!((\d{2}[:]\d{2})|(\d{4}))$))", '', timestamp)

        # Split on the offset to remove it. Use a capture group to keep the delimiter
        split_timestamp = re.split(r"[+|-]",conformed_timestamp)
        main_timestamp = split_timestamp[0]
        if len(split_timestamp) == 3:
            sign = split_timestamp[1]
            offset = split_timestamp[2]
        else:
            sign = None
            offset = None

        # Generate the datetime object without the offset at UTC time
        output_datetime = datetime.strptime(main_timestamp , "%Y%m%dT%H%M%S" )
        if offset:
            # Create timedelta based on offset
            offset_delta = datetime.timedelta(hours=int(sign+offset[:-2]), minutes=int(sign+offset[-2:]))
            # Offset datetime with timedelta
            output_datetime = output_datetime + offset_delta
    
        return output_datetime
    
    def parseMediaData(self, media_data):
        
        result = {}
        
        if not media_data:
            return result

        for pattern in media_data.get('patterns') or []:
            if pattern.get('type') in ('hero','carre') and 'w:400' in pattern.get('urls') or {}:
                thumb_file = pattern['urls'].get('w:400')
                if thumb_file:
                    result['thumb'] = self.MAIN_URL + thumb_file
            elif pattern.get('type') == 'vignette_16x9' and 'w:1024' in pattern.get('urls') or {}:
                fanart_file = pattern['urls'].get('w:1024')
                if fanart_file:
                    result['fanart'] = self.MAIN_URL + fanart_file

        return result

    def parseTopicData(self, data, artwork = True):
        metadata = {}
        info = {}
        art = {}

        result = (metadata, info, art)

        if not data:
            return result

        metadata['channel_id'] = data.get('channel')

        topic_id = data.get('url_complete')
        if topic_id:
            metadata['id'] = topic_id.replace('/', '_')

        info['title'] = data.get('label')
        if 'title' in info:
            info['title'] = info['title'].decode('utf-8').capitalize().encode('utf-8')
        info['plot'] = data.get('description') or data.get('synopsis') or data.get('base_line') or info.get('title')

        if artwork:
            art.update(self.parseMediaData(data.get('media_image')))

        return result

    
    def parseVideoData(self, data, live=False):
        metadata = {}
        info = {}
        art = {}

        if not data:
            return (metadata, info, art)

        info['mediatype'] = 'video'
        info['plot'] = data.get('text')
        info['plotoutline'] = data.get('headline_title')
        info['director'] = data.get('director')
        info['year'] = data.get('year') or data.get('production_year')
        info['season'] = data.get('saison')
        info['episode'] = data.get('episode')

        presenter = data.get('presenter')
        if presenter:
            info['cast'] = [presenter.encode('utf-8')]
        cast = [d for d in (data.get('casting') or '').encode('utf-8').split(', ') if d]
        info['cast'] = info.get('cast', []) + cast

        if live:
            metadata['channel_id'] = data.get('channel')

        for media in data.get('content_has_medias') or []:
            if media.get('type') == 'main':
                media_data = media.get('media')
                if media_data:
                    metadata['video_id'] = media_data.get('si_direct_id' if live else 'si_id')
                    metadata['mpaa'] = media_data.get('rating_csa')
                if not live:
                    info['duration'] = media_data.get('duration')
                    
                begin_date = media_data.get('begin_date')
                if begin_date:
                    begin_date = self.readDate(begin_date)
                    info['date'] = begin_date.strftime('%H:%M - %d/%m/%Y')
                    info['dateadded'] = begin_date.strftime('%Y-%m-%d %H:%M:%S')
            elif media.get('type') == 'image':
                art.update(self.parseMediaData(media.get('media')))

        program_title = None
        program_subtitle = data.get('title')
        for taxonomy in data.get('content_has_taxonomys') or []:
            taxonomy_data = taxonomy.get('taxonomy') or {}
            if taxonomy.get('type') == 'channel':
                # A video may have been broadcasted on several channels. Take the first one
                # available
                if 'channel_name' not in metadata:
                    metadata['channel_name'] = taxonomy_data.get('label')
                if 'channel_id' not in metadata:
                    metadata['channel_id'] = taxonomy_data.get('url')
            elif taxonomy.get('type') == 'program':
                program_title = taxonomy_data.get('label')
                if not art:
                    # Use program artwork if TV show artwork is unavailable
                    art.update(self.parseMediaData(taxonomy_data.get('media_image')))
            elif taxonomy.get('type') == 'category':
                if taxonomy_data.get('type') == 'sous_categorie':
                    info['genre'] = taxonomy_data.get('label')
                elif 'genre' not in info and taxonomy_data.get('type') == 'categorie':
                    info['genre'] = taxonomy_data.get('label')

        if 'genre' in info:
            info['genre'] = info['genre'].decode('utf-8').capitalize().encode('utf-8')

        if not program_title and program_subtitle:
            program_title = program_subtitle
        if program_title and program_subtitle and program_title != program_subtitle:
            program_title += ' - ' + program_subtitle

        if live:
            info['title'] = metadata.get('channel_name')
            info['plot'] = program_title
        else:
            info['title'] = program_title

        return (metadata, info, art)
    
    def listLive(self, cItem):
        printDBG("FranceTv.listLive")
        
        results = []
        sts, data = self.getPage (self.LIVE_URL)
        if not sts:
            return results

        data = json_loads(data)
        for channel in data['result']:
            if 'collection' in channel:
                item = channel['collection'][0]
                r = self.parseVideoData(item, live=True)
                printDBG(str(r))        
                url = self.VIDEO_API_URL + "?idDiffusion=%video_id%"
                url = url.replace("%video_id%", r[0]['video_id'])

                if r[2] != {}:
                    params={'title' : r[0]['channel_name'], 'desc': r[1]['plot'], 'icon': r[2]['thumb'], 'url': url, 'category': 'live'}
                else:
                    params={'title' : r[0]['channel_name'], 'desc': r[1]['plot'], 'url': url, 'category': 'live'}
                printDBG(str(params))
                self.addVideo(params)
    
    def listChannels(self, cItem):
        printDBG("FranceTv.listChannels")
        
        sts, data = self.getPage(self.CHANNEL_URL)
        
        if not sts:
            return 
        data = json_loads(data)
        
        for item in data.get('result') or []:
            r = self.parseTopicData(item, True)
            printDBG(str(r))        
            
            if r[2] != {}:
                params={'title' : r[1]['title'], 'desc': r[1]['plot'], 'icon': r[2]['thumb'], 'id': r[0]['id'], 'category': 'ch_item'}
            else:
                params={'title' : r[1]['title'], 'desc': r[1]['plot'], 'id': r[0]['id'], 'category': 'ch_item'}
            self.addDir(params)

    def listItems(self,cItem):
        printDBG("FranceTv.listItems")
        
        if cItem['category'] == 'ch_item':
            url = self.CHANNEL_URL + "/%channel%/categories".replace('%channel%', cItem['id'] )
            next_cat = 'cat_ch_item'
            next_all = 'ch_all'
            parent_id = cItem['id']
        elif cItem['category'] == 'categories':
            url = self.CATEGORIES_URL
            next_cat = 'cat_item'
            next_all = 'cat_all'
            parent_id = ''
        else:
            return 
        
        sts, data = self.getPage(url)
        
        if not sts: 
            return
        
        data = json_loads(data)
        
        if cItem['category'] == 'ch_item':
            self.addDir({'title' : _('All videos'), 'icon': cItem['icon'], 'desc': cItem['desc'] , 'id': cItem['id'], 'category': next_all})
            self.addDir({'title' : _('All programs'), 'icon': cItem['icon'], 'desc': cItem['desc'] , 'id': cItem['id'], 'category': 'ch_show' })
        
        for item in data.get('result') or []:
            r = self.parseTopicData(item, artwork = True)
            printDBG(str(r))        
            if r[2] != {}:
                params={'title' : r[1]['title'], 'desc': r[1]['plot'], 'icon': r[2]['thumb'], 'id': r[0]['id'], 'category': next_cat, 'parent_id': parent_id}
            else:
                params={'title' : r[1]['title'], 'desc': r[1]['plot'], 'id': r[0]['id'], 'category': next_cat , 'parent_id': parent_id}
            self.addDir(params)

    def listSubitems(self, cItem):
        printDBG("FranceTv.listSubitems")
        
        results = []
        url = self.CATEGORIES_URL +  "/%cat%".replace('%cat%', cItem['id'] )

        sts, data = self.getPage(url)
        
        if not sts: 
            return
        
        data = json_loads(data)

        self.addDir({'title' : _('All shows'), 'desc': cItem['desc'] , 'id': cItem['id'], 'category': 'cat_subitem'})
        self.addDir({'title' : _('All videos'), 'desc': cItem['desc'] , 'id': cItem['id'], 'category': 'cat_all'})
        
        for item in data.get('sub') or []:
            r = self.parseTopicData(item, True)
            printDBG(str(r))        
            if r[2] != {}:
                params={'title' : r[1]['title'], 'desc': r[1]['plot'], 'icon': r[2]['thumb'], 'id': r[0]['id'], 'category': 'cat_subitem'}
            else:
                params={'title' : r[1]['title'], 'desc': r[1]['plot'], 'id': r[0]['id'], 'category': 'cat_subitem'}
            self.addDir(params)
    
    def listShows(self, cItem):
        
        letter = ''
        
        if cItem['category'] == 'ch_show_letter':
            letter = cItem['name']
            url = self.CHANNEL_URL + '/{0}/programs'.format(cItem['id'])
        elif cItem['category'] == 'cat_subitem':
            url = self.CATEGORIES_URL + '/{0}/programs'.format(cItem['id'])
            self.addDir({'title' : _('All videos'), 'desc': cItem['desc'] , 'id': cItem['id'], 'category': 'cat_all'})

        elif cItem['category'] == 'cat_ch_item':
            url = self.CATEGORIES_URL + "/{0}/programs/{1}".format(cItem['id'], cItem['parent_id'])
        else:
            return 

        url = url + '?sort=title&filter=with-no-vod,only-visible'
        
        sts, data = self.getPage(url)
        
        if not sts:
            return 

        data = json_loads(data)
        
        for item in data.get('result') or []:
            r = self.parseTopicData(item, True)
            
            title = r[1]['title']
            if (len(letter)>0 and ((letter == title[:1]) or (letter == '0-9' and title[:1].isdigit()))) or (letter == ''):
            
                printDBG(str(r))        

                if r[2] != {}:
                    params={'title' : title, 'desc': r[1]['plot'], 'icon': r[2]['thumb'], 'id': r[0]['id'], 'category': 'show'}
                else:
                    params={'title' : title, 'desc': r[1]['plot'], 'id': r[0]['id'], 'category': 'show'}
                self.addDir(params)
           
    def listVideos(self, cItem):
        printDBG("FranceTv.listVideos")
        
        results = []
        
        #if cItem['category'] == 'cat_subitem':
        #    url = self.CATEGORIES_URL + "/%cat%/contents?sort=begin_date:desc&size=15&page={0}&filter=with-no-vod,only-visible".format(page).replace('%cat%', cItem['id'])
        if cItem['category'] == 'show':
            page = 0
            url = self.PROGRAM_URL + "/%show%/contents?sort=begin_date:desc&size=15&page=0&filter=with-no-vod,only-visible".replace('%show%', cItem['id'])
            next_cat = 'show_next'
        elif cItem['category'] == 'show_next':
            page = cItem['page']
            url = self.PROGRAM_URL + "/%show%/contents?sort=begin_date:desc&size=15&page={0}&filter=with-no-vod,only-visible".format(page).replace('%show%', cItem['id'])
            next_cat = 'show_next'
        elif cItem['category'] == 'ch_all':
            page = 0
            url = self.CHANNEL_URL + "/%ch%/contents?sort=begin_date:desc&size=15&page=0&filter=with-no-vod,only-visible".replace('%ch%', cItem['id'])
            next_cat = 'ch_all_next'
        elif cItem['category'] == 'ch_all_next':
            page = cItem['page']
            url = self.CHANNEL_URL + "/%ch%/contents?sort=begin_date:desc&size=15&page={0}&filter=with-no-vod,only-visible".format(page).replace('%ch%', cItem['id'])
            next_cat = 'ch_all_next'
        elif cItem['category'] == 'cat_all':
            page = 0
            url = self.CATEGORIES_URL + "/%cat%/contents?sort=begin_date:desc&size=15&page=0&filter=with-no-vod,only-visible".replace('%cat%', cItem['id'])
            next_cat = 'cat_all_next'
        elif cItem['category'] == 'cat_all_next':
            page = cItem['page']
            url = self.CATEGORIES_URL + "/%cat%/contents?sort=begin_date:desc&size=15&page={0}&filter=with-no-vod,only-visible".format(page).replace('%cat%', cItem['id'])
            next_cat = 'cat_all_next'
        else:
            return 

        sts, data = self.getPage(url)
        
        if not sts:
            return results

        data = json_loads(data)
        
        for item in data.get('result') or []:
            r = self.parseVideoData(item)
            printDBG(str(r))        
            url = self.VIDEO_API_URL + "?idDiffusion=%video_id%"
            url = url.replace("%video_id%", r[0]['video_id'])
            
            duration = timedelta(seconds = r[1]['duration'])
            desc =  _('Duration: {0}').format(str(duration)) +  ' | ' + _('Added: {0}').format(r[1]['date']) 

            if r[1]['plot'] != None:
                desc = desc + '\n' + r[1]['plot'] 
            
            if r[2] != {}:
                params={'title' : r[1]['title'], 'desc': desc , 'icon': r[2]['thumb'], 'url': url, 'category': 'video'}
            else:
                params={'title' : r[1]['title'], 'desc': desc,  'url': url, 'category': 'video'}
            self.addVideo(params)

        
        if data.get('cursor'):
            if data['cursor'].get('next'):
                self.addMore({'category':  next_cat , 'title': _('Next page'), 'page': (page + 1) , 'id' : cItem['id']})


    def listAZ(self,cItem):
        printDBG("FranceTv.listAZ")

        if cItem['category'] == 'ch_show':
            next_cat = 'ch_show_letter'
            
        # 0-9
        self.addDir(MergeDicts(cItem, {'category': next_cat, 'title': "0-9" , 'name': "0-9" } ))              
        
        #a-z
        for i in range(26):
            self.addDir(MergeDicts(cItem, {'category': next_cat, 'title': chr(ord('A')+i) , 'name': chr(ord('A')+i)} ))              
            
        
        
    def listMainMenu(self, cItem):
        printDBG("FranceTv.listMainMenu")
        MAIN_CAT_TAB = [{'category':'channels', 'title': _('Channels')},
                        {'category':'categories', 'title': _('Categories')},
                        {'category':'live', 'title': _('Live')}]  
        self.listsTab(MAIN_CAT_TAB, cItem)  
        
    def getLinksForVideo(self, cItem):
        printDBG("FranceTv.getLinksForVideo [%s]" % cItem)
        
        linksTab = []
        
        if cItem['category'] in ('video','live'):
            sts, data = self.getPage(cItem['url'])
            
            if not sts: 
                return
            
            data = json_loads(data)
            
            v_links=[]
            v_geoblock_links=[]    
            
            for v in data['videos']:
                # check video format 
                video_format = v.get('format')
                if video_format in ("hls_v1_os","hls_v5_os"):
                    # check georestricted streams
                    countries = v.get('geoblocage')
                    if countries:
                        geoblock = True
                    else:
                        geoblock = False
                    
                    printDBG("url: %s, video format: %s" % (v.get('url',''),video_format))
                    # check times
                    now = time.time()
                    for interval in v.get('plages_ouverture') or []:
                        if ((interval.get('debut') or 0) <= now ) and (now <= (interval.get('fin') or sys.maxsize)):
                            video_url = self.VIDEO_TOKEN_URL + '?' + urllib.urlencode({'json':'0', 'url': v.get('url')})
                            sts, data = self.getPage(video_url)
                            if not sts: 
                                continue

                            real_url = data
                            if geoblock:
                                v_geoblock_links.append({'url' : v.get('url'), 'real_url': real_url, 'geoblock' : geoblock})
                            else:
                                v_links.append({'url' : v.get('url'), 'real_url': real_url, 'geoblock' : geoblock})
                
                if len(v_links)>0:
                    for v in v_links: 
                        #printDBG(str(v))
                        linksTab.extend(getDirectM3U8Playlist(v['real_url'], checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))  
                elif len(v_geoblock_links)>0:
                    if config.plugins.iptvplayer.francetv_skip_geoblocked == True :
                        msg = _('There are some geoblocked links. If you want to use them, change option in the host configuration, available under blue button.' )
                        self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_INFO, timeout = 5)
                    else:
                        for v in v_geoblock_links:            
                            #printDBG(str(v))
                            linksTab.extend(getDirectM3U8Playlist(v['real_url'] , checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))  
        
        return linksTab
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('FR')
        
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||| name[%s], category[%s] " % (name, category) )
        self.cacheLinks = {}
        self.currList = []
        
        #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'live':
            self.listLive(self.currItem)
        elif category == 'channels':
            self.listChannels(self.currItem)
        elif category in ('categories', 'ch_item'):
            self.listItems(self.currItem)
        elif category == 'cat_item':
            self.listSubitems(self.currItem)
        elif category in ('ch_show', 'cat_show'):
            self.listAZ(self.currItem)
        elif category in  ('ch_show_letter', 'cat_ch_item', 'cat_subitem', 'cat_show'):
            self.listShows(self.currItem)
        elif category in ('ch_all', 'ch_all_next', 'show', 'show_next', 'cat_all', 'cat_all_next'):
            self.listVideos(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FranceTv(), True, [])
    
