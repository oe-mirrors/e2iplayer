# -*- coding: utf-8 -*-
#### Local imports
from __init__ import _
import settings
import webParts
import webThreads
import Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget

from webTools import *
from Plugins.Extensions.IPTVPlayer.components.ihost import IHost, CDisplayListItem, RetHost, CUrlItem, ArticleContent, CFavItem
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper, DMItemBase
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import IsUrlDownloadable
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetPluginDir, printDBG
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdmapi import IPTVDMApi, DMItem
#### e2 imports
from Components.config import configfile, config
from Components.Language import language

#### system imports
import os
from twisted.web import resource, http, util
import urllib

########################################################


def reloadScripts():
    #### Reload scripts if new version of source exists ####
    webPath = GetPluginDir(file='/Web/')
    if os.path.exists(os.path.join(webPath, "webParts.py")):
        if os.path.exists(os.path.join(webPath, "webParts.pyo")):
            if (int(os.path.getmtime(os.path.join(webPath, "webParts.pyo"))) <
                int(os.path.getmtime(os.path.join(webPath, "webParts.py")))):
                reload(webParts)
        else:
            reload(webParts)
    if os.path.exists(os.path.join(webPath, "webThreads.py")):
        if os.path.exists(os.path.join(webPath, "webThreads.pyo")):
            if (int(os.path.getmtime(os.path.join(webPath, "webThreads.pyo"))) <
                int(os.path.getmtime(os.path.join(webPath, "webThreads.py")))):
                reload(webThreads)
        else:
            reload(webThreads)
########################################################


class redirectionPage(resource.Resource):

    title = "E2iPlayer Webinterface"
    isLeaf = False

    def render(self, req):
        req.setHeader('Content-type', 'text/html')
        req.setHeader('charset', 'UTF-8')

        """ rendering server response """
        command = req.args.get("cmd", None)
        html = """
<html lang="%s">
  <head>
    <title>%s</title>
    <meta http-equiv="refresh" content="5; URL=/iptvplayer/">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <meta name="keywords" content="automatic redirection">
  </head>
  <body>
  <p align="center"> %s
  <a href="/iptvplayer/">%s</a></p>
  </body>
</html>""" % (language.getLanguage()[:2],
          _('Redirect'),
          _('You are using old version of OpenWebif.<br> To go to E2iPlayer web Select the following link<br>'),
          _('Click'))

        return html

#######################################################


class StartPage(resource.Resource):
    title = "E2iPlayer Webinterface"
    isLeaf = False

    def __init__(self):
        pass

    def render(self, req):
        req.setHeader('Content-type', 'text/html')
        req.setHeader('charset', 'UTF-8')
        resetStatusMSG = []
        if len(req.args.keys()) > 0:
            if req.args.keys()[0] == 'resetState':
                settings.activeHost = {}
                settings.activeHostsHTML = {}
                settings.currItem = {}
                settings.retObj = None
                settings.configsHTML = {}
                settings.tempLogsHTML = ''
                settings.NewHostListShown = True
                settings.StopThreads = True
                settings.hostsWithNoSearchOption = []
                settings.GlobalSearchListShown = True
                settings.GlobalSearchTypes = ["VIDEO"]
                settings.GlobalSearchQuery = ''
                settings.GlobalSearchResults = {}
                settings.searchingInHost = None
                for myThread in ['buildtempLogsHTML', 'buildConfigsHTML', 'doUseHostAction', 'doGlobalSearch']:
                    ret = stopRunningThread(myThread)
                    if ret:
                        resetStatusMSG.append(myThread)
                if len(resetStatusMSG) == 0:
                    resetStatusMSG.append(_('Web component has been reset and all threads are stopped. :)'))
                else:
                    resetStatusMSG.insert(0, _('Web component has been reset, the following threads are still working:'))

        """ rendering server response """
        if isActiveHostInitiated():
            return util.redirectTo("/iptvplayer/usehost", req)
        reloadScripts()
        html = '<html lang="%s">' % language.getLanguage()[:2]
        html += webParts.IncludeHEADER()
        html += webParts.Body().StartPageContent(', '.join(resetStatusMSG))
        return html
#######################################################


