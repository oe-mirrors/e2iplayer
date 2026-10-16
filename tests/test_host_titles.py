# Offline tests for GetHostTitle() in IPTVPlayer/tools/iptvtools.py: the host lists read the title from the
# host file instead of importing the host. Only the reader is taken out of iptvtools.py (it needs no Enigma2),
# then checked against gettytul() of every host, evaluated with ast. Also GetHostInfo() (PlayerSelector info
# line: LAST_MODIFIED, hostxxx version) and the reader for images that install only the .pyc files.
import ast
import glob
import io
import os
import py_compile
import re

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
HOSTS = sorted(glob.glob(os.path.join(ROOT, "hosts", "host*.py")))


def _loadReader():
    path = os.path.join(ROOT, "tools", "iptvtools.py")
    with io.open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    wanted = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith(("_HOST_", "_PYC_")) for t in node.targets):
            wanted.append(node)
        elif isinstance(node, ast.FunctionDef) and (node.name.startswith("_pyc") or node.name in (
                "_readHostTitleFromFile", "GetHostTitle", "_getFileKey", "_formatHostDate", "_readHostInfoFromFile", "_readHostPyc", "GetHostInfo")):
            wanted.append(node)
    module = ast.Module(body=wanted, type_ignores=[])
    namespace = {"re": re, "io": io, "os": os, "ensure_str": str, "_": lambda text: "T(%s)" % text,
                 "printExc": lambda *args: None, "getHostsPath": lambda name: os.path.join(ROOT, "hosts", name)}
    exec(compile(module, path, "exec"), namespace)
    return namespace


TOOLS = _loadReader()
readTitle = TOOLS["_readHostTitleFromFile"]


def _expectedTitle(path):
    # gettytul() of the host: a single return of a string or of _("string")
    with io.open(path, encoding="utf-8", errors="replace") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "gettytul":
            body = node.body
            if len(body) > 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                body = body[1:]  # docstring
            assert len(body) == 1, "gettytul() is not a single return"
            assert isinstance(body[0], ast.Return), "gettytul() is not a single return"
            value = body[0].value
            if isinstance(value, ast.Call) and getattr(value.func, "id", None) == "_" and len(value.args) == 1:
                return "T(%s)" % ast.literal_eval(value.args[0])
            return ast.literal_eval(value)
    raise AssertionError("no gettytul()")


@pytest.mark.parametrize("path", HOSTS, ids=[os.path.basename(p)[4:-3] for p in HOSTS])
def test_title_read_from_file_matches_gettytul(path):
    # every host keeps a fixed gettytul(), so the host lists never have to load it
    assert readTitle(path) == _expectedTitle(path)


def _titleOf(tmp_path, source):
    path = tmp_path / "hostdemo.py"
    path.write_text(source, encoding="utf-8")
    return readTitle(str(path))


def test_fixed_titles(tmp_path):
    assert _titleOf(tmp_path, "def gettytul():\n    return 'https://demo.example/'\n") == "https://demo.example/"
    assert _titleOf(tmp_path, "x = 1\n\n\ndef gettytul():  # address\n\treturn \"XXX\"  # name\n\n\nclass A:\n    pass\n") == "XXX"
    assert _titleOf(tmp_path, "def gettytul():\n    return _('Favorites')\n") == "T(Favorites)"
    assert _titleOf(tmp_path, "def gettytul():\n    # comment\n\n    return 'it\\'s'\n") == "it's"
    assert _titleOf(tmp_path, "def gettytul():\n    \"\"\"Host title.\"\"\"\n    return 'https://demo.example/'\n") == "https://demo.example/"


@pytest.fixture
def getHostTitle(tmp_path, monkeypatch):
    # GetHostTitle() on a hosts folder in tmp_path; imports are recorded instead of done
    imported = []
    titles = {"pyconly": "https://pyc.example/", "dynamic": "https://dyn.example/"}

    def fakeImport(name, *args, **kw):
        if not name.startswith("Plugins.Extensions.IPTVPlayer.hosts.host"):
            return __import__(name, *args, **kw)
        hostName = name.rsplit(".host", 1)[1]
        imported.append(hostName)
        if hostName not in titles:
            raise ImportError(name)
        return type("Module", (), {"gettytul": staticmethod(lambda: titles[hostName])})

    # a module global named __import__ is found before the builtin one
    monkeypatch.setitem(TOOLS, "__import__", fakeImport)
    monkeypatch.setitem(TOOLS, "getHostsPath", lambda name: str(tmp_path / name))
    monkeypatch.setitem(TOOLS, "_HOST_TITLE_CACHE", {})
    monkeypatch.setitem(TOOLS, "_HOST_PYC_CACHE", {})
    return TOOLS["GetHostTitle"], imported


