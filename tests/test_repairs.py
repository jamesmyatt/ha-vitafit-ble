"""Test the Vitafit repair issue."""

from unittest.mock import patch

from bleak.backends.device import BLEDevice
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
CONNECTABLE_LOOKUP = (
    "custom_components.vitafit_ble.coordinator.async_ble_device_from_address"
)


async def _async_setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, title="Vitafit VT701 AA60"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _async_wake_unreachable(hass: HomeAssistant) -> None:
    """Wake the scale where only a passive scanner hears it."""
    info = make_service_info()
    info.connectable = False
    with patch(CONNECTABLE_LOOKUP, return_value=None):
        inject_service_info(hass, info)
        await hass.async_block_till_done()
        # The timer checks again while the scale is awake.
        async_fire_time_changed(hass, dt_util.utcnow() + FALLBACK_POLL_INTERVAL)
        await hass.async_block_till_done()


async def test_issue_raised_and_cleared(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, mock_scale: FakeScaleClient
) -> None:
    """No connectable scanner raises an issue once; the next weigh-in clears it."""
    await _async_setup(hass)
    with patch.object(
        ir, "async_create_issue", wraps=ir.async_create_issue
    ) as create_issue:
        await _async_wake_unreachable(hass)

    mock_scale.disconnect.assert_not_awaited()
    create_issue.assert_called_once()
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "no_connectable_scanner"
    assert issue.severity is ir.IssueSeverity.WARNING
    assert not issue.is_fixable
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["name"] == "Vitafit VT701 AA60"

    # A connectable proxy now reaches the scale, so the weigh-in goes ahead.
    with patch(
        CONNECTABLE_LOOKUP, return_value=BLEDevice(ADDRESS, "Vitafit Body Fat", {})
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + FALLBACK_POLL_INTERVAL * 2)
        await hass.async_block_till_done()

    mock_scale.disconnect.assert_awaited_once()
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_issue_deleted_with_entry(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Removing the config entry deletes its issue."""
    entry = await _async_setup(hass)
    await _async_wake_unreachable(hass)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
