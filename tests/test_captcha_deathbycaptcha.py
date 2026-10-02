# Offline tests for IPTVPlayer/libs/captcha_deathbycaptcha.py: the enigma2 / E2iPlayer imports are
# stubbed, the API answers are hand-made JSON strings following deathbycaptcha.com/api, no network.
import importlib.util
import json
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class _Value(object):
    def __init__(self, value):
        self.value = value


class _Sleep(object):
    def __init__(self):
        self.left = 0

    def Sleep(self, timeout, blocking=True):
        self.left = timeout

    def getTimeout(self):
        return self.left

    def Reset(self):
        self.left = 0


class _Meta(str):
    pass


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


@pytest.fixture
def dbc():
    saved = dict(sys.modules)
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(
        deathbycaptcha_login=_Value("user"), deathbycaptcha_password=_Value("secret"))))
    for pkg in ("Components", "Screens", "Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer",
                "Plugins.Extensions.IPTVPlayer.libs", "Plugins.Extensions.IPTVPlayer.components", "Plugins.Extensions.IPTVPlayer.tools"):
        _stubModule(pkg)
    sleepObj = _Sleep()
    _stubModule("Components.config", config=cfg)
    _stubModule("Screens.MessageBox", MessageBox=types.SimpleNamespace(TYPE_ERROR=3))
    _stubModule("Plugins.Extensions.IPTVPlayer.components.iptvplayerinit", TranslateTXT=lambda t: t, GetIPTVSleep=lambda: sleepObj)
    _stubModule("Plugins.Extensions.IPTVPlayer.components.asynccall", MainSessionWrapper=lambda: None)
    _stubModule("Plugins.Extensions.IPTVPlayer.libs.e2ijson", loads=json.loads, dumps=json.dumps)
    _stubModule("Plugins.Extensions.IPTVPlayer.libs.pCommon", common=lambda: None)
    _stubModule("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None)
    spec = importlib.util.spec_from_file_location("dbc_under_test", os.path.join(ROOT, "libs", "captcha_deathbycaptcha.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.time = types.SimpleNamespace(sleep=lambda s: None)
    module.cfg = cfg.plugins.iptvplayer
    module.sleepObj = sleepObj
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _solver(dbc, answers):
    # answers: list of (sts, data) returned by getPage one after the other; the requests are recorded
    solver = dbc.UnCaptchaReCaptcha()
    solver.requests = []
    solver.messages = []

    def getPage(url, params, postData=None):
        solver.requests.append((url, params, postData))
        if answers:
            return answers.pop(0)
        dbc.sleepObj.left = 0  # no more answers: let the poll loop time out
        return False, None
    solver.cm = types.SimpleNamespace(getPage=getPage)
    solver.sessionEx = types.SimpleNamespace(waitForFinishOpen=lambda *a, **k: solver.messages.append(a[1]))
    return solver


def test_build_task_types(dbc):
    assert dbc.buildTask("k", "https://s/p") == (4, "token_params", {"googlekey": "k", "pageurl": "https://s/p"})
    assert dbc.buildTask("k", "https://s/p", "", "login") == (5, "token_params", {"googlekey": "k", "pageurl": "https://s/p", "action": "login", "min_score": 0.3})
    assert dbc.buildTask("k", "https://s/p", "ENTERPRISE") == (25, "token_enterprise_params", {"googlekey": "k", "pageurl": "https://s/p"})
    assert dbc.buildTask("0x4", "https://s/p", "cf_re") == (12, "turnstile_params", {"sitekey": "0x4", "pageurl": "https://s/p"})
    assert dbc.buildTask("0x4", "https://s/p", "cf_re", "act")[2]["action"] == "act"
    for unsupported in ("h1", "h1_invisible", "CF", "COOKIES"):
        assert dbc.buildTask("k", "https://s/p", unsupported) is None


def test_parse_answer(dbc):
    assert dbc.parseAnswer('{"captcha": 1234, "is_correct": true, "status": 0, "text": "TOKEN"}') == (1234, "TOKEN", "")
    assert dbc.parseAnswer('{"captcha": 1234, "is_correct": true, "status": 0, "text": ""}') == (1234, "", "")
    assert dbc.parseAnswer('{"captcha": 1234, "is_correct": false, "status": 0, "text": ""}')[2]
    assert dbc.parseAnswer('{"error": "not-logged-in", "status": 255}') == (0, "", "Login or password is wrong.")
    assert dbc.parseAnswer('{"error": "insufficient-funds", "status": 255}')[2] == "The balance of the account is too low."
    assert dbc.parseAnswer('{"error": "something-new", "status": 255}')[2] == "something-new"
    assert dbc.parseAnswer("<html>")[2]
    # an empty answer is no error by itself: the upload reports the missing id, polling just goes on
    assert dbc.parseAnswer("") == (0, "", "")


def test_solve_with_polling(dbc):
    solver = _solver(dbc, [
        (True, '{"captcha": 77, "is_correct": true, "status": 0, "text": ""}'),
        (True, '{"captcha": 77, "is_correct": true, "status": 0, "text": ""}'),
        (True, '{"captcha": 77, "is_correct": true, "status": 0, "text": "TOKEN"}'),
    ])
    assert solver.processCaptcha("k", "https://s/p") == "TOKEN"
    url, params, post = solver.requests[0]
    assert url == "https://api.dbcapi.me/api/captcha"
    assert params["header"]["Accept"] == "application/json"
    assert post["username"] == "user" and post["password"] == "secret" and post["type"] == "4"
    assert json.loads(post["token_params"]) == {"googlekey": "k", "pageurl": "https://s/p"}
    assert [r[0] for r in solver.requests[1:]] == ["https://api.dbcapi.me/api/captcha/77"] * 2
    assert all(r[2] is None for r in solver.requests[1:])
    assert solver.messages == [] and dbc.sleepObj.left == 0


def test_turnstile_is_sent_as_type_12(dbc):
    solver = _solver(dbc, [(True, '{"captcha": 5, "is_correct": true, "status": 0, "text": "CF"}')])
    assert solver.processCaptcha("0x4", "https://s/p", "cf_re", "act") == "CF"
    post = solver.requests[0][2]
    assert post["type"] == "12" and json.loads(post["turnstile_params"]) == {"sitekey": "0x4", "pageurl": "https://s/p", "action": "act"}


def test_login_error_from_403_body_without_pycurl(dbc):
    # urllib path: sts False, the text is "Access Forbidden" and the JSON body sits in meta['body_head']
    page = _Meta("Access Forbidden")
    page.meta = {"status_code": 403, "body_head": '{"error": "not-logged-in", "status": 255}'}
    solver = _solver(dbc, [(False, page)])
    assert solver.processCaptcha("k", "https://s/p") == ""
    assert len(solver.requests) == 1
    assert "Login or password is wrong." in solver.messages[0]


def test_failed_solution_stops_polling(dbc):
    solver = _solver(dbc, [
        (True, '{"captcha": 9, "is_correct": true, "status": 0, "text": ""}'),
        (True, '{"captcha": 9, "is_correct": false, "status": 0, "text": ""}'),
    ])
    assert solver.processCaptcha("k", "https://s/p") == ""
    assert len(solver.requests) == 2
    assert "could not solve the captcha" in solver.messages[0]


def test_timeout(dbc):
    solver = _solver(dbc, [(True, '{"captcha": 9, "is_correct": true, "status": 0, "text": ""}')])
    assert solver.processCaptcha("k", "https://s/p") == ""
    assert "timeout" in solver.messages[0]


def test_no_request_without_login_or_for_hcaptcha(dbc):
    solver = _solver(dbc, [])
    assert solver.processCaptcha("k", "https://s/p", "h1") == ""
    assert solver.requests == [] and "cannot solve this type of captcha" in solver.messages[0]
    dbc.cfg.deathbycaptcha_password.value = ""
    solver = _solver(dbc, [])
    assert solver.processCaptcha("k", "https://s/p") == ""
    assert solver.requests == [] and "login and password" in solver.messages[0]
