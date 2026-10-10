# Offline tests for the batch download: IPTVPlayer/iptvdm/batchdownload.py (file name, file extension, skip
# rules, choice of the url, summary text, looking up a row through a host) and its queue side in
# IPTVPlayer/iptvdm/iptvdmapi.py (deferred items, one lookup at a time, ERROR with reason, timeout, summary).
# The enigma2 / E2iPlayer imports are stubbed; strwithmeta, DMHelper and IPTVDMApi are the real ones.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PKG = "Plugins.Extensions.IPTVPlayer"


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Value(object):
    def __init__(self, value):
        self.value = value


class _Timer(object):
    # enigma.eTimer: started / stopped only, the tests call the callbacks themselves
    def __init__(self):
        self.timeout = None
        self.active = False

    def start(self, msec, singleShot=False):
        self.active = True

    def stop(self):
        self.active = False


class RetHost(object):
    OK = "OK"
    ERROR = "ERROR"

    def __init__(self, status, value, message=''):
        self.status = status
        self.value = value
        self.message = message


class CUrlItem(object):
    def __init__(self, name="", url="", urlNeedsResolve=0):
        self.name = name
        self.url = url
        self.urlNeedsResolve = urlNeedsResolve


class CFavItem(object):
    RESOLVER_DIRECT_LINK = 'DIRECT_LINK'
    RESOLVER_SELF = 'SELF'
    RESOLVER_URLLPARSER = 'URLLPARSER'

    def __init__(self, name='', description='', type='', iconimage='', data='', resolver='SELF'):
        self.name = name
        self.type = type
        self.data = data
        self.resolver = resolver
        self.hostName = ''


class IHost(object):
    pass


class _Notify(object):
    def __init__(self):
        self.shown = []

    def showNotify(self, text, status="", statusColor="white"):
        self.shown.append((text, status, statusColor))


class _Downloader(object):
    # what IPTVDMApi.runCMD / cmdFinished use of a downloader
    started = []

    def __init__(self, url):
        self.url = url
        self.fileName = ''
        self.callback = None

    def getName(self):
        return 'wget'

    def subscribeFor_Finish(self, callback):
        self.callback = callback

    def unsubscribeFor_Finish(self, callback):
        self.callback = None

    def start(self, url, fileName, params={}):
        self.fileName = fileName
        # makeUnikalFileName joins with os.sep - "\" when the tests run on Windows
        _Downloader.started.append((str(url), fileName.replace('\\', '/')))

    def getFullFileName(self):
        return self.fileName

    def terminate(self):
        pass

    # updateItemSTS
    def updateStatistic(self):
        pass

    def getLocalFileSize(self):
        return 100

    def getRemoteFileSize(self):
        return 100

    def getDownloadSpeed(self):
        return 0

    def hasDurationInfo(self):
        return False

    def getStatus(self):
        return 'STS_DOWNLOADED'


