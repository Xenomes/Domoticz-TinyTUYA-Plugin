# AGENTS.md

> Architecture and conventions for agents working on the TinyTUYA Domoticz plugin.

## Repository overview

`plugin.py` is the single file that contains all plugin logic. There is no
package structure; every helper lives at module level in that file.

The plugin runs as a DomoticzEx Python hardware plugin. Domoticz loads it
once per configured hardware instance, so every instance gets its own
Python process. Module-level globals are therefore naturally isolated
between instances — do not add cross-instance state or shared files.

## Runtime model

- Domoticz calls `onStart`, `onStop`, `onHeartbeat`, `onCommand`,
  `onConnect`, `onMessage`, `onDisconnect`, `onNotification`.
- `onHeartbeat` is called every few seconds. It does **not** do the
  heavy work directly: it spawns a background thread that runs
  `onHandleThread()` for the local path and, when the cloud poll
  interval has elapsed, for the cloud path. A module-level
  `_handle_lock` prevents two poll cycles from running at the same
  time.
- `onCommand` runs on the Domoticz main thread. The actual LAN or
  cloud socket write is performed on a background thread so a slow
  device cannot block Domoticz.
- LAN connections are persistent (`LocalListener`) and run in their
  own threads, one per device. They never touch the Domoticz API
  directly: `onHandleThread()` reads their most recent values with
  `listener.values()`.
- Pulsar realtime push messages arrive on the `tuya-connector-python`
  network thread. `_pulsar_on_message()` uses them as a trigger to
  re-run the plugin's regular status resolution for a single device
  (via `onHandleThread(..., target_dev_id=dev_id)`), except for a small
  set of device types that have a direct fast path.

## Directory layout

- `plugin.py` — the plugin
- `README.md`, `CHANGELOG.md`, `AGENTS.md`
- `tools/` — debug scripts
- `examples/`, `backup/`, `.devin/`

## Device type classification

`DeviceType(category, product_id=None, product_name=None)` maps the Tuya
category string to an internal device type. Some categories are
ambiguous and are resolved by `product_id` or `product_name` (see
*Known Issues*).

## Data structures

- `devs` — the Tuya device list as returned by the cloud, or loaded
  from `tuya-raw.json` in full-local mode.
- `properties[dev_id]` — dict with `functions` and `status` lists.
  Each entry has `code`, `type`, `values` (JSON string with
  `min`/`max`/`scale`/`step`/`unit`/`label`/`range`).
- `dps_map[dev_id] = {'by_code': {code: dp_id}, 'by_id': {dp_id: code}}`
- `result[dev_id]` — the most recent status list, in the same shape
  the cloud returns (`[{'code': ..., 'value': ...}, ...]`).
- `localtuya[dev_id] = {'ip': ..., 'version': ..., 'key': ...}` — what
  the UDP LAN scan found.
- `cloud_status_time[dev_id]` — timestamp of the last cloud status
  read, for rate limiting.

## Configuration

`DomoticzEx.Configuration()` is a persistent key/value store attached
to the hardware instance. Two kinds of keys are used:

- `getConfigItem(dev_id, 'key')` etc. — per-device settings, written
  once during the initial device creation (`setConfigItem(dev_id,
  {...})`).
- `getConfigItem(f"{dev_id}-{unit}", 'mode')` — per-selector state.
- `getConfigItem(USAGE_KEY)` — the cloud usage counter store.
- `getConfigItem(f"{dev_id}:rain", 'rain_24h')` — the last rain
  counter value for the weather station.

Do **not** add files. The plugin must remain self-contained and must
not create anything outside Domoticz's own plugin directory.

## Version bumping

The version number lives in the XML header:

    <plugin key="tinytuya" name="TinyTUYA" ... version="3.2.2" ...>
        ...
        <h2>TinyTuya Plugin - Hybrid Local / Cloud Control version 3.2.2</h2><br/>

Both places must match. `Parameters['Version']` is populated by
Domoticz from the header, so nothing else needs to change.

## Cloud usage counters

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

## LAN / Pulsar logging helpers

All plugin log output goes through three structured wrappers so every
line carries the same fixed fields in the same order:

    [device=X unit=U name="Y" ip=Z event=E] <message>

