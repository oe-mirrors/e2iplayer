import os
import sys

sys.path.insert(0, os.path.join("IPTVPlayer", "libs"))

import botprotection as bp  # noqa: E402


def kind(status=403, headers=None, body="", url=""):
    found = bp.detect(status, headers, body, url)
    return (found.name, found.kind) if found else None


def test_cloudflare_challenge_by_header():
    assert kind(403, {"cf-mitigated": "challenge"}) == ("Cloudflare", bp.KIND_CLOUDFLARE)


def test_cloudflare_challenge_by_body():
    assert kind(403, {"Server": "cloudflare"}, "<title>Just a moment...</title>") == ("Cloudflare", bp.KIND_CLOUDFLARE)


def test_cloudflare_bare_403_defaults_to_challenge():
    assert kind(403, {"Server": "cloudflare"}, "") == ("Cloudflare", bp.KIND_CLOUDFLARE)


def test_cloudflare_passive_jsd_script_is_not_a_challenge():
    body = "<h1>Too many requests</h1><script src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'></script>"
    assert kind(429, {}, body) is None
    body = "<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1?ray=1'></script>"
    assert kind(403, {}, body) == ("Cloudflare", bp.KIND_CLOUDFLARE)


def test_cloudflare_waf_block_is_not_solvable():
    body = "<h1>Sorry, you have been blocked</h1> Cloudflare Ray ID: 1"
    assert kind(403, {"Server": "cloudflare"}, body) == ("Cloudflare WAF block", bp.KIND_BLOCK)


def test_ddos_guard_by_server_header():
    assert kind(403, {"Server": "ddos-guard"}) == ("DDoS-Guard", bp.KIND_COOKIE_GATE)


def test_sucuri_js_challenge_vs_block():
    assert kind(403, {}, "<script>sucuri_cloudproxy_js='';</script>") == ("Sucuri", bp.KIND_COOKIE_GATE)
    assert kind(403, {"Server": "Sucuri/Cloudproxy"}, "Access Denied - Sucuri Website Firewall") == ("Sucuri (block)", bp.KIND_BLOCK)


def test_imperva_challenge_and_block():
    assert kind(200, {}, "<script src='/_Incapsula_Resource?SWJIYLWA=1'>") == ("Imperva / Incapsula", bp.KIND_COOKIE_GATE)
    assert kind(403, {"X-Iinfo": "1-2-3"}, "Request unsuccessful. Incapsula incident ID: 1") == ("Imperva / Incapsula (block)", bp.KIND_BLOCK)


def test_anubis():
    body = "<h1>Making sure you're not a bot!</h1> Protected by Anubis from Techaro"
    assert kind(200, {}, body) == ("Anubis", bp.KIND_COOKIE_GATE)
    assert kind(200, {}, "<script src='/.within.website/x/cmd/anubis/static/js/main.mjs'></script>") == ("Anubis", bp.KIND_COOKIE_GATE)


def test_the_word_anubis_alone_is_not_a_bot_check():
    assert kind(200, {}, "<h1>Anubis, the Egyptian god of the dead</h1>") is None
    assert kind(200, {}, "<h1>Making sure you have everything for the trip</h1>") is None


def test_datadome_perimeterx_awswaf_vercel():
    assert kind(403, {"X-DataDome": "protected"}) == ("DataDome", bp.KIND_COOKIE_GATE)
    assert kind(403, {}, "<div id='px-captcha'></div>") == ("PerimeterX / HUMAN", bp.KIND_COOKIE_GATE)
    assert kind(202, {"x-amzn-waf-action": "challenge"}) == ("AWS WAF", bp.KIND_COOKIE_GATE)
    assert kind(429, {"x-vercel-mitigated": "challenge"}) == ("Vercel Security Checkpoint", bp.KIND_COOKIE_GATE)


def test_interactive_captchas_without_mode():
    assert kind(200, {}, "<script src='https://static.geetest.com/gt.js'>")[1] == bp.KIND_CAPTCHA
    assert kind(200, {}, "<div class='frc-captcha'>")[1] == bp.KIND_CAPTCHA


def test_widget_on_blocking_page_is_named():
    assert kind(403, {}, "<script src='https://hcaptcha.com/1/api.js'>") == ("hCaptcha", bp.KIND_CAPTCHA)


def test_hostadmin_waf_before_cloudflare():
    verify = ("<title>Verification...</title><script>window.__WAF_I18N__ = {};</script>"
              "<footer>powered by <a href='https://hostadmin.online'>HostAdmin.online</a></footer>"
              "<script>window.runWafEngine({seed: 'x', rounds: 21});</script>")
    assert kind(200, {"Server": "cloudflare"}, verify) == ("HostAdmin.online WAF", bp.KIND_COOKIE_GATE)
    deny = "<title>Access Denied</title><h2>Access is denied</h2><footer>powered by <a href='https://hostadmin.online'>HostAdmin.online</a></footer>"
    assert kind(403, {"Server": "cloudflare"}, deny) == ("HostAdmin.online WAF", bp.KIND_COOKIE_GATE)
    # a normal page that links the hoster in its footer is not a check page
    assert kind(200, {"Server": "cloudflare"}, "<title>Filme</title><a href='https://hostadmin.online'>Hosting</a>") is None
    # the verification page arrives as HTTP 200 - pCommon must not take it for the site
    assert bp.gate_page_on_success(200, {}, verify).name == "HostAdmin.online WAF"
    assert bp.gate_page_on_success(200, {}, "<div id='px-captcha'></div>") is None  # other gates only on errors
    assert bp.gate_page_on_success(200, {}, "<html>normal</html>") is None


def test_normal_page_is_not_flagged():
    assert bp.detect(200, {"Server": "nginx"}, "<html><body>hello</body></html>") is None
    assert bp.detect() is None


def test_garbage_input_does_not_raise():
    assert bp.detect(403, None, None, None) is None
    assert bp.detect(403, {"a": object()}, 123) is None


def test_solving_user_agent_is_remembered_next_to_the_cookie_file(tmp_path):
    jar = str(tmp_path / "site.cookie")
    assert bp.remembered_user_agent(jar) == ""
    assert bp.remember_user_agent(jar, "Mozilla/5.0 (X11; Linux x86_64) Chrome/153.0.0.0 Safari/537.36")
    assert bp.remembered_user_agent(jar) == "Mozilla/5.0 (X11; Linux x86_64) Chrome/153.0.0.0 Safari/537.36"
    assert bp.remember_user_agent(jar, "Mozilla/5.0 (Windows NT 10.0) Firefox/156.0")  # a later solve replaces it
    assert bp.remembered_user_agent(jar) == "Mozilla/5.0 (Windows NT 10.0) Firefox/156.0"
    other = str(tmp_path / "other.cookie")
    assert bp.remembered_user_agent(other) == ""  # per cookie file (= per site)


def test_user_agent_memory_ignores_nonsense(tmp_path):
    jar = str(tmp_path / "site.cookie")
    assert not bp.remember_user_agent("", "Mozilla/5.0")
    assert not bp.remember_user_agent(jar, "")
    assert not bp.remember_user_agent(jar, "a\nb")
    assert bp.remembered_user_agent("") == ""
    assert not bp.remember_user_agent(str(tmp_path / "missing-dir" / "site.cookie"), "Mozilla/5.0")
    (tmp_path / "site.cookie.ua").write_bytes(b"line one\nline two")
    assert bp.remembered_user_agent(jar) == ""  # a damaged file is not used