@pytest.fixture
def env(tmp_path):
    saved = dict(sys.modules)
    state = {'lastHostError': '', 'downloadable': True, 'hosts': {}}
    for pkg in ("Components", "Tools", "Screens", "Plugins", "Plugins.Extensions", PKG, PKG + ".tools", PKG + ".iptvdm",
                PKG + ".components", PKG + ".libs", PKG + ".hosts", PKG + ".p2p3"):
        _stubModule(pkg)
        sys.modules[pkg].__path__ = []
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(ZablokujWMV=_Value(True), IPTVDMBatchPause=_Value("0"))))
    _stubModule("Components.config", config=cfg)
    _stubModule("Tools.Directories", resolveFilename=lambda *a: '', SCOPE_PLUGINS=0, fileExists=os.path.exists)
    _stubModule("Tools.BoundFunction", boundFunction=lambda fnc, *args: (lambda *more: fnc(*(args + more))))
    _stubModule("enigma", eTimer=_Timer)
    _stubModule(PKG + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None, IsExecutable=lambda p: False,
                eConnectCallback=lambda signal, fnc: fnc)
    types_mod = _load(PKG + ".tools.iptvtypes", os.path.join(ROOT, "tools", "iptvtypes.py"))
    strwithmeta = types_mod.strwithmeta

    def getLastHostError(clear=True):
        return state['lastHostError']

    _stubModule(PKG + ".components.iptvplayerinit", TranslateTXT=lambda t: t, GetIPTVPlayerLastHostError=getLastHostError)
    _stubModule(PKG + ".components.ihost", RetHost=RetHost, CUrlItem=CUrlItem, CFavItem=CFavItem, IHost=IHost)
    _stubModule(PKG + ".libs.pCommon", common=types.SimpleNamespace(HOST='UA'))

    def decorateUrl(url, metaParams={}):
        url = strwithmeta(url, dict(getattr(url, 'meta', {})))
        low = url.lower()
        if '.m3u8' in low:
            url.meta['iptv_proto'] = 'm3u8'
        elif low.startswith('https'):
            url.meta['iptv_proto'] = 'https'
        elif low.startswith('http'):
            url.meta['iptv_proto'] = 'http'
        return url

    _stubModule(PKG + ".libs.urlparser", urlparser=types.SimpleNamespace(decorateUrl=staticmethod(decorateUrl)))
    _stubModule(PKG + ".iptvdm.iptvdownloadercreator", IsUrlDownloadable=lambda url: state['downloadable'],
                DownloaderCreator=lambda url, forDownload=False: _Downloader(url))
    _stubModule(PKG + ".iptvdm.downloaderhelpers", ensureText=lambda text: text or u'')
    marked = {}
    _stubModule(PKG + ".tools.iptvdownloaded", markDownloaded=marked.__setitem__)
    asyncQueue = types.SimpleNamespace(procFun=None, processed=0)
    asyncQueue.processQueue = lambda: setattr(asyncQueue, 'processed', asyncQueue.processed + 1)
    _stubModule(PKG + ".components.asynccall", gMainFunctionsQueueTab=[asyncQueue, None])

    iptvdh = _load(PKG + ".iptvdm.iptvdh", os.path.join(ROOT, "iptvdm", "iptvdh.py"))
    batch = _load(PKG + ".iptvdm.batchdownload", os.path.join(ROOT, "iptvdm", "batchdownload.py"))
    dmapi = _load(PKG + ".iptvdm.iptvdmapi", os.path.join(ROOT, "iptvdm", "iptvdmapi.py"))
    _Downloader.started = []
    env = types.SimpleNamespace(batch=batch, dmapi=dmapi, STS=iptvdh.DMHelper.STS, strwithmeta=strwithmeta, decorateUrl=decorateUrl,
                                state=state, marked=marked, asyncQueue=asyncQueue, tmp=str(tmp_path), cfg=cfg)
    yield env
    sys.modules.clear()
    sys.modules.update(saved)


def _addFakeHost(name, links, resolved=None, raiseIn=None, notice=None):
    # hosts/host<name>.py: getLinksForFavourite -> links [(url, needs resolve)], getResolvedURL(url) -> resolved[url]
    resolved = resolved or {}

    class IPTVHost(IHost):
        def getLinksForFavourite(self, favItem):
            IPTVHost.favItem = favItem
            if raiseIn == 'links':
                raise ValueError('site down')
            if notice:
                import threading
                notices = getattr(threading.current_thread(), 'e2iWebNotices', None)
                if notices is not None:
                    notices.append({'screen': 'MessageBox', 'text': notice})
            return RetHost(RetHost.OK, value=[CUrlItem('link %d' % idx, url, 1 if needs else 0) for idx, (url, needs) in enumerate(links)])

        def getResolvedURL(self, url):
            if raiseIn == 'resolve':
                raise ValueError('resolver crashed')
            return RetHost(RetHost.OK, value=[CUrlItem('q', u, 0) for u in resolved.get(url, [])])

    _stubModule(PKG + ".hosts.host" + name, IPTVHost=IPTVHost)
    return IPTVHost


def _source(env, title='Show S01E01', host='fakebatch', itemType='VIDEO'):
    return env.batch.makeBatchSource({'title': title, 'type': itemType, 'source': (host, '{"url": "%s"}' % title)}, '/hdd/movie')


