"""Load and validate config.json (schema v3).

Terminology (owner spec):
- COLOR   — a named, defined color (hex list). Defaults ship built-in;
            the user can add fully custom ones.
- PRESET  — a RULE: a trigger grouping (hours / weekdays / monthdays /
            months / daylight) whose slots reference colors. Several
            presets can exist; exactly one is ACTIVE.

Validation fails loudly (Rule #1): a broken config must never half-run
the resolver — every error names the exact field that is wrong.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CONFIG_VERSION = 3

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTH_KEYS = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]
PRESET_TYPES = ["hours", "weekdays", "monthdays", "months", "daylight"]
SHORTCUT_SELECTORS = ["shift", "ctrl", "alt", "ctrl+shift", "alt+shift",
                      "ctrl+alt", "hypershift"]


class ConfigError(Exception):
    """Raised when config.json is missing, unreadable, or invalid."""


@dataclass(frozen=True)
class OpenRGBSettings:
    host: str
    port: int
    connect_retries: int
    retry_seconds: float


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str


@dataclass(frozen=True)
class DeviceFilter:
    mode: str          # "exclude" | "include"
    names: list[str]   # case-insensitive substrings matched against device names


@dataclass(frozen=True)
class Preset:
    """One RULE: a trigger grouping whose slots reference colors."""
    name: str
    type: str                       # one of PRESET_TYPES
    hours: list[dict]               # [{"from": int, "to": int, "color": str}]
    weekdays: dict[str, str]        # mon..sun -> color
    monthdays: list[dict]           # [{"from": int, "to": int, "color": str}]
    months: dict[str, str]          # jan..dec -> color
    daylight: dict                  # {"day": [..], "twilightMorning": str|None,
                                    #  "twilightEvening": str|None, "night": [..]}


@dataclass(frozen=True)
class ShortcutSet:
    name: str                # user-chosen set name (also the slot folder name)
    selector: str            # one of SHORTCUT_SELECTORS
    bindings: dict[str, str] # key label (any mix from keymap) -> color name


@dataclass(frozen=True)
class ChromaSettings:
    """Optional Razer Chroma module: color the keyboard alongside the
    schedule WITHOUT touching Synapse key bindings (held by the daemon —
    Chroma sessions die without heartbeat, so a one-shot cannot do it)."""
    enabled: bool
    follow_schedule: bool


@dataclass(frozen=True)
class Settings:
    openrgb: OpenRGBSettings
    location: Location
    devices: DeviceFilter
    colors: dict[str, list[str]]    # name -> list of RRGGBB hex strings
    presets: list[Preset]
    active_preset: str | None       # name of the active preset (None = off)
    schedule_enabled: bool
    shortcuts_enabled: bool = True
    shortcut_sets: list[ShortcutSet] = field(default_factory=list)
    chroma: ChromaSettings = field(
        default_factory=lambda: ChromaSettings(False, True))

    def active(self) -> Preset | None:
        for preset in self.presets:
            if preset.name == self.active_preset:
                return preset
        return None


def load(config_path: Path) -> Settings:
    if not config_path.is_file():
        raise ConfigError(f"config.json not found: {config_path}")
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"config.json is not valid JSON: {e}") from e
    return parse(raw)


def parse(raw: dict) -> Settings:
    """Validate a raw config dict (the GUI validates edits through this
    before writing the file)."""
    if raw.get("version") != CONFIG_VERSION:
        raise ConfigError(
            f"config.json version is {raw.get('version')!r}, expected {CONFIG_VERSION}.")

    colors = _parse_colors(raw)
    presets = [_parse_preset(p, i, colors, raw)
               for i, p in enumerate(raw.get("presets", []))]
    names = [p.name for p in presets]
    if len(set(n.lower() for n in names)) != len(names):
        raise ConfigError("presets: duplicate preset names")

    active = raw.get("activePreset")
    if active is not None and active not in names:
        raise ConfigError(f"activePreset {active!r} does not match any preset")

    shortcut_sets = _parse_shortcuts(raw, colors)

    o = raw.get("openrgb", {})
    dev = raw.get("devices", {})
    if dev.get("mode") not in ("exclude", "include"):
        raise ConfigError('devices.mode must be "exclude" or "include"')

    return Settings(
        openrgb=OpenRGBSettings(
            host=o.get("host", "127.0.0.1"),
            port=int(o.get("port", 6742)),
            connect_retries=int(o.get("connectRetries", 30)),
            retry_seconds=float(o.get("retrySeconds", 2)),
        ),
        location=_parse_location(raw),
        devices=DeviceFilter(mode=dev["mode"], names=list(dev.get("names", []))),
        colors=colors,
        presets=presets,
        active_preset=active,
        schedule_enabled=bool(raw.get("scheduleEnabled", True)),
        shortcuts_enabled=bool(raw.get("shortcuts", {}).get("enabled", True)),
        shortcut_sets=shortcut_sets,
        chroma=ChromaSettings(
            enabled=bool(raw.get("chroma", {}).get("enabled", False)),
            follow_schedule=bool(raw.get("chroma", {}).get("followSchedule", True)),
        ),
    )


def _parse_location(raw: dict) -> Location:
    loc = raw.get("location", {})
    return Location(
        name=loc.get("name", ""),
        latitude=float(loc.get("latitude", 0.0)),
        longitude=float(loc.get("longitude", 0.0)),
        timezone=loc.get("timezone", ""),
    )


def _parse_colors(raw: dict) -> dict[str, list[str]]:
    colors = raw.get("colors")
    if not isinstance(colors, dict) or not colors:
        raise ConfigError("colors must be a non-empty object {name: [RRGGBB, ...]}")
    for name, values in colors.items():
        if not isinstance(values, list) or not values:
            raise ConfigError(f"colors[{name!r}] must be a non-empty list of hex colors")
        for c in values:
            if not (isinstance(c, str) and len(c) == 6
                    and all(ch in "0123456789abcdefABCDEF" for ch in c)):
                raise ConfigError(f"colors[{name!r}]: {c!r} is not RRGGBB hex")
    return colors


def _require_color(colors: dict, name: str, where: str) -> None:
    if name not in colors:
        raise ConfigError(f"{where} references unknown color {name!r}")


def _parse_preset(p: dict, index: int, colors: dict, raw: dict) -> Preset:
    where = f"presets[{index}]"
    name = (p.get("name") or "").strip()
    if not name:
        raise ConfigError(f"{where} needs a non-empty name")
    ptype = p.get("type")
    if ptype not in PRESET_TYPES:
        raise ConfigError(f"{where}.type must be one of {PRESET_TYPES}, got {ptype!r}")

    hours = p.get("hours", [])
    weekdays = p.get("weekdays", {})
    monthdays = p.get("monthdays", [])
    months = p.get("months", {})
    daylight = p.get("daylight", {})

    if ptype == "hours":
        for slot in hours:
            if not (0 <= slot["from"] <= 23 and 0 <= slot["to"] <= 23):
                raise ConfigError(f"{where}.hours slot {slot}: hours must be 0-23")
            _require_color(colors, slot["color"], f"{where}.hours")
    elif ptype == "weekdays":
        missing = [k for k in WEEKDAY_KEYS if k not in weekdays]
        if missing:
            raise ConfigError(f"{where}.weekdays must cover all 7 days; missing: {missing}")
        for k in WEEKDAY_KEYS:
            _require_color(colors, weekdays[k], f"{where}.weekdays.{k}")
    elif ptype == "monthdays":
        for slot in monthdays:
            if not (1 <= slot["from"] <= 31 and 1 <= slot["to"] <= 31
                    and slot["from"] <= slot["to"]):
                raise ConfigError(f"{where}.monthdays slot {slot}: needs 1 <= from <= to <= 31")
            _require_color(colors, slot["color"], f"{where}.monthdays")
    elif ptype == "months":
        missing = [k for k in MONTH_KEYS if k not in months]
        if missing:
            raise ConfigError(f"{where}.months must cover all 12 months; missing: {missing}")
        for k in MONTH_KEYS:
            _require_color(colors, months[k], f"{where}.months")
    elif ptype == "daylight":
        day = daylight.get("day", [])
        if not day:
            raise ConfigError(f"{where}.daylight.day must list at least one color")
        for c in day:
            _require_color(colors, c, f"{where}.daylight.day")
        for twilight_key in ("twilightMorning", "twilightEvening"):
            value = daylight.get(twilight_key)
            if value is not None:
                _require_color(colors, value, f"{where}.daylight.{twilight_key}")
        for c in daylight.get("night", []):
            _require_color(colors, c, f"{where}.daylight.night")
        _validate_daylight_location(raw, where)

    return Preset(name=name, type=ptype, hours=hours, weekdays=weekdays,
                  monthdays=monthdays, months=months, daylight=daylight)


def _validate_daylight_location(raw: dict, where: str) -> None:
    loc = raw.get("location", {})
    tz = loc.get("timezone", "")
    if not tz or "latitude" not in loc or "longitude" not in loc:
        raise ConfigError(
            f"{where}: daylight needs a location — pick your city "
            "in the Presets tab (Daylight editor)")
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ConfigError(f"location.timezone {tz!r} is not a valid IANA zone: {e}") from e


def _parse_shortcuts(raw: dict, colors: dict) -> list[ShortcutSet]:
    from core.keymap import VIRTUAL_KEYS

    sets = []
    names: set[str] = set()
    for i, s in enumerate(raw.get("shortcuts", {}).get("sets", [])):
        name = (s.get("name") or "").strip()
        if not name:
            raise ConfigError(f"shortcuts.sets[{i}] needs a non-empty name")
        if name.lower() in names:
            raise ConfigError(f"shortcuts.sets[{i}]: duplicate set name {name!r}")
        names.add(name.lower())
        if s.get("selector") not in SHORTCUT_SELECTORS:
            raise ConfigError(f"shortcuts.sets[{i}].selector must be one of {SHORTCUT_SELECTORS}")
        bindings = s.get("bindings", {})
        for key, color in bindings.items():
            if key not in VIRTUAL_KEYS:
                raise ConfigError(f"shortcuts.sets[{i}]: unknown key {key!r}")
            _require_color(colors, color, f"shortcuts.sets[{i}].bindings[{key!r}]")
        sets.append(ShortcutSet(name=name, selector=s["selector"], bindings=bindings))
    return sets
