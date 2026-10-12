"""The Vitafit coordinator."""

from datetime import datetime, timedelta
import logging
from typing import override

from bluetooth_data_tools import monotonic_time_coarse
from vitafit_ble import VitafitSession, WeightFrame, async_poll, poll_needed
from vitafit_ble.const import ADVERTISEMENT_MAX_AGE

from homeassistant.components.bluetooth import (
    BluetoothReachabilityIntent,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_address_reachability_diagnostics,
    async_ble_device_from_address,
    async_last_service_info,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, IMPEDANCE, MASS, REAL_TIME_WEIGHT, SIGNAL_STRENGTH

_LOGGER = logging.getLogger(__name__)

# The longest wait between the scale waking and the poll starting.
FALLBACK_POLL_INTERVAL = timedelta(seconds=5)

ISSUE_NO_CONNECTABLE_SCANNER = "no_connectable_scanner"
# How long the scale must be awake with no connectable scanner before the issue
# is raised. The fallback timer's checks make it 5-10 s after the scale wakes.
NO_CONNECTABLE_GRACE = 5.0
TROUBLESHOOTING_URL = "https://github.com/jamesmyatt/ha-vitafit-ble#troubleshooting"


def no_connectable_issue_id(address: str) -> str:
    """Return the ID of the repair issue for the scale at ``address``."""
    return f"{ISSUE_NO_CONNECTABLE_SCANNER}_{address}"


type VitafitDataUpdate = PassiveBluetoothDataUpdate[float | None]


def _data_update(values: dict[str, float | None]) -> VitafitDataUpdate:
    """Return an update for the given sensor keys and values."""
    return PassiveBluetoothDataUpdate(
        entity_data={
            PassiveBluetoothEntityKey(key, None): value for key, value in values.items()
        }
    )


class VitafitActiveBluetoothProcessorCoordinator(
    ActiveBluetoothProcessorCoordinator[VitafitDataUpdate]
):
    """Coordinator for Vitafit scales.

    Advertisements update the signal strength, each weight frame during the poll
    updates the real-time weight, and the poll's result updates the weight and
    impedance.
    """

    weight_only: bool
    """Select the scale's weight-only mode at the next weigh-in; set by the switch."""
    polling: bool
    """True while connected to the scale for a weigh-in."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Vitafit Bluetooth processor coordinator."""
        address = entry.unique_id
        assert address is not None
        self.weight_only = False
        self.polling = False
        self._name = entry.title
        self._no_connectable_issue = False
        self._unreachable_since: float | None = None
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=address,
            mode=BluetoothScanningMode.PASSIVE,
            update_method=self._async_on_advertisement,
            needs_poll_method=self._async_needs_poll,
            poll_method=self._async_poll_data,
            # Advertisements from non-connectable scanners are taken too,
            # since the poll swaps the BLEDevice for a connectable one.
            connectable=False,
        )

    @override
    async def _async_poll_data(
        self, last_service_info: BluetoothServiceInfoBleak
    ) -> VitafitDataUpdate:
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
        session = VitafitSession(weight_only=self.weight_only)
        session.register_callback(WeightFrame, self._async_on_weight)
        self.polling = True
        try:
            measurement = await async_poll(connectable_device, session)
        finally:
            # Disconnected, so the real-time weight goes unavailable. It's
            # pushed here because the base class sends no update for a poll
            # that raises, and the entity would keep showing the last frame.
            self.polling = False
            self.async_set_updated_data(_data_update({REAL_TIME_WEIGHT: None}))
        # A failed weigh-in keeps the last weight and impedance.
        if measurement is None:
            return _data_update({})
        return _data_update(
            {MASS: measurement.weight_kg, IMPEDANCE: measurement.impedance_ohm}
        )

    @callback
    def _async_on_weight(self, frame: WeightFrame) -> None:
        """Push each weight frame during the poll as the real-time weight."""
        self.async_set_updated_data(_data_update({REAL_TIME_WEIGHT: frame.weight_kg}))

    @callback
    def _async_on_advertisement(
        self, service_info: BluetoothServiceInfoBleak
    ) -> VitafitDataUpdate:
        return _data_update({SIGNAL_STRENGTH: service_info.rssi})

    @callback
    def _async_needs_poll(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        now = monotonic_time_coarse()
        if now - service_info.time > ADVERTISEMENT_MAX_AGE:
            # Asleep, so the next wake starts a new grace period.
            self._unreachable_since = None
        # Only poll if hass isn't stopping, no poll is running, a poll is due,
        # and a connectable adapter or proxy can reach the scale.
        if (
            self.hass.is_stopping
            or self.polling
            or not poll_needed(service_info, last_poll)
        ):
            return False
        # A poll is due, so the scale is awake. Without a connectable adapter or
        # proxy, every weigh-in would be missed, so tell the user. A passive
        # scanner can hear the scale a moment before a connectable one does, so
        # wait for the grace period first.
        if not async_ble_device_from_address(
            self.hass, service_info.device.address, connectable=True
        ):
            if self._unreachable_since is None:
                self._unreachable_since = now
            elif now - self._unreachable_since >= NO_CONNECTABLE_GRACE:
                self._async_create_no_connectable_issue()
            return False
        self._unreachable_since = None
        self._no_connectable_issue = False
        # Unconditional, as the issue outlives a reload of the integration.
        ir.async_delete_issue(self.hass, DOMAIN, no_connectable_issue_id(self.address))
        return True

    @callback
    def _async_create_no_connectable_issue(self) -> None:
        """Raise a repair issue that no connectable scanner can reach the scale."""
        if self._no_connectable_issue:
            return
        self._no_connectable_issue = True
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            no_connectable_issue_id(self.address),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            learn_more_url=TROUBLESHOOTING_URL,
            translation_key=ISSUE_NO_CONNECTABLE_SCANNER,
            translation_placeholders={
                "name": self._name,
                "reason": async_address_reachability_diagnostics(
                    self.hass, self.address, BluetoothReachabilityIntent.CONNECTION
                ),
            },
        )

    @callback
    @override
    def _async_start(self) -> None:
        """Start the callbacks and the fallback poll timer."""
        super()._async_start()
        self._on_stop.append(
            async_track_time_interval(
                self.hass, self._async_schedule_poll, FALLBACK_POLL_INTERVAL
            )
        )

    @callback
    def _async_schedule_poll(self, _: datetime) -> None:
        """Poll if the scale is awake but its advertisements weren't dispatched."""
        # HA doesn't dispatch an advertisement that repeats the last one, so a
        # weigh-in soon after the previous one (before HA marks the scale
        # unavailable) wouldn't be polled. The Bluetooth manager still records
        # each advertisement's time, which poll_needed checks for recency.
        service_info = (
            async_last_service_info(self.hass, self.address, connectable=False)
            or self._last_service_info
        )
        if service_info and self.needs_poll(service_info):
            # The base _async_poll polls _last_service_info.
            self._last_service_info = service_info
            self._debounced_poll.async_schedule_call()