def test_get_host_title_reads_the_file_without_import(tmp_path, getHostTitle):
    get, imported = getHostTitle
    (tmp_path / "hostdemo.py").write_text("def gettytul():\n    return 'https://demo.example/'\n", encoding="utf-8")
    assert get("demo") == "https://demo.example/"
    assert imported == []


def test_get_host_title_imports_pyc_only_and_dynamic_hosts(tmp_path, getHostTitle):
    get, imported = getHostTitle
    (tmp_path / "hostdynamic.py").write_text("def gettytul():\n    return MAIN_URL\n", encoding="utf-8")
    assert get("pyconly") == "https://pyc.example/"  # no .py file: image ships only .pyc
    assert get("dynamic") == "https://dyn.example/"
    assert get("broken") is None
    assert imported == ["pyconly", "dynamic", "broken"]


def test_get_host_title_cache_follows_file_changes(tmp_path, getHostTitle):
    get, imported = getHostTitle
    path = tmp_path / "hostdemo.py"
    path.write_text("def gettytul():\n    return 'https://old.example/'\n", encoding="utf-8")
    assert get("demo") == "https://old.example/"
    path.write_text("def gettytul():\n    return 'https://newer.example/'\n", encoding="utf-8")
    assert get("demo") == "https://newer.example/"  # size changed -> read again
    assert imported == []


def test_dynamic_titles_fall_back_to_the_import(tmp_path):
    # None -> GetHostTitle() imports the host as before
    assert _titleOf(tmp_path, "def gettytul():\n    return MAIN_URL\n") is None
    assert _titleOf(tmp_path, "def gettytul():\n    return 'https://' + DOMAIN\n") is None
    assert _titleOf(tmp_path, "def gettytul():\n    return config.x.value\n") is None
    assert _titleOf(tmp_path, "def gettytul():\n    if X:\n        return 'a'\n    return 'b'\n") is None
    assert _titleOf(tmp_path, "def gettytul():\n    return 'a'\n    print(1)\n") is None
    assert _titleOf(tmp_path, "def gettytul():\n    \"\"\"Doc.\"\"\"\n    \"\"\"Doc.\"\"\"\n    return 'a'\n") is None
    assert _titleOf(tmp_path, "def gettytul():\n    return _('a'\n") is None
    assert _titleOf(tmp_path, "def other():\n    return 'a'\n") is None
    assert _titleOf(tmp_path, "class Host:\n    def gettytul():\n        return 'a'\n") is None


_LAST_MODIFIED_LINE_RE = re.compile(r'^LAST_MODIFIED = "\d\d\.\d\d\.\d{4}"$')


@pytest.mark.parametrize("path", HOSTS, ids=[os.path.basename(p)[4:-3] for p in HOSTS])
def test_host_has_last_modified_code_line(path):
    # the date is code, not a comment: a .pyc keeps it (openATV feed installs only the .pyc files)
    with io.open(path, encoding="utf-8", errors="replace") as f:
        head = [f.readline().rstrip("\r\n") for _ in range(3)]
    assert any(_LAST_MODIFIED_LINE_RE.match(line) for line in head), head
    assert not any(re.match(r"#\s*Last\s*Modified", line, re.IGNORECASE) for line in head), head


def _compile(source, tmp_path, name, keepSource=False):
    # host<name>.pyc next to where the .py would be, like the feed package installs it
    src = tmp_path / ("host%s.py" % name)
    src.write_text(source, encoding="utf-8")
    py_compile.compile(str(src), cfile=str(tmp_path / ("host%s.pyc" % name)), doraise=True)
    if not keepSource:
        src.unlink()
    return str(tmp_path / ("host%s.pyc" % name))


