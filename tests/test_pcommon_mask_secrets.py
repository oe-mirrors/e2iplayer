# pCommon.maskSecrets(): captcha service credentials (2captcha/9kw key in the URL,
# DeathByCaptcha password in the POST data) never reach the debug log. pCommon itself
# needs enigma2, so only the helper and its two constants are taken out of the source.
import ast
import os
import re

import pytest

SOURCE = os.path.join(os.path.dirname(__file__), "..", "IPTVPlayer", "libs", "pCommon.py")
NAMES = ("_SECRET_FIELDS", "_SECRET_FIELD_RE", "maskSecrets")


@pytest.fixture(scope="module")
def maskSecrets():
    with open(SOURCE, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in NAMES)
             or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in NAMES for t in n.targets))]
    assert len(nodes) == len(NAMES)
    namespace = {"re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), SOURCE, "exec"), namespace)
    return namespace["maskSecrets"]


def test_api_key_in_url(maskSecrets):
    url = "https://2captcha.com/in.php?key=abc123SECRET&method=userrecaptcha&googlekey=6Lc-site&json=1"
    masked = maskSecrets(url)
    assert "abc123SECRET" not in masked
    assert "key=***&method=userrecaptcha" in masked
    # googlekey is the public site key, not a credential
    assert "googlekey=6Lc-site" in masked
    assert maskSecrets("https://www.9kw.eu/index.cgi?apikey=XYZ&action=x") == "https://www.9kw.eu/index.cgi?apikey=***&action=x"


def test_password_in_post_data(maskSecrets):
    post = {"username": "me", "password": "hunter2", "type": "4", "token_params": "{}"}
    masked = maskSecrets(post)
    assert masked == {"username": "me", "password": "***", "type": "4", "token_params": "{}"}
    assert post["password"] == "hunter2"  # the request itself still gets the real data
    assert maskSecrets("username=me&password=hunter2&type=4") == "username=me&password=***&type=4"
    assert maskSecrets(b"username=me&password=hunter2") == "username=me&password=***"


def test_params_dict_with_url(maskSecrets):
    params = {"url": "https://2captcha.com/res.php?key=SECRET&action=get&id=1", "header": {"User-Agent": "x"}}
    masked = maskSecrets(params)
    assert "SECRET" not in str(masked)
    assert masked["header"] == {"User-Agent": "x"}


def test_ordinary_values_unchanged(maskSecrets):
    url = "https://site.example/video?id=5&monkey=1&keyword=abc"
    assert maskSecrets(url) == url
    assert maskSecrets(None) is None
    assert maskSecrets(42) == 42
