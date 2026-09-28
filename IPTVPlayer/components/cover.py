# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, GetIconDir
from Plugins.Extensions.IPTVPlayer.components.asynccall import AsyncMethod

###################################################
# FOREIGN import
###################################################
from Tools.LoadPixmap import LoadPixmap
from Components.Pixmap import Pixmap
from enigma import ePicLoad, ePoint, eTimer
import os


def PicLoadPara(width, height, filename):
    # ePicLoad.setPara values; the 8th turns on EXIF auto-orientation (older images ignore it). Only for
    # files ePicLoad decodes as PNG/JPEG (same magic as its getFileType): for any other format OpenATV,
    # OpenPLi, OpenViX and others crash in ePicLoad.getData with it on (EXIF info never allocated).
    try:
        with open(filename, 'rb') as f:
            head = f.read(12)
    except Exception:
        head = b''
    autoOrient = 12 == len(head) and (head[1:4] == b'PNG' or head[6:10] == b'JFIF' or head[:3] == b'\xff\xd8\xff')
    return (width, height, 1, 1, False, 1, "#FF000000", autoOrient)


class Cover(Pixmap):
    def __init__(self):
        printDBG("Cover.__init__ ---------------------------")
        Pixmap.__init__(self)
        self.picload = ePicLoad()

        self.currIcon = {}
        self.waitIcon = {}

        self.decoding = False
        self.picload_conn = eConnectCallback(self.picload.PictureData, self.decodeCallBack)
        # decodePreparedCover(): the picture being made showable in a worker thread
        self.prepare = None
        self.prepareTimer = None
        self.prepareTimer_conn = None

    def __del__(self):
        printDBG("Cover.__del__ ---------------------------")

    def preWidgetRemove(self, instance):
        printDBG("Cover.preWidgetRemove ---------------------------")
        self._stopPrepare()
        if None is not self.picload_conn:
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
        # checking if decoding is needed
        self.waitIcon = {"CallBackFun": callBackFun, "FileName": filename, "Ident": ident}
        if filename != self.currIcon.get('FileName', ''):
            if not self.decoding:
                printDBG("_______________start decodeCover")
                self.decoding = True
                prevIcon = self.currIcon
                self.currIcon = self.waitIcon
                self.waitIcon = {}
                if os.path.exists(filename):
                    self.picload.setPara(PicLoadPara(self.instance.size().width(), self.instance.size().height(), filename))
                    ret = self.picload.startDecode(filename)
                else:
                    printDBG("_______________decodeCover file not exists (%s)" % filename)
                    ret = -1
                if ret != 0:
                    printDBG("_______________error start decodeCover[%d]" % ret)
                    self.decoding = False
                    self.currIcon = prevIcon
                    return -1
            return True
        else:
            printDBG("___________________________decodeCover not need (%s)" % filename)
            return False

    # decodeCover() for a picture downloaded by wget/curl: gzip-encoded, WebP or AVIF files (also under a .jpg
    # name) are made showable first, like the list icons, in a worker thread because an ffmpeg conversion
    # takes a moment. Returns what decodeCover returns; while preparing True, and a picture that then still
    # can't be decoded ends in callBackFun without a Pixmap. Main thread only. The conversion happens in place,
    # so for the user's own files pass sourceFile: filename is then a copy of it that gets converted (a
    # picture that needs nothing is decoded straight from sourceFile).
    def decodePreparedCover(self, filename, callBackFun, ident, sourceFile=None):
        from Plugins.Extensions.IPTVPlayer.libs.pCommon import ImageFileNeedsPreparing, PrepareImageFile
        self._stopPrepare()
        if not ImageFileNeedsPreparing(sourceFile or filename):
            return self.decodeCover(sourceFile or filename, callBackFun, ident)
        printDBG("Cover.decodePreparedCover preparing %s%s" % (filename, (" from %s" % sourceFile) if sourceFile else ""))
        self.prepareTimer = eTimer()
        self.prepareTimer_conn = eConnectCallback(self.prepareTimer.timeout, self._checkPrepared)
        # a plugin worker thread (AsyncMethod), not a bare threading.Thread: the ffmpeg fallback of convertWebp
        # runs through iptv_execute, which needs the plugin's thread data (_iptvplayer_ext)
        self.prepare = {'call': AsyncMethod(PrepareImageFile)(filename, sourceFile), 'args': (filename, callBackFun, ident)}
        self.prepareTimer.start(100)
        return True

    def _checkPrepared(self):
        if self.prepare is None or self.prepare['call'].isAlive():
            return
        filename, callBackFun, ident = self.prepare['args']
        self._stopPrepare()
        if -1 == self.decodeCover(filename, callBackFun, ident):
            callBackFun({"Changed": True, "Pixmap": None, "FileName": filename, "Ident": ident})

    def _stopPrepare(self):
        if self.prepareTimer is not None:
            self.prepareTimer.stop()
        self.prepareTimer_conn = None
        self.prepareTimer = None
        self.prepare = None

    # the red X for a picture that exists at the source but failed; the callback gets it like any picture
    @staticmethod
    def getErrorCoverPath():
        return GetIconDir('CoverError.png')

    def decodeErrorCover(self, callBackFun, ident):
        ret = self.decodeCover(self.getErrorCoverPath(), callBackFun, ident)
        if -1 == ret:
            printDBG("Cover.decodeErrorCover placeholder can not be started: %s" % self.getErrorCoverPath())
        return ret

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
        if ptrPixmap is not None:
            self.instance.setPixmap(ptrPixmap)

    def decodeCallBack(self, picInfo=None):
        printDBG("decodeCallBack")
        if not self.decoding:
            printDBG("decodeCallBack ignored - no active decode")
            return
        self.decoding = False
        ptr = self.picload.getData()
        if '' != self.waitIcon.get('FileName', '') and self.waitIcon.get('FileName', '') != self.currIcon.get('FileName', ''):
            self.decodeCover(self.waitIcon['FileName'], self.waitIcon['CallBackFun'], self.waitIcon['Ident'])
        elif None is not self.currIcon.get("CallBackFun", None):
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
        if None is not self.picload_conn:
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
        if ptr is not None:
            self.instance.setPixmap(ptr)
            self.show()

    def updateIcon(self, filename):
        if not self.paramsSet:
            self.picload.setPara((self.instance.size().width(), self.instance.size().height(), 1, 1, False, 1, "#FF000000"))
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
        # printDBG('loadFrames')
        self.framesList = []
        for item in framesPathList:
            # printDBG('loadFrames [%s]' % item)
            self.framesList.append(LoadPixmap(item))

    def nextFrame(self):
        # printDBG('nextFrame')
        if 0 < len(self.framesList) and self.visible:
            self.currFrame += 1
            if (self.currFrame + 1) > len(self.framesList):
                self.currFrame = 0
            # printDBG('nextFrame [%d]' % self.currFrame)
            self.setPixmap(self.framesList[self.currFrame])

    def onShow(self):
        # printDBG('onShow')
        self.visible = True
        if -1 == self.currFrame:
            self.nextFrame()
        Pixmap.onShow(self)

    def onHide(self):
        # printDBG('onHide')
        self.visible = False
        Pixmap.onHide(self)

    def setPixmap(self, ptr):
        if self.instance:
            self.instance.setPixmap(ptr)
            return True
        return False