#####################################################################
# pure helpers
#####################################################################
def test_file_title_like_playvideo(env):
    assert env.batch.cleanFileTitle('A/B: C*D?E"F<G>H|I') == 'A-B- C-D-E-F-G-H-I'
    assert env.batch.makeBatchSource({'title': 'Ep 1: Pilot', 'type': 'VIDEO', 'source': ('kinoking', 'x')}, '/hdd/movie')['file'] == '/hdd/movie/Ep 1- Pilot'


def test_file_ext(env):
    url = env.decorateUrl('https://cdn.example/v/file.mkv?token=1')
    assert env.batch.getFileExt(url, 'VIDEO') == '.mkv'
    assert env.batch.getFileExt(env.decorateUrl('https://cdn.example/master.m3u8'), 'VIDEO') == '.mp4'
    assert env.batch.getFileExt(env.decorateUrl('https://cdn.example/stream'), 'AUDIO') == '.mp3'
    url = env.decorateUrl('https://cdn.example/stream')
    url.meta['iptv_format'] = 'ts'
    assert env.batch.getFileExt(url, 'VIDEO') == '.ts'


def test_blocked(env):
    assert env.batch.isUrlBlocked(env.decorateUrl('https://x.example/a.wmv'), 'VIDEO', True)[0]
    assert not env.batch.isUrlBlocked(env.decorateUrl('https://x.example/a.wmv'), 'VIDEO', False)[0]
    assert env.batch.isUrlBlocked(env.decorateUrl('ftpx://x.example/a'), 'VIDEO', False)[0]
    # the setting of the box when not given
    assert env.batch.isUrlBlocked(env.decorateUrl('https://x.example/a.wmv'), 'VIDEO')[0]


def test_live_row(env):
    assert env.batch.isLiveRow({'live': True})
    assert env.batch.isLiveRow({'is_live': True})
    assert not env.batch.isLiveRow({'url': 'x'})
    assert not env.batch.isLiveRow(None)


def test_skip_rules(env):
    rows = [{'title': 'ok 1', 'key': 'h|1', 'source': ('h', 'd')},
            {'title': 'no key', 'key': '', 'source': ('h', 'd')},
            {'title': 'no source', 'key': 'h|2', 'source': None},
            {'title': 'pin', 'key': 'h|3', 'source': ('h', 'd'), 'pin': True},
            {'title': 'live', 'key': 'h|4', 'source': ('h', 'd'), 'live': True},
            {'title': 'queued', 'key': 'h|5', 'source': ('h', 'd')},
            {'title': 'downloaded', 'key': 'h|6', 'source': ('h', 'd')},
            {'title': 'twice', 'key': 'h|1', 'source': ('h', 'd')},
            {'title': 'ok 2', 'key': 'h|7', 'source': ('h', 'd')}]
    accepted, skipped = env.batch.selectBatchRows(rows, {'h|5'}, lambda key: key == 'h|6')
    assert [row['title'] for row in accepted] == ['ok 1', 'ok 2']
    assert skipped == 7


def test_candidates_keep_order_and_skip_bad(env):
    urls = ['', 'file:///media/x.mp4', 'https://cdn.example/best.wmv', 'https://cdn.example/720.mp4', 'https://cdn.example/480.mp4']
    candidates, reason = env.batch.filterCandidates(urls, 'VIDEO', env.decorateUrl, lambda url, t: env.batch.isUrlBlocked(url, t, True))
    assert [str(url) for url in candidates] == ['https://cdn.example/720.mp4', 'https://cdn.example/480.mp4']
    assert candidates[0].meta['iptv_proto'] == 'https'
    candidates, reason = env.batch.filterCandidates(['https://cdn.example/a.wmv'], 'VIDEO', env.decorateUrl, lambda url, t: env.batch.isUrlBlocked(url, t, True))
    assert candidates == [] and 'wmv' in reason


def test_pick_downloadable(env):
    candidates = [env.decorateUrl('https://cdn.example/a.mp4'), env.decorateUrl('https://cdn.example/b.mkv')]
    url, ext, reason = env.batch.pickDownloadable(candidates, 'VIDEO', lambda url: url.endswith('.mkv'))
    assert str(url) == 'https://cdn.example/b.mkv' and ext == '.mkv' and reason == ''
    url, ext, reason = env.batch.pickDownloadable(candidates, 'VIDEO', lambda url: False)
    assert url is None and 'unsupported' in reason


