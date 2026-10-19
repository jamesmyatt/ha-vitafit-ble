"""Test the Vitafit repair issue."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from bleak.backends.device import BLEDevice
from bluetooth_data_tools import monotonic_time_coarse
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.vitafit_ble.const import DOMAIN
from custom_components.vitafit_ble.coordinator import (
    FALLBACK_POLL_INTERVAL,
    no_connectable_issue_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from . import ADDRESS, inject_service_info, make_service_info
from .conftest import FakeScaleClient

ISSUE_ID = no_connectable_issue_id(ADDRESS)
COORDINATOR = "custom_components.vitafit_ble.coordinator"
CONNECTABLE_DEVICE = BLEDevice(ADDRESS, "Vitafit Body Fat", {})


class FakeClock:
    """Monotonic clock for the coordinator and the library's awake()."""

    def __init__(self) -> None:
        """Start at the real time."""
        self.now = monotonic_time_coarse()
        self.timer_ticks = 0

    def __call__(self) -> float:
        """Return the current time."""
        return self.now


@pytest.fixture
def clock() -> Generator[FakeClock]:
    """Patch the clocks that decide whether the scale is awake."""
    clock = FakeClock()
    with (
        patch(f"{COORDINATOR}.monotonic_time_coarse", clock),
        patch("vitafit_ble.device.monotonic_time_coarse", clock),
    ):
        yield clock


@pytest.fixture
def create_issue() -> Generator[MagicMock]:
    """Count the issues created."""
    with patch.object(
        ir, "async_create_issue", wraps=ir.async_create_issue
    ) as create_issue:
        yield create_issue


async def _async_setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, title="Vitafit VT701 AA60"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _async_check(
    hass: HomeAssistant,
    clock: FakeClock,
    seconds: float,
    *,
    advertise: bool = True,
    connectable_device: BLEDevice | None = None,
) -> None:
    """Advance the clock, then let the fallback timer check the scale.

    ``advertise`` sends a fresh advertisement from a passive scanner first.
    ``connectable_device`` is what a connectable scanner sees, if any.
    """
    clock.now += seconds
    clock.timer_ticks += 1
    with patch(
        f"{COORDINATOR}.async_ble_device_from_address", return_value=connectable_device
    ):
        if advertise:
            info = make_service_info()
            info.connectable = False
            info.time = clock.now
            inject_service_info(hass, info)
        async_fire_time_changed(
            hass, dt_util.utcnow() + FALLBACK_POLL_INTERVAL * clock.timer_ticks
        )
        await hass.async_block_till_done()


async def _async_raise_issue(hass: HomeAssistant, clock: FakeClock) -> None:
    """Keep the scale awake without a connectable scanner past the grace period."""
    await _async_check(hass, clock, 0)
    await _async_check(hass, clock, 3)
    await _async_check(hass, clock, 3)


async def test_issue_raised_after_grace_period(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_scale: FakeScaleClient,
    clock: FakeClock,
    create_issue: MagicMock,
) -> None:
    """The issue is raised once, after 5 s awake, and the next weigh-in clears it."""
    await _async_setup(hass)
    await _async_check(hass, clock, 0)
    await _async_check(hass, clock, 3)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None

    await _async_check(hass, clock, 3)
    await _async_check(hass, clock, 3)
    create_issue.assert_called_once()
    mock_scale.disconnect.assert_not_awaited()
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "no_connectable_scanner"
    assert issue.severity is ir.IssueSeverity.WARNING
    assert not issue.is_fixable
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["name"] == "Vitafit VT701 AA60"

    # A connectable proxy now reaches the scale, so the weigh-in goes ahead.
    await _async_check(hass, clock, 1, connectable_device=CONNECTABLE_DEVICE)
    mock_scale.disconnect.assert_awaited_once()
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_no_issue_if_connectable_scanner_hears_scale_soon(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_scale: FakeScaleClient,
    clock: FakeClock,
    create_issue: MagicMock,
) -> None:
    """A passive scanner hearing the scale first doesn't raise the issue."""
    await _async_setup(hass)
    await _async_check(hass, clock, 0)
    await _async_check(hass, clock, 1, connectable_device=CONNECTABLE_DEVICE)

    mock_scale.disconnect.assert_awaited_once()
    create_issue.assert_not_called()
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_grace_period_restarts_after_sleep(
    hass: HomeAssistant, clock: FakeClock, create_issue: MagicMock
) -> None:
    """Time unreachable during an earlier wake doesn't count towards the next."""
    await _async_setup(hass)
    await _async_check(hass, clock, 0)
    # The scale sleeps, so its last advertisement gets old.
    await _async_check(hass, clock, 30, advertise=False)
    # It wakes again, still without a connectable scanner.
    await _async_check(hass, clock, 70)
    create_issue.assert_not_called()


async def test_issue_cleared_after_reload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_scale: FakeScaleClient,
    clock: FakeClock,
) -> None:
    """A weigh-in after reloading the integration clears an earlier issue."""
    entry = await _async_setup(hass)
    await _async_raise_issue(hass, clock)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None

    # Reload while the scale is asleep, so nothing raises the issue again.
    clock.now += 30
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await _async_check(hass, clock, 1, connectable_device=CONNECTABLE_DEVICE)

    mock_scale.disconnect.assert_awaited_once()
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_issue_deleted_with_entry(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, clock: FakeClock
) -> None:
    """Removing the config entry deletes its issue."""
    entry = await _async_setup(hass)
    await _async_raise_issue(hass, clock)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
