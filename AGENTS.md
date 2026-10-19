```markdown
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
  time. **`RefreshDevice()` also acquires this lock.**
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
- `.gitignore` — ignores `tuya-raw.json`, `snapshot.json`, `__pycache__`,
  `tools/dump.json`, `tools/creds.json`
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
- `getConfigItem(f"{dev_id}:motion", 'last_pic')` — the last value of
  the camera's `movement_detect_pic` DP, used to deduplicate motion
  events between the Pulsar fast path and the regular poll loop.

Do **not** add files. The plugin must remain self-contained and must
not create anything outside Domoticz's own plugin directory.

## Version bumping

The version number lives in the XML header:

    <plugin key="tinytuya" name="TinyTUYA" ... version="3.2.7" ...>
        ...
        <h2>TinyTuya Plugin - Hybrid Local / Cloud Control version 3.2.7</h2><br/>

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
- `_merge_pulsar_into_result(dev_id, status_list)` — writes the DP
  values from a Pulsar push into `result[dev_id]` so the next
  cloud-fallback read does not overwrite the fresh value with a stale one.
  Called once at the top of `_pulsar_on_message()`.
- `_log_realtime_capable_devices()` — startup overview of devices
  covered by the Pulsar fast path (door contacts, motion sensors,
  doorbells, smoke detectors, water leak sensors, smart locks, human
  presence sensors, cameras), with OK / MISMATCH (not yet in Domoticz) /
  MISMATCH (orphaned in Domoticz). Uses the structured `Log()` and
  `Debug()` helpers.
- `_log_status(text)` — logs at Status level when available; falls back
  to `Log(event="cloud-usage", message=text)` on a Domoticz without
  `DomoticzEx.Status`.
- `_device_name(dev_id)` — best-effort human-readable name; tries the
  Tuya device list first, then `Devices[dev_id].Units[1].Name`, then the ID.
- `_sys_date(d, kind)` — formats a date using the locale of the system
  Domoticz runs on. Falls back to ISO when only C/POSIX is available.
- `UpdateDomoticz(ID, Unit, sValue, nValue, TimedOut, AlwaysUpdate=0, source="poll")`
  — writes a value to a Domoticz unit. The `source=` keyword argument
  (default `"poll"`) appears in the log line as `[source] Update device: ...`
  so a reader can tell which engine wrote the value. Non-default callers use
  `"pulsar"` (Pulsar fast paths), `"command"` (onCommand), `"credits"`
  (_usage_update_devices), `"refresh"` (RefreshDevice and one-off reads),
  or `"motion-reset"` (the camera motion auto-reset).

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
- **Security cameras** (`dev_type == 'camera'`, category `cdsxj`): only
  the motion event is handled directly. The Raw DP
  `movement_detect_pic` is compared against the last value stored in
  the plugin config under `{dev_id}:motion` / `last_pic`; when the
  value changed, `_camera_motion_check()` pulses Unit 21 (a Motion
  Sensor) to "On". Every other camera DP goes through the verified
  slow path.
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

The fast paths do **not** pass `AlwaysUpdate=1` to `UpdateDomoticz()`. The
fresh value is kept in sync with the poll path by calling
`_merge_pulsar_into_result()` at the top of `_pulsar_on_message()`, which
writes the pushed DP values into `result[dev_id]` so that a subsequent
`CloudFallback()` (which returns held values when rate-limited) does not
overwrite the fresh value with a stale one.

Any device type that is **not** listed above goes through the slow,
verified path. Adding a new fast path requires that the DP-to-unit
mapping is fixed for the whole category and that the value conversion
is already implemented (or is trivially a boolean or a battery
percentage).

## Camera motion event tracking

Purpose: cameras have no boolean "motion detected" DP. The only motion
signal is the Raw DP `movement_detect_pic`, which is empty until
something happens and then contains a unique base64 blob (a timestamp +
snapshot path). So **"the value changed" IS the motion event.**

Two channels can observe the same change — the Pulsar fast path and the
regular cloud-poll loop — so the plugin needs to deduplicate. It does
that by storing the last seen value in the plugin config under
`{dev_id}:motion` / `last_pic`. Both channels call
`_camera_motion_check()`:

```python
def _camera_motion_check(dev_id, current_value, source):
    if current_value is None or current_value == '':
        return                                          # nothing to report
    stored = getConfigItem(f"{dev_id}:motion", 'last_pic') or ''
    if str(current_value) == str(stored):
        return                                          # already handled
    setConfigItem(f"{dev_id}:motion", {'last_pic': current_value})
    _camera_trigger_motion(dev_id, source=source)
