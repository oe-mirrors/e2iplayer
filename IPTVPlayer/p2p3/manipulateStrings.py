# macro to load functions from correct modules depending on the python version
# some functions copied from six library to support old nbox python - al credits go to it authors.
# build to simplify loading modules in e2iplayer scripts
# just change:
#   from urlib import
# to:
#   from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import 
#
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2

def strDecode(text,  setErrors = 'strict'):
    if isPY2():
        retVal = text
    else: #PY3
        retVal = text.decode(encoding='utf-8', errors=setErrors)
    return retVal

def iterDictItems(myDict):
    if isPY2():
        return myDict.iteritems()
    else:
        return myDict.items()

def iterDictKeys(myDict):
    if isPY2():
        return myDict.iterkeys()
    else: #PY3
        return myDict.keys()

def iterDictValues(myDict):
    if isPY2():
        return myDict.itervalues()
    else: #PY3
        return myDict.values()

def strEncode(text,  encoding = 'utf-8'):
    if isPY2():
        retVal = text
    else: #PY3
        retVal = text.encode(encoding)
    return retVal

def ensure_binary(text, encoding='utf-8', errors='strict'): #based on six library
    if isPY2():
        return text
    else: #PY3
        if isinstance(text, bytes):
          return text
        if isinstance(text, str):
            try:
                return text.encode(encoding, errors)
            except Exception:
                return text.encode(encoding, 'ignore')
    return text

def ensure_str(text, encoding='utf-8', errors='strict'): #based on six library
    if type(text) is str:
        return text
    if isPY2():
        if isinstance(text, unicode):
            try:
                return text.encode(encoding, errors)
            except Exception:
                return text.encode(encoding, 'ignore')
    else: #PY3
        if isinstance(text, bytes):
            try:
                return text.decode(encoding, errors)
            except Exception:
                return text.decode(encoding, 'ignore')
    return text # strwithmeta type defined in e2iplayer goes thorugh it