# CLAUDE.md: ha-vitafit-ble

Home Assistant custom integration (HACS) for the Vitafit VT701 Bluetooth body fat scale. Domain `vitafit_ble`, minimum HA 2026.9 (Python 3.14.2 or later).

Everything about the protocol (weigh-in sequence, polling, timeouts) is in the sibling library repo `../vitafit-ble`, PyPI package `vitafit-ble`; see its `CLAUDE.md` and `docs/protocol.md`. It's pinned in `manifest.json` and `requirements_dev.txt`. Keep both repos side by side.

## Decisions

Owner's decisions. Don't revisit them without asking.

- **Scope:** weight and impedance sensors, a real-time weight sensor (added 10 Oct 2026), the default RSSI diagnostic, and a weight-only mode switch. No body composition (nothing needing height, age or sex) and no assigning readings to people; HA can build these.
- **Weight-only mode:** a config switch (so automations can use it), off by default. Its state is restored after a restart, because the scale's mode can't be read back. Every connection sets the mode again.
- **Patterns:** follow HA core `eufylife_ble` (owner's decision, 10 Oct 2026) for how a scale is presented: a real-time weight while connected, and the final weight kept. Keep the `inkbird`-style `ActiveBluetoothProcessorCoordinator` (owner chose it over Eufy's plain callback), because inkbird also reads devices by GATT polling. Keep both repos as simple as possible (owner, 11 Oct 2026): the library has plain functions and `VitafitSession`, with no device class or live state.
- **Repo template:** follow [ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint), except: `uv pip` locally (CI uses pip), pre-commit instead of `lint.yml`, and tests and `test.yml`, which the blueprint doesn't have.
- **Availability:** like `eufylife_ble`. Weight and impedance are always available and keep the last weigh-in (the processor restores its data after a restart). Real-time weight is available only while connected. Signal strength follows the core default. Disconnect as soon as the weigh-in ends, unlike Eufy's 120 s, so other apps can use the scale.
- **Detection:** local name `Vitafit*` only. The manufacturer data uses ID `0xFFFF`, the SIG test ID many devices share, so it isn't matched.
- **Display unit:** the integration never sets it, so the scale keeps its own. Readings are always kg.

## Architecture

- `coordinator.py`: `VitafitActiveBluetoothProcessorCoordinator`, based on core `inkbird/coordinator.py`. It listens passively, so advertisements can come from any proxy. It polls when HA isn't stopping, the library's `poll_needed` is true, and a connectable adapter or proxy can reach the scale. Its data is a `PassiveBluetoothDataUpdate` keyed by the sensor keys in `const.py`: advertisements set the signal strength, the poll (which swaps in a connectable `BLEDevice` and calls the library's `async_poll` with a `VitafitSession` using the coordinator's `weight_only`) sets weight and impedance. The session has a `WeightFrame` callback, `_async_on_weight`, that pushes each weight frame as the real-time weight with `async_set_updated_data`. A failed weigh-in leaves weight and impedance out of the update, so the last one stays. When the connection ends, however the poll ends, the coordinator clears the real-time weight with `async_set_updated_data`, because the base class sends no update for a poll that raises. HA doesn't dispatch an advertisement that repeats the last one, so a weigh-in soon after another one wouldn't be polled. Like inkbird, a fallback timer (`FALLBACK_POLL_INTERVAL`, 5 s) checks the Bluetooth manager's latest advertisement. It relies on the recency check in `poll_needed` (`ADVERTISEMENT_MAX_AGE`, 5 s), so it doesn't poll a sleeping scale. The interval only sets how long a repeat weigh-in waits for its poll. `polling` is true while connected: it stops the timer from queuing a second poll, and sets the real-time weight's availability.
- `__init__.py`: stores the coordinator as `entry.runtime_data`.
- `sensor.py`: `PassiveBluetoothDataProcessor` entities with keys `mass`, `impedance`, `real_time_weight` and `signal_strength` (the first three keep the unique IDs from when the keys came from `sensor-state-data`). The processor's update method is the identity, as the coordinator builds the updates. The processor only creates entities when their descriptions arrive, and the coordinator's updates carry only values. So setup registers the processor (which restores the last data), then sets every description and the device info (manufacturer and model from `vitafit_ble.const`), then adds the entities listener. Entities keep the description and device info they're created with, so this order means restored data never keeps an older version's descriptions, and every sensor exists before the first weigh-in. `available` is overridden per key, not per description, because restored descriptions come back as plain `SensorEntityDescription`s. Impedance's unit stays `ohm` (`UNIT_OHM`), as HA has none.
- `switch.py`: the weight-only switch, a `RestoreEntity` like core `voip`'s. It sets `coordinator.weight_only`, and joins the sensors' device through the Bluetooth connection, because it's created before the first advertisement.
- `diagnostics.py`: config entry diagnostics, with the coordinator's flags and the latest advertisement. The advertisement's fields are copied out, because its `as_dict()` holds `bytes` and Bleak objects that HA's JSON encoder can't serialise.
- `config_flow.py`: Bluetooth discovery, plus a user step that requests an active scan first.
- 2026.9 constraints: config flows use `import voluptuous as vol` (later HA releases alias it to Probatio). `no_devices_found` has its own string, because central abort translations need 2026.10. Custom integrations need `translations/en.json`, not `strings.json`.
- `brand/`: the Vitafit app's icon, from its Google Play listing (owner's choice, 11 Oct 2026). vitafitapp.com uses the same icon, but only as a lower-quality palette PNG, and has no wordmark or SVG. HACS requires it.

