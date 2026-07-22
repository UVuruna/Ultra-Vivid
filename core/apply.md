# Apply

**Script:** [Apply (script)](apply.py)

## Purpose
Put a preset's colors on the hardware through the OpenRGB SDK server
(default `127.0.0.1:6742`) — no `.orp` profiles, no CLI spawning.

## Behavior (pseudocode)

```
CONNECT with retry (server may still be starting at log on)
devices = ALL devices, filtered by config include/exclude substrings
FOR EACH selected device i:
    color = preset.colors[i mod N]     (one color -> everything;
                                        N colors -> round-robin by device)
    prefer mode "Direct" (no flash writes, no flicker),
    fall back to "Static" (e.g. ASRock motherboard has no Direct)
    set color
preset None -> every selected device gets 000000 (all RGB off)
```

## Connections

### Uses
- [Settings](settings.md); `openrgb-python` (SDK client)

### Used by
- [Resolver](../resolver.md)
