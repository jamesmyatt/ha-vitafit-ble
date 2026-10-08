# CLAUDE.md: ha-vitafit-ble

Home Assistant custom integration (HACS) for the Vitafit VT701 Bluetooth body fat scale. Domain `vitafit_ble`, minimum HA 2026.9 (Python 3.14.2 or later).

Everything about the protocol (weigh-in sequence, polling, timeouts) is in the sibling library repo `../vitafit-ble`, PyPI package `vitafit-ble`; see its `CLAUDE.md` and `docs/protocol.md`. It's pinned in `manifest.json` and `requirements_dev.txt`. Keep both repos side by side.

## Decisions

Owner's decisions. Don't revisit them without asking.

- **Scope:** weight and impedance sensors, the default RSSI diagnostic, and a weight-only mode switch. No body composition (nothing needing height, age or sex) and no assigning readings to people; HA can build these.
- **Weight-only mode:** a config switch (so automations can use it), off by default. Its state is restored after a restart, because the scale's mode can't be read back. Every connection sets the mode again.
- **Patterns:** follow HA core `inkbird` / `inkbird-ble`, because inkbird also reads devices by GATT polling.
- **Repo template:** follow [ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint), except: `uv pip` locally (CI uses pip), pre-commit instead of `lint.yml`, and tests and `test.yml`, which the blueprint doesn't have.
- **Availability:** core default, so entities are unavailable while the scale sleeps and after a restart. (`oralb` instead overrides `available` and `assumed_state`; adding those to `VitafitBluetoothSensorEntity` would change this.)
- **Detection:** local name `Vitafit*` only. The manufacturer data uses ID `0xFFFF`, the SIG test ID many devices share, so it isn't matched.
- **Display unit:** the integration never sets it, so the scale keeps its own. Readings are always kg.

## Architecture

- `coordinator.py`: `VitafitActiveBluetoothProcessorCoordinator`, based on core `inkbird/coordinator.py`. It listens passively, so advertisements can come from any proxy. It polls when HA isn't stopping, the library's `poll_needed` is true, and a connectable adapter or proxy can reach the scale. The poll swaps in a connectable `BLEDevice` and calls the library's `async_poll` with the coordinator's `weight_only`.
- `__init__.py`: stores the coordinator as `entry.runtime_data`.
- `sensor.py`: `PassiveBluetoothDataProcessor` entities with keys `mass`, `impedance` and `signal_strength`.
- `switch.py`: the weight-only switch, a `RestoreEntity` like core `voip`'s. It sets `coordinator.weight_only`, and joins the sensors' device through the Bluetooth connection, because it's created before the first advertisement.
- `config_flow.py`: Bluetooth discovery, plus a user step that requests an active scan first.
- 2026.9 constraints: config flows use `import voluptuous as vol` (later HA releases alias it to Probatio). `no_devices_found` has its own string, because central abort translations need 2026.10. Custom integrations need `translations/en.json`, not `strings.json`.
- `brand/`: an original generic icon, not Vitafit's logo. HACS requires it.

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

- Not yet tested in HA or via an ESPHome proxy. Weight and impedance did match the display on the real scale with the library's `scripts/capture.py`. Owner's criteria still to check: it works via a proxy with no local adapter, and readings appear in history and statistics.
- Step on twice, about 5 minutes apart, in HA. If the second weigh-in isn't polled (HA drops repeated identical advertisements), copy inkbird's fallback poll timer. That first needs a recency check in the library's `poll_needed`.