- `device` — Tuya device ID (= Domoticz DeviceID)
- `unit`   — Domoticz unit number, when the message concerns one unit
- `name`   — human-readable device name
- `ip`     — LAN IP, when known
- `event`  — short tag for what happened (startup, command, recovered, ...)

Fields are emitted in that fixed order. `name` and `ip` are filled in
automatically from `device=` via `_log_resolve()` when the caller does
not supply them. Values containing whitespace or quotes are quoted by
`_log_quote()`, so a single log line never breaks the `key=value`
pairing.

- `_log_quote(value)` — quotes a value if it contains whitespace or `"`.
- `_log_resolve(device, name, ip)` — fills in `name`/`ip` from the
  device ID via `_device_name()` and `localtuya`/`getConfigItem()`.
  Never raises.
- `_log_fields(device=None, unit=None, name=None, ip=None, event=None)` —
  builds the bracketed prefix `[device=<id> unit=<u> name="<name>"
  ip=<ip> event=<event>]`. All fields are optional.
- `Log(device=None, unit=None, name=None, ip=None, event=None, message="")`
  — INFO-level structured log line. Use for normal flow: LAN messages,
  Pulsar messages, device state changes, cloud fallbacks. Calls
  `DomoticzEx.Log()` internally.
- `Debug(device=None, unit=None, name=None, ip=None, event=None, message="")`
  — DEBUG-level structured log line. Same fields as `Log()`; only
  visible when Mode6 debugging is enabled. Calls `DomoticzEx.Debug()`
  internally.
- `Error(device=None, unit=None, name=None, ip=None, event=None, message="")`
  — ERROR-level structured log line. Use for unreachable devices,
  protocol errors, cloud failures, misconfiguration. Calls
  `DomoticzEx.Error()` internally.
- `_log_local_error(dev_id, source, reply)` — if the reply contains
  `Err`/`Error`: a clear ERROR line with the translated meaning from
  `_LOCAL_ERRORS` (901/902/904/905/914) and a hint. Repeats within
  `_LOCAL_ERROR_REPEAT = 3600` seconds go to Debug. Uses the
  structured `Error()` and `Debug()` helpers.
- `_log_local_message(dev_id, source, reply)` — INFO line for every
  message arriving over the LAN (status reply, push, heartbeat).
  Calls `_log_local_error()` first. Uses the structured `Log()` helper.
- `_log_pulsar_message(data)` — INFO line for every Pulsar message, in
  both the legacy and IoT Core shapes, before any processing. Uses the
  structured `Log()` helper.
- `_log_realtime_capable_devices()` — startup overview of devices
  covered by the Pulsar fast path (door contacts, motion sensors,
  doorbells, smoke detectors, water leak sensors, smart locks, human
  presence sensors), with OK / MISMATCH (not yet in Domoticz) /
  MISMATCH (orphaned in Domoticz). Uses the structured `Log()` and
  `Debug()` helpers.
- `_log_status(text)` — logs at Status level when available; falls back
  to `Log(event="cloud-usage", message=text)` on a Domoticz without
  `DomoticzEx.Status`.
- `_device_name(dev_id)` — best-effort human-readable name; tries the
  Tuya device list first, then `Devices[dev_id].Units[1].Name`, then the ID.
- `_sys_date(d, kind)` — formats a date using the locale of the system
  Domoticz runs on. Falls back to ISO when only C/POSIX is available.

**Important:** Do NOT use the standard library `logging` module for plugin
logging. Domoticz captures the plugin's output on its own, and the stdlib
logger writes to a different stream. Always use the structured `Log()`,
`Debug()`, and `Error()` helpers to ensure messages appear in the Domoticz
log. The only exception is the `_DomoticzPulsarLogHandler`, which exists
precisely to route `tuya-connector-python`'s own stdlib logging back into
the plugin's wrappers.

## Pulsar realtime fast paths

`_pulsar_on_message()` receives every realtime push from the Tuya IoT
Message Service. For most devices it simply triggers a targeted
`onHandleThread(..., target_dev_id=dev_id)` in a background thread, so
the regular poll path resolves the new state with the exact same code
that a normal poll would use. That path is always correct but does a
full LAN or cloud status read.

For a small set of device types the push is used **directly**: the DP
code is mapped to a known Domoticz unit, the value is converted with
the same helper the poll path uses, and `UpdateDomoticz()` is called
in-process with no extra network round-trip. These fast paths are only
applied when the mapping from DP code to unit is fixed by the device
type — for these categories the plugin never assigns a unit number
based on the per-device DP layout, so the mapping cannot drift.