```

The first channel to see the new value triggers; the second sees the
same value and does nothing. A motion is therefore **never published
twice** for the same event, regardless of which channel sees it first.

### Auto-reset

`_camera_trigger_motion()` pulses Unit 21 to "On" and schedules a reset
back to "Off" after `CAMERA_MOTION_RESET_SECONDS` (15 s). A per-device
generation counter in `_camera_motion_gen` cancels a pending reset when
a newer motion arrives, so the sensor stays "On" for the full window
after the **most recent** motion — the same pattern a real PIR would
produce.

- **Constants:** `CAMERA_MOTION_RESET_SECONDS = 15`,
  `CAMERA_MOTION_UNIT = 21`.
- **State:** `_camera_motion_gen[dev_id]` — an integer that is
  incremented on every new motion. The reset thread compares the
  current value to its captured generation and exits silently if they
  differ.
- **Cleanup:** `_camera_motion_gen` is small and per-process; it does
  not need to be cleared in `onStop()`, but adding it there would be
  harmless.
- **Do NOT set an Off Delay on Unit 21** in Domoticz. The plugin
  resets the sensor itself, with a generation counter that a Domoticz
  Off Delay cannot replicate. An Off Delay would race the plugin's
  reset and could turn the sensor off too early or too late.
- **Log lines:**
  - `[device=X unit=21 name="Y" event=motion] motion detected via pulsar, unit will reset in 15s`
  - `[device=X unit=21 ...] Update device: ... sValue:1 nValue:1 ... [pulsar]` (the On write)
  - `[device=X unit=21 ...] Update device: ... sValue:0 nValue:0 ... [motion-reset]` (the Off write, after the reset thread fires)

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

## Orphaned devices

Purpose: detect and handle devices that exist in Domoticz for this hardware
instance but are no longer reported by Tuya (removed from the app, re-paired
with a new ID, or factory reset).

- **Detection:** After the device-creation loop in `onHandleThread()`,
  still inside the `if startup and not local:` block, the plugin compares
  `devs` (Tuya's current device list) with `Devices` (Domoticz's device
  list for this hardware instance). Any ID in `Devices` that is not in
  `devs` and is not the plugin's own `USAGE_DEVICE_ID` is considered
  orphaned. The scan runs **once per startup**, not per device — it is
  placed after the `for dev in devs:` loop.
- **Marking inactive:** `_mark_orphaned_device_inactive(dev_id, dev_name)`
  sets `Used = 0` on every unit of the device via
  `unit.Update(Log=False, UpdateProperties=True)`, so Domoticz stops
  treating it as a live sensor and stops generating "did not update"
  warnings. The device is **not** deleted — the user can decide whether
  to remove it manually.
- **Why `UpdateProperties=True`:** setting `unit.Used = 0` alone does
  not persist the flag to the Domoticz database. Only
  `UpdateProperties=True` writes `Used` (together with `Name`,
  `SignalLevel`, `BatteryLevel`, `Image`, `Type`, `SubType`,
  `SwitchType`, `Description`, `Color`) to the database. Available from
  Domoticz 2024.4.16100. This was the root cause of the "orphaned device
  sub-units remain active" bug: without `UpdateProperties=True`, the
  helper silently logged success on every heartbeat while the units
  stayed `Used=1`.
- **Remembering:** `orphaned_devices` is a module-level set that stores
  all orphaned IDs. It is filled once during startup and cleared in
  `onStop()`. Every update path checks this set before touching a device.
- **Guard points:** The following functions check `dev_id in orphaned_devices`
  and skip the device early:
  - Main polling loop (`for dev in devs:` in `onHandleThread`)
  - Pulsar handler (`_pulsar_on_message`)
  - Pulsar realtime overview (`_log_realtime_capable_devices`)
  - IP scan result logger (`_log_local_scan_results`)
  - `RefreshDevice()` — **sinds PR #230** gebruikt deze functie
    `onHandleThread(False, False, target_dev_id=DeviceID)` en past de
    globale `devs`-lijst niet meer aan. Hierdoor kan de orphan scan
    aan het einde van `onHandleThread()` geen andere apparaten per
    ongeluk als orphaned markeren.
  - `onCommand()`
- **Logging:** One clear log line per orphaned device at startup using
  the structured logging wrappers, listing the unit numbers that were
  flipped to inactive:

  ```
  [device=<id> name=<name> event="device removed"] no longer reported by Tuya, marked inactive in Domoticz (units: 1, 2, 3)
  ```

  The event tag is `"device removed"` for easy grepping. Units that were
  already `Used=0` are skipped silently; only the freshly marked units
  appear in the list.
- **Constants:** None needed; this is pure bookkeeping with a set.
- **Bug to avoid:** when a device is re-added in the Tuya app with the
  **same ID** (unlikely but possible if it was just a network hiccup),
  the plugin will stop treating it as orphaned on the next restart, but
  the units will still be marked `Used=0` in Domoticz. The user must
  re-enable them manually. This is intentional — we cannot safely guess
  whether the user wants the old device back.

## Known Issues

### Security camera support (`cdsxj`)

**What it is:** Tuya security cameras (category `cdsxj`, e.g. the
"Security Camera" device with `product_id = he4r8lisqbynliun`) create
21 units. Units 1–20 are switches/selectors/values; **Unit 21 is a
real Motion Sensor** (Switchtype=8).

**Why 21 units and not a Domoticz camera widget:** the DomoticzEx
Python plugin API has **no camera device type**. There is no Type/
Subtype combination that produces a camera widget. Cameras in Domoticz
live in a separate table (Setup → More Options → Camera), and a plugin
cannot write to that table. So the plugin exposes the camera's *state*
and *controls* (switches, selectors, motion event) as ordinary
Domoticz units, and the user adds the camera to the Camera table
manually if they want a live view.

**Unit numbering:** the plugin reuses the doorbell's unit numbers
wherever the DP overlaps (units 2, 3, 5, 6, 9, 10, 12, 13), so a
user's dzVents scripts, scenes and graphs that referenced those
doorbell units keep working when the same DP shows up on a camera.
Camera-only DPs fill units 1, 4, 7, 8, 11, and 14–21.

**Motion handling:** see the *Camera motion event tracking* section.
`movement_detect_pic` is a Raw base64 DP that is empty until something
happens; the plugin treats **any change** of the value as a motion
event, stores the last seen value in the config to deduplicate between
Pulsar and the poll loop, and pulses Unit 21 to "On" with an automatic
reset after 15 s. A generation counter keeps the sensor "On" until 15 s
after the **most recent** motion, not the first.

**Not exposed** (deliberately):

- `sd_status`, `sd_storge` — internal SD-card state; no useful Domoticz
  widget.
- `initiative_message`, `movement_detect_pic` (as a raw value) —
  Raw blobs; only used internally as the motion trigger.
- `motion_area`, `ipc_res_change` — Raw JSON strings; static
  configuration that would need a custom widget to be useful.
- `device_restart`, `sd_format`, `onvif_change_pwd` — one-shot,
  risky actions that should not have a persistent Domoticz button.
- `onvif_*`, `ipc_magnification`, `ipc_save_percent` — configuration
  that is set once by the Tuya app.

**User-facing note:** see *User Notes → Camera has no video stream in
Domoticz* for what the user can do instead.

### White colour temperature not applied / colour wheel does nothing (fixed in 3.2.6)

**Symptom:** On Calex and other `dj`-category bulbs, the colour wheel
changes nothing physically. The device is created correctly, on/off works,
brightness works, but the white-temperature slider has no effect on the
bulb. Issue #226.

**Root cause (two separate bugs):**

1. **`temp_value_scale()` was converting in the wrong direction.** It is
   called from `SendCommandTuya()` and must map the Domoticz 0–255 scale
   to the device's raw Tuya value. The original implementation did the
   opposite, producing wrong (often clamped) values that the bulb
   ignored.

2. **`raw_max` was guessed from the value instead of tracked explicitly.**
   In the poll loop's `work_mode == 'white'` branch, the code used
   `raw_max = 1000 if raw_temp > 255 else 255`. If Domoticz starts with
   a bulb whose `temp_value_v2` happens to be below 255, the plugin
   assumes a 255-scale device and inverts the temperature incorrectly.
   The DP code (`temp_value` vs `temp_value_v2`) already tells you which
   scale the device uses — no guessing needed.

**Fix:**

1. `temp_value_scale()` now converts **from** the Domoticz 0–255 scale
   **to** the raw value. The parameter was renamed from `raw` to
   `scaled` to make the direction explicit in the signature:

   ```python
   def temp_value_scale(device_functions, actual_function_name, scaled):
       # ... convert 0-255 -> device raw value
       return round(max_value + (min_value - max_value) * (scaled / 255))
   ```

2. The poll loop now sets a `temp_is_v2` flag while reading the DP, and
   derives `raw_max` from **that flag**, not from the value:

   ```python
   temp = StatusDeviceTuya('temp_value')
   temp_is_v2 = False
   if temp is None:
       temp = StatusDeviceTuya('temp_value_v2')
       temp_is_v2 = True
   if temp is not None:
       raw_temp = int(temp)
       raw_max = 1000 if temp_is_v2 == True else 255
       t = round((raw_max - raw_temp) * 255 / raw_max)
       t = min(255, max(0, t))
       color_dict = {'m': 2, 'r': 0, 'g': 0, 'b': 0, 't': t, 'cw': 0, 'ww': 0}
   ```

3. `UpdateDomoticz()` colour branch now passes `UpdateProperties=True`
   when writing a colour, so the colour value is persisted to the
   database (not just held in memory):

   ```python
   unit.Update(UpdateProperties=True, Log=True)
   ```

**Testing:** On a Calex GU10 (`colour_data_v2` / `temp_value_v2`), open
the colour wheel and move the white-temperature slider:

- The physical bulb must change temperature (warm ↔ cold).
- The log must **not** show `raw_max = 255` for a v2 device.
- After a Domoticz restart, the colour and temperature must survive
  (the `UpdateProperties=True` fix).

**PR:** [#229](https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/pull/229),
fixing [#226](https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/issues/226).

### Colour tile stays on the old colour / too dark (fixed in 3.2.6)

**Symptom:** The colour tile lags behind the app, or shows a dimmed
version of the chosen colour; on v1 lamps the slider sits at 100% no
matter what; on v2 lamps (Calex GU10) the colour never updates at all.

**Root cause:** `decode_colour_data()` only handled the JSON and 6-byte
hex forms, so the 7-byte v1 hex frame fell through to a branch that
treated the first 3 bytes as live RGB — but those bytes are the *dimmed*
RGB, not the colour. Separately, `_hsv_to_domoticz()` scaled RGB by `v`,
baking brightness into the colour.

**Fix:** add a 7-byte branch (h = bytes 3-4, s = byte 5, v = byte 6);
add a 6-byte branch back in case it is accidentally removed; drop `v`
from the RGB calculation in `_hsv_to_domoticz()`.

**Testing:** on a v1 lamp, set a colour at low brightness; the tile
must show the full-brightness colour and the slider must drop.

### Colour change takes 3 seconds (fixed in 3.2.6)

**Symptom:** `[LOCAL FAILED] ..., fallback to cloud: None` on every
colour change, followed 3 s later by `[CLOUD] Command sent to Tuya`.

**Root cause:** the plugin sent the raw `{'h','s','v'}` dict as the DP
value. The device rejects it, `set_status()` returns `None`, and the
3-second socket timeout fires before the cloud fallback runs.

**Fix:** pack the dict into the hex layout the device expects
(`RR GG BB HHHH SS VV` for `colour_data`, `HHHH SSSS VVVV` for
`colour_data_v2`) before calling `set_status()`. Branch on the DP code,
not on the `s` value.

**Testing:** a colour change completes locally in <300 ms with no
`[LOCAL FAILED]` line.

### `'Device' object has no attribute 'set_colour'`

**Symptom:** `[LOCAL FAILED] ..., fallback to cloud: 'Device' object
has no attribute 'set_colour'`.

**Root cause:** `set_colour()` only exists on `tinytuya.BulbDevice`.
The plugin instantiates `tinytuya.Device` for all non-cover devices.

**Fix:** guard with `hasattr(d, 'set_colour')` and fall back to a
hand-built hex payload. Never assume the method exists.

### Pulsar fast path value revert (fixed in 3.2.5)

**Symptom:** A Pulsar fast path writes a fresh value to Domoticz, but the next
regular poll overwrites it with the old value a few seconds later. The log shows
two update lines for the same unit in quick succession:
`[pulsar] Update device: ... sValue:X` followed by `[poll] Update device: ... sValue:Y`.

**Root cause:** The fast path wrote to Domoticz but did not update `result[dev_id]`.
When the next regular poll ran, `CloudFallback()` returned the held (stale)
value from `result[dev_id]` (because the cloud poll was rate-limited), and the
status-update loop wrote that stale value back to Domoticz.

**Fix:** `_merge_pulsar_into_result()` is called at the top of
`_pulsar_on_message()` to write the pushed DP values into `result[dev_id]` before
any fast path runs. This keeps the held value in sync with the fresh value, so
the subsequent `CloudFallback()` returns the new value instead of the old one.

**Testing:** After the fix, a Pulsar push should not cause a revert on the next
poll cycle, and the log should show exactly one `[pulsar] Update device:` line per
push, not followed by a `[poll] Update device:` line with an older value.

### Netwerkfouten 901/904/905 vervuilen de log (opgelost in 3.2.8)

**Symptoom:** de log toont herhaaldelijk `Error: ... (TinyTuya error
901/904/905)`-regels voor apparaten die helemaal niet kapot zijn —
bijvoorbeeld een buitenlamp die via een tijdschema uit staat, of een
apparaat dat even in WiFi-slaapstand gaat. Issue #200.

**Oorzaak:** `_log_local_error()` logde elke fout op `Error`-niveau,
ook als de fout optrad tijdens een bericht dat het apparaat zelf
stuurde (`pushed by device`), tijdens een heartbeat-antwoord, of
tijdens een eenmalige query met terugval op de cloud. Dat zijn
verwachte hikjes die zichzelf oplossen bij de volgende reconnect.
De "is not recovering"-detectie was hier al voor bedoeld, maar de
ruis op Error-niveau maakte de log onbruikbaar.

**Oplossing:** nieuwe constante `_QUIET_ERROR_SOURCES` met daarin
de bronnen waarvoor een netwerkfout als verwacht geldt. Fouten uit
die bronnen worden op `Debug`-niveau gelogd. De "is not recovering"-
detectie blijft werken: `_local_note_failure()` wordt nog steeds
voor élke fout aangeroepen, dus een apparaat dat blijft falen zonder
één geslaagd antwoord krijgt nog steeds één `Error`-waarschuwing per
uur, met een duidelijke oorzaak.

**Niet veranderd:** de socket-levensduur. De `LocalListener` blijft
bij een 904 tijdens een push de verbinding openhouden, en bij andere
fouten de socket sluiten voor een reconnect — precies zoals vóór de
fix. Alleen het log-niveau verandert.

**Testen:** met Mode6 op `None` mogen er bij een apparaat dat even
onbereikbaar is geen `901/904/905`-regels meer op `Error`-niveau
verschijnen. Met Mode6 op `Basic Debugging` of hoger verschijnen ze
weer, met dezelfde uitleg en hint als voorheen.

**PR:** [issue #200](https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/issues/200).

### Refresh-knop markeert alle andere apparaten als orphaned (opgelost in 3.2.9)

**Symptoom:** Het indrukken van de Refresh-knop (Unit 200) op een
apparaat resulteert in een `TypeError` in de log. In eerdere versies
(zonder de TypeError) verdwenen alle *andere* apparaten plotseling
van het dashboard en stopten met reageren.

**Oorzaak:**
1. `RefreshDevice()` riep `onHandleThread(False)` aan, maar de
   signatuur is `onHandleThread(startup, local, target_dev_id=None)`.
   De parameter `local` ontbrak, wat resulteerde in een `TypeError`.
2. Om alleen dat ene apparaat te pollen, verving `RefreshDevice()`
   tijdelijk de globale `devs`-lijst. Echter, sinds 3.2.4 eindigt
   `onHandleThread()` met een orphan scan die `devs` vergelijkt met
   de Domoticz-database. Omdat `devs` tijdelijk maar één apparaat
   bevatte, werden alle andere apparaten als "orphaned" bestempeld
   en op `Used=0` gezet.

**Oplossing (PR #230):**
- `RefreshDevice()` gebruikt nu `target_dev_id`, exact zoals de
  Pulsar fast path doet. De globale `devs`-lijst blijft intact,
  dus de orphan scan is veilig.
- De functie neemt nu de `_handle_lock` (met 10s timeout). Als er
  al een poll loopt, wordt de refresh netjes overgeslagen.
- `last_update` wordt niet meer overschreven tijdens de refresh.

**Testing:** Zorg voor meerdere apparaten met een Refresh-knop.
Druk op Refresh bij één apparaat. Alleen dat apparaat mag een
`[refresh] Update device:` regel loggen. De andere apparaten
blijven `Used=1` en de `last_update`-klok blijft ongewijzigd.

**PR:** [#230](https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/pull/230).

## Build and Verification

### Syntax Check

    python3 -m py_compile plugin.py

The new log line to grep for when testing orphaned device handling is
`event="device removed"`.

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

    <plugin key="tinytuya" name="TinyTUYA" author="Xenomes" version="3.2.7" ...>
        ...
        <h2>TinyTuya Plugin - Hybrid Local / Cloud Control version 3.2.7</h2><br/>

`Parameters['Version']` is populated by Domoticz from the header, so no
other file needs changing.

**3.2.9 is the current working version.** It fixes the Refresh button
(Unit 200) which was broken since 3.0.1 and could mark other devices
as orphaned. It also includes the transient LAN error quiet-mode from
3.2.8 and the camera support from 3.2.7.

Changes since 3.2.8:

- `RefreshDevice()` no longer replaces the global `devs` list. It uses
  `onHandleThread(False, False, target_dev_id=DeviceID)` instead,
  which is the same targeted path Pulsar pushes use. This fixes a
  critical bug where the orphan scan at the end of `onHandleThread()`
  would mark every *other* device as orphaned (`Used=0`) when the
  Refresh button was pressed.
- `RefreshDevice()` now acquires `_handle_lock` (10 s timeout) before
  calling `onHandleThread()`, just like the heartbeat poll and Pulsar
  handler. Without it, a background poll could overwrite `last_update`
  while the refresh was running, corrupting the regular poll clock.
- Fixes a `TypeError: onHandleThread() missing 1 required positional
  argument: 'local'` that had made the Refresh button a no-op.
- Fixes issue #200: false-positive error lines from devices that are
  briefly asleep, off, or sending a packet TinyTuya cannot decode.

Both version strings in the header must be bumped to 3.2.9 together.

**3.2.8 is the current working version.** It quiets transient LAN
errors (901/904/905) from push and heartbeat sources, on top of the
camera support from 3.2.7.

Changes since 3.2.7:

- New constant `_QUIET_ERROR_SOURCES` listing `'pushed by device'`,
  `'heartbeat reply'`, `'status reply, single query'` and
  `'status reply to wake-up ping'` as expected-transient sources.
- `_log_local_error()` logs errors from those sources at `Debug`
  level instead of `Error`. The failure is still registered via
  `_local_note_failure()`, so the "is not recovering" detection is
  unchanged.
- Real errors (`'status reply on connect'`,
  `'periodic status reply'`) still go to `Error` with the existing
  `_LOCAL_ERROR_REPEAT` (1 h) throttle.
- Fixes issue #200: false-positive error lines from devices that are
  briefly asleep, off, or sending a packet TinyTuya cannot decode.

Both version strings in the header must be bumped to 3.2.8 together.

**3.2.7 is the current working version.** It adds Tuya security camera
support (`cdsxj`), on top of the colour-temperature and RGB fixes from
PR #229 (3.2.6).

Changes since 3.2.6:

- New device type `camera` for Tuya security cameras (category
  `cdsxj`). 21 units: 20 settings/controls plus a real Motion Sensor
  on Unit 21.
- New helpers `_camera_motion_check()` and `_camera_trigger_motion()`:
  treat any change of the Raw DP `movement_detect_pic` as a motion
  event, deduplicate between the Pulsar fast path and the poll loop
  via a config entry `{dev_id}:motion` / `last_pic`, and pulse Unit 21
  to "On" with an automatic reset after
  `CAMERA_MOTION_RESET_SECONDS` (15 s) using a generation counter.
- New Pulsar fast path for `dev_type == 'camera'` that only handles
  the motion event; every other camera DP goes through the verified
  slow path.
- `_log_realtime_capable_devices()` extended to list cameras in the
  startup realtime overview.

Both version strings in the header must be bumped to 3.2.7 together.

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
| `camera` | Changes to the security camera device type (`cdsxj`) or motion event handling |
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
- White colour temperature not applied: `bug` + `color`
- New camera device type or motion event: `enhancement` + `device-support` + `camera`
- Camera motion not firing: `bug` + `camera`

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
- **Camera units reuse the doorbell's numbering** wherever the DP
  overlaps (`floodlight_switch` → 2, `motion_switch` → 3,
  `decibel_switch` → 5, `basic_private` → 6, `siren_switch` → 9,
  `nightvision_mode` → 10, `ipc_siren_volume` → 12,
  `ipc_siren_duration` → 13). This is a hard rule: changing these
  numbers would break existing user automation. Camera-only DPs fill
  units 1, 4, 7, 8, 11, and 14–21.

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
- **Camera** — the boolean switch group in the status-update loop via
  a tuple of `(unit, code)` pairs, and the `camera_toggles` dict in
  `onCommand`

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
  thread so a slow device cannot block the Domoticz main loop.
- For a series of identical on/off units on the same device, use the
  same tuple-driven approach as in device creation (see SmartLock and
  Thermor examples).

### Camera motion event
- `_camera_motion_check(dev_id, current_value, source)` is the **only**
  entry point for camera motion. It must be called from the Pulsar fast
  path and from the poll loop's camera block. It stores
  `{dev_id}:motion` / `last_pic` and triggers `_camera_trigger_motion()`
  only when the value actually changed.
- `_camera_trigger_motion(dev_id, unit=CAMERA_MOTION_UNIT, source)` must
  use `checkDevice(dev_id, unit)` before updating, and must use a
  per-device generation counter in `_camera_motion_gen` so a newer
  motion cancels a pending reset.
- Never write a motion event directly with `UpdateDomoticz()` without
  going through `_camera_trigger_motion()`. The reset scheduling is the
  whole point.
- Constants: `CAMERA_MOTION_RESET_SECONDS = 15`,
  `CAMERA_MOTION_UNIT = 21`. Do not hardcode these values at the call
  sites.
- The motion sensor unit (21) is read-only from the user's point of
  view; do not add `onCommand` handling for it.

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

### Orphaned devices
- `orphaned_devices` is a module-level set that stores device IDs that
  exist in Domoticz but are no longer reported by Tuya.
- `_mark_orphaned_device_inactive(dev_id, dev_name)` marks every unit
  of a device as Unused (Used=0) in Domoticz. It must use
  `unit.Update(Log=False, UpdateProperties=True)` — without
  `UpdateProperties=True` the `Used` flag is not persisted to the
  database and the units stay active.
- The orphaned scan runs **once per startup**, **after** the
  `for dev in devs:` loop, not inside it. Placing it inside the loop
  makes it run once per device per heartbeat, which spams the log and
  re-processes already-handled devices.
- The scan must include an `if existing_id in orphaned_devices: continue`
  guard so a device that is already in the set is not re-processed.
- Every new update path must check `dev_id in orphaned_devices` and skip
  the device early. Current guard points: main polling loop, Pulsar
  handler, Pulsar realtime overview, IP scan result logger,
  `RefreshDevice()`, and `onCommand()`.
- The set is filled once during startup (after the device loop) and
  cleared in `onStop()`.
- See *Orphaned devices* for the full description and the log line format.

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
- Every new update path (LAN listener, cloud poll, Pulsar fast path,
  testdata, manual refresh) must check `dev_id in orphaned_devices` and
  skip the device early. See *Orphaned devices* for the full guard point
  list.
- `_log_realtime_capable_devices()` must be extended whenever a new
  device type gains a fast path, so the startup log lists it in the
  realtime overview.
- The camera fast path only handles `movement_detect_pic` and returns
  immediately afterwards. Every other camera DP must go through the
  slow path; do not extend the camera fast path without a per-DP
  justification (a fixed mapping AND an idempotent value conversion).

### Camera motion event helpers
- `_camera_motion_check(dev_id, current_value, source)` — deduplicates
  motion events via the `{dev_id}:motion` / `last_pic` config entry.
  Called from both the Pulsar fast path and the poll loop; the first
  channel to see a new value triggers, the other does nothing.
- `_camera_trigger_motion(dev_id, unit=CAMERA_MOTION_UNIT, source='poll')`
  — pulses Unit 21 to "On", schedules a reset via a daemon thread, and
  uses `_camera_motion_gen[dev_id]` to cancel a pending reset when a
  newer motion arrives.
- Constants: `CAMERA_MOTION_RESET_SECONDS = 15`, `CAMERA_MOTION_UNIT = 21`.
- **Do not** use Domoticz' Off Delay on Unit 21. The plugin resets the
  sensor itself; an Off Delay races the plugin's timer.

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

## Tuya colour round-trip (v1, v2, cloud)

Tuya colour handling is asymmetric: the same DP code arrives in three
different shapes depending on where it came from, and the device expects
yet another shape on the way back. Getting this wrong produces the
symptoms users report most often: colours that don't follow the app,
colours that are too dark, colour tiles that stay yellow, sliders stuck
at 100%, or a 3-second delay per colour change.

### The three read shapes

`colour_data` and `colour_data_v2` are the same logical DP but arrive as:

| Source | Example | Layout |
|---|---|---|
| Cloud (getstatus) | `'{"h":114.0,"s":238.0,"v":107.1}'` | JSON string, s/v = 0..1000 for v2, 0..255 for v1 |
| Pulsar push | same as cloud | JSON string |
| LAN listener (v1 device) | `'116b070072ee6b'` | 7 bytes: `RR GG BB HHHH SS VV` |
| LAN listener (v2 device) | `'000003e8000a'` | 6 bytes: `HHHH SSSS VVVV` |

All three must be handled by `decode_colour_data()`:

- JSON string → recurse after `json.loads`
- 7-byte hex → h = bytes 3-4, s = byte 5, v = byte 6 (**not** RGB; the
  first 3 bytes are the *dimmed* RGB, only useful as a fallback)
- 6-byte hex → h = bytes 0-1, s = bytes 2-3, v = bytes 4-5

**Do not** treat the first 3 bytes of a 7-byte frame as the live colour.
The device is dimming them by `v`, so a lamp at 12% shows `0c0cb0...`
for the same hue that reads `ff66cc...` at full brightness. Doing this
produces the "tile is too dark" symptom.

### `_hsv_to_domoticz()` must not bake `v` into RGB

Domoticz has a separate brightness slider for a Color Switch. The colour
dict must therefore carry the colour at *full* brightness; the slider
shows the dimming. Use only `s` to decide the scale:

```python
def _hsv_to_domoticz(h, s, v):
    if h is None or s is None or v is None:
        return None
    h, s = int(h), int(s)
    if s > 255:
        r, g, b = hsv_to_rgb_v2(h, s, 1000)   # full v2 brightness
    else:
        r, g, b = hsv_to_rgb(h, s, 255)       # full v1 brightness
    return {'m': 3, 'r': r, 'g': g, 'b': b, 't': 0, 'cw': 0, 'ww': 0}
