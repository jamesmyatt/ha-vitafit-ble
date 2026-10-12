# Vitafit for Home Assistant

Local Bluetooth integration for Vitafit smart scales, using the [vitafit-ble](https://github.com/jamesmyatt/vitafit-ble) library. It works with ESPHome Bluetooth proxies.

Supported models:

- Vitafit VT701 body fat scale

The library's [supported devices](https://vitafit-ble.readthedocs.io/en/latest/supported_devices.html) page has the details. To request another model, open an issue there.

Unofficial; not affiliated with Vitafit.

## Sensors

| Sensor           | Unit | Notes                                                                          |
| ---------------- | ---- | ------------------------------------------------------------------------------ |
| Weight           | kg   | The last weigh-in, to 0.01 kg                                                  |
| Impedance        | ohm  | The last weigh-in, whole-body. Unknown if you stepped off early or wore socks. |
| Real-time weight | kg   | The weight as it settles, while connected. Not in long-term statistics.        |
| Signal strength  | dBm  | Diagnostic; disabled by default                                                |

Weight and impedance are updated at every weigh-in, even when the reading is the same as last time, so automations can trigger on each weigh-in.

The integration does not calculate body composition or assign readings to people. Build these from the weight and impedance sensors with templates or automations (see [Examples](#examples)).

## Use cases

- Keep your weight history in Home Assistant, without the Vitafit app or a cloud account.
- Graph weight trends on a dashboard, from the long-term statistics.
- Send a notification, or a reading to another service, after each weigh-in.
- Calculate BMI or body composition with your own templates.
- Show the real-time weight on a wall tablet while you stand on the scale.

## Weight-only mode

The **Weight-only mode** switch (under the device's configuration entities) does the same as the Vitafit app's "Weight Only Mode": the scale passes no current through the body, so impedance is not measured. The manual recommends it if you are pregnant or have a pacemaker or other internal device.

- A change applies from the next weigh-in that Home Assistant reads.
- The scale remembers the mode, so it also applies to weigh-ins when Home Assistant doesn't connect. Each connection from Home Assistant or the Vitafit app sets it again.
- Home Assistant can't read the mode back from the scale, so if you change it in the Vitafit app, the switch won't show the change, and Home Assistant will set its own mode at the next weigh-in.

## Requirements

- Home Assistant 2026.9 or later.
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
3. It acknowledges the weight.
4. It waits up to 10 s for impedance, then disconnects.

Readings within 60 s of the previous connection are ignored, so a weigh-in is not read twice.

Weight and impedance keep the last weigh-in while the scale is asleep and after a Home Assistant restart. A weigh-in without a stable weight, or a failed connection, leaves them unchanged. Real-time weight is only available while connected, and signal strength only while the scale is advertising.

## Examples

Replace `sensor.vitafit_vt701_aa60_weight` with your weight sensor's entity ID.

Notify your phone after each weigh-in:

```yaml
automation:
  - alias: Weigh-in notification
    triggers:
      - trigger: state
        entity_id: sensor.vitafit_vt701_aa60_weight
    conditions:
      # Skip the sensor being removed or added, at startup or when the integration reloads.
      - "{{ trigger.from_state and trigger.to_state and trigger.to_state.state | is_number }}"
    actions:
      - action: notify.mobile_app_your_phone
        data:
          message: "Weight: {{ trigger.to_state.state }} kg"
```

A BMI sensor, for someone 1.75 m tall:

```yaml
template:
  - sensor:
      - name: BMI
        unit_of_measurement: kg/m²
        state_class: measurement
        state: "{{ (states('sensor.vitafit_vt701_aa60_weight') | float / 1.75 ** 2) | round(1) }}"
        availability: "{{ has_value('sensor.vitafit_vt701_aa60_weight') }}"
```

## Known limitations

- Weight is always reported in kg. The scale keeps whichever display unit it is set to (kg, lb or st).
- Two weigh-ins less than 60 s apart: only the first is read.

## Troubleshooting

- **The scale isn't discovered:** step on it to wake it. It only advertises while it's awake. A Bluetooth adapter or proxy must be in range, and an ESPHome proxy needs `active: true`.
- **The weight doesn't update:** stay on the scale until the weight is stable. Check that a connectable adapter or proxy is in range. If the Vitafit app is open nearby, it may connect to the scale first.
- **Impedance is unknown:** stand barefoot on the four electrodes, and stay on until impedance is measured. Check that **Weight-only mode** is off.
- **Reporting a problem:** on the integration's page, choose **⋮ → Enable debug logging**, weigh in, then disable it to download the log. Attach the log and the diagnostics (**⋮ → Download diagnostics** on the same page) to an [issue](https://github.com/jamesmyatt/ha-vitafit-ble/issues).

## Removal

**Settings → Devices & services → Vitafit → ⋮ → Delete**, then remove the HACS download or the `custom_components/vitafit_ble` folder.

## Acknowledgements

This library has been created with the assistance of Claude Code and Opus 5.5.

## Licence

MIT