- **Door contacts** (`dev_type == 'doorcontact'`, category `mcs` or
  `qt`-as-curtain excluded): `doorcontact_state` → Unit 1. Boolean,
  `True` = open.
- **Motion sensors** (`dev_type in ('sensor', 'switch/sensor')` with a
  `pir` or `pir_state` DP): any of those two codes → Unit 48.
  `value != 'none'` means detected. Other DP codes on the same device
  (temperature, humidity, battery) are handled in the same fast path
  block and fall through to the slow path when they do not match.
- **Doorbells** (`dev_type == 'doorbell'`): a fixed `doorbell_unit_map`
  routes each DP code to its known unit (1, 3-11). The
  `nightvision_mode` selector uses its schema values to translate the
  string value into the Domoticz level. The video doorbell aliases
  (`doorbell_calling`, `bell_ring`, `doorbell_ring`, `floodlight`,
  `light_switch`, `pir_sensor`) are handled in a second pass so the
  original DP names keep working on older firmware.
- **Smoke detectors** (`dev_type == 'smokedetector'`):
  `smoke_sensor_status` / `smoke_state` / `alarm_state` → Unit 1
  (switch, alarm/normal) and Unit 2 (text status). `PIR` → Unit 1.
  `battery_state` / `battery` / `battery_percentage` update the
  battery level of every unit.
- **Water leak sensors** (`dev_type == 'waterleak'`):
  `watersensor_state` / `leak_state` / `water_leak` / `alarm_state` →
  Unit 1. Battery handled the same way as the smoke detector.
- **Smart locks** (`dev_type == 'smartlock'`):
  `lock_motor_state` / `rtc_lock` / `switch` → Unit 1 (inverted for
  Domoticz, locked = closed). `alarm_lock` → Unit 2 (selector).
  The unlock methods (`unlock_ble`, `unlock_card`,
  `unlock_fingerprint`, `unlock_password`, `unlock_app`, `unlock_key`,
  `unlock_face`, `unlock_hand`, `unlock_temporary`) → Units 3-11.
- **Human presence sensors** (`dev_type == 'human_presence'`):
  `presence_state` → Unit 1, `sensitivity` → Unit 2 (selector),
  `near_detection` → Unit 3 (scaled), `far_detection` → Unit 4
  (scaled), `checking_result` → Unit 5 (selector), `target_dis_closest`
  → Unit 6 (scaled), `presence_state` selector → Unit 10. Battery
  handled the same way as the smoke detector.

All fast paths apply the **same** value conversion as the regular poll
path (`brightness_to_pct`, `hsv_to_rgb`, the `battery_state` →
`high/middle/low` mapping, and so on) so a device cannot end up with a
value from the fast path that disagrees with the next regular poll.

Any device type that is **not** listed above goes through the slow,
verified path. Adding a new fast path requires that the DP-to-unit
mapping is fixed for the whole category and that the value conversion
is already implemented (or is trivially a boolean or a battery
percentage).

## "Is not recovering" detection

Purpose: distinguish an occasional LAN hik that recovers by itself from
a device that has really gone away.

- **State:** `_local_failures[dev_id] = {'errors': [(t, err), ...],
  'last_success': t, 'alerted_at': t, 'started_at': t}`.
  A device is only warned about once per `LOCAL_ALERT_REPEAT` (1 h).
- **Helpers:**
  - `_local_note_success(dev_id)` — called by `_log_local_message()`
    for every non-error reply. Clears `errors`, restarts the settling
    period (`started_at`), and logs a single INFO line
    `Local connection to <name> recovered after N failed attempt(s)`
    when there had been errors.
  - `_local_note_failure(dev_id, err_code, now)` — called by
    `_log_local_error()`. Keeps only errors within
    `LOCAL_ALERT_WINDOW` (5 min). Raises the ERROR-level warning
    `... is not recovering: N failed attempt(s) ...` only when
    `LOCAL_ALERT_MIN_ERRORS` (3) is reached, the settling period
    `LOCAL_ALERT_GRACE` (5 min) has passed since the last success, no
    successful reply has happened since the first error in the burst,
    and `LOCAL_ALERT_REPEAT` has elapsed since the last warning.
