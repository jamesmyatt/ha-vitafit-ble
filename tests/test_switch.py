"""Test the Vitafit weight-only mode switch."""

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)
from vitafit_ble.protocol import start_commands

from custom_components.vitafit_ble.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import ADDRESS, inject_service_info, make_service_info
from .conftest import FakeScaleClient

ENTITY_ID = "switch.vitafit_vt701_aa60_weight_only_mode"
NORMAL_MODE_COMMAND = next(start_commands())
WEIGHT_ONLY_MODE_COMMAND = next(start_commands(weight_only=True))


async def _async_setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, title="Vitafit VT701 AA60"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _async_switch(hass: HomeAssistant, service: str) -> None:
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )


async def test_default_measures_impedance(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_scale: FakeScaleClient,
) -> None:
    """The switch starts off, so a weigh-in selects normal mode."""
    await _async_setup(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity is not None
    assert entity.entity_category is EntityCategory.CONFIG
    assert entity.unique_id == f"{ADDRESS}-weight_only"

    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()
    assert mock_scale.written[0] == NORMAL_MODE_COMMAND


async def test_weight_only(hass: HomeAssistant, mock_scale: FakeScaleClient) -> None:
    """Turning the switch on selects weight-only mode at the next weigh-in."""
    entry = await _async_setup(hass)

    await _async_switch(hass, SERVICE_TURN_ON)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert entry.runtime_data.weight_only

    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()
    assert mock_scale.written[0] == WEIGHT_ONLY_MODE_COMMAND

    await _async_switch(hass, SERVICE_TURN_OFF)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert not entry.runtime_data.weight_only


async def test_restore_state(hass: HomeAssistant) -> None:
    """The switch state survives a restart, because the scale can't report it."""
    mock_restore_cache(hass, [State(ENTITY_ID, STATE_ON)])
    entry = await _async_setup(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert entry.runtime_data.weight_only