def test_summary(env):
    text, status, colour = env.batch.batchSummary([('A', 'ok'), ('B', 'ok')])
    assert (text, status, colour) == ('2 of 2 downloaded', '', 'green')
    # a row the user took out of the queue is not counted
    text, status, colour = env.batch.batchSummary([('A', 'ok'), ('Bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'failed'), ('C', 'removed')])
    assert text == '1 of 2 downloaded' and colour == 'orange'
    assert status == 'Bbbbbbbbbbbbbbbbbbbbbbbbbbb...'
    assert env.batch.batchSummary([('A', 'ok'), ('C', 'removed')]) == ('1 of 1 downloaded', '', 'green')
    # all of them taken out: no notification at all
    assert env.batch.batchSummary([('A', 'removed'), ('B', 'removed')]) is None
    titles = [('T%d' % idx, 'failed') for idx in range(7)]
    text, status, colour = env.batch.batchSummary(titles)
    assert text == '0 of 7 downloaded' and colour == 'red'
    assert status == 'T0, T1, T2, T3, T4, ...'


#####################################################################
# looking up a row (worker thread side)
#####################################################################
def test_resolve_first_mirror_that_resolves(env):
    host = _addFakeHost('fakebatch', [('https://mirror1.example/e/1', True), ('https://mirror2.example/e/1', True)],
                        {'https://mirror2.example/e/1': ['https://cdn.example/1080.m3u8', 'https://cdn.example/720.m3u8']})
    candidates = env.batch.resolveBatchSource(_source(env), [], blockWmv=True)
    assert [str(url) for url in candidates] == ['https://cdn.example/1080.m3u8', 'https://cdn.example/720.m3u8']
    assert candidates[0].meta['iptv_proto'] == 'm3u8'
    # the favourite data of the row reaches the host like the favourites host passes it
    assert host.favItem.data == '{"url": "Show S01E01"}' and host.favItem.hostName == 'fakebatch'


def test_resolve_direct_link(env):
    _addFakeHost('fakebatch', [('https://cdn.example/direct.mp4', False)])
    candidates = env.batch.resolveBatchSource(_source(env), [], blockWmv=True)
    assert [str(url) for url in candidates] == ['https://cdn.example/direct.mp4']


def test_resolve_no_links_reason(env):
    _addFakeHost('fakebatch', [('https://mirror1.example/e/1', True)])
    with pytest.raises(env.batch.BatchError) as err:
        env.batch.resolveBatchSource(_source(env), [], blockWmv=True)
    assert err.value.args[0] == 'No valid links available.'


def test_resolve_notice_is_reason(env):
    # a captcha / MyE2i question the host wanted to show on the TV
    # (asked in the worker thread: there the question lands in its e2iWebNotices instead of on the TV)
    _addFakeHost('fakebatch', [], notice='Please solve the captcha in MyE2i.\nmore text')
    thread = env.batch.BatchResolveThread(_source(env), 1)
    thread.start()
    thread.join(5)
    assert thread.finished and thread.error == 'Please solve the captcha in MyE2i.'


def test_resolve_host_error(env):
    _addFakeHost('fakebatch', [('https://mirror1.example/e/1', True)], raiseIn='resolve')
    thread = env.batch.BatchResolveThread(_source(env), 1)
    thread.run()
    assert thread.finished and thread.candidates == [] and 'resolver crashed' in thread.error
    # a host error that was there before the lookup is not about this row
    env.state['lastHostError'] = 'old error of the GUI'
    _addFakeHost('fakebatch', [])
    thread = env.batch.BatchResolveThread(_source(env), 1)
    thread.run()
    assert thread.error == 'No valid links available.'


def test_resolve_unknown_host(env):
    thread = env.batch.BatchResolveThread(_source(env, host='doesnotexist'), 1)
    thread.run()
    assert thread.finished and thread.error.startswith('Last Exception error')


def test_thread_runs_in_background(env):
    _addFakeHost('fakebatch', [('https://cdn.example/direct.mp4', False)])
    thread = env.batch.BatchResolveThread(_source(env), 1)
    assert thread.daemon and thread._iptvplayer_ext['terminated'] is False
    thread.start()
    thread.join(5)
    assert thread.finished and [str(url) for url in thread.candidates] == ['https://cdn.example/direct.mp4']


#####################################################################
# download manager side
#####################################################################
class _FakeThread(object):
    # BatchResolveThread stand-in: the test decides when and how it ends
    instances = []

    def __init__(self, source, downloadIdx):
        self.source = source
        self.downloadIdx = downloadIdx
        self.finished = False
        self.candidates = []
        self.error = ''
        self.cancelled = False
        self.age = 0
        _FakeThread.instances.append(self)

    def start(self):
        pass

    def elapsed(self):
        return self.age

    def cancel(self):
        self.cancelled = True


def _dm(env, parallel=1):
    _FakeThread.instances = []
    env.batch.BatchResolveThread = _FakeThread
    notify = _Notify()
    dm = env.dmapi.IPTVDMApi(2, parallel, lambda: notify)
    dm.notify = notify
    dm.runWorkThread()
    return dm


def _batchItems(env, dm, titles):
    items = []
    for title in titles:
        source = _source(env, title)
        item = env.dmapi.DMItem('', source['file'])
        item.batchSource = source
        item.itemKey = 'fakebatch|' + title
        items.append(item)
    return items


def _finishLookup(env, dm, urls=None, error=''):
    thread = _FakeThread.instances[-1]
    thread.candidates = [env.decorateUrl(url) for url in (urls or [])]
    thread.error = error
    thread.finished = True
    dm.pollResolve()
    return thread


def _finishDownload(dm, ok=True):
    item = dm.queueUD[0]
    item.downloader.getLocalFileSize = (lambda: 100) if ok else (lambda: 0)
    dm.cmdFinished(item.downloadIdx)
    return item


def test_batch_items_dedup_by_item_key(env):
    dm = _dm(env)
    assert dm.addBatchToDQueue(_batchItems(env, dm, ['E1', 'E2'])) == 2
    # the same rows again: already in the queue
    assert dm.addBatchToDQueue(_batchItems(env, dm, ['E1', 'E3'])) == 1
    assert [item.batchSource['title'] for item in dm.queueDQ] == ['E1', 'E2', 'E3']
    assert dm.getActiveItemKeys() == {'fakebatch|E1', 'fakebatch|E2', 'fakebatch|E3'}
    # normal items still dedup by their url
    assert dm.addToDQueue(env.dmapi.DMItem(env.decorateUrl('https://cdn.example/x.mp4'), '/hdd/movie/x.mp4'))
    assert not dm.addToDQueue(env.dmapi.DMItem(env.decorateUrl('https://cdn.example/x.mp4'), '/hdd/movie/x2.mp4'))


def test_batch_flow_lookup_download_summary(env):
    dm = _dm(env)
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1', 'E2', 'E3']))
    dm.processDQ()
    # the first item is looked up, it holds the only download slot - nothing else starts
    assert [item.status for item in dm.queueRS] == [env.STS.RESOLVING]
    assert dm.resolveTimer.active and len(_FakeThread.instances) == 1
    dm.processDQ()
    assert len(_FakeThread.instances) == 1 and len(dm.queueDQ) == 2
    # with the E2iPlayer screen closed the download manager works off the main thread queue
    assert env.asyncQueue.processed == 0
    _finishLookup(env, dm, ['https://cdn.example/e1.m3u8'])
    assert env.asyncQueue.processed == 1
    assert not dm.resolveTimer.active and dm.queueRS == []
    # the normal downloader runs with the url and the title as file name + extension
    assert _Downloader.started == [('https://cdn.example/e1.m3u8', '/hdd/movie/E1.mp4')]
    assert dm.queueUD[0].status == env.STS.DOWNLOADING
    _finishDownload(dm)
    assert {key: path.replace('\\', '/') for key, path in env.marked.items()} == {'fakebatch|E1': '/hdd/movie/E1.mp4'}
    # the second fails: ERROR with reason, the queue goes on with the third
    dm.processDQ()
    _finishLookup(env, dm, error='No valid links available.')
    failed = dm.queueAA[-1]
    assert failed.status == env.STS.ERROR and failed.errorReason == 'No valid links available.'
    assert failed.url == '' and dm.needsResolve(failed)
    dm.processDQ()
    _finishLookup(env, dm, ['https://cdn.example/e3.mp4'])
    assert dm.notify.shown[-1][0] != '2 of 3 downloaded'
    _finishDownload(dm)
    # one summary when the last item of the batch has ended (after the notifications of the downloads)
    assert dm.notify.shown[-1] == ('2 of 3 downloaded', 'E2', 'orange')
    assert dm.batches == {}


def test_lookup_without_downloadable_url(env):
    dm = _dm(env)
    env.state['downloadable'] = False
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1']))
    dm.processDQ()
    _finishLookup(env, dm, ['https://cdn.example/e1.mp4'])
    item = dm.queueAA[-1]
    assert item.status == env.STS.ERROR and 'unsupported' in item.errorReason
    assert dm.notify.shown[-1] == ('0 of 1 downloaded', 'E1', 'red')


def test_lookup_timeout(env):
    dm = _dm(env)
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1', 'E2']))
    dm.processDQ()
    thread = _FakeThread.instances[-1]
    thread.age = env.batch.RESOLVE_TIMEOUT - 1
    dm.pollResolve()
    assert dm.queueRS and not thread.cancelled
    thread.age = env.batch.RESOLVE_TIMEOUT + 1
    dm.pollResolve()
    assert thread.cancelled and dm.queueRS == [] and dm.resolveThread is None
    assert dm.queueAA[-1].errorReason == 'Operation timed out.'
    # a late result of the given up thread changes nothing
    thread.finished = True
    dm.pollResolve()
    # the queue goes on
    dm.processDQ()
    assert len(_FakeThread.instances) == 2 and dm.queueRS[0].batchSource['title'] == 'E2'


def test_stop_manager_puts_lookup_back(env):
    dm = _dm(env)
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1', 'E2']))
    dm.processDQ()
    dm.stopWorkThread()
    assert _FakeThread.instances[-1].cancelled
    assert [(item.batchSource['title'], item.status) for item in dm.queueDQ] == [('E1', env.STS.WAITING), ('E2', env.STS.WAITING)]
    assert dm.queueRS == []


def test_stop_lookup_from_list(env):
    dm = _dm(env)
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1']))
    dm.processDQ()
    dm.stopDownloadItem(dm.queueRS[0].downloadIdx)
    assert dm.queueAA[-1].status == env.STS.ERROR and dm.queueAA[-1].errorReason == 'Cancelled.'


def test_retry_failed_lookup(env):
    dm = _dm(env)
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1']))
    dm.processDQ()
    _finishLookup(env, dm, error='Captcha')
    summaries = len(dm.notify.shown)
    item = dm.queueAA[-1]
    dm.retryDownloadItem(item.downloadIdx)
    assert dm.queueDQ == [item] and item.errorReason == ''
    dm.processDQ()
    # looked up again, the file gets a free name like a new download
    assert item.status == env.STS.RESOLVING and item.tries == 'INIT_DOWNLOAD'
    _finishLookup(env, dm, ['https://cdn.example/e1.mp4'])
    assert _Downloader.started[-1] == ('https://cdn.example/e1.mp4', '/hdd/movie/E1.mp4')
    assert len(dm.notify.shown) == summaries


def test_delete_unresolved_never_touches_files(env):
    dm = _dm(env)
    # a file that happens to have exactly the title as name
    title = os.path.join(env.tmp, 'E1')
    open(title, 'w').close()
    item = env.dmapi.DMItem('', title)
    item.batchSource = {'host': 'fakebatch', 'data': '{}', 'type': 'VIDEO', 'title': 'E1', 'file': title}
    item.itemKey = 'fakebatch|E1'
    dm.addBatchToDQueue([item])
    dm.deleteDownloadItem(item.downloadIdx)
    assert os.path.exists(title) and dm.queueDQ == []
    # removed by the user: no summary for a batch nobody waits for any more
    assert dm.notify.shown == [] and dm.batches == {}
    # an ERROR item that never had a url leaves the list without file removal too
    item2 = env.dmapi.DMItem('', title)
    item2.batchSource = dict(item.batchSource)
    item2.itemKey = 'fakebatch|E1b'
    dm.addBatchToDQueue([item2])
    dm.processDQ()
    _finishLookup(env, dm, error='x')
    dm.deleteDownloadItem(item2.downloadIdx)
    assert os.path.exists(title) and dm.queueAA == []
    # the same through "Delete" of the web interface (removeDownloadItem)
    item3 = env.dmapi.DMItem('', title)
    item3.batchSource = dict(item.batchSource)
    item3.itemKey = 'fakebatch|E1c'
    dm.addBatchToDQueue([item3])
    dm.processDQ()
    _finishLookup(env, dm, error='x')
    dm.removeDownloadItem(item3.downloadIdx)
    assert os.path.exists(title) and dm.queueAA == []


def test_retry_after_download_looks_up_again(env):
    # "Download again" of a batch item that had a download: the old url may have expired - the links are
    # looked up again and the file of the first try is written anew (no second "E1 (1).mp4")
    dm = _dm(env)
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1']))
    dm.processDQ()
    _finishLookup(env, dm, ['https://cdn.example/old.mp4'])
    item = _finishDownload(dm, ok=False)
    fileName = item.fileName
    assert item.status == env.STS.ERROR and not dm.hasNoFile(item)
    dm.retryDownloadItem(item.downloadIdx)
    assert item.url == '' and dm.needsResolve(item)
    dm.processDQ()
    assert item.status == env.STS.RESOLVING and item.tries == 'RETRY_DOWNLOAD'
    _finishLookup(env, dm, ['https://cdn.example/new.mkv'])
    assert _Downloader.started[-1] == ('https://cdn.example/new.mkv', fileName.replace('\\', '/'))
    assert item.fileName == fileName
    # a lookup that fails now keeps the file of the first try: "Remove" (with the file) is offered, not "delete"
    _finishDownload(dm, ok=False)
    dm.retryDownloadItem(item.downloadIdx)
    dm.processDQ()
    _finishLookup(env, dm, error='Captcha')
    assert item.status == env.STS.ERROR and item.fileName == fileName and not dm.hasNoFile(item)


def test_list_shows_lookup_between_running_and_waiting(env):
    dm = _dm(env, parallel=2)
    dm.addToDQueue(env.dmapi.DMItem(env.decorateUrl('https://cdn.example/x.mp4'), '/hdd/movie/x.mp4'))
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1', 'E2']))
    dm.processDQ()
    dm.processDQ()
    assert [item.status for item in dm.getList()] == [env.STS.DOWNLOADING, env.STS.RESOLVING, env.STS.WAITING]


def test_batch_pause_left(env):
    pauseLeft = env.batch.batchPauseLeft
    assert pauseLeft(0, 1000.0, "20") == 0          # no lookup of this host yet
    assert pauseLeft(990.0, 1000.0, "20") == 10
    assert pauseLeft(970.0, 1000.0, "20") == 0
    assert pauseLeft(990.0, 1000.0, "0") == 0       # pause off
    assert pauseLeft(990.0, 1000.0, "x") == 0
    assert pauseLeft(1010.0, 1000.0, "20") == 0     # clock went back: no endless wait


def test_batch_pause_between_lookups_of_one_host(env):
    # IPTVDMBatchPause: the next lookup of the same host waits, the timer of the download manager comes again
    env.cfg.plugins.iptvplayer.IPTVDMBatchPause.value = "30"
    dm = _dm(env, parallel=2)
    dm.addBatchToDQueue(_batchItems(env, dm, ['E1', 'E2']))
    dm.processDQ()
    _finishLookup(env, dm, ['https://cdn.example/e1.mp4'])
    dm.processDQ()
    assert len(_FakeThread.instances) == 1 and dm.queueDQ[0].batchSource['title'] == 'E2'
    assert dm.queueDQ[0].status == env.STS.WAITING
    # the pause is over
    host = dm.queueDQ[0].batchSource['host']
    dm.lastBatchLookup[host] -= 31
    dm.processDQ()
    assert len(_FakeThread.instances) == 2 and dm.queueRS[0].batchSource['title'] == 'E2'