- **Constants:** `LOCAL_ALERT_WINDOW`, `LOCAL_ALERT_MIN_ERRORS`,
  `LOCAL_ALERT_REPEAT`, `LOCAL_ALERT_GRACE`.
- **Bug to avoid:** both helpers must call
  `_local_failures.setdefault(...)` as their **first statement** so
  `state` exists before it is read. A previous version of the patch
  referenced `state` before it was created, giving
  `UnboundLocalError: cannot access local variable 'state'`.

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

    <plugin key="tinytuya" name="TinyTUYA" author="Xenomes" version="3.2.2" ...>
        ...
        <h2>TinyTuya Plugin - Hybrid Local / Cloud Control version 3.2.2</h2><br/>

`Parameters['Version']` is populated by Domoticz from the header, so no
other file needs changing.

**3.2.2 is the current working version.** It extends the Pulsar
realtime fast paths to cover doorbells, smoke detectors, water leak
sensors, smart locks and human presence sensors (see *Pulsar realtime
fast paths*). Both version strings in the header already say 3.2.2.

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
| `local-control` | Changes to `LocalListener`, `LocalCovered`, LAN polling or the wake-up |
| `cloud` | Changes to Pulsar, cloud fallback, or the Tuya IoT API |
| `pulsar` | Changes to the realtime fast paths or the Pulsar listener |
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
- New Pulsar fast path: `enhancement` + `pulsar`
- New usage counter or forecast change: `enhancement` + `cloud-usage`
- Log line missing or wrong: `bug` + `logging`
- Aromatherapy follow-up: `bug` + `device-support` + `color`
- Sleeping device / wake-up work: `enhancement` + `local-control`

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
- Before the first connect of a listener that is not connected, or of a
  device that recently failed, call `_wake_device(dev_id)` first. The
  wake-up is throttled per device by `LOCAL_WAKE_MIN_INTERVAL`.
- IR controllers (`smartir`, `infrared`, `infrared_ac`) get no listener
  and no local status read at all; they only accept send-IR commands.

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
- Use the structured `Log()`, `Debug()`, and `Error()` helpers for all
  device-bound log lines. They build a grep-able prefix
  `[device=<id> unit=<u> name="<name>" ip=<ip> event=<event>]` and
  forward to `DomoticzEx.Log/Debug/Error` internally.
- Do **not** call `DomoticzEx.Log/Debug/Error` directly from the plugin
  body. The wrappers are the single entry point; the only exceptions are
  `_log_status()` (which uses `DomoticzEx.Status` when available and
  falls back to `Log(event="cloud-usage", message=text)`) and the
  wrappers themselves.
- All fields in the structured helpers are optional. A line without
  device context (e.g. account-wide summaries) can omit those fields;
  `name` and `ip` are then resolved from `device=` automatically.
- `_log_local_message()` and `_log_pulsar_message()` must never raise:
  logging must not be able to break a connection. Wrap the body in
  try/except if the surrounding code can throw.
- Repeated TinyTuya errors are throttled in `_log_local_error()` via
  `_local_error_logged`; keep the throttle key as `(dev_id, err)`.
- `_device_name()` is the single place that resolves a raw `dev_id` to
  a name for log output. Do not add local lookups elsewhere.
- The "is not recovering" state must be created with
  `_local_failures.setdefault(...)` as the first statement of both
  `_local_note_failure()` and `_local_note_success()`, so `state` always
  exists before it is read.
- Watch the argument order: the wrapper signatures put `event=` before
  `message=`, and both are keyword-only in practice. Never pass a
  positional argument after a keyword argument — Python raises
  `SyntaxError: positional argument follows keyword argument` at import
  time and the whole plugin fails to load.

### Pulsar fast paths
- Only add a fast path for a device type where the DP-to-unit mapping is
  fixed by the category — a door contact always uses Unit 1, a motion
  sensor always Unit 48, and so on. Device types whose unit numbers
  depend on the per-device DP layout (switches, lights, covers,
  thermostats, ...) must always go through the verified slow path.
- The value conversion in the fast path must be identical to the poll
  path. Reuse the same helper (`brightness_to_pct`, the `high` /
  `middle` / `low` battery mapping, `hsv_to_rgb`) — never reimplement.
- If a fast path cannot confidently interpret a value (unknown selector
  string, unexpected payload), fall through to the slow path instead of
  writing a guessed value.
