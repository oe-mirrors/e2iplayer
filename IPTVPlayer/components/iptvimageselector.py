# -*- coding: utf-8 -*-
#
#  IPTV IMAGE SELECTOR
#
#  $Id$
#
# 
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVListComponentBase
###################################################

###################################################
# FOREIGN import
###################################################
from skin import parseColor
from enigma import eListboxPythonMultiContent, getDesktop, ePicLoad
from Tools.LoadPixmap import LoadPixmap
from Tools.BoundFunction import boundFunction
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
###################################################

class IPTVImagesSelectionList(IPTVListComponentBase):
    ICONS_FILESNAMES = {'on': 'radio_button_on.png', 'off': 'radio_button_off.png'}
    def __init__(self, height):
        IPTVListComponentBase.__init__(self)
        
        self.l.setItemHeight(height)
        self.dictPIX = {}
        printDBG('IPTVImagesSelectionList.__init__ height: %d' % height)
    
    def _nullPIX(self):
        for key in self.ICONS_FILESNAMES:
            self.dictPIX[key] = None

    def onCreate(self):
        printDBG('--- onCreate ---')
        self._nullPIX()
        for key in self.dictPIX:
            try:
                pixFile = self.ICONS_FILESNAMES.get(key, None)
                if None != pixFile:
                    self.dictPIX[key] = LoadPixmap(cached=True, path=GetIconDir(pixFile))
            except Exception:
                printExc()
        
    def onDestroy(self):
        printDBG('--- onDestroy ---')
        self._nullPIX()
    
    def buildEntry(self, item):
        res = [None]
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        try:
            printDBG('--- buildEntry ---')
            printDBG('%s: ' % (item['id']))
            x = (width - item['width']) / 2
            y = (height - item['height']) / 2
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, x, y, item['width'], item['height'], item['pixmap']))
            if item['id'] != None:
                if item['selected']:
                    sel_key = 'on'
                else:
                    sel_key = 'off'
                res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, 3, 16, 16, self.dictPIX.get(sel_key, None)))
        except Exception:
            printExc()
        return res

