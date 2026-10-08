"""Support for Vitafit switches."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import VitafitConfigEntry
from .coordinator import VitafitActiveBluetoothProcessorCoordinator

WEIGHT_ONLY_DESCRIPTION = SwitchEntityDescription(
    key="weight_only",
    translation_key="weight_only",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitafitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vitafit switches."""
    assert entry.unique_id is not None
    async_add_entities(
        [VitafitWeightOnlySwitch(entry.runtime_data, entry.unique_id, entry.title)]
    )


class VitafitWeightOnlySwitch(RestoreEntity, SwitchEntity):
    """Select the scale's weight-only mode, which passes no current.

    The scale's mode can't be read back, so the state is restored after a
    restart. A change applies at the next weigh-in, and the scale keeps the mode
    for later weigh-ins without Home Assistant.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = WEIGHT_ONLY_DESCRIPTION

    def __init__(
        self,
        coordinator: VitafitActiveBluetoothProcessorCoordinator,
        address: str,
        name: str,
    ) -> None:
        """Initialise the switch for the scale at ``address``."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{address}-{WEIGHT_ONLY_DESCRIPTION.key}"
        # Same device as the sensors, which share the Bluetooth connection.
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)}, name=name
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        self._set(is_on=state is not None and state.state == STATE_ON)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Use weight-only mode from the next weigh-in."""
        self._set(is_on=True)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Measure impedance from the next weigh-in."""
        self._set(is_on=False)
        self.async_write_ha_state()

    def _set(self, *, is_on: bool) -> None:
        self._attr_is_on = is_on
        self._coordinator.weight_only = is_on
