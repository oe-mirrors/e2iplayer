# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, eConnectCallback, byteify, E2PrioFix, GetPyScriptCmd, getDebugMode, GetPluginDir
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eConsoleAppContainer, getDesktop, eTimer
from Screens.Screen import Screen
from Components.Label import Label
from Components.ActionMap import ActionMap
from Tools.LoadPixmap import LoadPixmap
from Tools.BoundFunction import boundFunction
from Components.config import config

import codecs

try:
    import json
except Exception:
    import simplejson as json
import base64
###################################################


class UnCaptchaReCaptchaMyJDWidget(Screen):
    
    def __init__(self, session, title, sitekey, referer):
        self.session = session
        Screen.__init__(self, session)
        self.sitekey = sitekey
        self.referer = referer
        
        sz_w = 504 #getDesktop(0).size().width() - 190
        sz_h = 300 #getDesktop(0).size().height() - 195
        if sz_h < 500:
            sz_h += 4
        self.skin = """
            <screen position="center,center" title="%s" size="%d,%d">
             <ePixmap position="5,9"   zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
             
             <widget name="label_red"    position="45,9"  zPosition="5" size="175,27" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
             <widget name="title"        position="5,47"  zPosition="1" size="%d,23" font="Regular;20"            transparent="1"  backgroundColor="#00000000"/>
             <widget name="console"      position="10,%d" zPosition="2" size="%d,160" valign="center" halign="center"   font="Regular;24" transparent="0" foregroundColor="white" backgroundColor="black"/>
            </screen>""" %(
                title,
                sz_w, sz_h,                # size
                GetIconDir('red' + '.png'),
                sz_w - 135,                # size title
                (sz_h - 160)/2, sz_w - 20, # console
                )
        
        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)
        
        self["title"]         = Label(" ")
        self["console"]       = Label(" ")
        
        self["label_red"]     = Label(_("Cancel"))
        
        self["actions"] = ActionMap(["ColorActions", "SetupActions", "WizardActions", "ListboxActions"],
            {
                "cancel": self.keyExit,
                #"ok"    : self.keyOK,
                "red": self.keyRed,
            }, -2)
        
        self.workconsole = {'console':None, 'close_conn':None, 'stderr_conn':None, 'stdout_conn':None, 'stderr':'', 'stdout':''}
        self.result = ''
        
        self.timer = {'timer':eTimer(), 'is_started':False}
        self.timer['callback_conn'] = eConnectCallback(self.timer['timer'].timeout, self._timoutCallback)
        self.errorCodeSet = False
        
    def _timoutCallback(self):
        self.timer['is_started'] = False
        self.close(self.result)
    
    def __onClose(self):
        self.workconsole['close_conn'] = None
        self.workconsole['stderr_conn'] = None
        self.workconsole['stdout_conn'] = None
        if  self.workconsole['console']:
            self.workconsole['console'].sendCtrlC()
        self.workconsole['console'] = None
        
        if self.timer['is_started']:
            self.timer['timer'].stop()
        self.timer['callback_conn'] = None
        self.timer = None
    
    def _scriptClosed(self, code=0):
        if code == 0:
            self["console"].setText(_('JDownloader script finished.'))
            self.close(self.result)
        elif not self.errorCodeSet:
            self["console"].setText(_("JDownloader script execution failed.\nError code: %s\n") % (code))
            
    def _scriptStderrAvail(self, data):
        self.workconsole['stderr'] += data
        self.workconsole['stderr'] = self.workconsole['stderr'].split('\n')
        if data.endswith('\n'):
            data = ''
        else:
            data = self.workconsole['stderr'].pop(-1)
        for line in self.workconsole['stderr']:
            line = line.strip()
            if line == '':
                continue
            try:
                line = byteify(json.loads(line))
                if line['type'] == 'captcha_result':
                    self.result = line['data']
                    # timeout timer
                    if self.timer['is_started']:
                        self.timer['timer'].stop()
                    # start timeout timer 3s
                    self.timer['timer'].start(3000, True)
                    self.timer['is_started'] = True
                    self["console"].setText(_('Captcha solved.\nWaiting for notification.'))
                elif line['type'] == 'status':
                    self["console"].setText(_(str(line['data'])))
                elif line['type'] == 'error':
                    if line['code'] == 500:
                        self["console"].setText(_('Invalid email.'))
                    elif line['code'] == 403:
                        self["console"].setText(_('Access denied. Please check password.'))
                    else:
                        self["console"].setText(_("Error code: %s\nError message: %s") % (line['code'], line['data']))
                    self.errorCodeSet = True
            except Exception:
                printExc()
        self.workconsole['stderr'] = data

    def _scriptStdoutAvail(self, data):
        self.workconsole['stdout'] += data
        self.workconsole['stdout'] = self.workconsole['stdout'].split('\n')
        if data.endswith('\n'):
            data = ''
        else:
            data = self.workconsole['stdout'].pop(-1)
        for line in self.workconsole['stdout']:
            printDBG(line)
        self.workconsole['stdout'] = data

    def startExecution(self):
        login = config.plugins.iptvplayer.myjd_login.value
        password = config.plugins.iptvplayer.myjd_password.value
        jdname = config.plugins.iptvplayer.myjd_jdname.value
        
        captcha = {'siteKey': self.sitekey, 'sameOrigin': True, 'siteUrl': self.referer, 'contextUrl': '/'.join(self.referer.split('/')[:3]), 'boundToDomain': True, 'stoken': None}
        try:
            captcha = base64.b64encode(json.dumps(captcha))
        except Exception:
            printExc()
        if getDebugMode() == '':
            debug = 0
        else:
            debug = 1
        
        cmd = GetPyScriptCmd('fakejd') + ' "%s" "%s" "%s" "%s" "%s" %d' % (GetPluginDir('libs/'), login, password, jdname, captcha, debug)
        
        self["console"].setText(_('JDownloader script execution'))
        
        self.workconsole['console']    = eConsoleAppContainer()
        self.workconsole['close_conn'] = eConnectCallback(self.workconsole['console'].appClosed, self._scriptClosed)
        self.workconsole['stderr_conn']  = eConnectCallback(self.workconsole['console'].stderrAvail, self._scriptStderrAvail)
        self.workconsole['stdout_conn']  = eConnectCallback(self.workconsole['console'].stdoutAvail, self._scriptStdoutAvail)
        self.workconsole["console"].execute(E2PrioFix(cmd, 0))
        printDBG(">>> EXEC CMD [%s]" % cmd)
    
    def onStart(self):
        self.onShown.remove(self.onStart)
        self.startExecution()
    
    def keyExit(self):
        self.close(self.result)
    
    def keyRed(self):
        self.close(self.result)
    