class IPTVMultipleImageSelectorWidget(Screen):

    def __prepareSkin(self):
        if None == self.iptv_width:
            self.iptv_width = getDesktop(0).size().width()
        if None == self.iptv_height:
            self.iptv_height = getDesktop(0).size().height()
        if self.iptv_title == None:
            self.iptv_title = _('Select pictures')
        
        if self.iptv_message != None and self.iptv_message_height == None:
            self.iptv_message_height = self.iptv_height / 10
        if self.iptv_accep_label != None and self.iptv_accep_height == None:
            self.iptv_accep_height = self.iptv_height / 20
        
        y = 0
        skin = ['<screen position="center,center" title="%s" size="%d,%d">' % (self.iptv_title, self.iptv_width, self.iptv_height)]
        if self.iptv_message != None:
            skin.append('<widget name="message" position="10,10" zPosition="1" size="%d,%d" valign="center" halign="center" font="Regular;22"  transparent="1"  backgroundColor="#00000000"/>' % (self.iptv_width - 20, self.iptv_message_height))
            y += 10 + self.iptv_message_height
        
        list_width = self.iptv_image_width + 40
        list_height = (self.iptv_height - y) - 20
        if self.iptv_accep_label != None:
            list_height -= self.iptv_accep_height + 10 
        
        x = (self.iptv_width - (10 * (self.iptv_col_num + 1) + list_width * self.iptv_col_num)) / 2
        for idx in range(self.iptv_col_num):
            if idx != self.iptv_col_num - 1: 
                scrollbar_mode = 'showNever'
            else: 
                scrollbar_mode = 'showOnDemand'
                list_width += 30 # added for scrollbar
            skin.append('<widget name="col_%d" position="%d,%d" zPosition="1" size="%d,%d" scrollbarMode="%s" transparent="1"  backgroundColor="#00000000" enableWrapAround="1" />' % (idx, x, y, list_width, list_height, scrollbar_mode))
            x += 10 + list_width
        y += list_height + 10 
        
        if self.iptv_accep_label != None:
            skin.append('<widget name="accept_button"  position="10,%d"  zPosition="1" size="%d,%d"  valign="center" halign="center" font="Regular;22" foregroundColor="#00FFFFFF" backgroundColor="#320F0F0F" />' % (y, self.iptv_width - 20, self.iptv_accep_height))
        skin.append('</screen>')
        skin = '\n'.join(skin)
        printDBG(">>>")
        printDBG(skin)
        printDBG("<<<")
        return skin
        
    def __init__(self, session, title=None, width=None, height=None, message=None, message_height=None, accep_label=None, accep_height=None, col_num=4, images=[], image_width=160, image_height=160, max_sel_items=None):
        self.iptv_title = title
        self.iptv_width = width
        self.iptv_height = height
        self.iptv_message = message
        self.iptv_message_height = message_height
        
        self.iptv_accep_label = accep_label
        self.iptv_accep_height = accep_height
        
        self.iptv_col_num = col_num
        self.iptv_row_num = len(images) / col_num
        if len(images) % col_num > 0:
            self.iptv_row_num += 1
        
        self.iptv_images = images
        self.iptv_image_width = image_width
        self.iptv_image_height = image_width
        self.iptv_max_sel_items = max_sel_items
        self.iptv_num_sel_items = 0
        self.iptv_images_data = None
        
        self.iptv_grid = []
        for x in range(self.iptv_col_num):
            self.iptv_grid.append([])
            for y in range(self.iptv_row_num):
                self.iptv_grid[x].append(None)
        
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        #self.skinName = "IPTVMultipleImageSelectorWidget"
        
        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        # create controls
        self["title"] = Label(self.iptv_title)
        if self.iptv_message != None:
            self["message"] = Label(str(self.iptv_message))
        
        for idx in range(self.iptv_col_num):
            self["col_%d" % idx] = IPTVImagesSelectionList(self.iptv_image_height + 20)
        
        if self.iptv_accep_label:
            self["accept_button"] = Label(self.iptv_accep_label)
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "WizardActions", "ListboxActions", "IPTVPlayerListActions"],
            {
                "cancel": self.key_cancel,
                "ok": self.key_ok,
                "green": self.key_green,
                "read": self.key_read,
                
                "up": self.key_up,
                "down": self.key_down,
                "moveUp": self.key_up,
                "moveDown": self.key_down,
                "moveTop": self.key_home,
                "moveEnd": self.key_end,
                "home": self.key_home,
                "end": self.key_end,
                "pageUp": self.key_page_up,
                "pageDown": self.key_page_down,
                
                "left": self.key_left,
                "right": self.key_right,
            }, -2)
            
        self.column_index = 0
        self.row_index = 0
        self.picload = ePicLoad()
        self.picload.setPara((self.iptv_image_width, self.iptv_image_height, 1, 1, False, 1, "#00000000"))
        self.picload_conn = None
                
    def __onClose(self):
        self.picload_conn = None
        
    def onStart(self):
        printDBG('-- ON START --')
        self.onShown.remove(self.onStart)
        self.setMarker()
        self.decodedCallBack()
    
    def decodedCallBack(self, picInfo=None):
        if self.iptv_images_data != None:
            self.picload_conn = None
            self.iptv_images_data.append(self.picload.getData())
        else:
            self.iptv_images_data = []
        
        while len(self.iptv_images_data) < len(self.iptv_images):
            idx = len(self.iptv_images_data)
            self.picload_conn = eConnectCallback(self.picload.PictureData, self.decodedCallBack)
            ret = self.picload.startDecode(self.iptv_images[idx]['path'])
            if ret != 0:
                printDBG('startDecode failed for "%s"' % self.iptv_images[idx]['path'])
                self.picload_conn = None
                self.iptv_images_data.append(None)
            else:
                return
        
        i = 0
        for y in range(self.iptv_row_num):
            for x in range(self.iptv_col_num):
                item = {'pixmap': None, 'id': None, 'width': self.iptv_image_width, 'height': self.iptv_image_height, 'selected': False}
                if i < len(self.iptv_images): 
                    item['id'] = self.iptv_images[i]['id']
                    item['pixmap'] = self.iptv_images_data[i]
                self.iptv_grid[x][y] = item
                i += 1
        
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            item.setList([(x,) for x in self.iptv_grid[i]])
        self.changeColumnSelection()
        
    def changeColumnSelection(self):
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            if i != self.column_index:
                item.instance.setSelectionEnable(0)
            else:
                item.instance.setSelectionEnable(1)
    
    def key_ok(self):
        maxItemsSelected = False
        if self.row_index < self.iptv_row_num:
            try:
                item = self["col_%d" % self.column_index]
                itemContent = item.l.getCurrentSelection()[0]
                if itemContent['id'] == None: # do not allow to select empty cell
                    return
                if itemContent['selected']:
                    self.iptv_num_sel_items -= 1
                else:
                    self.iptv_num_sel_items += 1
                itemContent['selected'] = not itemContent['selected'] 
                item.instance.setSelectionEnable(0)
                item.instance.setSelectionEnable(1)
            except Exception:
                printExc()
            
            if self.iptv_num_sel_items != None and self.iptv_num_sel_items >= self.iptv_max_sel_items:
                maxItemsSelected = True
            else:
                return 
        
        if self.iptv_accep_label != None or maxItemsSelected:
            ret = []
            for y in range(self.iptv_row_num):
                for x in range(self.iptv_col_num):
                    if self.iptv_grid[x][y]['selected']:
                        ret.append(self.iptv_grid[x][y]['id'])
            self.close(ret)
        
    def key_read(self):
        self.close(None)
        
    def key_cancel(self):
        self.close(None)
    
    def key_green(self):
        pass
        
    def setMarker(self, prevIdx=None):
        if self.iptv_accep_label != None:
            if self.row_index == self.iptv_row_num:
                self['accept_button'].instance.setForegroundColor(parseColor("#000000"))
                self['accept_button'].instance.setBackgroundColor(parseColor("#32CD32"))
                for i in range(self.iptv_col_num):
                    item = self["col_%d" % i]
                    item.instance.setSelectionEnable(0)
            else:
                self['accept_button'].instance.setForegroundColor(parseColor("#FFFFFF"))
                self['accept_button'].instance.setBackgroundColor(parseColor("#320F0F0F"))
                self.changeColumnSelection()
                
    def move_list_up(self):
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            if item.instance is not None:
                item.instance.moveSelection(item.instance.moveUp)
    
    def move_list_down(self):
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            if item.instance is not None:
                item.instance.moveSelection(item.instance.moveDown)
                
    def set_list_index(self):
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            if item.instance is not None:
                item.instance.moveSelectionTo(self.row_index)
    
    def key_up(self):
        prev_row_index = self.row_index
        if self.row_index == 0:
            if self.iptv_accep_label != None:
                self.row_index = self.iptv_row_num
            else:
                self.row_index = self.iptv_row_num - 1
        elif self.row_index == self.iptv_row_num:
            self.row_index = self.iptv_row_num - 1
        else:
            self.row_index -= 1
        
        if self.row_index < self.iptv_row_num:
            if prev_row_index == self.iptv_row_num:
                self.setMarker()
                self.set_list_index()
            else:
                self.move_list_up()
        
        if self.iptv_row_num == self.row_index:
            self.setMarker()
        
    def key_down(self):
        prev_row_index = self.row_index
        if self.row_index + 1 == self.iptv_row_num:
            if self.iptv_accep_label != None:
                self.row_index = self.iptv_row_num
            else:
                self.row_index = 0
        elif self.row_index == self.iptv_row_num:
            self.row_index = 0
        else:
            self.row_index += 1
        
        if self.row_index < self.iptv_row_num:
            if prev_row_index == self.iptv_row_num:
                self.setMarker()
                self.set_list_index()
            else:
                self.move_list_down()
        
        if self.iptv_row_num == self.row_index:
            self.setMarker()
    
    def key_home(self):
        pass

    def key_end(self):
        pass
    
    def key_page_up(self):
        pass
    
    def key_page_down(self):
        pass
        
    def key_left(self):
        if self.row_index < self.iptv_row_num:
            if self.column_index == 0:
                self.column_index = self.iptv_col_num - 1
            else:
                self.column_index -= 1
            self.changeColumnSelection()
        
    def key_right(self):
        if self.row_index < self.iptv_row_num:
            if self.column_index == self.iptv_col_num - 1:
                self.column_index = 0
            else:
                self.column_index += 1
            self.changeColumnSelection()
