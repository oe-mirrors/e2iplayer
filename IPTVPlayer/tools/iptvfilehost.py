# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc

###################################################
# FOREIGN import
###################################################
import codecs


class IPTVFileHost:
    def __init__(self):
        printDBG("IPTVFileHost.__init__")
        self.items = []
        self.groups = []

    def _getGroup(self, title):
        # for now only first group is considered: "[group1][group2] ala" will return "[group1]" and "[group2] ala"
        titleInGroup = ''
        groupTitle = ''
        if 2 < len(title) and '[' == title[0]:
            idx = title.find(']')
            if -1 < idx:
                groupTitle = title[1:idx].strip()
                titleInGroup = title[idx + 1:].strip()
        return groupTitle, titleInGroup

    def addFile(self, filePath, encoding='utf-8', addItemParams={}):
        printDBG('IPTVFileHost.addFile file[%s]' % filePath)
        try:
            with codecs.open(filePath, 'r', encoding, 'replace') as fp:
                lineNum = 0
                while True:
                    lineNum += 1
                    line = fp.readline()
                    if not line:
                        break
                    line = line.strip()
                    if type(line) == type(u''):
                        line = line.encode('utf-8', 'replace')
                    if 0 == len(line) or '#' == line[0]:
                        continue
                    idx1 = line.find(';')
                    if -1 < idx1:
                        fullTitle = line[0:idx1].strip()
                        desc = ''
                        icon = ''
                        idx2 = line.find(';;', idx1 + 1)
                        if -1 < idx2:
                            url = line[idx1 + 1:idx2].strip()
                            idx1 = idx2 + 2
                            idx2 = line.find(';;;', idx1)
                            if -1 < idx2:
                                icon = line[idx1:idx2].strip()
                                desc = line[idx2 + 3:].strip()
                            else:
                                icon = line[idx1:].strip()
                        else:
                            url = line[idx1 + 1:].strip()
                        if '' != fullTitle and url != '':
                            # get group
                            groupTitle, titleInGroup = self._getGroup(fullTitle)
                            if groupTitle not in self.groups:
                                self.groups.append(groupTitle)
                            params = {'full_title': fullTitle, 'url': url, 'icon': icon, 'desc': desc, 'group': groupTitle, 'title_in_group': titleInGroup}
                            params.update(addItemParams)
                            self.items.append(params)
                            continue
                    printDBG('IPTVFileHost.addFile wrong line[%d]' % (lineNum))
        except Exception:
            printExc()

    def getGroups(self, sort=False):
        def _compare(it1, it2):
            name1 = it1.lower()
            name2 = it2.lower()
            if name1 == name2:
                return 0
            elif '' == name2 or name1 < name2:
                return -1
            elif '' == name1 or name1 > name2:
                return 1
        tmpList = list(self.groups)
        if sort:
            tmpList.sort(_compare)
        return tmpList

    def getItemsInGroup(self, group, sort=False):
        tmpList = []

        def _compare(it1, it2):
            name1 = it1['title_in_group'].lower()
            name2 = it2['title_in_group'].lower()
            if name1 < name2:
                return -1
            elif name1 > name2:
                return 1
            else:
                return 0
        for item in self.items:
            if item['group'] == group:
                tmpList.append(item)
        if sort:
            tmpList.sort(_compare)
        return tmpList

    def getAllItems(self, sort=False):
        tmpList = []

        def _compare(it1, it2):
            name1 = it1['full_title'].lower()
            name2 = it2['full_title'].lower()
            if name1 < name2:
                return -1
            elif name1 > name2:
                return 1
            else:
                return 0
        tmpList = list(self.items)
        if sort:
            tmpList.sort(_compare)
        return tmpList
