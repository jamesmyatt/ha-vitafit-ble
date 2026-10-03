"""Support for Vitafit sensors."""

from datetime import date, datetime
from decimal import Decimal
from typing import override

from vitafit_ble import DeviceClass, DeviceKey, SensorUpdate, Units

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from . import VitafitConfigEntry

type SensorValueType = str | int | float | date | datetime | Decimal | None

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    DeviceClass.MASS: SensorEntityDescription(
        key=DeviceClass.MASS,
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    DeviceClass.IMPEDANCE: SensorEntityDescription(
        key=DeviceClass.IMPEDANCE,
        translation_key="impedance",
        native_unit_of_measurement=Units.OHM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DeviceClass.SIGNAL_STRENGTH: SensorEntityDescription(
        key=DeviceClass.SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


def _to_entity_key(device_key: DeviceKey) -> PassiveBluetoothEntityKey:
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate[SensorValueType]:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _to_entity_key(device_key): SENSOR_DESCRIPTIONS[device_key.key]
            for device_key in sensor_update.entity_descriptions
        },
        entity_data={
            _to_entity_key(device_key): sensor_value.native_value
            for device_key, sensor_value in sensor_update.entity_values.items()
        },
        entity_names={},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitafitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vitafit sensors."""
    coordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            VitafitBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class VitafitBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[SensorValueType, SensorUpdate]
    ],
    SensorEntity,
):
    """Representation of a Vitafit sensor."""

    @property
    @override
    def native_value(self) -> SensorValueType:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
