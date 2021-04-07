# -*- coding: utf-8 -*-
import time
import threading

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.asynccall import AsyncMethod
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback


from enigma import eTimer

class AutocompleteSearch:

    def __init__(self, provider, historyList=[]):
        printDBG("AS.__init__")

        self.lock = threading.Lock()
        self.event = threading.Event()

        self.run = True
        self.workThread = None
        self.requestParams = {}
        self.requestStamp = 0

        self.lastSuggestions = None
        self.lastStamp = -1

        self.timer = eTimer()
        self.timer_conn = None
        self.timer_started = False
        self.callback = None
        self.provider = provider

        self.historyList = []
        for item in historyList:
            try:
                self.historyList.append((item.decode('utf-8').lower(), item))
            except Exception:
                printExc()

    def __del__(self):
        printDBG("AS.__del__")

    def term(self):
        printDBG("AS._terminate")
        self.stop()
        self.provider = None

    def start(self, callback):
        if self.workThread == None:
            self.workThread = AsyncMethod(self._process)(self.provider)
            self.callback = callback
            self.timer_conn = eConnectCallback(self.timer.timeout, self._poll)
            return True
        return False

    def stop(self):
        if self.workThread != None:
            self.timer.stop()
            self.timer_conn = None
            self.callback = None
            self.timer_started = False

            with self.lock:
                last = self.requestStamp == self.lastStamp
                self.run = False
                self.event.set()
            
            if last:
                # give a chance to finish in the normal way
                time.sleep(0.01)
            self.workThread.kill()
            self.workThread = None

    def set(self, txt, locale):
        if self.workThread != None:
            with self.lock:
                self.requestParams = {'text':str(txt), 'locale':locale}
                self.requestStamp += 1
                self.event.set()
                stamp = int(self.requestStamp)

            if not self.timer_started:
                printDBG("AutocompleteSearch >>> START TIMER")
                self.timer.start(500)
                self.timer_started = True
            return stamp
        return -1

    def getProviderName(self):
        try:
            return self.provider.getName()
        except Exception:
            printExc()
        return _('Error occurs')

    def _process(self, provider):
        printDBG("AS._process start")
        prevStamp = 0
        stamp = 0
        text = ''
        while True:
            with self.lock:
                if not self.run:
                    return
                stamp = self.requestStamp
                text = self.requestParams.get('text', '')
                locale = self.requestParams.get('locale', '')
                self.event.clear()

            if stamp != prevStamp:
                if self.historyList:
                    try:
                        text = text.decode('utf-8').lower()
                        for item in self.historyList:
                            if item[0] == text:
                                retList.append(item[1])
                    except Exception:
                        printExc()

                try:
                    retList = provider.getSuggestions(text, locale)
                except Exception:
                    retList = None
                    printExc()

                with self.lock:
                    self.lastSuggestions = retList
                    self.lastStamp = stamp
                prevStamp = stamp
            self.event.wait()

    def _poll(self):

        with self.lock:
            last = self.requestStamp == self.lastStamp
            retList = self.lastSuggestions
            retStamp = self.lastStamp
            self.lastSuggestions = None
            self.lastStamp = -1

        if last:
            printDBG("AutocompleteSearch <<< STOP TIMER")
            self.timer.stop()
            self.timer_started = False

        if retStamp != -1 and self.callback:
            self.callback(retList, retStamp)

