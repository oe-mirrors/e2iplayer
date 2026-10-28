# Offline test of the status line parser of the movie player (components/iptvextmovieplayer.py LoadPlayerMessage):
# the module needs Enigma2, so the function is taken from the source
import ast
import json
import os

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "IPTVPlayer")


@pytest.fixture(scope="module")
def load():
    src = open(os.path.join(ROOT, "components", "iptvextmovieplayer.py"), encoding="utf-8").read()
    node = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "LoadPlayerMessage"][0]
    ns = {"json": json}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "iptvextmovieplayer.py", "exec"), ns)
    return ns["LoadPlayerMessage"]


# exteplayer3 cut its PLAYBACK_OPEN of a long Pluto TV url and put it in front of every later message (box log 28.10.)
CUT = '{"PLAYBACK_OPEN":{"OutputName":"Output", "file":"https://stitcher.pluto.tv/v2/stitch/hls/channel/x/playlist.m3u8?jwt=' + 'eyJhbGciOi' * 200


def test_plain_messages(load):
    assert load('{"PLAYBACK_PLAY":{"sts":0}}') == {"PLAYBACK_PLAY": {"sts": 0}}
    assert load('{"v_c":{"id":1,"e":"V_MPEG4/ISO/AVC","w":1216}}') == {"v_c": {"id": 1, "e": "V_MPEG4/ISO/AVC", "w": 1216}}


def test_message_behind_a_cut_playback_open(load):
    assert load(CUT + '{"PLAYBACK_PLAY":{"sts":0}}') == {"PLAYBACK_PLAY": {"sts": 0}}
    # a nested message: the outer one, not its inner object
    assert load(CUT + '{"v_c":{"id":1,"e":"V_MPEG4/ISO/AVC","n":"und"}}') == {"v_c": {"id": 1, "e": "V_MPEG4/ISO/AVC", "n": "und"}}
    assert load(CUT + '{"a_l": [{"id":0,"e":"A_AAC","n":"und"}]}') == {"a_l": [{"id": 0, "e": "A_AAC", "n": "und"}]}


def test_broken_line_still_fails(load):
    with pytest.raises(ValueError):
        load(CUT)