@pytest.mark.parametrize("path", HOSTS, ids=[os.path.basename(p)[4:-3] for p in HOSTS])
def test_pyc_reader_matches_the_py_file(path, tmp_path):
    # what a .pyc-only install shows = what the .py gives
    name = os.path.basename(path)[4:-3]
    pyc = str(tmp_path / ("host%s.pyc" % name))
    py_compile.compile(path, cfile=pyc, doraise=True)
    info = TOOLS["_readHostPyc"](pyc)
    title = readTitle(path)
    if title is None:
        assert "title" not in info
    else:
        assert ("T(%s)" % info["title"] if info["translate"] else info["title"]) == title
    expected = TOOLS["_readHostInfoFromFile"](path, withVersion=True)
    assert info.get("modified") == expected["modified"]
    assert info.get("version") == expected.get("version")
    if name == "xxx":
        assert info["version"]


def test_get_host_title_pyc_only_reads_the_pyc(tmp_path, getHostTitle):
    get, imported = getHostTitle
    _compile("LAST_MODIFIED = \"08.10.2026\"\n\n\ndef gettytul():\n    return 'https://twitch.tv/'\n", tmp_path, "twitch")
    _compile("def gettytul():\n    \"\"\"Doc.\"\"\"\n    return _('Favorites')\n", tmp_path, "fav")
    _compile("MAIN_URL = 'https://x.example/'\n\n\ndef gettytul():\n    return MAIN_URL\n", tmp_path, "dynamic")
    assert get("twitch") == "https://twitch.tv/"
    assert get("fav") == "T(Favorites)"
    assert get("dynamic") == "https://dyn.example/"  # no fixed title in the .pyc -> import
    assert imported == ["dynamic"]


def test_pyc_of_another_python_is_not_read(tmp_path, getHostTitle):
    get, imported = getHostTitle
    pyc = _compile("def gettytul():\n    return 'https://other.example/'\n", tmp_path, "pyconly")
    with open(pyc, "r+b") as f:
        f.write(b"\x00\x00\r\n")  # different magic number
    assert TOOLS["GetHostInfo"]("pyconly") == {}
    assert get("pyconly") == "https://pyc.example/"
    assert imported == ["pyconly"]


def test_get_host_title_prefers_the_py_file(tmp_path, getHostTitle):
    get, imported = getHostTitle
    _compile("def gettytul():\n    return 'https://stale.example/'\n", tmp_path, "demo")
    (tmp_path / "hostdemo.py").write_text("def gettytul():\n    return 'https://demo.example/'\n", encoding="utf-8")
    assert get("demo") == "https://demo.example/"
    assert imported == []


def test_get_host_info(tmp_path, getHostTitle):
    getInfo = TOOLS["GetHostInfo"]
    (tmp_path / "hostdemo.py").write_text("# -*- coding: utf-8 -*-\nLAST_MODIFIED = \"7.10.2026\"\n", encoding="utf-8")
    (tmp_path / "hostold.py").write_text("# -*- coding: utf-8 -*-\n# Last Modified: 05.10.2026\n", encoding="utf-8")
    (tmp_path / "hostiso.py").write_text("#Last Modified 2026-09-03\n", encoding="utf-8")
    (tmp_path / "hostshort.py").write_text("# last modified: 03/09/26\n", encoding="utf-8")
    (tmp_path / "hostnone.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "hostxxx.py").write_text("LAST_MODIFIED = '12.10.2026'\nclass Host:\n\tXXXversion = \"2026.10.12.1\"\n", encoding="utf-8")
    assert getInfo("demo") == {"modified": "07.10.2026"}
    assert getInfo("old") == {"modified": "05.10.2026"}  # hosts from other sources: the old comment
    assert getInfo("iso") == {"modified": "03.09.2026"}
    assert getInfo("short") == {"modified": "03.09.2026"}
    assert getInfo("none") == {}
    assert getInfo("xxx") == {"modified": "12.10.2026", "version": "2026.10.12.1"}
    # .pyc-only install
    _compile("# -*- coding: utf-8 -*-\nLAST_MODIFIED = \"08.10.2026\"\n", tmp_path, "pyconly")
    _compile("# Last Modified: 08.10.2026\n", tmp_path, "pyccomment")
    _compile("LAST_MODIFIED = \"12.10.2026\"\n\n\nclass Host:\n    XXXversion = \"1.2\"\n", tmp_path, "xxxc")
    assert getInfo("pyconly") == {"modified": "08.10.2026"}
    assert getInfo("pyccomment") == {}  # a comment is not in the .pyc
    assert getInfo("xxxc") == {"modified": "12.10.2026", "version": "1.2"}
    assert getInfo("missing") == {}
