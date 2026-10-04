# curl-impersonate backend (IPTVPlayer/libs/curlimpersonate.py + pCommon.getPage(..., {'impersonate': True})
# and the automatic retry in getPageCFProtection). No network, no binary: subprocess.Popen is replaced
# by a fake curl that answers from the command line it gets; pCommon's enigma2 imports are stubbed.
import http.cookiejar
import importlib.util
import json
import os
import sys
import types
from urllib.parse import parse_qs

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PKG = "Plugins.Extensions.IPTVPlayer"


def _module(name, path=None, **attrs):
    mod = types.ModuleType(name)
    if path is not None:
        mod.__path__ = [path]
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeProc(object):
    """what subprocess.Popen returns: stdout = the body, the -D file and stderr (-w line) written at start"""

    def __init__(self, returncode, bodyPath):
        self.returncode = returncode
        self.stdout = open(bodyPath, "rb")
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self):
        return -9 if self.killed else self.returncode

    def kill(self):
        self.killed = True


class FakeCurl(object):
    """answers: callable(args) -> dict(status, headers [(name, value)], body bytes, url, returncode,
    error, redirects [(status, location)], setCookies [cookie file lines])"""

    def __init__(self, tmp_path, answer):
        self.tmp_path = tmp_path
        self.answer = answer
        self.calls = []

    @staticmethod
    def opt(args, name):
        return args[args.index(name) + 1] if name in args else None

    def __call__(self, args, stdin=None, stdout=None, stderr=None, close_fds=False):
        self.calls.append(list(args))
        info = {"post": None}
        data = self.opt(args, "--data-binary")
        if data:
            with open(data[1:], "rb") as f:
                info["post"] = f.read()
        cookieIn = [args[i + 1] for i, a in enumerate(args) if a == "-b"]
        info["cookies"] = []
        for value in cookieIn:
            if os.path.isfile(value):
                with open(value) as f:
                    info["cookies"].append(f.read())
            else:
                info["cookies"].append(value)
        self.calls[-1] = (list(args), info)
        ans = self.answer(args, info)
        url = args[-1]
        hdr = ""
        for status, location in ans.get("redirects", []):
            hdr += "HTTP/2 %d\r\nlocation: %s\r\n\r\n" % (status, location)
        if ans.get("status"):
            hdr += "HTTP/2 %d\r\n" % ans["status"]
            for name, value in ans.get("headers", []):
                hdr += "%s: %s\r\n" % (name, value)
            hdr += "\r\n"
        with open(self.opt(args, "-D"), "w", newline="") as f:
            f.write(hdr)
        if "-c" in args and ans.get("setCookies") is not None:
            with open(self.opt(args, "-c"), "w") as f:
                f.write("# Netscape HTTP Cookie File\n\n" + "".join(line + "\n" for line in ans["setCookies"]))
        err = ans.get("error", "")
        if err:
            err = "curl: " + err + "\n"
        if ans.get("writeout", True) and ans.get("status") is not None:
            err += "\n@@E2I-IMPERSONATE@@ %d %s\n" % (ans.get("status") or 0, ans.get("url", url))
        stderr.write(err.encode())
        stderr.flush()
        bodyPath = str(self.tmp_path / ("body%d" % len(self.calls)))
        with open(bodyPath, "wb") as f:
            f.write(ans.get("body", b""))
        outFile = self.opt(args, "-o")
        if outFile != "-":  # download: curl writes the body (what arrived of it) to the file itself
            with open(outFile, "wb") as f:
                f.write(ans.get("body", b""))
            with open(bodyPath, "wb"):
                pass  # nothing on stdout
        return FakeProc(ans.get("returncode", 0), bodyPath)


@pytest.fixture
def ci(tmp_path, monkeypatch):
    saved = dict(sys.modules)
    module = _load("curlimpersonate_under_test", os.path.join(ROOT, "libs", "curlimpersonate.py"))
    module.resetCache()
    monkeypatch.setattr(module, "CA_BUNDLE", str(tmp_path / "no-ca.crt"))
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _fake(ci, tmp_path, monkeypatch, answer):
    fake = FakeCurl(tmp_path, answer)
    monkeypatch.setattr(ci.subprocess, "Popen", fake)
    return fake


# --- curlimpersonate.py --------------------------------------------------------------------------

def test_filter_headers_drops_browser_headers(ci):
    lines = ci.filterHeaders({"User-Agent": "Firefox", "Accept": "*/*", "accept-language": "de", "Accept-Encoding": "text",
                              "sec-ch-ua": "x", "Sec-CH-UA-Platform": "y", "DNT": 1, "Referer": "https://a.example/",
                              "X-Requested-With": "XMLHttpRequest", "Origin": "https://a.example", "Cookie": "a=1",
                              "Content-Type": "application/json", "Sec-Fetch-Mode": "cors", "Bad": "x\r\nInjected: 1", "Empty": ""})
    assert sorted(lines) == sorted(["Referer: https://a.example/", "X-Requested-With: XMLHttpRequest", "Origin: https://a.example",
                                    "Cookie: a=1", "Content-Type: application/json", "Sec-Fetch-Mode: cors", "Empty;"])


