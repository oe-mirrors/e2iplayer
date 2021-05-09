# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import iptv_system, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
###################################################
# FOREIGN import
###################################################
import threading
import traceback
try:
    import ctypes
except Exception:
    pass
###################################################

gMainThreadId = None


def IsMainThread():
    global gMainThreadId
    return gMainThreadId == threading.current_thread()


def SetMainThreadId(mainThreadId=None):
    global gMainThreadId
    if mainThreadId == None:
        gMainThreadId = threading.current_thread()
    else:
        gMainThreadId = mainThreadId


def IsThreadTerminated():
    # this function shall be called only from working thread
    # NOT from main thread
    terminated = True
    try:
        thread = threading.current_thread()
        with thread._iptvplayer_ext['kill_lock']:
            terminated = thread._iptvplayer_ext['terminated']
    except Exception:
        printExc()
    return terminated


def SetThreadKillable(killable):
    # this function shall be called only from working thread
    # NOT from main thread
    terminated = False
    try:
        thread = threading.current_thread()
        with thread._iptvplayer_ext['kill_lock']:
            if not killable:
                thread._iptvplayer_ext['killable'] = killable
            terminated = thread._iptvplayer_ext['terminated']
            thread._iptvplayer_ext['killable'] = killable
    except Exception:
        # This is used to catch exceptions like:
        # thread do not have member _iptvplayer_ext
        printExc()

    if terminated:
        # there was request to terminate this
        # thread as soon as possible
        raise SystemExit(-1)


gMainFunctionsQueueTab = [None, None]


class AsyncCall(object):
    def __init__(self, fnc, callback=None, callbackWithThreadID=False):
        printDBG("AsyncCall.__init__ [%s]---" % fnc.__name__)
        self.Callable = fnc
        self.Callback = callback
        self.CallbackWithThreadID = callbackWithThreadID

        self.mainLock = threading.Lock()
        self.finished = False
        self.Thread = None
        self.exceptStack = ''

    def __del__(self):
        printDBG("AsyncCall.__del__ ---")

    def __call__(self, *args, **kwargs):
        SetIPTVPlayerLastHostError()
        self.Thread = threading.Thread(target=self.run, name=self.Callable.__name__, args=args, kwargs=kwargs)
        self.Thread._iptvplayer_ext = {'kill_lock': threading.Lock(), 'killable': True, 'terminated': False, 'iptv_execute': None}
        self.Thread.start()
        return self

    def isFinished(self):
        return self.finished

    def isAlive(self):
        return None != self.Thread and self.Thread.isAlive()

    def _kill(self):
        bRet = False
        if None != self.Thread:
            try:
                thread_id = None
                # do we have it cached?
                if hasattr(self.Thread, "_thread_id"):
                    thread_id = self.Thread._thread_id

                # no, look for it in the _active dict
                for tid, tobj in threading._active.items():
                    if tobj is self.Thread:
                        thread_id = tid
                if None != thread_id:
                    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), ctypes.py_object(SystemExit))
                    if res == 0:
                        printDBG("AsyncCall._kill *** invalid thread id")
                    elif res != 1:
                        # "if it returns a number greater than one, you're in trouble,
                        # and you should call it again with exc=NULL to revert the effect"
                        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), None)
                        printDBG("AsyncCall._kill *** PyThreadState_SetAsyncExc failed")
                    else:
                        bRet = True
                        printDBG("AsyncCall._kill *** KILL OK")
            except Exception:
                printDBG("AsyncCall._kill *** exception")
        return bRet

    def kill(self):
        bRet = False

        printDBG("THREAD KILL >>>")

        killable = True
        try:
            thread = self.Thread
            if thread:
                with thread._iptvplayer_ext['kill_lock']:
                    killable = thread._iptvplayer_ext['killable']
                    thread._iptvplayer_ext['terminated'] = True
                thread = None
                if not killable:
                    # if thread was marked as not killable then thread will
                    # finish it self, after exist from not killable block
                    return True
        except Exception:
            thread = None
            printExc()

        # we will kill this thread, so we need clear
        # resource which it allocated
        self.mainLock.acquire()

        if self.Thread:
            if self.Thread._iptvplayer_ext['iptv_execute'] != None:
                try:
                    self.Thread._iptvplayer_ext['iptv_execute'].terminate()
                    self.Thread._iptvplayer_ext['iptv_execute'] = None
                except Exception:
                    printExc()

            self.Callback = None
            if self.finished == False:
                if self.Thread.isAlive():
                    self._kill()
                    self.Thread._Thread__stop()
                bRet = True

        self.mainLock.release()

        return bRet

    def getExceptStack(self):
        self.mainLock.acquire()
        exceptStack = self.exceptStack
        self.mainLock.release()
        return exceptStack

    def run(self, *args, **kwargs):
        try:
            result = self.Callable(*args, **kwargs)
        except Exception:
            self.mainLock.acquire()
            self.exceptStack = traceback.format_exc()
            self.mainLock.release()
            printDBG(">> %s" % self.exceptStack)
            return

        self.mainLock.acquire()

        self.finished = True
        if self.Callback:
            if self.CallbackWithThreadID:
                printDBG(">> self[%r] [%r]" % (self, self.CallbackWithThreadID))
                self.Callback(self, result)
            else:
                self.Callback(result)

        self.Thread = None
        self.Callable = None
        self.Callback = None
        self.CallbackWithThreadID = None

        self.mainLock.release()


