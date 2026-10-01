# Domoticz TinyTUYA Plugin - Agent Documentation

## Project Overview

**Repository:** Domoticz-TinyTUYA-Plugin
**Main File:** plugin.py
**Purpose:** Domoticz plugin for Tuya IoT devices with hybrid local/cloud control
**Current Version:** 3.2.0
**Author:** Xenomes (xenomes@outlook.com)

## Architecture

### Hybrid Control System
- **Cloud Communication:** Used for initial device discovery, DPS mapping, and configuration
- **Local Communication:** Uses TinyTuya library for device control and status updates
- **Fallback:** Automatically falls back to cloud when local control is unavailable
- **Realtime Updates:** Tuya Pulsar websocket for push updates from devices

### Key Components
- **plugin.py:** Main plugin file with all device logic
- **TinyTuya:** Python library for local Tuya device communication
- **Tuya Cloud API:** Used for device discovery and configuration

## Device Categorization

### Main Device Types
- **switch/sensor:** Basic switches with optional sensor functionality
- **switch:** Basic switches without sensors (e.g. Maxcio plug, category 'cz')
- **light:** RGB/RGBW/RGBWW lights, dimmers, fans with lights
- **thermostat/heater/heatpump:** Temperature control devices
- **cover:** Curtains, blinds, shutters
- **smartlock:** Door locks with multiple unlock methods
- **aromatherapy:** Aroma diffusers with light and mist control
- **dehumidifier:** Humidity control devices
- **sensor:** Motion sensors, temperature/humidity sensors
- **doorcontact:** Door/window contact sensors
- **Other:** Many specialized device types

### Special Categories
- **Category 'qt':** Ambiguous - can be smoke detector OR curtain switch (detected via product_name)
- **Category 'wnykq':** Smart IR devices (currently marked as unsupported)
- **Category 'jsq':** Aromatherapy devices
- **Category 'ms'/'jtmspro':** Smart locks
- **Category 'cz':** Smart socket, possibly with RGB LED ring (e.g. Maxcio plug)
- **Category 'dc':** Light, sometimes RGBIC multi-LED strip (e.g. Faretti esterni, KSIX BXOUTL1)
- **Category 'kt':** Air conditioner (e.g. Thermor Niseko, half-degree temperature scale)

## Important Implementation Details

### Tuya protocol v3.1 single-connection limit

- **Symptom:** Commands work for the first ~20 seconds after plugin
  startup, then stop responding once the log shows
  `Local connection to <name> established`. The plugin still logs
  `[LOCAL] Command sent` but the device does not act, and the next poll
  reports the unchanged state.
- **Cause:** Tuya v3.1 firmware accepts only one TCP connection per
  device. `LocalListener` opens a persistent socket (`persist=True`) to
  receive pushed DP updates. `SendCommandTuya` then opens a *second*
  socket to send the command. The device accepts the second handshake
  but drops the payload, so nothing errors in the log while the command
  is lost.
- **Fix:** `start_local_listeners()` reads the protocol version from
  `localtuya[dev_id]['version']` and skips every device whose version
  is `3.1`. Those devices are poll-only: the poll loop opens a
  short-lived socket, reads the status, closes it — the same connection
  style `SendCommandTuya` uses, so the two no longer fight over the
  single slot.
- **Covered by this rule:** every Maxcio device, and any other device
  reporting v3.1 in the initial IP scan.
- **Not affected:** v3.3 and v3.4 devices keep their persistent listeners.

### Work mode must be set before colour data — but not on every device

- **Symptom:** Sending `colour_data` to a light whose `work_mode` is
  still `white` has no visible effect, or the device falls back to a
  rainbow/effect mode.
- **Cause:** On **most** Tuya lights the firmware ignores `colour_data`
  while `work_mode` is `white`.
- **Fix (general case):** whenever `Set Color` is sent with a
  colour-mode payload (`Color['m'] == 3`), send `work_mode = 'colour'`
  immediately before `colour_data`.
- **Applies to:** `light` Unit 1, `light` Unit 2, socket LED (Unit 2).
- **Exception — aromatherapy (`jsq`):** some firmware revisions interpret
  `work_mode = 'colour'` (DP 109) as a request to switch the device
  **off**, and they use `lightmode` (DP 110) rather than `work_mode` to
  select between steady colour and cycling effects. On those devices the
  plugin must **not** send `work_mode` at all; it sets a steady
  `lightmode` instead. See *Aromatherapy Support* below.

### Domoticz colour dict — only m, r, g, b for mode 3

Domoticz' `Color` parameter uses these fields:

```
m  - ColorMode (0=none, 1=white, 2=temp, 3=RGB, 4=custom)
t  - colour temperature 0-255
r  - red 0-255
g  - green 0-255
b  - blue 0-255
cw - cold white 0-255
ww - warm white 0-255
```

For `m=3` (ColorModeRGB), **only `r`, `g`, `b` are valid**. Extra
fields (`t`, `cw`, `ww`) can make Domoticz reject the colour update and
leave the wheel at its previous value.

Always use `rgb_to_hsv` (0-255 scale) for Tuya `colour_data`, not the
`_v2` variant (0-1000 scale). Tuya reports `colour_data` with `s` and
`v` in 0-255 for most devices.

**Reading** a Tuya `colour_data` value is a separate problem: the
device can report it as JSON (`{'h':.., 's':.., 'v':..}`) **or** as a
raw hex string (e.g. `DC0A00000200DC`). Never write the raw value into
`sValue`; always decode it first with `decode_colour_data()` (see
*Colour helpers*).

### Curtain Switch Support (Issue #208, #216)
- Category 'qt' devices with "curtain" in product_name are treated as covers
- Status mapping: 1=Open, 2=Close, 3=Stop
- Command mapping: open→1, close→2, stop→3
- Other 'qt' devices remain smoke detectors

