"""Resolve which COLOR the active preset produces at a given moment.

Pure logic: (Settings, now) -> color name, or None meaning ALL RGB OFF.
No I/O, no OpenRGB — the applier consumes the result.

A PRESET is a rule (owner spec): a trigger grouping whose slots
reference colors. Exactly one preset is active at a time.

Rules per preset type:
- hours:     from/to slots, `to` exclusive, may wrap midnight;
             hours not covered by any slot -> OFF
- weekdays:  every day of the week has a color (validated in settings)
- monthdays: from/to day-of-month groups, both inclusive; first match
             wins on overlapping boundaries; uncovered day -> OFF
- months:    every month has a color (validated in settings)
- daylight:  N day colors in equal arcs sunrise->sunset (equal split of
             the true interval is centered on solar noon by definition);
             SEPARATE morning and evening civil-twilight colors
             (dawn->sunrise and sunset->dusk); optional night colors in
             equal arcs dusk->next dawn; empty night list -> OFF
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.settings import MONTH_KEYS, WEEKDAY_KEYS, Preset, Settings
from core.solar import compute_sun_day


def tick_timezone(settings: Settings) -> ZoneInfo | None:
    """Timezone for 'now' at tick time: the configured location zone for
    the daylight type (sun events are tz-aware), naive local otherwise."""
    preset = settings.active()
    if preset and preset.type == "daylight" and settings.location.timezone:
        return ZoneInfo(settings.location.timezone)
    return None


def resolve(settings: Settings, now: datetime) -> str | None:
    """Return the active color name, or None for all-off."""
    if not settings.schedule_enabled:
        return None
    preset = settings.active()
    if preset is None:
        return None
    if preset.type == "hours":
        return _resolve_hours(preset.hours, now.hour)
    if preset.type == "weekdays":
        return preset.weekdays[WEEKDAY_KEYS[now.weekday()]]
    if preset.type == "monthdays":
        for slot in preset.monthdays:
            if slot["from"] <= now.day <= slot["to"]:
                return slot["color"]
        return None
    if preset.type == "months":
        return preset.months[MONTH_KEYS[now.month - 1]]
    return _resolve_daylight(settings, preset, now)


def _resolve_hours(slots: list[dict], hour: int) -> str | None:
    for slot in slots:
        start, end = slot["from"], slot["to"]
        if start == end:
            continue  # zero-length slot covers nothing
        if start < end:
            hit = start <= hour < end
        else:  # wraps midnight, e.g. 21 -> 3
            hit = hour >= start or hour < end
        if hit:
            return slot["color"]
    return None


def _index_in_arc(start: datetime, end: datetime, now: datetime, count: int) -> int:
    """Which of `count` equal sub-arcs of [start, end) contains `now`."""
    total = (end - start).total_seconds()
    elapsed = (now - start).total_seconds()
    return min(int(elapsed / total * count), count - 1)


def _resolve_daylight(settings: Settings, preset: Preset, now: datetime) -> str | None:
    d = preset.daylight
    day_colors: list[str] = d["day"]
    twilight_morning: str | None = d.get("twilightMorning")
    twilight_evening: str | None = d.get("twilightEvening")
    night_colors: list[str] = d.get("night", [])

    sun = compute_sun_day(settings.location, now.date())

    # Polar edge days: no horizon crossing at all -> sun elevation decides.
    if sun.sunrise is None or sun.sunset is None:
        import astral
        import astral.sun
        observer = astral.Observer(settings.location.latitude, settings.location.longitude)
        elevation = astral.sun.elevation(observer, now)
        if elevation > 0:
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return day_colors[_index_in_arc(
                midnight, midnight + timedelta(days=1), now, len(day_colors))]
        return night_colors[0] if night_colors else None

    if sun.sunrise <= now < sun.sunset:
        return day_colors[_index_in_arc(sun.sunrise, sun.sunset, now, len(day_colors))]

    if sun.dawn is not None and sun.dawn <= now < sun.sunrise:
        if twilight_morning is not None:
            return twilight_morning
    elif sun.dusk is not None and sun.sunset <= now < sun.dusk:
        if twilight_evening is not None:
            return twilight_evening

    if not night_colors:
        return None

    # Night arc: today's dusk -> tomorrow's dawn (or yesterday's dusk ->
    # today's dawn when we are in the small hours before dawn).
    if now < (sun.dawn or sun.sunrise):
        prev = compute_sun_day(settings.location, now.date() - timedelta(days=1))
        start = prev.dusk or prev.sunset or now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = sun.dawn or sun.sunrise
    else:
        nxt = compute_sun_day(settings.location, now.date() + timedelta(days=1))
        start = sun.dusk or sun.sunset
        end = nxt.dawn or nxt.sunrise or start + timedelta(hours=12)
    return night_colors[_index_in_arc(start, end, now, len(night_colors))]
