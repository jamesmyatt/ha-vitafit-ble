# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- "Health & wellbeing" integration category.

## [0.5.0] - 2026-10-19

### Changed

- **Behaviour change:** acknowledges each settling and stable weight frame, as the Vitafit app does, so the scale can replace any that are missed or corrupt. (via vitafit-ble 0.5.0)
- **Behaviour change:** if the scale reports impedance before a stable weight, the weigh-in ends at once with no new weight or impedance, instead of waiting for a stable weight that won't come. (via vitafit-ble 0.5.0)
- **Behaviour change:** after a weigh-in that gives no weight, for any reason (a Bluetooth error, no stable weight, or impedance first), the scale is polled again as soon as it next wakes, instead of up to 60 s later, and not again while it's still awake. After a weigh-in with a weight, it still waits at least 60 s. (requires vitafit-ble 0.6.0)
- Uses vitafit-ble 0.6.0.

## [0.4.0] - 2026-10-12

### Added

- Repair issue when the scale can only be heard by Bluetooth adapters or proxies that can't connect to it.

### Changed

- **Behaviour change:** weight and impedance update on every weigh-in, even if the reading is unchanged, so automations triggered by them run on every weigh-in.
- **Behaviour change:** a failed weigh-in is logged once as an error, instead of a warning every time.
- Uses vitafit-ble 0.4.0.
- Renamed to "Vitafit" in HACS.

### Fixed

- After an update, the sensors pick up the new version's settings.
- Real-time weight goes unavailable if a weigh-in fails.

## [0.3.0] - 2026-10-11

### Added

- Real-time weight sensor, showing the weight as it settles while you stand on the scale.
- Diagnostics.
- README: supported models, use cases, examples, known limitations and troubleshooting.

### Changed

- **Behaviour change:** weight and impedance keep the last weigh-in while the scale is asleep and after a restart, instead of going unavailable.
- A weigh-in without a stable weight, or a failed connection, leaves the last readings unchanged.
- New integration icon.
- Uses vitafit-ble 0.3.0.

## [0.2.0] - 2026-10-11

### Changed

- Sensors are created at setup, instead of after the first weigh-in.
- Uses vitafit-ble 0.2.0.

### Fixed

- A weigh-in soon after the previous one is now read.

## [0.1.0] - 2026-10-08

First release, for the Vitafit VT701 body fat scale.

### Added

- Weight and impedance sensors.
- Signal strength diagnostic sensor, disabled by default.
- Weight-only mode switch.
- Bluetooth discovery, plus manual setup.
- Works with ESPHome Bluetooth proxies.

[Unreleased]: https://github.com/jamesmyatt/ha-vitafit-ble/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/jamesmyatt/ha-vitafit-ble/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/jamesmyatt/ha-vitafit-ble/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jamesmyatt/ha-vitafit-ble/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jamesmyatt/ha-vitafit-ble/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jamesmyatt/ha-vitafit-ble/releases/tag/v0.1.0