class AsyncMethod(object):
    def __init__(self, fnc, callback=None, callbackWithThreadID=False):
        printDBG("AsyncMethod.__init__ ---")
        self.Callable = fnc
        self.Callback = callback
        self.CallbackWithThreadID = callbackWithThreadID

    def __del__(self):
        printDBG("AsyncMethod.__del__ ---")

    def __call__(self, *args, **kwargs):
        fnc = self.Callable
        callback = self.Callback
        callbackWithThreadID = self.CallbackWithThreadID
        self.Callable = None
        self.Callback = None
        self.CallbackWithThreadID = None
        return AsyncCall(fnc, callback, callbackWithThreadID)(*args, **kwargs)


class Delegate(object):
    def __init__(self, proxyFunctionQueue, fnc):
        self.function = fnc
        self.proxyQueue = proxyFunctionQueue
        self.event = threading.Event()
        self.returnValues = None

    def __call__(self, *args, **kwargs):
        if self.proxyQueue:
            if self.proxyQueue.mainThreadName != threading.currentThread().getName():
                self.event.clear()

                item = CPQItemDelegate(self.function, args, kwargs, self.finished)
                self.proxyQueue.addItemQueue(item)

                self.event.wait()
                returnValues = self.returnValues
                self.returnValues = None
                return returnValues
            else:
                raise BaseException("Delegate cannot be used in MainThread!")

    def finished(self, *args):
        self.returnValues = args
        self.event.set()

    #def __del__(self):
    #    printDBG("Delegate.__del__ ---")


class DelegateToMainThread(Delegate):
    def __init__(self, fnc, mainThreadIdx=0):
        global gMainFunctionsQueueTab
        Delegate.__init__(self, gMainFunctionsQueueTab[mainThreadIdx], fnc)

    #def __del__(self):
    #    printDBG("DelegateToMainThread.__del__ ---")


class MainSessionWrapper(object):
    '''
    MainSessionWrapper
    can be used only from other thread then MainThread.
    '''
    WAIT_RET = "WaitForFinish"

    def __init__(self, mainThreadIdx=0):
        self.retVal = None
        self.event = threading.Event()
        self.mainThreadIdx = mainThreadIdx

    def open(self, *args, **kwargs):
        DelegateToMainThread(self._open, self.mainThreadIdx)(*args, **kwargs)

    def _open(self, session, *args, **kwargs):
        session.open(*args, **kwargs)

    def waitForFinishOpen(self, *args, **kwargs):
        self.event.clear()
        tmpRet = DelegateToMainThread(self._waitForFinishOpen, self.mainThreadIdx)(*args, **kwargs)
        if tmpRet and tmpRet[0] == MainSessionWrapper.WAIT_RET:
            self.event.wait()
            return self.retVal
        else:
            raise BaseException("DelegateToMainThread Error")

    def _waitForFinishOpen(self, session, *args, **kwargs):
        session.openWithCallback(self._callBack, *args, **kwargs)
        return MainSessionWrapper.WAIT_RET

    def _callBack(self, *args):
        self.retVal = args
        self.event.set()


class iptv_execute(object):
    '''
    Calling os.system is not recommended, it may fail due to lack of memory,
    please use iptv_execute instead, this should be used as follow:
    ret = iptv_execute()("cmd")
    ret['sts'], ret['code'], ret['data']

    iptv_execute must be used outside from MainThread context, please see
    iptv_system class from iptvtools module which is dedicated to be
    used inside MainThread context
    '''
    WAIT_RET = "WaitForFinish"

    def __init__(self, mainThreadIdx=0):
        self.retVal = None
        self.event = threading.Event()
        self.mainThreadIdx = mainThreadIdx
        self.Thread = threading.current_thread()

    def __call__(self, cmd):
        printDBG("iptv_execute.__call__: Here we must not be in main thread context: [%s]" % threading.current_thread())
        self.event.clear()
        tmpRet = DelegateToMainThread(self._system, self.mainThreadIdx)(cmd)
        if tmpRet and tmpRet[0] == iptv_execute.WAIT_RET:
            self.event.wait()
            ret = self.retVal
            self.retVal = None
            return ret
        else:
            return {'sts': False}

    def _system(self, session, cmd):
        printDBG("iptv_execute._system: Here we must be in main thread context: [%s]" % threading.current_thread())

        try:
            terminated = self.Thread._iptvplayer_ext['terminated']
        except Exception:
            printExc()
            terminated = False

        if not terminated and self.Thread.isAlive():
            try:
                self.Thread._iptvplayer_ext['iptv_execute'] = self
            except Exception:
                printExc()
            self.iptv_system = iptv_system(cmd, self._callBack)

            return iptv_execute.WAIT_RET
        return

    def _callBack(self, code, outData):
        printDBG("iptv_execute._callBack: Here we must be in main thread context: [%s]" % threading.current_thread())
        self.iptv_system = None
        self.retVal = {'sts': True, 'code': code, 'data': outData}
        self.event.set()

        try:
            self.Thread._iptvplayer_ext['iptv_execute'] = None
        except Exception:
            printExc()
        self.Thread = None

    def terminate(self):
        printDBG("iptv_execute.terminate: Here we must be in main thread context: [%s]" % threading.current_thread())
        self.iptv_system.kill()
        self._callBack(-1, "terminated")

    #def __del__(self):
    #    printDBG("iptv_execute.__del__ ---")

