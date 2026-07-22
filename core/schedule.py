"""Resolve which color preset is active at a given moment.

Pure logic: (Settings, now) -> preset name, or None meaning ALL RGB OFF.
No I/O, no OpenRGB — the applier consumes the result.

Rules per schedule type (owner spec):
- hours:     from/to slots, `to` exclusive, may wrap midnight;
             hours not covered by any slot -> OFF
- weekdays:  every day of the week has a preset (validated in settings)
- monthdays: from/to day-of-month groups, both inclusive; first match
             wins on overlapping boundaries; uncovered day -> OFF
- months:    every month has a preset (validated in settings)
- daylight:  N day presets in equal arcs sunrise->sunset (equal split of
             the true interval is centered on solar noon by definition);
             optional twilight preset for civil twilight (dawn->sunrise,
             sunset->dusk); optional night presets in equal arcs
             dusk->next dawn; empty night list -> OFF at night
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.settings import MONTH_KEYS, WEEKDAY_KEYS, Settings
from core.solar import compute_sun_day


def tick_timezone(settings: Settings) -> ZoneInfo | None:
    """Timezone for 'now' at tick time: the configured location zone for
    the daylight type (sun events are tz-aware), naive local otherwise."""
    if settings.schedule.type == "daylight" and settings.location.timezone:
        return ZoneInfo(settings.location.timezone)
    return None


def resolve(settings: Settings, now: datetime) -> str | None:
    """Return the active color preset name, or None for all-off."""
    s = settings.schedule
    if not s.enabled:
        return None
    if s.type == "hours":
        return _resolve_hours(s.hours, now.hour)
    if s.type == "weekdays":
        return s.weekdays[WEEKDAY_KEYS[now.weekday()]]
    if s.type == "monthdays":
        for slot in s.monthdays:
            if slot["from"] <= now.day <= slot["to"]:
                return slot["preset"]
        return None
    if s.type == "months":
        return s.months[MONTH_KEYS[now.month - 1]]
    return _resolve_daylight(settings, now)


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
            return slot["preset"]
    return None


def _index_in_arc(start: datetime, end: datetime, now: datetime, count: int) -> int:
    """Which of `count` equal sub-arcs of [start, end) contains `now`."""
    total = (end - start).total_seconds()
    elapsed = (now - start).total_seconds()
    return min(int(elapsed / total * count), count - 1)


def _resolve_daylight(settings: Settings, now: datetime) -> str | None:
    d = settings.schedule.daylight
    day_presets: list[str] = d["day"]
    twilight: str | None = d.get("twilight")
    night_presets: list[str] = d.get("night", [])

    sun = compute_sun_day(settings.location, now.date())

    # Polar edge days: no horizon crossing at all -> noon elevation decides.
    if sun.sunrise is None or sun.sunset is None:
        import astral
        import astral.sun
        observer = astral.Observer(settings.location.latitude, settings.location.longitude)
        elevation = astral.sun.elevation(observer, now)
        if elevation > 0:
            return day_presets[_index_in_arc(
                now.replace(hour=0, minute=0, second=0, microsecond=0),
                now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
                now, len(day_presets))]
        return night_presets[0] if night_presets else None

    if sun.sunrise <= now < sun.sunset:
        return day_presets[_index_in_arc(sun.sunrise, sun.sunset, now, len(day_presets))]

    in_morning_twilight = sun.dawn is not None and sun.dawn <= now < sun.sunrise
    in_evening_twilight = sun.dusk is not None and sun.sunset <= now < sun.dusk
    if (in_morning_twilight or in_evening_twilight) and twilight is not None:
        return twilight

    if not night_presets:
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
    return night_presets[_index_in_arc(start, end, now, len(night_presets))]
