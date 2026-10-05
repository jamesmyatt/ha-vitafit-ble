# CLAUDE.md: ha-vitafit-ble

Home Assistant custom integration (HACS) for the Vitafit VT701 Bluetooth body fat scale. Domain `vitafit_ble`.

The protocol code lives in the sibling library repo `../vitafit-ble` (PyPI package `vitafit-ble`, which has its own `CLAUDE.md`). Keep both repos side by side:

```
work/
├── vitafit-ble/      # library
└── ha-vitafit-ble/   # this repo
```

## Status (5 Oct 2026)

- Code is complete, with one initial commit. All local checks pass (see Verification).
- **Not yet tested on a real scale.** The weigh-in has only been run against a fake GATT client.
- The GitHub repos don't exist yet, and `vitafit-ble` is not on PyPI (404).
- HA 2026.10.0 is not released yet; the latest tag is `2026.10.0b0`.

## Owner's working preferences

- Based in the UK; use metric units. Prefers Python.
- Think first. Don't assume or guess; ask, offer options, and wait for feedback.
- Simplicity first. Give overviews and offer details. Gather all feedback before regenerating. Make minimal changes to existing content.
- Define success criteria, then loop until verified.
- Follow current idiomatic best practice. Plain prose, with no mannered writing.
- Owner's homelab: Home Assistant, ESPHome Bluetooth proxies (all `active: true`), Proxmox, TrueNAS, Ubiquiti.

## Decisions already made

Don't revisit these without asking.