###############################################################################
#                          Proxy function Queue
#           can be used to run callback function from MainThread
###############################################################################


class CPQItemBase:
    def __init__(self):
        pass


class CPQItemDelegate(CPQItemBase):
    def __init__(self, callFnc, args, kwargs, retFnc):
        CPQItemBase.__init__(self)
        self.callFnc = callFnc
        self.args = args
        self.kwargs = kwargs
        self.retFnc = retFnc


class CPQItemCallBack(CPQItemBase):
    def __init__(self, clientFunName, retValue):
        CPQItemBase.__init__(self)
        self.clientFunName = clientFunName
        self.retValue = retValue


class CPQParamsWrapper:
    def __init__(self, params):
        self.params = params


class CFunctionProxyQueue:
    def __init__(self, session):
        # read/write/change display elements should be done from main thread
        self.session = session
        self.Queue = []
        self.QueueLock = threading.Lock()
        self.mainThreadName = threading.currentThread().getName()
        self.procFun = None

        # this flag will be checked with mutex taken
        # to less lock check
        self.QueueEmpty = True

    ############################################################
    #       This method can be called only from mainThread
    #       so there is no need to synchronize it by mutex
    ############################################################
    def setProcFun(self, fun):
        currThreadName = threading.currentThread().getName()
        if self.mainThreadName != currThreadName:
            printDBG("ERROR CFunctionProxyQueue.registerFunction: thread [%s] is not main thread" % currThreadName)
            raise AssertionError
            return False
        # field self.procFun is accessed only from main thread
        self.procFun = fun
        return True

    def isQueueEmpty(self):
        try:
            if self.QueueEmpty:
                return True
        except Exception:
            pass
        return False

    def clearQueue(self):
        printDBG('clearQueue')
        self.QueueLock.acquire()
        self.Queue = []
        self.QueueEmpty = True
        self.QueueLock.release()

    def addItemQueue(self, item):
        self.QueueLock.acquire()
        self.Queue.append(item)
        self.QueueEmpty = False
        self.QueueLock.release()

    def addToQueue(self, funName, retValue):
        printDBG("addToQueue")
        item = CPQItemCallBack(funName, retValue)
        self.addItemQueue(item)

    def peekClientFunName(self):
        name = None
        if not self.isQueueEmpty():
            self.QueueLock.acquire()
            try:
                item = self.Queue[-1]
                if isinstance(item, CPQItemCallBack):
                    name = str(item.clientFunName)
            except Exception:
                pass
            self.QueueLock.release()
        return name

    def processQueue(self):
       # Queue can be processed only from main thread
        currThreadName = threading.currentThread().getName()
        if self.mainThreadName != currThreadName:
            printDBG("ERROR CFunctionProxyQueue.processQueue: Queue can be processed only from main thread, thread [%s] is not main thread" % currThreadName)
            raise AssertionError, ("ERROR CFunctionProxyQueue.processQueue: Queue can be processed only from main thread, thread [%s] is not main thread" % currThreadName)
            return False

        if self.isQueueEmpty():
            return

        while True:
            QueueIsEmpty = False

            self.QueueLock.acquire()
            if len(self.Queue) > 0:
                #get CPQItemCallBack from mainList
                item = self.Queue.pop(0)
                printDBG("CFunctionProxyQueue.processQueue")
            else:
                QueueIsEmpty = True
            if QueueIsEmpty:
                self.QueueEmpty = True
            self.QueueLock.release()

            if QueueIsEmpty:
                return

            if isinstance(item, CPQItemCallBack) and None != self.procFun:
                self.procFun(item)
            elif isinstance(item, CPQItemDelegate) and hasattr(item.callFnc, '__call__') and hasattr(item.retFnc, '__call__'):
                item.retFnc(item.callFnc(self.session, *item.args, **item.kwargs))
            else:
                printDBG("processQueue WRONG TYPE of proxy queue item")

        # and while True:
        return