def test_filter_headers_bytes_and_numbers(ci):
    # bytes (e.g. a header built with ensure_binary) are sent as text, not as "b'...'"
    lines = ci.filterHeaders({b"X-Token": b"\xc3\xa4bc", "X-Count": 5})
    assert sorted(lines) == ["X-Count: 5", "X-Token: äbc"]


def test_build_args(ci):
    args = ci.buildArgs("/usr/bin/curl-impersonate", "chrome150", "https://a.example/x?q='\"", {"User-Agent": "u", "Referer": "r"},
                        cookieIn="/tmp/in", cookieOut="/tmp/jar", cookieString="cf=1", dataFile="/tmp/post",
                        timeout=7, proxy="http://p:1", headerFile="/tmp/h")
    assert args[:3] == ["/usr/bin/curl-impersonate", "--impersonate", "chrome150"]
    # the profile asks for gzip/br/zstd - without --compressed curl hands over the encoded bytes (box test:
    # mlblive.net zstd, pinkbike.com gzip -> the host parsed nothing)
    assert "--compressed" in args
    assert args[-2:] == ["--", "https://a.example/x?q='\""]
    assert "-L" in args and args[args.index("--max-redirs") + 1] == "10"
    assert args[args.index("--connect-timeout") + 1] == "7"
    assert args[args.index("-D") + 1] == "/tmp/h"
    assert args[args.index("-o") + 1] == "-"
    assert ["-H", "Referer: r"] == args[args.index("-H"):args.index("-H") + 2]
    assert "User-Agent" not in " ".join(args)  # the User-Agent comes from the profile
    assert [args[i + 1] for i, a in enumerate(args) if a == "-b"] == ["/tmp/in", "cf=1"]
    assert args[args.index("-c") + 1] == "/tmp/jar"
    assert args[args.index("--data-binary") + 1] == "@/tmp/post"
    assert args[args.index("-x") + 1] == "http://p:1"
    assert "-k" not in args and "-4" not in args
    plain = ci.buildArgs("b", "chrome150", "http://a/", noRedirection=True, insecure=True, cacert="/ca", ipv4Only=True, headerFile="h")
    assert "-L" not in plain and "-b" not in plain and "-c" not in plain and "--data-binary" not in plain
    assert "-k" in plain and "--cacert" not in plain and "-4" in plain
    assert ci.buildArgs("b", "p", "http://a/", cacert="/ca", headerFile="h")[-4:-2] == ["--cacert", "/ca"]


def test_build_args_ip_family(ci):
    assert "-6" not in ci.buildArgs("b", "p", "http://a/", headerFile="h")
    v6 = ci.buildArgs("b", "p", "http://a/", ipv6Only=True, headerFile="h")
    assert "-6" in v6 and "-4" not in v6
    both = ci.buildArgs("b", "p", "http://a/", ipv4Only=True, ipv6Only=True, headerFile="h")
    assert "-4" in both and "-6" not in both  # ipv4Only wins


def test_header_file_parsing(ci):
    text = ("HTTP/1.1 100 Continue\r\n\r\nHTTP/2 302\r\nlocation: /next\r\nset-cookie: a=1\r\n\r\n"
            "HTTP/2 301\r\nLocation: https://b.example/final\r\n\r\n"
            "HTTP/2 200\r\nContent-Type: text/html; charset=utf-8\r\nSet-Cookie: x=1\r\nSet-Cookie: y=2\r\n\r\n")
    blocks = ci.parseHeaderFile(text)
    assert [b[0] for b in blocks] == [100, 302, 301, 200]
    status, headers, url = ci.finalResponse(blocks, "https://a.example/start")
    assert status == 200 and url == "https://b.example/final"
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert headers["set-cookie"] == "x=1, y=2"
    assert ci.finalResponse([], "u") == (0, {}, "u")
    code, url, rest = ci.parseWriteOut("curl: (6) Could not resolve host\n\n@@E2I-IMPERSONATE@@ 404 https://a/x y\n")
    assert (code, url, rest) == (404, "https://a/x y", "curl: (6) Could not resolve host")


