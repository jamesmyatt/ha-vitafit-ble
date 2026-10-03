"""The Vitafit integration."""

import logging

from vitafit_ble import SensorUpdate, VitafitBluetoothDeviceData

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CoreState, HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type VitafitConfigEntry = ConfigEntry[ActiveBluetoothProcessorCoordinator[SensorUpdate]]


async def async_setup_entry(hass: HomeAssistant, entry: VitafitConfigEntry) -> bool:
    """Set up Vitafit scale from a config entry."""
    address = entry.unique_id
    assert address is not None
    data = VitafitBluetoothDeviceData()

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        # Only poll if hass is running, a poll is due,
        # and a connectable adapter or proxy can reach the scale.
        return (
            hass.state is CoreState.running
            and data.poll_needed(service_info, last_poll)
            and bool(
                async_ble_device_from_address(
                    hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_poll(service_info: BluetoothServiceInfoBleak) -> SensorUpdate:
        # The advertisement may have come from a passive scanner,
        # so swap it for a connectable device.
        if service_info.connectable:
            connectable_device = service_info.device
        elif device := async_ble_device_from_address(
            hass, service_info.device.address, connectable=True
        ):
            connectable_device = device
        else:
            raise RuntimeError(
                f"No connectable device found for {service_info.device.address}"
            )
        return await data.async_poll(connectable_device)

    coordinator = entry.runtime_data = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=data.update,
        needs_poll_method=_needs_poll,
        poll_method=_async_poll,
        connectable=False,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Only start after all platforms have had a chance to subscribe.
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitafitConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
