"""The Vitafit integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .coordinator import (
    VitafitActiveBluetoothProcessorCoordinator,
    no_connectable_issue_id,
)

type VitafitConfigEntry = ConfigEntry[VitafitActiveBluetoothProcessorCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: VitafitConfigEntry) -> bool:
    """Set up Vitafit scale from a config entry."""
    coordinator = VitafitActiveBluetoothProcessorCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Only start after all platforms have had a chance to subscribe.
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitafitConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: VitafitConfigEntry) -> None:
    """Remove the scale's repair issue with its config entry."""
    assert entry.unique_id is not None
    ir.async_delete_issue(hass, DOMAIN, no_connectable_issue_id(entry.unique_id))