def test_cookie_file_for_curl(ci, tmp_path):
    # MozillaCookieJar writes a session cookie with an empty expires field - curl drops such lines
    jar = http.cookiejar.MozillaCookieJar()
    jar.set_cookie(http.cookiejar.Cookie(0, "sess", "v", None, False, ".a.example", True, True, "/", True, False, None, True, None, None, {}))
    jar.set_cookie(http.cookiejar.Cookie(0, "perm", "w", None, False, "a.example", False, False, "/", True, True, 4102444800, False, None, None, {"HTTPOnly": ""}))
    src, dst = str(tmp_path / "c.txt"), str(tmp_path / "c.curl")
    jar.save(src, ignore_discard=True)
    assert ci.prepareCookieFile(src, dst)
    lines = open(dst).read().splitlines()
    assert ".a.example\tTRUE\t/\tFALSE\t0\tsess\tv" in lines
    assert "#HttpOnly_a.example\tFALSE\t/\tTRUE\t4102444800\tperm\tw" in lines
    assert not ci.prepareCookieFile(str(tmp_path / "missing"), dst)
    # and what curl writes (#HttpOnly_ prefix, 0 for session cookies) loads back into pCommon's jar
    with open(src, "w") as f:
        f.write("# Netscape HTTP Cookie File\n# https://curl.se/docs/http-cookies.html\n\n"
                "#HttpOnly_.a.example\tTRUE\t/\tTRUE\t0\tcf_clearance\tabc\n"
                "a.example\tFALSE\t/\tFALSE\t4102444800\tperm\tw\n")
    # Python < 3.13.16 (and py2) skip "#HttpOnly_" lines and treat expires 0 as expired
    assert ci.normalizeCookieFile(src)
    assert "#HttpOnly_" not in open(src).read()
    back = http.cookiejar.MozillaCookieJar()
    back.load(src, ignore_discard=True)
    assert sorted((c.name, c.value, c.domain) for c in back) == [("cf_clearance", "abc", ".a.example"), ("perm", "w", "a.example")]


