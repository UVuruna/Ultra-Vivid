# Solar

**Script:** [Solar (script)](solar.py)

## Purpose
The five sun events of one local calendar day — civil dawn, sunrise, solar
noon, sunset, civil dusk — tz-aware, via the `astral` library. Same library
and civil-twilight convention (sun 6° below horizon) as DOMY Watch.

Events that do not occur at the given latitude on the given day (polar
day/night, white nights) are `None` — documented behavior, not an error.
Solar noon always exists.

## Connections

### Uses
- [Settings](settings.md) — the `Location` dataclass

### Used by
- [Schedule](schedule.md) — the daylight schedule type
