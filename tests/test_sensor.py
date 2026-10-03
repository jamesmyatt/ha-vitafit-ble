"""Test the Vitafit sensors."""

from unittest.mock import AsyncMock, patch

from bleak import BleakError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitafit_ble.const import DOMAIN
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import ADDRESS, VITAFIT_SERVICE_INFO, inject_service_info
from .conftest import FakeScaleClient


async def _async_setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_weigh_in(hass: HomeAssistant, mock_scale: FakeScaleClient) -> None:
    """Test a full weigh-in creates the sensors."""
    entry = await _async_setup(hass)
    assert not hass.states.async_all("sensor")

    inject_service_info(hass, VITAFIT_SERVICE_INFO)
    await hass.async_block_till_done()

    weight = hass.states.get("sensor.vitafit_vt701_aa60_weight")
    assert weight is not None
    assert weight.state == "85.0"
    assert weight.attributes[ATTR_UNIT_OF_MEASUREMENT] == "kg"

    impedance = hass.states.get("sensor.vitafit_vt701_aa60_impedance")
    assert impedance is not None
    assert impedance.state == "393"
    assert impedance.attributes[ATTR_UNIT_OF_MEASUREMENT] == "ohm"

    assert hass.states.get("sensor.vitafit_vt701_aa60_signal_strength") is not None
    mock_scale.disconnect.assert_awaited_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_connection_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed connection is logged and creates no weight reading."""
    await _async_setup(hass)
    with patch(
        "vitafit_ble.parser.establish_connection",
        AsyncMock(side_effect=BleakError("out of range")),
    ):
        inject_service_info(hass, VITAFIT_SERVICE_INFO)
        await hass.async_block_till_done()

    assert "Bluetooth error whilst polling" in caplog.text
    weight = hass.states.get("sensor.vitafit_vt701_aa60_weight")
    assert weight is None or weight.state == STATE_UNKNOWN
