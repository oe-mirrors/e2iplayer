# Offline tests for IPTVPlayer/libs/subtitlesmatch.py, the shared helpers of the subtitle providers.
import importlib.util
import os

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
_spec = importlib.util.spec_from_file_location("subtitlesmatch_under_test", os.path.join(ROOT, "libs", "subtitlesmatch.py"))
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)


def test_parse_title():
    assert sm.parseTitle("Breaking Bad S02E05") == ("Breaking Bad", None, 2, 5)
    assert sm.parseTitle("The.Office.2x03.HDTV") == ("The Office", None, 2, 3)
    assert sm.parseTitle("Inception (2010)") == ("Inception", "2010", None, None)
    assert sm.parseTitle("Inception.2010.1080p.BluRay") == ("Inception", "2010", None, None)
    # a number in the title is no year
    assert sm.parseTitle("Blade Runner 2049") == ("Blade Runner 2049", None, None, None)
    assert sm.parseTitle("1917 2019") == ("1917", "2019", None, None)


def test_match_title():
    results = [("Dune", "1984", "old"), ("Dune: Part One", "2021", "new"), ("Dune World", "2021", "x")]
    assert sm.matchTitle("Dune", "2021", results) == "new"
    assert sm.matchTitle("Dune", "1984", results) == "old"
    assert sm.matchTitle("The Fate of the Furious", None, [("Fate of the Furious, The", "2017", 1)]) == 1
    assert sm.matchTitle("Amelie", "2001", [("Amélie", "2001", 7)]) == 7
    # year unknown: the first exact title; an exact title in the wrong year only when it is the only one
    assert sm.matchTitle("Dune", None, [("Dune", "1984", 1), ("Dune", "2000", 2)]) == 1
    assert sm.matchTitle("Dune", "2021", [("Dune", "1984", 1)]) == 1
    assert sm.matchTitle("Dune", "2021", [("Dune", "1984", 1), ("Dune", "2000", 2)]) is None
    assert sm.matchTitle("Nothing", "2020", results) is None


def test_lang_code():
    assert sm.langCode("German") == "de"
    assert sm.langCode("ger") == "de"
    assert sm.langCode("deu") == "de"
    assert sm.langCode("DE") == "de"
    assert sm.langCode("Brazilian Portuguese") == "pt-br"
    assert sm.langCode("Portuguese (Brazil)") == "pt-br"
    assert sm.langCode("Spanish (Latin America)") == "es"
    assert sm.langCode("Klingon") is None
    assert sm.langName("de") == "German"
    assert sm.langIso2("de") == "ger"


def test_episode_fits():
    assert sm.episodeFits("Show.S02E05.720p", 2, 5)
    assert sm.episodeFits("Show 2x05", 2, 5)
    assert not sm.episodeFits("Show.S02E15", 2, 5)
    assert not sm.episodeFits("Show.S12E05", 2, 5)
    assert sm.episodeFits("Show Season 2 Complete", 2, 5)
    assert not sm.episodeFits("Show Season 3 Complete", 2, 5)
    assert sm.episodeFits("anything", None, None)


def test_release_ranking():
    wanted = "Inception.2010.1080p.BluRay.x264-SPARKS.mkv"
    items = [{"title": "Inception.2010.720p.WEB-DL"}, {"title": "Inception.2010.1080p.BluRay.x264-SPARKS"},
             {"title": "Inception.2010.BluRay"}]
    assert [i["title"] for i in sm.sortByRelease(items, wanted)] == [
        "Inception.2010.1080p.BluRay.x264-SPARKS", "Inception.2010.BluRay", "Inception.2010.720p.WEB-DL"]
    # nothing known about the played release: order unchanged
    assert sm.sortByRelease(items, "") == items
    assert sm.downloadRating(0) == "1" and sm.downloadRating(10000) == "10" and sm.downloadRating("x") == "1"
