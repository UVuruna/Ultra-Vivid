# Settings

**Script:** [Settings (script)](settings.py)

## Purpose
Load `config.json` (schema v3) into typed, frozen dataclasses and validate
every field loudly. The resolver refuses to run on an old-schema or broken
config — no silent fallbacks (Rule #1).

Terminology (owner spec): a COLOR is a named, defined color; a PRESET is
a RULE — a trigger grouping whose slots reference colors. Several presets
can exist; `activePreset` names the one the resolver follows.

## Schema v3 (summary)

```
version: 3
openrgb:         host, port, connectRetries, retrySeconds, path,
                 readyPollSeconds, readyStableChecks, readyTimeoutSeconds
                 (device-readiness wait — see Apply.wait_until_ready)
location:        name, latitude, longitude, timezone (picked via the
                 city picker — validated as a real IANA zone)
devices:         mode ("exclude"|"include"), names [substrings]
colors:          { name: [RRGGBB, ...] }         (defaults + custom)
presets:         [ { name, type, + the matching trigger section } ]
activePreset:    name of the preset the resolver follows
scheduleEnabled: global on/off
chroma:          enabled, followSchedule
shortcuts:       sets: [ { name, selector, bindings {key: color} } ]
```

## Validation rules (pseudocode)

```
IF version != 3            -> error (migrate first)
FOR EACH color value       -> must be RRGGBB hex
FOR EACH preset (rule):
    weekdays  -> all 7 days present
    months    -> all 12 months present
    monthdays -> 1 <= from <= to <= 31 per slot
    daylight  -> day list non-empty AND location with a VALID IANA zone
EVERY referenced color     -> must exist in colors
activePreset               -> must name an existing preset
shortcut sets              -> unique names, known keys, known colors
```

## Connections

### Used by
- [Schedule](schedule.md), [Apply](apply.md), [Resolver](../resolver.md)
