"""Tests for the Vitafit integration."""

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bluetooth_data_tools import monotonic_time_coarse

from homeassistant.components.bluetooth import (
    SOURCE_LOCAL,
    BluetoothServiceInfoBleak,
    async_get_advertisement_callback,
)
from homeassistant.core import HomeAssistant

ADDRESS = "F8:8F:C8:14:AA:60"


def make_service_info(name: str = "Vitafit Body Fat") -> BluetoothServiceInfoBleak:
    """Return a connectable advertisement from the scale."""
    advertisement = AdvertisementData(
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        rssi=-60,
        platform_data=((),),
        tx_power=-127,
    )
    return BluetoothServiceInfoBleak(
        name=name,
        address=ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source=SOURCE_LOCAL,
        device=BLEDevice(ADDRESS, name, {}),
        advertisement=advertisement,
        connectable=True,
        time=monotonic_time_coarse(),
        tx_power=-127,
    )


VITAFIT_SERVICE_INFO = make_service_info()
NOT_VITAFIT_SERVICE_INFO = make_service_info("Other")


def inject_service_info(hass: HomeAssistant, info: BluetoothServiceInfoBleak) -> None:
    """Inject an advertisement into the Bluetooth manager."""
    async_get_advertisement_callback(hass)(info)
