"""Golden tests for schedule resolution semantics (owner spec, schema v3).

Run: python -m pytest tests
"""

import dataclasses
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import schedule
from core import settings as sm

TZ = ZoneInfo("Europe/Belgrade")
BASE = sm.load(Path(__file__).parent.parent / "config.json")


def _cfg(ptype: str, **sections) -> sm.Settings:
    preset = sm.Preset(name="test", type=ptype,
                       hours=sections.get("hours", []),
                       weekdays=sections.get("weekdays", {}),
                       monthdays=sections.get("monthdays", []),
                       months=sections.get("months", {}),
                       daylight=sections.get("daylight", {}))
    return dataclasses.replace(BASE, presets=[preset], active_preset="test")


HOURS = [
    {"from": 3, "to": 6, "color": "blue"}, {"from": 6, "to": 9, "color": "cyan"},
    {"from": 9, "to": 12, "color": "green"}, {"from": 12, "to": 15, "color": "yellow"},
    {"from": 15, "to": 18, "color": "orange"}, {"from": 18, "to": 21, "color": "red"},
    {"from": 21, "to": 0, "color": "magenta"}, {"from": 0, "to": 3, "color": "purple"},
]


# -- hours ---------------------------------------------------------------

@pytest.mark.parametrize("hour,expected", [
    (3, "blue"), (5, "blue"), (6, "cyan"), (9, "green"), (12, "yellow"),
    (15, "orange"), (18, "red"), (21, "magenta"), (23, "magenta"),
    (0, "purple"), (2, "purple"),
])
def test_hours_full_cycle(hour, expected):
    cfg = _cfg("hours", hours=HOURS)
    assert schedule.resolve(cfg, datetime(2026, 7, 22, hour, 30)) == expected


def test_hours_uncovered_is_off():
    cfg = _cfg("hours", hours=[{"from": 8, "to": 20, "color": "white"}])
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 10, 0)) == "white"
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 22, 0)) is None  # OFF


def test_schedule_disabled_is_off():
    cfg = dataclasses.replace(_cfg("hours", hours=HOURS), schedule_enabled=False)
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 10, 0)) is None


def test_no_active_preset_is_off():
    cfg = dataclasses.replace(_cfg("hours", hours=HOURS), active_preset=None)
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 10, 0)) is None


# -- weekdays / monthdays / months ---------------------------------------

def test_weekdays():
    week = {k: c for k, c in zip(sm.WEEKDAY_KEYS,
            ["red", "orange", "yellow", "green", "cyan", "blue", "purple"])}
    cfg = _cfg("weekdays", weekdays=week)
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 12, 0)) == "yellow"  # Wednesday
    assert schedule.resolve(cfg, datetime(2026, 7, 26, 12, 0)) == "purple"  # Sunday


def test_monthdays_groups_first_match_wins():
    cfg = _cfg("monthdays", monthdays=[
        {"from": 1, "to": 5, "color": "red"},
        {"from": 5, "to": 10, "color": "green"},   # 5 overlaps: first wins
        {"from": 11, "to": 31, "color": "blue"},
    ])
    assert schedule.resolve(cfg, datetime(2026, 7, 5, 12, 0)) == "red"
    assert schedule.resolve(cfg, datetime(2026, 7, 7, 12, 0)) == "green"
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 12, 0)) == "blue"


def test_months():
    months = {k: ("cyan" if k == "jul" else "white") for k in sm.MONTH_KEYS}
    cfg = _cfg("months", months=months)
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 12, 0)) == "cyan"
    assert schedule.resolve(cfg, datetime(2026, 1, 1, 12, 0)) == "white"


# -- daylight (Belgrade 2026-07-22: dawn 04:37, sunrise 05:13, noon 12:44,
#              sunset 20:15, dusk 20:50 — verified against astral) --------

DAYLIGHT = {"day": ["cyan", "green", "yellow", "orange"],
            "twilightMorning": "magenta", "twilightEvening": "red",
            "night": ["purple"]}


@pytest.mark.parametrize("hh,mm,expected", [
    (4, 30, "purple"),    # before dawn -> night
    (4, 50, "magenta"),   # MORNING civil twilight -> its own color
    (5, 30, "cyan"),      # day arc 1
    (8, 0, "cyan"),       # arc 2 starts 08:59
    (13, 0, "yellow"),    # just after solar noon 12:44 -> arc 3
    (19, 0, "orange"),    # arc 4
    (20, 45, "red"),      # EVENING civil twilight -> its own color
    (23, 0, "purple"),    # night
    (2, 0, "purple"),     # small hours -> previous night arc
])
def test_daylight_arcs_two_twilights_night(hh, mm, expected):
    cfg = _cfg("daylight", daylight=DAYLIGHT)
    assert schedule.resolve(cfg, datetime(2026, 7, 22, hh, mm, tzinfo=TZ)) == expected


def test_daylight_no_night_list_is_off():
    cfg = _cfg("daylight", daylight={
        "day": ["cyan"], "twilightMorning": None,
        "twilightEvening": None, "night": []})
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 23, 0, tzinfo=TZ)) is None
    # twilight None -> twilight time falls through to night handling -> OFF
    assert schedule.resolve(cfg, datetime(2026, 7, 22, 20, 45, tzinfo=TZ)) is None


# -- validation ----------------------------------------------------------

def test_daylight_requires_valid_timezone():
    import json
    raw = json.loads((Path(__file__).parent.parent / "config.json")
                     .read_text(encoding="utf-8"))
    raw["activePreset"] = "Solar day"
    raw["location"]["timezone"] = ""          # the GUI bug that crashed 0.1.140
    with pytest.raises(sm.ConfigError):
        sm.parse(raw)
    raw["location"]["timezone"] = "Not/AZone"
    with pytest.raises(sm.ConfigError):
        sm.parse(raw)