- A fast path returns immediately after handling its own DP. Do not
  return from the outer function before all matching DPs in the same
  message have been processed — doorbell messages carry several DPs at
  once.
- `_log_realtime_capable_devices()` must be extended whenever a new
  device type gains a fast path, so the startup log lists it in the
  realtime overview.

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
- **Sleeping WiFi modules**: a device that is online but refuses the
  LAN connection with 901 is probably in the Tuya low-power mode.
  `_wake_device()` sends a UDP discovery broadcast first; see
  *Sleeping Tuya WiFi modules*.

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

### `UnboundLocalError: cannot access local variable 'state'`
- Symptom: every LAN reply logs
  `Local: could not log incoming message for <id>: cannot access local
  variable 'state' where it is not associated with a value`, and the
  device falls back to the cloud on every poll.
- Cause: in `_local_note_failure()` or `_local_note_success()`, `state`
  is read before `_local_failures.setdefault(...)` has created it.
- Fix: `state = _local_failures.setdefault(dev_id, {...})` must be the
  **first** statement in both helpers.

### `SyntaxError: positional argument follows keyword argument`
- Symptom: Domoticz refuses to load the plugin with
  `Error: TinyTuya: (tinytuya) failed to load 'plugin.py'.
   Exception: 'SyntaxError: positional argument follows keyword argument
   (plugin.py, line N)'.`
- Cause: a leftover log-level constant from the pre-structured-logging
  code was passed as a **positional** argument *after* the keyword
  arguments. Typical shape:

      Log(event='device', message=f"…", DomoticzEx.ERROR)   # wrong

  The old `DomoticzEx.Log(message, DomoticzEx.ERROR)` form used a
  second positional argument for the level. The wrapper signature does
  not have that, so the leftover constant becomes a syntax error at
  import time and the whole plugin fails to load.
- Fix: drop the constant and, if the original intent was ERROR-level,
  use `Error()` instead of `Log()`:

      Error(event='device', message=f"…")

- Where it appeared: `UpdateDevice()` had exactly one such line
  (`Failed to remove device idx …: …`, `DomoticzEx.ERROR`). Search the
  file for `, DomoticzEx.ERROR)` and `, DomoticzEx.LOG)` after any
  future bulk edit.

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
  cloud usage counters, extended structured logging, wake-up of
  sleeping modules, LAN failure detection, and expanded Pulsar fast
  paths (doorbell, smoke detector, water leak, smart lock, human
  presence).

## Recent Work

### Current (Version 3.2.2)

**Pulsar realtime fast paths expanded**

The list of device types that are handled directly from the realtime
push (no extra network round-trip) is extended beyond door contacts and
motion sensors to cover:

- **Doorbell** (`sp`) — a fixed unit map routes `doorbell_active`,
  `floodlight_switch`, `motion_switch`, `basic_indicator`,
  `decibel_switch`, `basic_private`, `motion_tracking`,
  `motion_area_switch`, `siren_switch`, `nightvision_mode` (selector)
  and the video-doorbell aliases (`doorbell_calling`, `bell_ring`,
  `doorbell_ring`, `floodlight`, `light_switch`, `pir_sensor`) to their
  Domoticz units in-process. All matching DPs in a single push are
  processed; the fast path does not return after the first one.
- **Smoke detector** (`qt` without "curtain", `ywbj`) —
  `smoke_sensor_status` / `smoke_state` / `alarm_state` update Unit 1
  (switch) and Unit 2 (text status). `PIR` updates Unit 1. Battery
  codes update the battery level of every unit.
- **Water leak sensor** (`sj`) — `watersensor_state` / `leak_state` /
  `water_leak` / `alarm_state` update Unit 1. Battery handled the same
  way.
- **Smart lock** (`ms`, `jtmspro`) — Unit 1 (lock state, inverted for
  Domoticz), Unit 2 (`alarm_lock` selector), Units 3-11 (unlock
  methods). Battery handled the same way.
- **Human presence sensor** (`hps`) — Unit 1 (`presence_state`),
  Unit 2 (`sensitivity` selector), Unit 3 (`near_detection`),
  Unit 4 (`far_detection`), Unit 5 (`checking_result` selector),
  Unit 6 (`target_dis_closest`), Unit 10 (`presence_state` selector).
  Battery handled the same way.

