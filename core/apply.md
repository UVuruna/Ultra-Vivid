# Apply

**Script:** [Apply (script)](apply.py)

## Purpose
Put a preset's colors on the hardware through the OpenRGB SDK server
(default `127.0.0.1:6742`) — no `.orp` profiles, no CLI spawning.

## Behavior (pseudocode)

```
CONNECT with retry (server may still be starting at log on)
WAIT until the device list is COMPLETE (wait_until_ready) — see below
devices = ALL devices, filtered by config include/exclude substrings
FOR EACH selected device i:
    color = preset.colors[i mod N]     (one color -> everything;
                                        N colors -> round-robin by device)
    ALWAYS write mode "Direct" (fallback "Static") — even if OpenRGB already
        reports that mode: RGB RAM boots running its ONBOARD effect while
        OpenRGB's detected state already says "Direct", so only a forced mode
        write stops the effect and latches Direct (what the GUI click does)
    set color
preset None -> every selected device gets 000000 (all RGB off)
```

## Hardware readiness (`wait_until_ready`)

The SDK server reports its socket as ready BEFORE device detection finishes,
so a slow device (typically RGB RAM) can be missing for a few seconds at
log on — the classic "everything got colored except the RAM". This is fixed
generically, with NO hardware names in the code: the program learns how many
devices this machine has when everything is loaded and waits for that count
before applying.

```
count_expected = last-loaded device count for THIS machine   (devices.json, learned)
IF readyTimeoutSeconds <= 0 -> don't wait (escape hatch)
LOOP (until ready or readyTimeoutSeconds elapses):
    n = number of devices the server reports now
    IF we have a learned count -> ready when n >= count_expected
    ELSE (first run ever)       -> ready when n has not changed for
                                   readyStableChecks polls (the list "settled")
    IF not ready -> sleep readyPollSeconds, client.update(), poll again
ON ready   -> remember n (self-calibrates UP when a device is added)
ON timeout -> WARN, apply to what is present, remember the lower n
              (self-calibrates DOWN once a device is physically removed)
```

- **Warm machine** (shortcuts, 10-min tick, resume): the count is already
  met -> returns on the first poll, zero added latency.
- **Cold boot with a slow device**: polls until it appears, THEN applies —
  until then the previous color stays on the hardware.
- The learned count lives in `logs/devices.json`, owned solely by this module
  (separate from the resolver's `state.json`).

## Connections

### Uses
- [Settings](settings.md); `openrgb-python` (SDK client)

### Used by
- [Resolver](../resolver.md)
