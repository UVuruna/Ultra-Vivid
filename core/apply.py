"""Apply a named color to the selected OpenRGB devices via the SDK.

Connects to the running OpenRGB server (retrying while it starts up),
filters devices by the config's include/exclude list, and sets colors
directly — no .orp profiles involved. Prefers each device's Direct mode
(no flash writes, no flicker); falls back to Static when the hardware
has no Direct mode (e.g. ASRock motherboard).

Color semantics: one hex -> every selected device gets it; N hex values
-> selected device i gets colors[i mod N] (device order = OpenRGB id).
None -> all selected devices go black (all RGB off).
"""

import json
import logging
import time
from datetime import datetime

from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

from core import paths
from core.settings import Settings

logger = logging.getLogger(__name__)

_MODE_PREFERENCE = ["direct", "static"]


def connect(settings: Settings) -> OpenRGBClient:
    """Connect to the SDK server, retrying while OpenRGB starts up."""
    o = settings.openrgb
    last_error: Exception | None = None
    for attempt in range(1, o.connect_retries + 1):
        try:
            return OpenRGBClient(o.host, o.port, "UltraVivid")
        except (ConnectionError, OSError, TimeoutError) as e:
            last_error = e
            logger.info("OpenRGB server not up yet (attempt %d/%d): %s",
                        attempt, o.connect_retries, e)
            time.sleep(o.retry_seconds)
    raise ConnectionError(
        f"OpenRGB SDK server unreachable at {o.host}:{o.port} "
        f"after {o.connect_retries} attempts"
    ) from last_error


def selected_devices(client: OpenRGBClient, settings: Settings) -> list:
    """Filter client.devices by the config include/exclude name list."""
    f = settings.devices
    needles = [n.lower() for n in f.names]

    def matches(device) -> bool:
        name = device.name.lower()
        return any(n in name for n in needles)

    if f.mode == "include":
        chosen = [d for d in client.devices if matches(d)]
    else:
        chosen = [d for d in client.devices if not matches(d)]
    logger.info("Devices selected: %s (of %s)",
                [d.name for d in chosen], [d.name for d in client.devices])
    return chosen


def detect_hypershift_keyboard(settings: Settings) -> bool:
    """True when a Hypershift-capable keyboard (Razer) is present.
    Quick single-attempt probe; False when the server is unreachable."""
    import dataclasses
    quick = dataclasses.replace(
        settings, openrgb=dataclasses.replace(settings.openrgb, connect_retries=1))
    try:
        client = connect(quick)
    except ConnectionError:
        return False
    try:
        return any(d.type.name == "KEYBOARD" and "razer" in d.name.lower()
                   for d in client.devices)
    finally:
        client.disconnect()


def _read_expected_count() -> int | None:
    """The device count seen last time the hardware was fully loaded, or None
    on first run / unreadable file."""
    try:
        return int(json.loads(
            paths.DEVICE_STATE_PATH.read_text(encoding="utf-8"))["count"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return None


def _remember_count(count: int, previous: int | None) -> None:
    """Persist the ready device count so future boots wait for the same set.
    Only writes on change (self-calibrates up when a device is added, down
    once a device is removed)."""
    if count == previous:
        return
    paths.DEVICE_STATE_PATH.write_text(
        json.dumps({"count": count, "at": datetime.now().isoformat()}),
        encoding="utf-8",
    )


def wait_until_ready(client: OpenRGBClient, settings: Settings) -> None:
    """Block until the OpenRGB device list is COMPLETE, then return.

    The SDK server reports the socket as ready before device detection
    finishes, so a slow device (typically RGB RAM) can be missing for a few
    seconds at log on — coloring "everything except the RAM". Generic fix,
    no hardware names: wait until as many devices are present as the last
    time everything was loaded (learned per machine, DEVICE_STATE_PATH).

    - Warm machine (shortcuts, ticks, resume): the count is already met, so
      this returns on the first poll — no added latency.
    - Cold boot with a slow device: polls until it appears.
    - First run ever (no learned count): waits for the count to plateau.
    - Timeout (a device was physically removed): logs a warning, applies to
      what is present, and re-learns the lower count so it never waits again.
    """
    o = settings.openrgb
    if o.ready_timeout_seconds <= 0:
        return
    expected = _read_expected_count()
    deadline = time.monotonic() + o.ready_timeout_seconds
    last_count, stable = -1, 0
    waited = False

    while True:
        n = len(client.devices)
        if expected is not None:
            ready = n >= expected
        else:  # first run: no learned count — wait for the list to settle
            if n == last_count:
                stable += 1
            else:
                last_count, stable = n, 1
            ready = n > 0 and stable >= o.ready_stable_checks

        if ready:
            if waited:
                logger.info("Devices ready: %d present.", n)
            _remember_count(n, expected)
            return
        if time.monotonic() >= deadline:
            logger.warning(
                "Device list still incomplete after %.0fs (%d present, "
                "expected %s) — applying anyway; a slow/removed device keeps "
                "its previous color.", o.ready_timeout_seconds, n, expected)
            _remember_count(n, expected)
            return

        waited = True
        time.sleep(o.ready_poll_seconds)
        client.update()


def apply_color(settings: Settings, color: str | None) -> None:
    """Apply the named color (or all-off when None) to the selected devices."""
    colors = settings.colors[color] if color else ["000000"]
    client = connect(settings)
    try:
        wait_until_ready(client, settings)
        devices = selected_devices(client, settings)
        if not devices:
            logger.warning("No devices left after filtering — nothing to apply.")
            return
        for i, device in enumerate(devices):
            hex_color = colors[i % len(colors)]
            _set_device_color(device, RGBColor.fromHEX(f"#{hex_color}"))
            logger.info("Applied #%s to %s", hex_color, device.name)
    finally:
        client.disconnect()


def _set_device_color(device, color: RGBColor) -> None:
    mode_names = {m.name.lower(): m for m in device.modes}
    for wanted in _MODE_PREFERENCE:
        if wanted in mode_names:
            # ALWAYS send the mode write (UpdateMode), even when OpenRGB already
            # reports this mode active. RGB RAM (e.g. HyperX Predator) powers up
            # running its ONBOARD effect while OpenRGB's *detected* state already
            # reads "Direct" — so the old `active_mode !=` guard skipped the
            # write, the hardware effect kept running, and the per-LED colors
            # were ignored (the RAM stayed on its rainbow until the user opened
            # the OpenRGB GUI and clicked). This forced UpdateMode IS what that
            # click does: it stops the onboard effect and latches Direct.
            device.set_mode(mode_names[wanted])
            break
    device.set_color(color)