```

`v` stays in the signature because `decode_colour_data` passes it, but
it is no longer used. Any call site that used `v` to scale RGB must be
fixed separately (see `colour_data_brightness_pct`).

### `colour_data_brightness_pct()` is the single source for the slider

The brightness shown by the slider in **colour mode** is `v` from
`colour_data`, *not* `bright_value`. In **white mode** it is
`bright_value`. The poll loop must therefore branch on `work_mode`:

```python
work_mode = StatusDeviceTuya('work_mode') if searchCode('work_mode', StatusProperties) else 'white'

if work_mode == 'colour':
    raw_cd = StatusDeviceTuya('colour_data')
    if raw_cd is None:
        raw_cd = StatusDeviceTuya('colour_data_v2')
    color_dict = decode_colour_data(raw_cd)
    dimtuya = colour_data_brightness_pct(raw_cd) or 100
elif work_mode == 'white':
    # m:2 — reconstruct from temp_value, invert the scale
    temp = StatusDeviceTuya('temp_value')
    temp_is_v2 = False
    if temp is None:
        temp = StatusDeviceTuya('temp_value_v2')
        temp_is_v2 = True
    if temp is not None:
        raw_temp = int(temp)
        raw_max = 1000 if temp_is_v2 == True else 255   # from the DP code, not the value
        t = round((raw_max - raw_temp) * 255 / raw_max)  # 255=warm
        t = min(255, max(0, t))
        color_dict = {'m': 2, 'r': 0, 'g': 0, 'b': 0, 't': t, 'cw': 0, 'ww': 0}
    # brightness from bright_value
    ...