def test_binary_lookup(ci, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert ci.getImpersonateBinary([str(tmp_path / "nope")]) == ""
    ci.resetCache()
    exe = tmp_path / "curl-impersonate"
    exe.write_text("")
    monkeypatch.setattr(ci, "_isExecutable", lambda p: p == str(exe))
    assert ci.getImpersonateBinary(["/usr/bin/curl-impersonate", str(exe)]) == str(exe)
    assert ci.getImpersonateBinary() == str(exe)  # cached
    ci.markBinaryUnusable()
    assert ci.getImpersonateBinary() == ""


def test_fetch_get_with_redirect(ci, tmp_path, monkeypatch):
    fake = _fake(ci, tmp_path, monkeypatch, lambda args, info: {
        "status": 200, "redirects": [(301, "https://a.example/new")], "url": "https://a.example/new",
        "headers": [("content-type", "text/html")], "body": b"<html>ok</html>"})
    res = ci.fetch("/bin/ci", "https://a.example/", str(tmp_path), headers={"Referer": "r"})
    assert res["status"] == 200 and res["url"] == "https://a.example/new" and res["body"] == b"<html>ok</html>"
    assert res["headers"]["content-type"] == "text/html" and res["exitcode"] == 0 and res["profile"] == "chrome150"
    assert len(fake.calls) == 1
    assert os.listdir(str(tmp_path)) == ["body1"]  # header / stderr / temp files removed


def test_fetch_decoded_body_drops_encoding_headers(ci, tmp_path, monkeypatch):
    # curl --compressed already decoded the body: Content-Encoding / the encoded Content-Length must go,
    # else ImpersonateResponse.info() / meta would make a caller gunzip plain HTML a second time
    fake = _fake(ci, tmp_path, monkeypatch, lambda args, info: {
        "status": 200, "headers": [("content-type", "text/html"), ("content-encoding", "zstd"), ("content-length", "4")],
        "body": b"<!DOCTYPE html>"})
    res = ci.fetch("/bin/ci", "https://a.example/", str(tmp_path))
    assert "--compressed" in fake.calls[0][0]
    assert res["body"] == b"<!DOCTYPE html>" and res["headers"] == {"content-type": "text/html"}
    plain = {"content-encoding": "identity", "content-length": "9"}
    assert ci.dropEncodingHeaders(dict(plain)) == plain
    assert ci.dropEncodingHeaders({"content-length": "9"}) == {"content-length": "9"}
    assert ci.dropEncodingHeaders({"content-encoding": "gzip, br", "content-length": "9", "etag": "e"}) == {"etag": "e"}


def test_fetch_unknown_profile_falls_back(ci, tmp_path, monkeypatch):
    def answer(args, info):
        if args[2] in ("chrome150", "chrome146"):
            return {"status": None, "returncode": 2, "error": "option --impersonate: is badly used here"}
        return {"status": 200, "body": b"x"}
    fake = _fake(ci, tmp_path, monkeypatch, answer)
    res = ci.fetch("/bin/ci", "https://a.example/", str(tmp_path))
    assert res["profile"] == "chrome145" and [c[0][2] for c in fake.calls] == ["chrome150", "chrome146", "chrome145"]
    ci.fetch("/bin/ci", "https://a.example/", str(tmp_path))
    assert fake.calls[-1][0][2] == "chrome145"  # remembered


def test_fetch_binary_cannot_run(ci, tmp_path, monkeypatch):
    def popen(*a, **k):
        raise OSError(8, "Exec format error")
    monkeypatch.setattr(ci.subprocess, "Popen", popen)
    with pytest.raises(ci.ImpersonateUnavailable):
        ci.fetch("/bin/ci", "https://a.example/", str(tmp_path))


def test_fetch_max_data_size(ci, tmp_path, monkeypatch):
    fake = _fake(ci, tmp_path, monkeypatch, lambda args, info: {"status": 200, "body": b"0123456789" * 10000, "writeout": False,
                                                                "redirects": [(302, "https://cdn.example/v.mp4")]})
    res = ci.fetch("/bin/ci", "https://a.example/v", str(tmp_path), maxDataSize=0)
    assert res["body"] == b"" and res["status"] == 200 and res["exitcode"] == 0
    assert res["url"] == "https://cdn.example/v.mp4"  # derived from the -D file when -w gave nothing
    res = ci.fetch("/bin/ci", "https://a.example/v", str(tmp_path), maxDataSize=5)
    assert res["body"] == b"01234"
    assert len(fake.calls) == 2


def test_fetch_to_file(ci, tmp_path, monkeypatch):
    fake = _fake(ci, tmp_path, monkeypatch, lambda args, info: {"status": 200, "headers": [("content-type", "image/jpeg")],
                                                                "body": b"\xff\xd8jpegdata"})
    target = str(tmp_path / "cover.jpg")
    res = ci.fetch("/bin/ci", "https://a.example/_pu/1.jpg", str(tmp_path), outFile=target, maxDataSize=3)
    assert res["status"] == 200 and res["body"] == b"" and res["size"] == 10 and res["exitcode"] == 0
    assert fake.calls[0][0][fake.calls[0][0].index("-o") + 1] == target
    with open(target, "rb") as f:
        assert f.read() == b"\xff\xd8jpegdata"  # maxDataSize is not used for files
    args = ci.buildArgs("b", "p", "http://a/", headerFile="h", outFile="/x/f")
    assert args[args.index("-o") + 1] == "/x/f"


# --- pCommon -----------------------------------------------------------------------------------

class _Cfg(object):
    pass


@pytest.fixture
def pc(tmp_path, monkeypatch):
    saved = dict(sys.modules)
    logs = []
    _module("Components", "")
    _module("Components.config", config=_Cfg(), configfile=_Cfg(), ConfigText=object)
    _module("Plugins", "")
    _module("Plugins.Extensions", "")
    _module(PKG, ROOT)
    for sub in ("libs", "p2p3", "tools", "components", "iptvdm"):
        _module(PKG + "." + sub, os.path.join(ROOT, sub))
    _module(PKG + ".iptvdm.iptvdh", DMHelper=types.SimpleNamespace(HANDLED_HTTP_HEADER_PARAMS=["Host", "User-Agent", "Referer", "Cookie", "Accept", "Range"]))
    _module(PKG + ".components.asynccall", iptv_execute=None, IsMainThread=lambda: False, IsThreadTerminated=lambda: False,
            SetThreadKillable=lambda v: None)
    _module(PKG + ".components.iptvplayerinit", GetIPTVNotify=None, TranslateTXT=lambda t: t)
    _module(PKG + ".tools.iptvtools", GetDefaultLang=lambda: "en", GetTmpDir=lambda f="": os.path.join(str(tmp_path), f),
            iptv_system=None, IsExecutable=lambda p: False, IsHttpsCertValidationEnabled=lambda: True,
            printDBG=lambda *a: logs.append(" ".join(str(x) for x in a)), printExc=lambda *a: logs.append("EXC"), rm=os.remove,
            UsePyCurl=lambda: False)
    ci = _load(PKG + ".libs.curlimpersonate", os.path.join(ROOT, "libs", "curlimpersonate.py"))
    ci.resetCache()
    monkeypatch.setattr(ci, "CA_BUNDLE", str(tmp_path / "no-ca.crt"))
    sys.modules[PKG + ".libs"].curlimpersonate = ci
    pcommon = _load(PKG + ".libs.pCommon", os.path.join(ROOT, "libs", "pCommon.py"))
    pcommon.logs = logs
    pcommon.ci = ci
    yield pcommon
    sys.modules.clear()
    sys.modules.update(saved)


def _withBinary(pc, tmp_path, monkeypatch, answer):
    monkeypatch.setattr(pc.ci, "_isExecutable", lambda p: p == "/usr/bin/curl-impersonate")
    return _fake(pc.ci, tmp_path, monkeypatch, answer)


CHALLENGE = b"<html><head><title>Just a moment...</title></head><body>cf-chl</body></html>"


def test_getpage_impersonate_get(pc, tmp_path, monkeypatch):
    fake = _withBinary(pc, tmp_path, monkeypatch, lambda args, info: {
        "status": 200, "headers": [("Content-Type", "application/json; charset=utf-8"), ("X-Foo", "bar")], "body": '{"a": "ä"}'.encode()})
    cm = pc.common()
    sts, data = cm.getPage("https://a.example/api", {"impersonate": True, "with_metadata": True, "collect_all_headers": True,
                                                     "header": {"User-Agent": "Firefox", "Referer": "https://a.example/", "Accept": "*/*"}})
    assert sts is True and json.loads(data) == {"a": "ä"}
    assert data.meta["status_code"] == 200 and data.meta["url"] == "https://a.example/api"
    assert data.meta["content-type"].startswith("application/json") and data.meta["x-foo"] == "bar"
    assert data.meta["impersonate"] == "chrome150"
    args = fake.calls[0][0]
    assert "Referer: https://a.example/" in args and "Firefox" not in " ".join(args) and "Accept: */*" not in args


def test_getpage_impersonate_post_and_cookies(pc, tmp_path, monkeypatch):
    jarPath = str(tmp_path / "site.cookie")
    jar = http.cookiejar.MozillaCookieJar()
    jar.set_cookie(http.cookiejar.Cookie(0, "old", "1", None, False, ".a.example", True, True, "/", True, False, None, True, None, None, {}))
    jar.save(jarPath, ignore_discard=True)
    fake = _withBinary(pc, tmp_path, monkeypatch, lambda args, info: {
        "status": 200, "body": b"ok", "setCookies": ["#HttpOnly_.a.example\tTRUE\t/\tTRUE\t0\tcf_bm\tnew", ".a.example\tTRUE\t/\tFALSE\t0\told\t1"]})
    cm = pc.common()
    params = {"impersonate": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": jarPath,
              "cookie_items": {"extra": "x"}, "header": {"X-Requested-With": "XMLHttpRequest"}}
    sts, data = cm.getPage("https://a.example/login", params, {"user": "me", "password": "secret"})
    assert sts and data == "ok"
    args, info = fake.calls[0]
    assert parse_qs(info["post"].decode()) == {"user": ["me"], "password": ["secret"]}
    assert "\t0\told\t1" in info["cookies"][0]  # the session cookie reaches curl with expires 0
    assert info["cookies"][1] == "extra=x"
    assert args[args.index("-c") + 1] == jarPath
    assert sorted(cm.getCookieItems(jarPath).items()) == [("cf_bm", "new"), ("old", "1")]
    assert not any("secret" in line for line in pc.logs)
    # raw post data goes as is
    cm.getPage("https://a.example/api", {"impersonate": True, "raw_post_data": True, "header": {"Content-Type": "application/json"}}, '{"q": 1}')
    assert fake.calls[1][1]["post"] == b'{"q": 1}' and "-b" not in fake.calls[1][0]


def test_getpage_impersonate_ip_family(pc, tmp_path, monkeypatch):
    fake = _withBinary(pc, tmp_path, monkeypatch, lambda args, info: {"status": 200, "body": b"ok"})
    cm = pc.common()
    cm.getPage("https://a.example/t", {"impersonate": True, "ipv6_only": True})
    cm.getPage("https://a.example/t", {"impersonate": True, "ipv4_only": True})
    cm.getPage("https://a.example/t", {"impersonate": True})
    assert "-6" in fake.calls[0][0] and "-4" not in fake.calls[0][0]
    assert "-4" in fake.calls[1][0] and "-6" not in fake.calls[1][0]
    assert "-4" not in fake.calls[2][0] and "-6" not in fake.calls[2][0]


class _FakeCurlError(Exception):
    pass


class _FakePyCurlSession(object):
    def __init__(self, opts):
        self.opts = opts

    def setopt(self, opt, value):
        self.opts[opt] = value

    def reset(self):
        self.opts.clear()

    def perform(self):
        raise _FakeCurlError(7, "Failed to connect")


def test_pycurl_ip_family(pc, monkeypatch):
    opts = {}
    fake = types.ModuleType("pycurl")
    fake.__getattr__ = lambda name: name  # every constant is its own name
    fake.error = _FakeCurlError
    fake.Curl = lambda: _FakePyCurlSession(opts)
    monkeypatch.setattr(pc, "pycurl", fake, raising=False)
    expected = [({"ipv6_only": True}, "IPRESOLVE_V6"), ({"ipv4_only": True}, "IPRESOLVE_V4"),
                ({"ipv4_only": True, "ipv6_only": True}, "IPRESOLVE_V4"), ({}, "IPRESOLVE_WHATEVER")]
    for params, value in expected:
        cm = pc.common()
        params.update({"header": {"User-Agent": "u"}, "return_data": True})
        sts, _data = cm._getPageWithPyCurl("https://a.example/t", params)
        assert sts is False and opts["IPRESOLVE"] == value
        assert cm.meta["pycurl_error"][0] == 7 and not cm.meta.get("status_code")  # what parserVIDSRC's fallback checks


def test_getpage_impersonate_no_redirection(pc, tmp_path, monkeypatch):
    fake = _withBinary(pc, tmp_path, monkeypatch, lambda args, info: {
        "status": 302, "headers": [("Location", "https://cdn.example/f.mp4")], "body": b""})
    sts, data = pc.common().getPage("https://a.example/go", {"impersonate": True, "no_redirection": True, "with_metadata": True})
    assert sts and data.meta["location"] == "https://cdn.example/f.mp4" and data.meta["status_code"] == 302
    assert "-L" not in fake.calls[0][0]


def test_getpage_impersonate_http_errors(pc, tmp_path, monkeypatch):
    answers = {"/403": {"status": 403, "headers": [("Server", "cloudflare"), ("cf-mitigated", "challenge")], "body": CHALLENGE},
               "/404": {"status": 404, "body": b"not here"},
               "/410": {"status": 410, "body": b"gone"},
               "/dns": {"status": None, "returncode": 6, "error": "(6) Could not resolve host: x"}}
    _withBinary(pc, tmp_path, monkeypatch, lambda args, info: answers["/" + args[-1].rsplit("/", 1)[-1]])
    cm = pc.common()
    sts, data = cm.getPage("https://a.example/403", {"impersonate": True})
    assert sts is False and "Just a moment" in data and data.meta["status_code"] == 403
    assert data.meta["cf-mitigated"] == "challenge" and "Just a moment" in data.meta["body_head"]
    sts, data = cm.getPage("https://a.example/404", {"impersonate": True})
    assert sts is True and data == "not here"  # ignore_http_code_ranges default like urllib / pycurl
    sts, data = cm.getPage("https://a.example/410", {"impersonate": True})
    assert sts is False and data == "gone" and data.meta["status_code"] == 410
    assert cm.getPage("https://a.example/dns", {"impersonate": True}) == (False, None)
    assert cm.meta["curl_error"][0] == 6


def test_getpage_without_binary_uses_normal_path(pc, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    calls = []
    monkeypatch.setattr(pc.common, "getURLRequestData", lambda self, params, post_data=None: calls.append(params) or "normal")
    cm = pc.common()
    assert cm.getPage("https://a.example/", {"impersonate": True}) == (True, "normal")
    assert cm.getPage("https://a.example/", {"impersonate": True}) == (True, "normal")
    assert len(calls) == 2
    assert sum("not installed" in line for line in pc.logs) == 1


def test_getpage_binary_unusable_falls_back(pc, tmp_path, monkeypatch):
    monkeypatch.setattr(pc.ci, "_isExecutable", lambda p: p == "/usr/bin/curl-impersonate")

    def popen(*a, **k):
        raise OSError(8, "Exec format error")
    monkeypatch.setattr(pc.ci.subprocess, "Popen", popen)
    monkeypatch.setattr(pc.common, "getURLRequestData", lambda self, params, post_data=None: "normal")
    cm = pc.common()
    assert cm.getPage("https://a.example/", {"impersonate": True}) == (True, "normal")
    assert pc.ci.getImpersonateBinary() == ""


def _urllibChallenge(pc, monkeypatch, calls):
    # the normal path (urllib) gets the Cloudflare challenge, like getPage's 403 branch returns it
    def normal(self, url, addParams={}, post_data=None):
        calls.append(("normal", url))
        meta = {"status_code": 403, "url": url, "server": "cloudflare", "body_head": CHALLENGE.decode()}
        return False, pc.strwithmeta("Access Forbidden", meta)
    return normal


def test_cfprotection_retries_with_impersonate(pc, tmp_path, monkeypatch):
    calls = []
    normal = _urllibChallenge(pc, monkeypatch, calls)
    orig = pc.common.getPage

    def getPage(self, url, addParams={}, post_data=None):
        if self._useImpersonate(url, addParams):
            calls.append(("impersonate", url))
            return orig(self, url, addParams, post_data)
        return normal(self, url, addParams, post_data)
    monkeypatch.setattr(pc.common, "getPage", getPage)
    fake = _withBinary(pc, tmp_path, monkeypatch, lambda args, info: {"status": 200, "body": b"<html>real page</html>"})
    started = []
    recaptcha = _module(PKG + ".libs.recaptcha_mye2i", UnCaptchaReCaptcha=lambda **k: started.append(1))
    sys.modules[PKG + ".libs"].recaptcha_mye2i = recaptcha
    cm = pc.common()
    sts, data = cm.getPageCFProtection("https://mlb.example/game", {"header": {"User-Agent": "Firefox"}, "cookiefile": str(tmp_path / "c")})
    assert sts and data == "<html>real page</html>" and data.meta["cf_user"] == "Firefox"
    assert calls == [("normal", "https://mlb.example/game"), ("impersonate", "https://mlb.example/game")]
    assert started == []  # MyE2i not needed
    assert "mlb.example" in pc._impersonateDomains
    assert any("retrying with curl-impersonate" in line for line in pc.logs)
    assert any("impersonate: mlb.example passes as Chrome" in line for line in pc.logs)
    # the domain now goes straight through curl-impersonate, also for plain getPage()
    sts, data = cm.getPage("https://mlb.example/next", {})
    assert sts and calls[-1] == ("impersonate", "https://mlb.example/next") and len(fake.calls) == 2
    # ... unless the host switches it off
    cm.getPage("https://mlb.example/next", {"impersonate": False})
    assert calls[-1] == ("normal", "https://mlb.example/next")


def test_cfprotection_impersonate_challenged_too_goes_to_mye2i(pc, tmp_path, monkeypatch):
    calls = []
    normal = _urllibChallenge(pc, monkeypatch, calls)
    orig = pc.common.getPage

    def getPage(self, url, addParams={}, post_data=None):
        if self._useImpersonate(url, addParams):
            calls.append(("impersonate", url))
            return orig(self, url, addParams, post_data)
        return normal(self, url, addParams, post_data)
    monkeypatch.setattr(pc.common, "getPage", getPage)
    _withBinary(pc, tmp_path, monkeypatch, lambda args, info: {
        "status": 403, "headers": [("server", "cloudflare"), ("cf-mitigated", "challenge")], "body": CHALLENGE})

    class Recaptcha(object):
        def __init__(self, **k):
            pass

        def processCaptcha(self, *a, **k):
            calls.append(("mye2i", a[1]))
            return ""
    recaptcha = _module(PKG + ".libs.recaptcha_mye2i", UnCaptchaReCaptcha=Recaptcha)
    sys.modules[PKG + ".libs"].recaptcha_mye2i = recaptcha
    sts, data = pc.common().getPageCFProtection("https://hard.example/", {"cookiefile": str(tmp_path / "c")})
    assert sts is False
    assert calls == [("normal", "https://hard.example/"), ("impersonate", "https://hard.example/"), ("mye2i", "https://hard.example/")]
    assert "hard.example" not in pc._impersonateDomains


def test_cfprotection_no_retry_without_binary_or_when_asked(pc, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    calls = []
    monkeypatch.setattr(pc.common, "getPage", _urllibChallenge(pc, monkeypatch, calls))
    recaptcha = _module(PKG + ".libs.recaptcha_mye2i", UnCaptchaReCaptcha=lambda **k: types.SimpleNamespace(processCaptcha=lambda *a, **k: ""))
    sys.modules[PKG + ".libs"].recaptcha_mye2i = recaptcha
    cm = pc.common()
    cm.getPageCFProtection("https://a.example/", {})
    assert calls == [("normal", "https://a.example/")]
    pc.ci.resetCache()
    monkeypatch.setattr(pc.ci, "_isExecutable", lambda p: True)
    cm.getPageCFProtection("https://a.example/", {"impersonate": False})
    assert len(calls) == 2  # switched off by the host: no retry


# --- file downloads (covers, subtitles) and domain registration ------------------------------------

JPEG = b"\xff\xd8\xff\xe0jpegdata"
ICON_PARAMS = {"check_first_bytes": [b"\xFF\xD8", b"\x89\x50\x4E\x47", b"GIF89a"]}


def _normalPath(pc, monkeypatch):
    calls = []

    def normal(self, params, post_data=None):
        calls.append(params["url"])
        raise pc.URLError("normal path")
    monkeypatch.setattr(pc.common, "getURLRequestData", normal)
    return calls


def test_save_web_file_registered_domain_uses_impersonate(pc, tmp_path, monkeypatch):
    normal = _normalPath(pc, monkeypatch)
    fake = _withBinary(pc, tmp_path, monkeypatch, lambda args, info: {
        "status": 200, "headers": [("Content-Type", "image/jpeg")], "body": JPEG})
    pc._impersonateDomains.add("mlb.example")
    target = str(tmp_path / "cover.jpg")
    cm = pc.common()
    # IconMenager: no host params, a CDN subdomain of the registered site
    ret = cm.saveWebFile(target, "https://img.mlb.example/_pu/1.jpg", dict(ICON_PARAMS))
    assert ret == {"sts": True, "fsize": len(JPEG), "reason": ""}
    with open(target, "rb") as f:
        assert f.read() == JPEG
    args = fake.calls[0][0]
    assert args[args.index("-o") + 1] == target and args[-1] == "https://img.mlb.example/_pu/1.jpg"
    assert cm.meta["status_code"] == 200 and cm.meta["size_download"] == len(JPEG)
    assert normal == []
    assert sorted(f for f in os.listdir(str(tmp_path)) if f.startswith("e2i_imp")) == []  # temp files removed


def test_save_web_file_other_domain_normal_path(pc, tmp_path, monkeypatch):
    normal = _normalPath(pc, monkeypatch)
    fake = _withBinary(pc, tmp_path, monkeypatch, lambda args, info: {"status": 200, "body": JPEG})
    pc._impersonateDomains.add("mlb.example")
    cm = pc.common()
    ret = cm.saveWebFile(str(tmp_path / "c.jpg"), "https://notmlb.example/c.jpg", dict(ICON_PARAMS))
    assert ret["sts"] is False and normal == ["https://notmlb.example/c.jpg"] and fake.calls == []
    ret = cm.saveWebFile(str(tmp_path / "c.jpg"), "https://mlb.example/c.jpg", dict(ICON_PARAMS, impersonate=False))
    assert ret["sts"] is False and len(normal) == 2 and fake.calls == []


def test_save_web_file_failures_remove_the_file(pc, tmp_path, monkeypatch):
    answers = {"404": {"status": 404, "body": b"<html>not found</html>"},
               "html": {"status": 200, "headers": [("Content-Type", "text/html")], "body": b"<html>Just a moment</html>"},
               "partial": {"status": 200, "headers": [("Content-Type", "image/jpeg")], "body": JPEG[:6], "returncode": 18,
                           "error": "(18) transfer closed with 100 bytes remaining to read"},
               "empty": {"status": 200, "body": b""},
               "type": {"status": 200, "headers": [("Content-Type", "text/html")], "body": JPEG}}
    _withBinary(pc, tmp_path, monkeypatch, lambda args, info: answers[args[-1].rsplit("/", 1)[-1]])
    cm = pc.common()
    target = str(tmp_path / "cover.jpg")
    reasons = {}
    for name in ("404", "html", "partial", "empty"):
        ret = cm.saveWebFile(target, "https://a.example/" + name, dict(ICON_PARAMS, impersonate=True))
        assert ret["sts"] is False and ret["fsize"] == 0 and not os.path.exists(target), name
        reasons[name] = ret["reason"]
    assert reasons["404"] == "HTTP 404" and reasons["html"].startswith("not a picture")
    assert reasons["partial"].startswith("curl error (18") and reasons["empty"] == "empty answer"
    ret = cm.saveWebFile(target, "https://a.example/type", {"impersonate": True, "maintype": "image"})
    assert ret["sts"] is False and ret["reason"] == "wrong content-type text/html" and not os.path.exists(target)
    assert "a.example" in pc._impersonateDomains  # the 200 answers registered it (explicit impersonate)


def test_explicit_impersonate_registers_domain_on_success_only(pc, tmp_path, monkeypatch):
    answers = {"/ok": {"status": 200, "body": b"ok"}, "/cf": {"status": 403, "body": CHALLENGE},
               "/dns": {"status": None, "returncode": 6, "error": "(6) Could not resolve host"}}
    _withBinary(pc, tmp_path, monkeypatch, lambda args, info: answers["/" + args[-1].rsplit("/", 1)[-1]])
    cm = pc.common()
    cm.getPage("https://blocked.example/cf", {"impersonate": True})
    cm.getPage("https://gone.example/dns", {"impersonate": True})
    assert pc._impersonateDomains == set()
    assert cm.getPage("https://www.mlb.example/ok", {"impersonate": True}) == (True, "ok")
    assert pc._impersonateDomains == {"mlb.example"}  # stored without www.
    # a registered domain covers itself, www. and subdomains - not look-alikes or the parent zone
    assert cm._useImpersonate("https://mlb.example/_pu/a.jpg", {})
    assert cm._useImpersonate("https://cdn.img.mlb.example/a.jpg", {})
    assert not cm._useImpersonate("https://notmlb.example/a.jpg", {})
    assert not cm._useImpersonate("https://example/a.jpg", {})
    assert not cm._useImpersonate("https://mlb.example.org/a.jpg", {})
    # a registered (not host-asked) request does not register anything new
    cm.getPage("https://sub.mlb.example/ok", {})
    assert pc._impersonateDomains == {"mlb.example"}


def test_getpage_return_data_false_impersonate(pc, tmp_path, monkeypatch):
    answers = {"/v": {"status": 200, "headers": [("Content-Type", "video/mp4"), ("Content-Length", "6")], "body": b"012345",
                      "url": "https://cdn.mlb.example/v.mp4"},
               "/missing": {"status": 404, "body": b"nope"},
               "/cf": {"status": 403, "headers": [("server", "cloudflare")], "body": CHALLENGE}}
    _withBinary(pc, tmp_path, monkeypatch, lambda args, info: answers["/" + args[-1].rsplit("/", 1)[-1]])
    pc._impersonateDomains.add("mlb.example")
    cm = pc.common()
    sts, resp = cm.getPage("https://mlb.example/v", {"return_data": False})
    assert sts is True and resp.geturl() == "https://cdn.mlb.example/v.mp4" and resp.getcode() == 200
    assert resp.info().get("Content-Type") == "video/mp4" and resp.info().get("content-length") == "6"
    assert resp.read(2) == b"01" and resp.read() == b"2345"
    tmpFiles = [f for f in os.listdir(str(tmp_path)) if f.startswith("e2i_impdl_")]
    assert len(tmpFiles) == 1
    resp.close()
    assert [f for f in os.listdir(str(tmp_path)) if f.startswith("e2i_impdl_")] == []
    sts, resp = cm.getPage("https://mlb.example/missing", {"return_data": False})
    assert sts is False and resp.code == 404 and resp.read() == b"nope"  # like urllib's HTTPError
    resp.close()
    sts, data = cm.getPage("https://mlb.example/cf", {"return_data": False})
    assert sts is False and data == "Access Forbidden" and "Just a moment" in data.meta["body_head"]
    assert [f for f in os.listdir(str(tmp_path)) if f.startswith("e2i_impdl_")] == []
