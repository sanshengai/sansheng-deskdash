"""Calendar fonts retain their sizes and readable CJK glyphs across platforms."""
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

ImageFont = pytest.importorskip("PIL.ImageFont")
Image = pytest.importorskip("PIL.Image")


@pytest.fixture
def collector():
    path = Path(__file__).resolve().parents[1] / "modules/clock-calendar/collector.py"
    spec = importlib.util.spec_from_file_location("clock_calendar_fonts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def installed_fonts(collector):
    try:
        return collector._load_fonts()
    except OSError:
        if sys.platform == "darwin":
            pytest.fail("macOS system CJK fonts must load")
        pytest.skip("No CJK font installed on this test host")


def test_calendar_sizes_and_distinct_chinese_glyphs(collector):
    fonts = installed_fonts(collector)
    assert [font.size for font in fonts] == [36, 22, 30, 30]
    for font in fonts:
        assert collector._has_calendar_glyphs(font)
        signatures = [(font.getmask(char).size, bytes(font.getmask(char))) for char in "年月一二三四五六日"]
        assert len(set(signatures)) == len(signatures)


def test_default_font_with_missing_chinese_is_rejected(collector):
    assert not collector._has_calendar_glyphs(ImageFont.load_default())


def test_empty_glyph_is_rejected(collector):
    class EmptyMask:
        size = (0, 0)
        def __bytes__(self):
            return b""
    class EmptyFont:
        def getmask(self, text):
            return EmptyMask()
    assert not collector._has_calendar_glyphs(EmptyFont())


def test_fallback_skips_unreadable_and_non_chinese_fonts(collector, monkeypatch):
    real = installed_fonts(collector)[0]
    original = ImageFont.truetype
    latin = ImageFont.load_default()
    calls = []
    def fake(path, size, index=0):
        calls.append(path)
        if path == "missing":
            raise OSError("missing")
        if path == "latin":
            return latin
        return original(real.path, size, index=real.index)
    monkeypatch.setattr(collector, "_font_candidates", lambda bold=False: [(name, 0) for name in ["missing", "latin", "cjk"]])
    monkeypatch.setattr(ImageFont, "truetype", fake)
    assert [font.size for font in collector._load_fonts()] == [36, 22, 30, 30]
    assert calls == ["missing", "latin", "cjk"] * 4


def test_missing_fonts_hide_calendar_but_keep_date(collector, monkeypatch, tmp_path):
    monkeypatch.setattr(collector, "_font_candidates", lambda bold=False: [])
    original = collector.render_cal
    monkeypatch.setattr(collector, "render_cal", lambda now, week: original(now, week, str(tmp_path / "calendar.png")))
    result = collector.collect({"show_calendar": True})
    assert result["CalReady"] == 0
    assert result["CalPng"] == ""
    assert result["DateText"] and result["YearMonth"]
    assert not (tmp_path / "calendar.png").exists()


@pytest.mark.parametrize("start", ["monday", "sunday"])
def test_render_calendar_png(collector, tmp_path, start):
    installed_fonts(collector)
    output = tmp_path / "calendar.png"
    assert collector.render_cal(datetime(2026, 9, 12), start, str(output)) == str(output)
    with Image.open(output) as image:
        assert image.size == (700, 516)
        assert image.getbbox() is not None
    assert not (tmp_path / "calendar.png.tmp.png").exists()


def test_windows_font_root_comes_from_environment(collector, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("WINDIR", "X:/CustomWindows")
    assert collector._font_candidates(True)[0][0].replace("\\", "/") == "X:/CustomWindows/Fonts/msyhbd.ttc"


def test_macos_uses_simplified_heiti_faces(collector, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert collector._font_candidates()[0] == ("/System/Library/Fonts/STHeiti Light.ttc", 1)
    assert collector._font_candidates(True)[0] == ("/System/Library/Fonts/STHeiti Medium.ttc", 1)
