"""The MyE2i texts exist in three places that must not drift apart:

- scripts/mye2iserver.py  DEFAULT_TEXTS: the English texts the server (and, via the server, the extension) uses
- components/recaptcha_mye2i_widget.py  _serverTexts(): the same keys as _("...") literals, so the plugin's
  translation tooling finds them and the plugin can send the translations to the server
- the extension's built-in English fallbacks (solver template, e2iText(...) calls)
"""
import ast
import os
import re
import sys

sys.path.insert(0, os.path.join("IPTVPlayer", "scripts"))

import mye2iserver as server  # noqa: E402

WIDGET = os.path.join("IPTVPlayer", "components", "recaptcha_mye2i_widget.py")
EXTENSION = "mye2i-extension"


def widget_texts():
    tree = ast.parse(open(WIDGET, encoding="utf-8").read())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_serverTexts")
    result = next(n for n in ast.walk(method) if isinstance(n, ast.Return)).value
    assert isinstance(result, ast.Dict)
    texts = {}
    for key, value in zip(result.keys, result.values):
        assert isinstance(value, ast.Call) and value.func.id == "_" and isinstance(value.args[0], ast.Constant), ast.dump(value)[:80]
        texts[key.value] = value.args[0].value
    return texts


def test_widget_sends_exactly_the_keys_and_english_texts_of_the_server():
    texts = widget_texts()
    assert set(texts) == set(server.DEFAULT_TEXTS)
    assert {k: v for k, v in texts.items() if v != server.DEFAULT_TEXTS[k]} == {}


def test_extension_fallback_texts_are_the_english_defaults():
    found = {}
    for name in ("contentscripts/rc2ContentscriptProxy.js", "contentscripts/e2it.js"):
        source = open(os.path.join(EXTENSION, name), encoding="utf-8").read()
        for key, english in re.findall(r"e2iText\('(\w+)',\s*'((?:[^'\\]|\\.)*)'", source):
            found[key] = english.replace("\\'", "'")
    assert found, "no e2iText() calls found"
    for key, english in found.items():
        assert english == server.DEFAULT_TEXTS[key], key


def test_solver_template_english_texts_are_the_defaults():
    template = open(os.path.join(EXTENSION, "res", "browser_solver_template.html"), encoding="utf-8").read()
    for key in ("header_please_solve", "help_whats_happening_header", "help_whats_happening_description", "help_whats_happening_link"):
        match = re.search(r'id="%s">(.*?)</span>' % key, template, re.S)
        assert match, key
        assert " ".join(match.group(1).split()) == server.DEFAULT_TEXTS[key], key


def test_every_solver_text_key_is_a_default():
    assert set(server.SOLVER_TEXT_KEYS) <= set(server.DEFAULT_TEXTS)


def test_translation_lookup_falls_back_to_english_and_survives_broken_format_strings():
    server.TEXTS.clear()
    try:
        assert server.T("pin_wrong") == "Wrong code."
        server.TEXTS["pin_wrong"] = "Falscher Code."
        assert server.T("pin_wrong") == "Falscher Code."
        server.TEXTS["extension_outdated"] = "ohne Platzhalter"
        assert "1.17" in server.T("extension_outdated", "1.17")  # no %s in the translation: English text
        server.TEXTS["extension_outdated"] = "kaputt %d %d"
        assert "1.17" in server.T("extension_outdated", "1.17")  # falls back to the English text
        server.TEXTS["pin_wrong"] = 42  # not a string
        assert server.T("pin_wrong") == "Wrong code."
    finally:
        server.TEXTS.clear()
