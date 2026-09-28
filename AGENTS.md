# Domoticz TinyTUYA Plugin - Agent Documentation

## Project Overview

**Repository:** Domoticz-TinyTUYA-Plugin
**Main File:** plugin.py
**Purpose:** Domoticz plugin for Tuya IoT devices with hybrid local/cloud control
**Current Version:** 3.1.9
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

### Work mode must be set before colour data

- **Symptom:** Sending `colour_data` to a light whose `work_mode` is
  still `white` has no visible effect, or the device falls back to a
  rainbow/effect mode. The Domoticz colour tile updates but the physical
  light does not.
- **Cause:** Tuya firmware ignores `colour_data` while `work_mode` is
  `white`. The value is buffered but not applied.
- **Fix:** whenever `Set Color` is sent with a colour-mode payload
  (`Color['m'] == 3`), the plugin sends `work_mode = 'colour'`
  immediately before `colour_data`.
- **Applies to:** `light` Unit 1, `light` Unit 2, `aromatherapy` Unit 6,
  `dehumidifier` Unit 6, socket LED (Unit 2).

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
- Unit 1: Power (main switch)
- Unit 2: Light (light switch)
- Unit 3: Lightmode (selector)
- Unit 4: Mist grade (small/big selector)
- Unit 5: Scene/Work mode (white/colour/scene/music selector)
- Unit 6: RGB (color control)
- Unit 6 `Set Color` (m==3) must send `work_mode = 'colour'` before
  `colour_data`, and convert Domoticz RGB to Tuya HSV with `rgb_to_hsv`.
- Unit 6 state update must respect `work_mode`: when the device reports
  `white` (or anything other than `colour`) or the RGB switch is off,
  the Domoticz RGB unit must not be forced to `nValue = 1`.

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

    <plugin key="tinytuya" name="TinyTUYA" author="Xenomes" version="3.1.9" ...>
        ...
        <h2>TinyTuya Plugin - Hybrid Local / Cloud Control version 3.1.9</h2><br/>

`Parameters['Version']` is populated by Domoticz from the header, so no
other file needs changing.

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

### Command Handling
- Pattern: check function code, send command, update Domoticz
- Special cases for dimmers, colors, multi-channel devices
- When a colour command is sent, set `work_mode` before `colour_data`.
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
- **`work_mode` must be set before `colour_data`** on every device that
  has a `work_mode` enum.
- **`nValue` on an RGB unit must follow the on/off state**, not be
  hardcoded to `1`.
- **Colour dict for `m=3` should only carry `m, r, g, b`.** Extra fields
  can cause Domoticz to ignore the update.

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
- **3.x:** Hybrid local/cloud control with Pulsar realtime updates

## Recent Work

### Latest Changes (Version 3.1.9)
- Add Thermor Niseko HVAC support (PR #221, thanks @Chrominator):
  optional units 30–34 for turbo, quiet, sleep, energy_save, healthy;
  half-degree temperature scale for `product_id == '9xvzf8c0bg33eenj'`.
- Fix light colour control: `work_mode` set before `colour_data` on
  `light` Unit 1, `light` Unit 2, `aromatherapy` Unit 6,
  `dehumidifier` Unit 6.
- Fix `NameError: Colour` in `dehumidifier` Unit 6 handler — renamed to
  `Color`.
- Fix `KeyError: 's'` in `aromatherapy` and `dehumidifier` Unit 6
  `Set Color`: use `rgb_to_hsv(Color['r'], Color['g'], Color['b'])`
  instead of the non-existent `Color['s']` and the wrong `Color['t']`.
- Humidifier RGB unit `nValue` follows `work_mode` instead of being
  hardcoded to `1`.
- **Code cleanup (same release):** SmartLock unlock methods, irrigation
  area switches, switch multi-gang, Thermor HVAC extras and doorbell
  status updates are now tuple-driven loops. This incidentally fixed a
  pre-existing bug where the doorbell's Unit 7 status update used
  `motion_area_switch` instead of `motion_tracking`.

### Previous notable releases
- `3.1.8`: Socket LED `switch_2` guard, light colour follow-up
- `3.1.7`: Skip covers in start_local_listeners (#216) and socket LED `switch_2` guard
- `3.1.6`: Skip all v3.1 devices in start_local_listeners (Télé plug and future v3.1 devices)
- `3.1.5`: Skip covers in start_local_listeners (#216)
- `3.1.4`: Local connection coverage, non-blocking SendCommandTuya
- `3.1.3`: Pulsar per-instance logging, smarter cover dispatch
- `3.1.2`: Cover fix follow-ups (#208)
- `3.1.1`: RGBW/RGBWW white channel support for draw_tool
- `3.1.0`: Add aromatherapy device (#200)
- `3.0.9`: Add SmartLock unlock methods (#205)
- `3.0.8`: Fix battery device detection, remove dead code
- `3.0.7`: Fix local status fetch for Tuya v3.4 devices
- `3.0.6`: Cloud fallback for non-local devices in local poll path
- `3.0.5`: Add missing DeviceModelMapping() helper
- `3.0.4`: DPS mapping robustness
- `3.0.3`: Prevent IR/sub-devices from crashing the whole poll run
- `3.0.2`: Fix infrared device support and command handling bugs
- `3.0.1`: Fix for category detection of 'tdq'
- `3.0.0`: Release of hybrid version
- `3.0.0-rc.3`: Weather station barometer/rain units (PR #210) and multi-zone irrigation support (PR #209)
- `3.0.0-rc.2`: Add refresh button functionality (Mode5) from PR #211
- `3.0.0-rc.1`: Merge Master branch changes (2.4.0-2.4.5) into Hybrid

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
   - The log should show `work_mode = 'colour'` sent before `colour_data`
4. Pick white
   - The light must return to white and honour the brightness slider

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

### Colour helpers
- `rgb_to_hsv(r, g, b)` - 0-255 scale, use for Tuya `colour_data`
- `hsv_to_rgb(h, s, v)` - 0-255 scale
- `rgb_to_hsv_v2` / `hsv_to_rgb_v2` - 0-1000 scale, only for
  `colour_data_v2` devices
- `brightness_to_pct` / `pct_to_brightness` - read min/max from schema

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
- Check whether the plugin sends `work_mode = 'colour'` before
  `colour_data`. If only `colour_data` is sent, the device is in white
  mode and ignores it. Fixed in 3.1.9.

### Humidifier RGB stays on
- Check whether the `nValue` of Unit 6 is forced to `1` regardless of
  `work_mode`. Fixed in 3.1.9.

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