### SmartLock Support (Issue #205)
- Unit 1: Lock state (lock_motor_state/rtc_lock)
- Unit 2: Alarm status (alarm_lock selector)
- Units 3-11: Unlock methods (BLE, Card, Fingerprint, Password, App,
  Key, Face, Hand, Temporary), created and updated through a single
  loop driven by a tuple of `(unit, code, label)` pairs
- Compatibility maintained for existing unit numbers

### Aromatherapy Support (Issue #200)

Six units, plus a fallback for firmware variants that behave
differently from the "generic" Tuya light.

| Unit | DP | Notes |
|---|---|---|
| 1 | `Power` | main humidifier switch |
| 2 | `Light` | light switch, **independent of `Power`** |
| 3 | `lightmode` | selector: effect (1 = multicolour, 2 = steady, ...) |
| 4 | `dp_mist_grade` | selector: mist intensity |
| 5 | `work_mode` | selector: scene (white / colour / scene / music) |
| 6 | `colour_data` | RGB colour, may be JSON or hex (see below) |

#### Key facts learned from real devices

- **`Light` is independent of `Power`.** The device can have
  `Light = true` while `Power = false` (light-only mode). The Light
  unit must follow its **own** DP and **not** be gated on the main
  Power state. (Earlier attempts coupled them; that caused the Light
  tile to flip back to off on every poll.)
- **The RGB unit's `nValue` follows `Light`, not `Power`.** A colour
  JSON in `sValue` does not imply the unit is on; the tile must be
  grey unless `Light = true`.
- **`colour_data` can be a hex string.** Older aromatherapy firmware
  reports DP 108 as a raw 7-byte hex string (e.g. `DC0A00000200DC`)
  rather than the JSON form. Decode with `decode_colour_data()`; never
  write the raw string into `sValue`.
- **`work_mode = 'colour'` can turn the device off.** On some firmware,
  sending `work_mode = 'colour'` on DP 109 is interpreted as "switch
  off". The plugin therefore does **not** send `work_mode` from the RGB
  Set Color handler on aromatherapy devices. Instead it sets a steady
  `lightmode` first.
- **The device starts in `lightmode = 1` (multicolour).** Turning the
  Light on without setting a lightmode produces a cycling effect.
  The Light On handler must send a steady lightmode right after
  `Light = true`. `find_steady_lightmode()` finds the value.
- **`work_mode` is not echoed back.** On this firmware DP 109 is
  write-only; it never appears in the status reply. The generic
  `update_select_device()` would guess a value and flip the tile back
  on every poll, so it now early-returns when `StatusDeviceTuya()`
  returns `None` for the requested code.
- **`colour_data` value on the device may not match what was sent.**
  On this firmware `colour_data` often stays at its last value while
  the light cycles or is off, so the RGB tile simply mirrors what the
  device reports (decoded) and does not try to infer intent.

#### What the plugin does on Set Color (Unit 6)

1. Find the steady lightmode (`find_steady_lightmode()`) and send it.
2. Build the `colour_data` payload from Domoticz' `Color` dict and send
   it.
3. **Do not send `work_mode`.**

#### What the plugin does on Light On (Unit 2)

1. Send `Light = true`.
2. Send the steady lightmode, so the light does not start cycling.

### Socket with RGB LED ring
- Category 'cz' sockets (e.g. Maxcio plug) expose two independent
  outputs:
  - Unit 1: relay, DP `switch_1`
  - Unit 2: LED ring, DPs `switch_led` + `work_mode` + `bright_value` +
    `colour_data`, created only when all four are present in the
    function list
- `bright_value` on such a device often uses `min: 25`; the helper
  functions read min and max from the schema, so the plugin adapts
  automatically.
- `colour_data` on such a device uses the classic 0–255 range for `s`
  and `v`, so the plain `rgb_to_hsv` / `hsv_to_rgb` helpers are used.
- The `Set Color` payload must set `work_mode` before `colour_data`.
  (This is the *general* rule; the aromatherapy exception above does
  not apply here.)
- The old `switch` block in `onCommand` is gated on `Unit == 1` so it
  does not build a bogus `switch_2` command for the LED unit.

### RGBIC Light Support (Issue #200)
- Multi-LED devices with `draw_tool` support (e.g. KSIX BXOUTL1,
  Faretti esterni giardino)
- Automatic RGBW/RGBWW detection based on `bright_value` max
- White channel support for better color rendering
- Units 11+ for individual LED control
- `draw_tool` frame layout:
  - Broadcast (9 bytes): `01 01 01 00 H S V 00 00`, H in colour-code
    table (0x01 red, 0x7B green, 0xDF blue), S saturation 0–100,
    V intensity 1–100
  - Per-LED (12 bytes): `01 02 01 00 H S V 00 00 81 00 SPOT`, SPOT is
    0-based LED index
  - Colour code table is not linear RGB; the plugin uses the code
    values observed from the device, not a formula.

### Thermor Niseko HVAC Support (PR #221, thanks @Chrominator)
- Extends `thermostat`/`heater`/`heatpump` with five optional units
  that are created only when the device exposes the corresponding DP:
  - Unit 30: Turbo (`turbo`)
  - Unit 31: Quiet (`quiet`)
  - Unit 32: Sleep (`sleep`)
  - Unit 33: Energy save (`energy_save`)
  - Unit 34: Health (`healthy`)
- Commands route through `SendCommandTuya(DeviceID, code, Command == 'On')`
- Status updates and creation both use a single tuple-driven loop;
  adding a new unit is one tuple entry, not a new block.
- `get_scale()` has a device-specific branch for `product_id ==
  '9xvzf8c0bg33eenj'`: `temp_current` is reported in half degrees, so
  the value is divided by 2.

### Protocol 3.4 Cloud Fallback
- Specific fallback for protocol 3.4 devices to show correct online/offline status
- Rate-limited to avoid excessive cloud API calls
- Prevents devices from incorrectly showing TimedOut=1

