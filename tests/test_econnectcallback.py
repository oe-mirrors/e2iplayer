# Offline tests for eConnectCallback / eConnectCallbackObj (IPTVPlayer/tools/iptvtools.py): the three signal
# kinds the images have - plain callback lists (OpenPLi / OpenATV), DreamOS signals with connect() returning a
# connection that ends on deletion, and OpenATV's HbbTV glue (10.2026) whose connect() connection only ends on
# disconnect(). The two definitions are taken from the source, iptvtools itself needs enigma2.
import ast
import gc
import os

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


def _load():
    path = os.path.join(ROOT, "tools", "iptvtools.py")
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    nodes = [n for n in tree.body if getattr(n, "name", "") in ("eConnectCallbackObj", "eConnectCallback")]
    ns = {"printDBG": lambda *a: None, "printExc": lambda *a: None}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), ns)
    return ns["eConnectCallback"]


eConnectCallback = _load()


def cb(*a):
    pass


def test_plain_list_signal():
    signal = []
    conn = eConnectCallback(signal, cb)
    assert signal == [cb]
    del conn
    gc.collect()
    assert signal == []


class _GetSignal(object):
    # OpenATV PSignal wrapper: get() returns the callback list
    def __init__(self):
        self.callbacks = []

    def get(self):
        return self.callbacks


def test_get_list_signal():
    signal = _GetSignal()
    conn = eConnectCallback(signal, cb)
    assert signal.callbacks == [cb]
    del conn
    gc.collect()
    assert signal.callbacks == []


class _HbbTVConnection(object):
    # copy of OpenATV's _HbbTVSignalConnection: leaves the list only on disconnect()
    def __init__(self, callbacks, slot):
        self._callbacks = callbacks
        self._callback = slot
        callbacks.append(slot)

    def disconnect(self):
        if self._callbacks is not None:
            self._callbacks.remove(self._callback)
            self._callbacks = None


class _HbbTVSignal(_GetSignal):
    def connect(self, slot):
        return _HbbTVConnection(self.get(), slot)


def test_openatv_hbbtv_connect_is_disconnected():
    signal = _HbbTVSignal()
    conn = eConnectCallback(signal, cb)
    assert signal.callbacks == [cb]
    del conn
    gc.collect()
    assert signal.callbacks == []


class _DreamConnection(object):
    # DreamOS: the connection ends when the object is deleted
    def __init__(self, owner):
        self.owner = owner
        owner.connected += 1

    def __del__(self):
        self.owner.connected -= 1


class _DreamSignal(object):
    def __init__(self):
        self.connected = 0

    def connect(self, slot):
        return _DreamConnection(self)


def test_dreamos_connection_ends_on_delete():
    signal = _DreamSignal()
    conn = eConnectCallback(signal, cb)
    assert signal.connected == 1
    del conn
    gc.collect()
    assert signal.connected == 0
