"""Fixtures for Vitafit tests."""

from collections.abc import AsyncGenerator, Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vitafit_ble.protocol import ACK_STABLE_WEIGHT, start_commands

from homeassistant.core import HomeAssistant

# Frames captured from a real VT701: 87.35 kg (stable) and 466 ohm.
STABLE = bytes.fromhex("5a 0a 26 10 02 00 00 21 22 1f 22 aa")
IMPEDANCE = bytes.fromhex("5a 0b 26 11 00 00 00 00 00 01 d2 ef aa")
# The last command the integration sends before waiting for a stable weight.
HELLO_COMMAND = tuple(start_commands())[-1]


class FakeScaleClient:
    """GATT client that replies like the scale."""

    def __init__(self) -> None:
        """Initialise."""
        self._callback: Callable[[Any, bytearray], None] | None = None
        self.disconnect = AsyncMock()
        self.written: list[bytes] = []

    async def start_notify(
        self, _: str, callback: Callable[[Any, bytearray], None]
    ) -> None:
        """Store the notification callback."""
        self._callback = callback

    async def write_gatt_char(self, _: str, data: bytes, **__: Any) -> None:
        """Reply to commands."""
        assert self._callback is not None
        self.written.append(data)
        if data == HELLO_COMMAND:
            self._callback(None, bytearray(STABLE))
        elif data == ACK_STABLE_WEIGHT:
            self._callback(None, bytearray(IMPEDANCE))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations."""


@pytest.fixture(autouse=True)
async def enable_bluetooth(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> AsyncGenerator[None]:
    """Set up the Bluetooth integration with a mocked adapter."""
    entry = MockConfigEntry(domain="bluetooth", unique_id="00:00:00:00:00:01")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    yield
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Enable entities that are disabled by default."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
        new_callable=PropertyMock,
    ):
        yield


@pytest.fixture
def mock_scale() -> Generator[FakeScaleClient]:
    """Patch the connection to return a fake scale."""
    client = FakeScaleClient()
    with patch(
        "vitafit_ble.parser.establish_connection", AsyncMock(return_value=client)
    ):
        yield client
