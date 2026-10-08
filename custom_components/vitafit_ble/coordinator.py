"""The Vitafit coordinator."""

import logging
from typing import override

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
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)


class VitafitActiveBluetoothProcessorCoordinator(
    ActiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Coordinator for Vitafit scales."""

    _data: VitafitBluetoothDeviceData
    weight_only: bool
    """Select the scale's weight-only mode at the next weigh-in; set by the switch."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Vitafit Bluetooth processor coordinator."""
        address = entry.unique_id
        assert address is not None
        self._data = VitafitBluetoothDeviceData()
        self.weight_only = False
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=address,
            mode=BluetoothScanningMode.PASSIVE,
            update_method=self._data.update,
            needs_poll_method=self._async_needs_poll,
            poll_method=self._async_poll_data,
            # Advertisements from non-connectable scanners are taken too,
            # since the poll swaps the BLEDevice for a connectable one.
            connectable=False,
        )

    @override
    async def _async_poll_data(
        self, last_service_info: BluetoothServiceInfoBleak
    ) -> SensorUpdate:
        """Poll the scale for one weigh-in."""
        # The advertisement may have come from a passive scanner,
        # so swap it for a connectable device.
        if last_service_info.connectable:
            connectable_device = last_service_info.device
        elif device := async_ble_device_from_address(
            self.hass, last_service_info.device.address, connectable=True
        ):
            connectable_device = device
        else:
            raise RuntimeError(
                f"No connectable device found for {last_service_info.device.address}"
            )
        return await self._data.async_poll(
            connectable_device, weight_only=self.weight_only
        )

    @callback
    def _async_needs_poll(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        # Only poll if hass isn't stopping, a poll is due,
        # and a connectable adapter or proxy can reach the scale.
        return (
            not self.hass.is_stopping
            and self._data.poll_needed(service_info, last_poll)
            and bool(
                async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )
