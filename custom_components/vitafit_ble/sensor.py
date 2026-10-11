"""Support for Vitafit sensors."""

from typing import cast, override

from vitafit_ble.const import MANUFACTURER, MODEL

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VitafitConfigEntry
from .const import IMPEDANCE, MASS, REAL_TIME_WEIGHT, SIGNAL_STRENGTH, UNIT_OHM
from .coordinator import VitafitActiveBluetoothProcessorCoordinator, VitafitDataUpdate

# The coordinator pushes updates; entities don't poll.
PARALLEL_UPDATES = 0

type SensorValueType = float | None

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    MASS: SensorEntityDescription(
        key=MASS,
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    IMPEDANCE: SensorEntityDescription(
        key=IMPEDANCE,
        translation_key="impedance",
        native_unit_of_measurement=UNIT_OHM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # No state class, so the settling readings stay out of long-term statistics.
    REAL_TIME_WEIGHT: SensorEntityDescription(
        key=REAL_TIME_WEIGHT,
        translation_key="real_time_weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=2,
    ),
    SIGNAL_STRENGTH: SensorEntityDescription(
        key=SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}

# The last weigh-in, kept while the scale sleeps and restored after a restart.
ALWAYS_AVAILABLE = {MASS, IMPEDANCE}


def _seed_entities(
    processor: PassiveBluetoothDataProcessor[SensorValueType, VitafitDataUpdate],
    name: str,
) -> None:
    """Create the sensors that weren't restored, before the first advertisement."""
    data = processor.data
    seed = PassiveBluetoothDataUpdate[SensorValueType](
        entity_descriptions={
            entity_key: description
            for key, description in SENSOR_DESCRIPTIONS.items()
            if (entity_key := PassiveBluetoothEntityKey(key, None))
            not in data.entity_descriptions
        },
    )
    if not seed.entity_descriptions:
        return
    if None not in data.devices:
        # Entities keep the device info they're created with.
        seed.devices[None] = DeviceInfo(
            name=name, manufacturer=MANUFACTURER, model=MODEL
        )
    data.update(seed)
    processor.async_update_listeners(data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitafitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vitafit sensors."""
    # The coordinator already builds the data updates.
    processor = PassiveBluetoothDataProcessor[SensorValueType, VitafitDataUpdate](
        lambda update: update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            VitafitBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        entry.runtime_data.async_register_processor(processor, SensorEntityDescription)
    )
    _seed_entities(processor, entry.title)


class VitafitBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[SensorValueType, VitafitDataUpdate]
    ],
    SensorEntity,
):
    """Representation of a Vitafit sensor."""

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available.

        The real-time weight is available only while connected. The weight and
        impedance are always available, like eufylife_ble's weight. The signal
        strength follows the scale's advertisements.
        """
        key = self.entity_key.key
        if key == REAL_TIME_WEIGHT:
            coordinator = cast(
                VitafitActiveBluetoothProcessorCoordinator,
                self.processor.coordinator,
            )
            return coordinator.polling
        if key in ALWAYS_AVAILABLE:
            return True
        return super().available

    @property
    @override
    def native_value(self) -> SensorValueType:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
