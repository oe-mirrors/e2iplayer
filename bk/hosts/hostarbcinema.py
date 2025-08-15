# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import base64
###################################################

def GetConfigList():
    optionList = []
    return optionList
###################################################

def gettytul():
    return 'https://w.arbcinema.com/'

class arbcinema(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'arbcinema', 'cookie':'arbcinema.cookie'})
        self.DEFAULT_ICON_URL = 'https://i.ibb.co/LzkK4G4/4.png' 
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://w.arbcinema.com/'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        self.cacheSeriesByLetters = {}
        self.cacheSeriesLetters = []
        self.cacheLinks  = {}
        self.defaultParams = {'header':self.HEADER, 'raw_post_data':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.MAIN_CAT_TAB = [{'category':'list_movies','title':'••أفـــلام أجنبية••','url':self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a%d8%a9-%d9%85%d8%aa%d8%b1%d8%ac%d9%85%d8%a9')},
                             {'category':'list_years','title': '••السنوات••','url':''},
                             {'category':'list_movies','title': '••افلام-اكشن••','url':self.getFullUrl('/tag/%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%A7%D9%83%D8%B4%D9%86')},
                             {'category':'list_movies','title': '••افلام رعب••','url':self.getFullUrl('/tag/%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%B1%D8%B9%D8%A8')},
                             {'category':'list_movies','title': '••افلام درامـــا••','url':self.getFullUrl('/tag/%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%AF%D8%B1%D8%A7%D9%85%D8%A7-%D9%88%D8%BA%D9%85%D9%88%D8%B6')},
                             {'category':'list_movies','title': '1080p-bluray','url':self.getFullUrl('/quality/bluray')},
                             {'category':'list_movies','title': '••أفــلام عربية••','url':self.getFullUrl('/category/%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%B9%D8%B1%D8%A8%D9%8A')},
                             {'category':'search','title': _('Search'),'search_item':True, },
                             {'category':'search_history','title': _('Search history'),} 
                            ]
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        addParams['cloudflare_params'] = {'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        sts, data =self.cm.getPage(baseUrl)# self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        printDBG("++++++++++++++++++++++++++++++++++++++++")
        printDBG("url: %s" % baseUrl)
        printDBG("sts: %s" % sts)
       
        printDBG("++++++++++++++++++++++++++++++++++++++++")
        return sts, data
    
    def listMainMenu(self, cItem):
        
        #self.setMainUrl(self.cm.meta['url'])
        self.listsTab(self.MAIN_CAT_TAB, cItem)
        
    def listItems1(self, cItem, nextCategory):
        printDBG("arbcinema.listItems1 [%s]" % cItem)
        page = cItem.get('page', 1)
        url = cItem['url']
        if page > 1:
            url += '/page/%s/' % page
           
            
        sts, data = self.getPage(url)
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', '</div>')[1]
        
       
        if ('/page/%s' % (page + 1)) in nextPage: nextPage = True
        else: nextPage = False
        
        
        
       
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="Block"', 'class="Block"')
        for item in data:
           
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data-lazy-src="(.*?)"''')[0])
            
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])

            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''<div class="movief">(.*?)</div>''')[0])
                      
            params = dict(cItem)
            params.update({'good_for_fav':True, 'category':'video','type':'video', 'title':title, 'url':url, 'icon':icon})
            self.addVideo(params)
        
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_("Next page"), 'page':page+1})
            self.addDir(params)
            
    def listSeriesLetters(self, cItem, nextCategory):
        printDBG("arbcinema.listSeriesLetters [%s]" % cItem)
        if 0 == len(self.cacheSeriesLetters):
            self.cacheSeriesByLetters = {}
            self.cacheSeriesLetters = []
            
            sts, data = self.getPage(cItem['url'])
            if not sts: return
            self.setMainUrl(self.cm.meta['url'])
            
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'list-series'), ('</ul', '>'))[1]
            data = re.compile('''<li[^>]+?class=['"]alpha\-title['"][^>]*?>''').split(data)
            if len(data): del data[0]
            for section in data:
                letter = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(section, ('<h3', '>'), ('</h3', '>'))[1])
                section = self.cm.ph.getAllItemsBeetwenMarkers(section, '<a', '</a>')
                tabList = []
                for item in section:
                    title = self.cleanHtmlStr(item)
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                    tabList.append({'title':title, 'url':url})
                if len(tabList):
                    title = tabList[0]['title'][0]
                    if title != letter: title += letter
                    self.cacheSeriesLetters.append({'title':title, 'f_letter':letter})
                    self.cacheSeriesByLetters[letter] = tabList
        
        params = dict(cItem)
        params.update({'good_for_fav':False, 'category':nextCategory})
        self.listsTab(self.cacheSeriesLetters, params)
        
    def listSeriesByLetters(self, cItem, nextCategory):
        printDBG("arbcinema.listSeriesByLetters [%s]" % cItem)
        letter = cItem.get('f_letter', '')
        tabList = self.cacheSeriesByLetters.get(letter, [])
        
        params = dict(cItem)
        params.update({'good_for_fav':True, 'category':nextCategory})
        self.listsTab(tabList, params)
        
    def exploreItem(self, cItem, nextCategory):
        printDBG("arbcinema.exploreItem")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        descTab = ['']
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="extradsbottom', '</div>')
        for item in tmp:
            item = self.cleanHtmlStr(item.replace('</p>', ' | '))
            if item != '': descTab[0] += ' ' + item
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]+?class=['"]dsclear'''), re.compile('</div>'))[1])
        descTab.append(tmp)
        desc = '[/br]'.join(descTab)
        
        trailerUrl = self.cm.ph.getDataBeetwenMarkers(data,  '<div class="trailerbox"', '</div>')[1]
        trailerUrl = self.cm.ph.getSearchGroups(trailerUrl, '''<ifram[^>]+?src=['"]([^'^"]+?)['"]''')[0]
        if self.cm.isValidUrl(trailerUrl):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':'%s [TRAILER]' % cItem['title'], 'url':trailerUrl, 'desc':desc})
            self.addVideo(params)
        
        if 'var movie' in data:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'desc':desc})
            self.addVideo(params)
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="seasons">', '<script>')[1].split('</ul>')
            for sItem in data:
                sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(sItem, re.compile('''<span[^>]+?class=['"]title['"]'''), re.compile('</span>'))[1])
                episodesTab = []
                sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem, '<li', '</li>')
                for item in sItem:
                    icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])
                    url  = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<div[^>]+?episodiotitle'), re.compile('</a>'))[1] )
                    desc  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<span[^>]+?date'), re.compile('</span>'))[1] )
                    num   = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<div[^>]+?numerando'), re.compile('</div>'))[1] ).replace(' ', '')
                    title = '%s - %s %s' % (cItem['title'], num, title)
                    episodesTab.append({'title':title, 'url':url, 'desc':desc, 'icon':icon})
                
                if len(episodesTab):
                    params = dict(cItem)
                    params.update({'good_for_fav':False, 'category':nextCategory, 'title':sTitle, 'episodes':episodesTab})
                    self.addDir(params)
                    
    def listEpisodes(self, cItem, nextCategory):
        printDBG("arbcinema.exploreItem")
        episodesTab = cItem.get('episodes', [])
        cItem = dict(cItem)
        cItem.pop('episodes', None)
        for item in episodesTab:
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav':False})
            self.addVideo(params)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("arbcinema.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        self.listItems1(cItem, 'explore_item')
        
    def getLinksForVideo(self, cItem):
       
         #url=url+"?v        
        sts, data = self.getPage(cItem['url'])
        if not sts: return []

        regx="rel='shortlink' href='(.+?)'"
        id = id = self.cm.ph.getSearchGroups(data,regx)[0].split("=")[1]
        print "id",id
        retTab=[]
        for i in range(1,10):
          url='https://m.arbcinema.com/wp-content/themes/yourcolor/servers/server.php?q='+id+'&i='+str(i)
          print 'url',url
         
          sts, data = self.getPage(url)
          print "data",data
          
          if not sts: break
          regx='''src="(.*?)"'''
          try:videoUrl=re.findall(regx,data, re.M|re.I)[0]
          except:break
          

          cacheKey = cItem['url']
          cacheTab = self.cacheLinks.get(cacheKey, [])
          #f len(cacheTab):
                #return cacheTab
          
          print "hrefxx",self.up.checkHostSupport(videoUrl)
          videoUrl = strwithmeta(videoUrl)
          print 'videoUrl-meta',videoUrl
          if 'ok.ru' in videoUrl:videoUrl='http:'+videoUrl 
          if 1 == self.up.checkHostSupport(videoUrl):
              print "hrefxx2",videoUrl
              title = self.up.getHostName(videoUrl)
                   
              retTab.append({'name':title, 'url':videoUrl, 'need_resolve':1})
        
          if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        
        return retTab
        
    def getVideoLinks(self, videoUrl):
        print "mahmoudxx1"
        printDBG("arbcinema.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break
        
        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = videoUrl.meta.get('Referer', '')
        
        sts, data = self.getPage(self.getFullUrl('/image/logo.png'), params)
        if not sts: return []
        
        if 1 != self.up.checkHostSupport(videoUrl):
            sts, data = self.getPage(videoUrl, params)
            if not sts: return []
            scripts = []
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
            for item in tmp:
                if 'eval(' not in item: continue
                scripts.append(item.strip())
            try:
                jscode = base64.b64decode('''dmFyIGRvY3VtZW50PXt9LHdpbmRvdz10aGlzO3dpbmRvdy5sb2NhdGlvbj17aG9zdG5hbWU6IiVzIn0sZG9jdW1lbnQud3JpdGU9ZnVuY3Rpb24obil7cHJpbnQobil9Ow==''') % (self.up.getDomain(videoUrl, True))
                ret = js_execute( jscode + '\n'.join(scripts))
                if ret['sts'] and 0 == ret['code']:
                    data = ret['data'].strip()
                    videoUrl = self.cm.ph.getSearchGroups(data, '''url['"]?=['"]?([^'^"^>]+?)['">]''')[0].strip()
            except Exception:
                printExc()
        
        if 0 and 1 != self.up.checkHostSupport(videoUrl):
            params = dict(self.defaultParams)
            params['header'] = dict(params['header'])
            params['header']['Referer'] = videoUrl.meta.get('Referer', '')
            params['max_data_size'] = 0
            self.getPage(videoUrl, params)
            videoUrl = self.cm.meta.get('url', '')

        urlTab = self.up.getVideoLinkExt(videoUrl)
        
        return urlTab
        
    def getArticleContent(self, cItem):
        printDBG("arbcinema.getArticleContent [%s]" % cItem)
        retTab = []
        
        otherInfo = {}
        
        url = cItem['url']
        
        sts, data = self.getPage(url)
        if not sts: return []
        
        if '/episodes/' in url:
            icon  = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''[\s:]url\(\s*['"]([^'^"]+?\.jpe?g[^'^"]*?)['"]''')[0])
            data  = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]+?id=['"]info['"]'''), re.compile('''<div[^>]+?class=['"]box_links['"]'''))[1]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<h1'''), re.compile('</h1>'))[1])
            otherInfo['alternate_title'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<h3'''), re.compile('</h3>'))[1])
            desc  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p', '</p>')[1])
        else:
            tmp  = ' '.join(self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="extradsbottom', '</div>'))
            data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]+?class=['"]content['"][^>]*?>'''), re.compile('''<div[^>]+?class=['"]extradsbottom'''), False)[1]
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p', '</p>')[1])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<h1'''), re.compile('</h1>'))[1])
            
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<p', '</p>')
            for item in tmp:
                item = item.split('</span>', 1)
                key = self.cleanHtmlStr(item[0]).lower()
                value = self.cleanHtmlStr(item[1].replace('</a>', ', '))
                if 'e original' in key: otherInfo['alternate_title'] = value
                elif 'statut' in key: otherInfo['status'] = value
                elif 'saisons' in key: otherInfo['seasons'] = value
                elif 'episodes' in key: otherInfo['episodes'] = value
                elif 'genre' in key: otherInfo['genres'] = value.replace(' , ', ', ')
                elif 'acteurs' in key: otherInfo['actors'] = value.replace(' , ', ', ')
                elif ' date' in key: otherInfo['released'] = value
                elif 'tmdb' in key: otherInfo['tmdb_rating'] = value
                elif 'année de production' in key: otherInfo['year'] = value
            
        if title == '': title = cItem['title']
        if desc == '':  desc = cItem.get('desc', '')
        if icon == '':  icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]
    
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
        elif category == 'list_movies':
            self.listItems1(self.currItem, 'explore_item')
        elif category == 'list_series':
            self.listSeriesLetters(self.currItem, 'list_series_by_letter')
        elif category == 'list_series_by_letter':
            self.listSeriesByLetters(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem, 'explore_item')
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
        CHostBase.__init__(self, arbcinema(), True, [])
        
    def withArticleContent(self, cItem):
        url = cItem.get('url', '')
        if '/episodes/' in url or '/films/' in url or '/series/' in url:
            return True
        return False
