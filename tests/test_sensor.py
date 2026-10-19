"""Test the Vitafit sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from bleak import BleakError
from bleak.backends.device import BLEDevice
from bluetooth_data_tools import monotonic_time_coarse
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from vitafit_ble.const import ADVERTISEMENT_MAX_AGE, MANUFACTURER

from custom_components.vitafit_ble.const import DOMAIN
from custom_components.vitafit_ble.coordinator import FALLBACK_POLL_INTERVAL
from homeassistant.components.bluetooth.active_update_processor import (
    POLL_DEFAULT_COOLDOWN,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PASSIVE_UPDATE_PROCESSOR,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
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


def _needs_poll_while_asleep(entry: MockConfigEntry) -> bool:
    """Ask the coordinator about an advertisement, with the scale asleep."""
    info = make_service_info()
    later = info.time + ADVERTISEMENT_MAX_AGE + 1
    with (
        patch(
            "custom_components.vitafit_ble.coordinator.monotonic_time_coarse",
            return_value=later,
        ),
        patch("vitafit_ble.device.monotonic_time_coarse", return_value=later),
    ):
        return entry.runtime_data.needs_poll(info)


@pytest.mark.parametrize("failure", ["bluetooth_error", "no_weight"])
async def test_failed_poll_waits_for_next_wake(
    hass: HomeAssistant, mock_scale: FakeScaleClient, failure: str
) -> None:
    """A poll without a weight is retried when the scale next wakes, at once."""
    entry = await _async_setup(hass)
    with (
        patch(
            "vitafit_ble.device.establish_connection",
            AsyncMock(side_effect=BleakError("out of range")),
        )
        if failure == "bluetooth_error"
        else patch(
            "vitafit_ble.session.VitafitSession.async_measure",
            AsyncMock(return_value=None),
        )
    ):
        inject_service_info(hass, make_service_info())
        await hass.async_block_till_done()
    assert _state(hass, WEIGHT) == STATE_UNKNOWN

    # Not again in the same wake, nor while asleep.
    assert not entry.runtime_data.needs_poll(make_service_info())
    assert not _needs_poll_while_asleep(entry)
    # At the next wake, well within POLL_INTERVAL, without the cooldown.
    assert entry.runtime_data.needs_poll(make_service_info())


async def test_successful_poll_keeps_cooldown(
    hass: HomeAssistant, mock_scale: FakeScaleClient
) -> None:
    """After a weigh-in with a weight, the next wake within POLL_INTERVAL waits."""
    entry = await _async_setup(hass)
    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()
    assert _state(hass, WEIGHT) == "87.35"

    assert not entry.runtime_data.needs_poll(make_service_info())
    assert not _needs_poll_while_asleep(entry)
    assert not entry.runtime_data.needs_poll(make_service_info())


@pytest.mark.parametrize(
    "error",
    [BleakError("disconnected"), RuntimeError("unexpected")],
    ids=["bleak", "other"],
)
async def test_drop_after_weight_frames(
    hass: HomeAssistant, mock_scale: FakeScaleClient, error: Exception
) -> None:
    """A weigh-in that fails after the weight frames clears the real-time weight."""
    await _async_setup(hass)
    mock_scale.ack_error = error
    real_time: list[str] = []
    async_track_state_change_event(
        hass,
        REAL_TIME_WEIGHT,
        lambda event: real_time.append(event.data["new_state"].state),
    )
    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()

    assert real_time == ["87.4", "87.35", STATE_UNAVAILABLE]
    assert _state(hass, WEIGHT) == STATE_UNKNOWN
    mock_scale.disconnect.assert_awaited_once()


async def test_restored_data_gets_current_descriptions(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Restored values are kept, with this version's descriptions and device info."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, title="Vitafit VT701 AA60"
    )
    entry.add_to_hass(hass)
    # Saved by an earlier version: a weight description without a device class,
    # so its entity would have no name, and a device without a manufacturer.
    hass.data[PASSIVE_UPDATE_PROCESSOR].all_restore_data[entry.entry_id] = {
        "sensor": {
            "devices": {"": {"name": "Vitafit VT701 AA60"}},
            "entity_descriptions": {
                "mass___": {"key": "mass", "native_unit_of_measurement": "kg"}
            },
            "entity_names": {},
            "entity_data": {"mass___": 80.5},
        }
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    weight = hass.states.get(WEIGHT)
    assert weight is not None
    assert weight.state == "80.5"
    assert weight.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.WEIGHT
    assert _state(hass, IMPEDANCE) == STATE_UNKNOWN
    device = device_registry.async_get_device_by_connection(
        (CONNECTION_BLUETOOTH, ADDRESS), entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == MANUFACTURER


async def test_poll_through_connectable_scanner(
    hass: HomeAssistant, mock_scale: FakeScaleClient
) -> None:
    """An advertisement from a passive scanner is polled through a connectable one."""
    await _async_setup(hass)
    info = make_service_info()
    info.connectable = False
    # The same scale, as seen by a connectable adapter or proxy.
    connectable_device = BLEDevice(ADDRESS, "Vitafit Body Fat", {"source": "proxy"})
    with (
        patch(
            "custom_components.vitafit_ble.coordinator.async_ble_device_from_address",
            return_value=connectable_device,
        ),
        patch(
            "vitafit_ble.device.establish_connection",
            AsyncMock(return_value=mock_scale),
        ) as connect,
    ):
        inject_service_info(hass, info)
        await hass.async_block_till_done()

    assert connect.call_args.args[1] is connectable_device
    assert _state(hass, WEIGHT) == "87.35"


async def test_connectable_scanner_lost(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Losing the connectable scanner before the poll is logged, and keeps the last weigh-in."""
    await _async_setup(hass)
    info = make_service_info()
    info.connectable = False
    # A connectable scanner can reach the scale when the poll is scheduled,
    # but not by the time it runs.
    with patch(
        "custom_components.vitafit_ble.coordinator.async_ble_device_from_address",
        side_effect=[BLEDevice(ADDRESS, "Vitafit Body Fat", {}), None],
    ):
        inject_service_info(hass, info)
        await hass.async_block_till_done()

    assert f"No connectable device found for {ADDRESS}" in caplog.text
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_repeated_weight_is_a_new_state(
    hass: HomeAssistant, mock_scale: FakeScaleClient
) -> None:
    """Each weigh-in writes the weight, even when it repeats the last one."""
    entry = await _async_setup(hass)
    weights: list[str] = []
    async_track_state_change_event(
        hass, WEIGHT, lambda event: weights.append(event.data["new_state"].state)
    )
    with patch(
        "homeassistant.components.bluetooth.active_update_processor"
        ".monotonic_time_coarse",
        return_value=monotonic_time_coarse() - 120,
    ):
        inject_service_info(hass, make_service_info())
        await hass.async_block_till_done()
    inject_service_info(hass, make_service_info())
    async_fire_time_changed(hass, dt_util.utcnow() + FALLBACK_POLL_INTERVAL)
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=POLL_DEFAULT_COOLDOWN + 1)
    )
    await hass.async_block_till_done()
    assert mock_scale.disconnect.await_count == 2
    assert weights == ["87.35", "87.35"]

    # The scale going to sleep isn't a weigh-in.
    entry.runtime_data._async_handle_unavailable(make_service_info())  # noqa: SLF001
    await hass.async_block_till_done()
    assert weights == ["87.35", "87.35"]
    assert _state(hass, SIGNAL_STRENGTH) == STATE_UNAVAILABLE


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
