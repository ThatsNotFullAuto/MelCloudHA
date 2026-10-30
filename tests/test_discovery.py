"""Network discovery behavior simulated at the mDNS boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from zeroconf import ServiceStateChange

from custom_components.melcloud_diagnostics.discovery import async_local_hints


async def test_mdns_candidates_are_filtered_and_browser_is_closed():
    registry = SimpleNamespace(devices={})
    browser = SimpleNamespace(async_cancel=AsyncMock())
    instance = SimpleNamespace(zeroconf=object())

    def browse(zc, service, handlers):
        assert service == "_esphomelib._tcp.local."
        for name in ["asgard._esphomelib._tcp.local.", "lamp._esphomelib._tcp.local."]:
            handlers[0](zc, service, name, ServiceStateChange.Added)
        return browser

    def info(service, name):
        return SimpleNamespace(
            async_request=AsyncMock(return_value=True), properties={b"project_name": b"generic"}
        )

    with (
        patch(
            "custom_components.melcloud_diagnostics.discovery.dr.async_get", return_value=registry
        ),
        patch(
            "custom_components.melcloud_diagnostics.discovery.async_get_async_instance",
            new=AsyncMock(return_value=instance),
        ),
        patch(
            "custom_components.melcloud_diagnostics.discovery.AsyncServiceBrowser",
            side_effect=browse,
        ),
        patch(
            "custom_components.melcloud_diagnostics.discovery.AsyncServiceInfo", side_effect=info
        ),
        patch("custom_components.melcloud_diagnostics.discovery.asyncio.sleep", new=AsyncMock()),
    ):
        hints, status = await async_local_hints(MagicMock())
    assert status == "completed"
    assert [(h.name, h.source) for h in hints] == [("asgard", "mdns_candidate")]
    browser.async_cancel.assert_awaited_once()


async def test_registry_hint_survives_unavailable_network_search():
    registry = SimpleNamespace(
        devices={
            "test": SimpleNamespace(
                name="Ecodan",
                name_by_user="Pompa di casa",
                manufacturer="Mitsubishi Electric",
                model="FTC7",
            )
        }
    )
    with (
        patch(
            "custom_components.melcloud_diagnostics.discovery.dr.async_get", return_value=registry
        ),
        patch(
            "custom_components.melcloud_diagnostics.discovery.async_get_async_instance",
            new=AsyncMock(side_effect=OSError),
        ),
    ):
        hints, status = await async_local_hints(MagicMock())
    assert status == "unavailable"
    assert hints[0].source == "home_assistant" and hints[0].name == "Pompa di casa"
