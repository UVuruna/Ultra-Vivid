# Settings

**Script:** [Settings (script)](settings.py)

## Purpose
Load `config.json` (schema v2) into typed, frozen dataclasses and validate
every field loudly. The resolver refuses to run on an old-schema or broken
config — no silent fallbacks (Rule #1).

## Schema v2 (summary)

```
version: 2
openrgb:      host, port, connectRetries, retrySeconds, path
location:     name, latitude, longitude, timezone   (needed for daylight)
devices:      mode ("exclude"|"include"), names [substrings]
colorPresets: { name: [RRGGBB, ...] }
schedule:     enabled, type (hours|weekdays|monthdays|months|daylight),
              + the matching section (see Schedule doc for semantics)
shortcuts:    sets: [ { selector, keys, bindings {key: preset} } ]
```

## Validation rules (pseudocode)

```
IF version != 2            -> error (migrate first)
FOR EACH preset color      -> must be RRGGBB hex
IF type = weekdays         -> all 7 days present
IF type = months           -> all 12 months present
IF type = monthdays        -> 1 <= from <= to <= 31 per slot
IF type = daylight         -> day list non-empty AND location present
EVERY referenced preset    -> must exist in colorPresets
```

## Connections

### Used by
- [Schedule](schedule.md), [Apply](apply.md), [Resolver](../resolver.md)