class searchPage(resource.Resource):
    title = "E2iPlayer Webinterface"
    isLeaf = False

    def __init__(self):
        self.Counter = 0

    def render(self, req):
        req.setHeader('Content-type', 'text/html')
        req.setHeader('charset', 'UTF-8')

        if len(req.args.keys()) > 0:
            key = req.args.keys()[0]
            arg = req.args.get(key, None)[0]
            if len(req.args.keys()) > 1:
                if req.args.keys()[1] == 'type':
                    if req.args.get(req.args.keys()[1], 'ALL')[0] == '':
                        settings.GlobalSearchTypes = ["VIDEO", "AUDIO"]
                    elif req.args.get(req.args.keys()[1], 'ALL')[0] == '':
                        settings.GlobalSearchTypes = ["AUDIO"]
                    else:
                        settings.GlobalSearchTypes = ["VIDEO"]
                arg = req.args.get(key, None)[0]
            #print 'searchPage received: ', key, '=' , arg
        else:
            key = None
            arg = None

        """ rendering server response """
        reloadScripts()

        if key is None or arg is None or arg == '':
            if isThreadRunning('doGlobalSearch'):
                stopRunningThread('doGlobalSearch')
                self.Counter += 1
                extraMeta = '<meta http-equiv="refresh" content="1">'
                MenuStatusMSG = _('Waiting search thread to stop, please wait (%d)') % (self.Counter)
            else:
                MenuStatusMSG = ''
                extraMeta = ''
                settings.GlobalSearchListShown = True
            ShowCancelButton = False
        elif key == 'cmd' and arg == 'stopThread':
            stopRunningThread('doGlobalSearch')
            self.Counter = 0
            return util.redirectTo("/iptvplayer/search", req)
        elif not isThreadRunning('doGlobalSearch') and key == 'GlobalSearch' and settings.GlobalSearchListShown == True:
            settings.GlobalSearchListShown = False
            settings.GlobalSearchQuery = arg
            webThreads.doGlobalSearch().start()
            self.Counter = 0
            extraMeta = '<meta http-equiv="refresh" content="1">'
            MenuStatusMSG = _('Initiating data, please wait')
            ShowCancelButton = False
            return util.redirectTo("/iptvplayer/search?doGlobalSearch=1", req)
        elif isThreadRunning('doGlobalSearch'):
            self.Counter += 1
            extraMeta = '<meta http-equiv="refresh" content="1">'
            if settings.searchingInHost is None:
                MenuStatusMSG = _('Searching, please wait (%d)') % (self.Counter)
            else:
                MenuStatusMSG = _('Searching in %s, please wait (%d)') % (settings.searchingInHost, self.Counter)
            ShowCancelButton = True
        elif not isThreadRunning('doGlobalSearch') and key == 'doGlobalSearch':
            return util.redirectTo("/iptvplayer/search", req)
        else:
            ShowCancelButton = False
            MenuStatusMSG = ''
            extraMeta = ''
            settings.GlobalSearchListShown = False

        html = '<html lang="%s">' % language.getLanguage()[:2]
        html += webParts.IncludeHEADER(extraMeta)
        html += webParts.Body().SearchPageContent(MenuStatusMSG, ShowCancelButton)
        return html


#######################################################
class hostsPage(resource.Resource):
    title = "E2iPlayer Webinterface"
    isLeaf = False

    def __init__(self):
        self.Counter = 0

    def render(self, req):

        req.setHeader('Content-type', 'text/html')
        req.setHeader('charset', 'UTF-8')

        """ rendering server response """
        reloadScripts()
        html = '<html lang="%s">' % language.getLanguage()[:2]

        if iSactiveHostsHTMLempty() and not isThreadRunning('buildActiveHostsHTML'):
            webThreads.buildActiveHostsHTML().start()
            extraMeta = '<meta http-equiv="refresh" content="1">'
            MenuStatusMSG = _('Initiating data, please wait')
            ShowCancelButton = False
        elif isThreadRunning('buildActiveHostsHTML'):
            self.Counter += 1
            extraMeta = '<meta http-equiv="refresh" content="1">'
            MenuStatusMSG = _('Loading data, please wait (%d)') % self.Counter
            ShowCancelButton = False
        else:
            extraMeta = ''
            MenuStatusMSG = ''
            self.Counter = 0
            ShowCancelButton = False

        html += webParts.IncludeHEADER(extraMeta)
        html += webParts.Body().hostsPageContent(MenuStatusMSG, ShowCancelButton)
        return html
