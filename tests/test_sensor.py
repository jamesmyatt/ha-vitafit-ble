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
from homeassistant.helpers.event import async_track_state_change_event
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


WEIGHT = "sensor.vitafit_vt701_aa60_weight"
IMPEDANCE = "sensor.vitafit_vt701_aa60_impedance"
REAL_TIME_WEIGHT = "sensor.vitafit_vt701_aa60_real_time_weight"
SIGNAL_STRENGTH = "sensor.vitafit_vt701_aa60_signal_strength"


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_weigh_in(hass: HomeAssistant, mock_scale: FakeScaleClient) -> None:
    """Test a full weigh-in updates the sensors."""
    entry = await _async_setup(hass)
    # Before the scale is seen, the weigh-in sensors are available but empty.
    assert {
        state.entity_id: state.state for state in hass.states.async_all("sensor")
    } == {
        WEIGHT: STATE_UNKNOWN,
        IMPEDANCE: STATE_UNKNOWN,
        REAL_TIME_WEIGHT: STATE_UNAVAILABLE,
        SIGNAL_STRENGTH: STATE_UNAVAILABLE,
    }

    real_time: list[str] = []
    async_track_state_change_event(
        hass,
        REAL_TIME_WEIGHT,
        lambda event: real_time.append(event.data["new_state"].state),
    )
    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()

    # The live weight while connected, then unavailable once disconnected.
    assert real_time == ["87.4", "87.35", STATE_UNAVAILABLE]

    weight = hass.states.get("sensor.vitafit_vt701_aa60_weight")
    assert weight is not None
    assert weight.state == "87.35"
    assert weight.attributes[ATTR_UNIT_OF_MEASUREMENT] == "kg"

    impedance = hass.states.get("sensor.vitafit_vt701_aa60_impedance")
    assert impedance is not None
    assert impedance.state == "466"
    assert impedance.attributes[ATTR_UNIT_OF_MEASUREMENT] == "ohm"

    assert _state(hass, SIGNAL_STRENGTH) == "-60"
    mock_scale.disconnect.assert_awaited_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_connection_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed connection is logged, and keeps the last weigh-in."""
    await _async_setup(hass)
    with patch(
        "vitafit_ble.device.establish_connection",
        AsyncMock(side_effect=BleakError("out of range")),
    ):
        inject_service_info(hass, make_service_info())
        await hass.async_block_till_done()

    assert "Bluetooth error whilst polling" in caplog.text
    assert _state(hass, WEIGHT) == STATE_UNKNOWN
    assert _state(hass, REAL_TIME_WEIGHT) == STATE_UNAVAILABLE


async def test_no_stable_weight_keeps_last_weigh_in(
    hass: HomeAssistant, mock_scale: FakeScaleClient
) -> None:
    """A weigh-in without a stable weight leaves the last one in place."""
    await _async_setup(hass)
    with patch(
        "homeassistant.components.bluetooth.active_update_processor"
        ".monotonic_time_coarse",
        return_value=monotonic_time_coarse() - 120,
    ):
        inject_service_info(hass, make_service_info())
        await hass.async_block_till_done()
    assert _state(hass, WEIGHT) == "87.35"

    # The repeat advertisement is polled by the timer, after the cooldown.
    with patch(
        "vitafit_ble.session.VitafitSession.async_measure", AsyncMock(return_value=None)
    ):
        inject_service_info(hass, make_service_info())
        async_fire_time_changed(hass, dt_util.utcnow() + FALLBACK_POLL_INTERVAL)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=POLL_DEFAULT_COOLDOWN + 1)
        )
        await hass.async_block_till_done()
    assert mock_scale.disconnect.await_count == 2
    assert _state(hass, WEIGHT) == "87.35"
    assert _state(hass, IMPEDANCE) == "466"


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