All fast paths use the same value conversion as the regular poll path,
so a device cannot end up with a value from the fast path that
disagrees with the next regular poll. Any device that is not covered by
one of the fast paths still goes through the verified slow path
(`onHandleThread(..., target_dev_id=dev_id)`) in a background thread.

`_log_realtime_capable_devices()` now lists all fast-path device types
in the startup overview, not just door contacts, motion sensors and
doorbells.

### Latest released (Version 3.2.1)

**Structured logging** — every plugin log line now goes through
`Log()`, `Debug()`, or `Error()` and carries the same fixed fields:

    [device=X unit=U name="Y" ip=Z event=E] <message>

- New wrappers with a fixed field order and an optional `unit=` field.
  `name` and `ip` are auto-resolved from `device=` via `_log_resolve()`.
- `_log_quote()` quotes values with whitespace or quotes so a single
  log line never breaks the `key=value` pairing.
- Every direct `DomoticzEx.Log/Debug/Error` call in the plugin body
  replaced by the matching wrapper with a per-call-site `event=` tag
  (`startup`, `shutdown`, `command`, `cloud-init`, `ip-scan`, `local`,
  `cloud-usage`, `pulsar`, `create`, `update`, `wake-up`, `draw-tool`,
  ...).
- `_log_status()` now falls back to `Log(event="cloud-usage", …)`
  instead of `DomoticzEx.Log` on a Domoticz without `DomoticzEx.Status`.
- The `_DomoticzPulsarLogHandler` routes `tuya-connector-python`'s own
  stdlib logging through the wrappers.
- All device-bound log lines can now be filtered by device ID, event
  type, or IP address using grep, making it easier to trace activity
  for a specific device across LAN, Pulsar, and cloud sources.
- No stdlib `logging` module used by the plugin itself; the only
  consumer is the `tuya-connector-python` handler described above.
- The bulk conversion introduced exactly one
  `SyntaxError: positional argument follows keyword argument` in
  `UpdateDevice()`; it was fixed in the same release by converting the
  offending line to `Error(...)`. See *Known Issues* for the pattern
  to search for after future bulk edits.

**Aromatherapy #200 follow-up**

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
  a steady `lightmode` first, using `find_steady_lightmode()`.
- `Light On` (Unit 2) now also sets the steady lightmode, so the light
  does not start in the cycling multicolour mode it defaults to.
- `update_select_device()` early-returns when the device does not
  report the requested code, so the Scene (work_mode) tile no longer
  flips back to `white` on every poll just because DP 109 is
  write-only on this firmware.

**Sleeping device wake-up**

- `_wake_device(dev_id)`: sends a UDP discovery broadcast before the
  first TCP connect of a device that recently failed, to pull a
  sleeping Tuya WiFi module back online. Throttled per device by
  `LOCAL_WAKE_MIN_INTERVAL`. Constants
  `LOCAL_WAKE_BEFORE_CONNECT`, `LOCAL_WAKE_MIN_INTERVAL`.
- Called from `LocalListener.listen()` (before the `tinytuya.Device`
  call when `self.error` or not connected) and from the single-query
  fallback in `onHandleThread()` when
  `_local_failures[dev_id]['errors']` is not empty.
- State: `_local_last_wake[dev_id]`, cleared in
  `stop_local_listeners()`.

**LAN failure detection**

- `_local_note_success()` / `_local_note_failure()`: per-device
  detection of a device that keeps failing without a single successful
  reply in between. Logs a single ERROR warning `... is not recovering:
  N failed attempt(s) ...` when `LOCAL_ALERT_MIN_ERRORS` is reached
  inside `LOCAL_ALERT_WINDOW`, the settling period `LOCAL_ALERT_GRACE`
  has passed, no success has happened since the first error, and
  `LOCAL_ALERT_REPEAT` has elapsed. Logs a single INFO line
  `recovered after N failed attempt(s)` on the next successful reply.
- Throttles the noise from devices that hiccup occasionally, while
  still telling the user clearly when something is really wrong.

### Previous released (Version 3.2.0)
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
- **Extended logging** (pre-structured):
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

### Older notable releases
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

### Sleeping device testing
1. Pick a device that is online but has not been operated for a while,
   so its TCP listener may be closed.
2. Confirm from a shell next to Domoticz that
   `nc -zv <ip> 6668` fails.
3. Restart the plugin, or wait for the next poll with the device not in
   the local listener's `connected` state.