##########################################################


class logsPage(resource.Resource):
    title = "E2iPlayer Webinterface"
    isLeaf = False

    def __init__(self):
        pass

    def render(self, req):
        """ rendering server response """
        htmlError = ''
        DBGFileContent = ''
        MenuStatusMSG = ''
        extraMeta = ''

        if os.path.exists('/hdd/iptv.dbg'):
            DBGFileName = '/hdd/iptv.dbg'
        elif os.path.exists('/tmp/iptv.dbg'):
            DBGFileName = '/tmp/iptv.dbg'
        else:
            DBGFileName = ''

        command = req.args.get("cmd", ['NOcmd'])

        if DBGFileName == '':
            req.setHeader('Content-type', 'text/html')
            req.setHeader('charset', 'UTF-8')
            reloadScripts()
            html = '<html lang="%s">' % language.getLanguage()[:2]
            html += webParts.IncludeHEADER(extraMeta)
            html += webParts.Body().logsPageContent(MenuStatusMSG, htmlError, DBGFileName, DBGFileContent)
            html += '<p align="center"><b><font color="#FFE4C4">%s</font></b></p>' % _('Debug file does not exist - nothing to download')
            return html
        elif command[0] == "downloadLog":
            req.responseHeaders.setRawHeaders('content-disposition', ['attachment; filename="iptv_dbg.txt"'])
            with open(DBGFileName, 'r') as f:
                  html = f.read()
                  f.close()
        elif command[0] == 'deleteLog':
            if os.path.exists(DBGFileName):
                try:
                    os.remove(DBGFileName)
                    htmlError = 'deleteLogOK'
                except Exception:
                    htmlError = 'deleteLogError'
            else:
                htmlError = 'deleteLogNO'

        req.setHeader('Content-type', 'text/html')
        req.setHeader('charset', 'UTF-8')
        reloadScripts()
        if settings.tempLogsHTML == '' and not isThreadRunning('buildtempLogsHTML'):
            webThreads.buildtempLogsHTML(DBGFileName).start()
            extraMeta = '<meta http-equiv="refresh" content="1">'
            MenuStatusMSG = _('Loading data, please wait')
        html = '<html lang="%s">' % language.getLanguage()[:2]
        html += webParts.IncludeHEADER(extraMeta)
        html += webParts.Body().logsPageContent(MenuStatusMSG, htmlError, DBGFileName, DBGFileContent)
        return html
#######################################################


class settingsPage(resource.Resource):
    title = "E2iPlayer Webinterface"
    isLeaf = False

    def __init__(self):
        pass

    def render(self, req):
        extraMeta = ''
        MenuStatusMSG = ''
        req.setHeader('Content-type', 'text/html')
        req.setHeader('charset', 'UTF-8')

        """ rendering server response """
        if len(req.args.keys()) > 0:
            key = req.args.keys()[0]
            arg = req.args.get(key, None)[0]
            print 'Received: ', key, '=', arg

            try:
                if key is None or arg is None:
                    pass
                elif key == 'cmd' and arg[:3] == 'ON:':
                    exec('config.plugins.iptvplayer.%s.setValue(True)\nconfig.plugins.iptvplayer.%s.save()' % (arg[3:], arg[3:]))
                    settings.configsHTML = {}
                    settings.activeHostsHTML = {}
                    return util.redirectTo("/iptvplayer/settings", req)
                elif key == 'cmd' and arg[:4] == 'OFF:':
                    print('config.plugins.iptvplayer.%s.setValue(False)\nconfig.plugins.iptvplayer.%s.save()' % (arg[4:], arg[4:]))
                    exec('config.plugins.iptvplayer.%s.setValue(False)\nconfig.plugins.iptvplayer.%s.save()' % (arg[4:], arg[4:]))
                    settings.activeHostsHTML.pop(arg[4:], None)
                    settings.activeHostsHTML.pop(arg[8:], None)
                    settings.configsHTML = {}
                    return util.redirectTo("/iptvplayer/settings", req)
                elif key[:4] == "CFG:":
                    exec('config.plugins.iptvplayer.%s.setValue("%s")\nconfig.plugins.iptvplayer.%s.save()' % (key[4:], arg, key[4:]))
                    settings.configsHTML = {}
                    return util.redirectTo("/iptvplayer/settings", req)
                elif key[:4] == "INT:":
                    exec('config.plugins.iptvplayer.%s.setValue("%s")\nconfig.plugins.iptvplayer.%s.save()' % (key[4:], arg, key[4:]))
                    settings.configsHTML = {}
                    return util.redirectTo("/iptvplayer/settings", req)
                configfile.save()
            except Exception:
                printDBG("[webSite.py:settingsPage] EXCEPTION for updating value '%s' for key '%s'" % (arg, key))

        if isConfigsHTMLempty() and not isThreadRunning('buildConfigsHTML'):
            webThreads.buildConfigsHTML().start()
            extraMeta = '<meta http-equiv="refresh" content="1">'
            MenuStatusMSG = _('Initiating data, please wait')
        elif isThreadRunning('buildConfigsHTML'):
            extraMeta = '<meta http-equiv="refresh" content="1">'
            MenuStatusMSG = _('Loading data, please wait')
        else:
            extraMeta = ''
            MenuStatusMSG = ''

        reloadScripts()
        html = '<html lang="%s">' % language.getLanguage()[:2]
        html += webParts.IncludeHEADER(extraMeta)
        html += webParts.Body().settingsPageContent(MenuStatusMSG)

        return html
