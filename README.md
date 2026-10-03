# Vitafit for Home Assistant

Local Bluetooth integration for the Vitafit VT701 body fat scale. It works with ESPHome Bluetooth proxies.

Unofficial; not affiliated with Vitafit.

## Sensors

| Sensor | Unit | Notes |
|---|---|---|
| Weight | kg | 0.01 kg resolution |
| Impedance | ohm | Whole-body. Unknown if you step off early or wear socks. |
| Signal strength | dBm | Diagnostic; disabled by default |

The integration does not calculate body composition or assign readings to people. Build these from the weight and impedance sensors with templates or automations.

## Requirements

- Home Assistant 2026.10 or later.
- A Bluetooth adapter or an ESPHome Bluetooth proxy within range of the scale. A proxy needs `active: true`, because the integration has to connect to the scale.

## Installation

### HACS

1. HACS → ⋮ → Custom repositories → add `https://github.com/jamesmyatt/ha-vitafit-ble` as type Integration.
2. Install **Vitafit**, then restart Home Assistant.

### Manual

Copy `custom_components/vitafit_ble` into your `config/custom_components` folder, then restart Home Assistant.

## Setup

Step on the scale to wake it. Home Assistant discovers it and shows a notification: **Settings → Devices & services → Discovered → Vitafit**. You can also add it manually: **Add integration → Vitafit**.

## How it works

1. Stepping on the scale makes it advertise. The integration then connects through the nearest connectable adapter or proxy.
2. It waits up to 30 s for a stable weight.
3. It acknowledges the weight, which makes the scale measure impedance.
4. It waits up to 6 s for impedance, then disconnects.

Readings within 60 s of the previous connection are ignored, so a weigh-in is not read twice.

Entities show as unavailable while the scale is asleep, and this includes after a Home Assistant restart. Every reading is still kept in history and long-term statistics.

## Known limitations

- Weight is always reported in kg; the scale's display unit is not read or changed.
- Two weigh-ins less than 60 s apart: only the first is read.

## Removal

**Settings → Devices & services → Vitafit → ⋮ → Delete**, then remove the HACS download or the `custom_components/vitafit_ble` folder.

## Licence

MIT. Protocol from openScale's [VT701 handler](https://github.com/oliexdev/openScale/pull/1423); implementation in [vitafit-ble](https://github.com/jamesmyatt/vitafit-ble).
