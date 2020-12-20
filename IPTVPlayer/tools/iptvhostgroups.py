# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, GetConfigDir, GetHostsList, IsHostEnabled
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostsGroupItem
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
import codecs
from os import path as os_path, remove as os_remove
###################################################


class IPTVHostsGroups:
    def __init__(self):
        printDBG("IPTVHostsGroups.__init__")
        self.lastError = ''
        self.GROUPS_FILE = GetConfigDir('iptvplayerhostsgroups.json')
        
        # groups
        self.PREDEFINED_GROUPS = ["userdefined", "moviesandseries", "cartoonsandanime", "music", "sport", "live", "documentary", "science", \
                                  "polish", "english", "german", "french", "russian", "hungarian", "arabic", "greek", "latino", "italian", \
                                  "swedish","balkans","others"]
        self.PREDEFINED_GROUPS_TITLES = {"userdefined":      "User defined", 
                                         "moviesandseries":  "Movies and series",
                                         "cartoonsandanime": "Cartoons and anime",
                                         "music":            "Music",
                                         "sport":            "Sport",
                                         "live":             "Live",
                                         "documentary":      "Documentary",
                                         "science":          "Science",
                                         "polish":           "Polish",
                                         "english":          "English",
                                         "german":           "German",
                                         "french":           "French",
                                         "russian":          "Russian",
                                         "hungarian":        "Hungarian",
                                         "arabic":           "Arabic",
                                         "greek":            "Greek",
                                         "latino":           "Latino",
                                         "italian":          "Italian",
                                         'swedish':          "Swedish",
                                         "balkans":          "Balkans",
                                         "others":           "Others",
                                        }
        
        self.LOADED_GROUPS = []
        self.LOADED_GROUPS_TITLES = {}
        self.LOADED_DISABLED_GROUPS = []
        
        self.CACHE_GROUPS = None
        
        # hosts
        self.PREDEFINED_HOSTS = {}
        HOST_AND_GROUPS = {
        '123movieshd' : [ 'english', 'moviesandseries'] ,
        '3player' : [ 'english'] ,
        '3sktv' : [ 'arabic', 'moviesandseries'] ,
        '7tvde' : [ 'german'] ,
        '9anime' : [ 'cartoonsandanime', 'english'] ,
        'akoam' : [ 'arabic', 'moviesandseries'] ,
        'alltubetv' : [ 'moviesandseries', 'polish'] ,
        'altadefinizione' : [ 'italian', 'moviesandseries'] ,
        'altadefinizione01' : [ 'italian', 'moviesandseries'] ,
        'altadefinizione1' : [ 'italian', 'moviesandseries'] ,
        'altadefinizionecool' : [ 'italian', 'moviesandseries'] ,
        'andrijaiandjelka' : [ 'balkans', 'moviesandseries'] ,
        'animeodcinki' : [ 'cartoonsandanime', 'polish'] ,
        'appletrailers' : [ 'moviesandseries'] ,
        'ardmediathek' : [ 'german'] ,
        'artetv' : [ 'english', 'french', 'german', 'latino', 'polish'] ,
        'bajeczkiorg' : [ 'cartoonsandanime', 'polish'] ,
        'bbciplayer' : [ 'english'] ,
        'bbcsport' : [ 'english', 'sport'] ,
        'bsto' : [ 'german', 'moviesandseries'] ,
        'cartoonhd' : [ 'english', 'moviesandseries'] ,
        'casacinema': [ 'italian', 'moviesandseries'] ,
        'cb01' : [ 'italian', 'moviesandseries'] ,
        'cb01uno' : [ 'italian', 'moviesandseries'] ,
        'cdapl' : [ 'moviesandseries', 'others', 'polish'] ,
        'chomikuj' : [ 'others', 'polish'] ,
        'christusvincit' : [ 'polish'] ,
        'cimaclubcom' : [ 'arabic', 'moviesandseries'] ,
        'cinemalibero' : ['italian', 'moviesandseries'],
        'cinemaxx' : [ 'german', 'moviesandseries'] ,
        'cinemay' : [ 'french', 'moviesandseries'] ,
        'cineto' : [ 'english', 'german', 'moviesandseries'] ,
        'classiccinemaonline' : [ 'english', 'moviesandseries'] ,
        'dailymotion' : [ 'arabic', 'balkans', 'documentary', 'english', 'french', 'german', 'greek', 'hungarian', 'italian', 'latino', 'live', 'music', 'others', 'polish', 'russian', 'science', 'swedish'] ,
        'dancetrippin' : [ 'english', 'music'] ,
        'dardarkomcom' : [ 'arabic', 'moviesandseries'] ,
        'ddl' : [ 'english', 'german', 'moviesandseries'] ,
        'del' : [ 'german', 'sport'] ,
        'dixmax' : [ 'latino', 'moviesandseries'] ,
        'dokumentalnenet' : [ 'documentary', 'polish', 'science'] ,
        'dplayit' : [ 'italian'] ,
        'dpstreamingcx' : [ 'french', 'moviesandseries'] ,
        'drdk' : [ 'others'] ,
        'dsda' : [ 'documentary', 'italian', 'science'] ,
        'efilmytv' : [ 'moviesandseries', 'polish'] ,
        'egybest' : [ 'arabic', 'moviesandseries'] ,
        'ekinomaniak' : ['moviesandseries', 'polish'], 
        'ekinotv' : [ 'moviesandseries', 'polish'] ,
        'ekstraklasatv' : [ 'polish', 'sport'] ,
        'eskago' : [ 'live', 'music', 'polish'] ,
        'eurosportplayer' : [ 'live', 'sport'] ,
        'faselhdcom' : [ 'arabic', 'moviesandseries'] ,
        'favourites' : [ 'userdefined'] ,
        'fenixsite' : [ 'balkans', 'moviesandseries'] ,
        'fighttube' : [ 'polish', 'sport'] ,
        'fightvideo' : [ 'english', 'sport'] ,
        'filisertv' : [ 'moviesandseries', 'polish'] ,
        'filma24hdcom' : [ 'balkans', 'moviesandseries'] ,
        'filma24io' : [ 'balkans', 'moviesandseries'] ,
        'filmaoncom' : [ 'balkans', 'moviesandseries'] ,
        'filmativa' : [ 'balkans', 'moviesandseries'] ,
        'filmehdnet' : [ 'balkans', 'moviesandseries'] ,
        'filmeonlineto' : [ 'balkans', 'english', 'moviesandseries'] ,
        'filmezz' : [ 'hungarian', 'moviesandseries'] ,
        'filmixco' : [ 'moviesandseries', 'russian'] ,
        'filmoviplex' : [ 'balkans', 'moviesandseries'] ,
        'filmpalast' : [ 'german', 'moviesandseries'] ,
        'filmpertutti' : [ 'italian', 'moviesandseries'] ,
        'filmstreamhdit' : [ 'italian', 'moviesandseries'] ,
        'filmstreamvkcom' : [ 'french', 'moviesandseries'] ,
        'filmynadzis': [ 'moviesandseries', 'polish'] ,
        'forjatn' : [ 'arabic', 'english', 'french', 'moviesandseries'] ,
        'francetv' : [ 'french'] ,
        'freediscpl' : [ 'moviesandseries', 'others', 'polish'] ,
        'fullmatchtvcom' : ['sport'] ,
        'gamatocom' : [ 'greek', 'moviesandseries'] ,
        'gamatotvme' : [ 'greek', 'moviesandseries'] ,
        'govodtv' : [ 'moviesandseries', 'polish'] ,
        'greekdocumentaries3' : [ 'documentary', 'greek'] ,
        'guardaserie' : [ 'italian', 'moviesandseries'] ,
        'hd1080online' : [ 'moviesandseries', 'russian'] ,
        'hdfilmetv' : [ 'german', 'moviesandseries'] ,
        'hdfull' : [ 'latino', 'moviesandseries'] ,
        'hdkinomir' : [ 'moviesandseries', 'russian'] ,
        'hdpopcornscom' : [ 'english', 'moviesandseries'] ,
        'hdstreams' : [ 'german', 'moviesandseries'] ,
        'hitboxtv' : [ 'arabic', 'balkans', 'english', 'french', 'german', 'greek', 'hungarian', 'italian', 'latino', 'others', 'polish', 'russian', 'sport', 'swedish'] ,
        'hoofootcom' : [ 'english', 'sport'] ,
        'icefilmsinfo' : [ 'english', 'moviesandseries'] ,
        'iitvpl' : [ 'moviesandseries', 'polish'] ,
        'interiatv' : [ 'polish'] ,
        'ipla' : [ 'polish'] ,
        'iptvplayerinfo' : [ 'others'] ,
        'itvcom' : [ 'english'] ,
        'joemonsterorg' : [ 'polish'] ,
        'kabarety' : [ 'others', 'polish'] ,
        'kijknl' : [ 'others'] ,
        'kinogo' : [ 'moviesandseries', 'russian'] ,
        'kinopokaz' : [ 'moviesandseries', 'russian'] ,
        'kinotan' : [ 'moviesandseries', 'russian'] ,
        'kinox' : [ 'german', 'moviesandseries'] ,
        'kisscartoonme' : [ 'cartoonsandanime', 'english'] ,
        'kkiste' : [ 'german', 'moviesandseries'] ,
        'kreskoweczki' : [ 'cartoonsandanime', 'polish'] ,
        'kreskowkazone' : [ 'cartoonsandanime', 'polish'] ,
        'la7it' : [ 'italian'] ,
        'librestream' : [ 'french', 'moviesandseries'] ,
        'liveleak' : [ 'english', 'others'] ,
        'localmedia' : [ 'others', 'userdefined'] ,
        'lookmovieag' : [ 'english', 'moviesandseries'] ,
        'losmovies' : [ 'english', 'moviesandseries'] ,
        'luxveritatis' : [ 'polish'] ,
        'maxtvgo' : [ 'polish'] ,
        'meczykipl' : [ 'polish', 'sport'] ,
        'mediasetplay' : [ 'italian'] ,
        'mooviecc' : [ 'hungarian', 'moviesandseries'] ,
        'movie4kto' : [ 'english', 'french', 'german', 'moviesandseries', 'russian'] ,
        'movienightws' : [ 'english', 'moviesandseries'] ,
        'movierulzsx' : [ 'arabic', 'english', 'moviesandseries'] ,
        'movizlandcom' : [ 'arabic', 'moviesandseries'] ,
        'movs4ucom' : [ 'arabic', 'moviesandseries'] ,
        'mozicsillag' : [ 'hungarian', 'moviesandseries'] ,
        'mrpiracy' : [ 'latino', 'moviesandseries'] ,
        'musicbox' : [ 'music'] ,
        'musicmp3ru' : [ 'music'] ,
        'myfreemp3' : [ 'music'] ,
        'mythewatchseries' : [ 'english', 'moviesandseries'] ,
        'ngolos' : [ 'sport'] ,
        'ninateka' : [ 'polish'] ,
        'nuteczki' : [ 'music', 'polish'] ,
        'ogladajto' : [ 'moviesandseries', 'polish'], 
        'officialfilmillimite' : [ 'french', 'moviesandseries'] ,
        'oipeirates' : [ 'greek', 'moviesandseries'] ,
        'okgoals' : [ 'sport'] ,
        'ororotv' : [ 'english', 'others'] ,
        'orthobulletscom' : [ 'documentary', 'english', 'science'] ,
        'otakufr' : [ 'cartoonsandanime', 'french'] ,
        'ourmatchnet' : [ 'english', 'sport'] ,
        'pinkbike' : [ 'english', 'others', 'sport'] ,
        'playpuls' : [ 'polish'] ,
        'playrtsiw' : [ 'english', 'french', 'german', 'italian', 'others'] ,
        'plusdede' : [ 'latino', 'moviesandseries'] ,
        'pmgsport' : [ 'italian'] ,
        'putlockertvto' : [ 'english', 'moviesandseries'] ,
        'questtvcouk' : [ 'english', 'science'] ,
        'radiostacja' : [ 'music', 'polish'] ,
        'raiplay' : [ 'italian'] ,
        'redbull' : [ 'sport'] ,
        'rtbfbe' : [ 'french', 'others'] ,
        'rteieplayer' : [ 'english'] ,
        'rtlmost' : [ 'hungarian', 'moviesandseries'] ,
        'serienstreamto' : [ 'german', 'moviesandseries'] ,
        'seriesonline' : [ 'english', 'moviesandseries'] ,
        'serijeonline' : [ 'balkans', 'moviesandseries'] ,
        'shahiidanimenet' : [ 'arabic', 'cartoonsandanime'] ,
        'shoutcast' : [ 'music'] ,
        'skstream' : [ 'french', 'moviesandseries'] ,
        'solarmovie' : [ 'english', 'latino', 'moviesandseries'] ,
        'sovdub' : [ 'moviesandseries', 'russian'] ,
        'spiegeltv' : [ 'german'] ,
        'sportdeutschland' : [ 'german', 'sport'] ,
        'sportitalia' : [ 'italian', 'sport'] ,
        'spryciarze' : [ 'others', 'polish'] ,
        'streaminghdfun' : [ 'italian', 'moviesandseries'] ,
        'streamliveto' : [ 'live'] ,
        'svtplayse' : [ 'swedish'] ,
        'tainieskaiseirestv' : [ 'greek', 'moviesandseries'] ,
        'tainiesonline' : [ 'greek', 'moviesandseries'] ,
        'tantifilmorg' : [ 'italian', 'moviesandseries'] ,
        'tata' : [ 'german'] ,
        'ted' : [ 'english', 'others'] ,
        'tfarjocom' : [ 'french', 'moviesandseries'] ,
        'thewatchseriesto' : [ 'english', 'moviesandseries'] ,
        'tvgrypl' : [ 'polish'] ,
        'tvn24' : [ 'polish'] ,
        'tvnowde' : [ 'german'] ,
        'tvnvod' : [ 'polish'] ,
        'tvplayercom' : [ 'english'] ,
        'tvproart' : [ 'polish'] ,
        'tvpvod' : [ 'polish'] ,
        'tvrepublika' : [ 'polish'] ,
        'twitchtv' : [ 'arabic', 'balkans', 'english', 'french', 'german', 'greek', 'hungarian', 'italian', 'latino', 'others', 'polish', 'russian', 'sport', 'swedish'] ,
        'uktvplay' : [ 'english'] ,
        'urllist' : [ 'others'] ,
        'ustreamtv' : [ 'english', 'live', 'science'] ,
        'vevo' : [ 'music'] ,
        'vidcorncom' : [ 'latino', 'moviesandseries'] ,
        'vimeo' : [ 'arabic', 'balkans', 'french', 'german', 'greek', 'hungarian', 'italian', 'latino', 'music', 'others', 'polish', 'russian', 'swedish'] ,
        'vodpl' : [ 'polish'] ,
        'vumedicom' : [ 'documentary', 'english', 'science'] ,
        'vumooch' : [ 'english', 'moviesandseries'] ,
        'watchcartoononline' : [ 'cartoonsandanime', 'english'] ,
        'watchwrestling' : [ 'english', 'sport'] ,
        'watchwrestlinguno' : [ 'english', 'sport'] ,
        'webstream' : [ 'arabic', 'english', 'german', 'live', 'polish', 'sport'] ,
        'wgrane' : [ 'others', 'polish'] ,
        'wolnelekturypl' : [ 'others', 'polish'] ,
        'worldfree4u' : [ 'english', 'moviesandseries'] ,
        'wpolscepl' : [ 'polish'] ,
        'wptv' : [ 'polish'] ,
        'wrealu24tv' : [ 'polish'] ,
        'xrysoise' : [ 'greek', 'moviesandseries'] ,
        'yesmoviesto' : [ 'english', 'moviesandseries'] ,
        'yifytv' : [ 'english', 'moviesandseries'] ,
        'youtube' : [ 'arabic', 'balkans', 'english', 'french', 'german', 'greek', 'hungarian', 'italian', 'latino', 'live', 'music', 'others', 'polish', 'russian', 'swedish'] ,
        'zdfmediathek' : ['german']
        }        
        
        for h in HOST_AND_GROUPS:
            for g in HOST_AND_GROUPS[h]:
                #printDBG("adding %s in group %s" % (h, g))
                
                if not g in self.PREDEFINED_HOSTS:
                    self.PREDEFINED_HOSTS[g]=[h]
                else:
                    self.PREDEFINED_HOSTS[g].append(h)
        
        self.LOADED_HOSTS = {}
        self.LOADED_DISABLED_HOSTS = {}
        self.CACHE_HOSTS = {}
        
        self.ADDED_HOSTS = {}
        
        self.hostListFromFolder = None
        self.hostListFromList = None
        
    def _getGroupFile(self, groupName):
        printDBG("IPTVHostsGroups._getGroupFile")
        return GetConfigDir("iptvplayer%sgroup.json" % groupName)
        
    def getLastError(self):
        return self.lastError
        
    def addHostToGroup(self, groupName, hostName):
        printDBG("IPTVHostsGroups.addHostToGroup")
        hostsList = self.getHostsList(groupName)
        self.ADDED_HOSTS[groupName] = []
        if hostName in hostsList or hostName in self.ADDED_HOSTS[groupName]:
            self.lastError = _('This host has been added already to this group.')
            return False
        self.ADDED_HOSTS[groupName].append(hostName)
        return True
        
    def flushAddedHosts(self):
        printDBG("IPTVHostsGroups.flushAddedHosts")
        for groupName in self.ADDED_HOSTS:
            if 0 == len(self.ADDED_HOSTS[groupName]): continue
            newList = list(self.CACHE_HOSTS[groupName])
            newList.extend(self.ADDED_HOSTS[groupName])
            self.setHostsList(groupName, newList)
        self.ADDED_HOSTS = {}
        
    def getGroupsWithoutHost(self, hostName):
        groupList = self.getGroupsList()
        retList = []
        for groupItem in groupList:
            hostsList = self.getHostsList(groupItem.name)
            if hostName not in hostsList and hostName not in self.ADDED_HOSTS.get(groupItem.name, []):
                retList.append(groupItem)
        return retList
        
    def getHostsList(self, groupName):
        printDBG("IPTVHostsGroups.getHostsList")
        if groupName in self.CACHE_HOSTS:
            return self.CACHE_HOSTS[groupName]
    
        if self.hostListFromFolder == None:
            self.hostListFromFolder = GetHostsList(fromList=False, fromHostFolder=True)
        if self.hostListFromList == None: 
            self.hostListFromList = GetHostsList(fromList=True, fromHostFolder=False)
        
        groupFile = self._getGroupFile(groupName)
        self._loadHosts(groupFile, groupName, self.hostListFromFolder, self.hostListFromFolder)
        
        hosts = []
        for host in self.LOADED_HOSTS[groupName]:
            if IsHostEnabled(host):
                hosts.append(host)
        
        for host in self.PREDEFINED_HOSTS.get(groupName, []):
            if host not in hosts and host not in self.LOADED_DISABLED_HOSTS[groupName] and host in self.hostListFromList and host in self.hostListFromFolder and IsHostEnabled(host):
                hosts.append(host)
                
        self.CACHE_HOSTS[groupName] = hosts
        return hosts
        
    def setHostsList(self, groupName, hostsList):
        printDBG("IPTVHostsGroups.setHostsList groupName[%s], hostsList[%s]" % (groupName, hostsList))
        # hostsList - must be updated with host which were not disabled in this group but they are not 
        # available or they are disabled globally
        outObj = {"version":0, "hosts":hostsList, "disabled_hosts":[]}
        
        #check if some host from diabled one has been enabled
        disabledHosts = []
        for host in self.LOADED_DISABLED_HOSTS[groupName]:
            if host not in hostsList:
                disabledHosts.append(host)
        
        # check if some host has been disabled
        for host in self.CACHE_HOSTS[groupName]:
            if host not in hostsList and host in self.PREDEFINED_HOSTS.get(groupName, []):
                disabledHosts.append(host)
        
        outObj['disabled_hosts'] = disabledHosts
        
        self.LOADED_DISABLED_HOSTS[groupName] = disabledHosts
        self.CACHE_HOSTS[groupName] = hostsList
        
        groupFile = self._getGroupFile(groupName)
        return self._saveHosts(outObj, groupFile)
        
    def _saveHosts(self, outObj, groupFile):
        printDBG("IPTVHostsGroups._saveHosts")
        ret = True
        try:
            data = json_dumps(outObj)
            self._saveToFile(groupFile, data)
        except Exception:
            printExc()
            self.lastError = _("Error writing file \"%s\".\n") % self.GROUPS_FILE
            ret = False
        return ret
        
    def _loadHosts(self, groupFile, groupName, hostListFromFolder, hostListFromList):
        printDBG("IPTVHostsGroups._loadHosts groupName[%s]" % groupName)
        predefinedHosts = self.PREDEFINED_HOSTS.get(groupName, [])
        hosts = []
        disabledHosts = []
        
        ret = True
        if os_path.isfile(groupFile):
            try:
                data = self._loadFromFile(groupFile)
                data = json_loads(data)
                for item in data.get('disabled_hosts', []):
                    # we need only information about predefined hosts which were disabled
                    if item in predefinedHosts and item in hostListFromList:
                        disabledHosts.append(str(item))
                
                for item in data.get('hosts', []):
                    if item in hostListFromFolder:
                        hosts.append(item)
            except Exception:
                printExc()
        
        self.LOADED_HOSTS[groupName] = hosts
        self.LOADED_DISABLED_HOSTS[groupName] = disabledHosts
        
    def getGroupsList(self):
        printDBG("IPTVHostsGroups.getGroupsList")
        if self.CACHE_GROUPS != None:
            return self.CACHE_GROUPS
        self._loadGroups()
        groups = list(self.LOADED_GROUPS)
        
        for group in self.PREDEFINED_GROUPS:
            if group not in self.LOADED_GROUPS and group not in self.LOADED_DISABLED_GROUPS:
                groups.append(group)
        
        groupList = []
        for group in groups:
            title = self.PREDEFINED_GROUPS_TITLES.get(group, '')
            if title == '': title = self.LOADED_GROUPS_TITLES.get(group, '')
            if title == '': title = group.title()
            item = CHostsGroupItem(group, _(title))
            groupList.append(item)
        self.CACHE_GROUPS = groupList
        return groupList
        
    def getPredefinedGroupsList(self):
        printDBG("IPTVHostsGroups.getPredefinedGroupsList")
        groupList = []
        for group in self.PREDEFINED_GROUPS: 
            title = self.PREDEFINED_GROUPS_TITLES[group]
            item = CHostsGroupItem(group, title)
            groupList.append(item)
        return groupList
        
    def setGroupList(self, groupList):
        printDBG("IPTVHostsGroups.setGroupList groupList[%s]" % groupList)
        # update disabled groups
        outObj = {"version":0, "groups":[], "disabled_groups":[]}
        
        for group in self.PREDEFINED_GROUPS:
            if group not in groupList:
                outObj['disabled_groups'].append(group)
        
        for group in groupList:
            outObj['groups'].append({'name':group})
            if group in self.LOADED_GROUPS_TITLES:
                outObj['groups']['title'] = self.LOADED_GROUPS_TITLES[group]
                
        return self._saveGroups(outObj)
        
    def _saveGroups(self, outObj):
        printDBG("IPTVHostsGroups._saveGroups")
        ret = True
        try:
            data = json_dumps(outObj)
            self._saveToFile(self.GROUPS_FILE, data)
        except Exception:
            printExc()
            self.lastError = _("Error writing file \"%s\".\n") % self.GROUPS_FILE
            ret = False
        return ret
        
    def _loadGroups(self):
        printDBG("IPTVHostsGroups._loadGroups")
        self.LOADED_GROUPS = []
        self.LOADED_DISABLED_GROUPS = []
        self.LOADED_GROUPS_TITLES = {}
        
        groups = []
        titles = {}
        disabledGroups = []
        
        ret = True
        if os_path.isfile(self.GROUPS_FILE):
            try:
                data = self._loadFromFile(self.GROUPS_FILE)
                data = json_loads(data)
                for item in data.get('disabled_groups', []):
                    # we need only information about predefined groups which were disabled
                    if item in self.PREDEFINED_GROUPS:
                        disabledGroups.append(str(item))
                
                for item in data.get('groups', []):
                    name = str(item['name'])
                    groups.append(name)
                    if 'title' in item: titles[name] = str(item['title'])
            except Exception:
                printExc()
        
        self.LOADED_GROUPS = groups
        self.LOADED_DISABLED_GROUPS = disabledGroups 
        self.LOADED_GROUPS_TITLES = titles
        
    def _saveToFile(self, filePath, data, encoding='utf-8'):
        printDBG("IPTVHostsGroups._saveToFile filePath[%s]" % filePath)
        with codecs.open(filePath, 'w', encoding, 'replace') as fp:
            fp.write(data)
            
    def _loadFromFile(self, filePath, encoding='utf-8'):
        printDBG("IPTVHostsGroups._loadFromFile filePath[%s]" % filePath)
        with codecs.open(filePath, 'r', encoding, 'replace') as fp:
            return fp.read()
        
        
