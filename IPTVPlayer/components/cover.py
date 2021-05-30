# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback
from asynccall import AsyncMethod

###################################################
# FOREIGN import
###################################################
from Tools.LoadPixmap import LoadPixmap
from Components.Pixmap import Pixmap
from enigma import ePicLoad, ePoint
from Tools.BoundFunction import boundFunction

import threading


class Cover(Pixmap):
    def __init__(self):
        printDBG("Cover.__init__ ---------------------------")
        Pixmap.__init__(self)
        self.picload = ePicLoad()

        self.currIcon = {}
        self.waitIcon = {}
        self.paramsSet = False

        self.decoding = False
        self.picload_conn = None

    def __del__(self):
        printDBG("Cover.__del__ ---------------------------")

    def preWidgetRemove(self, instance):
        printDBG("Cover.preWidgetRemove ---------------------------")
        if None != self.picload_conn:
            printDBG("Cover.preWidgetRemove Wife bug detected :)")
            self.picload_conn = None
        try:
            if 'preWidgetRemove' in dir(Pixmap):
                Pixmap.preWidgetRemove(self, instance)
        except Exception:
            printExc()

    def onShow(self):
        Pixmap.onShow(self)

    # this function should be called only from mainThread
    # filename - path to image wich will be decoded
    # callBackFun - the function wich will be called after decoding
    # if decoding will be finished with success
    def decodeCover(self, filename, callBackFun, ident):
        printDBG("_______________decodeCover")
        #checking if decoding is needed
        self.waitIcon = {"CallBackFun": callBackFun, "FileName": filename, "Ident": ident}
        if filename != self.currIcon.get('FileName', ''):
            if not self.paramsSet:
                self.picload.setPara((self.instance.size().width(), self.instance.size().height(), 1, 1, False, 1, "#00000000"))
                self.paramsSet = True
            if not self.decoding:
                printDBG("_______________start decodeCover")
                self.decoding = True
                prevIcon = self.currIcon
                self.currIcon = self.waitIcon
                self.waitIcon = {}
                self.picload_conn = eConnectCallback(self.picload.PictureData, self.decodeCallBack)
                ret = self.picload.startDecode(filename)
                if ret != 0:
                    printDBG("_______________error start decodeCover[%d]" % ret)
                    self.picload_conn = None
                    self.decoding = False
                    self.currIcon = prevIcon
                    return -1
            return True
        else:
            printDBG("___________________________decodeCover not need (%s)" % filename)
            return False

    def checkDecodeNeeded(self, filename):
        iconFile = self.waitIcon.get('FileName', '')
        if '' == iconFile:
            iconFile = self.currIcon.get('FileName', '')
        return filename != iconFile

    # end decodeCover(self, filename, callBackFun, ident):

    # this method should be called only from mainThread
    # ptrPixmap - decoded pixelmap to set
    # filename  - path to image corresponding to pixelmap
    def updatePixmap(self, ptrPixmap, filename):
        printDBG("updatePixmap %s=%s" % (filename, self.currIcon["FileName"]))
        if ptrPixmap != None:
            self.instance.setPixmap(ptrPixmap)

    def decodeCallBack(self, picInfo=None):
        printDBG("decodeCallBack")
        self.picload_conn = None
        self.decoding = False
        ptr = self.picload.getData()
        if '' != self.waitIcon.get('FileName', '') and self.waitIcon.get('FileName', '') != self.currIcon.get('FileName', ''):
            self.decodeCover(self.waitIcon['FileName'], self.waitIcon['CallBackFun'], self.waitIcon['Ident'])
        elif None != self.currIcon.get("CallBackFun", None):
            self.currIcon["CallBackFun"]({"Changed": True, "Pixmap": ptr, "FileName": self.currIcon['FileName'], "Ident": self.currIcon["Ident"]})
    # end decodeCallBack(self, picInfo=None):


class Cover2(Pixmap):
    def __init__(self):
        Pixmap.__init__(self)
        self.picload = ePicLoad()
        self.paramsSet = False
        self.picload_conn = None

    def preWidgetRemove(self, instance):
        printDBG("Cover2.preWidgetRemove ---------------------------")
        if None != self.picload_conn:
            printDBG("Cover2.preWidgetRemove Wife bug detected :)")
            self.picload_conn = None
        try:
            if 'preWidgetRemove' in dir(Pixmap):
                Pixmap.preWidgetRemove(self, instance)
        except Exception:
            printExc()

    def onShow(self):
        Pixmap.onShow(self)

    def paintIconPixmapCB(self, picInfo=None):
        self.picload_conn = None
        ptr = self.picload.getData()
        if ptr != None:
            self.instance.setPixmap(ptr)
            self.show()

    def updateIcon(self, filename):
        if not self.paramsSet:
            self.picload.setPara((self.instance.size().width(), self.instance.size().height(), 1, 1, False, 1, "#00000000"))
            self.paramsSet = True
        self.picload_conn = eConnectCallback(self.picload.PictureData, self.paintIconPixmapCB)
        ret = self.picload.startDecode(filename)
        if ret != 0:
            self.picload_conn = None


class Cover3(Pixmap):
    def __init__(self):
        Pixmap.__init__(self)
        self.visible = True

    def setPixmap(self, ptr):
        self.instance.setPixmap(ptr)

    def getWidth(self):
        return self.instance.size().width()

    def getHeight(self):
        return self.instance.size().height()

    def setPosition(self, x, y):
        self.instance.move(ePoint(int(x), int(y)))

    def getPosition(self):
        p = self.instance.position()
        return (p.x(), p.y())


class SimpleAnimatedCover(Pixmap):
    def __init__(self):
        Pixmap.__init__(self)
        Pixmap.hide(self)
        self.visible = False

        self.framesList = []
        self.currFrame = -1

    def loadFrames(self, framesPathList):
        #printDBG('loadFrames')
        self.framesList = []
        for item in framesPathList:
            #printDBG('loadFrames [%s]' % item)
            self.framesList.append(LoadPixmap(item))

    def nextFrame(self):
        #printDBG('nextFrame')
        if 0 < len(self.framesList) and self.visible:
            self.currFrame += 1
            if (self.currFrame + 1) > len(self.framesList):
                self.currFrame = 0
            #printDBG('nextFrame [%d]' % self.currFrame)
            self.setPixmap(self.framesList[self.currFrame])

    def onShow(self):
        #printDBG('onShow')
        self.visible = True
        if -1 == self.currFrame:
            self.nextFrame()
        Pixmap.onShow(self)

    def onHide(self):
        #printDBG('onHide')
        self.visible = False
        Pixmap.onHide(self)

    def setPixmap(self, ptr):
        if self.instance:
            self.instance.setPixmap(ptr)
            return True
        return False
