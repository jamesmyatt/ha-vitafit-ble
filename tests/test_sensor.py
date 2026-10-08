"""Test the Vitafit sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from bleak import BleakError
from bluetooth_data_tools import monotonic_time_coarse
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.vitafit_ble.const import DOMAIN
from custom_components.vitafit_ble.coordinator import FALLBACK_POLL_INTERVAL
from homeassistant.components.bluetooth.active_update_processor import (
    POLL_DEFAULT_COOLDOWN,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ADDRESS, inject_service_info, make_service_info
from .conftest import FakeScaleClient


async def _async_setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, title="Vitafit VT701 AA60"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_weigh_in(hass: HomeAssistant, mock_scale: FakeScaleClient) -> None:
    """Test a full weigh-in creates the sensors."""
    entry = await _async_setup(hass)
    assert {state.state for state in hass.states.async_all("sensor")} == {
        STATE_UNAVAILABLE
    }
    assert len(hass.states.async_all("sensor")) == 3

    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()

    weight = hass.states.get("sensor.vitafit_vt701_aa60_weight")
    assert weight is not None
    assert weight.state == "87.35"
    assert weight.attributes[ATTR_UNIT_OF_MEASUREMENT] == "kg"

    impedance = hass.states.get("sensor.vitafit_vt701_aa60_impedance")
    assert impedance is not None
    assert impedance.state == "466"
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
        inject_service_info(hass, make_service_info())
        await hass.async_block_till_done()

    assert "Bluetooth error whilst polling" in caplog.text
    weight = hass.states.get("sensor.vitafit_vt701_aa60_weight")
    assert weight is not None
    assert weight.state == STATE_UNKNOWN


async def test_repeat_weigh_in_polled_by_timer(
    hass: HomeAssistant, mock_scale: FakeScaleClient
) -> None:
    """A weigh-in whose advertisement repeats the last one is polled by the timer."""
    await _async_setup(hass)
    # Record the first poll as two minutes ago, more than POLL_INTERVAL.
    with patch(
        "homeassistant.components.bluetooth.active_update_processor"
        ".monotonic_time_coarse",
        return_value=monotonic_time_coarse() - 120,
    ):
        inject_service_info(hass, make_service_info())
        await hass.async_block_till_done()
    assert mock_scale.disconnect.await_count == 1

    # The scale wakes again with an identical advertisement,
    # which HA doesn't dispatch.
    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()
    assert mock_scale.disconnect.await_count == 1

    # The timer queues the poll, which runs once the debouncer's cooldown
    # from the first poll ends.
    async_fire_time_changed(hass, dt_util.utcnow() + FALLBACK_POLL_INTERVAL)
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=POLL_DEFAULT_COOLDOWN + 1)
    )
    await hass.async_block_till_done()
    assert mock_scale.disconnect.await_count == 2


async def test_timer_ignores_sleeping_scale(
    hass: HomeAssistant, mock_scale: FakeScaleClient
) -> None:
    """The timer doesn't poll when the last advertisement is old."""
    await _async_setup(hass)
    info = make_service_info()
    info.time -= 60
    inject_service_info(hass, info)
    async_fire_time_changed(hass, dt_util.utcnow() + FALLBACK_POLL_INTERVAL)
    await hass.async_block_till_done()
    mock_scale.disconnect.assert_not_awaited()
