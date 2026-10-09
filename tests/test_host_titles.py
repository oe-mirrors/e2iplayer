# Offline tests for GetHostTitle() in IPTVPlayer/tools/iptvtools.py: the host lists read the title from the
# host file instead of importing the host. Only the reader is taken out of iptvtools.py (it needs no Enigma2),
# then checked against gettytul() of every host, evaluated with ast.
import ast
import glob
import io
import os
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
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith("_HOST_TITLE_") and t.id.endswith("_RE") for t in node.targets):
            wanted.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_HOST_TITLE_CACHE" for t in node.targets):
            wanted.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in ("_readHostTitleFromFile", "GetHostTitle"):
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