#######################################################


class downloaderPage(resource.Resource):
    title = "E2iPlayer Webinterface"
    isLeaf = False

    def __init__(self):
        pass

    def render(self, req):
        req.setHeader('Content-type', 'text/html')
        req.setHeader('charset', 'UTF-8')

        """ rendering server response """
        extraMeta = '<meta http-equiv="refresh" content="5">'
        key = None
        arg = None
        arg2 = None
        arg3 = None
        DMlist = []
        if len(req.args.keys()) >= 1:
            key = req.args.keys()[0]
            arg = req.args.get(key, None)[0]
            try:
                arg2 = req.args.get(key, None)[1]
            except Exception:
                pass
            try:
                arg3 = req.args.get(key, None)[2]
            except Exception:
                pass
            print 'Received: "%s"="%s","%s","%s"' % (key, arg, arg2, arg3)

        if key is None or arg is None:
            if None != Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                DMlist = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList()
        elif key == 'cmd' and arg == 'initDM':
            if None == Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                printDBG('============WebSite.py Initialize Download Manager============')
                Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager = IPTVDMApi(2, int(config.plugins.iptvplayer.IPTVDMMaxDownloadItem.value))
                DMlist = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList()
        elif key == 'cmd' and arg == 'runDM':
            if None != Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.runWorkThread()
                DMlist = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList()
        elif key == 'cmd' and arg == 'stopDM':
            if None != Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.stopWorkThread()
                DMlist = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList()
                extraMeta = '<meta http-equiv="refresh" content="10">'
        elif key == 'cmd' and arg == 'downloadsDM':
            if None != Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                DMlist = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList()
        elif key == 'watchMovie' and os.path.exists(arg):
            return util.redirectTo("/file?action=download&file=%s" % urllib.quote(arg.decode('utf8', 'ignore').encode('utf-8')), req)
        elif key == 'stopDownload' and arg.isdigit():
            if None != Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.stopDownloadItem(int(arg))
                DMlist = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList()
        elif key == 'downloadAgain' and arg.isdigit():
            if None != Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.continueDownloadItem(int(arg))
                DMlist = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList()
        elif key == 'removeMovie' and arg.isdigit():
            if None != Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.removeDownloadItem(int(arg))
                DMlist = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList()

        elif key == 'cmd' and arg == 'arvchiveDM':
            if arg2 == 'deleteMovie' and os.path.exists(arg3):
                os.remove(arg3)
            elif arg2 == 'watchMovie' and os.path.exists(arg3):
                return util.redirectTo("/file?action=download&file=%s" % urllib.quote(arg3.decode('utf8', 'ignore').encode('utf-8')), req)
            if os.path.exists(config.plugins.iptvplayer.NaszaSciezka.value) and None != Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
                files = os.listdir(config.plugins.iptvplayer.NaszaSciezka.value)
                files.sort(key=lambda x: x.lower())
                for item in files:
                    if item.startswith('.'):
                        continue # do not list hidden items
                    if item[-4:].lower() not in ['.flv', '.mp4']:
                        continue
                    fileName = os.path.join(config.plugins.iptvplayer.NaszaSciezka.value, item)
                    skip = False
                    for item2 in Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.getList():
                        if fileName == item2.fileName.replace('//', '/'):
                            skip = True
                            break
                    if skip:
                        continue
                    listItem = DMItemBase(url=fileName, fileName=fileName)
                    try:
                        listItem.downloadedSize = os.path.getsize(fileName)
                    except Exception:
                        listItem.downloadedSize = 0
                    listItem.status = DMHelper.STS.DOWNLOADED
                    listItem.downloadIdx = -1
                    DMlist.append(listItem)
                if len(DMlist) == 0:
                    listItem = DMItemBase(_('Nothing has been downloaded yet.'), '')
                    listItem.status = 'INFO'
                    DMlist.append(listItem)

        if len(DMlist) == 0 and arg != 'arvchiveDM':
            listItem = DMItemBase(_('No materials waiting in the downloader queue'), '')
            listItem.status = 'INFO'
            DMlist.append(listItem)
            extraMeta = ''
        elif len(DMlist) == 0 and arg in ['arvchiveDM', 'stopDM']:
            extraMeta = ''

        reloadScripts()
        html = '<html lang="%s">' % language.getLanguage()[:2]
        html += webParts.IncludeHEADER(extraMeta)
        html += webParts.Body().downloaderPageContent(Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager, DMlist)
        return html
