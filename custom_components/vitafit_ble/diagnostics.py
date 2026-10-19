"""Diagnostics support for the Vitafit integration."""

from typing import Any

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.core import HomeAssistant

from . import VitafitConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VitafitConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    service_info = async_last_service_info(hass, coordinator.address, connectable=False)
    return {
        "entry": entry.as_dict(),
        "weight_only": coordinator.weight_only,
        "polling": coordinator.polling,
        "last_poll_successful": coordinator.last_poll_successful,
        "poll_failed": coordinator.poll_failed,
        # The latest advertisement, or None if the scale hasn't been seen
        # since Home Assistant started.
        "service_info": service_info
        and {
            "name": service_info.name,
            "rssi": service_info.rssi,
            "manufacturer_data": {
                company_id: data.hex()
                for company_id, data in service_info.manufacturer_data.items()
            },
            "service_data": {
                uuid: data.hex() for uuid, data in service_info.service_data.items()
            },
            "service_uuids": service_info.service_uuids,
            "source": service_info.source,
            "connectable": service_info.connectable,
        },
    }
