"""Test the Vitafit config flow."""

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitafit_ble.const import DOMAIN
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ADDRESS, NOT_VITAFIT_SERVICE_INFO, VITAFIT_SERVICE_INFO

TITLE = "Vitafit VT701 AA60"


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery and confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VITAFIT_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch("custom_components.vitafit_ble.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {}
    assert result["result"].unique_id == ADDRESS


async def test_bluetooth_discovery_not_supported(hass: HomeAssistant) -> None:
    """Test discovery of an unsupported device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_VITAFIT_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test discovery of a configured device."""
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VITAFIT_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_setup(hass: HomeAssistant) -> None:
    """Test manual setup."""
    with patch(
        "custom_components.vitafit_ble.config_flow.async_discovered_service_info",
        return_value=[VITAFIT_SERVICE_INFO, NOT_VITAFIT_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("custom_components.vitafit_ble.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["result"].unique_id == ADDRESS


async def test_user_no_devices(hass: HomeAssistant) -> None:
    """Test manual setup with no devices."""
    with patch(
        "custom_components.vitafit_ble.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_skips_configured(hass: HomeAssistant) -> None:
    """Test manual setup ignores configured devices."""
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS).add_to_hass(hass)
    with patch(
        "custom_components.vitafit_ble.config_flow.async_discovered_service_info",
        return_value=[VITAFIT_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_setup_replaces_discovery(hass: HomeAssistant) -> None:
    """Test manual setup aborts the discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VITAFIT_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.vitafit_ble.config_flow.async_discovered_service_info",
        return_value=[VITAFIT_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    with patch("custom_components.vitafit_ble.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not hass.config_entries.flow.async_progress(DOMAIN)
