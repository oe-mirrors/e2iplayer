# -*- coding: utf-8 -*-

import sys


def printDBG(strDat):
    print("%s" % strDat)
    #print("%s" % strDat, file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        printDBG('Please provide libsPath and module name')
        sys.exit(1)
    try:
        libsPath = sys.argv[1]
        moduleDir = sys.argv[2]
        moduleName = sys.argv[3]
        sys.path.insert(1, libsPath)
        mod = __import__('%s.%s' % (moduleDir, moduleName), globals(), locals(), [''], -1)
        if hasattr(mod, '__version__'):
            print(mod.__version__)
        else:
            print(mod.version())
        sys.exit(0)
    except Exception as e:
        printDBG(e)
    sys.exit(1)
