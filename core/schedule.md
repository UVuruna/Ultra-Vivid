# Schedule

**Script:** [Schedule (script)](schedule.py)

## Purpose
Pure resolution: given the loaded settings and the current moment, return
the active color preset name — or `None`, meaning ALL RGB OFF.

## Semantics per type (owner spec, pseudocode)

```
hours:      slots {from, to, preset}, `to` exclusive, may wrap midnight
            hour in no slot -> OFF
weekdays:   every weekday has a preset (all 7 required)
monthdays:  groups {from, to, preset}, both inclusive; first match wins;
            uncovered day -> OFF
months:     every month has a preset (all 12 required)

daylight:   events = sun(today)
            IF sunrise <= now < sunset:
                arc = which of N equal parts of [sunrise, sunset] holds now
                -> day[arc]            (equal split of the true interval is
                                        centered on solar noon by definition)
            ELSE IF in civil twilight AND twilight preset set -> twilight
            ELSE (night):
                IF night list empty -> OFF
                arc over [dusk, next dawn] (or [prev dusk, dawn] before
                sunrise) -> night[arc]
```

## Connections

### Uses
- [Settings](settings.md), [Solar](solar.md)

### Used by
- [Resolver](../resolver.md)