### Local connection coverage (`LocalCovered`)
- A device whose open local connection already reports every DP that its
  units read is skipped from the cloud poll. Codes are tracked in
  `local_used` by `StatusDeviceTuya()` while the poll loop runs.
- Logs a single line when a device enters or leaves this state.

### Cloud usage counters

Purpose: make visible how much of the monthly Tuya budget (API calls +
Pulsar messages) the plugin itself consumes.

- `_usage_days` is the in-memory store: `'YYYY-MM-DD' -> {'api': n, 'msg': n}`.
- `_usage_load()` / `_usage_save()` persist the counter store in
  `DomoticzEx.Configuration()` under key `USAGE_KEY` (`'cloud_usage'`).
  Saving is throttled (`USAGE_SAVE_INTERVAL = 60`); forcing is possible
  with `_usage_save(force=True)` (done in `onStop`).
- `_usage_count('api')` is called by `_count_cloud_calls()`, which wraps
  `Cloud._tuyaplatform()`. If that method does not exist (older tinytuya)
  the public methods are wrapped instead, and the count is approximate.
- `_usage_count('msg')` is called at the start of `_pulsar_on_message()`.
- `_usage_tick()` runs from `onHeartbeat()`: saves, detects a day
  rollover (`_usage_last_day != today`) and then logs the midnight
  report plus the month forecast.
- `_usage_create_devices()` creates the two `CloudCredits` units
  (Type=243, Subtype=31, Custom `1;Calls` and `1;Msg`).
- `_usage_update_devices()` pushes the month totals every hour
  (`USAGE_DEVICE_UPDATE_INTERVAL = 3600`) with `AlwaysUpdate=1`, so
  `LastUpdate` shows the plugin is alive.
- Limits (`USAGE_LIMITS`) and the warning threshold
  (`USAGE_WARN_FRACTION = 0.9`) are constants at the top of the file.

**Note:** the counters cover only what **this** plugin sends. Other
tools on the same Tuya project are not included, so the Tuya console
(Cloud → Usage) can show a higher number.

**Bar Ranges** on the two credits devices are not set from the plugin:
the Domoticz feature is too recent and its internal storage format
could not be verified. Users set them by hand once in Setup → Devices.

### LAN / Pulsar logging helpers

- `_format_value(value, max_len=80)` — readable rendering of a DP value
  for log lines; long base64 blobs are shortened.
- `_dp_code(dev_id, dp_id)` — translates a DP id to the function code via
  `dps_map`, or `None` if unknown.
- `_describe_local_dps(dev_id, dps)` — `'switch_1 (DP 1) = true, ...'`.
- `_log_local_error(dev_id, source, reply)` — if the reply contains
  `Err`/`Error`: a clear ERROR line with the translated meaning from
  `_LOCAL_ERRORS` (901/902/904/905/914) and a hint. Repeats within
  `_LOCAL_ERROR_REPEAT = 3600` seconds go to Debug.
- `_log_local_message(dev_id, source, reply)` — INFO line for every
  message arriving over the LAN (status reply, push, heartbeat).
  Calls `_log_local_error()` first.
- `_log_pulsar_message(data)` — INFO line for every Pulsar message, in
  both the legacy and IoT Core shapes, before any processing.
- `_log_realtime_capable_devices()` — startup overview of devices
  covered by the Pulsar fast path (door contacts, motion sensors,
  doorbells), with OK / MISMATCH (not yet in Domoticz) / MISMATCH
  (orphaned in Domoticz).
- `_device_name(dev_id)` — best-effort human-readable name; tries the
  Tuya device list first, then `Devices[dev_id].Units[1].Name`, then the ID.
- `_sys_date(d, kind)` — formats a date using the locale of the system
  Domoticz runs on. Falls back to ISO when only C/POSIX is available.

## Build and Verification

### Syntax Check

    python3 -m py_compile plugin.py

