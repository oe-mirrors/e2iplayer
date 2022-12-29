# -*- coding: utf-8 -*-
###################################################
# 2022-12-10 by Blindspot - M4 SPORT
###################################################
HOST_VERSION = "1.8"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIPTVPlayerVersion, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import os
import datetime
import time
import zlib
import urllib
import base64
from urllib.parse import *
from hashlib import sha1
from Components.config import config, ConfigText, ConfigYesNo, getConfigListEntry
from Tools.Directories import resolveFilename, fileExists, SCOPE_PLUGINS
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.m4sport_id = ConfigYesNo(default = False)
config.plugins.iptvplayer.boxtipus = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.boxrendszer = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("m4sport_id:", config.plugins.iptvplayer.m4sport_id))
    return optionList
###################################################

def gettytul():
    return 'M4 Sport'

class m4sport(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'m4sport.hu', 'cookie':'m4sport.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0'
        self.HEADER = {'User-Agent':self.USER_AGENT, 'DNT':'1', 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate, br'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.MAIN_URL = 'https://www.m4sport.hu/videok/'
        self.DEFAULT_ICON_URL = 'http://www.figyelmeztetes.hu/m4sport_logo.png'
        self.ICON_URL_ELO = 'http://www.figyelmeztetes.hu/m4sport_logo_elo.png'
        self.ICON_URL_FOCI = 'http://www.figyelmeztetes.hu/m4sport_logo_foci.png'
        self.vivn = GetIPTVPlayerVersion()
        self.porv = self.gits()
        self.pbtp = '-'
        self.btps = config.plugins.iptvplayer.boxtipus.value
        self.brdr = config.plugins.iptvplayer.boxrendszer.value
        self.aid = config.plugins.iptvplayer.m4sport_id.value
        self.aid_ki = ''
        self.eblf = 'https://www.m4sport.hu/bajnokokligaja'
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getFullIconUrl(self, url):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullIconUrl(self, url)
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urllib.parse.urljoin(baseUrl, url)
            
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data
        
    def listMainMenu(self, cItem):
        try:
            if self.btps != '' and self.brdr != '': self.pbtp = self.btps.strip() + ' - ' + self.brdr.strip()
            n_bx = self.malvadst('1', '11', 'm4_boxutca')
            if n_bx != '' and self.aid:
                self.aid_ki = 'ID: ' + n_bx + '\n'
            else:
                self.aid_ki = ''
            msg_boxutca = self.aid_ki + 'm4sport - v' + HOST_VERSION + '\n\nBoxutca adásainak megjelenítése'
            n_f = self.malvadst('1', '11', 'm4_foci')
            if n_f != '' and self.aid:
                self.aid_ki = 'ID: ' + n_f + '\n'
            else:
                self.aid_ki = ''
            msg_foci = self.aid_ki + 'Magyar Foci adásainak megjelenítése'
            n_fbl = self.malvadst('1', '11', 'm4_blfoci')
            if n_fbl != '' and self.aid:
                self.aid_ki = 'ID: ' + n_fbl + '\n'
            else:
                self.aid_ki = ''
            msg_blfoci = self.aid_ki + 'UEFA Bajnokok Ligája adásainak megjelenítése\n\n(Előfordulhat, hogy egyes műsorokat nem lehet lejátszani a tartalom védelme miatt! - "Nincs elérhető link." üzenet jelenik meg)'
            n_sh = self.malvadst('1', '11', 'm4_sporthirek')
            if n_sh != '' and self.aid:
                self.aid_ki = 'ID: ' + n_sh + '\n'
            else:
                self.aid_ki = ''
            msg_sporthirek = self.aid_ki + 'Sporthírek adásainak megjelenítése'
            n_sk = self.malvadst('1', '11', 'm4_kozvetitesek')
            if n_sk != '' and self.aid:
                self.aid_ki = 'ID: ' + n_sk + '\n'
            else:
                self.aid_ki = ''
            msg_kozvetitesek = self.aid_ki + 'Sportközvetítések megjelenítése'
            n_krs = self.malvadst('1', '11', 'm4_kereses')
            if n_krs != '' and self.aid:
                self.aid_ki = 'ID: ' + n_krs + '\n'
            else:
                self.aid_ki = ''
            msg_kereses = self.aid_ki + 'Keresés eredményeinek megjelenítése'
            n_krse = self.malvadst('1', '11', 'm4_kereses_elozmeny')
            if n_krse != '' and self.aid:
                self.aid_ki = 'ID: ' + n_krse + '\n'
            else:
                self.aid_ki = ''
            msg_keres_elozmeny = self.aid_ki + 'Keresés az előzmények között'
            n_elo = self.malvadst('1', '11', 'm4_elo')
            if n_elo != '' and self.aid:
                self.aid_ki = 'ID: ' + n_elo + '\n'
            else:
                self.aid_ki = ''
            msg_elo = self.aid_ki + 'M4 élő adásának megjelenítése.'
            msg_eloplus = self.aid_ki + 'M4 Sport + élő adásának megjelenítése.' + "\n" + 'Figyelem! Ez az élő adás csak hétvégén érhető el, a fennmaradó időben a Duna World adása látható.'
            msg_elo1 = self.aid_ki + 'M4 Sport 1 élő adásának megjelenítése.'
            msg_elo2 = self.aid_ki + 'M4 Sport 2 élő adásának megjelenítése.'
            msg_elo3 = self.aid_ki + 'M4 Sport 3 élő adásának megjelenítése.'
            msg_elo4 = self.aid_ki + 'M4 Sport 4 élő adásának megjelenítése.'
            msg_elo5 = self.aid_ki + 'M4 Sport 5 élő adásának megjelenítése.'
            MAIN_CAT_TAB = [{'category': 'list_main', 'title': 'BOXUTCA', 'tab_id': 'boxutca', 'desc': msg_boxutca, 'icon':self.DEFAULT_ICON_URL},
                            {'category': 'list_main', 'title': 'MAGYAR FOCI', 'tab_id': 'foci', 'desc': msg_foci, 'icon':self.ICON_URL_FOCI},
                            {'category': 'list_main', 'title': 'UEFA BAJNOKOK LIGÁJA FOCI', 'tab_id': 'blfoci', 'desc': msg_blfoci, 'icon':self.ICON_URL_FOCI},
                            {'category': 'list_main', 'title': 'SPORTHÍREK', 'tab_id': 'sporthirek', 'desc': msg_sporthirek, 'icon':self.DEFAULT_ICON_URL},
                            {'category': 'list_main', 'title': 'SPORTKÖZVETÍTÉSEK', 'tab_id': 'kozvetitesek', 'desc': msg_kozvetitesek, 'icon':self.DEFAULT_ICON_URL},
                            {'category': 'search', 'title': 'Keresés', 'search_item': True, 'tab_id': 'kereses', 'desc': msg_kereses, 'icon':self.DEFAULT_ICON_URL },
                            {'category': 'search_history', 'title': 'Keresés az előzmények közt', 'tab_id': 'keres_elozmeny', 'desc': msg_keres_elozmeny, 'icon':self.DEFAULT_ICON_URL}
                           ]
            self.listsTab(MAIN_CAT_TAB, cItem)
            pvt = 'M4 ÉLŐ ADÁSA'
            pvd = msg_elo
            pvu = "https://www.mediaklikk.hu/m4-elo/"
            icon = self.ICON_URL_ELO
            params = MergeDicts(cItem, {'good_for_fav':False, 'title':pvt, 'url':pvu, 'url2':pvu, 'desc':pvd, 'icon':icon, 'md': 'elo', 'id': "mtv4live"})
            self.addVideo(params)
            pvt = 'M4 SPORT+'
            pvd = msg_eloplus
            pvu = "https://www.mediaklikk.hu/m4-elo/"
            icon = self.ICON_URL_ELO
            params = MergeDicts(cItem, {'good_for_fav':False, 'title':pvt, 'url':pvu, 'url2':pvu, 'desc':pvd, 'icon':icon, 'md': 'elo', 'id': "mtv4plus"})
            self.addVideo(params)
            pvt = 'M4 SPORT 1'
            pvd = msg_elo1
            pvu = "https://www.mediaklikk.hu/m4-elo/"
            icon = self.ICON_URL_ELO
            params = MergeDicts(cItem, {'good_for_fav':False, 'title':pvt, 'url':pvu, 'url2':pvu, 'desc':pvd, 'icon':icon, 'md': 'elo', 'id': "m4sport1"})
            self.addVideo(params)
            pvt = 'M4 SPORT 2'
            pvd = msg_elo2
            pvu = "https://www.mediaklikk.hu/m4-elo/"
            icon = self.ICON_URL_ELO
            params = MergeDicts(cItem, {'good_for_fav':False, 'title':pvt, 'url':pvu, 'url2':pvu, 'desc':pvd, 'icon':icon, 'md': 'elo', 'id': "m4sport2"})
            self.addVideo(params)
            pvt = 'M4 SPORT 3'
            pvd = msg_elo3
            pvu = "https://www.mediaklikk.hu/m4-elo/"
            icon = self.ICON_URL_ELO
            params = MergeDicts(cItem, {'good_for_fav':False, 'title':pvt, 'url':pvu, 'url2':pvu, 'desc':pvd, 'icon':icon, 'md': 'elo', 'id': "m4sport3"})
            self.addVideo(params)
            pvt = 'M4 SPORT 4'
            pvd = msg_elo4
            pvu = "https://www.mediaklikk.hu/m4-elo/"
            icon = self.ICON_URL_ELO
            params = MergeDicts(cItem, {'good_for_fav':False, 'title':pvt, 'url':pvu, 'url2':pvu, 'desc':pvd, 'icon':icon, 'md': 'elo', 'id': "m4sport4"})
            self.addVideo(params)
            pvt = 'M4 SPORT 5'
            pvd = msg_elo5
            pvu = "https://www.mediaklikk.hu/m4-elo/"
            icon = self.ICON_URL_ELO
            params = MergeDicts(cItem, {'good_for_fav':False, 'title':pvt, 'url':pvu, 'url2':pvu, 'desc':pvd, 'icon':icon, 'md': 'elo', 'id': "m4sport5"})
            self.addVideo(params)
        except Exception:
            printExc()
            
    def listMainItems(self, cItem):
        try:
            tabID = cItem.get('tab_id', '')
            if tabID == 'boxutca':
                self.susn('2', '11', 'm4_boxutca')
                self.dfml('548','4',4)
            elif tabID == 'foci':
                self.susn('2', '11', 'm4_foci')
                self.dfml('768','4',4)
            elif tabID == 'blfoci':
                self.susn('2', '11', 'm4_blfoci')
                self.dfbl(self.eblf)
            elif tabID == 'sporthirek':
                self.susn('2', '11', 'm4_sporthirek')
                self.dfml('1020','4',4)
            elif tabID == 'kozvetitesek':
                self.susn('2', '11', 'm4_kozvetitesek')
                self.dfml('1025','4',7)
        except Exception:
            printExc()
            
    def dfml(self, cid='', bid='', mig=0):
        try:
            if cid != '' and bid != '' and mig > 0:
                params = dict(self.defaultParams)
                params['header'] = dict(self.AJAX_HEADER)
                pue = 'https://www.m4sport.hu/wp-content/plugins/telesport.hu.widgets/widgets/newSubCategory/ajax_loadmore.php?cat_id={}&post_type=video&blog_id={}&page_number={}'
                for x in range(1, mig):
                    puf = pue.format(cid,bid,str(x))
                    sts, data = self.getPage(puf, params)
                    if not sts: return
                    if len(data) == 0: return
                    data = json_loads(data)
                    for item in data:
                        title = item['title']
                        date_str = item['date'][0:10].replace('.','/').strip()
                        url = item['link']
                        rstr = 'video/' + date_str + '/' 
                        url2 = url.replace('videok//',rstr)
                        desc = item['date'] + '-i adás\n\nA műsor tartalma:\n' + title
                        icon = item['image']
                        params = {'title':title, 'url':url, 'url2':url2, 'desc':desc, 'icon':icon, 'md': 'egyeb'}
                        self.addVideo(params)
        except Exception:
            printExc()
            
    def dfbl(self, pu=''):
        ln = 0
        try:
            if pu != '':
                sts, data = self.getPage(pu)
                if not sts: return
                if len(data) == 0: return
                tn = self.cm.ph.getDataBeetwenMarkers(data, '<h2 style="color: ;">Videók', '<div class="pagination" id="pagination', False)[1]
                if len(tn) == 0: return
                data = self.cm.ph.getAllItemsBeetwenMarkers(tn, '<div class="image-wrapper tizenhatkilenc overflow hmsLazyLoad', '<div class="typeico">')
                if len(data) == 0: return
                for item in data:
                    ln += 1
                    icon = self.cm.ph.getSearchGroups(item, '''data-src=['"]([^"^']+?)['"]''')[0]
                    if icon.startswith('//'):
                        icon = 'https:' + icon
                    if not icon.startswith('https'): continue
                    if not self.cm.isValidUrl(icon): continue
                    tnt = self.cm.ph.getDataBeetwenMarkers(item, '<div class="cikk-content-title', '</h1>')[1]
                    if len(tnt) == 0: continue
                    url = self.cm.ph.getSearchGroups(tnt, 'href=[\'"]([^"^\']+?)[\'"]')[0]
                    if url.startswith('//'):
                        url = 'https:' + url
                    if not url.startswith('https'): continue
                    title_tmp = self.cm.ph.getDataBeetwenMarkers(tnt, 'href="', '/a>', False)[1]
                    title = self.cm.ph.getDataBeetwenMarkers(title_tmp, '>', '<', False)[1].strip()
                    if title == '': continue
                    desc = 'A műsor tartalma:\n' + title
                    params = {'title':title, 'url':url, 'url2':url, 'desc':desc, 'icon':icon, 'md': 'egyeb'}
                    self.addVideo(params)
                    if ln > 30: break
        except Exception:
            printExc()

    def listSecondItems(self, cItem):
        try:
            tabID = cItem.get('tab_id', '')
            return
        except Exception:
            printExc()
        
    def getLinksForVideo(self, cItem):
        a = 0
        url = cItem['url']
        url2 = cItem['url2']
        md = cItem['md']
        printDBG(md)
        if md == 'elo':
            self.susn('2', '11', 'm4_elo')
            urllist = []
            new = self.kvlva(url, cItem['id'])
            urllist.append(new)
            a = 1
            for i in urllist:
                if i == '':
                     urllist.remove(i)
        videoUrls = []
        turl = self.kvlva(url, False)
        if len(turl) == 0:
            turl = self.kvlva(url2, False)
        if a == 1:
             turl = urllist
             for i in turl:
                 uri = urlparser.decorateParamsFromUrl(i)
                 protocol = uri.meta.get('iptv_proto', '')
                 if protocol == 'm3u8':
                     retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                     retTab = retTab[-1]
                     retTab['name'] = 'direct link'
                     videoUrls.append(retTab)
        if a == 0:
             uri = urlparser.decorateParamsFromUrl(turl)
             protocol = uri.meta.get('iptv_proto', '')
             if protocol == 'm3u8':
                 retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                 videoUrls.extend(retTab)
             elif protocol == 'f4m':
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
             elif protocol == 'mpd':
                retTab = getMPDLinksWithMeta(uri, False)
                videoUrls.extend(retTab)
             else:
                videoUrls.append({'name':'direct link', 'url':uri})
        return videoUrls
        
    def kvlva(self, pu, opcio):
        bu = ''
        try:
            if pu != '':
                sts, data = self.getPage(pu)
                if not sts: 
                    return ''
                tn = self.cm.ph.getDataBeetwenMarkers(data, 'token":"', '","', False)[1]
                if len(tn) == 0:
                    tn = self.cm.ph.getDataBeetwenMarkers(data, 'streamId":"', '","', False)[1]
                    if len(tn) == 0: 
                        return ''
                if not opcio:
                    tul = "https://player.mediaklikk.hu/playernew/player.php?video=" + tn
                if opcio:
                    tul = "https://player.mediaklikk.hu/playernew/player.php?video=" + opcio + "&noflash=yes&osfamily=Android&osversion=7.0&browsername=Chrome%20Mobile&browserversion=&title=&contentid=" + opcio + "&embedded=1"
                sts, data = self.getPage(tul)
                if not sts: 
                    return ''
                printDBG(data)
                vl = self.cm.ph.getAllItemsBeetwenMarkers(data, 'file": "', '",', False)
                if len(vl) > 1:
                    vl = vl[1]
                else:
                   vl = vl[0]
                vl = vl.replace('\/','/')
                if vl.startswith('/'):
                    vl = 'https:' + vl
                if not self.cm.isValidUrl(vl): 
                    return ''
                if len(vl) != '':
                    bu = vl
        except Exception:
            return ''
        return bu
        
    def malvadst(self, i_md='', i_hgk='', i_mpu=''):
        uhe = 'http://www.figyelmeztetes.hu/hely/sata/vansatdb.php'
        pstd = {'md':i_md, 'hgk':i_hgk, 'mpu':i_mpu}
        t_s = ''
        temp_vn = ''
        temp_vni = ''
        try:
            if i_md != '' and i_hgk != '' and i_mpu != '':
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
                if not sts: return t_s
                if len(data) == 0: return t_s
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_a_div', '</div>')[1]
                if len(data) == 0: return t_s
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '/>')
                if len(data) == 0: return t_s
                for item in data:
                    t_i = self.cm.ph.getSearchGroups(item, 'id=[\'"]([^"^\']+?)[\'"]')[0]
                    if t_i == 'vn':
                        temp_vn = self.cm.ph.getSearchGroups(item, 'value=[\'"]([^"^\']+?)[\'"]')[0]
                    elif t_i == 'vni':
                        temp_vni = self.cm.ph.getSearchGroups(item, 'value=[\'"]([^"^\']+?)[\'"]')[0]
                if temp_vn != '':
                    t_s = temp_vn
            return t_s
        except Exception:
            return t_s
        
    def susn(self, i_md='', i_hgk='', i_mpu=''):
        uhe = 'http://www.figyelmeztetes.hu/hely/sata/vansatdb.php'
        pstd = {'md':i_md, 'hgk':i_hgk, 'mpu':i_mpu, 'hv':self.vivn, 'orv':self.porv, 'bts':self.pbtp}
        try:
            if i_md != '' and i_hgk != '' and i_mpu != '':
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
            return
        except Exception:
            return
            
    def gits(self):
        bv = '-'
        tt = []
        try:
            if fileExists('/etc/issue'):
                fr = open('/etc/issue','r')
                for ln in fr:
                    ln = ln.rstrip('\n')
                    if ln != '':
                        tt.append(ln)
                fr.close()
                if len(tt) == 1:
                    bv = tt[0].strip()[:-6].capitalize()
                if len(tt) == 2:
                    bv = tt[1].strip()[:-6].capitalize()
            return bv
        except:
            return '-'
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        try:
            printDBG("listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
            self.susn('2', '11', 'm4_kereses')
            return
        except Exception:
            return
        return
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        self.currList = []
        if name == None:
            self.listMainMenu( {'name':'category'} )
        elif category == 'list_main':
            self.listMainItems(self.currItem)
        elif category == 'list_second':
            self.listSecondItems(self.currItem)
        elif category in ['search', 'search_next_page']:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, m4sport(), True, [])