def start():
        from xbmctools import get_params,getsearchtext
        import ast
        params=get_params()
       
        printDBG("params:"+str(params))
        url=None
        name=None
        mode=None
        page=1
        name=params.get("name",None)
        url=params.get("url",None)
        try:mode=params.get("mode",None)
        except:mode=None
        image=params.get("image",None)      
        page=int(params.get("page",1))
        cItem=params.get("extra",{})        
        try:
                cItem=ast.literal_eval(str(cItem))
        except:
                cItem={}

        host=arbcinema()####change host
        type=cItem.get('type',None)
        printDBG("mode:"+str(mode))
        printDBG("type:"+str(type))
        printDBG("cItem:"+str(cItem))
        need_resolve=cItem.get('need_resolve',None)
        searchPattern=''
        search_item=cItem.get('search_item',False)
        if search_item:
           searchPattern=getsearchtext()
        if mode==None:
            cItem['name']=None
        host.currItem=cItem
        if type=='video':
            urlTab=host.getLinksForVideo( cItem)
            
            
            host.TSaddDir(urlTab)
            return

        elif need_resolve and need_resolve==0:
             urlTab=host.getVideoLinks(cItem['url'])   
             host.TSaddDir(urlTab)
             return
            
        elif need_resolve and need_resolve==1:
             urlTab=host.getVideoLinks(cItem['url'])
             host.TSaddDir(urlTab)
        else:
        
             host.handleService(0,0,searchPattern =searchPattern)
        		
    



    
    
    