### Git Operations

    # Check status
    git status --short
    git diff -- plugin.py

    # Commit format
    git commit -m "Description

    Generated with [Devin](https://devin.ai)

    Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>"

### Version bump

The version number lives in **two places** in the XML header of
`plugin.py` and must match:

    <plugin key="tinytuya" name="TinyTUYA" author="Xenomes" version="3.2.0" ...>
        ...
        <h2>TinyTuya Plugin - Hybrid Local / Cloud Control version 3.2.0</h2><br/>

`Parameters['Version']` is populated by Domoticz from the header, so no
other file needs changing.

**Aromatherapy follow-up for #200 is in `master` but not yet released:**
the header is still on `3.2.0`. The next release that includes the
aromatherapy fix should bump both places to `3.2.1`.

## GitHub Labels

When opening or triaging issues and PRs, apply the repository's existing
labels. Match the label to the change so the changelog and filters stay
useful.

| Label | When to use |
|---|---|
| `bug` | Confirmed defect with a reproduction |
| `enhancement` | New feature or improvement |
| `documentation` | README, AGENT.md, CHANGELOG-only changes |
| `device-support` | Adds or fixes support for a specific device type or product_id |
| `protocol-3.1` | Anything related to the v3.1 single-connection limit |
| `protocol-3.4` | Anything related to the v3.4 cloud fallback path |
| `local-control` | Changes to `LocalListener`, `LocalCovered`, or LAN polling |
| `cloud` | Changes to Pulsar, cloud fallback, or the Tuya IoT API |
| `cloud-usage` | Changes to the usage counters, credits devices or forecast |
| `logging` | Changes to LAN / Pulsar message logging or error translation |
| `color` | Changes to colour handling, `colour_data`, `work_mode`, `draw_tool` |
| `good first issue` | Small, self-contained issues suitable for newcomers |
| `help wanted` | Needs outside input or device logs |
| `duplicate` | Same root cause as an existing issue |
| `wontfix` | Out of scope for the plugin |
| `question` | User needs help, not a code change |
| `upstream` | Blocked by tinytuya or Tuya firmware behaviour |

Common combinations:

- New device type: `enhancement` + `device-support`
- Shutter / plug / Télé regression: `bug` + `protocol-3.1`
- Colour wheel not following the device: `bug` + `color`
- New Thermor Niseko unit: `enhancement` + `device-support`
- New usage counter or forecast change: `enhancement` + `cloud-usage`
- Log line missing or wrong: `bug` + `logging`
- Aromatherapy follow-up: `bug` + `device-support` + `color`

When in doubt, add `question` and ask for a log.

## Code Conventions

### DeviceType Function
- Signature: `DeviceType(category, product_id=None, product_name=None)`
- Returns device type string based on category and product information
- Special handling for ambiguous categories (e.g., 'qt' with product_name)

### Device Creation
- Uses `createDevice(dev_id, unit)` to check if device exists
- Pattern: `if createDevice(dev_id, unit) and searchCode('code', Properties):`
- Unit numbering: maintain compatibility for existing devices
- New optional units (e.g. Thermor 30-34) must be gated on `searchCode`
  in `FunctionProperties` so a device without the DP does not gain a
  phantom switch

### Repetitive unit patterns — use a tuple-driven loop

When a device type creates or updates a series of units that differ only
in unit number, DP code and display label, write it as a single
`for unit, code, label in (...)` loop. Do not copy the same block N
times. Existing examples:

- **SmartLock unlock methods** (units 3-11) — creation and status update
- **Irrigatie area switches** (units 3-8) — in `onCommand` via an
  `area_codes` dict
- **Switch multi-gang** (units 3-9) — in creation via `for unit in
  range(3, 10)`
- **Thermor HVAC extras** (units 30-34) — creation, status update and
  `onCommand` all use the same shape
- **Doorbell** — status update via a tuple of `(unit, code)` pairs

This is not just cosmetic: adding a new unlock method or a new HVAC
mode becomes one tuple entry, and there is no risk of the creation
block and the status-update block drifting apart.

### Status Updates
- Helper functions: `update_bool_device()`, `update_select_device()`,
  `update_value_device()`, `update_nvalue_device()`,
  `update_dualvalue_device()`, `update_power_device()`,
  `update_selectnum_device()`, `update_level_device()`,
  `update_text_device()`
- Pattern: check code, get value, update if changed
- Battery devices handled separately
- RGB units must gate their `nValue` on the actual on/off state. A colour
  JSON in `sValue` does not imply the unit is on.
- Dimmer units need `nValue = 2` to redraw the slider from `LastLevel`.
  `nValue = 1` leaves the slider frozen.
- `update_select_device()` must **early-return when the device does not
  report the code**. Some Tuya firmware has DPs that are write-only
  (e.g. `work_mode` on aromatherapy); guessing the current value makes
  the tile flip on every poll. If `StatusDeviceTuya(code)` returns
  `None`, leave the tile alone.

### Command Handling
- Pattern: check function code, send command, update Domoticz
- Special cases for dimmers, colors, multi-channel devices
- **General case:** when a colour command is sent, set `work_mode`
  before `colour_data`.
- **Aromatherapy exception:** do **not** send `work_mode`. Set a steady
  `lightmode` first; see *Aromatherapy Support*.
- When a socket has both a relay and an RGB LED, the plain switch
  handler must be gated on `Unit == 1`, and the LED handler on
  `Unit == 2`.
- `SendCommandTuya()` runs the actual socket write on a background
  thread so a slow device does not block the Domoticz main loop.
- For a series of identical on/off units on the same device, use the
  same tuple-driven approach as in device creation (see SmartLock and
  Thermor examples).

### Local listeners
- `LocalListener` is only started for devices whose protocol version is
  **not** 3.1. Version is read from `localtuya[dev_id]['version']`,
  populated by the initial UDP scan.
- Never start a listener for a device that a command has to reach over
  the same TCP connection.

### Usage counters
- All counter mutations go through `_usage_count(kind, amount=1)`.
  Never write to `_usage_days` directly.
- `_usage_tick()` must be called from `onHeartbeat()`; it saves,
  detects a day rollover and logs the report.
- `_usage_save(force=True)` in `onStop()` guarantees the counters
  survive a restart.
- The device updates in `_usage_update_devices()` use `AlwaysUpdate=1`
  on purpose: the hour stamp on the tile is the plugin's liveness.
- When adding a new counter kind, extend `USAGE_LIMITS`, `USAGE_LABELS`
  and (if applicable) `_usage_forecast_lines()` — do not hardcode a
  third value anywhere.

### Logging helpers
- `_log_local_message()` and `_log_pulsar_message()` must never raise:
  logging must not be able to break a connection. Wrap the body in
  try/except if the surrounding code can throw.
- Repeated TinyTuya errors are throttled in `_log_local_error()` via
  `_local_error_logged`; keep the throttle key as `(dev_id, err)`.
- `_device_name()` is the single place that resolves a raw `dev_id` to
  a name for log output. Do not add local lookups elsewhere.

### Colour decoding helpers
- **Never write a raw Tuya colour value into `sValue`.** It may be JSON
  *or* hex, and Domoticz expects a colour dict.
- `decode_colour_data(raw)` is the single entry point: it accepts the
  JSON dict form (`{'h','s','v'}`) **and** the hex string form
  (`'DC0A00000200DC'`), and returns a Domoticz colour dict
  (`{'m':3,'r','g','b','t':0,'cw':0,'ww':0}`) or `None` when the value
  cannot be interpreted. Callers must handle `None` by leaving the tile
  untouched, not by writing the raw value.
- `find_steady_lightmode(function)` finds the "steady" value in a
  `lightmode` enum by looking for `steady` / `static` / `normal` /
  `constant`, falling back to index 2. Returns `None` when the device
  has no `lightmode` DP; callers must skip the send in that case.

## Known Issues and Solutions

### Category Mismatches
- **Category 'qt':** Can be smoke detector OR curtain switch → use product_name detection
- **Category 'wnykq':** Smart IR devices with limited functionality → mark as unsupported
- **Category 'jsq':** Aromatherapy devices → treat as dedicated type
- **Category 'cz':** Smart socket; can also expose an RGB LED ring
- **Category 'kt':** Air conditioner; `temp_current` may be in half degrees

### Indentation Issues
- Complex try/except blocks in status updates can cause indentation errors
- Solution: Carefully match indentation levels when adding new device types

### Color Control
- RGB vs RGBW vs RGBWW format differences
- Solution: Detect type from `bright_value` max and use appropriate encoding
- `draw_tool` commands need special base64 encoding
- **`work_mode` must be set before `colour_data`** on the *general*
  case, but **never on aromatherapy devices** (see the section on
  aromatherapy).
- **`nValue` on an RGB unit must follow the on/off state**, not be
  hardcoded to `1`. On aromatherapy devices the relevant on/off state
  is `Light`, not `Power`.
- **Colour dict for `m=3` should only carry `m, r, g, b`.** Extra fields
  can cause Domoticz to ignore the update.
- **Reading `colour_data` requires decoding.** It can arrive as JSON or
  as a hex string; use `decode_colour_data()`.

### Local Connection Issues
- Protocol 3.4 devices may not respond to local queries
- Solution: Cloud fallback with rate limiting
- **Protocol 3.1 devices must not get a persistent listener**.

### Battery device detection
- `is_battery_device()` handles both `str` and `list`/`dict` inputs.
- **Known bug (pending):** the outer guard in `battery_device()` only
  checks `battery_state`, `battery`, `va_battery` and
  `battery_percentage`. Devices with only `BatteryStatus` or only
  `residual_electricity` are correctly flagged as battery devices by
  `is_battery_device()` (and therefore never time out), but the
  battery-update branches inside `battery_device()` are unreachable for
  them. Fix: replace the outer guard with a call to
  `is_battery_device(StatusProperties)`.

### Duplicate battery update fragment
- The six-line "write `battery_level` to every unit of a device" block
  appears six times (five Pulsar fast paths + `battery_device()`).
- Fix: extract to a single `apply_battery_level(dev_id, level, source)`
  helper. This is cleanup, not a behaviour change, but it prevents the
  copies from drifting apart on future changes.

### Fallback code chains
- `thermostat`/`heater`/`heatpump` and `sensor` blocks contain several
  `if update_x('code_a', n): ... elif update_x('code_b', n): ...` chains,
  because different Tuya firmwares name the same DP differently.
- Fix: a small `update_first_of(('code_a', 'code_b', ...), unit,
  updater)` helper makes the intent explicit. Behaviour is identical to
  the `if/elif` chain — first matching code wins, later codes skipped.

### Aromatherapy firmware variants
- Some firmware revisions have a `Power` DP that stays `false` while
  `Light` is `true` (light-only mode). Never gate the Light unit on the
  main Power state.
- Some revisions interpret `work_mode = 'colour'` as "switch off". Never
  send `work_mode` from the aromatherapy RGB handler.
- `work_mode` (DP 109) is write-only on some revisions; it never appears
  in the status reply. `update_select_device()` must early-return when
  the value cannot be read, or the Scene tile flips back on every poll.
- `colour_data` (DP 108) can be a hex string on older firmware; decode
  it with `decode_colour_data()`.

### Testdata mode confusion
- If the plugin's home folder contains `debug_devices.json`,
  `debug_functions.json`, or `debug_result.json`, the plugin runs in
  **testdata mode**: it reads all device data from those files and
  never contacts the real cloud or the real devices. The startup log
  shows `!!! Warning Plugin overruled by local json files !!!` and
  `Pulsar realtime listener skipped`.
- Commands sent in this mode never reach hardware. Tests run in
  testdata mode are meaningless for hardware.
- To return to normal operation, delete all three files and restart.

## Branch Information

### Main Branches
- **Master:** Stable version with latest features

### Version Differences
- **3.x:** Hybrid local/cloud control with Pulsar realtime updates,
  cloud usage counters and extended logging

## Recent Work

### In master, not yet released (aromatherapy #200 follow-up)
- `Light` unit (2) no longer follows the main `Power` state. The device
  can have the light on while the humidifier itself is off, so the
  Light tile now tracks its own DP only.
- `RGB` unit (6) `nValue` follows `Light` (not `Power`) and the RGB
  tile only shows "on" when the light is actually on. Previously it was
  hardcoded to `1`, which is why the tile stayed "Acceso" on every poll.
- `colour_data` on the RGB unit is now decoded through
  `decode_colour_data()` — supports both the JSON form and the hex
  string form (`DC0A00000200DC`) that older aromatherapy firmware
  reports. The raw value is never written into `sValue` again.
- `Set Color` on the RGB unit no longer sends `work_mode` (this
  firmware interprets `work_mode = 'colour'` as "switch off"). It sets
  a steady `lightmode` first, using the new `find_steady_lightmode()`
  helper.
- `Light On` (Unit 2) now also sets the steady lightmode, so the light
  does not start in the cycling multicolour mode it defaults to.
- `update_select_device()` early-returns when the device does not
  report the requested code, so the Scene (work_mode) tile no longer
  flips back to `white` on every poll just because DP 109 is
  write-only on this firmware.

### Latest released (Version 3.2.0)
- **Cloud usage counters**: per-day tracking of API calls and Pulsar
  messages, persisted in the plugin configuration, with day / week /
  month totals.
- **Two 'credits' devices** per hardware instance
  (`DeviceID = CloudCredits`, Unit 1 = API calls, Unit 2 = Pulsar
  messages), updated hourly with `AlwaysUpdate=1`.
- **Midnight report** with the day's final totals, device count against
  the account maximum, and a month forecast (average/day, expected
  month total, expected shortage date). Warnings repeat as ERROR lines.
- **Hourly INFO summary** of the day/week/month totals.
- **Extended logging**:
  - `_log_local_message()` logs every LAN message (status reply, push,
    heartbeat) with device name, IP, DP code and value.
  - `_log_local_error()` translates TinyTuya error codes
    (901/902/904/905/914) into plain language plus a hint, throttled to
    one ERROR per device + code per hour.
  - `_log_pulsar_message()` logs every Pulsar message at INFO level
    before any processing, in both legacy and IoT Core shapes.
  - `_log_realtime_capable_devices()` logs a startup overview of the
    devices covered by the Pulsar fast path with OK / MISMATCH states.
- **`_sys_date()`** formats dates in log lines and reports using the
  locale of the system Domoticz runs on.
- **`_device_name()`** helper resolves a raw `dev_id` to a
  human-readable name for log output.
- **`_count_cloud_calls()`** wraps `Cloud._tuyaplatform()` so every
  HTTP request to Tuya is counted, with a fallback to counting public
  methods on older tinytuya versions.

### Previous notable releases
- `3.1.9`: Add Thermor Niseko HVAC support (PR #221, thanks
  @Chrominator): optional units 30–34 for turbo, quiet, sleep,
  energy_save, healthy; half-degree temperature scale for
  `product_id == '9xvzf8c0bg33eenj'`.
- `3.1.8`: Fix light colour control: `work_mode` set before
  `colour_data` on `light` Unit 1, `light` Unit 2, `aromatherapy`
  Unit 6, `dehumidifier` Unit 6. Fix `NameError: Colour` in
  `dehumidifier` Unit 6 handler. Humidifier RGB `nValue` follows
  `work_mode` instead of being hardcoded to `1`.
- `3.1.7`: Add RGB LED ring as Unit 2 for socket devices with
  `switch_led` + `work_mode` + `colour_data`.
- `3.1.6`: Skip all v3.1 devices in `start_local_listeners` (fix Télé
  plug and future v3.1 devices) (#216).
- `3.1.5`: Local connection: leave covered devices out of the cloud poll.
- `3.1.4`: Added pull request qxj weather station: Wind device from the
  wind direction.
- `3.1.3`: fix(powermeter): label 3-phase units by phase letter only
  when multiple phases are present (#217).
- `3.1.2`: fix(local): fire-and-forget for Tuya 3.1 devices to avoid
  Err 901 cloud fallback (#216).
- `3.1.1`: Add RGBW/RGBWW white channel support to draw_tool commands
  for RGBIC lights #200.
- `3.1.0`: Add aromatherapy device #200.
- `3.0.9`: Add SmartLock unlock methods #205.
- `3.0.8`: Fix battery device detection, remove dead code (Arjan), drop
  bare excepts (PR #214 alternative).
- `3.0.7`: Fix local status fetch for Tuya v3.4 devices.
- `3.0.6`: Cloud fallback for non-local devices in local poll path
  (fixes covers timing out after 3 minutes).
- `3.0.5`: Add missing `DeviceModelMapping()` helper (fix NameError
  during cloud-init for all devices).
- `3.0.4`: DPS mapping robustness: skip schema entries without dp_id,
  add `DeviceModelMapping` fallback for DPs missing from `getdps()`.
- `3.0.3`: fix: prevent IR/sub-devices from crashing the whole poll run.
- `3.0.2`: Fix infrared device support and command handling bugs.
- `3.0.1`: Fix for category detection of 'tdq'.
- `3.0.0`: Release of hybrid version.
- `3.0.0-rc.3`: Weather station barometer/rain units (PR #210) and
  multi-zone irrigation support (PR #209).
- `3.0.0-rc.2`: Add refresh button functionality (Mode5) from PR #211.
- `3.0.0-rc.1`: Merge Master branch changes (2.4.0-2.4.5) into Hybrid.

## Testing Approach

### Device Testing
1. Add device to Domoticz
2. Check device creation (correct units?)
3. Test commands (On/Off, Set Level, Set Color)
4. Verify status updates
5. Check logs for errors

### Confirm plugin is not in testdata mode
Before any hardware test, verify the startup log does **not** contain:
- `!!! Warning Plugin overruled by local json files !!!`
- `Pulsar realtime listener skipped (testdata/fulllocal mode active)`

If either appears, delete the three `debug_*.json` files from the plugin
folder and restart.

### Protocol version testing
1. Start plugin, wait ~30 s for the log to settle
2. Confirm every v3.1 device appears in a
   `Skipping local listener for <name> (v3.1: single-connection protocol)`
   line and in **no** `Local connection to <name> established` line
3. Confirm every v3.3 / v3.4 device still appears in a
   `Local connection to <name> established` line
4. Send a command to one v3.1 device — it should act, and the next poll
   should read back the new state
5. Send a command to one v3.3+ device — it should act as before

### Light colour testing
1. Turn the light on
2. Set brightness to a mid value
3. Pick a solid colour (red, then blue)
   - The physical light must actually change colour
   - On generic lights the log should show `work_mode = 'colour'` sent
     before `colour_data`
   - On aromatherapy devices the log should show a steady `lightmode`
     sent before `colour_data`, and no `work_mode`
4. Pick white
   - The light must return to white and honour the brightness slider

### Aromatherapy testing (Issue #200)
1. **Main switch off, Light on.** The Light tile must stay green, and
   the RGB tile must go grey. Before the fix, the plugin flipped the
   Light tile back to off on every poll.
2. **Turn Light on.** The light must come up steady (not cycling). The
   log must show a `lightmode` send right after the `Light = true` send.
3. **Pick a colour on the RGB unit.** The physical light must change
   colour, and the RGB tile must show a colour (not a hex string).
   The log must **not** contain `dp_id 109 = colour`.
4. **Pick a Scene on the Scene selector.** The tile must stay on
   whatever was picked, and must not flip back to `white` on the next
   poll. Whether picking `colour` turns the physical device off is a
   firmware limitation, not a plugin bug — note it in the issue and
   leave the fix at "the tile state is preserved".
5. **Lightmode selector.** Toggling between values must work; the tile
   must reflect the current value (it *is* reported back on this
   firmware).

### RGB unit state testing
1. Open the Humidifier RGB unit or the socket LED unit
2. Switch it off — the tile must go grey and stay grey across at least
   three poll cycles
3. Switch it on — the tile must go green and stay green
4. If the tile flips between grey and green every poll, the `nValue`
   is being forced to `1` by the colour branch

### Socket LED testing
1. Confirm the socket tile has two units (relay and LED) in Domoticz
2. Toggle the relay — the LED must stay in its previous state
3. Toggle the LED — the relay must stay in its previous state
4. Check the log: no `switch_2` command should appear

### Thermor Niseko testing
1. Confirm the device only creates the units 30–34 that its function
   list actually contains
2. Toggle each unit that exists — the corresponding DP must change
3. Confirm `temp_current` reads in half degrees on this device

### Cloud usage testing
1. Delete any `debug_*.json` files and restart the plugin.
2. Check the log for `Created device '<hw> API Credits'` and
   `Created device '<hw> Message Credits'`.
3. Confirm in the Domoticz UI that both Custom Sensors exist and show a
   number (initially 0 or the calls since start).
4. Wait one full poll cycle: the API number must rise by roughly the
   number of devices (one call per device status).
5. Send a command to a cloud-only device: the API number rises by 1.
6. Let a Pulsar message come in (open a door contact, trigger motion):
   the message number rises by 1 and the log shows a
   `Pulsar message from ...` line.
7. Restart the plugin: the values must have been preserved via
   `USAGE_KEY` in the configuration.
8. Temporarily move the system clock (or a value in `_usage_days`) one
   day forward to test the midnight report: a
   `Tuya cloud usage on <date> (final)` line must appear, followed by
   the month forecast.

### Logging testing
1. Trigger a LAN status read on a device with a known error (e.g. power
   it off and force a poll): a single ERROR line with the translated
   TinyTuya code and hint must appear.
2. Force the same error again within the hour: nothing new on ERROR,
   the repeat goes to Debug.
3. Watch a Pulsar-triggered device (door contact, motion sensor): a
   `Pulsar message from ...` INFO line appears even when the plugin
   decides to ignore it because the device is reachable locally.

### Syntax Verification
Always run `python3 -m py_compile plugin.py` after changes

### Log Analysis
- Debug level shows detailed device communication
- Look for "Cloud fallback" messages for protocol issues
- Check "Multi-LED" logs for `draw_tool` problems
- `[LOCAL] Command queued` / `[LOCAL] Command sent` — a queued line
  without a matching "sent" line one second later means the background
  send thread raised before completing
- `Skipping local listener for <name> (v3.1: ...)` — the device is
  poll-only by design, not an error
- `!!! Warning Plugin overruled by local json files !!!` — testdata
  mode, delete the `debug_*.json` files
- `Tuya cloud usage on <date> (final)` — the midnight report; the
  forecast lines right below it show the expected month total
- `Pulsar message from ... -- will be ignored` — expected for a device
  that is reachable locally
- `[LOCAL] Command queued: dp_id 109 = colour` — on an aromatherapy
  device this is a **bug**: DP 109 must not be sent from the RGB
  handler. If you see this line, the aromatherapy RGB handler is
  falling into the generic colour path.

## Dependencies

### Required
- Python 3.8+
- tinytuya library (pip3 install tinytuya)
- Domoticz with plugin support

### Optional
- tuya-connector-python (pip3 install tuya-connector-python --break-system-packages)
  — enables Pulsar realtime push updates. Without it the plugin falls
  back to poll-only mode.

## File Structure

- **plugin.py:** Main plugin file (all logic)
- **CHANGELOG.md:** Version history
- **README.md:** User documentation
- **AGENTS.md:** This file — architecture and conventions for agents
- **tools/**: Debug and utility scripts
- **backup/**: Backup files
- **examples/**: Example configurations
- **.devin/**: Devin agent configuration

## Important Functions

### Device Detection
- `DeviceType(category, product_id=None, product_name=None)` - Classify devices
- `createDevice(dev_id, unit)` - Check if device unit exists
- `searchCode(code, properties)` - Search for specific Tuya DP codes

### Communication
- `SendCommandTuya(DeviceID, switch, value)` - Send command via LAN or cloud
  (socket write runs on a background thread)
- `StatusDeviceTuya(code)` - Get current device status, records code in
  `local_used` for `LocalCovered()` while the poll loop is running
- `UpdateDomoticz(dev_id, unit, sValue, nValue, TimedOut)` - Update
  Domoticz device

### Local connections
- `LocalListener` - per-device persistent LAN connection. Only started
  for devices whose protocol version is not 3.1.
- `start_local_listeners()` / `stop_local_listeners()` - lifecycle
- `LocalCovered(dev_id, dev_name)` - returns the codes the cloud poll
  would still have to bring; `[]` means the local connection already
  covers everything and the cloud read can be skipped.

### Cloud usage
- `_usage_count(kind, amount=1)` - add to today's counter ('api' or 'msg')
- `_usage_load()` / `_usage_save(force=False)` - persist / restore the
  counter store via `USAGE_KEY`
- `_usage_totals()` - day / week / month totals
- `_usage_summary()` - single-line text for the log
- `_usage_forecast(kind)` / `_usage_forecast_lines()` - month forecast
  and warnings
- `_usage_midnight_report(ended_day)` - the report logged at midnight
- `_usage_create_devices()` / `_usage_update_devices(force=False)` -
  the `CloudCredits` units
- `_usage_tick()` - called from `onHeartbeat()`
- `_count_cloud_calls(cloud)` - wraps `Cloud._tuyaplatform()`

### Logging
- `_device_name(dev_id)` - resolve a raw id to a readable name
- `_format_value(value, max_len=80)` - readable DP value
- `_describe_local_dps(dev_id, dps)` - readable DP list
- `_dp_code(dev_id, dp_id)` - DP id -> function code
- `_log_local_message(dev_id, source, reply)` - INFO line per LAN message
- `_log_local_error(dev_id, source, reply)` - translated TinyTuya error
- `_log_pulsar_message(data)` - INFO line per Pulsar message
- `_log_realtime_capable_devices()` - startup overview of the Pulsar
  fast-path devices
- `_sys_date(d, kind='day')` - locale-aware date format

### Colour helpers
- `rgb_to_hsv(r, g, b)` - 0-255 scale, use for Tuya `colour_data`
- `hsv_to_rgb(h, s, v)` - 0-255 scale
- `rgb_to_hsv_v2` / `hsv_to_rgb_v2` - 0-1000 scale, only for
  `colour_data_v2` devices
- `brightness_to_pct` / `pct_to_brightness` - read min/max from schema
- `decode_colour_data(raw)` - **new**. Accepts a Tuya `colour_data`
  value in JSON or hex-string form and returns a Domoticz colour dict,
  or `None` when the value cannot be interpreted. Callers must handle
  `None` by leaving the tile untouched.
- `find_steady_lightmode(function)` - **new**. Finds the "steady" value
  in a `lightmode` enum (`steady` / `static` / `normal` / `constant`,
  falling back to index 2). Returns `None` when the device has no
  `lightmode` DP.

### Battery
- `is_battery_device(StatusProperties)` - correctly recognises a device
  with any of the battery codes, on both `str` and `list`/`dict` inputs
- `apply_battery_level(dev_id, level)` *(pending extraction)* - single
  place that writes a battery percentage to every unit of a device

### RGBIC Light Support
- `encode_draw_tool_command()` - Encode multi-LED commands
- `decode_draw_tool_status()` - Decode LED status
- `detect_white_channel_type()` - Detect RGBW vs RGB
- `send_draw_tool_command_local()` - Local LED command sending

## User Notes

### Device Not Working?
1. Check if device is in correct category
2. Verify device has proper DPS mapping
3. Check logs for error messages
4. Confirm the plugin is not in testdata mode
5. Test with tinytuya directly if possible

### Device responds to nothing after ~20 s
- Check the log line for the device's protocol version
  (`[protocol vX.Y]` in the initial IP scan). If it is v3.1 and the
  device still appears in a `Local connection to <name> established`
  line, the plugin is running a version older than 3.1.6.

### Light does not change colour
- On generic lights: check whether the plugin sends
  `work_mode = 'colour'` before `colour_data`. If only `colour_data`
  is sent, the device is in white mode and ignores it. Fixed in 3.1.9.
- On aromatherapy devices: check whether the plugin sends a steady
  `lightmode` before `colour_data` and **does not** send `work_mode`.
  Fixed in the #200 follow-up.

### Aromatherapy Light tile stays green while the humidifier is off
- Not a bug. The Light unit follows its own `Light` DP, which can be
  `true` while the humidifier's `Power` DP is `false`. Fixed in the
  #200 follow-up (the Light tile used to be coupled to `Power`).

### Aromatherapy RGB tile stays on / shows a hex string
- Both were fixed in the #200 follow-up. The RGB tile now follows the
  `Light` DP for its `nValue` and decodes the hex-string `colour_data`
  through `decode_colour_data()`.

### Aromatherapy Scene selector flips back
- `work_mode` (DP 109) is write-only on some aromatherapy firmware. The
  plugin now early-returns from `update_select_device()` when the
  device does not report the code, so the tile stays on what was last
  picked. Fixed in the #200 follow-up.

### Picking "colour" on the Aromatherapy Scene selector turns the device off
- Firmware behaviour, not a plugin bug. On this firmware DP 109 accepts
  `white` but not `colour`. The plugin no longer sends `work_mode` from
  the RGB handler, so picking a colour on the RGB unit does not turn
  the device off. Use the RGB unit for colours, not the Scene selector.

### Socket LED does not respond
- Check whether the plugin sends `switch_2`. If so, the plain `switch`
  handler is running for the LED unit instead of the LED handler.
  Fixed in 3.1.7.

### Protocol Issues
- Protocol 3.4 devices may need cloud fallback
- Check device version in device properties
- Enable debug logging for detailed communication logs

### Color Problems
- Check if device is RGB, RGBW, or RGBWW
- Verify `bright_value` max in device properties
- Enable debug logging to see `work_mode` and `colour_data` order
- `draw_tool` uses a non-linear colour code table, not RGB values
- Domoticz `m=3` colour dicts should carry only `m, r, g, b`

### Maxcio devices in general
- Almost all Maxcio Wi-Fi devices report protocol **v3.1** in the local
  IP scan. They are poll-only by design and do not work well with a
  persistent listener. The plugin handles this automatically from
  version 3.1.6 onwards.

### The credits devices show a lower number than the Tuya console
- Expected. The counters cover only this plugin. Other tools or
  projects on the same Tuya Cloud account are not included.
- On very old tinytuya versions the fallback in `_count_cloud_calls()`
  counts public method calls instead of HTTP requests, which can be
  lower than what Tuya actually bills.

### Bar chart on the credits devices is empty
- The plugin does not set Bar Ranges; set them once by hand in
  Setup → Devices → edit the device → bar-chart icon. The setting is
  saved with the device and survives restarts.

### Midnight report not in the log
- The report only fires when `_usage_tick()` sees a day rollover.
  Check that `onHeartbeat()` still calls `_usage_tick()`, and that the
  Domoticz system clock is correct.