## Commands

Run from the repo root. HA doesn't run on Windows (`fcntl`), so use Linux, WSL or the dev container (`.devcontainer.json`, venv at `/home/vscode/.venv`).

```sh
uv venv --python 3.14
. .venv/bin/activate
scripts/setup                   # requirements_test.txt and pre-commit install
uv pip install -e ../vitafit-ble   # optional: unreleased library changes
scripts/develop                 # run HA with config/configuration.yaml (debug logging)

pre-commit run --all-files      # ruff, prettier, codespell and others; scripts/lint does the same
mypy custom_components
pytest --cov=custom_components.vitafit_ble --cov-report=term-missing
```

Requirements files: `common` (pip, CI only), `lint` (pre-commit), `dev` (+ `colorlog`, `homeassistant`, `vitafit-ble`), `test` (+ mypy, the test harness, and `aiousbwatcher` and `serialx`, which the `bluetooth` integration needs through `usb`). `pyproject.toml` only holds the pytest and mypy config.

CI: `test.yml` (mypy and pytest), `validate.yml` (hassfest on HA dev, and HACS), and pre-commit.ci (configured in `.pre-commit-config.yaml`). Mypy isn't a pre-commit hook, because it needs `homeassistant` installed.

Bluetooth in `scripts/develop` needs an ESPHome proxy, because neither WSL nor the container can reach the PC's adapter.

## Version pins

Keep these on the minimum HA version (2026.9.4) and update them together, by hand, when the owner raises it:

- `homeassistant` and the test harness (`pytest-homeassistant-custom-component` 0.13.367)
- core's ruff (0.16.3, a local hook in `.pre-commit-config.yaml`), mypy (2.3.1) and colorlog (6.10.1), plus `aiousbwatcher` and `serialx`
- `hacs.json`'s `homeassistant`
- `.ruff.toml`, copied from core's `[tool.ruff.lint]`. Its only local additions are `target-version`, `custom_components` as first-party, and a `TID251` ignore for `tests/**`. Don't tune it.

`.github/renovate.json` disables updates to these. Renovate still updates Actions SHAs, dev container features and `vitafit-ble`, bumping the `manifest.json` pin in the same PR.

## Open items

- On the real scale: check the real-time weight updates while standing on it (the scale streams about every 0.36 s), and that two weigh-ins about 5 minutes apart are both polled.
