# -*- coding: utf-8 -*-
#
#  IPTV download manager List UI
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, formatBytes, GetIPTVDMImgDir, GetIconDir
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVListComponentBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
import skin
from datetime import timedelta
###################################################


class IPTVDownloadManagerList(IPTVListComponentBase):
    ICONS_FILESNAMES = {DMHelper.STS.WAITING: 'iconwait1.png',
                        DMHelper.STS.DOWNLOADING: 'iconwait2.png',
                        DMHelper.STS.DOWNLOADED: 'icondone.png',
                        DMHelper.STS.INTERRUPTED: 'iconerror.png',
                        DMHelper.STS.ERROR: 'iconwarning.png',
                        }

    def __init__(self):
        IPTVListComponentBase.__init__(self)

        self.fonts = {}
        try:
            self.fonts[0] = skin.fonts["iptvdwnlistitem_0"]
        except Exception:
            self.fonts[0] = ("Regular", 20, 40, 0)
        try:
            self.fonts[1] = skin.fonts["iptvdwnlistitem_1"]
        except Exception:
            self.fonts[1] = ("Regular", 16, 20, 0)
        try:
            self.fonts[2] = skin.fonts["iptvdwnlistitem_2"]
        except Exception:
            self.fonts[2] = ("Regular", 26, 55, 0)

        self.l.setFont(0, gFont(self.fonts[0][0], self.fonts[0][1]))
        self.l.setFont(1, gFont(self.fonts[1][0], self.fonts[1][1]))
        self.l.setFont(2, gFont(self.fonts[2][0], self.fonts[2][1]))

        height = self.fonts[0][2] + self.fonts[1][2] + self.fonts[2][2]

        self.l.setItemHeight(115)

        self.dictPIX = {}

    def _nullPIX(self):
        for key in self.ICONS_FILESNAMES:
            self.dictPIX[key] = None

    def onCreate(self):
        self._nullPIX()
        for key in self.dictPIX:
            try:
                pixFile = self.ICONS_FILESNAMES.get(key, None)
                if None != pixFile:
                    self.dictPIX[key] = LoadPixmap(cached=True, path=GetIconDir(pixFile))
            except Exception:
                printExc()

    def onDestroy(self):
        self._nullPIX()

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]

        # Downloaded Size
        info1 = formatBytes(item.downloadedSize)

        # File Size
        if item.fileSize > 0:
            info1 += "/" + formatBytes(item.fileSize)

        elif item.totalFileDuration > 0 and item.downloadedFileDuration > 0:
            totalDuration = item.totalFileDuration
            downloadDuration = item.downloadedFileDuration
            totalDuration = str(timedelta(seconds=totalDuration))
            downloadDuration = str(timedelta(seconds=downloadDuration))
            if totalDuration.startswith('0:'):
                totalDuration = totalDuration[2:]
            if downloadDuration.startswith('0:'):
                downloadDuration = downloadDuration[2:]
            info1 = "{0}/{1} ({2})".format(downloadDuration, totalDuration, info1)

        # Downloaded Procent
        if item.downloadedProcent >= 0:
            info1 += ", " + str(item.downloadedProcent) + "%"

        # Download Speed
        info2 = info1 + ", " + formatBytes(item.downloadedSpeed) + "/s"

        try:
            fileName = item.fileName.split('/')[-1]
        except Exception:
            fileName = ''
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, 0, width - 70, self.fonts[0][2], 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, fileName))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, self.fonts[0][2], width - 70, self.fonts[1][2], 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.url))

        status = ""
        info = ""
        if DMHelper.STS.WAITING == item.status:
            status += _("PENDING")
        elif DMHelper.STS.DOWNLOADING == item.status:
            status += _("DOWNLOADING")
            info = info2
        elif DMHelper.STS.DOWNLOADED == item.status:
            status += _("DOWNLOADED")
            info = info1
        elif DMHelper.STS.INTERRUPTED == item.status:
            status += _("ABORTED")
            info = info1
        elif DMHelper.STS.ERROR == item.status:
            status += _("DOWNLOAD ERROR")

        res.append((eListboxPythonMultiContent.TYPE_TEXT, width - 240, self.fonts[0][2] + self.fonts[1][2], 240, self.fonts[2][2], 2, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, status))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 45, self.fonts[0][2] + self.fonts[1][2], width - 45 - 240, self.fonts[2][2], 2, RT_HALIGN_LEFT | RT_VALIGN_CENTER, info))

        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, 1, 64, 64, self.dictPIX.get(item.status, None)))

        return res