```

**Do not use `or` for the `raw_cd` lookup.** `StatusDeviceTuya(a) or
StatusDeviceTuya(b)` calls the second even when the first returned an
empty-but-valid value, and worse: it registers the unused DP in
`local_used` via the second call's side effect. Use an explicit `if
raw_cd is None:`.

**Do not guess the temperature scale from the value.** The heuristic
`raw_max = 1000 if raw_temp > 255 else 255` fails when a v2 bulb happens
to start below 255 (issue #226, fixed in 3.2.6). The DP code already
tells you which scale applies — track it with a `temp_is_v2` flag while
reading.

`colour_data_brightness_pct(raw)` must accept all three shapes (dict,
JSON string, 7-byte hex, 6-byte hex) and return a percentage 0..100, or
`None` when the value cannot be interpreted. Callers must fall back to
`100` when it returns `None`.

### Temperature inversion

Domoticz and Tuya use opposite scales:

| | Domoticz `t` | Tuya `temp_value` |
|---|---|---|
| Warm (yellow) | 255 | 0 |
| Cold (blue) | 0 | 255 |

- **On write**, `SendCommandTuya()` calls `temp_value_scale()` to invert.
  The function converts **from** the Domoticz 0–255 scale **to** the
  device's raw value:

  ```python
  return round(max_value + (min_value - max_value) * (scaled / 255))
  ```

  The parameter is named `scaled` (not `raw`) to make the direction
  unambiguous. A previous version converted the wrong way, which is why
  white-temperature changes were silently ignored on some bulbs (issue
  #226, fixed in 3.2.6).
- **On read**, the poll loop must invert manually (see the `raw_max`
  snippet above). **Do not guess the scale from the value** — track
  which DP the value came from with a `temp_is_v2` flag. Forgetting the
  inversion entirely produces a colour-temperature tile that jumps to
  the opposite end on every poll.

### Write side: pack the hex, do not send the dict

The device firmware expects a packed hex string on DP 5. Sending the
raw `{'h':..,'s':..,'v':..}` dict makes TinyTuya's `set_status()`
return `None`, which triggers the 3-second socket timeout and a cloud
fallback. See `SendCommandTuya()` in `_do_send()`:

```python
if actual_function_name in ('colour_data', 'colour_data_v2') and isinstance(actual_status, dict) and 'h' in actual_status:
    h, s, v = int(actual_status['h']), int(actual_status['s']), int(actual_status['v'])
    if hasattr(d, 'set_colour'):
        d.set_colour(r, g, b)               # Tuya's helper builds the format
    else:
        if actual_function_name == 'colour_data':
            # v1: 7 bytes RR GG BB HHHH SS VV
            hex_colour = f"{r:02x}{g:02x}{b:02x}{h16:04x}{s8:02x}{v8:02x}"
        else:
            # v2: 6 bytes HHHH SSSS VVVV
            hex_colour = f"{h16:04x}{s16:04x}{v16:04x}"
        d.set_status(hex_colour, int(dp_id))
