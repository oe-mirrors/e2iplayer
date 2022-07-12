#from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
import sys

pyVersion = sys.version_info[0]


def isPY2():
    if pyVersion == 2:
        return True
    else:
        return False


def pVersion():
    return '%s.%s.%s' % (sys.version_info[0], sys.version_info[1], sys.version_info[2])
