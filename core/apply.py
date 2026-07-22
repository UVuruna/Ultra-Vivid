"""Apply a color preset to the selected OpenRGB devices via the SDK.

Connects to the running OpenRGB server (retrying while it starts up),
filters devices by the config's include/exclude list, and sets colors
directly — no .orp profiles involved. Prefers each device's Direct mode
(no flash writes, no flicker); falls back to Static when the hardware
has no Direct mode (e.g. ASRock motherboard).

Preset semantics: one color -> every selected device gets it; N colors
-> selected device i gets colors[i mod N] (device order = OpenRGB id).
Preset None -> all selected devices go black (all RGB off).
"""

import logging
import time

from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

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


def apply_preset(settings: Settings, preset: str | None) -> None:
    """Apply `preset` (or all-off when None) to the selected devices."""
    colors = settings.color_presets[preset] if preset else ["000000"]
    client = connect(settings)
    try:
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
            if device.active_mode != mode_names[wanted].id:
                device.set_mode(mode_names[wanted].id)
            break
    device.set_color(color)