#######################################################


class useHostPage(resource.Resource):
    title = "E2iPlayer Webinterface"
    isLeaf = False

    def __init__(self):
        self.Counter = 0

    def render(self, req):
        reloadScripts()

        """ rendering server response """
        self.key = None
        self.arg = None
        self.searchType = None
        html = ''
        extraMeta = ''
        MenuStatusMSG = ''

        if len(req.args.keys()) > 0:
            self.key = req.args.keys()[0]
            self.arg = req.args.get(self.key, None)[0]
            if len(req.args.keys()) > 1:
                self.searchType = req.args.keys()[1]
                print "useHostPage received: '%s'='%s' searchType='%s'" % (self.key, str(self.arg), self.searchType)
            else:
                print "useHostPage received: '%s'='%s'" % (self.key, str(self.arg))

        if self.key is None and isActiveHostInitiated() == False:
            return util.redirectTo("/iptvplayer/hosts", req)
        elif self.key == 'cmd' and self.arg == 'hosts':
            initActiveHost(None)
            return util.redirectTo("/iptvplayer/hosts", req)
        elif self.key == 'cmd' and self.arg == 'stopThread':
            stopRunningThread('doUseHostAction')
            initActiveHost(None)
            setNewHostListShown(False)
            return util.redirectTo("/iptvplayer/hosts", req)
        elif self.key == 'cmd' and self.arg == 'InitList':
            settings.retObj = settings.activeHost['Obj'].getInitList()
            settings.activeHost['PathLevel'] = 1
            settings.activeHost['ListType'] = 'ListForItem'
            settings.activeHost['Status'] = ''
            settings.currItem = {}
            setNewHostListShown(False)
        elif self.key == 'cmd' and self.arg == 'PreviousList':
            settings.retObj = settings.activeHost['Obj'].getPrevList()
            settings.activeHost['PathLevel'] -= 1
            settings.activeHost['ListType'] = 'ListForItem'
            settings.currItem = {}
            settings.activeHost['Status'] = settings.activeHost['Status'].rpartition('>')[0]
            setNewHostListShown(False)
        #long running commands
        elif isNewHostListShown() and not isThreadRunning('doUseHostAction'):
            self.Counter = 0
            setNewHostListShown(False)
            webThreads.doUseHostAction(self.key, self.arg, self.searchType).start()
            extraMeta = '<meta http-equiv="refresh" content="1">'
            MenuStatusMSG = _('Initiating data, please wait')
        elif isThreadRunning('doUseHostAction'):
            self.Counter += 1
            extraMeta = '<meta http-equiv="refresh" content="1">'
            MenuStatusMSG = _('Loading data, please wait (%d)') % self.Counter

        req.setHeader('Content-type', 'text/html')
        req.setHeader('charset', 'UTF-8')

        html += '<html lang="%s">' % language.getLanguage()[:2]
        html += webParts.IncludeHEADER(extraMeta)
        html += webParts.Body().useHostPageContent(MenuStatusMSG, True)
        return html
##########################################################