4. The log should show one wake-up followed by
   `Local connection to <name> established` and then
   `Local message from ... [status reply on connect]`.
5. Confirm with `nc -zv <ip> 6668` from the shell that the port is now
   open (the device was woken up by the broadcast).
6. Confirm that the wake-up is throttled: two consecutive polls of the
   same device should only show one wake-up attempt per
   `LOCAL_WAKE_MIN_INTERVAL` seconds.

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

### Pulsar fast path testing
For every device type that has a direct fast path (door contact, motion
sensor, doorbell, smoke detector, water leak sensor, smart lock, human
presence sensor):

1. Trigger a status change on the physical device (open a door,
   press the doorbell, spill water on the leak sensor, ...).
2. The corresponding Domoticz tile must update within a second or two,
   and the log must show a `Pulsar: fast path applied for <name>
   (<id>)` line for the DP that changed.
3. Confirm that the next regular poll does not contradict the fast
   path value.
4. On a doorbell, press the button and then trigger motion in quick
   succession — both units must update from their own pushes, and a
   single push carrying two DPs must update both.
5. On a smoke detector, trigger the test button: Unit 1 must switch to
   "alarm" and Unit 2 must show the text status.
6. On a smart lock, lock and unlock physically: Unit 1 must follow,
   and the corresponding unlock-method unit must be set for the method
   that was used.

### LAN failure detection testing
1. Unplug a device that is currently in the local listener's
   `connected` state, or block its port 6668 from the Domoticz host.
2. Wait for at least `LOCAL_ALERT_MIN_ERRORS` failed polls inside
   `LOCAL_ALERT_WINDOW`. You should see **one** ERROR line
   `Local connection to <name> ... is not recovering: N failed
   attempt(s) ...`.
3. Keep the device offline. The warning must not repeat until
   `LOCAL_ALERT_REPEAT` has passed.
4. Plug the device back in / unblock the port. The plugin should log
   `Local connection to <name> ... recovered after N failed attempt(s)
   (first error ..., last error ...)` and then
   `Local connection to <name> established`.
5. Hiccups shorter than `LOCAL_ALERT_MIN_ERRORS` inside the window must
   **not** produce the warning.

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
   TinyTuya code and hint must appear, prefixed with the structured
   fields.
2. Force the same error again within the hour: nothing new on ERROR,
   the repeat goes to Debug.
3. Watch a Pulsar-triggered device (door contact, motion sensor): a
   `Pulsar message from ...` INFO line appears even when the plugin
   decides to ignore it because the device is reachable locally.
4. Check a command to a device with a known LAN IP: the resulting
   `event=command` line must carry `device=`, `name=` and `ip=`. A
   call site that forgot `device=` shows only `event=command` — that is
   a bug in the call site, not the wrapper.
5. Try a name with spaces (e.g. a device renamed to "Voordeur sensor"
   in Domoticz) and confirm it appears as `name="Voordeur sensor"` with
   the quotes, so the `key=value` pairing stays intact.

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
- `Skipping local listener for <name> (IR controller: no local status)`
  — the device is an IR controller, has no local status, works through
  the cloud only, not an error
- `!!! Warning Plugin overruled by local json files !!!` — testdata
  mode, delete the `debug_*.json` files
- `Tuya cloud usage on <date> (final)` — the midnight report; the
  forecast lines right below it show the expected month total
- `Pulsar message from ... -- will be ignored` — expected for a device
  that is reachable locally
- `Pulsar: fast path applied for <name> ...` — a DP from a realtime
  push was written directly to its Domoticz unit; no extra network
  round-trip happened. If the tile did **not** update, the fast path
  either missed the DP (check the code against the list in this file)
  or the device's category is not what the fast path expects.
- `[LOCAL] Command queued: dp_id 109 = colour` — on an aromatherapy
  device this is a **bug**: DP 109 must not be sent from the RGB
  handler. If you see this line, the aromatherapy RGB handler is
  falling into the generic colour path.
- `Local connection to <name> ... is not recovering: N failed
  attempt(s) ...` — ERROR, raised at most once per `LOCAL_ALERT_REPEAT`
  when the plugin believes the device is really gone. Look for the
  matching `recovered after N failed attempt(s)` INFO line once the
  device answers again.