| Decision | Choice | Reason |
|---|---|---|
| Approach | New integration and library, not a fork of `prabhjotsbhatia-ca/vitafit_body_fat_scale` | The fork bypasses HA's Bluetooth stack (no proxy support), never sends the ack (so no impedance), and contains copied Etekcity unit commands. |
| Scope | **Minimal.** Weight and impedance only, plus the default RSSI diagnostic. | HA can build anything else from these. |
| Body composition | **Excluded.** No sensors that need height, age or sex. | Owner's decision. |
| Users | No assignment of readings to people | Out of scope; HA templates or automations can do it. |
| Protocol source | openScale `VitafitVT701Handler.kt` ([PR #1423](https://github.com/oliexdev/openScale/pull/1423)) | The owner's VT701 works with openScale, so treat its protocol as correct. |
| Patterns | Follow HA core, using `oralb` / `oralb-ble` as the template | Owner's request |
| Names | Domain `vitafit_ble`, PyPI `vitafit-ble`, repos `jamesmyatt/vitafit-ble` and `jamesmyatt/ha-vitafit-ble`, codeowner `@jamesmyatt` | Owner's choice |
| Licence | MIT (both repos) | Protocol facts are reused, but no GPL code from openScale was copied. |
| Minimum HA | 2026.10 | Lets the integration use `probatio` and central abort translations. |
| Availability | Core default: unavailable while the scale is asleep | Owner's choice (see Corrections) |
| Library | Published on PyPI, pinned in `manifest.json` | Owner's decision |

### Corrections

During planning I said `oralb` uses core's default availability. That was wrong: `oralb` overrides `available` to always return `True` and sets `assumed_state` when the device is not broadcasting. The owner chose "core default" on the basis of the wrong description. If they want `oralb` behaviour, add those two property overrides to `VitafitBluetoothSensorEntity` in `sensor.py`. Ask before changing it.

## Architecture

- `__init__.py`: an `ActiveBluetoothProcessorCoordinator`, structured the same as core `oralb/__init__.py`.
  - It listens passively, so advertisements can come from any proxy.
  - When `poll_needed` is true, it swaps in a connectable `BLEDevice` (adapter or proxy) and calls the library's `async_poll`.
- `sensor.py`: maps `PassiveBluetoothDataProcessor` and sensor-state-data to entities. Keys are `mass`, `impedance` and `signal_strength`.
- `config_flow.py`: Bluetooth discovery plus a user step.
  - Imports `probatio`, not voluptuous.
  - `no_devices_found` uses `translation_domain=HOMEASSISTANT_DOMAIN`, which needs HA 2026.10 or later.
- `manifest.json`: matches `local_name: "Vitafit*"`. openScale saw the name "Vitafit Body Fat"; no manufacturer data is required.
- `translations/en.json`: custom integrations need `translations/`, because `strings.json` is only compiled for core integrations.
- `brand/icon.png` and `brand/icon@2x.png`: an original generic scale glyph, not Vitafit's logo. HA 2026.3 or later serves these locally, and HACS requires them.
- The weigh-in sequence, polling and timeouts are in the library; see `../vitafit-ble/CLAUDE.md`.

## Commands

All commands run from this repo's root and need `uv` and Python 3.14.2 or later.

**Setup before `vitafit-ble` is on PyPI.** `uv sync` fails at this stage, so install the sibling repo editable:

```sh
uv venv -p 3.14
uv pip install --prerelease=allow -e ../vitafit-ble \
  "pytest-homeassistant-custom-component==0.13.368" \
  "aiousbwatcher==1.1.2" "serialx==1.11.0" ruff mypy
```

**Setup after publishing:** `uv sync`

**Checks**, which match `.github/workflows/test.yml`:

```sh
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy custom_components
.venv/bin/pytest
.venv/bin/pytest --cov=custom_components.vitafit_ble --cov-report=term-missing
script/hassfest.sh            # HA_TAG=2026.10.0 script/hassfest.sh once released
```

Notes:

- The ruff config in `pyproject.toml` is copied from HA core 2026.10. Keep it in sync with core rather than tuning it.
- `aiousbwatcher` and `serialx` are only there because the `bluetooth` integration depends on `usb`; the test harness doesn't install them.
- `prerelease = "allow"` is needed because harness 0.13.368 pins `homeassistant==2026.10.0b0`.

## Verification

Last run on 3–5 Oct 2026.

| Check | Result |
|---|---|
| ruff (core rule set), strict mypy | Pass |
| pytest against HA 2026.10.0b0, clean env | 9 passed, 97% coverage. Only `__init__.py` lines 52–57 (the no-connectable-device branch) are uncovered. |
| hassfest (2026.10.0b0) | 0 invalid |
| HACS action | Not run; it needs the GitHub repo |
| Real VT701 via an ESPHome proxy | **Not done** |

### Success criteria agreed with the owner

1. Weight matches the scale display to within 0.05 kg.
2. Impedance is captured on barefoot weigh-ins. Weight is still recorded if the user steps off early.
3. It works via an ESPHome proxy with no local adapter.
4. Values appear in history and statistics. With the current availability choice, entities are not available after a restart.
5. Tests pass on captured frames, and hassfest/HACS validation passes.

## Next steps

1. Publish the library: create `jamesmyatt/vitafit-ble`, add a PyPI trusted publisher (environment `pypi`, workflow `release.yml`), then publish GitHub release `v0.1.0`.
2. Create `jamesmyatt/ha-vitafit-ble` with a description and topics (HACS checks these). Push, then confirm the hassfest, HACS and test workflows pass.
3. Do a real weigh-in with `logger: logs: {vitafit_ble: debug, custom_components.vitafit_ble: debug}` set. Check the frames and the success criteria.
4. When HA 2026.10.0 ships:
   - Bump `pytest-homeassistant-custom-component` to the release that pins it.
   - Remove `prerelease = "allow"`.
   - Update `HA_TAG` in `script/hassfest.sh`.
5. Optionally add a GitHub release workflow and a `CHANGELOG.md`.

### Assumptions to verify on the real scale

- The advertised local name starts with "Vitafit".
- Byte 2 of every frame is `0x26`. The old fork's test frame had `0x00`; openScale says `0x26`, and the owner's scale works with openScale.
- The hello sequence is accepted, and the scale stops advertising soon after a weigh-in. The library's 60 s poll interval assumes this.

## Research summary

**Existing VT701 integrations.** The only one is `prabhjotsbhatia-ca/vitafit_body_fat_scale` with its library `vitafit_vt701_ble`, last updated Oct 2024 and never published to PyPI. These don't support the VT701:

- ble-scale-sync
- clentfort/homeassistant-openScale (Beurer only)
- Feelfit (cloud)
- the Fitdays ESPHome thread (different protocol, service `0xFFB0`)

**Relevant HA and HACS changes:**

- [Probatio replaced voluptuous](https://developers.home-assistant.io/blog/2026/09/30/probatio-validation-engine/) in 2026.9. Core now bans `import voluptuous`.
- [Shared abort reasons are translated centrally](https://developers.home-assistant.io/blog/2026/09/28/central-config-flow-abort-reasons/) from 2026.10.
- [Custom integrations ship their own brand images](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/) from 2026.3.
- [HACS integration requirements](https://hacs.xyz/docs/publish/integration/)
- [Quality scale checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist). The current code targets Bronze plus `discovery`, `devices`, `entity-translations` and `entity-device-class`.
