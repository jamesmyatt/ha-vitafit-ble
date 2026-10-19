"""Test the Vitafit diagnostics."""

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.vitafit_ble.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import ADDRESS, inject_service_info, make_service_info
from .conftest import FakeScaleClient


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_scale: FakeScaleClient,
) -> None:
    """Test the config entry diagnostics before and after a weigh-in."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, title="Vitafit VT701 AA60"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics["entry"]["unique_id"] == ADDRESS
    assert diagnostics["service_info"] is None

    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics["weight_only"] is False
    assert diagnostics["polling"] is False
    assert diagnostics["last_poll_successful"] is True
    assert diagnostics["poll_failed"] is False
    assert diagnostics["service_info"] == {
        "name": "Vitafit Body Fat",
        "rssi": -60,
        "manufacturer_data": {},
        "service_data": {},
        "service_uuids": [],
        "source": "local",
        "connectable": True,
    }