```

The `hasattr(d, 'set_colour')` fallback matters: `tinytuya.Device` does
not have `set_colour`, only `BulbDevice` does. The plugin instantiates
`tinytuya.Device` for everything that is not a cover, so the manual hex
path is what actually runs. **Do not assume `set_colour` exists.**

Also important: `v1` and `v2` have **different byte layouts**. Emitting
the v1 layout for a v2 device (or vice versa) produces a colour that
the device silently ignores. Always branch on the DP code, never on
`s > 255`.

### `colour_code` selection

When sending a colour, pick the DP code that actually exists on the
device:

```python
colour_code = 'colour_data_v2' if searchCode('colour_data_v2', function) else 'colour_data'
SendCommandTuya(DeviceID, colour_code, hvs)
```

The prefix matcher in `SendCommandTuya()` will **not** map
`'colour_data'` to `'colour_data_v2'` (they share a prefix, not a
suffix). A Calex GU10 with only `colour_data_v2` would otherwise fail
with `No dp_id for code colour_data` on every colour change.

Do **not** reuse the existing `colour_data_v2` variable from the scale
detection block: that variable means "v is 0..1000" and can be `True`
for devices that have only `colour_data`. Use a fresh name
(`colour_code`) for the DP selection.

### `UpdateDomoticz()` for a Color Switch

A Domoticz Color Switch (Type 241) stores colour and brightness
separately:

- `unit.Color` → the JSON dict
- `unit.sValue` → the brightness number

`UpdateDomoticz()` must therefore never write the colour JSON to
`sValue`. The current implementation detects the colour dict (in both
string and dict form) and takes an early-return path that only touches
`unit.Color`:

```python
if is_color:
    if str(unit.Color) == str(sValue) and not AlwaysUpdate:
        return
    unit.Color = str(sValue)
    unit.nValue = nValue
    Devices[ID].TimedOut = TimedOut
    unit.Update(UpdateProperties=True, Log=True)
    return

# non-colour path below
```

The early `return` is essential. Without it the code falls through and
writes the JSON into `sValue`, freezing the slider at a non-numeric
value.

The `UpdateProperties=True` is **required** for the colour to be written
to the Domoticz database. Without it the colour is only held in memory
and is lost on restart (fixed in 3.2.6, follow-up to PR #229). This
matches the same flag used by `_mark_orphaned_device_inactive()`.

### Order of writes in the poll loop

In the `light` / `fanlight` block, always write brightness **first**,
then colour:

```python
svalue = str(dimtuya) if currentstatus else '0'
if str(unit.sValue) != svalue or unit.nValue != nval:
    UpdateDomoticz(dev_id, 1, svalue, nval, 0)

if color_dict is not None:
    color_str = json.dumps(color_dict)
    if str(unit.Color) != color_str:
        UpdateDomoticz(dev_id, 1, color_str, nval, 0)
