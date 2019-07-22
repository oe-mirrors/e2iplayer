# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, NextDay, PrevDay
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
import time
import urllib
import re
from datetime import date, datetime, timedelta
###################################################

def gettytul():
    return 'https://www.sportitalia.com/'

class Sportitalia(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'sportitalia.com', 'cookie':'sportitalia.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
        self.MAIN_URL = "https://www.sportitalia.com" 
        self.PAGES_URL = self.MAIN_URL + "/it-int/page/" 
        self.HOME_URL = self.PAGES_URL + "home-sportitalia"

        self.DEFAULT_ICON_URL = 'https://www.sportitalia.com/image/original/5cd2d4995a029.png?v=20190516104423'
        self.IMG_URL = 'https://www.sportitalia.com/image/{0}/{1}?v={2}'
        # {0} = item['logo_id']['manipulations'] ex. 'original', 'thumbnail'
        # {1} = item['logo_id']['path'] ex. 5cd43a9ee9cc9.png 
        # {2} = item['logo_id']['version'] ex. 20190509143512

        self.API_URL = "https://www.sportitalia.com/api"
        self.API_MODULE_URL =  self.API_URL + "/module/{0}/content?page={1}"
        # {0} module id
        # {1} page number
        self.API_CONTENTBOX_URL = self.API_URL + "/content-box/?baseconfig={0}&module={1}&live={2}"
        # {0} = base config id ex. 38 
        # {1} = module *
        # {2} = true: select live streams, false: select recorded ones
        self.API_CONTENT_URL = self.API_URL + "/content"
        # self.API_CONTENT_URL = "https://www.sportitalia.com/api/content/{0}"
        # {0} = video id *
        # {1} = module id
        self.API_RELATED_CONTENT_URL = self.API_URL + "/related-content/{0}/?module={1}"
        # {0} = video id *
        # {1} = module id *
        self.API_PLAYERPAGE_URL = self.API_URL + "/playerpage/{0}?portal={1}"
        # {0} = video id *
        # {1} = portal id ex. 44 *
        self.API_PLAYERSETTING_URL = self.API_URL + "/v2/content/{0}/player-setting"
        # {0} = video id *
        self.API_VIDEO_URL = self.API_URL + "/video/{0}/access" 
        # ?device_category_id=1"
        # {0} = video id *
        
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT}
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 
                              'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        
        self.OFFSET = datetime.now() - datetime.utcnow()
        seconds = self.OFFSET.seconds + self.OFFSET.days * 24 * 3600
        if ((seconds + 1) % 10) == 0: seconds += 1  
        elif ((seconds - 1) % 10) == 0: seconds -= 1 
        self.OFFSET = timedelta(seconds=seconds)
        
        self.MONTH_NAME_TAB = [_('January'), _('February'), _('Mars'), _('April'), _('May'), _('June'), _('July'), _('August'), _('September'), _('October'), _('November'), _('December')]
        self.DAYS_NAME_TAB = [_('Monday'), _('Tuesday'), _('Wednesday'), _('Thursday'), _('Friday'), _('Saturday'), _('Sunday')]
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def getThumb(self, img):
        url = self.IMG_URL.format('original', img['path'], img['version'])
        return url
    
    def listMainMenu(self, cItem):
        printDBG("Sportitalia.listMainMenu")

        sts, data = self.getPage(self.HOME_URL)
        if not sts: return
        
        # embedded player
        j=re.findall("window\.pageTree = (\{.*?);\n", data)

        d1 = json_loads(j[0])
        d1 = d1['children'][1]
        
        for page in d1['children']:
            if page['name'] == 'Player Page':
                params = {'title': _('LIVE STREAMING'), 'module_id': page['page']['modules'][0]['id'], 'category' : 'si_player', 'icon': self.DEFAULT_ICON_URL}
                printDBG(str(params))
                self.addDir (params)

        
        # menu item
        
        j=re.findall("window\.pageTree = (\{.*?);\n", data)

        data = json_loads(j[0])
        data = data['children'][0]
        
        for item in data['children']:
            title = item['name']
            #printDBG(title)
            if not(title in ["Sportitalia HD","SI SOLOCALCIO","SI MOTORI","SI LIVE 24", "SPORTS CENTER"]):
                
                url = self.PAGES_URL + item['page']['slug']
                if item['page']['logo_id'] != None:
                    icon = self.getThumb( item['page']['logo_id'])           
                else:
                    icon = self.DEFAULT_ICON_URL

                children=[]
                if 'children' in item:
                    if len(item['children'])>0:
                        for ii in item['children']:

                            url_child = self.PAGES_URL + ii['page']['slug']

                            if ii['page']['logo_id'] != None:
                                icon_child = self.getThumb( ii['page']['logo_id'])           
                            else:
                                icon_child = self.DEFAULT_ICON_URL

                            children.append({'name': ii['page']['languages'][0]['nav_title'], 'slug': ii['page']['slug'], 'logo_data' : ii['page']['logo_id'], 'url' : url_child , 'icon': icon_child })

                            params = {'title': item['page']['languages'][0]['nav_title'], 'slug': item ['page']['slug'], 'category': 'si_menu', 'children': children}
                    else:
                            params = {'title': item['page']['languages'][0]['nav_title'], 'slug': item ['page']['slug'], 'url': url, 'category': 'si_page', 'icon': icon}

                printDBG(str(params))
                self.addDir (params)
    
    def listMenu(self,cItem):
        printDBG("Sportitalia.listMenu")
 
        for item in cItem['children']:
            params = {'title': item['name'], 'slug': item['slug'], 'url': item ['url'], 'category': 'si_page', 'icon' : item['icon']}
            printDBG(str(params))
            self.addDir (params)
    

    def listPage(self,cItem):
        printDBG("Sportitalia.listPage %s"  % cItem['slug'])
        
        if not ('url' in cItem):
            return
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        # search for collections
        j=re.findall("window\.pages = \[(\{.*?)\];\n", data)

        data = json_loads("[" + j[0] + "]")
        
        for page in data:  
            if page['slug'] == cItem['slug']:        
                #printDBG(str(data))
                for m in page['modules']:
                    #printDBG(str(m))
                    if m['type']['category'] == 'Content':
                        params = {'title': m['languages'][0]['title'], 'desc': m['languages'][0]['description'] , 'module_id': m['id'], 'category' : 'si_module', 'icon': cItem['icon']}
                        printDBG(str(params))
                        self.addDir (params)

                        
    def listModule(self,cItem):
        printDBG("Sportitalia.listModule %s"  % cItem['module_id'])
        if 'page' in cItem:
            page = int(cItem['page'])
        else:
            page = 1
        
        if cItem['category'] == 'si_module':
            url = self.API_MODULE_URL.format(cItem['module_id'], page)
        elif cItem['category'] == 'si_player':
            url = self.API_CONTENTBOX_URL.format(38, cItem['module_id'], 'true')

        else:        
            return
        
        sts, data = self.getPage(url)
        
        if not sts:
            return
        
        data = json_loads(data)
        
        for item in data['data']:
            title = item['fields']['Title'][0]['title']
            
            if cItem['category'] == 'si_module':
                length = timedelta(seconds = item['video_length'])
                desc =  _('Duration: {0}').format(str(length)) +  ' | ' + _('Added: {0}').format(item['content']['start_datetime']) 
                if item['fields']['Title'][0]['description'] != None:
                    desc = desc +  '\n' + item['fields']['Title'][0]['description']
            else:
                desc = ''
                
            video_id = item['id']
            icon = "https://www.sportitalia.com/image/original/{0}".format(item['editorial']['images'][0]['image']['path'])
            
            params = {'title': title, 'desc': desc, 'id': video_id, 'icon': icon, 'category' : 'si_video'}
            self.addVideo (params)
        
        if cItem['category'] == 'si_module':
            if int(data['meta']['last_page']) > page:
                self.addMore ({'title': _('Next page'), 'module_id': cItem['module_id'], 'page' : str(page +1), 'category' : 'si_module'})
            
            
    def getLinksForVideo(self, cItem):
        printDBG("Sportitalia.getLinksForVideo [%s]" % cItem)
        
        linksTab = []
        
        if cItem['category'] == 'si_video':
            video_id = cItem['id']
            url = self.API_VIDEO_URL.format(video_id)
    
            post_data = {'device_category_id' : '1'}
            sts, data = self.getPage(url, self.defaultParams, post_data)
            
            if not sts:
                return linksTab
            
            printDBG(data)
            data = json_loads(data)
            if data['status'] == 'success':
                video_url = strwithmeta(data['data']['stream'],{'Referer' : 'https://www.sportitalia.com/', 'User-Agent': self.USER_AGENT })
                printDBG(video_url)
                linksTab.extend(getDirectM3U8Playlist(video_url , checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))  
              
        return linksTab
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||| name[%s], category[%s] " % (name, category) )
        self.cacheLinks = {}
        self.currList = []
        
        #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'si_menu':
            self.listMenu(self.currItem)
        elif category == 'si_page':
            self.listPage(self.currItem)
        elif category == 'si_module' or category == 'si_player':
            self.listModule(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Sportitalia(), True, [])
    