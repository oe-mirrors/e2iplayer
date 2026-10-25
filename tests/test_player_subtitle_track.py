# Offline test of IPTVExtMoviePlayer.enableSubtitles (components/iptvextmovieplayer.py): a remembered subtitle file
# that is gone (the download manager put it into the MKV, box log 28.10.) is dropped without an error message.
# The module needs Enigma2, so the method is taken from the source and run on a stand-in player.
import ast
import os
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "IPTVPlayer")


def _method():
    src = open(os.path.join(ROOT, "components", "iptvextmovieplayer.py"), encoding="utf-8").read()
    cls = [n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "IPTVExtMoviePlayer"][0]
    node = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "enableSubtitles"][0]
    ns = {"printDBG": lambda *a: None, "printExc": lambda *a: None, "fileExists": os.path.isfile, "_": lambda t: t,
          "MessageBox": types.SimpleNamespace(TYPE_ERROR=3)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "iptvextmovieplayer.py", "exec"), ns)
    return ns["enableSubtitles"]


class _Meta(object):
    def __init__(self, tracks, idx):
        self.tracks, self.idx = tracks, idx

    def getSubtitleTrack(self):
        return self.tracks[self.idx] if 0 <= self.idx < len(self.tracks) else None

    def getSubtitleIdx(self):
        return self.idx

    def removeSubtitleTrack(self, idx):
        del self.tracks[idx]
        self.idx = -1

    def hasSubtitlesTracks(self):
        return bool(self.tracks)


class _Player(object):
    def __init__(self, tracks, idx, src):
        self.isClosing = False
        self.metaHandler = _Meta(tracks, idx)
        self.subConfig = {"auto_enable": False}
        self.fileSRC = src
        self.messages, self.loaded = [], []
        self.subHandler = {"handler": types.SimpleNamespace(loadSubtitles=lambda path, enc: self.loaded.append(path) or True)}
        self.setMoviePlayerConfig = False

    def showMessage(self, msg, kind):
        self.messages.append(msg)

    def _autoEnableSubtitleFile(self):
        self.searched = True

    def updateSubSynchroControl(self):
        pass


def test_gone_file_is_dropped_quietly(tmp_path):
    enable = _method()
    video = tmp_path / "BBC Elephants Dream.mkv"
    video.write_bytes(b"x")
    # another remembered track does not stop the search next to the video
    other = tmp_path / "other.srt"
    other.write_text("x", encoding="utf-8")
    player = _Player([{"path": str(tmp_path / "BBC Elephants Dream.en.srt"), "title": "en"}, {"path": str(other), "title": "x"}], 0, str(video))
    enable(player)
    assert player.messages == [] and player.loaded == [] and len(player.metaHandler.tracks) == 1
    assert getattr(player, "searched", False)


def test_existing_file_still_loads(tmp_path):
    enable = _method()
    srt = tmp_path / "film.de.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nHallo\n", encoding="utf-8")
    player = _Player([{"path": str(srt), "title": "de"}], 0, str(tmp_path / "film.mkv"))
    enable(player)
    assert player.loaded == [str(srt)] and player.subHandler["enabled"]