```

**Do not duplicate this block.** During development it is easy to end
up with two identical writes; that produces the doubled `[poll] Update
device:` lines users see in the log and wastes a call per poll. Grep
for `Write brightness first` — that comment should appear exactly once.

### Colour helpers summary

- `colour_data_brightness_pct(raw)` — percentage 0..100 derived from
  the `v` field of a `colour_data` value, in all three shapes (dict,
  JSON string, 7-byte hex, 6-byte hex). Returns `None` when the value
  cannot be interpreted. Used by the poll loop to drive the brightness
  slider in colour mode.
- `_hsv_to_domoticz(h, s, v)` — internal helper used by
  `decode_colour_data()`. Chooses the v1/v2 scale from `s` and returns
  a Domoticz colour dict at full brightness. `v` is accepted for
  signature compatibility but not used.
- `temp_value_scale(device_functions, name, scaled)` (write) / manual
  inversion with `temp_is_v2` (read) — Domoticz `t` ↔ Tuya
  `temp_value`. The parameter is named `scaled` because the function
  converts **from** the Domoticz 0–255 scale **to** the raw value.
- `colour_code = 'colour_data_v2' if searchCode(...) else 'colour_data'`
  — DP selection for writes.

### Testing the colour round-trip

Minimum checks after any colour change:

1. App sets a colour → tile shows the **same** hue, at full brightness,
   slider at the value from `colour_data.v`.
2. App sets white mode → tile switches to `m:2`, `t` matches the app's
   temperature direction (warm stays warm).
3. App sets a colour at low brightness → tile keeps the full-brightness
   colour, slider drops.
4. Send a colour from Domoticz → device receives it in <300 ms, no
   `[LOCAL FAILED]`, no `[CLOUD] Command sent to Tuya` fallback.
5. Move the white-temperature slider end to end on a v2 bulb → the
   physical bulb must change temperature and the log must not show
   `raw_max = 255`.
6. Restart Domoticz → the colour and temperature survive (the
   `UpdateProperties=True` fix from 3.2.6).
7. Log shows **one** `[poll] Update device:` for colour and **one** for
   brightness per cycle, not two of each.

## Known Issues and Solutions

### Pulsar fast path value overwritten by a second update (issue #225)

**Symptom:** A battery-powered T+H sensor (`wsdcg`, category `wsdcg`,
`product_name = 'T & H Sensor'`) does not update in Domoticz at all. The log
shows the Pulsar fast path firing correctly, but no `[event=update]` line
follows the `fast path BEFORE` line:

    [event=pulsar] Pulsar: fast path BEFORE for Véranda (...) unit 1:
        mem='20.6', new=20.2, TimedOut=0
    [event=pulsar] Pulsar: fast path applied for Véranda (...) (temperature) -> 20.2

The tile stays on the old value. When `UpdateDomoticz()` *is* reached (e.g.
after a manual refresh or a cloud poll), the log shows two updates within
the same second, the second one with the **older** value:

    [event=update] Update device: Véranda (Temperature) Unit:1 sValue:16.3
    ...
    [event=update] Update device: Véranda (Temperature) Unit:1 sValue:16.0

**Root cause:** `UpdateDomoticz()` updated the in-memory `unit.sValue` and
`unit.nValue` and called `unit.Update(Log=True)`, but the `[event=update]`
log line was placed **after** `unit.Update()`. In a race with the heartbeat
poll, the poll path read the still-old value from `Devices[...]` before the
Pulsar write reached the database, and the poll's own `Update()` then wrote
the stale value on top of the fresh one. The user-visible effect: the
sensor's tile never catches up with the Tuya app, even though the plugin
receives every push.

**Fix (three parts, all in the Pulsar fast path and `UpdateDomoticz`):**

1. **Extend the sensor fast path.** The `sensor` / `switch/sensor` block
   in `_pulsar_on_message()` only matched `pir` / `pir_state`. Add
   `va_temperature` / `temp_current` / `local_temp` / `Tin`,
   `va_humidity` / `humidity_value` / `humidity` / `local_hum` / `Hin`,
   and the `BATTERY_CODES` list, using the same scaling as the cloud
   poll (`/10.0` for temperature, integer for humidity, the
   `high/middle/low → 100/50/5` map for `battery_state`).
2. **Only ignore Pulsar when a LAN listener is actually connected.**
   The old check `if dev_id in localtuya` was too broad: a device that
   was scanned once (IP known) but has no persistent listener still got
   the "reachable locally" shortcut and its push was dropped. Gate on
   `local_listeners.get(dev_id) and local_listeners[dev_id].connected`
   instead.
3. **Write the update log line before `unit.Update()`.** This is what
   actually stopped the revert on #225: moving

       Log(event='update', message=f"Update device: {ID} {Name} ...")

   to just before `unit.Update(Log=True)` means the value is committed
   to the Domoticz database in the same call, so a racing poll cannot
   overwrite it with the stale held value.

**Testing:** After the fix, one Pulsar push produces exactly three log
lines in order:

    [event=pulsar] Pulsar: fast path BEFORE ... mem='20.6', new=20.2 ...
    [event=update] Update device: <id> <name> (Temperature) Unit:1
        sValue:20.2 ...
    [event=pulsar] Pulsar: fast path applied ... (temperature) -> 20.2

and no `[event=update]` line with the older value within the same minute.
On issue #225 the sensor stayed stable for 3 hours across 3 devices.

**Do not** try to fix this by calling `unit.Update()` twice or by adding
`AlwaysUpdate=1` to the fast path — the root cause is the ordering, not
the update itself.

**Related:** the 3.2.5 fix (`_merge_pulsar_into_result()`) keeps
`result[dev_id]` in sync so `CloudFallback()` does not return a stale
value. That was necessary but not sufficient; the #225 fix above closes
the remaining hole where the poll path still wrote its own held value
directly to the unit.

### Camera motion not firing (issue pending)

**Symptom:** `movement_detect_pic` changes in the Tuya app, but Unit 21
never pulses to "On". The log shows the `Pulsar message from ...` line
but no `event=motion` line follows it.

**Root cause candidates:**

1. **Wrong DP code name.** The DP code is `movement_detect_pic`, not
   `movement_detect_picture` or `motion_detect_pic`. Case-sensitive.
2. **Empty value on motion.** Some firmware reports `movement_detect_pic`
   as an empty string on motion and only fills it on a subsequent poll.
   In that case the plugin's `_camera_motion_check()` returns early
   because `current_value == ''` and no event fires. Check the raw
   value in the `Pulsar message from ...` INFO line.
3. **Config stale.** If the config entry `{dev_id}:motion` / `last_pic`
   already contains the current value (e.g. from a previous run), no
   event fires because nothing changed. Delete the entry or restart
   the plugin with the DP reset to empty.
4. **Unit 21 not created.** If `searchCode('movement_detect_pic',
   StatusProperties)` is False (the DP is only in `functions`, not
   `status`), the unit is not created and `_camera_trigger_motion()`
   silently exits at `checkDevice()`.

**Diagnostics:** grep the log for `event=motion`, `movement_detect_pic`
and `{dev_id}:motion`. The `Pulsar message from ...` line right before
the (missing) `event=motion` line shows the raw DP values.

**Do not** try to fix this by removing the `current_value == ''` early
return. An empty value is the normal "no motion recorded" state and
treating it as motion would pulse the sensor on every poll.

### Category Mismatches
- **Category 'qt':** Can be smoke detector OR curtain switch → use product_name detection
- **Category 'wnykq':** Smart IR devices with limited functionality → mark as unsupported
- **Category 'jsq':** Aromatherapy devices → treat as dedicated type
- **Category 'cz':** Smart socket; can also expose an RGB LED ring
- **Category 'kt':** Air conditioner; `temp_current` may be in half degrees
- **Category 'cdsxj':** Security camera (Tuya). 21-unit mapping; the
  Raw DP `movement_detect_pic` is used as a motion *event* — any change
  of the value means motion. No Domoticz camera widget is created (the
  plugin API has none; see *Security camera support (`cdsxj`)*).

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
- **White temperature scale is set by the DP code, not the value.**
  Track `temp_is_v2` while reading and derive `raw_max` from that flag.
  The old heuristic `1000 if raw_temp > 255 else 255` misfires on a v2
  bulb that starts below 255 (issue #226, fixed in 3.2.6).
- **Colour writes need `UpdateProperties=True`.** Without it the colour
  is only held in memory and is lost on restart (fixed in 3.2.6).

### Camera motion event
- The camera has no boolean motion DP. Only the Raw DP
  `movement_detect_pic` is a motion signal, and only via *change*.
- Both the Pulsar fast path and the poll loop observe the same change.
  Deduplicate via `{dev_id}:motion` / `last_pic` in the config; do
  not skip this or a single motion produces two events.
- Never treat an empty `movement_detect_pic` as motion. An empty value
  is the normal "no motion recorded" state.
- Do not add a Domoticz Off Delay on Unit 21. The plugin resets the
  sensor itself; an Off Delay races the plugin's timer.

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

### Orphaned device sub-units remain active in Domoticz
- Symptom: the plugin logs
  `[device=<id> ... event="device removed"] no longer reported by Tuya,
  marked inactive in Domoticz` on every heartbeat, but the units stay
  visible on the dashboard and are still `Used=1` in Setup → Devices.
- Cause 1: `_mark_orphaned_device_inactive()` used
  `unit.Update(Log=False)` without `UpdateProperties=True`. Setting
  `unit.Used = 0` alone does not persist the flag; only
  `UpdateProperties=True` writes it to the database.
- Cause 2: the orphaned scan was placed **inside** the `for dev in devs:`
  loop in `onHandleThread()`, so it ran once per device per heartbeat.
- Fix:
  - Use `unit.Update(Log=False, UpdateProperties=True)`.
  - Move the scan block **after** the `for dev in devs:` loop, still
    inside `if startup and not local:`.
  - Add the guard `if existing_id in orphaned_devices: continue`.
  - Log the list of unit numbers that were actually marked, so the
    user can verify that all sub-units were handled:
    `... marked inactive in Domoticz (units: 1, 2, 3)`.
- Verify in the database:

  ```
  SELECT Unit, Name, Used FROM DeviceStatus
   WHERE DeviceID='<orphaned-id>';
  ```

  All rows must have `Used=0` after the fix. If a tile is still visible
  with `Used=0` in the database, check the `Favorite` column — a
  favourited device stays on the dashboard regardless of `Used`.
- Verify the log: the `event="device removed"` line must appear **once**
  at startup, not on every heartbeat.

## Branch Information

### Main Branches
- **Master:** Stable version with latest features

### Version Differences
- **3.x:** Hybrid local/cloud control with Pulsar realtime updates,
  cloud usage counters, extended structured logging, quiet-mode for
  transient LAN errors (901/904/905), wake-up of sleeping modules,
  LAN failure detection, expanded Pulsar fast paths (doorbell, smoke
  detector, water leak, smart lock, human presence, camera motion),
  colour-temperature/RGB fixes, and a safe Refresh button (PR #230).

## Recent Work

### Current (Version 3.2.9)

**Refresh-knop gerepareerd en beveiligd (PR #230)**

De Refresh-knop (Unit 200) werkte sinds 3.0.1 niet meer door een
`TypeError`. Bovendien kon de knop, als de TypeError er niet was,
alle andere apparaten per ongeluk als orphaned markeren.

- `RefreshDevice()` roept nu `onHandleThread(False, False, target_dev_id=DeviceID)`
  aan. Dit is hetzelfde gerichte update-pad dat de Pulsar-handler
  gebruikt, waardoor de globale `devs`-lijst niet meer tijdelijk
  vervangen hoeft te worden.
- De orphan scan aan het einde van `onHandleThread()` is nu veilig:
  alleen het opgevraagde apparaat wordt geüpdatet, de rest blijft
  onaangeroerd.
- `RefreshDevice()` neemt nu de `_handle_lock` (10 seconden timeout).
  Als de achtergrond-poll al bezig is, wordt de refresh geannuleerd
  met een duidelijke melding in de log, in plaats van te racen.
- De `last_update`-klok wordt netjes hersteld in een `finally`-blok,
  zodat de reguliere polling niet in de war raakt.

### Previous released (Version 3.2.8)

**Transient LAN errors worden stil gemaakt (issue #200)**

De plugin logt fouten 901/904/905 uit verwachte bronnen nu op
`Debug`-niveau in plaats van `Error`. Dit zijn hikjes die zichzelf
oplossen: het apparaat is even onbereikbaar (WiFi-slaapstand,
tijdschema), stuurt een pakket dat TinyTuya niet kan decoderen, of
antwoordt niet op een eenmalige query. De "is not recovering"-
detectie blijft ongewijzigd.

- Nieuwe constante `_QUIET_ERROR_SOURCES` met de bronnen
  `'pushed by device'`, `'heartbeat reply'`,
  `'status reply, single query'` en
  `'status reply to wake-up ping'`.
- `_log_local_error()` kijkt naar de bron; bij een match wordt
  `Debug()` gebruikt in plaats van `Error()`.
  `_local_note_failure()` wordt nog steeds voor élke fout
  aangeroepen, dus een apparaat dat blijft falen zonder succes
  krijgt nog steeds één `Error`-waarschuwing per uur via het
  `is not recovering`-alarm.
- Bronnen die niet in `_QUIET_ERROR_SOURCES` staan
  (`'status reply on connect'`, `'periodic status reply'`) worden
  nog steeds op `Error`-niveau gelogd met de bestaande
  `_LOCAL_ERROR_REPEAT`-throttle.
- Geen wijziging aan de socket-levensduur: de `LocalListener` blijft
  bij een 904 tijdens een push de verbinding openhouden, bij andere
  fouten sluit hij de socket voor een reconnect.

### Previous released (Version 3.2.7)

**Security camera support (`cdsxj`)**

New device type `camera` for Tuya security cameras. The Tuya category
is `cdsxj`, e.g. the "Security Camera" device with
`product_id = he4r8lisqbynliun`.

The camera exposes 21 units:

- **Units 1–20** — the settings and controls the Tuya app exposes:
  OSD, flip, motion-detect enable, floodlight, decibel detect, private
  mode, auto-siren, SD record, siren, night vision, humanoid filter,
  siren volume/duration, motion sensitivity, event linkage, record
  mode, siren sound, decibel sensitivity, anti-flicker, volume.
- **Unit 21 — Motion Sensor (Switchtype=8).** The camera has no
  boolean motion DP; it reports motion through the Raw DP
  `movement_detect_pic`, which is empty until something happens and
  then contains a unique base64 blob. The plugin treats **any change**
  of that DP as a motion event.

**Deduplication:** the last seen value is stored in the plugin config
under `{dev_id}:motion` / `last_pic`. Both the Pulsar fast path and the
regular cloud-poll loop call `_camera_motion_check()`, which only
triggers when the value differs from the stored one. A motion is never
published twice for the same event, regardless of which channel sees
it first.

**Auto-reset:** `_camera_trigger_motion()` pulses Unit 21 to On and
schedules a reset to Off after `CAMERA_MOTION_RESET_SECONDS` (15 s).
A per-device generation counter in `_camera_motion_gen` cancels a
pending reset when a newer motion arrives, so the sensor stays On for
the full window after the most recent motion.

**Pulsar fast path** only covers the motion event. Every other camera
DP goes through the verified slow path, so a fast-path value can never
disagree with the next regular poll.

**Unit numbering** keeps the doorbell's numbering wherever the DP
overlaps (`floodlight_switch` → 2, `motion_switch` → 3,
`decibel_switch` → 5, `basic_private` → 6, `siren_switch` → 9,
`nightvision_mode` → 10, `ipc_siren_volume` → 12,
`ipc_siren_duration` → 13). New camera-only DPs fill units 1, 4, 7, 8,
11, and 14–21. This preserves existing user automation that already
referenced those unit numbers on a doorbell.

**Not exposed:** `sd_status`, `sd_storge`, `initiative_message`,
`movement_detect_pic` (as a raw value), `motion_area`,
`ipc_res_change`, `device_restart`, `sd_format`, `onvif_*`,
`ipc_magnification`, `ipc_save_percent`. They are either internal
state, raw blobs, one-shot actions that should not have a persistent
Domoticz button, or configuration set once by the Tuya app.

**No Domoticz camera-widget integration:** the DomoticzEx Python plugin
API has no camera device type. Cameras are managed in a separate
Domoticz table (Setup → More Options → Camera), which a plugin cannot
write to. Users add the camera to that table manually using the
snapshot URL from the Tuya app or the camera's ONVIF endpoint.

### Previous released (Version 3.2.6)

**Colour temperature and RGB fixes (PR #229, issue #226)**

Three fixes from sieger82 that make the colour wheel and
white-temperature slider work on Calex and other `dj`-category bulbs:

- **`temp_value_scale()` direction fixed.** The function is only called
  from `SendCommandTuya()` and must convert from the Domoticz 0–255
  scale to the device's raw value. It was doing the conversion
  backwards, so the device received wrong values and ignored the
  temperature change. The parameter was renamed from `raw` to `scaled`
  to make the direction explicit.
- **`raw_max` no longer guessed from the value.** The poll loop's
  `work_mode == 'white'` branch used
  `raw_max = 1000 if raw_temp > 255 else 255`, which misidentifies a v2
  device if its temperature happens to start below 255. It now tracks
  whether the value came from `temp_value` or `temp_value_v2` with a
  `temp_is_v2` flag and derives `raw_max` from the DP code.
- **`UpdateProperties=True` added to the colour-update path** in
  `UpdateDomoticz()`. Without it the colour was only held in memory and
  was not persisted to the Domoticz database.

**File added:** `.gitignore` with `tuya-raw.json`, `snapshot.json`,
`__pycache__`, `tools/dump.json`, `tools/creds.json`.

### Previous released (Version 3.2.4)

**Orphaned device sub-units fixed**

Devices that exist in Domoticz but are no longer reported by Tuya are
now correctly marked inactive at **every** unit, in a single pass at
startup. Two defects in the 3.2.3 implementation kept sub-units of a
removed Tuya device visible in Domoticz:

- `_mark_orphaned_device_inactive()` used `unit.Update(Log=False)`,
  which does not persist the `Used` flag. Changed to
  `unit.Update(Log=False, UpdateProperties=True)`. This is the flag
  that writes `Used` (and other unit attributes) to the database;
  available from Domoticz 2024.4.16100.
- The orphaned scan ran inside the `for dev in devs:` loop, so it
  executed once per device per heartbeat. Moved it after the loop and
  added an `if existing_id in orphaned_devices: continue` guard, so it
  runs once per startup.
- The helper now logs the list of unit numbers it actually marked
  (`units: 1, 2, 3`), so a partially-inactive device is visible in the
  log instead of silently staying half-processed.

Verified on Domoticz 2026.4 build 18474: the three units of the
orphaned `vdevo179157410360265` device were marked inactive with a
single log line at startup, and the dashboard tile disappeared.

### Latest released (Version 3.2.3)

**Orphaned device detection added**

Devices that exist in Domoticz for this hardware instance but are no
longer reported by Tuya (removed from the app, re-paired with a new ID,
or factory reset) are detected at startup and marked inactive:

- `_mark_orphaned_device_inactive(dev_id, dev_name)` sets `Used = 0` on
  every unit of the device.
- `orphaned_devices` is a module-level set filled once during startup
  and cleared in `onStop()`. Every update path checks it and skips the
  device early: the main polling loop, the Pulsar handler, the Pulsar
  realtime overview, the IP scan result logger, `RefreshDevice()` and
  `onCommand()`.
- One clear log line per orphaned device at startup, tagged
  `event="device removed"`.

This release had two defects that were fixed in 3.2.4:

- `_mark_orphaned_device_inactive()` used `unit.Update(Log=False)`
  without `UpdateProperties=True`, so the `Used` flag was not written
  to the database and the units stayed active.
- The orphaned scan ran inside the `for dev in devs:` loop, so it
  executed once per device per heartbeat instead of once per startup.

See *Orphaned devices* and *Known Issues* for the full description of
the fix.

### Latest released (Version 3.2.2)

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
- `_log_local_error(dev_id, source, reply)` — if the reply contains
  `Err`/`Error`: a clear ERROR line with the translated meaning from
  `_LOCAL_ERRORS` (901/902/904/905/914) and a hint. Sources listed in
  `_QUIET_ERROR_SOURCES` are logged at **Debug** level instead of
  Error — a transient hik does not belong in the normal log. For the
  other sources, repeats within `_LOCAL_ERROR_REPEAT = 3600` seconds
  go to Debug. Uses the structured `Error()` and `Debug()` helpers.
- `_QUIET_ERROR_SOURCES` — tuple of sources for which a network error
  is expected to resolve on its own: `'pushed by device'`,
  `'heartbeat reply'`, `'status reply, single query'` and
  `'status reply to wake-up ping'`. Errors from these sources are
  still registered for the "is not recovering" detection via
  `_local_note_failure()`, but only appear in the log when Mode6
  debugging is enabled. Real errors (`'status reply on connect'`,
  `'periodic status reply'`) still go to Error level with the
  existing `_LOCAL_ERROR_REPEAT` throttle.
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

### Pulsar fast path testing
1. Trigger a state change on a fast-path device (door contact, motion sensor,
   doorbell, smoke detector, water leak sensor, smart lock, or human presence)
   from the Tuya app or physically.
2. Confirm the log shows a `[pulsar] Update device:` line with the new value.
3. Wait for the next regular poll cycle (cloud or LAN, whichever applies).
4. Confirm the log does **not** show a `[poll] Update device:` line with the
   old value — the value should stay at the fresh value from the push.
5. If a revert does appear, check the Known Issues section for the
   `_merge_pulsar_into_result()` fix.

### Camera motion testing
1. Confirm the camera creates 21 units, with Unit 21 labelled
   `(Motion)` and shaped as a Motion Sensor (Switchtype=8).
2. Wave in front of the camera.
3. Within a second or two, Unit 21 must show "Motion" on the
   dashboard, and the log must show `event=motion` with
   `motion detected via pulsar`.
4. Wait 15 s — the unit must go back to "No motion" automatically
   (log: `source=motion-reset`).
5. Trigger two motions within the 15 s window — the sensor must stay
   On until 15 s after the **second** motion, not reset early.
6. Delete the `{dev_id}:motion` config entry or restart the plugin,
   then poll once: the poll fallback (`source=poll`) must trigger the
   same event if Pulsar is not running.
7. Confirm that the same motion is never published twice (no two
   `event=motion` lines within one second of each other).
8. Confirm no Off Delay is set on Unit 21 in the Domoticz UI. If there
   is one, clear it — the plugin resets the sensor itself.

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
5. **Move the white-temperature slider from one end to the other**
   - The physical bulb must change temperature (warm ↔ cold)
   - On a v2 device the log must not show `raw_max = 255`
   - Restart Domoticz and confirm the colour and temperature survive
     (they are persisted via `UpdateProperties=True`)
   - Issue #226 was exactly this failing silently

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
presence sensor, camera motion):

1. Trigger a status change on the physical device (open a door,
   press the doorbell, spill water on the leak sensor, wave in front
   of the camera, ...).
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
7. On a camera, wave once: Unit 21 must pulse and auto-reset. Wave
   again during the reset window: the reset must be delayed.

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
- `event="device removed"` met `(units: N, N, N)` — de orphaned-scan
  markeerde deze unitnummers als inactief. Als de regel op **elke**
  heartbeat terugkomt in plaats van één keer bij startup, staat de
  scan nog binnen de `for dev in devs:` loop.
- `event="device removed"` zonder `(units: ...)` erachter — oude
  plugin-versie (vóór de 3.2.3-correctie) die de unit-lijst nog niet
  logde. Werk bij naar de huidige `plugin.py`.
- `raw_max = 255` in a `work_mode = 'white'` log for a v2 bulb — **bug**
  in the temperature read path: `raw_max` is being guessed from the
  value instead of derived from the `temp_is_v2` flag (issue #226,
  fixed in 3.2.6).
- `Error: ... (TinyTuya error 901/904/905)` — verschijnt alleen nog
  voor de bronnen `status reply on connect` en `periodic status
  reply`, of als het `is not recovering`-alarm afgaat. Kom je deze
  fouten tegen tijdens een push of een heartbeat, dan is Mode6-debug
  aan — zet die uit om de ruis te laten verdwijnen (vanaf 3.2.8).
- `Refresh: poll busy, device ... not refreshed` — de Refresh-knop
  werd ingedrukt terwijl er al een achtergrond-poll liep. Dit is een
  veiligheidsmaatregel (vanaf 3.2.9) om te voorkomen dat de
  `last_update`-klok in de war raakt. Probeer het over een paar
  seconden opnieuw.
- `[device=X unit=21 ... event=motion] motion detected via pulsar` —
  camera motion event fired from the Pulsar fast path. A matching
  `[motion-reset]` line appears 15 s later unless a newer motion
  arrived first, in which case the reset is silently cancelled and the
  sensor stays On.
- `[device=X unit=21 ... event=motion] motion detected via poll` —
  camera motion event fired from the poll fallback (Pulsar not
  available or the config entry was stale). Same auto-reset behaviour.
- No `event=motion` line even though the Tuya app shows motion — check
  the preceding `Pulsar message from ...` line for the raw
  `movement_detect_pic` value. If it is an empty string, the plugin
  correctly ignores it; if it is a non-empty string that matches the
  stored `{dev_id}:motion` / `last_pic`, the entry is stale — clear it
  or restart the plugin.

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
- **.gitignore:** Ignores `tuya-raw.json`, `snapshot.json`, `__pycache__`,
  `tools/dump.json`, `tools/creds.json`
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

### Camera motion
- `_camera_motion_check(dev_id, current_value, source)` - deduplicates
  motion events via the `{dev_id}:motion` / `last_pic` config entry.
  Called from the Pulsar fast path and the poll loop.
- `_camera_trigger_motion(dev_id, unit=CAMERA_MOTION_UNIT, source='poll')`
  - pulses Unit 21 to "On", schedules a reset after
  `CAMERA_MOTION_RESET_SECONDS` (15 s), and cancels a pending reset
  when a newer motion arrives (via `_camera_motion_gen[dev_id]`).
- Constants: `CAMERA_MOTION_RESET_SECONDS = 15`, `CAMERA_MOTION_UNIT = 21`.

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
- `temp_value_scale(device_functions, actual_function_name, scaled)` -
  convert **from** the Domoticz 0–255 scale **to** the device raw value
  (direction is fixed in 3.2.6). The parameter is named `scaled` to
  make the direction explicit.
- `colour_data_brightness_pct(raw)` - percentage 0..100 from the `v`
  field of a `colour_data` value, in all shapes (dict, JSON string,
  7-byte hex, 6-byte hex). Returns `None` when the value cannot be
  interpreted.
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

### Log vol met 901/904/905 errors voor apparaten die gewoon werken
- Sinds 3.2.8 worden deze fouten alleen nog op `Error`-niveau gelogd
  voor de bronnen `status reply on connect` en `periodic status
  reply`. Komen ze uit een push, heartbeat, of eenmalige query, dan
  zijn ze alleen zichtbaar met Mode6-debug aan. Upgrade naar 3.2.8
  of nieuwer (issue #200).
- Als je de fouten nog steeds ziet op `Error`-niveau ná de update,
  kijk dan naar de `event=` tag in de logregel:
  - `event="status reply on connect"` — het apparaat accepteert de
    eerste TCP-connect niet. Dit is een echt probleem; controleer
    `nc -zv <ip> 6668` vanaf de Domoticz-host.
  - `event="periodic status reply"` — het apparaat antwoordt niet op
    de periodieke statusvraag. Ook een echt probleem.
  - Elke andere `event=` tag met een 901/904/905 — Mode6-debug staat
    aan. Uitzetten laat de ruis verdwijnen.

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

### White colour temperature slider does nothing
- The plugin is older than 3.2.6. `temp_value_scale()` was converting
  the wrong way, so the device received wrong values and ignored them.
  Upgrade to 3.2.6 or newer (PR #229, issue #226).
- If the plugin is already on 3.2.6, check the log for
  `raw_max = 255` on a v2 bulb — that means `raw_max` is still being
  guessed from the value instead of derived from the `temp_is_v2` flag.
- Colour changes should also survive a Domoticz restart on 3.2.6; if
  they don't, the colour-write path is missing
  `unit.Update(UpdateProperties=True, ...)`.

### Camera has no video stream in Domoticz
- Expected. The DomoticzEx Python plugin API has **no camera device
  type**. Cameras in Domoticz live in a separate table
  (Setup → More Options → Camera), and a plugin cannot write to that
  table. The plugin exposes the camera's state and controls as
  ordinary Domoticz units (switches, selectors, a motion sensor) but
  cannot create a video widget.
- To add the camera to the Domoticz Camera table manually, use the
  snapshot URL from the Tuya app or the camera's ONVIF endpoint. The
  camera reports `onvif_ip_addr` and `onvif_switch` in its status; once
  ONVIF is enabled and the network IP is known, a browser at
  `http://<camera-ip>/` usually reveals the snapshot and stream paths
  (they differ per firmware).
