# Offline tests for the chapter parser IPTVPlayer/libs/chapters.py (player infobar/marks/>|/|< and the merge
# downloader's MKV chapters + cuts). The module has no enigma2 / E2iPlayer imports.
import importlib.util
import os

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


def _load():
    spec = importlib.util.spec_from_file_location("chapters_under_test", os.path.join(ROOT, "libs", "chapters.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ch = _load()


def starts(chapters):
    return [(c['start'] // 1000, c['title']) for c in chapters]


def test_plain_list():
    text = "Markus Koch\nIntro text\n\n00:00 Huang als CEO zurück | Aktie explodiert\n04:27 Einordnung und Folgen\n20:45 Ausblick\n1:02:03 Ende\n"
    assert starts(ch.parseChapters(text)) == [(0, 'Huang als CEO zurück | Aktie explodiert'), (267, 'Einordnung und Folgen'),
                                              (1245, 'Ausblick'), (3723, 'Ende')]


def test_two_digit_minutes_not_cut():
    # Kamikaze24's py2 bug: "20:45" became "0:45"
    assert starts(ch.parseChapters("0:00 A\n20:45 B\n25:10 C")) == [(0, 'A'), (1245, 'B'), (1510, 'C')]


def test_separators_and_brackets():
    text = "- 0:00 - Intro\n• 1:00 | Teil 1\n[2:00] Teil 2\n(3:00) Teil 3\n4:00: Teil 4"
    assert starts(ch.parseChapters(text)) == [(0, 'Intro'), (60, 'Teil 1'), (120, 'Teil 2'), (180, 'Teil 3'), (240, 'Teil 4')]


def test_markdown_links():
    text = "[0:00](https://www.youtube.com/watch?v=x&t=0s) Intro\n[5:00](https://www.youtube.com/watch?v=x&t=300s) Main [link](https://a.b/c)"
    assert starts(ch.parseChapters(text)) == [(0, 'Intro'), (300, 'Main link')]


def test_time_last():
    assert starts(ch.parseChapters("Intro 0:00\nMain - 5:00\nOutro (9:30)")) == [(0, 'Intro'), (300, 'Main'), (570, 'Outro')]


def test_time_last_not_mixed_with_time_first():
    text = "0:00 Intro\n3:00 Main\nLive ab 20:15"
    assert starts(ch.parseChapters(text)) == [(0, 'Intro'), (180, 'Main')]


def test_needs_zero_and_two():
    assert ch.parseChapters("1:00 A\n2:00 B") == []
    assert ch.parseChapters("0:00 A") == []
    assert starts(ch.parseChapters("1:00 A\n2:00 B", requireStartAtZero=False)) == [(60, 'A'), (120, 'B')]


def test_second_list_and_falling_times_stop():
    text = "0:00 Intro\n2:00 Teil\n\nEnglish:\n0:00 Intro\n2:00 Part\n1:00 back"
    assert starts(ch.parseChapters(text)) == [(0, 'Intro'), (120, 'Teil')]


def test_short_steps_dropped():
    assert starts(ch.parseChapters("0:00 A\n0:05 too short\n1:00 B")) == [(0, 'A'), (60, 'B')]


def test_lone_zero_earlier_restarts():
    text = "0:00 stray\n\n0:00 Intro\n1:00 Main"
    assert starts(ch.parseChapters(text)) == [(0, 'Intro'), (60, 'Main')]


def test_minutes_over_an_hour_without_hours():
    # "75:30" is 1:15:30 (descriptions without an hour part); minutes over 59 next to hours stay invalid
    assert starts(ch.parseChapters("0:00 A\n59:00 B\n75:30 C")) == [(0, 'A'), (3540, 'B'), (4530, 'C')]
    assert ch.timeToMs('1:75:00') is None
    assert ch.timeToMs('75:30') == 4530000


def test_invalid_times_and_empty_titles():
    assert starts(ch.parseChapters("0:00 A\n1:75 bad\n2:00\n3:00 C")) == [(0, 'A'), (180, 'C')]


def test_bytes_and_empty():
    assert ch.parseChapters(None) == []
    assert ch.parseChapters(b"0:00 A\n1:00 \xc3\x9cber") == [{'start': 0, 'title': 'A'}, {'start': 60000, 'title': '\xdcber'}]


def test_index_and_label():
    chapters = ch.parseChapters("0:00 A\n1:00 B\n1:00:00 C")
    assert ch.chapterIndexAt(chapters, 0) == 0
    assert ch.chapterIndexAt(chapters, 59999) == 0
    assert ch.chapterIndexAt(chapters, 60000) == 1
    assert ch.chapterIndexAt(chapters, 99999999) == 2
    assert ch.chapterLabel(chapters[2]) == '1:00:00 • C'
    assert ch.formatTime(267000) == '4:27'