- `Local: could not log incoming message for <id>: cannot access local
  variable 'state'` — **bug**: `state` is read before
  `_local_failures.setdefault()` in `_local_note_failure()` or
  `_local_note_success()`. `setdefault` must be the first statement.

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
  for devices whose protocol version is not 3.1 and that are not IR
  controllers.
- `start_local_listeners()` / `stop_local_listeners()` - lifecycle
- `LocalCovered(dev_id, dev_name)` - returns the codes the cloud poll
  would still have to bring; `[]` means the local connection already
  covers everything and the cloud read can be skipped.
- `_wake_device(dev_id)` - send a UDP discovery broadcast to pull a
  sleeping Tuya WiFi module back online. Throttled per device.
- `_local_note_success(dev_id)` / `_local_note_failure(dev_id, err, now)`
  - per-device LAN failure tracking, feeds the "is not recovering"
  warning and the "recovered after N failed attempt(s)" INFO line.

### Pulsar realtime
- `start_pulsar_listener()` / `stop_pulsar_listener()` - lifecycle of
  the `TuyaOpenPulsar` client for this hardware instance.
- `_pulsar_on_message(msg)` - receives every realtime push. Logs it
  (via `_log_pulsar_message`), then applies a fast path for the
  supported device types or spawns a targeted
  `onHandleThread(..., target_dev_id=dev_id)` in a background thread.
- `_log_pulsar_message(data)` - INFO line for every message, before
  any processing.
- `_log_realtime_capable_devices()` - startup overview of the devices
  covered by the fast paths.

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
- `Log(device=None, unit=None, name=None, ip=None, event=None, message="")`
  - INFO-level structured log line
- `Debug(device=None, unit=None, name=None, ip=None, event=None, message="")`
  - DEBUG-level structured log line
- `Error(device=None, unit=None, name=None, ip=None, event=None, message="")`
  - ERROR-level structured log line
- `_log_quote(value)` - quote a value with whitespace or quotes
- `_log_resolve(device, name, ip)` - auto-fill name/ip from device ID
- `_log_fields(device=None, unit=None, name=None, ip=None, event=None)`
  - build the bracketed prefix
- `_log_status(text)` - Status-level log with a `Log(event="cloud-usage")`
  fallback
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
- `decode_colour_data(raw)` - Accepts a Tuya `colour_data` value in
  JSON or hex-string form and returns a Domoticz colour dict, or
  `None` when the value cannot be interpreted. Callers must handle
  `None` by leaving the tile untouched.
- `find_steady_lightmode(function)` - Finds the "steady" value in a
  `lightmode` enum (`steady` / `static` / `normal` / `constant`,
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

### Device is online but the plugin says 901 Unable to Connect
- The device is probably in the Tuya low-power mode: it answers UDP
  broadcasts but has closed the TCP listener. Confirm with
  `nc -zv <ip> 6668` from a shell next to Domoticz: it will fail with
  `No route to host` while the device is actually online. Operate the
  device once from the app; `nc` will then succeed.
- The plugin now sends a UDP wake-up (`_wake_device`) before the first
  TCP connect of a device that recently failed, so it should recover by
  itself. If the warning `is not recovering` appears, the device is
  genuinely offline or on a different IP.

### `cannot access local variable 'state'`
- Bug in the "is not recovering" helpers. `_local_failures.setdefault`
  must be the first statement of `_local_note_failure()` and
  `_local_note_success()`. Fixed in 3.2.1.

### `SyntaxError: positional argument follows keyword argument`
- Bug introduced by a bulk edit in 3.2.1, fixed in the same release.
  The cause is a leftover log-level constant passed positionally after
  keyword arguments, e.g. `Log(event=…, message=…, DomoticzEx.ERROR)`.
  Fix: use `Error(...)` instead. Search the file for
  `, DomoticzEx.ERROR)` if the plugin refuses to load.

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

### Pulsar push comes in, but the tile does not update
- Check the log for a `Pulsar: fast path applied for <name> ...` line.
  If it is missing, the DP code in the push is not in the fast path's
  list for that device type. If the DP code is only handled by the slow
  path, the plugin spawns a targeted `onHandleThread` in the
  background, which will log the regular status reply.
- If the device is reachable locally, the fast path still applies (it
  runs before the "is the device reachable locally" check). If no line
  appears at all, the push did not carry a DP the plugin knows about;
  check the preceding `Pulsar message from ...` INFO line for the raw
  DP codes.

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