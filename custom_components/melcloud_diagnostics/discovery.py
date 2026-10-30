"""Bounded LAN hints and existing HA accounts, separate from cloud identity."""

import asyncio
from dataclasses import dataclass

from homeassistant.components.zeroconf import async_get_async_instance
from homeassistant.helpers import device_registry as dr
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo


@dataclass(frozen=True)
class LocalHint:
    name: str
    source: str


def existing_accounts(hass):
    """Reuse only the known credential schema of the official HA integration."""
    return {
        entry.entry_id: entry
        for entry in hass.config_entries.async_entries("melcloud_home")
        if isinstance(entry.data.get("email"), str)
        and isinstance(entry.data.get("password"), str)
        and entry.data["email"]
        and entry.data["password"]
    }


def account_label(email):
    local, separator, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if separator else "Account MELCloud Home"


def relevant_device(text):
    lowered = text.lower()
    return any(token in lowered for token in ("asgard", "ecodan", "gekkekoe", "mitsubishi"))


async def async_local_hints(hass) -> tuple[list[LocalHint], str]:
    """Browse ESPHome advertisements; never scan ports or authenticate to devices.

    A name/project match is a hint only, not proof of Ecodan identity or MAC-597 support.
    """
    hints = {}
    registry = dr.async_get(hass)
    for device in registry.devices.values():
        text = " ".join(str(v or "") for v in (device.name, device.manufacturer, device.model))
        if relevant_device(text):
            name = device.name_by_user or device.name or device.model or "Mitsubishi / Ecodan"
            hints[name] = LocalHint(name, "home_assistant")
    names = set()
    browser = None
    status = "completed"
    try:
        async with asyncio.timeout(6):
            instance = await async_get_async_instance(hass)

            def changed(zeroconf, service_type, name, state_change):
                if (
                    state_change in (ServiceStateChange.Added, ServiceStateChange.Updated)
                    and len(names) < 20
                ):
                    names.add(name)

            browser = AsyncServiceBrowser(
                instance.zeroconf, "_esphomelib._tcp.local.", handlers=[changed]
            )
            await asyncio.sleep(2)

            async def resolve(name):
                info = AsyncServiceInfo("_esphomelib._tcp.local.", name)
                if await info.async_request(instance.zeroconf, 1000):
                    properties = " ".join(
                        f"{k.decode('utf-8', 'replace')}={v.decode('utf-8', 'replace') if v else ''}"
                        for k, v in info.properties.items()
                    )
                    if relevant_device(name + " " + properties):
                        display = name.removesuffix("._esphomelib._tcp.local.")
                        hints.setdefault(display, LocalHint(display, "mdns_candidate"))

            await asyncio.gather(*(resolve(name) for name in names))
    except (TimeoutError, OSError, RuntimeError):
        status = "unavailable"
    finally:
        if browser:
            await browser.async_cancel()
    return list(hints.values()), status
