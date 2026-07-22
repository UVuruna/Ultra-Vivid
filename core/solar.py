"""Sun events for the daylight schedule type.

Thin wrapper around astral (same library and civil-twilight convention
as the DOMY Watch project). Events that do not occur on a given day at
the given latitude are None — documented astral behavior, not an error.
"""

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import astral
import astral.sun

from core.settings import Location

CIVIL_DEPRESSION = 6.0  # degrees below horizon: civil twilight boundary


@dataclass(frozen=True)
class SunDay:
    """Civil dawn, sunrise, solar noon, sunset, civil dusk of one local day."""

    dawn: datetime | None
    sunrise: datetime | None
    noon: datetime
    sunset: datetime | None
    dusk: datetime | None


def compute_sun_day(location: Location, local_date: date) -> SunDay:
    tz = ZoneInfo(location.timezone)
    observer = astral.Observer(latitude=location.latitude, longitude=location.longitude)

    def try_event(fn, **kwargs) -> datetime | None:
        try:
            return fn(observer, date=local_date, tzinfo=tz, **kwargs)
        except ValueError:
            # The event does not occur on this day at this latitude
            # (polar day/night, white nights).
            return None

    return SunDay(
        dawn=try_event(astral.sun.dawn, depression=CIVIL_DEPRESSION),
        sunrise=try_event(astral.sun.sunrise),
        noon=astral.sun.noon(observer, date=local_date, tzinfo=tz),
        sunset=try_event(astral.sun.sunset),
        dusk=try_event(astral.sun.dusk, depression=CIVIL_DEPRESSION),
    )