- If you need a live view in Domoticz, configure it in
  Setup → More Options → Camera. The plugin will still provide the
  motion event on Unit 21 and the switches/selectors on units 1–20, so
  dzVents scripts can react to motion without needing the video widget.

### Camera motion sensor keeps flipping to "No motion" immediately
- Check that the Domoticz **Off Delay** on Unit 21 is set to 0. The
  plugin resets the sensor itself after 15 s; a Domoticz Off Delay
  races the plugin's timer and can reset the sensor too early.
- If the sensor flips off within a second or two, the plugin's reset
  thread is firing immediately — check that
  `CAMERA_MOTION_RESET_SECONDS` has not been changed to a very small
  value, and that the system clock is stable.

### Camera motion never fires
- Check the plugin version: camera support was added in 3.2.7.
- Check the log for a `Pulsar message from ...` line right after the
  physical motion. If the line is missing, Pulsar is not running —
  install `tuya-connector-python` and restart.
- If the `Pulsar message from ...` line shows `movement_detect_pic`
  with an empty value, the firmware is reporting "no motion recorded";
  wait for the next motion — the value is only filled on the event.
- If the `Pulsar message from ...` line shows a non-empty
  `movement_detect_pic` value but no `event=motion` follows, the config
  entry `{dev_id}:motion` / `last_pic` is stale (contains the same
  value). Restart the plugin to reset it, or delete the entry.
- If nothing appears at all and the camera's category is not `cdsxj`,
  the DeviceType mapping does not apply. Confirm with the Tuya app's
  device info or the plugin's `deviceType` log line at startup.

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