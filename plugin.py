# DomoticzEx TUYA Plugin
#
# Author: Xenomes (xenomes@outlook.com)
#
"""
<plugin key="tinytuya" name="TinyTUYA" author="Xenomes" version="3.0.8" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git">
    <description>
        Support forum:
        <a href="https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441">
            https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441
        </a>
        <br/><br/>

        <h2>TinyTuya Plugin - Hybrid Local / Cloud Control version 3.0.8</h2><br/>

        This plugin uses the Tuya IoT Cloud Platform <b>only for initial device discovery, DPS mapping and configuration</b>.
        Once devices are configured, commands and status updates are handled locally using <b>TinyTuya</b> whenever possible.
        If a device is not reachable locally, the plugin automatically falls back to Tuya Cloud control.
        <br/><br/>

        Cloud setup instructions can be found here:<br/>
        https://github.com/jasonacox/tinytuya (step 3)<br/>
        or via PDF:<br/>
        https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf
        <br/><br/>

        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Automatic discovery of Tuya devices using the Tuya IoT Cloud</li>
            <li>Automatic DPS (data point) detection and mapping</li>
            <li>Local device control via TinyTuya (LAN)</li>
            <li>Automatic fallback to Tuya Cloud when local control is unavailable</li>
            <li>On/Off control, dimming, color temperature and device-specific features</li>
            <li>Status updates from local devices when available</li>
        </ul>

        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>Most Tuya-based WiFi devices are supported</li>
            <li>Support depends on available DPS provided by the device</li>
        </ul>

        <h3>Configuration</h3>
        <ul style="list-style-type:square">
            <li>
                Enter your <b>Region</b>, <b>Access ID / Client ID</b>,
                <b>Access Secret / Client Secret</b> and a <b>Search Device ID</b>
                from your Tuya IoT account.
            </li>
            <li>
                A Device ID can be found in the Tuya IoT platform:
                Cloud → Your Project → Devices → select a device.
                This Device ID is only used to discover all other devices.
            </li>
            <li>
                Complete the initial setup of your devices using the official Tuya app.
                The plugin will automatically import device settings, DPS mapping and local keys.
            </li>
            <li>
                Set the API polling interval carefully.
                Due to Tuya API rate limits, a <b>15-minute interval</b> is recommended for most accounts.
                Keep the <b>Data Timeout</b> option disabled.
            </li>
            <li>
                After setup, the plugin minimizes cloud usage and prefers local LAN communication.
            </li>
        </ul>

        If your Tuya Cloud development subscription has expired, you can extend it
        <a href="https://iot.tuya.com/cloud/products/apply-extension">HERE</a>.
    </description>
    <params>
        <param field="Mode1" label="Region" width="150px" required="true" default="EU">
            <options>
                <option label="EU" value="eu" default="true" />
                <option label="US" value="us"/>
                <option label="CN" value="cn"/>
                <option label="IND" value="in"/>
            </options>
        </param>
        <param field="Username" label="Access ID" width="300px" required="true" default="" />
        <param field="Password" label="Access Secret" width="300px" required="true" default="" password="true" />
        <param field="Mode2" label="Search DeviceID" width="300px" required="true" />
        <param field="Mode3" label="API Polling interval" width="150px" required="true" default="15 minutes">
            <options>
                <option label="1 minute" value="60" />
                <option label="5 minutes" value="300" />
                <option label="10 minutes" value="600" />
                <option label="15 minutes" value="900" />
                <option label="30 minutes" value="1800" default="true"/>
                <option label="1 hour" value="3600" />
                <option label="2 hour" value="7200" />
                <option label="3 hour" value="10800" />
                <option label="6 hour" value="21600" />
                <option label="12 hour" value="43200" />
            </options>
        </param>
        <param field="Mode4" label="Local IP rescan interval" width="200px" required="true" default="3600">
            <options>
                <option label="1 hour" value="3600"/>
                <option label="6 hours" value="21600"/>
                <option label="12 hours" value="43200"/>
                <option label="24 hours" value="86400" default="true"/>
                <option label="Static (no rescan)" value="0"/>
            </options>
        </param>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic + Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections + Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
import os
import sys
import ast
import json
import colorsys
import time
import re
import base64
import traceback
import threading

# Runtime timing
last_update = 0
last_ip_scan = 0

# Prevents overlapping heartbeat poll cycles from blocking onCommand
_handle_lock = threading.Lock()

# --- Tuya Pulsar (realtime push) support -----------------------------------
# Optional dependency: pip3 install tuya-connector-python --break-system-packages
# If it's not installed, the plugin silently falls back to poll-only behaviour
# (exactly as before) instead of crashing on startup.
import logging as _logging
try:
    from tuya_connector import TUYA_LOGGER, TuyaOpenPulsar, TuyaCloudPulsarTopic
    PULSAR_AVAILABLE = True
except ImportError:
    PULSAR_AVAILABLE = False


class _DomoticzPulsarLogHandler(_logging.Handler):
    """Forwards tuya-connector-python's own internal logging (connection
    established / closed / auth errors / reconnect attempts) into the
    plugin's normal Domoticz log, instead of it silently going nowhere.
    Without this, a failed Pulsar handshake (e.g. Message Service not
    enabled, or bad credentials) produces zero visible output."""

    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        if record.levelno >= _logging.ERROR:
            DomoticzEx.Error(f"Pulsar (lib): {msg}")
        else:
            DomoticzEx.Debug(f"Pulsar (lib): {msg}")


def _configure_pulsar_logging():
    """Route the tuya-connector-python library's own log output into
    DomoticzEx, at DEBUG level whenever this hardware instance has Mode6
    debugging enabled -- so connection problems on the Tuya side actually
    become visible instead of being silently swallowed."""
    if not PULSAR_AVAILABLE:
        return
    handler = _DomoticzPulsarLogHandler()
    handler.setFormatter(_logging.Formatter("%(message)s"))
    # Remove the library's own default StreamHandler (writes to stdout,
    # which may or may not end up in the Domoticz log depending on how
    # Domoticz captures the embedded interpreter's output) and replace it
    # with ours so everything reliably lands in DomoticzEx.Debug/Error.
    for existing in list(TUYA_LOGGER.handlers):
        TUYA_LOGGER.removeHandler(existing)
    TUYA_LOGGER.addHandler(handler)
    debug_enabled = Parameters.get('Mode6', '0') != '0'
    TUYA_LOGGER.setLevel(_logging.DEBUG if debug_enabled else _logging.WARNING)

PULSAR_REGION_ENDPOINTS = {
    'eu': 'wss://mqe.tuyaeu.com:8285/',
    'us': 'wss://mqe.tuyaus.com:8285/',
    'cn': 'wss://mqe.tuyacn.com:8285/',
    'in': 'wss://mqe.tuyain.com:8285/',
}

# Per-process (= per hardware instance) Pulsar client handle. Because every
# Domoticz Hardware entry of this plugin type runs in its own Python
# process, this global is automatically isolated per instance -- no
# cross-instance state, no shared files, no naming collisions.
pulsar_client = None


def _device_name(dev_id):
    """Best-effort human-readable name for a Tuya dev_id, for log lines
    that otherwise only show the raw ID. Tries the Tuya-side device list
    first (works even before Domoticz has created the device), then the
    Domoticz device's own Name (covers orphaned devices Tuya no longer
    reports), then falls back to the bare ID."""
    for dev in devs:
        if dev.get('id') == dev_id:
            return dev.get('name', dev_id)
    try:
        return Devices[dev_id].Units[1].Name
    except Exception:
        return dev_id


def _pulsar_on_message(msg):
    """Called from the Pulsar network thread the instant Tuya reports a
    device status change (the same channel the Tuya app uses). We don't
    trust the raw payload values directly -- we just use it as a trigger
    and re-run the plugin's own, already-correct local/cloud status
    resolution for that single device, via onHandleThread's target_dev_id
    filter. This means zero duplicated DP-mapping logic and zero risk of
    the realtime path disagreeing with the regular poll path.

    NOTE on message shape: tuya-connector-python's TuyaOpenPulsar already
    base64-decodes and AES-decrypts the raw websocket frame before calling
    this listener, so `msg` here is already the final plaintext JSON
    string -- there is no outer {"payload": {"data": ...}} envelope left
    to unwrap at this point (an earlier version of this code incorrectly
    assumed there was, which would have raised on every real message).

    Two message shapes are supported, since which one you get depends on
    which BizCode(s) you enabled under Message Service -> Messaging Rules:
      - legacy style:   {"devId": "...", "status": [{"code":..,"value":..}]}
      - IoT Core style:  {"bizCode": "devicePropertyMessage",
                          "bizData": {"devId": "...",
                                      "properties": [{"code":..,"value":..}]}}
    """
    try:
        data = json.loads(msg)
    except Exception as e:
        DomoticzEx.Debug(f"Pulsar: could not parse message ({e}): {msg}")
        return

    try:
        if 'bizData' in data:
            # IoT Core style message (e.g. bizCode 'devicePropertyMessage'
            # or 'deviceEventMessage')
            biz_data = data.get('bizData', {})
            dev_id = biz_data.get('devId')
            status_list = [
                {'code': p.get('code'), 'value': p.get('value')}
                for p in biz_data.get('properties', [])
            ]
            DomoticzEx.Debug(f"Pulsar: bizCode={data.get('bizCode')} devId={dev_id} ({_device_name(dev_id)}) properties={status_list}")
        else:
            # Legacy style message
            dev_id = data.get('devId')
            status_list = data.get('status', [])
    except Exception as e:
        DomoticzEx.Debug(f"Pulsar: could not interpret message contents ({e}): {data}")
        return

    if not dev_id:
        return

    # Check if device is locally reachable - if so, ignore Pulsar updates
    try:
        if dev_id in localtuya and localtuya[dev_id].get('ip', '') != '':
            DomoticzEx.Debug(f"Pulsar: ignoring push event for locally reachable device {_device_name(dev_id)} ({dev_id}) at {localtuya[dev_id].get('ip')}")
            return
    except Exception as e:
        DomoticzEx.Debug(f"Pulsar: error checking local reachability for device {dev_id}: {e}")

    DomoticzEx.Debug(f"Pulsar: push event received for device {_device_name(dev_id)} ({dev_id})")

    # --- Fast path: doorcontact sensors -------------------------------
    # For simple boolean sensors (category 'mcs' -> dev_type 'doorcontact',
    # always Domoticz Unit 1, DP code 'doorcontact_state') we trust the
    # pushed value directly and update Domoticz immediately, in-process,
    # with zero extra network round-trip. This is safe specifically for
    # this device type because the mapping (DP code -> Unit, boolean
    # True=open/False=closed) is fixed and simple -- unlike switches,
    # lights, covers etc. which have per-device DP layouts that only the
    # full onHandleThread logic can resolve correctly, so those still go
    # through the slower, verified fallback path below.
    try:
        category = properties.get(dev_id, {}).get('category')
        dev_type = DeviceType(category) if category else None
    except Exception:
        dev_type = None

    if dev_type == 'doorcontact':
        for item in status_list:
            if item.get('code') == 'doorcontact_state':
                is_open = bool(item.get('value'))
                UpdateDomoticz(dev_id, 1, bool(is_open), int(is_open), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (doorcontact) -> {'open' if is_open else 'closed'}")
                return

    # PIR / motion sensors: several categories (e.g. 'pir', but also 'tdq'
    # -> dev_type 'switch/sensor', 'wnykq' -> 'smartir') share this same
    # broad dev_type bucket, matching the exact set the regular poll logic
    # uses -- so instead of gating on a single dev_type, we gate on the
    # specific DP codes ('pir' / 'pir_state') that this plugin always maps
    # to Domoticz Unit 48, with "value != 'none'" meaning motion detected.
    # Any other DP code on a device in this bucket (temperature, CO2, etc.)
    # simply won't match here and falls through to the verified fallback
    # path below.
    if dev_type in ('sensor', 'smartir', 'switch/sensor'):
        for item in status_list:
            if item.get('code') in ('pir', 'pir_state'):
                motion_detected = str(item.get('value')) != 'none'
                UpdateDomoticz(dev_id, 48, bool(motion_detected), int(motion_detected), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (motion) -> {'detected' if motion_detected else 'clear'}")
                return

    # --- Fast path: Doorbell (category 'sp') ----------------------------
    # Doorbell devices have several boolean switches that we can update
    # immediately without full poll. We handle each known DP code separately.
    if dev_type == 'doorbell':
        # Map DP codes to Domoticz units (based on createDevice logic in onHandleThread)
        doorbell_unit_map = {
            'doorbell_active': 1,      # Doorbell button pressed (switch)
            'floodlight_switch': 11,   # Floodlight switch (unit 11)
            'motion_switch': 3,        # Motion switch
            'basic_indicator': 4,      # Indicator LED
            'decibel_switch': 5,       # Decibel switch
            'basic_private': 6,        # Privacy mode
            'motion_tracking': 7,      # Motion tracking
            'motion_area_switch': 8,   # Motion area switch
            'siren_switch': 9,         # Siren switch
            'nightvision_mode': 10,    # Night vision mode (selector)
        }

        for item in status_list:
            code = item.get('code')
            value = item.get('value')

            # Handle boolean switches
            if code in doorbell_unit_map:
                unit = doorbell_unit_map[code]

                # For selector (nightvision_mode), handle differently
                if code == 'nightvision_mode':
                    # We need to map the value to a level
                    try:
                        # Get the mode list from StatusProperties
                        status_props = properties.get(dev_id, {}).get('status', [])
                        for prop in status_props:
                            if prop.get('code') == 'nightvision_mode':
                                the_values = json.loads(prop.get('values', '{}'))
                                mode_list = []
                                if prop.get('type') == 'Bitmap':
                                    mode_list.extend(the_values.get('label', []))
                                else:
                                    mode_list.extend(the_values.get('range', []))
                                # Find the index of the value
                                try:
                                    level = mode_list.index(str(value)) * 10
                                    UpdateDomoticz(dev_id, unit, level, 1, 0)
                                    DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (doorbell nightvision) -> {value}")
                                except ValueError:
                                    DomoticzEx.Debug(f"Pulsar: unknown nightvision mode value '{value}' for {_device_name(dev_id)}")
                                break
                    except Exception as e:
                        DomoticzEx.Debug(f"Pulsar: error processing nightvision_mode for {_device_name(dev_id)}: {e}")
                else:
                    # Boolean switch
                    is_on = bool(value)
                    UpdateDomoticz(dev_id, unit, bool(is_on), int(is_on), 0)
                    DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (doorbell {code}) -> {is_on}")

                # Don't return immediately - process all doorbell DPs in this message

    # --- Fast path: Video Doorbell (additional DP codes) ----------------
    # Some video doorbells may have additional DP codes not covered above
    if dev_type == 'doorbell':
        # Additional DP codes for video doorbells
        video_doorbell_map = {
            'doorbell_calling': 1,      # Doorbell ring (some models use this)
            'bell_ring': 1,             # Bell ring (alternative name)
            'doorbell_ring': 1,         # Doorbell ring (alternative name)
            'floodlight': 11,           # Floodlight (alternative name)
            'light_switch': 11,         # Light switch (alternative name)
            'motion_switch': 3,         # Already covered, but keep for completeness
            'pir_sensor': 3,            # PIR sensor (alternative name)
        }

        for item in status_list:
            code = item.get('code')
            value = item.get('value')

            # Handle additional video doorbell DP codes
            if code in video_doorbell_map and code not in doorbell_unit_map:
                unit = video_doorbell_map[code]
                is_on = bool(value)
                UpdateDomoticz(dev_id, unit, bool(is_on), int(is_on), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (video doorbell {code}) -> {is_on}")

    # --- Fast path: Smoke detector (category 'qt' / 'ywbj') --------------
    # Smoke detectors typically have a simple boolean status (alarm/normal)
    # and often a battery level. We handle the main status DP codes directly.
    if dev_type == 'smokedetector':
        # Map DP codes to Domoticz units
        smoke_unit_map = {
            'smoke_sensor_status': 1,   # Smoke status (Unit 1 is the main switch)
            'smoke_state': 1,           # Alternative smoke state
            'alarm_state': 1,           # Alternative alarm state
            'PIR': 1,                   # PIR detection (some smoke detectors have this)
            'battery_state': 0,         # Battery state (handled separately)
            'battery': 0,               # Battery level (handled separately)
            'battery_percentage': 0,    # Battery percentage (handled separately)
        }

        # Battery codes to check
        battery_codes = ['battery_state', 'battery', 'battery_percentage', 'va_battery', 'residual_electricity']

        for item in status_list:
            code = item.get('code')
            value = item.get('value')

            # Handle smoke status codes
            if code in ('smoke_sensor_status', 'smoke_state', 'alarm_state'):
                # Check if value indicates alarm
                is_alarm = False
                if isinstance(value, str):
                    is_alarm = value.lower() == 'alarm'
                elif isinstance(value, (int, float)):
                    is_alarm = bool(value)

                # Update Unit 1 (switch) with alarm status
                UpdateDomoticz(dev_id, 1, bool(is_alarm), int(is_alarm), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (smoke detector {code}) -> {'alarm' if is_alarm else 'normal'}")

                # Also update Unit 2 (alarm status text) if it exists
                if checkDevice(dev_id, 2):
                    status_text = 'Alarm' if is_alarm else 'Normal'
                    UpdateDomoticz(dev_id, 2, status_text, int(is_alarm), 0)
                    DomoticzEx.Debug(f"Pulsar: updated Unit 2 for {_device_name(dev_id)} ({dev_id}) -> {status_text}")

            # Handle PIR detection (some smoke detectors have PIR)
            elif code == 'PIR':
                is_detected = bool(value) if isinstance(value, (int, float)) else str(value) != '0'
                UpdateDomoticz(dev_id, 1, bool(is_detected), int(is_detected), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (smoke detector PIR) -> {'detected' if is_detected else 'clear'}")

            # Handle battery status - update battery level for all units
            elif code in battery_codes:
                try:
                    battery_level = None
                    if code == 'battery_state':
                        if value == 'high':
                            battery_level = 100
                        elif value == 'middle':
                            battery_level = 50
                        elif value == 'low':
                            battery_level = 5
                    elif code == 'battery':
                        battery_level = int(value) * 10 if value is not None else None
                    elif code == 'va_battery':
                        battery_level = int(value) if value is not None else None
                    elif code == 'battery_percentage':
                        battery_level = int(value) if value is not None else None
                    elif code == 'residual_electricity':
                        battery_level = int(value) if value is not None else None

                    if battery_level is not None and 0 <= battery_level <= 100:
                        # Update battery level for all units of this device
                        for unit in Devices[dev_id].Units:
                            if Devices[dev_id].Units[unit].BatteryLevel != battery_level:
                                Devices[dev_id].Units[unit].BatteryLevel = battery_level
                                Devices[dev_id].Units[unit].Update()
                        DomoticzEx.Debug(f"Pulsar: updated battery for {_device_name(dev_id)} ({dev_id}) -> {battery_level}%")
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error updating battery for {_device_name(dev_id)}: {e}")

    # --- Fast path: Water leak sensor (category 'sj') --------------------
    # Water leak sensors have a simple boolean status (leak/normal)
    if dev_type == 'waterleak':
        battery_codes = ['battery_state', 'battery', 'battery_percentage', 'va_battery', 'residual_electricity']

        for item in status_list:
            code = item.get('code')
            value = item.get('value')

            if code in ('watersensor_state', 'leak_state', 'water_leak', 'alarm_state'):
                is_leak = False
                if isinstance(value, str):
                    is_leak = value.lower() == 'leak' or value.lower() == 'alarm'
                elif isinstance(value, (int, float)):
                    is_leak = bool(value)

                # Update Unit 1 (switch) with leak status
                UpdateDomoticz(dev_id, 1, bool(is_leak), int(is_leak), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (water leak {code}) -> {'leak' if is_leak else 'normal'}")

            # Handle battery status
            elif code in battery_codes:
                try:
                    battery_level = None
                    if code == 'battery_state':
                        if value == 'high':
                            battery_level = 100
                        elif value == 'middle':
                            battery_level = 50
                        elif value == 'low':
                            battery_level = 5
                    elif code == 'battery':
                        battery_level = int(value) * 10 if value is not None else None
                    elif code == 'va_battery':
                        battery_level = int(value) if value is not None else None
                    elif code == 'battery_percentage':
                        battery_level = int(value) if value is not None else None
                    elif code == 'residual_electricity':
                        battery_level = int(value) if value is not None else None

                    if battery_level is not None and 0 <= battery_level <= 100:
                        for unit in Devices[dev_id].Units:
                            if Devices[dev_id].Units[unit].BatteryLevel != battery_level:
                                Devices[dev_id].Units[unit].BatteryLevel = battery_level
                                Devices[dev_id].Units[unit].Update()
                        DomoticzEx.Debug(f"Pulsar: updated battery for {_device_name(dev_id)} ({dev_id}) -> {battery_level}%")
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error updating battery for {_device_name(dev_id)}: {e}")

    # --- Fast path: Smart Lock (category 'ms' / 'jtmspro') --------------
    # Smart locks have lock/unlock state, alarm status, and battery level
    if dev_type == 'smartlock':
        battery_codes = ['battery_state', 'battery', 'battery_percentage', 'va_battery', 'residual_electricity']

        for item in status_list:
            code = item.get('code')
            value = item.get('value')

            # Lock motor state (Unit 1)
            if code in ('lock_motor_state', 'rtc_lock', 'switch'):
                is_locked = bool(value) if isinstance(value, (int, float)) else str(value) != '0'
                # Unit 1: nValue=0 means locked (closed), nValue=1 means unlocked (open)
                UpdateDomoticz(dev_id, 1, bool(not is_locked), int(not is_locked), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (smartlock {code}) -> {'locked' if is_locked else 'unlocked'}")

            # Alarm lock status (Unit 2 - selector)
            elif code == 'alarm_lock':
                try:
                    status_props = properties.get(dev_id, {}).get('status', [])
                    for prop in status_props:
                        if prop.get('code') == 'alarm_lock':
                            the_values = json.loads(prop.get('values', '{}'))
                            mode_list = []
                            if prop.get('type') == 'Bitmap':
                                mode_list.extend(the_values.get('label', []))
                            else:
                                mode_list.extend(the_values.get('range', []))
                            # Find the index of the value
                            try:
                                level = mode_list.index(str(value)) * 10
                                UpdateDomoticz(dev_id, 2, level, 1, 0)
                                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (smartlock alarm_lock) -> {value}")
                            except ValueError:
                                DomoticzEx.Debug(f"Pulsar: unknown alarm_lock value '{value}' for {_device_name(dev_id)}")
                            break
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error processing alarm_lock for {_device_name(dev_id)}: {e}")

            # Unlock methods (Unit 3 - switches)
            elif code == 'unlock_ble':
                is_unlocked = bool(value) if isinstance(value, (int, float)) else str(value) != '0'
                UpdateDomoticz(dev_id, 3, bool(is_unlocked), int(is_unlocked), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (smartlock unlock_ble) -> {is_unlocked}")

            elif code == 'unlock_card':
                is_unlocked = bool(value) if isinstance(value, (int, float)) else str(value) != '0'
                UpdateDomoticz(dev_id, 4, bool(is_unlocked), int(is_unlocked), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (smartlock unlock_card) -> {is_unlocked}")

            # Handle battery status
            elif code in battery_codes:
                try:
                    battery_level = None
                    if code == 'battery_state':
                        if value == 'high':
                            battery_level = 100
                        elif value == 'middle':
                            battery_level = 50
                        elif value == 'low':
                            battery_level = 5
                    elif code == 'battery':
                        battery_level = int(value) * 10 if value is not None else None
                    elif code == 'va_battery':
                        battery_level = int(value) if value is not None else None
                    elif code == 'battery_percentage':
                        battery_level = int(value) if value is not None else None
                    elif code == 'residual_electricity':
                        battery_level = int(value) if value is not None else None

                    if battery_level is not None and 0 <= battery_level <= 100:
                        for unit in Devices[dev_id].Units:
                            if Devices[dev_id].Units[unit].BatteryLevel != battery_level:
                                Devices[dev_id].Units[unit].BatteryLevel = battery_level
                                Devices[dev_id].Units[unit].Update()
                        DomoticzEx.Debug(f"Pulsar: updated battery for {_device_name(dev_id)} ({dev_id}) -> {battery_level}%")
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error updating battery for {_device_name(dev_id)}: {e}")

    # --- Fast path: Human Presence Sensor (category 'hps') --------------
    # Human presence sensors have presence state, sensitivity, and battery level
    if dev_type == 'human_presence':
        battery_codes = ['battery_state', 'battery', 'battery_percentage', 'va_battery', 'residual_electricity']

        for item in status_list:
            code = item.get('code')
            value = item.get('value')

            # Presence state (Unit 1 - switch)
            if code == 'presence_state':
                is_present = bool(value) if isinstance(value, (int, float)) else str(value) != '0'
                UpdateDomoticz(dev_id, 1, bool(is_present), int(is_present), 0)
                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (human_presence presence_state) -> {'present' if is_present else 'absent'}")

            # Sensitivity (Unit 2 - selector)
            elif code == 'sensitivity':
                try:
                    status_props = properties.get(dev_id, {}).get('status', [])
                    for prop in status_props:
                        if prop.get('code') == 'sensitivity':
                            the_values = json.loads(prop.get('values', '{}'))
                            mode_list = []
                            if prop.get('type') == 'Bitmap':
                                mode_list.extend(the_values.get('label', []))
                            else:
                                mode_list.extend(the_values.get('range', []))
                            # Find the index of the value
                            try:
                                level = mode_list.index(str(value)) * 10
                                UpdateDomoticz(dev_id, 2, level, 1, 0)
                                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (human_presence sensitivity) -> {level}")
                            except ValueError:
                                DomoticzEx.Debug(f"Pulsar: unknown sensitivity value '{value}' for {_device_name(dev_id)}")
                            break
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error processing sensitivity for {_device_name(dev_id)}: {e}")

            # Near detection (Unit 3 - scale)
            elif code == 'near_detection':
                try:
                    # Scale the value to 0-100 range for Domoticz
                    scaled_value = int(value) if isinstance(value, (int, float)) else 0
                    if scaled_value > 100:
                        scaled_value = 100
                    UpdateDomoticz(dev_id, 3, str(scaled_value), 0, 0)
                    DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (human_presence near_detection) -> {scaled_value}")
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error processing near_detection for {_device_name(dev_id)}: {e}")

            # Far detection (Unit 4 - scale)
            elif code == 'far_detection':
                try:
                    # Scale the value to 0-100 range for Domoticz
                    scaled_value = int(value) if isinstance(value, (int, float)) else 0
                    if scaled_value > 100:
                        scaled_value = 100
                    UpdateDomoticz(dev_id, 4, str(scaled_value), 0, 0)
                    DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (human_presence far_detection) -> {scaled_value}")
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error processing far_detection for {_device_name(dev_id)}: {e}")

            # Checking result (Unit 5 - selector)
            elif code == 'checking_result':
                try:
                    status_props = properties.get(dev_id, {}).get('status', [])
                    for prop in status_props:
                        if prop.get('code') == 'checking_result':
                            the_values = json.loads(prop.get('values', '{}'))
                            mode_list = []
                            if prop.get('type') == 'Bitmap':
                                mode_list.extend(the_values.get('label', []))
                            else:
                                mode_list.extend(the_values.get('range', []))
                            # Find the index of the value
                            try:
                                level = mode_list.index(str(value)) * 10
                                UpdateDomoticz(dev_id, 5, level, 1, 0)
                                result_text = mode_list[int(level/10)] if int(level/10) < len(mode_list) else str(value)
                                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (human_presence checking_result) -> {result_text}")
                            except ValueError:
                                DomoticzEx.Debug(f"Pulsar: unknown checking_result value '{value}' for {_device_name(dev_id)}")
                            break
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error processing checking_result for {_device_name(dev_id)}: {e}")

            # Target distance closest (Unit 6 - scale)
            elif code == 'target_dis_closest':
                try:
                    # Scale the value to 0-100 range for Domoticz
                    scaled_value = int(value) if isinstance(value, (int, float)) else 0
                    if scaled_value > 100:
                        scaled_value = 100
                    UpdateDomoticz(dev_id, 6, str(scaled_value), 0, 0)
                    DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (human_presence target_dis_closest) -> {scaled_value}")
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error processing target_dis_closest for {_device_name(dev_id)}: {e}")

            # Presence state selector (Unit 7 - selector)
            elif code == 'presence_state_selector':
                try:
                    status_props = properties.get(dev_id, {}).get('status', [])
                    for prop in status_props:
                        if prop.get('code') == 'presence_state_selector':
                            the_values = json.loads(prop.get('values', '{}'))
                            mode_list = []
                            if prop.get('type') == 'Bitmap':
                                mode_list.extend(the_values.get('label', []))
                            else:
                                mode_list.extend(the_values.get('range', []))
                            # Find the index of the value
                            try:
                                level = mode_list.index(str(value)) * 10
                                UpdateDomoticz(dev_id, 7, level, 1, 0)
                                DomoticzEx.Debug(f"Pulsar: fast path applied for {_device_name(dev_id)} ({dev_id}) (human_presence presence_state_selector) -> {value}")
                            except ValueError:
                                DomoticzEx.Debug(f"Pulsar: unknown presence_state value '{value}' for {_device_name(dev_id)}")
                            break
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error processing presence_state selector for {_device_name(dev_id)}: {e}")

            # Handle battery status
            elif code in battery_codes:
                try:
                    battery_level = None
                    if code == 'battery_state':
                        if value == 'high':
                            battery_level = 100
                        elif value == 'middle':
                            battery_level = 50
                        elif value == 'low':
                            battery_level = 5
                    elif code == 'battery':
                        battery_level = int(value) * 10 if value is not None else None
                    elif code == 'va_battery':
                        battery_level = int(value) if value is not None else None
                    elif code == 'battery_percentage':
                        battery_level = int(value) if value is not None else None
                    elif code == 'residual_electricity':
                        battery_level = int(value) if value is not None else None

                    if battery_level is not None and 0 <= battery_level <= 100:
                        for unit in Devices[dev_id].Units:
                            if Devices[dev_id].Units[unit].BatteryLevel != battery_level:
                                Devices[dev_id].Units[unit].BatteryLevel = battery_level
                                Devices[dev_id].Units[unit].Update()
                        DomoticzEx.Debug(f"Pulsar: updated battery for {_device_name(dev_id)} ({dev_id}) -> {battery_level}%")
                except Exception as e:
                    DomoticzEx.Debug(f"Pulsar: error updating battery for {_device_name(dev_id)}: {e}")

    # -------------------------------------------------------------------

    def _run_targeted_update():
        if not _handle_lock.acquire(timeout=10):
            DomoticzEx.Debug(f"Pulsar: poll busy, dropping event for {_device_name(dev_id)} ({dev_id}) (next heartbeat will catch up)")
            return
        try:
            onHandleThread(False, False, target_dev_id=dev_id)
        except Exception as e:
            DomoticzEx.Error(f"Pulsar: error handling push event for {_device_name(dev_id)} ({dev_id}): {e}")
        finally:
            _handle_lock.release()

    threading.Thread(target=_run_targeted_update, daemon=True).start()


def start_pulsar_listener():
    """Start the realtime push listener for this hardware instance, using
    the same Access ID / Access Secret / Region already configured for
    this plugin instance (Username / Password / Mode1). No extra setup
    or config file needed beyond what the plugin already requires."""
    global pulsar_client

    if not PULSAR_AVAILABLE:
        DomoticzEx.Log(
            "Pulsar realtime updates disabled: 'tuya-connector-python' package not installed. "
            "Install with: pip3 install tuya-connector-python --break-system-packages. "
            "Falling back to poll-only mode."
        )
        return

    region = Parameters.get('Mode1', 'eu')
    endpoint = PULSAR_REGION_ENDPOINTS.get(region)
    if not endpoint:
        DomoticzEx.Error(f"Pulsar: unknown region '{region}', realtime updates disabled")
        return

    _configure_pulsar_logging()
    DomoticzEx.Log(f"Pulsar realtime listener starting (region={region})...")

    try:
        pulsar_client = TuyaOpenPulsar(
            Parameters['Username'],
            Parameters['Password'],
            endpoint,
            TuyaCloudPulsarTopic.PROD,
        )
        pulsar_client.add_message_listener(_pulsar_on_message)
        pulsar_client.start()
        DomoticzEx.Log(f"Pulsar realtime listener started (region={region})")
        _log_realtime_capable_devices()
    except Exception as e:
        DomoticzEx.Error(f"Pulsar: failed to start realtime listener: {e}")
        pulsar_client = None


def _log_realtime_capable_devices():
    """Log a clear startup overview of the realtime (Pulsar) situation for
    every device type covered by the fast path (door contacts, motion sensors,
    and doorbells), distinguishing every case that matters instead of leaving it
    to be discovered via Debug logging:

      1. OK        - Tuya reports it as a covered device type AND Domoticz
                      has the device -> realtime updates will apply
                      correctly.
      2. MISMATCH  - Tuya reports it as a covered device type but Domoticz
                      has NOT (yet) created a device for it -- e.g. right
                      after startup, before the first regular poll has run.
      3. MISMATCH  - a device exists in Domoticz for this hardware instance,
                      but Tuya no longer reports that device ID at all --
                      typically means the physical sensor was re-paired /
                      factory reset and got a new ID; the Domoticz device
                      is now orphaned and stops receiving updates.
    """
    try:
        tuya_ids = set()
        realtime_devices = {}  # dev_id -> (name, unit, label)
        for dev in devs:
            dev_id = dev.get('id')
            tuya_ids.add(dev_id)
            category = properties.get(dev_id, {}).get('category')
            dev_type = DeviceType(category) if category else None
            status_props = properties.get(dev_id, {}).get('status', [])

            if dev_type == 'doorcontact':
                realtime_devices[dev_id] = (dev.get('name', 'Unknown'), 1, 'door contact')
            elif dev_type in ('sensor', 'smartir', 'switch/sensor') and (searchCode('pir', status_props) or searchCode('pir_state', status_props)):
                realtime_devices[dev_id] = (dev.get('name', 'Unknown'), 48, 'motion sensor')
            elif dev_type == 'doorbell':
                # Doorbell devices have multiple units that can be updated
                realtime_devices[dev_id] = (dev.get('name', 'Unknown'), 1, 'doorbell (multiple units)')

        active = []
        missing_in_domoticz = []
        for dev_id, (name, unit, label) in realtime_devices.items():
            entry = f"{name} ({dev_id}) [{label}]"
            if checkDevice(dev_id, unit):
                active.append(entry)
            else:
                missing_in_domoticz.append(entry)

        # Orphaned: a device exists in Domoticz for this hardware instance,
        # but its ID no longer appears anywhere in Tuya's current device
        # list at all (any device type, not just the ones covered by the
        # fast path -- an ID that vanished from Tuya's side is abnormal
        # regardless of type).
        orphaned = []
        try:
            for existing_id in Devices:
                if existing_id not in tuya_ids:
                    try:
                        existing_name = Devices[existing_id].Units[1].Name
                    except Exception:
                        existing_name = existing_id
                    orphaned.append(f"{existing_name} ({existing_id})")
        except Exception as e:
            DomoticzEx.Debug(f"Pulsar: could not enumerate existing Domoticz devices for orphan check: {e}")

        if active:
            DomoticzEx.Log(f"Realtime (Pulsar) updates active for {len(active)} device(s):")
            for entry in active:
                DomoticzEx.Log(f"  - OK: {entry}")

        if missing_in_domoticz:
            DomoticzEx.Log(f"MISMATCH: {len(missing_in_domoticz)} device(s) known to Tuya, but not yet created in Domoticz (will appear after the next regular poll):")
            for entry in missing_in_domoticz:
                DomoticzEx.Log(f"  - {entry}")

        if orphaned:
            DomoticzEx.Log(f"MISMATCH: {len(orphaned)} orphaned device(s) found in Domoticz (present here, but Tuya no longer reports this ID -- likely after re-pairing/resetting the physical device; the old device no longer receives updates and can be removed manually):")
            for entry in orphaned:
                DomoticzEx.Log(f"  - {entry}")

        if not realtime_devices and not orphaned:
            DomoticzEx.Log("No door contacts, motion sensors, or doorbells found for this instance -- realtime Pulsar updates are not applicable right now.")
    except Exception as e:
        DomoticzEx.Debug(f"Pulsar: could not build realtime-devices overview: {e}")


def stop_pulsar_listener():
    """Cleanly tear down the Pulsar connection for this hardware instance.
    Important for multi-instance setups: without this, disabling/reloading
    one instance could leave an orphaned background thread and websocket
    connection running."""
    global pulsar_client
    if pulsar_client is not None:
        DomoticzEx.Log("Pulsar realtime listener stopping...")
        try:
            pulsar_client.stop()
            DomoticzEx.Log("Pulsar realtime listener stopped")
        except AttributeError as e:
            # Handle case where internal Pulsar state is already corrupted
            DomoticzEx.Error(f"Pulsar: internal state error while stopping listener: {e}")
        except Exception as e:
            DomoticzEx.Error(f"Pulsar: error while stopping listener: {e}")
        finally:
            # Clear the reference even if stop() failed to prevent further errors
            pulsar_client = None
# -----------------------------------------------------------------------

try:
    import DomoticzEx
except ImportError:
    import fakeDomoticz as DomoticzEx
try:
    import tinytuya
except ImportError:
    print('No tinytuya module installed')
    sys.exit(1)
print(f"Tinytuya version: {tinytuya.version}")
class BasePlugin:
    def __init__(self):
        self.enabled = True
        return

    def onStart(self):
        if Parameters['Mode6'] != '0':
            DomoticzEx.Debugging(int(Parameters['Mode6']))
            # DomoticzEx.Log('Debugger started, use 'telnet 0.0.0.0 4444' to connect')
            # import rpdb
            # rpdb.set_trace()
            DumpConfigToLog()

        DomoticzEx.Log(f"Domoticz version: {Parameters['DomoticzVersion']}")
        DomoticzEx.Log(f"TinyTUYA {Parameters['Version']} plugin started")
        DomoticzEx.Log(f"TinyTuya Version: {tinytuya.version}")

        global testdata, Error, fulllocal

        if os.path.isfile(Parameters['HomeFolder'] + '/debug_devices.json'):
            testdata = True
            fulllocal = False
            DomoticzEx.Error('!!! Warning Plugin overruled by local json files !!!')
        elif os.path.isfile(Parameters['HomeFolder'] + '/tuya-raw.json'):
            testdata = False
            fulllocal = True
            DomoticzEx.Debug('Plugin is full local mode from tuya-raw.json')
        else:
            testdata = False
            fulllocal = False
        # DomoticzEx.Heartbeat(2)
        onHandleThread(True, False)

        # Start realtime push updates (falls back to poll-only if the
        # tuya-connector-python package isn't installed, or if it's not
        # a cloud-mode setup)
        if not testdata and not fulllocal:
            DomoticzEx.Log("Initializing Pulsar realtime listener...")
            start_pulsar_listener()
        else:
            DomoticzEx.Log("Pulsar realtime listener skipped (testdata/fulllocal mode active)")

    def onStop(self):
        DomoticzEx.Log('onStop called')

        stop_pulsar_listener()

        # Give background threads time to exit cleanly
        time.sleep(0.5)

        try:
            # Cleanup devices that are not recognized
            devs = Devices
            for dev in devs:
                if 'This device is not recognized.' in Devices[dev].Units[1].sValue:
                    Devices[dev].Units[1].Delete()
        except Exception as e:
            DomoticzEx.Error(f"Error during device cleanup: {e}")

        # Start the shutdown process
        start_time = time.time()

        DomoticzEx.Log('Exiting plugin.')

    def onConnect(self, Connection, Status, Description):
        DomoticzEx.Log('onConnect called')

    def onMessage(self, Connection, Data):
        DomoticzEx.Log('onMessage called')

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        # device for the DomoticzEx
        dev = Devices[DeviceID].Units[Unit]
        # Prefer the device-level name if available, otherwise fall back to unit name or ID
        dev_name = Devices[DeviceID].Name if DeviceID in Devices and hasattr(Devices[DeviceID], 'Name') else getattr(dev, 'Name', DeviceID)
        DomoticzEx.Debug(f"onCommand called for Device '{dev_name}' Unit {Unit}: Parameter '{Command}', Level: {Level}, Color: {Color}")
        DomoticzEx.Debug(f"Device Name: {dev_name}")
        DomoticzEx.Debug(f"nValue: {dev.nValue}")
        DomoticzEx.Debug(f"sValue: {dev.sValue} Type {type(dev.sValue)}")
        DomoticzEx.Debug(f"LastLevel: {dev.LastLevel}")

        try:
            if Error is not None:
                DomoticzEx.Error(Error['Payload'])
            else:
                # Control device and update status in DomoticzEx
                dev_type = getConfigItem(DeviceID, 'category')
                # scalemode = getConfigItem(DeviceID, 'scalemode')
                product_id = getConfigItem(DeviceID, 'product_id')
                # if len(properties) == 0:
                #     properties = {}
                #     for dev in devs:
                #         properties[dev_id] = tuya.getproperties(dev_id)['result']

                function = properties[DeviceID]['functions']
                status = properties[DeviceID]['status']
                if len(Color) != 0:
                    Color = ast.literal_eval(Color)

                if dev_type in ('switch', 'switch/sensor'):
                    if searchCode('switch', function):
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, 'switch', False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, 'switch', True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif searchCode('switch_on', function):
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, 'switch_on', False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, 'switch_on', True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    else:
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, f"switch_{Unit}", False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, f"switch_{Unit}", True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'wswitch':
                    if Command == 'Set Level':
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        if searchCode(f"switch{Unit}_value", status):
                            SendCommandTuya(DeviceID, f"switch{Unit}_value", mode[int(Level / 10)])
                        if searchCode(f"switch_type_{Unit}", status):
                            SendCommandTuya(DeviceID, f"switch_type_{Unit}", mode[int(Level / 10)])
                        if searchCode(f"switch_mode{Unit}", status):
                            SendCommandTuya(DeviceID, f"switch_mode{Unit}", mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type in ('dimmer'):
                    if Command == 'Off':
                        SendCommandTuya(DeviceID, f"switch_led_{Unit}", False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'Set Level':
                        SendCommandTuya(DeviceID, f"switch_led_{Unit}", True)
                        SendCommandTuya(DeviceID, f"bright_value_{Unit}", Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if (dev_type in ('light') or dev_type in ('fanlight') or dev_type in ('pirlight')) and Unit == 1:
                    if searchCode('led_switch', function):
                        switch = 'led_switch'
                    elif searchCode('switch_led', function):
                        switch = 'switch_led'
                    elif searchCode('Light', function):
                        switch = 'Light'

                    # Check if colour_data uses v2 scaling (max = 1000)
                    colour_data_v2 = False
                    for item in function:
                        if item['code'] == 'colour_data_v2':
                            colour_data_v2 = True
                            break
                        if item['code'] == 'colour_data':
                            try:
                                values = json.loads(item['values'])
                                if values.get('v', {}).get('max', 255) == 1000:
                                    colour_data_v2 = True
                                    break
                            except:
                                pass
                        if item['code'] in ('bright_value', 'bright_value_1', 'bright_value_2'):
                            try:
                                values = json.loads(item['values'])
                                if values.get('max', 0) >= 1000:
                                    colour_data_v2 = True
                                    break
                            except:
                                pass

                    if Command == 'Off':
                        SendCommandTuya(DeviceID, switch, False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandTuya(DeviceID, switch, True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level':
                        if searchCode('bright_value_v2', function):
                            SendCommandTuya(DeviceID, switch, True)
                            SendCommandTuya(DeviceID, 'bright_value_v2', Level)
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                        elif searchCode('bright_value', function):
                            SendCommandTuya(DeviceID, switch, True)
                            SendCommandTuya(DeviceID, 'bright_value', Level)
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif (Command == 'Set Color' or Command == 'Set Level') and len(Color) != 0:
                        if Color['m'] == 2:
                            SendCommandTuya(DeviceID, switch, True)
                            SendCommandTuya(DeviceID, 'work_mode', 'white')
                            if searchCode('bright_value_v2', function):
                                SendCommandTuya(DeviceID, 'bright_value_v2', Level)
                                SendCommandTuya(DeviceID, 'temp_value_v2', int(Color['t']))
                                UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                                UpdateDomoticz(DeviceID, Unit, Color, 1, 0)
                            elif searchCode('bright_value', function):
                                SendCommandTuya(DeviceID, 'bright_value', Level)
                                SendCommandTuya(DeviceID, 'temp_value', int(Color['t']))
                                UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                                UpdateDomoticz(DeviceID, Unit, Color, 1, 0)
                        elif Color['m'] == 3:
                            # Determine target scale for colour_data 'v' (255 or 1000)
                            bright_max = 0
                            for it in function:
                                if it.get('code') in ('bright_value', 'bright_value_1', 'bright_value_2'):
                                    try:
                                        vals = json.loads(it.get('values', '{}'))
                                        bright_max = max(bright_max, int(vals.get('max', 0)))
                                    except:
                                        pass

                            use_v1000 = colour_data_v2 or bright_max >= 1000
                            if use_v1000:
                                h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                                v_scaled = int(Level * 10)
                            else:
                                h, s, v = rgb_to_hsv(int(Color['r']), int(Color['g']), int(Color['b']))
                                v_scaled = Level * 2.55

                            hvs = {'h': h, 's': s, 'v': v_scaled}
                            SendCommandTuya(DeviceID, switch, True)
                            SendCommandTuya(DeviceID, 'colour_data', hvs)
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                            UpdateDomoticz(DeviceID, Unit, Color, 1, 0)

                # Multi-LED ondersteuning voor draw_tool (buiten Unit == 1 check)
                if dev_type in ('light', 'fanlight', 'pirlight') and Unit >= 11:
                    DomoticzEx.Debug(f"Multi-LED check: Unit {Unit}, draw_tool in functions: {searchCode('draw_tool', function)}")
                    if searchCode('draw_tool', function):
                        led_index = Unit - 11
                        DomoticzEx.Log(f"Multi-LED detected: LED {led_index}, command {Command}")
                        if Command == 'Off':
                            max_value = get_draw_tool_max_value(DeviceID)
                            send_draw_tool_command(DeviceID, led_index, 0, 0, 0, 0, max_value)
                            UpdateDomoticz(DeviceID, Unit, 0, 0, 0)

                        elif Command == 'On':
                            current_level = 100
                            huidige_kleur = get_led_color(DeviceID, Unit)
                            max_value = get_draw_tool_max_value(DeviceID)
                            send_draw_tool_command(DeviceID, led_index,
                                                   huidige_kleur['r'],
                                                   huidige_kleur['g'],
                                                   huidige_kleur['b'],
                                                   current_level, max_value)
                            UpdateDomoticz(DeviceID, Unit, current_level, 1, 0)

                        elif Command == 'Set Level':
                            huidige_kleur = get_led_color(DeviceID, Unit)
                            max_value = get_draw_tool_max_value(DeviceID)
                            send_draw_tool_command(DeviceID, led_index,
                                                   huidige_kleur['r'],
                                                   huidige_kleur['g'],
                                                   huidige_kleur['b'],
                                                   Level, max_value)
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                        elif (Command == 'Set Color' or Command == 'Set Level') and len(Color) != 0:
                            max_value = get_draw_tool_max_value(DeviceID)
                            if Color['m'] == 2:
                                send_draw_tool_command(DeviceID, led_index, 255, 255, 255, Level, max_value)
                            elif Color['m'] == 3:
                                send_draw_tool_command(DeviceID, led_index,
                                                       int(Color['r']),
                                                       int(Color['g']),
                                                       int(Color['b']),
                                                       Level, max_value)
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                            if Color['m'] == 3:
                                kleur_string = f"{int(Color['r'])},{int(Color['g'])},{int(Color['b'])}"
                                UpdateDomoticz(DeviceID, Unit, kleur_string, 1, 0)

                if dev_type in ('light') and Unit == 2:
                    if searchCode('Power', function):
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, 'Power', False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, 'Power', True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    # Handle Set Color / Set Level for non-Unit-1 color-capable devices (e.g., Unit 11)
                    elif (Command == 'Set Color' or Command == 'Set Level') and len(Color) != 0 and (searchCode('colour_data', function) or searchCode('colour_data_v2', function)):
                        # determine switch name if present
                        if searchCode('led_switch', function):
                            switch = 'led_switch'
                        elif searchCode('switch_led', function):
                            switch = 'switch_led'
                        elif searchCode('Light', function):
                            switch = 'Light'
                        else:
                            switch = None

                        # Determine if colour_data v2 scaling is used
                        colour_data_v2_local = False
                        for item in function:
                            if item.get('code') == 'colour_data_v2':
                                colour_data_v2_local = True
                                break
                            if item.get('code') == 'colour_data':
                                try:
                                    values = json.loads(item.get('values','{}'))
                                    if values.get('v', {}).get('max', 255) == 1000:
                                        colour_data_v2_local = True
                                        break
                                except:
                                    pass

                        # determine bright max
                        bright_max = 0
                        for it in function:
                            if it.get('code') in ('bright_value', 'bright_value_1', 'bright_value_2'):
                                try:
                                    vals = json.loads(it.get('values', '{}'))
                                    bright_max = max(bright_max, int(vals.get('max', 0)))
                                except:
                                    pass

                        use_v1000 = colour_data_v2_local or bright_max >= 1000

                        if Color.get('m') == 2:
                            if switch:
                                SendCommandTuya(DeviceID, switch, True)
                            SendCommandTuya(DeviceID, 'work_mode', 'white')
                            if searchCode('bright_value_v2', function):
                                SendCommandTuya(DeviceID, 'bright_value_v2', Level)
                                SendCommandTuya(DeviceID, 'temp_value_v2', int(Color['t']))
                            elif searchCode('bright_value', function):
                                SendCommandTuya(DeviceID, 'bright_value', Level)
                                SendCommandTuya(DeviceID, 'temp_value', int(Color['t']))
                        elif Color.get('m') == 3:
                            if use_v1000:
                                h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                                v_scaled = int(Level * 10)
                            else:
                                h, s, v = rgb_to_hsv(int(Color['r']), int(Color['g']), int(Color['b']))
                                v_scaled = Level * 2.55

                            hvs = {'h': h, 's': s, 'v': v_scaled}
                            if switch:
                                SendCommandTuya(DeviceID, switch, True)
                            SendCommandTuya(DeviceID, 'colour_data', hvs)

                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                        UpdateDomoticz(DeviceID, Unit, Color, 1, 0)
                if dev_type in ('light') and Unit == 3:
                    if searchCode('lightmode', function):
                        switch = 'lightmode'
                        if Command == 'Set Level' and Unit  == 3:
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, switch, mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                if dev_type in ('light') and Unit == 4:
                    if searchCode('dp_mist_grade', function):
                        switch = 'dp_mist_grade'
                        if Command == 'Set Level' and Unit  == 4:
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, switch, mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type == ('cover'):
                    ext = '_' + str(Unit) if Unit > 1 else ''
                    if Command == 'Open':
                        if searchCode(f"mach_operate{ext}", function):
                            SendCommandTuya(DeviceID, f"mach_operate{ext}", 'FZ')
                        elif searchCode(f"status{ext}" , function):
                            SendCommandTuya(DeviceID, 'status', '1')
                        else:
                            SendCommandTuya(DeviceID, f"control{ext}", 'open')
                        UpdateDomoticz(DeviceID, Unit, 'Open', 0, 0)
                    elif Command == 'Close':
                        if searchCode(f"mach_operate{ext}", function):
                            SendCommandTuya(DeviceID, f"mach_operate{ext}", 'ZZ')
                        elif searchCode(f"status{ext}" , function):
                            SendCommandTuya(DeviceID, 'status', '2')
                        else:
                            SendCommandTuya(DeviceID, f"control{ext}", 'close')
                        UpdateDomoticz(DeviceID, Unit, 'Close', 1, 0)
                    elif Command == 'Stop':
                        if searchCode(f"mach_operate{ext}", function):
                            SendCommandTuya(DeviceID, f"mach_operate{ext}", 'STOP')
                        elif searchCode(f"status{ext}" , function):
                            SendCommandTuya(DeviceID, 'status', '3')
                        else:
                            SendCommandTuya(DeviceID, f"control{ext}", 'stop')
                        UpdateDomoticz(DeviceID, Unit, 'Stop', 1, 0)
                    elif Command == 'Set Level':
                        if searchCode(f"percent_control{ext}", function):
                            control = f"percent_control{ext}"
                        elif searchCode(f"position{ext}", function):
                            control = f"position{ext}"
                        SendCommandTuya(DeviceID, control, Level)
                        UpdateDomoticz(DeviceID, 1, Level, 1, 0)

                elif dev_type == 'smartheatpump' :
                    if searchCode('switch', function):
                        switch = 'switch'
                        if Command == 'Off' and Unit == 1:
                            SendCommandTuya(DeviceID, switch, False)
                            UpdateDomoticz(DeviceID, 1, False, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandTuya(DeviceID, switch, True)
                            UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    if searchCode('ach_stemp', function):
                        switch = 'ach_stemp'
                        if Command == 'Set Level' and Unit  == 11:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 11, Level, 1, 0)
                    if searchCode('wth_stemp', function):
                        switch = 'wth_stemp'
                        if Command == 'Set Level' and Unit  == 12:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 12, Level, 1, 0)
                    if searchCode('aircond_temp_diff', function):
                        switch = 'aircond_temp_diff'
                        if Command == 'Set Level' and Unit  == 13:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 13, Level, 1, 0)
                    if searchCode('wth_temp_diff', function):
                        switch = 'wth_temp_diff'
                        if Command == 'Set Level' and Unit  == 14:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 14, Level, 1, 0)
                    if searchCode('acc_stemp', function):
                        switch = 'acc_stemp'
                        if Command == 'Set Level' and Unit  == 15:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 15, Level, 1, 0)
                    if searchCode('mode', function):
                        if Command == 'Set Level' and Unit == 16:
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, 16, Level, 1, 0)
                    if searchCode('work_mode', function):
                        if Command == 'Set Level' and Unit == 17:
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, 'work_mode', mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, 17, Level, 1, 0)
                    if searchCode('temp_set', function):
                        switch = 'temp_set'
                        if Command == 'Set Level' and Unit  == 19:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 19, Level, 1, 0)
                    # if searchCode('water_set', function):
                    #     switch = 'water_set'
                    #     if Command == 'Set Level' and Unit  == 20:
                    #         SendCommandTuya(DeviceID, switch, Level)
                    #         UpdateDomoticz(DeviceID, 20, Level, 1, 0)
                    if searchCode('compressor_state', function):
                        switch = 'compressor_state'
                        if Command == 'Off' and Unit == 24:
                            SendCommandTuya(DeviceID, switch, False)
                            UpdateDomoticz(DeviceID, 24, False, 0, 0)
                        elif Command == 'On' and Unit == 24:
                            SendCommandTuya(DeviceID, switch, True)
                            UpdateDomoticz(DeviceID, 24, True, 1, 0)

                elif dev_type == 'thermostat' or dev_type == 'heater' or dev_type == 'heatpump':
                    if searchCode('switch_1', function):
                        switch = 'switch_1'
                    elif searchCode('Power', function):
                        switch = 'Power'
                    elif searchCode('infared_switch', function):
                        switch = 'infared_switch'
                    else:
                        switch = 'switch'
                    if searchCode('temp_set', function):
                        switch3 = 'temp_set'
                    elif searchCode('set_temp', function):
                        switch3 = 'set_temp'
                    elif searchCode('temperature_c', function):
                        switch3 = 'temperature_c'
                    elif searchCode('TempSet', function):
                        switch3 = 'TempSet'
                    elif searchCode('target_temp', function):
                        switch3 = 'target_temp'
                    if searchCode('Mode', function):
                        switch4 = 'Mode'
                    elif searchCode('mode', function):
                        switch4 = 'mode'
                    #Disabled for isseu #147
                    # elif searchCode('work_mode', function):
                    #     switch4 = 'work_mode'
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, switch, False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, switch, True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 3:
                        SendCommandTuya(DeviceID, switch3, Level)
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = getConfigItem(f"{DeviceID}-4", 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, switch4, mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)
                    if Command == 'Off' and Unit == 5:
                        SendCommandTuya(DeviceID, 'window_check', False)
                        UpdateDomoticz(DeviceID, 5, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandTuya(DeviceID, 'window_check', True)
                        UpdateDomoticz(DeviceID, 5, True, 1, 0)
                    if Command == 'Off' and Unit == 6:
                        SendCommandTuya(DeviceID, 'child_lock', False)
                        UpdateDomoticz(DeviceID, 6, False, 0, 0)
                    elif Command == 'On' and Unit == 6:
                        SendCommandTuya(DeviceID, 'child_lock', True)
                        UpdateDomoticz(DeviceID, 6, True, 1, 0)
                    if Command == 'Off' and Unit == 7:
                        SendCommandTuya(DeviceID, 'eco', False)
                        UpdateDomoticz(DeviceID, 7, False, 0, 0)
                    elif Command == 'On' and Unit == 7:
                        SendCommandTuya(DeviceID, 'eco', True)
                        UpdateDomoticz(DeviceID, 7, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 9:
                        if searchCode('fan_level', function) or searchCode('fan_speed_enum', function):
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, 9, mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, 9, Level, 1, 0)
                        else:
                            wind = 'windspeed'
                            SendCommandTuya(DeviceID, wind, Level)
                            UpdateDomoticz(DeviceID, 9, Level, 1, 0)
                    if Command == 'Off' and Unit == 17:
                        SendCommandTuya(DeviceID, 'anti_bother', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 17:
                        SendCommandTuya(DeviceID, 'anti_bother', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type in ('sensor', 'switch/sensor'):
                    if Command == 'Set Level' and Unit == 15:
                        SendCommandTuya(DeviceID, 'ph_warn_min', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 16:
                        SendCommandTuya(DeviceID, 'ph_warn_max', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 17:
                        SendCommandTuya(DeviceID, 'pro_warn_min', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 18:
                        SendCommandTuya(DeviceID, 'pro_warn_max', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 19:
                        SendCommandTuya(DeviceID, 'orp_warn_min', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 20:
                        SendCommandTuya(DeviceID, 'orp_warn_max', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 24:
                        SendCommandTuya(DeviceID, 'temp_warn_min', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 25:
                        SendCommandTuya(DeviceID, 'temp_warn_max', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 45:
                        SendCommandTuya(DeviceID, 'cook_temperature', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 46:
                        SendCommandTuya(DeviceID, 'cook_temperature_2', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    # if Command == 'Off' and Unit == 47:
                    #     SendCommandTuya(DeviceID, 'alarm_switch', False)
                    #     UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    # elif Command == 'On' and Unit == 47:
                    #     SendCommandTuya(DeviceID, 'alarm_switch', True)
                    #     UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'doorbell':
                    if Command == 'Off' and Unit == 2:
                        SendCommandCloud(DeviceID, 'floodlight_switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandCloud(DeviceID, 'floodlight_switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 3:
                        SendCommandCloud(DeviceID, 'motion_switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 3:
                        SendCommandCloud(DeviceID, 'motion_switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 4:
                        SendCommandCloud(DeviceID, 'basic_indicator', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 4:
                        SendCommandCloud(DeviceID, 'basic_indicator', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 5:
                        SendCommandCloud(DeviceID, 'decibel_switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandCloud(DeviceID, 'decibel_switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 6:
                        SendCommandCloud(DeviceID, 'basic_private', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 6:
                        SendCommandCloud(DeviceID, 'basic_private', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 7:
                        SendCommandCloud(DeviceID, 'motion_tracking', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 7:
                        SendCommandCloud(DeviceID, 'motion_tracking', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 8:
                        SendCommandCloud(DeviceID, 'motion_area_switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 8:
                        SendCommandCloud(DeviceID, 'motion_area_switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 9:
                        SendCommandCloud(DeviceID, 'siren_switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 9:
                        SendCommandCloud(DeviceID, 'siren_switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Set Level' and Unit  == 10:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 10, mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 10, Level, 1, 0)
                    if Command == 'Off' and Unit == 11:
                        SendCommandCloud(DeviceID, 'floodlight_switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 11:
                        SendCommandCloud(DeviceID, 'floodlight_switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Set Level' and Unit == 12:
                        SendCommandCloud(DeviceID, 'ipc_siren_volume', Level)
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 13:
                        SendCommandCloud(DeviceID, 'ipc_siren_duration', Level)
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'fan':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'fan_speed', int(mode[int(Level / 10)]))
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit  == 4:
                        SendCommandTuya(DeviceID, 'set_temp', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Off' and Unit == 7:
                        SendCommandTuya(DeviceID, 'light', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 7:
                        SendCommandTuya(DeviceID, 'light', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 8:
                        SendCommandTuya(DeviceID, 'RH_switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 8:
                        SendCommandTuya(DeviceID, 'RH_switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 11:
                        SendCommandTuya(DeviceID, 'anion', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 11:
                        SendCommandTuya(DeviceID, 'anion', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 12:
                        SendCommandTuya(DeviceID, 'free_cooling', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 12:
                        SendCommandTuya(DeviceID, 'free_cooling', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 13:
                        SendCommandTuya(DeviceID, 'powerful', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 13:
                        SendCommandTuya(DeviceID, 'powerful', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'fanlight':
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'fan_switch', False)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'fan_switch', True)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'fan_speed', int(mode[int(Level / 10)]))
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'fan_direction', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'powermeter' and searchCode('switch', function):
                    if Command == 'Off':
                        SendCommandTuya(DeviceID, 'switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandTuya(DeviceID, 'switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'powermeter' and searchCode('switch_1', function):
                    if Command == 'Off':
                        SendCommandTuya(DeviceID, 'switch_1', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandTuya(DeviceID, 'switch_1', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'siren':
                    if Command == 'Off':
                        SendCommandTuya(DeviceID, 'AlarmSwitch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandTuya(DeviceID, 'AlarmSwitch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    # Other Type of alarm with same code
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'muffling', False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'muffling', True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'alarm_state', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'alarm_volume', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)

                if dev_type == 'pirlight':
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'switch_pir', False)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'switch_pir', True)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'device_mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'pir_sensitivity', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'garagedooropener':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch_1', False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch_1', True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)

                if dev_type == 'feeder':
                    if Command == 'Off' and Unit == 5:
                        SendCommandTuya(DeviceID, 'light', False)
                        UpdateDomoticz(DeviceID, 5, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandTuya(DeviceID, 'light', True)
                        UpdateDomoticz(DeviceID, 5, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 1:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'manual_feed', int(mode[int(Level / 10)]))
                        UpdateDomoticz(DeviceID, 1, Level, 1, 0)

                if dev_type == 'irrigation':
                    if searchCode('switch_1', function):
                        switch = 'switch_1'
                    else:
                        switch = 'switch'
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, switch, False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, switch, True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    if Command == 'Off' and Unit == 3:
                        SendCommandTuya(DeviceID, 'areaone', False)
                        UpdateDomoticz(DeviceID, 3, False, 0, 0)
                    elif Command == 'On' and Unit == 3:
                        SendCommandTuya(DeviceID, 'areaone', True)
                        UpdateDomoticz(DeviceID, 3, True, 1, 0)
                    if Command == 'Off' and Unit == 4:
                        SendCommandTuya(DeviceID, 'areatwo', False)
                        UpdateDomoticz(DeviceID, 4, False, 0, 0)
                    elif Command == 'On' and Unit == 4:
                        SendCommandTuya(DeviceID, 'areatwo', True)
                        UpdateDomoticz(DeviceID, 4, True, 1, 0)
                    if Command == 'Off' and Unit == 5:
                        SendCommandTuya(DeviceID, 'areathree', False)
                        UpdateDomoticz(DeviceID, 5, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandTuya(DeviceID, 'areathree', True)
                        UpdateDomoticz(DeviceID, 5, True, 1, 0)
                    if Command == 'Off' and Unit == 6:
                        SendCommandTuya(DeviceID, 'areafour', False)
                        UpdateDomoticz(DeviceID, 6, False, 0, 0)
                    elif Command == 'On' and Unit == 6:
                        SendCommandTuya(DeviceID, 'areafour', True)
                        UpdateDomoticz(DeviceID, 6, True, 1, 0)
                    if Command == 'Off' and Unit == 7:
                        SendCommandTuya(DeviceID, 'areafive', False)
                        UpdateDomoticz(DeviceID, 7, False, 0, 0)
                    elif Command == 'On' and Unit == 7:
                        SendCommandTuya(DeviceID, 'areafive', True)
                        UpdateDomoticz(DeviceID, 7, True, 1, 0)
                    if Command == 'Off' and Unit == 8:
                        SendCommandTuya(DeviceID, 'areasix', False)
                        UpdateDomoticz(DeviceID, 8, False, 0, 0)
                    elif Command == 'On' and Unit == 8:
                        SendCommandTuya(DeviceID, 'areasix', True)
                        UpdateDomoticz(DeviceID, 8, True, 1, 0)

                if dev_type == 'starlight':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch_led', False)
                        SendCommandTuya(DeviceID, 'colour_switch', False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch_led', True)
                        SendCommandTuya(DeviceID, 'colour_switch', True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 1:
                        Color = Devices[DeviceID].Units[1].Color
                        if Color == '':
                            Color ={'b':255,'cw':0,'g':255,'m':3,'r':255,'t':0,'ww':0}
                        h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                        hvs = {'h':h, 's':s, 'v':Level * 10}
                        SendCommandTuya(DeviceID, 'colour_data', hvs)
                        SendCommandTuya(DeviceID, 'colour_switch', True)
                        UpdateDomoticz(DeviceID, 1, json.dumps(Color), 1, 0)
                    elif Command == 'Set Color' and Unit == 1: #
                        h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                        hvs = {'h':h, 's':s, 'v':Level * 10}
                        SendCommandTuya(DeviceID, 'colour_data', hvs)
                        SendCommandTuya(DeviceID, 'colour_switch', True)
                        UpdateDomoticz(DeviceID, 1, json.dumps(Color), 1, 0)
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'colour_switch', False)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'colour_switch', True)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    if Command == 'Off' and Unit == 3:
                        SendCommandTuya(DeviceID, 'laser_switch', False)
                        UpdateDomoticz(DeviceID, 3, False, 0, 0)
                    elif Command == 'On' and Unit == 3:
                        SendCommandTuya(DeviceID, 'laser_switch', True)
                        UpdateDomoticz(DeviceID, 3, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        SendCommandTuya(DeviceID, 'laser_switch', True)
                        SendCommandTuya(DeviceID, 'laser_bright', 21.25 + ((Level / 100) * 78.75)) # 21.25 + ((Level / 100) * 78.75) ) * 10
                        UpdateDomoticz(DeviceID, 3, True, 1, 0)
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    if Command == 'Off' and Unit == 4:
                        SendCommandTuya(DeviceID, 'fan_switch', False)
                        UpdateDomoticz(DeviceID, 4, False, 0, 0)
                    elif Command == 'On' and Unit == 4:
                        SendCommandTuya(DeviceID, 'fan_switch', True)
                        UpdateDomoticz(DeviceID, 4, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        SendCommandTuya(DeviceID, 'fan_switch', True)
                        SendCommandTuya(DeviceID, 'fan_speed', Level)
                        UpdateDomoticz(DeviceID, 4, True, 1, 0)
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'smartlock':
                    if searchCode('lock_motor_state', function):
                        if Command == 'Off' and Unit == 1:
                            SendCommandTuya(DeviceID, 'lock_motor_state', False)
                            UpdateDomoticz(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandTuya(DeviceID, 'lock_motor_state', True)
                            UpdateDomoticz(DeviceID, 1, 0, 1, 0)
                    elif searchCode('rtc_lock', function):
                        if Command == 'Off' and Unit == 1:
                            SendCommandTuya(DeviceID, 'rtc_lock', 0)
                            UpdateDomoticz(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandTuya(DeviceID, 'rtc_lock', 1)
                            UpdateDomoticz(DeviceID, 1, 0, 1, 0)
                    else:
                        if Command == 'Off' and Unit == 1:
                            SendCommandTuya(DeviceID, 'switch', False)
                            UpdateDomoticz(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandTuya(DeviceID, 'switch', True)
                            UpdateDomoticz(DeviceID, 1, 0, 1, 0)

                if dev_type == 'dehumidifier':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        if searchCode('dehumidify_set_value', function):
                            tdev = 'dehumidify_set_value'
                        elif searchCode('dehumidify_set_enum', function):
                            tdev = 'dehumidify_set_enum'
                        SendCommandTuya(DeviceID, tdev, Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'fan_speed_enum', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Off' and Unit == 9:
                        SendCommandTuya(DeviceID, 'child_lock', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 9:
                        SendCommandTuya(DeviceID, 'child_lock', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 10:
                        SendCommandTuya(DeviceID, 'anion', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 10:
                        SendCommandTuya(DeviceID, 'anion', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 11:
                        SendCommandTuya(DeviceID, 'filter_life', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 11:
                        SendCommandTuya(DeviceID, 'filter_life', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 13:
                        SendCommandTuya(DeviceID, 'runtime_total_reset', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 13:
                        SendCommandTuya(DeviceID, 'anruntime_total_resetion', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'vacuum':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'power_go', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'power_go', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'suction', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 5:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'cistern', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'purifier':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'speed', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'smartkettle':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'start', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'start', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 4:
                        SendCommandTuya(DeviceID, 'cook_temperature', Level)
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'mower':
                    if Command == 'Set Level' and Unit == 1:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'MachineControlCmd', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 1, Level, 1, 0)
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'MachineRainMode', False)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'MachineRainMode', True)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                    if Command == 'Set Level' and Unit == 6:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'MachineWorkMode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 6, Level, 1, 0)

                if dev_type == 'human_presence':
                    if Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'sensitivity', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit  == 3:
                        SendCommandTuya(DeviceID, 'near_detection', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit  == 4:
                        SendCommandTuya(DeviceID, 'far_detection', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'evcharger':
                    if searchCode('switch', function):
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, 'switch', False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, 'switch', True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'infrared_ac':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'PowerOff', 'PowerOff')
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'PowerOn', 'PowerOn')
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 2:
                        SendCommandTuya(DeviceID, 'T', Level)
                        UpdateDomoticz(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'M', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'F', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'siren':
                    if Command == 'Off':
                        SendCommandCloud(DeviceID, 'AlarmSwitch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandCloud(DeviceID, 'AlarmSwitch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 3, Level, 1, 0)
                    # Other Type of alarm with same code
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, 'muffling', False)
                        UpdateDevice(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, 'muffling', True)
                        UpdateDevice(DeviceID, 1, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'alarm_state', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'alarm_volume', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 3, Level, 1, 0)

                if dev_type == 'pirlight':
                    if Command == 'Off' and Unit == 2:
                        SendCommandCloud(DeviceID, 'switch_pir', False)
                        UpdateDevice(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandCloud(DeviceID, 'switch_pir', True)
                        UpdateDevice(DeviceID, 2, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'device_mode', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'pir_sensitivity', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 4, Level, 1, 0)

                if dev_type == 'garagedooropener':
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, 'switch_1', False)
                        UpdateDevice(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, 'switch_1', True)
                        UpdateDevice(DeviceID, 1, True, 1, 0)

                if dev_type == 'feeder':
                    if Command == 'Off' and Unit == 5:
                        SendCommandCloud(DeviceID, 'light', False)
                        UpdateDevice(DeviceID, 5, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandCloud(DeviceID, 'light', True)
                        UpdateDevice(DeviceID, 5, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 1:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'manual_feed', int(mode[int(Level / 10)]))
                        UpdateDevice(DeviceID, 1, Level, 1, 0)

                if dev_type == 'irrigation':
                    if searchCode('switch_1', function):
                        switch = 'switch_1'
                    else:
                        switch = 'switch'
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, switch, False)
                        UpdateDevice(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, switch, True)
                        UpdateDevice(DeviceID, 1, True, 1, 0)
                    if Command == 'Off' and Unit == 3:
                        SendCommandCloud(DeviceID, 'areaone', False)
                        UpdateDevice(DeviceID, 3, False, 0, 0)
                    elif Command == 'On' and Unit == 3:
                        SendCommandCloud(DeviceID, 'areaone', True)
                        UpdateDevice(DeviceID, 3, True, 1, 0)
                    if Command == 'Off' and Unit == 4:
                        SendCommandCloud(DeviceID, 'areatwo', False)
                        UpdateDevice(DeviceID, 4, False, 0, 0)
                    elif Command == 'On' and Unit == 4:
                        SendCommandCloud(DeviceID, 'areatwo', True)
                        UpdateDevice(DeviceID, 4, True, 1, 0)
                    if Command == 'Off' and Unit == 5:
                        SendCommandCloud(DeviceID, 'areathree', False)
                        UpdateDevice(DeviceID, 5, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandCloud(DeviceID, 'areathree', True)
                        UpdateDevice(DeviceID, 5, True, 1, 0)
                    if Command == 'Off' and Unit == 6:
                        SendCommandCloud(DeviceID, 'areafour', False)
                        UpdateDevice(DeviceID, 6, False, 0, 0)
                    elif Command == 'On' and Unit == 6:
                        SendCommandCloud(DeviceID, 'areafour', True)
                        UpdateDevice(DeviceID, 6, True, 1, 0)
                    if Command == 'Off' and Unit == 7:
                        SendCommandCloud(DeviceID, 'areafive', False)
                        UpdateDevice(DeviceID, 7, False, 0, 0)
                    elif Command == 'On' and Unit == 7:
                        SendCommandCloud(DeviceID, 'areafive', True)
                        UpdateDevice(DeviceID, 7, True, 1, 0)
                    if Command == 'Off' and Unit == 8:
                        SendCommandCloud(DeviceID, 'areasix', False)
                        UpdateDevice(DeviceID, 8, False, 0, 0)
                    elif Command == 'On' and Unit == 8:
                        SendCommandCloud(DeviceID, 'areasix', True)
                        UpdateDevice(DeviceID, 8, True, 1, 0)

                if dev_type == 'starlight':
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, 'switch_led', False)
                        SendCommandCloud(DeviceID, 'colour_switch', False)
                        UpdateDevice(DeviceID, 1, False, 0, 0)
                        UpdateDevice(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, 'switch_led', True)
                        SendCommandCloud(DeviceID, 'colour_switch', True)
                        UpdateDevice(DeviceID, 1, True, 1, 0)
                        UpdateDevice(DeviceID, 2, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 1:
                        Color = Devices[DeviceID].Units[1].Color
                        if Color == '': Color ={"b":255,"cw":0,"g":255,"m":3,"r":255,"t":0,"ww":0}
                        h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                        hvs = {'h':h, 's':s, 'v':Level * 10}
                        SendCommandCloud(DeviceID, 'colour_data', hvs)
                        SendCommandCloud(DeviceID, 'colour_switch', True)
                        UpdateDevice(DeviceID, 1, Color, 1, 0)
                    elif Command == 'Set Color' and Unit == 1: #
                        h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                        hvs = {'h':h, 's':s, 'v':Level * 10}
                        SendCommandCloud(DeviceID, 'colour_data', hvs)
                        SendCommandCloud(DeviceID, 'colour_switch', True)
                        UpdateDevice(DeviceID, 1, Color, 1, 0)
                    if Command == 'Off' and Unit == 2:
                        SendCommandCloud(DeviceID, 'colour_switch', False)
                        UpdateDevice(DeviceID, 2, False, 0, 0)
                        UpdateDevice(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandCloud(DeviceID, 'colour_switch', True)
                        UpdateDevice(DeviceID, 2, True, 1, 0)
                        UpdateDevice(DeviceID, 1, True, 1, 0)
                    if Command == 'Off' and Unit == 3:
                        SendCommandCloud(DeviceID, 'laser_switch', False)
                        UpdateDevice(DeviceID, 3, False, 0, 0)
                    elif Command == 'On' and Unit == 3:
                        SendCommandCloud(DeviceID, 'laser_switch', True)
                        UpdateDevice(DeviceID, 3, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        SendCommandCloud(DeviceID, 'laser_switch', True)
                        SendCommandCloud(DeviceID, 'laser_bright', 21.25 + ((Level / 100) * 78.75)) # 21.25 + ((Level / 100) * 78.75) ) * 10
                        UpdateDevice(DeviceID, 3, True, 1, 0)
                        UpdateDevice(DeviceID, 3, Level, 1, 0)
                    if Command == 'Off' and Unit == 4:
                        SendCommandCloud(DeviceID, 'fan_switch', False)
                        UpdateDevice(DeviceID, 4, False, 0, 0)
                    elif Command == 'On' and Unit == 4:
                        SendCommandCloud(DeviceID, 'fan_switch', True)
                        UpdateDevice(DeviceID, 4, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        SendCommandCloud(DeviceID, 'fan_switch', True)
                        SendCommandCloud(DeviceID, 'fan_speed', Level)
                        UpdateDevice(DeviceID, 4, True, 1, 0)
                        UpdateDevice(DeviceID, 4, Level, 1, 0)

                if dev_type == 'smartlock':
                    if searchCode('lock_motor_state', function):
                        if Command == 'Off' and Unit == 1:
                            SendCommandCloud(DeviceID, 'lock_motor_state', False)
                            UpdateDevice(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandCloud(DeviceID, 'lock_motor_state', True)
                            UpdateDevice(DeviceID, 1, 0, 1, 0)
                    elif searchCode('rtc_lock', function):
                        if Command == 'Off' and Unit == 1:
                            SendCommandCloud(DeviceID, 'rtc_lock', 0)
                            UpdateDevice(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandCloud(DeviceID, 'rtc_lock', 1)
                            UpdateDevice(DeviceID, 1, 0, 1, 0)
                    else:
                        if Command == 'Off' and Unit == 1:
                            SendCommandCloud(DeviceID, 'switch', False)
                            UpdateDevice(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandCloud(DeviceID, 'switch', True)
                            UpdateDevice(DeviceID, 1, 0, 1, 0)

                if dev_type == 'dehumidifier':
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, 'switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, 'switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        if searchCode('dehumidify_set_value', function):
                            tdev = 'dehumidify_set_value'
                        elif searchCode('dehumidify_set_enum', function):
                            tdev = 'dehumidify_set_enum'
                        SendCommandCloud(DeviceID, tdev, Level)
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'fan_speed_enum', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Off' and Unit == 9:
                        SendCommandCloud(DeviceID, 'child_lock', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 9:
                        SendCommandCloud(DeviceID, 'child_lock', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 10:
                        SendCommandCloud(DeviceID, 'anion', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 10:
                        SendCommandCloud(DeviceID, 'anion', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 11:
                        SendCommandCloud(DeviceID, 'anion', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 11:
                        SendCommandCloud(DeviceID, 'anion', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 13:
                        SendCommandCloud(DeviceID, 'anion', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 13:
                        SendCommandCloud(DeviceID, 'anion', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)

                if dev_type == 'vacuum':
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, 'power_go', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, 'power_go', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'suction', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 5:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'cistern', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'purifier':
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, 'switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, 'switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'speed', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'smartkettle':
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, 'start', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, 'start', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 4:
                        SendCommandCloud(DeviceID, 'cook_temperature', Level)
                        UpdateDevice(DeviceID, 4, Level, 1, 0)

                if dev_type == 'mower':
                    if Command == 'Set Level' and Unit == 1:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'MachineControlCmd', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 1, Level, 1, 0)
                    if Command == 'Off' and Unit == 2:
                        SendCommandCloud(DeviceID, 'MachineRainMode', False)
                        UpdateDevice(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandCloud(DeviceID, 'MachineRainMode', True)
                        UpdateDevice(DeviceID, 2, True, 1, 0)
                    if Command == 'Set Level' and Unit == 6:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'MachineWorkMode', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 6, Level, 1, 0)

                if dev_type == 'human_presence':
                    if Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'sensitivity', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit  == 3:
                        SendCommandCloud(DeviceID, 'near_detection', Level)
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit  == 4:
                        SendCommandCloud(DeviceID, 'far_detection', Level)
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'evcharger':
                    if searchCode('switch', function):
                        if Command == 'Off':
                            SendCommandCloud(DeviceID, 'switch', False)
                            UpdateDevice(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandCloud(DeviceID, 'switch', True)
                            UpdateDevice(DeviceID, Unit, True, 1, 0)

                if dev_type == 'infrared_ac':
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, 'PowerOff', 'PowerOff')
                        UpdateDevice(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, 'PowerOn', 'PowerOn')
                        UpdateDevice(DeviceID, 1, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 2:
                        SendCommandCloud(DeviceID, 'T', Level)
                        UpdateDevice(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'M', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'F', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 4, Level, 1, 0)

        except Exception as e:
            DomoticzEx.Error(f"onCommand ERROR: {str(e)}")
    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        DomoticzEx.Log(f"Notification: {Name}, {Subject}, {Text}, {Status}, {Priority}, {Sound}, {ImageFile}")

    def onDeviceRemoved(self, DeviceID, Unit):
        DomoticzEx.Log('onDeviceDeleted called')

    def onDisconnect(self, Connection):
        DomoticzEx.Log('onDisconnect called')

    def onHeartbeat(self):
        DomoticzEx.Debug('onHeartbeat called')
        if Devices:
            def _run_poll(do_cloud):
                if not _handle_lock.acquire(blocking=False):
                    DomoticzEx.Debug('onHeartbeat: poll already running, skipping this cycle')
                    return
                try:
                    onHandleThread(False, True)
                    if do_cloud:
                        onHandleThread(False, False)
                finally:
                    _handle_lock.release()

            do_cloud = (time.time() - last_update >= synctime and not fulllocal)
            DomoticzEx.Debug(f"Heartbeat check for sync {time.time() - last_update} >= {synctime} and fulllocal={fulllocal}")
            threading.Thread(target=_run_poll, args=(do_cloud,), daemon=True).start()

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onHandleThread(startup, local, target_dev_id=None):
    global tuya, devs, properties, dps_map, result, product_id, Error
    global last_update, last_ip_scan, localtuya, testdata
    global cloud_status_cache, cloud_status_time
    global FunctionProperties, StatusProperties, ResultValue, dev_type, line
    global synctime, ip_scan_interval

    try:
        # INIT (startup only)
        if startup and not local:
            DomoticzEx.Log('Initializing Tuya plugin')

            last_update = 0
            last_ip_scan = 0

            devs = []
            snap = []
            ResultValue = []
            properties = {}
            dps_map = {}
            result = {}
            localtuya = {}
            cloud_status_cache = {}
            cloud_status_time = {}
            online = True
            Error = None
            line = 0

            try:
                synctime = int(Parameters.get('Mode3') or 900)
            except (ValueError, TypeError):
                synctime = 900
            try:
                ip_scan_interval = int(Parameters.get('Mode4') or 86400)
            except (ValueError, TypeError):
                ip_scan_interval = 86400

            if not fulllocal:
                # Cloud init
                DomoticzEx.Log('Cloud mode: fetching device data from Tuya cloud')
                if 'tuya' not in globals():
                    try:
                        tuya = tinytuya.Cloud(
                            apiRegion=Parameters['Mode1'],
                            apiKey=Parameters['Username'],
                            apiSecret=Parameters['Password'],
                            apiDeviceID=Parameters['Mode2']
                        )
                    except Exception as e:
                        DomoticzEx.Error(f"Tuya initialization failed: {e}")
                        return

                # Stop script immediately if Tuya reports an error
                if hasattr(tuya, 'error') and tuya.error:
                    error_msg = tuya.error.get('Payload', tuya.error)
                    DomoticzEx.Error(f"Tuya API error: {error_msg}")
                    return

                tuya.use_old_device_list = True
                tuya.new_sign_algorithm = True

                # Fetch devices
                devs = None
                last_error = None
                for attempt in range(4):
                    try:
                        result_devs = tuya.getdevices()
                        # On failure tinytuya returns an error dict like
                        # {"Error": "...", "Err": "...", "Payload": ...}
                        # instead of raising, so detect and retry on that too.
                        if isinstance(result_devs, dict):
                            last_error = result_devs.get('Payload', result_devs.get('Error', result_devs))
                            DomoticzEx.Error(f"Tuya cloud returned an error (attempt {attempt + 1}/4), retrying... ({last_error})")
                            time.sleep(1)
                            continue
                        if result_devs:
                            devs = result_devs
                            break
                    except Exception as e:
                        last_error = e
                        DomoticzEx.Error(f"getdevices() raised an exception (attempt {attempt + 1}/4), retrying... ({e})")
                        time.sleep(1)

                if not devs:
                    raise Exception(f'No device data returned from Tuya cloud: {last_error}')

                DomoticzEx.Log(f'Successfully fetched {len(devs)} device(s) from Tuya cloud')
                for dev in devs:
                    DomoticzEx.Log(f"  - Device: {dev.get('name', 'Unknown')} (ID: {dev.get('id', 'Unknown')})")

                # Fetch schemas
                for dev in devs:
                    dev_id = dev.get('id')
                    dev_name = dev.get('name', 'Unknown')

                    try:
                        props = tuya.getproperties(dev_id).get('result', {})
                        props.setdefault('functions', [])
                        props.setdefault('status', [])
                        properties[dev_id] = props

                        result[dev_id] = tuya.getstatus(dev_id).get('result', {})

                        dps_map[dev_id] = {'by_code': {}, 'by_id': {}}
                        schema = tuya.getdps(dev_id)
                        if schema['success']:
                            for f in schema['result'].get('status', []):
                                dps_map[dev_id]['by_code'][f['code']] = f['dp_id']
                                dps_map[dev_id]['by_id'][f['dp_id']] = f['code']
                        DomoticzEx.Debug(f"Fetched properties for {dev_name} ({dev_id}): {len(properties.get(dev_id, {}).get('functions', []))} functions, {len(properties.get(dev_id, {}).get('status', []))} status items")
                    except Exception as e:
                        DomoticzEx.Error(f"Failed to fetch properties for {dev_name} ({dev_id}): {e}")
            elif fulllocal:
                DomoticzEx.Log('Full local mode: loading device data from files')
                with open(Parameters['HomeFolder'] + '/tuya-raw.json') as dFile:
                    raw = json.load(dFile)

                devs = raw.get('result', [])
                DomoticzEx.Debug(f"Loading {len(devs)} devices from tuya-raw.json")

                with open(Parameters['HomeFolder'] + '/snapshot.json') as eFile:
                    raw = json.load(eFile)
                snap = raw.get('devices', [])

                for dev in devs:
                    dev_id = dev['id']

                    if not dev.get('mapping'):
                        DomoticzEx.Error(f"!! Warning Mapping data is missing for {dev.get('name', 'Unknown')} ({dev_id}) !!")
                        continue

                    # ensure properties entry exists
                    properties.setdefault(dev_id, {'functions': [], 'status': []})
                    localtuya.setdefault(dev_id, {})

                    # fix mismatched fieldsproperties
                    dev['results'] = dev['status']
                    dev.pop('status', None)
                    dev['key'] = dev['local_key']
                    dev.pop('local_key', None)
                    for snap_dev in snap:
                        if snap_dev.get('id') == dev_id:
                            dev['ip'] = snap_dev.get('ip', dev.get('ip', '127.0.0.1'))
                            dev['version'] = snap_dev.get('ver', '3.3')
                            break
                    # mapping => functions/status
                    schema_list = []
                    for item in dev.get('mapping', {}).values():
                        raw_values = item.get('values', {})

                        if isinstance(raw_values, str):
                            # values is al JSON-string → eerst normaliseren
                            try:
                                raw_values = json.loads(raw_values)
                            except json.JSONDecodeError:
                                raw_values = {}

                        values_json = json.dumps(
                            raw_values,
                            ensure_ascii=False,
                            separators=(',', ':')
                        )

                        schema_list.append({
                            'code': item['code'],
                            'desc': values_json,
                            'name': '',
                            'type': item['type'],
                            'values': values_json
                        })
                    properties[dev_id] = dev

                    properties[dev_id]['functions'] = schema_list
                    properties[dev_id]['status'] = schema_list
                    dev['functions'] = schema_list
                    dev['status'] = schema_list

                    # DPS map (offline replacement for tuya.getdps)
                    dps_map[dev_id] = {'by_code': {}, 'by_id': {}}
                    for dp_id, item in dev.get('mapping', {}).items():
                        dp_id = int(dp_id)
                        code = item['code']
                        dps_map[dev_id]['by_code'][code] = dp_id
                        dps_map[dev_id]['by_id'][dp_id] = code

                    # remove unused fields
                    dev.pop('mapping', None)

                    # status values
                    result[dev_id] = dev['results']

                    localtuya[dev_id] = dev

                    # DomoticzEx.Debug(f"Convert {json.dumps(devs, indent=2)}")
                    # DomoticzEx.Debug(f"Localtuya {localtuya}")
                    # DomoticzEx.Debug(f"Loaded device {dev} from snapshot")
                    # DomoticzEx.Debug(f"Loaded device {dev_id} with properties {properties[dev_id]} and result {result[dev_id]}")

            # Active testdata loop
            if testdata:
                tuya = DomoticzEx.Log
                # Devices
                with open(Parameters['HomeFolder'] + '/debug_devices.json') as dFile:
                    devs = json.load(dFile)

                # Functies / status
                properties = {}

                with open(Parameters['HomeFolder'] + '/debug_functions.json') as fFile:
                    raw = json.load(fFile)

                for dev in devs:
                    dev_id = dev['id']
                    properties[dev_id] = raw['result']


                    if not properties[dev_id].get('functions'):
                        DomoticzEx.Error(f"!! Warning Functions data is missing for {dev.get('name', 'Unknown')} ({dev_id}) !!")

                    if not properties[dev_id].get('status'):
                        DomoticzEx.Error(f"!! Warning Status data is missing for {dev.get('name', 'Unknown')} ({dev_id}) !!")
            # Initial local scan
            if not testdata and not fulllocal:
                try:
                    DomoticzEx.Log('Initial Tuya IP scan, Please wait...')
                    localtuya = tinytuya.deviceScan(verbose=False, maxretry=None, byID=True)
                    last_ip_scan = time.time()
                    DomoticzEx.Log(f'Local IP scan completed: found {len(localtuya)} device(s) on local network')
                    for dev_id, dev_info in localtuya.items():
                        dev_name = next((d.get('name', 'Unknown') for d in devs if d.get('id') == dev_id), 'Unknown (not linked to this account)')
                        DomoticzEx.Log(f"  - Local device: {dev_name} ({dev_id}) at {dev_info.get('ip', 'unknown IP')}")
                except Exception as e:
                    DomoticzEx.Error(f"Local IP scan failed: {e}")
                    localtuya = {}

        # Periodic IP scan
        if (not startup and not testdata and ip_scan_interval > 0 and time.time() - last_ip_scan > ip_scan_interval) and not fulllocal :
            try:
                DomoticzEx.Log('Periodic Tuya IP scan, Please wait...')
                localtuya = tinytuya.deviceScan(verbose=False, maxretry=None, byID=True)
                last_ip_scan = time.time()
                DomoticzEx.Log(f'Periodic IP scan completed: found {len(localtuya)} device(s) on local network')
                for dev_id, dev_info in localtuya.items():
                    dev_name = next((d.get('name', 'Unknown') for d in devs if d.get('id') == dev_id), 'Unknown (not linked to this account)')
                    DomoticzEx.Log(f"  - Local device: {dev_name} ({dev_id}) at {dev_info.get('ip', 'unknown IP')}")
            except Exception as e:
                DomoticzEx.Error(f"Periodic IP scan failed: {e}")

        # Proactive ping loop for battery WiFi devices to wake them up
        if local and not testdata and not fulllocal:
            for dev in devs:
                dev_id = dev.get('id')
                if not dev_id:
                    continue

                # Check if WiFi device and has battery
                connect_type = dev.get('connect_type', 'wifi')
                protocol = dev.get('protocol', 'wifi')
                if 'zigbee' in str(connect_type).lower() or 'zigbee' in str(protocol).lower():
                    continue

                # Check battery status
                StatusProperties = properties.get(dev_id, {}).get('status', [])
                if not is_battery_device(StatusProperties):
                    continue

                # Try to ping battery device
                if dev_id in localtuya and localtuya[dev_id].get('ip', '') != '':
                    try:
                        DomoticzEx.Debug(f"Pinging battery device {dev.get('name', 'Unknown')} ({dev_id}) at {localtuya[dev_id].get('ip')}")
                        d = tinytuya.Device(
                            dev_id,
                            localtuya[dev_id].get('ip'),
                            dev.get('key', ''),
                            version=localtuya[dev_id].get('version', '3.3')
                        )
                        d.socketRetryLimit = 1
                        d.socketRetryDelay = 1
                        if hasattr(d, 'set_socketTimeout'):
                            d.set_socketTimeout(2)

                        # Send ping
                        ping_result = d.status()
                        if ping_result and isinstance(ping_result, dict) and 'dps' in ping_result:
                            DomoticzEx.Log(f"Battery device {dev.get('name', 'Unknown')} ({dev_id}) responded - woken up successfully")
                            # Update result cache with fresh status
                            if 'result' in str(ping_result) or 'dps' in ping_result:
                                result[dev_id] = ping_result
                        else:
                            DomoticzEx.Debug(f"Battery device {dev.get('name', 'Unknown')} ({dev_id}) no valid response")
                    except Exception as e:
                        DomoticzEx.Debug(f"Ping to battery device {dev.get('name', 'Unknown')} ({dev_id}) failed: {e}")

        # Main loop

        for dev in devs:
            # When triggered by a Pulsar push event, only process that one
            # device instead of the full device list -- everything below
            # this point is untouched, so the realtime path always agrees
            # exactly with the regular poll path.
            if target_dev_id and dev.get('id') != target_dev_id:
                continue

            # Zigbee filtering - only support WiFi devices
            connect_type = dev.get('connect_type', 'wifi')
            protocol = dev.get('protocol', 'wifi')
            if 'zigbee' in str(connect_type).lower() or 'zigbee' in str(protocol).lower():
                DomoticzEx.Error(f"!! Device '{dev.get('name', 'Unknown')}' ({dev.get('id', 'Unknown')}) is Zigbee - NOT SUPPORTED. Only WiFi devices are supported.")
                continue

            # Default values (offline-safe)
            t = 0
            StatusProperties   = properties.get(dev['id'], {}).get('status', [])
            FunctionProperties = properties.get(dev['id'], {}).get('functions', [])
            ResultValue        = result.get(dev['id'], [])
            product_id         = getConfigItem(dev['id'], 'product_id') or ''
            category           = properties.get(dev['id'], {}).get('category', 'unknown')
            dev_type           = DeviceType(category, product_id)
            dev_name           = dev.get('name', 'Unknown Device')
            dev_id             = dev.get('id', 'Unknown ID')
            online             = False
            now = time.time()

            if isinstance(StatusProperties, str):
                StatusProperties = json.loads(StatusProperties)
            if isinstance(FunctionProperties, str):
                FunctionProperties = json.loads(FunctionProperties)
            if isinstance(ResultValue, str):
                ResultValue = json.loads(ResultValue)

            # LOCAL FIRST
            try:
                if testdata:
                    DomoticzEx.Debug(f"Testdata mode: loading status for device {dev['name']} id {dev['id']}")
                    with open(Parameters['HomeFolder'] + '/debug_result.json') as rFile:
                        rData = json.load(rFile)
                        ResultValue = rData['result']
                        t = rData['t']
                    online = True
                elif local:
                    DomoticzEx.Debug(f"Attempting local connection to device {dev['name']} id {dev['id']}")
                    if dev_id in localtuya and localtuya[dev_id].get('ip', '') != '':
                        DomoticzEx.Debug(f"Local connection to device {dev['name']} id {dev['id']} using IP {localtuya[dev_id].get('ip', 'unknown')} and version {localtuya[dev_id].get('version', 'unknown')}")
                        d = tinytuya.Device(dev_id, localtuya[dev_id].get('ip'), dev['key'], version=localtuya.get(dev_id, {}).get('version', '3.3'))
                        d.socketRetryLimit = 1
                        d.socketRetryDelay = 1

                        d.detect_available_dps()
                        adps = d.detect_available_dps() # Two times for detection bulb devices
                        if adps:
                            status = d.status()
                            online = True

                            # ONLINE check
                            if (
                                not status
                                or 'Error' in status
                                or 'Err' in status
                                or 'dps' not in status
                            ):
                                online = False
                            else:
                                online = True
                            if 'dps' in status:
                                for dp_id, value in status['dps'].items():
                                    code = dps_map[dev_id]['by_id'].get(int(dp_id))

                                    if not code:
                                        if dp_id not in dps_map[dev_id]['by_id']:
                                            # DomoticzEx.Debug(f"[LOCAL] Ignoring unknown dp_id {dp_id}")
                                            dps_map[dev_id]['by_id'][int(dp_id)] = 'None'
                                            dps_map[dev_id]['by_code']['None'] = int(dp_id)
                                            continue

                                    if isinstance(ResultValue, str):
                                        try:
                                            ResultValue = json.loads(ResultValue)
                                        except json.JSONDecodeError:
                                            # DomoticzEx.Error("[LOCAL] ResultValue invalid JSON, resetting")
                                            ResultValue = []

                                    if not isinstance(ResultValue, list):
                                        # DomoticzEx.Error(f"[LOCAL] ResultValue unexpected type: {type(ResultValue)}")
                                        ResultValue = []

                                    # Search existing code
                                    item_found = False

                                    for item in ResultValue:
                                        if not isinstance(item, dict):
                                            continue

                                        if item.get('code') == code:
                                            item['value'] = value
                                            item_found = True
                                            break

                                    if not item_found:
                                        ResultValue.append({
                                            "code": code,
                                            "value": value
                                        })

                                    result[dev_id] = ResultValue
                                ResultValue = list(result.get(dev_id, []))

                        else:
                            DomoticzEx.Debug(f"[LOCAL] No DPS detected for device {dev['name']} id {dev['name']}, skipping local status fetch")
                            online = False

                elif ((not local and not startup) or (not fulllocal)):
                    last_update = time.time()
                    DomoticzEx.Debug(f"Cloud connection to device {dev['name']} id {dev['id']} synctime {now - cloud_status_time.get(dev_id, 0)}")
                    try:
                        cloud = tuya.getstatus(dev_id)
                        ResultValue = cloud.get('result', [])
                        online = True
                        cloud_status_time[dev_id] = now
                    except:
                        online = False
                else:
                    DomoticzEx.Debug(f"Skipping status fetch for device {dev['name']} id {dev['id']} in full local mode")
                    online = False

                # DomoticzEx.Debug(f"Device {dev["name"]} is online = {online}')
                # DomoticzEx.Debug(f"Device {dev["name"]} id {dev["id"]} FunctionProperties={properties[dev["id"]]["functions"]}')
                # DomoticzEx.Debug(f"Device {dev["name"]} id {dev["id"]} StatusProperties={properties[dev["id"]]["status"]}')
                # DomoticzEx.Debug(f"Device {dev["name"]} id {dev["id"]} ResultValue={result[dev["id"]]}')
                # DomoticzEx.Debug(f"Device {dev["name"]} id {dev["id"]} DPSMap={dps_map[dev_id]}')

            except Exception as err:
                # Device unreachable fallback
                ResultValue = []
                DomoticzEx.Error(f"Error line {sys.exc_info()[-1].tb_lineno}")
                DomoticzEx.Debug(f"handleThread: {err} line {sys.exc_info()[-1].tb_lineno}")

            # Create devices
            if startup:
                # if not Devices and ba:
                #     DomoticzEx.Log('Device data not initialized, skipping onHandleThread')
                #     return
                try:
                    deviceinfo = localtuya.get(dev_id, {'ip': '127.0.0.1', 'version': 'unknown'})
                    product_id = getConfigItem(dev_id, 'product_id') or ''
                    if dev_type in ('light', 'fanlight', 'pirlight') and createDevice(dev_id, 1):
                        main_subtype = 4  # Default subtype for RGBWW

                        if (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (searchCode('temp_value', StatusProperties) or searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                            DomoticzEx.Log('Create device Light RGBWW')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=4, Switchtype=7, Used=1).Create()
                            main_subtype = 4
                        elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and 'dc' == str(properties[dev_id]['category']) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)):
                            DomoticzEx.Log('Create device Light Stringlight')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=4, Switchtype=7, Used=1).Create()
                            main_subtype = 4
                        elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                            DomoticzEx.Log('Create device Light RGBW')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=1, Switchtype=7, Used=1).Create()
                            main_subtype = 1
                        elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                            DomoticzEx.Log('Create device Light RGB')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=2, Switchtype=7, Used=1).Create()
                            main_subtype = 2
                        elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (searchCode('temp_value', StatusProperties) or searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                            DomoticzEx.Log('Create device Light WWCW')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=8, Switchtype=7, Used=1).Create()
                            main_subtype = 8
                        elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                            DomoticzEx.Log('Create device Light Dimmer')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                            main_subtype = 3
                        elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (not searchCode('bright_value', StatusProperties) or not searchCode('bright_value_v2', StatusProperties)):
                            DomoticzEx.Log('Create device Light On/Off')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=7, Used=1).Create()
                            main_subtype = 73
                        elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)):
                            DomoticzEx.Log('Create device Light On/Off (Unknown Light Device)')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Unknown Light Device)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=7, Used=1).Create()
                            main_subtype = 73
                        # elif not (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)):
                        #     deleteDevice(dev_id,1)

                    # Multi-LED ondersteuning voor draw_tool (4Lights)
                    if searchCode('led_number_set', StatusProperties):
                        led_count = StatusDeviceTuya('led_number_set')

                        # Create or update devices for each LED
                        for i in range(1, led_count + 1):
                            # Calculate unit number (starting from 11 to avoid conflicts with main device at unit 1)
                            unit_number = 10 + i

                            # Check if device already exists
                            if createDevice(dev_id, unit_number):
                                # Create new device for this LED
                                DomoticzEx.Log(f'Create device LED {i} of {led_count}')

                                # Use same type/subtype as main device
                                if main_subtype == 73:  # On/Off type
                                    DomoticzEx.Unit(
                                        Name=f"{dev['name']} LED {i}",
                                        DeviceID=dev_id,
                                        Unit=unit_number,
                                        Type=244,
                                        Subtype=main_subtype,
                                        Switchtype=7,
                                        Used=1
                                    ).Create()
                                else:  # Light types (RGB, RGBW, etc.)
                                    DomoticzEx.Unit(
                                        Name=f"{dev['name']} LED {i}",
                                        DeviceID=dev_id,
                                        Unit=unit_number,
                                        Type=241,
                                        Subtype=main_subtype,
                                        Switchtype=7,
                                        Used=1
                                    ).Create()

                    if dev_type == 'dimmer':
                        if  createDevice(dev_id, 1) and searchCode('switch_led_1', FunctionProperties) and not searchCode('switch_led_2', FunctionProperties):
                            DomoticzEx.Log('Create device Dimmer')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                        # elif not createDevice(dev_id, 1) and not searchCode('switch_led_1', FunctionProperties) and not searchCode('switch_led_2', FunctionProperties):
                        #     deleteDevice(dev_id,1)
                        if searchCode('switch_led_2', FunctionProperties):
                            if createDevice(dev_id, 1):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Dimmer 1)", DeviceID=dev_id, Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                            # elif not createDevice(dev_id, 1) and not searchCode('switch_led_1', FunctionProperties):
                            #     deleteDevice(dev_id,1)
                            if createDevice(dev_id, 2):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Dimmer 2)", DeviceID=dev_id, Unit=2, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                            # elif not createDevice(dev_id, 2) and not searchCode('switch_led_2', FunctionProperties):
                            #     deleteDevice(dev_id,2)

                    if dev_type in ('switch', 'switch/sensor'):
                        if  createDevice(dev_id, 1) and (searchCode('switch_1', FunctionProperties) or searchCode('switch', FunctionProperties) or searchCode('switch_on', FunctionProperties)) and not searchCode('switch_2', FunctionProperties):
                            DomoticzEx.Log('Create device Switch')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if searchCode('switch_2', FunctionProperties):
                            DomoticzEx.Log('Create device Switch')
                            if createDevice(dev_id, 1):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Switch 1)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                            if createDevice(dev_id, 2):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Switch 2)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('switch_3', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 3)", DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('switch_4', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 4)", DeviceID=dev_id, Unit=4, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('switch_5', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 5)", DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('switch_6', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 6)", DeviceID=dev_id, Unit=6, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 7) and searchCode('switch_7', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 7)", DeviceID=dev_id, Unit=7, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 8) and searchCode('switch_8', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 8)", DeviceID=dev_id, Unit=8, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 9) and searchCode('switch_9', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 9)", DeviceID=dev_id, Unit=9, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 11) and ((searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'A') or searchCode('phase_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (A)", DeviceID=dev_id, Unit=11, Type=243, Subtype=23, Used=1).Create()
                        if createDevice(dev_id, 12) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (W)", DeviceID=dev_id, Unit=12, Type=248, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 13) and (searchCode('cur_voltage', StatusProperties) or searchCode('phase_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (V)", DeviceID=dev_id, Unit=13, Type=243, Subtype=8, Used=1).Create()
                        if createDevice(dev_id, 14) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (kWh)", DeviceID=dev_id, Unit=14, Type=243, Subtype=29, Used=1).Create()
                            #UpdateDomoticz(dev_id, 14, '0;0', 0, 0, 1)
                        if createDevice(dev_id, 15) and (searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'mA' or searchCode('leakage_current', StatusProperties)):
                            options = {}
                            options['Custom'] = '1;mA'
                            DomoticzEx.Unit(Name=f"{dev['name']} (mA)", DeviceID=dev_id, Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 16) and searchCode('temp_current', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=16, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 17) and (searchCode('out_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} outpower (W)", DeviceID=dev_id, Unit=17, Type=248, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 18) and (searchCode('out_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} outpower (kWh)", DeviceID=dev_id, Unit=18, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 19) and (searchCode('power_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} Reverse A(kWh)", DeviceID=dev_id, Unit=19, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 20) and (searchCode('power_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} Forward A(kWh)", DeviceID=dev_id, Unit=20, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 21) and (searchCode('power_b', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} Reverse B(kWh)", DeviceID=dev_id, Unit=21, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 22) and (searchCode('power_b', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} Forward B(kWh)", DeviceID=dev_id, Unit=22, Type=243, Subtype=29, Used=1).Create()

                    if dev_type == 'cover' and createDevice(dev_id, 1):
                        DomoticzEx.Log('Create device Cover')
                        if searchCode('position', StatusProperties) or searchCode('percent_control', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 1)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=21, Used=1).Create()
                        else:
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=14, Used=1).Create()
                        if searchCode('position_2', StatusProperties) or searchCode('percent_control_2', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch 2)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=21, Used=1).Create()

                    if dev_type == 'smartheatpump':
                        if createDevice(dev_id, 1) and searchCode('switch', FunctionProperties):
                            DomoticzEx.Log('Create device Smartheatpump')
                            DomoticzEx.Unit(Name=f"{dev['name']} (On/Off)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('intemp', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (INtemp)", DeviceID=dev_id, Unit=2, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('outtemp', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (OUTtemp)", DeviceID=dev_id, Unit=3, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('whjtemp', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (AMBtemp)", DeviceID=dev_id, Unit=4, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('cmptemp', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (COMPRtemp)", DeviceID=dev_id, Unit=5, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('wttemp', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (DHWtemp)", DeviceID=dev_id, Unit=6, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 7) and searchCode('hqtemp', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (rGAStemp)", DeviceID=dev_id, Unit=7, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 8) and searchCode('cmp_act_frep', StatusProperties):
                            options = {}
                            options['Custom'] = '1;Hz'
                            DomoticzEx.Unit(Name=f"{dev['name']} (COMPfrq)", DeviceID=dev_id, Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 9) and searchCode('cmp_cur', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (COMPRcur)", DeviceID=dev_id, Unit=9, Type=243, Subtype=23, Used=1).Create()
                        if createDevice(dev_id, 10) and searchCode('dc_fan_speed', StatusProperties):
                            options = {}
                            options['Custom'] = '1;Speed'
                            DomoticzEx.Unit(Name=f"{dev['name']} (FANspeed)", DeviceID=dev_id, Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 11) and searchCode('ach_stemp', StatusProperties):
                            for item in StatusProperties:
                                temp = 'ach_stemp'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (HEATtemp)", DeviceID=dev_id, Unit=11, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 12) and searchCode('wth_stemp', StatusProperties):
                            for item in StatusProperties:
                                temp = 'wth_stemp'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (DHWtemp)", DeviceID=dev_id, Unit=12, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 13) and searchCode('aircond_temp_diff', StatusProperties):
                            for item in StatusProperties:
                                temp = 'aircond_temp_diff'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (HE/COtemp-diff)", DeviceID=dev_id, Unit=13, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 14) and searchCode('wth_temp_diff', StatusProperties):
                            for item in StatusProperties:
                                temp = 'wth_temp_diff'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (DHWtemp-diff)", DeviceID=dev_id, Unit=14, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 15) and searchCode('acc_stemp', StatusProperties):
                            for item in StatusProperties:
                                temp = 'acc_stemp'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (ACCtemp)", DeviceID=dev_id, Unit=15, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 16) and searchCode('mode', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Mode)", DeviceID=dev_id, Unit=16, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 17) and searchCode('work_mode', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'work_mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (WorkMode)", DeviceID=dev_id, Unit=17, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if not(createDevice(dev_id, 18)):
                        # if createDevice(dev_id, 18) and searchCode('temp_current', StatusProperties):
                            # DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=18, Type=80, Subtype=5, Used=1).Create()
                            Devices[dev_id].Unit['18'].delete()
                        if createDevice(dev_id, 19) and searchCode('temp_set', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'temp_set'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Thermostat)", DeviceID=dev_id, Unit=19, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if not(createDevice(dev_id, 20)):
                        # if createDevice(dev_id, 20) and searchCode('water_set', FunctionProperties):
                            # for item in FunctionProperties:
                            #     temp = 'water_set'
                            #     if item['code'] == temp:
                            #         the_values = json.loads(item['values'])
                            #         options = {}
                            #         options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                            #         options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                            #         options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                            #         options['ValueUnit'] = the_values['unit']
                            # DomoticzEx.Unit(Name=dev['name'] + ' (Water Thermostat)', DeviceID=dev_id, Unit=20, Type=242, Subtype=1, Options=options, Used=1).Create()
                            Devices[dev_id].Unit['20'].delete()
                        if createDevice(dev_id, 21) and searchCode('temp_top', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temp Top)", DeviceID=dev_id, Unit=21, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 22) and searchCode('temp_bottom', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temp Bottom)", DeviceID=dev_id, Unit=22, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 23) and searchCode('switch', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Defrost)", DeviceID=dev_id, Unit=23, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 24) and searchCode('water_flow', StatusProperties):
                            options = {}
                            options['Custom'] = '1;L/Min'
                            DomoticzEx.Unit(Name=f"{dev['name']} (L/Min)", DeviceID=dev_id, Unit=24, Type=243, Subtype=31, Options=options, Used=1).Create()

                    if dev_type == 'thermostat' or dev_type == 'heater' or dev_type == 'heatpump':
                        temp = searchCode('temp_current', StatusProperties) or searchCode('upper_temp', StatusProperties) or searchCode('c_temperature', StatusProperties) or searchCode('TempCurrent', StatusProperties)
                        hum = searchCode('humidity_current', StatusProperties)
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log('Create device Thermostat/heater/heatpump')
                            if searchCode('switch', FunctionProperties) or searchCode('switch_1', FunctionProperties) or searchCode('Power', FunctionProperties) or searchCode('infared_switch', FunctionProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Power)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                            else:
                                DomoticzEx.Unit(Name=f"{dev['name']} (Power)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=0).Create()
                        if createDevice(dev_id, 2) and temp:
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=2, Type=80, Subtype=5, Used=0 if hum else 1).Create()
                        if createDevice(dev_id, 3) and (searchCode('set_temp', FunctionProperties) or searchCode('temp_set', FunctionProperties) or searchCode('temperature_c', FunctionProperties) or searchCode('TempSet', FunctionProperties) or searchCode('target_temp', FunctionProperties)):
                            if searchCode('temp_set', FunctionProperties):
                                temp = 'temp_set'
                            elif searchCode('set_temp', FunctionProperties):
                                temp = 'set_temp'
                            elif searchCode('temperature_c', FunctionProperties):
                                temp = 'temperature_c'
                            elif searchCode('TempSet', FunctionProperties):
                                temp = 'TempSet'
                            elif searchCode('target_temp', FunctionProperties):
                                temp = 'target_temp'
                            for item in StatusProperties:
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Thermostat)", DeviceID=dev_id, Unit=3, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 4) and (searchCode('mode', StatusProperties) or searchCode('Mode', StatusProperties)) and product_id != 'al8g1qdamyu5cfcc':
                            if dev_type == 'thermostat':
                                image = 16
                            elif dev_type == 'heater':
                                image = 15
                            else:
                                image = 7
                            for item in StatusProperties:
                                if searchCode('Mode', StatusProperties):
                                    mode = 'Mode'
                                else:
                                    mode = 'mode'
                                if item['code'] == mode:
                                    the_values = json.loads(item['values'])
                                    mode_list = []

                                    # Bepaal de off/standby modus
                                    if item['type'] == 'Bitmap':
                                        mode_list.extend(the_values['label'])
                                    else:
                                        mode_list.extend(the_values['range'])

                                    # Priority list for off/standby modes (from high to low priority)
                                    standby_options = ['standby', 'off', 'none', 'close', 'stop', 'idle', 'sleep', 'auto_off']

                                    # Determine the best off/standby mode
                                    standby_mode = 'off'  # Default fallback
                                    for option in standby_options:
                                        if option in mode_list:
                                            standby_mode = option
                                            break

                                    # Build the final list with standby/off mode first
                                    mode_final = [standby_mode]

                                    # Add the rest of the modes, but filter out 'standby' or 'off' if already present
                                    for mode_item in mode_list:
                                        if mode_item not in ['off', 'standby']:
                                            mode_final.append(mode_item)

                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode_final)
                                    setConfigItem(f"{dev_id}-4", {'mode': mode_final})
                                    options['SelectorStyle'] = '0' if len(mode_final) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Mode)", DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=image, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('window_check', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Window check)", DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('child_lock', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Child lock)", DeviceID=dev_id, Unit=6, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 7) and searchCode('eco', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Eco)", DeviceID=dev_id, Unit=7, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        # elif not createDevice(dev_id, 7) and not searchCode('Eco', FunctionProperties):
                        #     deleteDevice(dev_id,7)
                        if createDevice(dev_id, 8) and searchCode('temp_floor', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=8, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 9) and (searchCode('windspeed', StatusProperties) or searchCode('fan_level', StatusProperties) or searchCode('fan_speed_enum', StatusProperties)):
                            if searchCode('fan_level', StatusProperties):
                                wind = 'fan_level'
                            elif searchCode('fan_speed_enum', StatusProperties):
                                wind = 'fan_speed_enum'
                            else:
                                wind = 'windspeed'
                            for item in StatusProperties:
                                if item['code'] == wind:
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                    DomoticzEx.Unit(Name=f"{dev['name']} ({wind.capitalize().replace('_', ' ')})", DeviceID=dev_id, Unit=9, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 10) and hum:
                            DomoticzEx.Unit(Name=f"{dev['name']} (Humidity)", DeviceID=dev_id, Unit=10, Type=81, Subtype=1, Used=0).Create()
                        if createDevice(dev_id, 11) and ((searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'A') or searchCode('phase_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (A)", DeviceID=dev_id, Unit=11, Type=243, Subtype=23, Used=1).Create()
                        if createDevice(dev_id, 12) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties) or searchCode('average_power', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (W)", DeviceID=dev_id, Unit=12, Type=248, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 13) and (searchCode('cur_voltage', StatusProperties) or searchCode('phase_a', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (V)", DeviceID=dev_id, Unit=13, Type=243, Subtype=8, Used=1).Create()
                        if createDevice(dev_id, 14) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties) or searchCode('average_power', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (kWh)", DeviceID=dev_id, Unit=14, Type=243, Subtype=29, Used=1).Create()
                            #UpdateDomoticz(dev_id, 14, '0;0', 0, 0, 1)
                        if createDevice(dev_id, 15) and (searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'mA' or searchCode('leakage_current', StatusProperties)):
                            options = {}
                            options['Custom'] = '1;mA'
                            DomoticzEx.Unit(Name=f"{dev['name']} (mA)", DeviceID=dev_id, Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 16) and temp and hum:
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature + Humidity)", DeviceID=dev_id, Unit=16, Type=82, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 17) and searchCode('anti_bother', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Anti bother)", DeviceID=dev_id, Unit=17, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 18) and searchCode('fault', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fault)", DeviceID=dev_id, Unit=18, Type=243, Subtype=19, Image=13, Used=1).Create()

                    if dev_type in ('sensor', 'smartir', 'switch/sensor'):
                        temp = searchCode('va_temperature', StatusProperties) or searchCode('temp_current', StatusProperties) or searchCode('local_temp', StatusProperties) or searchCode('Tin', StatusProperties)
                        hum = searchCode('va_humidity', StatusProperties) or searchCode('humidity_value', StatusProperties) or searchCode('local_hum', StatusProperties) or searchCode('humidity', StatusProperties) or searchCode('Hin', StatusProperties)
                        if createDevice(dev_id, 1) and temp:
                            DomoticzEx.Log('Create Sensor device')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=1, Type=80, Subtype=5, Used=0 if hum else 1).Create()
                        if createDevice(dev_id, 2) and hum:
                            DomoticzEx.Unit(Name=f"{dev['name']} (Humidity)", DeviceID=dev_id, Unit=2, Type=81, Subtype=1, Used=0).Create()
                        if createDevice(dev_id, 3) and temp and hum:
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature + Humidity)", DeviceID=dev_id, Unit=3, Type=82, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('co2_value', StatusProperties):
                            options = {}
                            options['Custom'] = '1;ppm'
                            DomoticzEx.Unit(Name=f"{dev['name']} (CO2)", DeviceID=dev_id, Unit=4, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('air_quality_index', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Index)", DeviceID=dev_id, Unit=5, Type=243, Subtype=22, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('ch2o_value', StatusProperties):
                            options = {}
                            options['Custom'] = '1;mg/m3'
                            DomoticzEx.Unit(Name=f"{dev['name']} (CH2O)", DeviceID=dev_id, Unit=6, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 7) and searchCode('voc_value', StatusProperties):
                            options = {}
                            options['Custom'] = '1;mg/m3'
                            DomoticzEx.Unit(Name=f"{dev['name']} (VOC)", DeviceID=dev_id, Unit=7, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 8) and searchCode('pm25_value', StatusProperties):
                            options = {}
                            options['Custom'] = '1;µg/m3'
                            DomoticzEx.Unit(Name=f"{dev['name']} (PM2.5)", DeviceID=dev_id, Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 9) and searchCode('pm10', StatusProperties):
                            options = {}
                            options['Custom'] = '1;µg/m3'
                            DomoticzEx.Unit(Name=f"{dev['name']} (PM10)", DeviceID=dev_id, Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 10) and searchCode('bright_value', StatusProperties):
                            options = {}
                            options['Custom'] = '1;lux'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Lux)", DeviceID=dev_id, Unit=10, Type=243, Subtype=31, Options=options, Image=19, Used=1).Create()
                        if createDevice(dev_id, 11) and searchCode('switch', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Switch)", DeviceID=dev_id, Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 12) and searchCode('ph_current', StatusProperties):
                            options = {}
                            options['Custom'] = '1;pH'
                            DomoticzEx.Unit(Name=f"{dev['name']} (pH)", DeviceID=dev_id, Unit=12, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 13) and searchCode('pro_current', StatusProperties):
                            options = {}
                            options['Custom'] = '1;kPa'
                            DomoticzEx.Unit(Name=f"{dev['name']} (kPa)", DeviceID=dev_id, Unit=13, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 14) and searchCode('orp_current', StatusProperties):
                            options = {}
                            options['Custom'] = '1;ORP'
                            DomoticzEx.Unit(Name=f"{dev['name']} (ORP)", DeviceID=dev_id, Unit=14, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 15) and searchCode('ph_warn_min', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'ph_warn_min'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Min pH)", DeviceID=dev_id, Unit=15, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 16) and searchCode('ph_warn_max', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'ph_warn_max'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Max pH)", DeviceID=dev_id, Unit=16, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 17) and searchCode('pro_warn_min', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'pro_warn_min'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Min kPa)", DeviceID=dev_id, Unit=17, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 18) and searchCode('pro_warn_max', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'pro_warn_max'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Max kPa)", DeviceID=dev_id, Unit=18, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 19) and searchCode('orp_warn_min', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'orp_warn_min'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Min ORP)", DeviceID=dev_id, Unit=19, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 20) and searchCode('orp_warn_max', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'orp_warn_max'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Max ORP)", DeviceID=dev_id, Unit=20, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 21) and (searchCode('sub1_temp', StatusProperties) or searchCode('ToutCh1', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext1 (Temperature)", DeviceID=dev_id, Unit=21, Type=80, Subtype=5, Used=0).Create()
                        if createDevice(dev_id, 22) and (searchCode('sub1_hum', StatusProperties) or searchCode('HoutCh1', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext1 (Humidity)", DeviceID=dev_id, Unit=22, Type=81, Subtype=1, Used=0).Create()
                        if createDevice(dev_id, 23) and ((searchCode('sub1_temp', StatusProperties) and searchCode('sub1_hum', StatusProperties)) or (searchCode('ToutCh1', StatusProperties) and searchCode('HoutCh1', StatusProperties))):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext1 (Temperature + Humidity)", DeviceID=dev_id, Unit=23, Type=82, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 24) and searchCode('temp_warn_min', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'temp_warn_min'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Min Temp)", DeviceID=dev_id, Unit=24, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 25) and searchCode('temp_warn_max', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'temp_warn_max'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Max Temp)", DeviceID=dev_id, Unit=25, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 31) and (searchCode('sub2_temp', StatusProperties) or searchCode('ToutCh2', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext2 (Temperature)", DeviceID=dev_id, Unit=31, Type=80, Subtype=5, Used=0).Create()
                        if createDevice(dev_id, 32) and (searchCode('sub2_hum', StatusProperties) or searchCode('HoutCh2', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext2 (Humidity)", DeviceID=dev_id, Unit=32, Type=81, Subtype=1, Used=0).Create()
                        if createDevice(dev_id, 33) and ((searchCode('sub2_temp', StatusProperties) and searchCode('sub2_hum', StatusProperties)) or (searchCode('ToutCh2', StatusProperties) and searchCode('HoutCh2', StatusProperties))):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext2 (Temperature + Humidity)", DeviceID=dev_id, Unit=33, Type=82, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 41) and (searchCode('sub3_temp', StatusProperties) or searchCode('ToutCh3', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext3 (Temperature)", DeviceID=dev_id, Unit=41, Type=80, Subtype=5, Used=0).Create()
                        if createDevice(dev_id, 42) and (searchCode('sub3_hum', StatusProperties) or searchCode('HoutCh3', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext3 (Humidity)", DeviceID=dev_id, Unit=42, Type=81, Subtype=1, Used=0).Create()
                        if createDevice(dev_id, 43) and ((searchCode('sub3_temp', StatusProperties) and searchCode('sub3_hum', StatusProperties)) or (searchCode('ToutCh3', StatusProperties) and searchCode('HoutCh3', StatusProperties))):
                            DomoticzEx.Unit(Name=f"{dev['name']}_ext3 (Temperature + Humidity)", DeviceID=dev_id, Unit=43, Type=82, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 44) and searchCode('temp_current_2', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature 2)", DeviceID=dev_id, Unit=44, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 45) and searchCode('cook_temperature', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'cook_temperature'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Cook temperature)", DeviceID=dev_id, Unit=45, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 46) and searchCode('cook_temperature_2', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'cook_temperature_2'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Cook temperature 2)", DeviceID=dev_id, Unit=46, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 47) and searchCode('atmosphere', StatusProperties):
                            options = {}
                            options['Custom'] = '1;inHg'
                            DomoticzEx.Unit(Name=f"{dev['name']} (inHg)", DeviceID=dev_id, Unit=47, Type=243, Subtype=31, Options=options, Image=19, Used=1).Create()
                        if createDevice(dev_id, 48) and (searchCode('pir', StatusProperties) or searchCode('pir_state', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Pir)", DeviceID=dev_id, Unit=48, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 49) and searchCode('temper_alarm', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temper alarm)", DeviceID=dev_id, Unit=49, Type=244, Subtype=73, Switchtype=0, Image=13, Used=1).Create()
                        if createDevice(dev_id, 50) and searchCode('co_status', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'co_status':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (CO status)", DeviceID=dev_id, Unit=50, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                        if createDevice(dev_id, 51) and searchCode('checking_result', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'checking_result':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Checking result)", DeviceID=dev_id, Unit=51, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                        for channel in range(1, 8): # Unit 51, 54, 57, 60, 63, 66, 69
                            temp = searchCode(f"ch{channel}_temp", ResultValue)
                            hum = searchCode(f"ch{channel}_humi", ResultValue)
                            unit_base = 50 + (channel * 3)
                            current_temp = StatusDeviceTuya(f"ch{channel}_temp") if temp else None
                            current_hum = StatusDeviceTuya(f"ch{channel}_humi") if hum else None
                            temp_valid = temp and current_temp is not None and current_temp != -40
                            hum_valid = hum and current_hum is not None and current_hum != 0
                            if createDevice(dev_id, unit_base - 2) and temp_valid:
                                DomoticzEx.Log(f"Create Temperature Sensor device for channel {channel}")
                                DomoticzEx.Unit(Name=f"{dev['name']} (CH{channel} Temperature)", DeviceID=dev_id, Unit=unit_base - 2, Type=80, Subtype=5, Used=0 if hum_valid else 1).Create()
                            if createDevice(dev_id, unit_base - 1) and hum_valid:
                                DomoticzEx.Log(f"Create Humidity Sensor device for channel {channel}")
                                DomoticzEx.Unit(Name=f"{dev['name']} (CH{channel} Humidity)", DeviceID=dev_id, Unit=unit_base - 1, Type=81, Subtype=1, Used=0).Create()
                            if createDevice(dev_id, unit_base) and temp_valid and hum_valid:
                                DomoticzEx.Log(f"Create Combined Sensor device for channel {channel}")
                                DomoticzEx.Unit(Name=f"{dev['name']} (CH{channel} Temperature + Humidity)", DeviceID=dev_id, Unit=unit_base, Type=82, Subtype=5, Used=1).Create()
                        # if createDevice(dev_id, 47) and searchCode('alarm_switch', FunctionProperties):
                        #     DomoticzEx.Unit(Name=dev['name'] + ' (Alarm)', DeviceID=dev_id, Unit=47, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 72) and (searchCode('liquid_state', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (State)", DeviceID=dev['id'], Unit=72, Type=243, Subtype=22, Switchtype=0, Image=11, Used=1).Create()
                        if createDevice(dev['id'], 73) and (searchCode('liquid_level_percent', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Percent)", DeviceID=dev['id'], Unit=73, Type=243, Subtype=6, Switchtype=0, Image=11, Used=1).Create()
                        if createDevice(dev['id'], 74) and (searchCode('liquid_depth', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Depth)", DeviceID=dev['id'], Unit=74, Type=243, Subtype=27, Switchtype=0, Image=11, Used=1).Create()

                        if dev_type in ('smartir') and dev_id not in str(Devices):
                            DomoticzEx.Log(f"Infrared device: {dev['name']}")
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=0).Create()
                            UpdateDomoticz(dev_id, 1, 'Infrared devices are not yet able to be controlled by the plugin.', 0, 0)

                    if dev_type == 'doorbell':
                        if createDevice(dev['id'], 1) and searchCode('doorbell_active', StatusProperties):
                            DomoticzEx.Log('Create device Doorbell')
                            #DomoticzEx.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=1).Create()
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create() # Switchtype=1 is doorbell
                        if createDevice(dev['id'], 2) and searchCode('floodlight_switch', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Light switch)", DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 3) and searchCode('motion_switch', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Motion switch)", DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 4) and searchCode('basic_indicator', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Indicator)", DeviceID=dev['id'], Unit=4, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 5) and searchCode('decibel_switch', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Decibel)", DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 6) and searchCode('basic_private', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Private)", DeviceID=dev['id'], Unit=6, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 7) and searchCode('motion_tracking', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Motion tracking)", DeviceID=dev['id'], Unit=7, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 8) and searchCode('motion_area_switch', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Motion area switch)", DeviceID=dev['id'], Unit=8, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 9) and searchCode('siren_switch', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Siren)", DeviceID=dev['id'], Unit=9, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 10) and searchCode('nightvision_mode', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'nightvision_mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values.get('label'))
                                    else:
                                        mode.extend(the_values.get('range'))
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Night vision mode)", DeviceID=dev['id'], Unit=10, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 11) and searchCode('floodlight_switch', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Floodlight)", DeviceID=dev['id'], Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 12) and searchCode('ipc_siren_volume', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'ipc_siren_volume'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                    options['ValueUnit'] = the_values.get('unit')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Siren Volume)", DeviceID=dev['id'], Unit=12, Type=242, Subtype=1, Options=options, Image=8, Used=1).Create()
                        if createDevice(dev['id'], 13) and searchCode('ipc_siren_duration', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'ipc_siren_duration'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                    options['ValueUnit'] = the_values.get('unit')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Siren Duration)", DeviceID=dev['id'], Unit=13, Type=242, Subtype=1, Options=options, Image=21, Used=1).Create()


                    if dev_type == 'fan':
                        if createDevice(dev_id, 1) and searchCode('switch', FunctionProperties):
                            DomoticzEx.Log('Create device Fan')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('mode', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Mode)", DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('fan_speed', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'fan_speed':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values['min'],the_values['max'] + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fan Speed)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('temp_set', FunctionProperties):
                            for item in FunctionProperties:
                                temp = 'temp_set'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Thermostat)", DeviceID=dev_id, Unit=4, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('temp_current', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=5, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('fault', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fault)", DeviceID=dev_id, Unit=6, Type=243, Subtype=19, Image=13, Used=1).Create()
                        if createDevice(dev_id, 7) and searchCode('light', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Light)", DeviceID=dev_id, Unit=7, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                        if createDevice(dev_id, 8) and searchCode('switch', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (RH Switch)", DeviceID=dev_id, Unit=8, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                        if createDevice(dev_id, 9) and (searchCode('RH_threshold', StatusProperties)):
                            options = {}
                            options['Custom'] = '1;RH'
                            DomoticzEx.Unit(Name=f"{dev['name']} (RH Threshold)", DeviceID=dev_id, Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 10) and (searchCode('RH_value', StatusProperties)):
                            options = {}
                            options['Custom'] = '1;RH'
                            DomoticzEx.Unit(Name=f"{dev['name']} (RH Value)", DeviceID=dev_id, Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 11) and searchCode('anion', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Anion)", DeviceID=dev_id, Unit=11, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                        if createDevice(dev_id, 12) and searchCode('anion', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Free Cooling)", DeviceID=dev_id, Unit=12, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                        if createDevice(dev_id, 13) and searchCode('anion', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Powerful)", DeviceID=dev_id, Unit=13, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()

                    if dev_type == 'fanlight':
                        if createDevice(dev_id, 2) and searchCode('fan_switch', FunctionProperties):
                            DomoticzEx.Log('Create device Fanlight')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fan Power)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('fan_speed', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'fan_speed':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values['min'],the_values['max'] + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fan Speed)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('fan_direction', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'fan_direction':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fan Direction)", DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()

                    if dev_type == 'siren':
                        if createDevice(dev_id, 1) and searchCode('AlarmSwitch', FunctionProperties):
                            DomoticzEx.Log('Create device Siren')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=13, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('Alarmtype', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'Alarmtype':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Alarmtype)", DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=8, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('AlarmPeriod', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'AlarmPeriod':
                                    the_values = json.loads(item['values'])
                                    mode = []
                                    for num in range(the_values['min'],the_values['max'] + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'false'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (AlarmPeriod)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        # Other type of alarm with same code
                        if createDevice(dev_id, 1) and searchCode('muffling', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Muffling)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=8, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('alarm_state', FunctionProperties):
                            DomoticzEx.Log('Create device Siren')
                            for item in FunctionProperties:
                                if item['code'] == 'alarm_state':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (State)", DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('alarm_volume', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'alarm_volume':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Volume)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=8, Used=1).Create()

                    if dev_type == 'powermeter' and searchCode('Current', StatusProperties):
                        if createDevice(dev_id, 1) :
                            DomoticzEx.Log('Create Powermeter')
                            DomoticzEx.Unit(Name=f"{dev['name']} (3P A)", DeviceID=dev_id, Unit=1, Type=89, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('Current', StatusProperties):
                            options = {}
                            options['Custom'] = '1;Hz'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Hz)", DeviceID=dev_id, Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('Temperature', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=3, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('Current', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (A)", DeviceID=dev_id, Unit=4, Type=243, Subtype=23, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('ActivePower', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (kWh)", DeviceID=dev_id, Unit=5, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 11) and searchCode('ActivePowerA', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} L1 (V)", DeviceID=dev_id, Unit=11, Type=243, Subtype=8, Used=1).Create()
                        if createDevice(dev_id, 12) and searchCode('ActivePowerA', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} L1 (kWh)", DeviceID=dev_id, Unit=12, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 21) and searchCode('ActivePowerB', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} L2 (V)", DeviceID=dev_id, Unit=21, Type=243, Subtype=8, Used=1).Create()
                        if createDevice(dev_id, 22) and searchCode('ActivePowerB', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} L2 (kWh)", DeviceID=dev_id, Unit=22, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 31) and searchCode('ActivePowerC', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} L3 (V)", DeviceID=dev_id, Unit=31, Type=243, Subtype=8, Used=1).Create()
                        if createDevice(dev_id, 32) and searchCode('ActivePowerC', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} L3 (kWh)", DeviceID=dev_id, Unit=32, Type=243, Subtype=29, Used=1).Create()

                    if dev_type == 'powermeter' and searchCode('phase_a', StatusProperties):
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log('Create Powermeter')
                            DomoticzEx.Unit(Name=f"{dev['name']} (A)", DeviceID=dev_id, Unit=1, Type=243, Subtype=23, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('phase_a', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (W)", DeviceID=dev_id, Unit=2, Type=248, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('phase_a', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (V)", DeviceID=dev_id, Unit=3, Type=243, Subtype=8, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('phase_a', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (kWh)", DeviceID=dev_id, Unit=4, Type=243, Subtype=29, Used=1).Create()
                        if  createDevice(dev_id, 5) and searchCode('switch', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('fault', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fault)", DeviceID=dev_id, Unit=6, Type=243, Subtype=19, Image=13, Used=1).Create()

                    if dev_type == 'powermeter' and (searchCode('direction_a', StatusProperties) or searchCode('power_direction_a', StatusProperties)):
                        if createDevice(dev_id, 1) and (searchCode('voltage_a', StatusProperties) or searchCode('f_ac_v', StatusProperties)):
                            DomoticzEx.Log('Create Powermeter')
                            DomoticzEx.Unit(Name=f"{dev['name']} (V)", DeviceID=dev_id, Unit=1, Type=243, Subtype=8, Used=1).Create()
                        if createDevice(dev_id, 2) and (searchCode('freq', StatusProperties) or searchCode('f_ac_line_freq', StatusProperties)):
                            options = {}
                            options['Custom'] = '1;Hz'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Hz)", DeviceID=dev_id, Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('total_power', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} Total (W)", DeviceID=dev_id, Unit=3, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 11) and searchCode('power_a', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} A (W)", DeviceID=dev_id, Unit=11, Type=248, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 12) and searchCode('current_a', StatusProperties):
                            options = {}
                            options['Custom'] = '1;mA'
                            DomoticzEx.Unit(Name=f"{dev['name']} A (mA)", DeviceID=dev_id, Unit=12, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 13) and searchCode('direction_a', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} A (Direction)", DeviceID=dev_id, Unit=13, Type=243, Subtype=19, Used=1).Create()
                        if createDevice(dev_id, 14) and (searchCode('energy_forword_a', StatusProperties) or searchCode('forward_energy_a', StatusProperties)):
                            # DomoticzEx.Unit(Name=dev['name'] + ' A Forward (kWh)', DeviceID=dev_id, Unit=14, Type=243, Subtype=29, Used=1).Create()
                            options = {}
                            options['Custom'] = '1;kWh'
                            DomoticzEx.Unit(Name=f"{dev['name']} A Forward (kWh)", DeviceID=dev_id, Unit=14, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 15) and (searchCode('energy_reverse_a', StatusProperties) or searchCode('reverse_energy_a', StatusProperties)):
                            # DomoticzEx.Unit(Name=dev['name'] + ' A Reverse (kWh)', DeviceID=dev_id, Unit=15, Type=243, Subtype=29, Used=1).Create()
                            options = {}
                            options['Custom'] = '1;kWh'
                            DomoticzEx.Unit(Name=f"{dev['name']} A Reverse (kWh)", DeviceID=dev_id, Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 21) and searchCode('power_b', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} B (W)", DeviceID=dev_id, Unit=21, Type=248, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 22) and searchCode('current_b', StatusProperties):
                            options = {}
                            options['Custom'] = '1;mA'
                            DomoticzEx.Unit(Name=f"{dev['name']} B (mA)", DeviceID=dev_id, Unit=22, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 23) and searchCode('direction_b', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} B (Direction)", DeviceID=dev_id, Unit=23, Type=243, Subtype=19, Used=1).Create()
                        if createDevice(dev_id, 24) and (searchCode('energy_forword_b', StatusProperties) or searchCode('forward_energy_b', StatusProperties)):
                            # DomoticzEx.Unit(Name=dev['name'] + ' B Forward (kWh)', DeviceID=dev_id, Unit=24, Type=243, Subtype=29, Used=1).Create()
                            options = {}
                            options['Custom'] = '1;kWh'
                            DomoticzEx.Unit(Name=f"{dev['name']} B Forward (kWh)", DeviceID=dev_id, Unit=24, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 25) and (searchCode('energy_reverse_b', StatusProperties) or searchCode('reverse_energy_b', StatusProperties)):
                            # DomoticzEx.Unit(Name=dev['name'] + ' B Reverse (kWh)', DeviceID=dev_id, Unit=25, Type=243, Subtype=29, Used=1).Create()
                            options = {}
                            options['Custom'] = '1;kWh'
                            DomoticzEx.Unit(Name=f"{dev['name']} B Reverse (kWh)", DeviceID=dev_id, Unit=25, Type=243, Subtype=31, Options=options, Used=1).Create()

                    if dev_type == 'powermeter' and (searchCode('switch_1', StatusProperties) or searchCode('switch', StatusProperties)) and not searchCode('phase_a', StatusProperties):
                        if  createDevice(dev_id, 1) and (searchCode('switch_1', StatusProperties) or searchCode('switch', StatusProperties)):
                            DomoticzEx.Log('Create Powermeter')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('cur_current', StatusProperties):
                            options = {}
                            options['Custom'] = '1;mA'
                            DomoticzEx.Unit(Name=f"{dev['name']} (mA)", DeviceID=dev_id, Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('cur_power', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (kWh)", DeviceID=dev_id, Unit=3, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('cur_voltage', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (V)", DeviceID=dev_id, Unit=4, Type=243, Subtype=8, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('fault', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fault)", DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()

                    if dev_type == 'gateway':
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log('Create device Gateway')
                            if searchCode('master_state', StatusProperties):
                                DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=1).Create()
                            else:
                                DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=0).Create()

                    if dev_type == 'doorcontact':
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log('Create device Doorcontact')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                    if dev_type == 'pirlight':
                        if createDevice(dev_id, 2) and searchCode('switch_pir', FunctionProperties):
                            DomoticzEx.Log('Create device Pirlight')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Pir State)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=8, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('device_mode', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'device_mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Mode)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('pir_sensitivity', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'pir_sensitivity':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Sensitivity)", DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                    if dev_type == 'smokedetector':
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log('Create device Smokedetector')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=5, Used=1).Create()
                            DomoticzEx.Unit(Name=f"{dev['name']} (Alarm)", DeviceID=dev_id, Unit=2, Type=243, Subtype=19, Used=1).Create()

                    if dev_type == 'garagedooropener':
                        if createDevice(dev_id, 1) and searchCode('switch_1', FunctionProperties):
                            DomoticzEx.Log('Create device Garage door opener')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=5, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('doorcontact_state', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Contact state)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('door_control_1', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (State)", DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                    if dev_type == 'feeder':
                        if createDevice(dev_id, 1) and searchCode('manual_feed', FunctionProperties):
                            DomoticzEx.Log('Create device Feeder')
                            for item in FunctionProperties:
                                if item['code'] == 'manual_feed':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values['min'],the_values['max'] + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Manual)", DeviceID=dev_id, Unit=1, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('feed_state', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'feed_state':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Status)", DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('feed_report', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'feed_report':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values['min'],the_values['max'] + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Report)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('light', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Light)", DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Used=1).Create()

                    if dev_type == 'waterleak':
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log('Create device water leak sesor')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=22, Switchtype=0, Image=11, Used=1).Create()

                    if dev_type == 'presence':
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log('Create device PIR sensor')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Used=1).Create()

                    if dev_type == 'irrigation':
                        if createDevice(dev_id, 1) and (searchCode('switch', FunctionProperties) or searchCode('switch_1', FunctionProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Power)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('work_state', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'work_state':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Status)", DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=22, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('areaone', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Area One)", DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('areatwo', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Area Two)", DeviceID=dev_id, Unit=4, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('areathree', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Area Three)", DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('areafour', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Area Four)", DeviceID=dev_id, Unit=6, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                        if createDevice(dev_id, 7) and searchCode('areafive', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Area Five)", DeviceID=dev_id, Unit=7, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                        if createDevice(dev_id, 8) and searchCode('areasix', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Area Six)", DeviceID=dev_id, Unit=8, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()

                    if dev_type == 'wswitch':
                        # if createDevice(dev_id, 1) and searchCode('switch1_value', StatusProperties):
                        #     DomoticzEx.Unit(Name=dev['name'] + ' single click (Switch 1)', DeviceID=dev_id, Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        #     DomoticzEx.Unit(Name=dev['name'] + ' double click (Switch 1)', DeviceID=dev_id, Unit=12, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        #     DomoticzEx.Unit(Name=dev['name'] + ' long press (Switch 1)', DeviceID=dev_id, Unit=13, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        for x in range(1, 10):
                            if createDevice(dev_id, x) and searchCode(f"switch{x}_value", StatusProperties):
                                for item in StatusProperties:
                                    if item['code'] == f"switch{x}_value":
                                        the_values = json.loads(item['values'])
                                        mode = ['off']
                                        if item['type'] == 'Bitmap':
                                            mode.extend(the_values['label'])
                                        else:
                                            mode.extend(the_values['range'])
                                        options = {}
                                        options['LevelOffHidden'] = 'true'
                                        options['LevelActions'] = ''
                                        options['LevelNames'] = '|'.join(mode)
                                        options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                DomoticzEx.Unit(Name=f"{dev['name']} (Switch {x})", DeviceID=dev_id, Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                            if createDevice(dev_id, x) and searchCode(f"switch_type_{x}", StatusProperties):
                                for item in StatusProperties:
                                    if item['code'] == f"switch_type_{x}":
                                        the_values = json.loads(item['values'])
                                        mode = ['off']
                                        if item['type'] == 'Bitmap':
                                            mode.extend(the_values['label'])
                                        else:
                                            mode.extend(the_values['range'])
                                        options = {}
                                        options['LevelOffHidden'] = 'true'
                                        options['LevelActions'] = ''
                                        options['LevelNames'] = '|'.join(mode)
                                        options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                DomoticzEx.Unit(Name=f"{dev['name']} (Switch {x})", DeviceID=dev_id, Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                            if createDevice(dev_id, x) and searchCode(f"switch_mode{x}", StatusProperties):
                                for item in StatusProperties:
                                    if item['code'] == f"switch_mode{x}":
                                        the_values = json.loads(item['values'])
                                        mode = ['off']
                                        if item['type'] == 'Bitmap':
                                            mode.extend(the_values['label'])
                                        else:
                                            mode.extend(the_values['range'])
                                        options = {}
                                        options['LevelOffHidden'] = 'true'
                                        options['LevelActions'] = ''
                                        options['LevelNames'] = '|'.join(mode)
                                        options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                DomoticzEx.Unit(Name=f"{dev['name']} (Switch {x})", DeviceID=dev_id, Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                    if dev_type == 'starlight':
                        if createDevice(dev_id, 1) and searchCode('switch_led', FunctionProperties):
                            DomoticzEx.Log('Create device Starlight')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=2, Switchtype=7, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('colour_switch', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Colour)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('laser_switch', FunctionProperties) and searchCode('laser_bright', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Laser)", DeviceID=dev_id, Unit=3, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('fan_switch', FunctionProperties) and searchCode('fan_speed', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fan)", DeviceID=dev_id, Unit=4, Type=241, Subtype=3, Switchtype=7, Image=7, Used=1).Create()

                    if dev_type == 'smartlock':
                        if createDevice(dev_id, 1) and (searchCode('lock_motor_state', StatusProperties) or searchCode('rtc_lock', StatusProperties)):
                            DomoticzEx.Log('Create device smart lock')
                            DomoticzEx.Unit(Name=f"{dev['name']} (State)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        # if createDevice(dev_id, 3):
                        #     DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=19, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('alarm_lock', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'alarm_lock':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Status)", DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=13, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('unlock_ble', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (unlock ble)", DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('unlock_card', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (unlock card)", DeviceID=dev_id, Unit=4, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                    if dev_type == 'dehumidifier':
                        if createDevice(dev_id, 1) and searchCode('switch', FunctionProperties):
                            DomoticzEx.Log('Create device Dehumidifier')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and (searchCode('dehumidify_set_value', FunctionProperties) or searchCode('dehumidify_set_enum', FunctionProperties)):
                            if searchCode('dehumidify_set_value', FunctionProperties):
                                for item in FunctionProperties:
                                    if item['code'] == 'dehumidify_set_value':
                                        the_values = json.loads(item['values'])
                                        options = {'ValueStep':the_values['step'], 'ValueMin':the_values['min'], 'ValueMax':the_values['max'], 'ValueUnit':'%'}
                                DomoticzEx.Unit(Name=f"{dev['name']} (dehumidify)", DeviceID=dev_id, Unit=2, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                            elif searchCode('dehumidify_set_enum', FunctionProperties):
                                for item in FunctionProperties:
                                    if item['code'] == 'dehumidify_set_enum':
                                        the_values = json.loads(item['values'])
                                        options = {'ValueStep':the_values['step'], 'ValueMin':the_values['min'], 'ValueMax':the_values['max'], 'ValueUnit':'%'}
                                DomoticzEx.Unit(Name=f"{dev['name']} (dehumidify)", DeviceID=dev_id, Unit=2, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('fan_speed_enum', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'fan_speed_enum':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (fan speed)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('mode', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                    DomoticzEx.Unit(Name=f"{dev['name']} (Fan)", DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('fault', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Fault)", DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()
                        if createDevice(dev_id, 6) and (searchCode('temp_indoor', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=6, Type=80, Subtype=5, Used=0).Create()
                        if createDevice(dev_id, 7) and (searchCode('humidity_indoor', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Humidity)", DeviceID=dev_id, Unit=7, Type=81, Subtype=1, Used=0).Create()
                        if createDevice(dev_id, 8) and ((searchCode('temp_indoor', StatusProperties) and searchCode('humidity_indoor', StatusProperties))):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature + Humidity)", DeviceID=dev_id, Unit=8, Type=82, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 9) and searchCode('child_lock', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Child lock)", DeviceID=dev_id, Unit=9, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 10) and searchCode('switch', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Anion)", DeviceID=dev_id, Unit=10, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 11) and searchCode('filter_reset', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Filter reset)", DeviceID=dev_id, Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 12) and searchCode('filter_life', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Filter life)", DeviceID=dev_id, Unit=12, Type=243, Subtype=6, Used=1).Create()
                        if createDevice(dev_id, 13) and searchCode('runtime_total_reset', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Runtime total Reset)", DeviceID=dev_id, Unit=13, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 14) and searchCode('type_of_equipment', StatusProperties):
                            options = {}
                            options['Custom'] = '1;Hour'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Runtime)", DeviceID=dev_id, Unit=14, Type=243, Subtype=31, Options=options, Used=1).Create()

                    if dev_type == 'infrared_ac':
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log('Create device Infrared AC')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Power)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('temp', StatusProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Thermostat)", DeviceID=dev_id, Unit=2, Type=242, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('mode', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values['min'],the_values['max'] + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                    DomoticzEx.Unit(Name=f"{dev['name']} (Mode)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('wind', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'wind':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values['min'],the_values['max'] + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                    DomoticzEx.Unit(Name=f"{dev['name']} (Fan)", DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('anion', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (anion)", DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 6) and (searchCode('temp_indoor', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=6, Type=80, Subtype=5, Used=0).Create()
                        if createDevice(dev_id, 7) and (searchCode('humidity_indoor', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Humidity)", DeviceID=dev_id, Unit=7, Type=81, Subtype=1, Used=0).Create()
                        if createDevice(dev_id, 8) and ((searchCode('temp_indoor', StatusProperties) and searchCode('humidity_indoor', StatusProperties))):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature + Humidity)", DeviceID=dev_id, Unit=8, Type=82, Subtype=5, Used=1).Create()

                    if dev_type == 'vacuum':
                        if createDevice(dev_id, 1) and searchCode('power_go', FunctionProperties):
                            DomoticzEx.Log('Create device Robot vacuum')
                            DomoticzEx.Unit(Name=f"{dev['name']} Running", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('switch_charge', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Charge)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('mode', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Mode)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create() #Image=7,
                        if createDevice(dev_id, 4) and searchCode('suction', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'suction':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Suction)", DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('cistern', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'cistern':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Cistern)", DeviceID=dev_id, Unit=5, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('status', StatusProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Status)", DeviceID=dev_id, Unit=6, Type=243, Subtype=19, Used=1).Create()
                        if createDevice(dev_id, 7) and searchCode('electricity_left', StatusProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Electricity left)", DeviceID=dev_id, Unit=7, Type=243, Subtype=6, Used=1).Create()
                        if createDevice(dev_id, 8) and searchCode('edge_brush', StatusProperties):
                            options = {}
                            options['Custom'] = '1;Hour'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Edge brush))", DeviceID=dev_id, Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 9) and searchCode('roll_brush', StatusProperties):
                            options = {}
                            options['Custom'] = '1;Hour'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Roll brush))", DeviceID=dev_id, Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 10) and searchCode('filter', StatusProperties):
                            options = {}
                            options['Custom'] = '1;Hour'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Filter))", DeviceID=dev_id, Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 11) and searchCode('fault', StatusProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Fault)", DeviceID=dev_id, Unit=11, Type=243, Subtype=19, Image=13, Used=1).Create()

                    if dev_type == 'multifunctionalarm':
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log(f"Multifunction alarm: {dev['name']}")
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=0).Create()
                            UpdateDomoticz(dev_id, 1, 'update wait', 0, 0)

                    if dev_type == 'purifier':
                        if createDevice(dev_id, 1) and searchCode('switch', FunctionProperties):
                            DomoticzEx.Log('Create purifier device')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('pm25', StatusProperties):
                            options = {}
                            options['Custom'] = '1;µg/m3'
                            DomoticzEx.Unit(Name=f"{dev['name']} (PM2.5)", DeviceID=dev_id, Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('mode', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (mode)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('speed', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'speed':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (speed)", DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('filter', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Filter)", DeviceID=dev_id, Unit=5, Type=243, Subtype=6, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('air_quality', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Index)", DeviceID=dev_id, Unit=6, Type=243, Subtype=19, Used=1).Create()

                    if dev_type == 'smartkettle':
                        if createDevice(dev_id, 1) and searchCode('start', StatusProperties):
                            DomoticzEx.Log('Create device Smart Kettle')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Start)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('status', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'status':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = 0
                            DomoticzEx.Unit(Name=f"{dev['name']} (Status)", DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                        if createDevice(dev_id, 3) and (searchCode('temperature', StatusProperties)):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=3, Type=80, Subtype=5, Used=0).Create()
                        if createDevice(dev_id, 4) and (searchCode('cook_temperature', StatusProperties)):
                            # options={'ValueStep':'0.5', ' ValueMin':'-200', 'ValueMax':'200', 'ValueUnit':'°C'}
                            for item in StatusProperties:
                                temp = 'cook_temperature'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Cook Temperature)", DeviceID=dev_id, Unit=4, Type=242, Subtype=1, Options=options, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('fault', StatusProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Fault)", DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()

                    if dev_type == 'mower':
                        if createDevice(dev_id, 1) and searchCode('MachineControlCmd', FunctionProperties):
                            DomoticzEx.Log('Create device Smart Mower')
                            for item in FunctionProperties:
                                if item['code'] == 'MachineControlCmd':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Control)", DeviceID=dev_id, Unit=1, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('MachineRainMode', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Rain Mode)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('MachineStatus', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Status)", DeviceID=dev_id, Unit=3, Type=243, Subtype=19, Image=13, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('MachineWarning', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Warnig)", DeviceID=dev_id, Unit=4, Type=243, Subtype=19, Image=13, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('MachineError', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Error)", DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('MachineWorkMode', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'MachineWorkMode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (WorkMode)", DeviceID=dev_id, Unit=6, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()

                    if dev_type == 'human_presence':
                        if createDevice(dev_id, 1) and searchCode('presence_state', StatusProperties):
                            DomoticzEx.Log('Create device Human presence sensor')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Presence)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('sensitivity', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'sensitivity':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values['min'],the_values['max'] + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Sensitivity)", DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and (searchCode('near_detection', StatusProperties)):
                            for item in StatusProperties:
                                temp = 'near_detection'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Near detection)", DeviceID=dev_id, Unit=3, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 4) and (searchCode('far_detection', StatusProperties)):
                            for item in StatusProperties:
                                temp = 'far_detection'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Far detection)", DeviceID=dev_id, Unit=4, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('checking_result', StatusProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Result)", DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Used=1).Create()
                        if createDevice(dev_id, 6) and (searchCode('target_dis_closest', StatusProperties)):
                            for item in StatusProperties:
                                temp = 'target_dis_closest'
                                if item['code'] == temp:
                                    the_values = json.loads(item['values'])
                                    options = {}
                                    options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                    options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                    options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                    options['ValueUnit'] = the_values['unit']
                            DomoticzEx.Unit(Name=f"{dev['name']} (Target)", DeviceID=dev_id, Unit=6, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 10) and searchCode('presence_state', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'presence_state':
                                    the_values = json.loads(item['values'])
                                    mode = []
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'false'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Presence state)", DeviceID=dev_id, Unit=10, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                    if dev_type == 'evcharger':
                        if createDevice(dev_id, 1) and searchCode('switch', StatusProperties):
                            DomoticzEx.Log('Create EVcharger')
                            DomoticzEx.Unit(Name=f"{dev['name']} (Power)", DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('work_state', StatusProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Work state)", DeviceID=dev_id, Unit=2, Type=243, Subtype=19, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('temp_current', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Temperature)", DeviceID=dev_id, Unit=3, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('power_total', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (W)", DeviceID=dev_id, Unit=4, Type=248, Subtype=1, Used=1).Create()
                        if createDevice(dev_id, 5) and searchCode('charge_cur_set', StatusProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (A)", DeviceID=dev_id, Unit=5, Type=243, Subtype=23, Used=1).Create()
                        # if createDevice(dev_id, 6) and searchCode('forward_energy_total', StatusProperties) :
                        #     DomoticzEx.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev_id, Unit=6, Type=243, Subtype=29, Used=1).Create()
                        if createDevice(dev_id, 6) and searchCode('forward_energy_total', StatusProperties) :
                            options = {}
                            options['Custom'] = '1;kWh'
                            DomoticzEx.Unit(Name=f"{dev['name']} (kWh)", DeviceID=dev_id, Unit=6, Type=243, Subtype=31, Options=options, Used=1).Create()
                        if createDevice(dev_id, 7) and searchCode('online_state', StatusProperties):
                                DomoticzEx.Unit(Name=f"{dev['name']} (Online state)", DeviceID=dev_id, Unit=7, Type=243, Subtype=19, Used=1).Create()
                        # if createDevice(dev_id, 8) and searchCode('fault', StatusProperties):
                        #         DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=8, Type=243, Subtype=19, Image=13, Used=1).Create()

                    if dev_type in ('light'):
                        if createDevice(dev_id, 1) and searchCode('Light', FunctionProperties) and searchCode('work_mode', FunctionProperties) and (searchCode('colour_data', FunctionProperties) or searchCode('colour_data_v2', FunctionProperties)):
                            DomoticzEx.Log('Create device Light RGBW')
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=1, Switchtype=7, Used=1).Create()
                        if createDevice(dev_id, 2) and searchCode('Power', FunctionProperties):
                            DomoticzEx.Unit(Name=f"{dev['name']} (Power)", DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 3) and searchCode('lightmode', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'lightmode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Lightmode)", DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, 4) and searchCode('dp_mist_grade', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'dp_mist_grade':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=f"{dev['name']} (Mist grade)", DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                    if dev_type == 'infrared':
                        if createDevice(dev_id, 1):
                            DomoticzEx.Log(f"Infrared device: {dev['name']}")
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=0).Create()
                            UpdateDomoticz(dev_id, 1, 'Infrared devices are not yet able to be controlled by the plugin.', 0, 0)

                    if createDevice(dev_id, 1) and dev_id not in str(Devices):
                        DomoticzEx.Log(f"No controls found for device: {dev['name']}")
                        DomoticzEx.Unit(Name=f"{dev['name']} (Unknown Device)", DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=1).Create()
                        UpdateDomoticz(dev_id, 1, 'This device is not recognized. Please run the debug_discovery with Python from the tools directory and create an issue report at https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/issues so that the device can be added.', 0, 0)

                except Exception:
                    DomoticzEx.Error("Domoticz blocks new devices. Enable 'Accept new Hardware Devices'.")
                    return

                setConfigItem(
                    dev_id,
                    {
                        'key': dev['key'],
                        'category': dev_type,
                        'mac': dev.get('mac', '00:00:00:00:00:00'),
                        'ip': deviceinfo.get('ip', '127.0.0.1'),
                        'product_id': dev['product_id'],
                        'version': deviceinfo.get('version', '3.3')
                    }
                )
            if Devices:
                battery = is_battery_device(StatusProperties)

                if not battery:
                    try:
                        if online and Devices[dev_id].TimedOut == 1:
                            UpdateDomoticz(dev_id, 1, '', 0, 0)
                        elif not online and Devices[dev_id].TimedOut == 0:
                            UpdateDomoticz(dev_id, 1, False, 0, 1)
                    except:
                        DomoticzEx.Log(f"Device {dev_name} offline")
                else:
                    # Battery devices never timeout
                    if Devices[dev_id].TimedOut == 1:
                        UpdateDomoticz(dev_id, 1, True, 0, 0)
                if online:
                    try:
                        def update_bool_device(code, unit, value=None):
                            # Check if the given code is present and device is valid
                            if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                                return False
                            # Get the current status of the device
                            if value is None:
                                currentstatus = StatusDeviceTuya(code)
                            else:
                                currentstatus = False if value == StatusDeviceTuya(code) else True
                            UpdateDomoticz(dev_id, unit, bool(currentstatus), int(bool(currentstatus)), 0)
                            return True

                        def update_value_device(code, unit, codeunit=None):
                            # Check if the given code is present and device is valid
                            if not searchCode(code, StatusProperties) or not get_unit(code, StatusProperties) not in [codeunit, None] or not checkDevice(dev_id, unit):
                                return False
                            # Get the current value of the device
                            currentvalue = StatusDeviceTuya(code)
                            if str(currentvalue) != str(Devices[dev_id].Units[unit].sValue):
                                UpdateDomoticz(dev_id, unit, currentvalue, 0, 0)
                            return True

                        def update_nvalue_device(code, unit, codeunit=None):
                            # Check if the given code is present and device is valid
                            if not searchCode(code, StatusProperties) or not get_unit(code, StatusProperties) not in [codeunit, None] or not checkDevice(dev_id, unit):
                                return False
                            # Get the current value of the device
                            value = StatusDeviceTuya(code)
                            if isinstance(value, (int, float)):
                                currentvalue = int(value)
                            else:
                                currentvalue = value
                            if str(currentvalue) != str(Devices[dev_id].Units[unit].nValue):
                                UpdateDomoticz(dev_id, unit, 0, currentvalue, 0)
                            return True

                        def update_dualvalue_device(code1, code2, unit):
                            # Check if the given code is present and device is valid
                            if not searchCode(code1, StatusProperties) or not searchCode(code2, StatusProperties) or not checkDevice(dev_id, unit):
                                return False
                            # Get the current value of the device
                            currentvalue1 = StatusDeviceTuya(code1)
                            currentvalue2 = StatusDeviceTuya(code2)
                            currentdomo = Devices[dev_id].Units[unit].sValue
                            if str(currentvalue1) != str(currentdomo.split(';')[0]) or str(currentvalue2) != str(currentdomo.split(';')[1]):
                                UpdateDomoticz(dev_id, unit, f"{currentvalue1};{currentvalue2};0", 0, 0)
                            return True

                        def update_power_device(code, unit):
                            # Check if the given code is present and device is valid
                            if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                                return False
                            # Get the power value of the device
                            currentpower = StatusDeviceTuya(code)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[unit].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev_id].Units[unit].sValue if len(Devices[dev_id].Units[unit].sValue) > 0 else '0;0'
                            # Calculating the Power Difference in an time interval
                            UpdateDomoticz(dev_id, unit, f"{currentpower};{float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))}", 0, 0, 1)
                            return True

                        def update_select_device(code, unit):
                            # Check if the given code is present and device is valid
                            if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                                return False
                            # Get the current mode of the device
                            currentmode = StatusDeviceTuya(code)
                            # Get the mode configuration once
                            mode = getConfigItem(f"{dev_id}-{unit}", 'mode')
                            if mode is None or mode == {}:
                                # Loop through StatusProperties to set the mode
                                for item in StatusProperties:
                                    if item['code'] == code:
                                        DomoticzEx.Debug(f"code: {item['code']}")
                                        # Parse values based on item type
                                        the_values = json.loads(item['values'])
                                        mode = ['off']
                                        if item['type'] == 'Bitmap':
                                            mode.extend(the_values['label'])
                                        else:
                                            mode.extend(the_values['range'])
                                        setConfigItem(f"{dev_id}-{unit}", {'mode': mode})
                                        break  # Exit the loop once we find the code
                            # Calculate the new value
                            try:
                                new_value = mode.index(str(currentmode)) * 10
                            except:
                                mode.append(currentmode)
                                Devices[dev_id].Units[unit].Options={'LevelNames': '|'.join(mode)}
                                setConfigItem(f"{dev_id}-{unit}", {'mode': mode})
                                Devices[dev_id].Units[unit].Update(UpdateOptions=True)
                                new_value = mode.index(str(currentmode)) * 10
                            # Only update if the new value differs from the current value
                            if str(new_value) != str(Devices[dev_id].Units[unit].sValue):
                                UpdateDomoticz(dev_id, unit, int(new_value), 1, 0)
                            return True

                        def update_selectnum_device(code, unit):
                            # Check if the given code is present and device is valid
                            if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                                return False
                            # Get the current mode of the device
                            current = StatusDeviceTuya(code)
                            if str(current) != str(Devices[dev_id].Units[unit].sValue):
                                UpdateDomoticz(dev_id, unit, current, 1, 0)
                            return True

                        def update_level_device(code, unit, level_mapping):
                            # Validate code, unit, and device
                            if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                                return False
                            # Get current level code from Tuya
                            currentlevel = StatusDeviceTuya(code)
                            # Map Tuya level to Domoticz level
                            level = level_mapping.get(currentlevel)
                            if level is None:
                                return False
                            # Update only if changed
                            if str(currentlevel) != str(Devices[dev_id].Units[unit].sValue):
                                UpdateDomoticz(dev_id, unit, str(currentlevel), level, 0)
                            return True

                        def update_text_device(code, unit):
                            # Check if the given code is present and device is valid
                            if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                                return False
                            # Get the current mode of the device
                            value = StatusDeviceTuya(code)
                            # Loop through StatusProperties to set the mode
                            for item in StatusProperties:
                                if item['code'] == code:
                                    the_values = json.loads(item['values'])
                                    mode = ['No fault']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                        currentmode = mode[value].replace('_', ' ').capitalize()
                                    else:
                                        mode.extend(the_values['range'])
                                        currentmode = mode[value].replace('_', ' ').capitalize()
                            # Only update if the new value differs from the current value
                            if str(currentmode) != str(Devices[dev_id].Units[unit].nValue):
                                UpdateDomoticz(dev_id, unit, str(currentmode), 1, 0)
                            return True

                        def battery_device():
                            # Battery_device
                            if searchCode('battery_state', StatusProperties) or searchCode('battery', StatusProperties) or searchCode('va_battery', StatusProperties) or searchCode('battery_percentage', StatusProperties):
                                if searchCode('battery_state', StatusProperties):
                                    if StatusDeviceTuya('battery_state') == 'high':
                                        currentbattery = 100
                                    if StatusDeviceTuya('battery_state') == 'middle':
                                        currentbattery = 50
                                    if StatusDeviceTuya('battery_state') == 'low':
                                        currentbattery = 5
                                if searchCode('BatteryStatus', StatusProperties):
                                    if int(StatusDeviceTuya('BatteryStatus')) == 1:
                                        currentbattery = 100
                                    elif int(StatusDeviceTuya('BatteryStatus')) == 2:
                                        currentbattery = 50
                                    elif int(StatusDeviceTuya('BatteryStatus')) == 3:
                                        currentbattery = 5
                                    else:
                                        currentbattery = 100
                                if searchCode('battery', StatusProperties):
                                    currentbattery = StatusDeviceTuya('battery') * 10
                                if searchCode('va_battery', StatusProperties):
                                    currentbattery = StatusDeviceTuya('va_battery')
                                if searchCode('battery_percentage', StatusProperties):
                                    currentbattery = StatusDeviceTuya('battery_percentage')
                                if searchCode('residual_electricity', StatusProperties):
                                    currentbattery = StatusDeviceTuya('residual_electricity')
                                for unit in Devices[dev_id].Units:
                                    if str(currentbattery) != str(Devices[dev_id].Units[unit].BatteryLevel):
                                        Devices[dev_id].Units[unit].BatteryLevel = currentbattery
                                        Devices[dev_id].Units[unit].Update()
                            return
                        # status DomoticzEx
                        try:
                            sValue = Devices[dev_id].Units[1].sValue
                            nValue = Devices[dev_id].Units[1].nValue
                        except:
                            pass

                        if dev_type in ('switch', 'switch/sensor'):
                            if update_bool_device('switch_1', 1):
                                pass
                            elif update_bool_device('switch', 1):
                                pass
                            elif update_bool_device('switch_on', 1):
                                pass

                            for switch_number in range(2, 9):
                                update_bool_device(f"switch_{switch_number}", switch_number)
                            if update_value_device('cur_current', 15, 'mA'):
                                pass
                            elif update_value_device('cur_current', 11):
                                pass
                            update_value_device('cur_power', 12)
                            update_value_device('cur_voltage', 13)
                            update_power_device('cur_power', 14)
                            if searchCode('phase_a', StatusProperties):
                                base64_string = StatusDeviceTuya('phase_a')
                                # Decode base64 string
                                decoded_data = base64.b64decode(base64_string)
                                # Extract voltage, current, and power data
                                currentvoltage = int.from_bytes(decoded_data[:2], byteorder='big') * 0.1
                                currentcurrent = int.from_bytes(decoded_data[2:5], byteorder='big') * 0.001
                                currentpower = int.from_bytes(decoded_data[5:8], byteorder='big')
                                UpdateDomoticz(dev_id, 11, str(currentcurrent), 0, 0)
                                UpdateDomoticz(dev_id, 12, str(currentpower), 0, 0)
                                UpdateDomoticz(dev_id, 13, str(currentvoltage), 0, 0)
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[14].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev_id].Units[14].sValue if len(Devices[dev_id].Units[14].sValue) > 0 else '0;0'
                                currentEle = StatusDeviceTuya('add_ele')
                            update_value_device('leakage_current', 15)
                            update_value_device('temp_current', 16)
                            update_power_device('out_power', 17)
                            update_power_device('out_power', 18)
                            if searchCode('power_a', StatusProperties):
                                powerA = StatusDeviceTuya('power_a')
                                dirA = StatusDeviceTuya('direction_a')
                                if dirA == 'REVERSE':
                                    lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[19].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                    lastvalue = Devices[dev_id].Units[19].sValue if len(Devices[dev_id].Units[19].sValue) > 0 else '0;0'
                                    lastvalueR = Devices[dev_id].Units[20].sValue if len(Devices[dev_id].Units[20].sValue) > 0 else '0;0'
                                    UpdateDomoticz(dev_id, 19, f"{powerA};{float(lastvalue.split(';')[1]) + ((powerA) * (lastupdate / 3600))}", 0, 0, 1)
                                    UpdateDomoticz(dev_id, 20, f"0;{float(lastvalueR.split(';')[1])}", 0, 0, 1)
                                if dirA == 'FORWARD':
                                    lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[20].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                    lastvalue = Devices[dev_id].Units[20].sValue if len(Devices[dev_id].Units[20].sValue) > 0 else '0;0'
                                    lastvalueR = Devices[dev_id].Units[19].sValue if len(Devices[dev_id].Units[19].sValue) > 0 else '0;0'
                                    UpdateDomoticz(dev_id, 20, f"{powerA};{float(lastvalue.split(';')[1]) + ((powerA) * (lastupdate / 3600))}", 0, 0, 1)
                                    UpdateDomoticz(dev_id, 19, f"0;{float(lastvalueR.split(';')[1])}", 0, 0, 1)
                            if searchCode('power_b', StatusProperties):
                                powerB = StatusDeviceTuya('power_b')
                                dirB = StatusDeviceTuya('direction_b')
                                if dirB == 'REVERSE':
                                    lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[21].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                    lastvalue = Devices[dev_id].Units[21].sValue if len(Devices[dev_id].Units[21].sValue) > 0 else '0;0'
                                    lastvalueR = Devices[dev_id].Units[22].sValue if len(Devices[dev_id].Units[22].sValue) > 0 else '0;0'
                                    UpdateDomoticz(dev_id, 21, f"{powerB};{float(lastvalue.split(';')[1]) + ((powerB) * (lastupdate / 3600))}", 0, 0, 1)
                                    UpdateDomoticz(dev_id, 22, f"0;{float(lastvalueR.split(';')[1])}", 0, 0, 1)
                                if dirB == 'FORWARD':
                                    lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[22].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                    lastvalue = Devices[dev_id].Units[22].sValue if len(Devices[dev_id].Units[22].sValue) > 0 else '0;0'
                                    lastvalueR = Devices[dev_id].Units[21].sValue if len(Devices[dev_id].Units[21].sValue) > 0 else '0;0'
                                    UpdateDomoticz(dev_id, 22, f"{powerB};{float(lastvalue.split(';')[1]) + ((powerB) * (lastupdate / 3600))}", 0, 0, 1)
                                    UpdateDomoticz(dev_id, 21, f"0;{float(lastvalueR.split(';')[1])}", 0, 0, 1)
                            battery_device()

                        if dev_type == 'dimmer':
                            if searchCode('switch_led_1', StatusProperties):
                                currentstatus = StatusDeviceTuya('switch_led_1')
                                currentdim = brightness_to_pct(StatusProperties, 'bright_value_1', int(StatusDeviceTuya('bright_value_1')))
                                if bool(currentstatus) == False or currentdim == 0:
                                    UpdateDomoticz(dev_id, 1, False, 0, 0)
                                elif bool(currentstatus) == True and  currentdim > 0 and str(currentdim) != str(Devices[dev_id].Units[1].sValue):
                                    UpdateDomoticz(dev_id, 1, currentdim, 1, 0)

                            if searchCode('switch_led_2', StatusProperties):
                                currentstatus = StatusDeviceTuya('switch_led_2')
                                currentdim = brightness_to_pct(StatusProperties, 'bright_value_2', int(StatusDeviceTuya('bright_value_2')))
                                if bool(currentstatus) == False or currentdim == 0:
                                    UpdateDomoticz(dev_id, 2, False, 0, 0)
                                elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev_id].Units[2].sValue):
                                    UpdateDomoticz(dev_id, 2, currentdim, 1, 0)

                        if dev_type in ('light','fanlight'):
                            unit = Devices[dev_id].Units[1]
                            if searchCode('switch_led', StatusProperties):
                                currentstatus = bool(StatusDeviceTuya('switch_led'))
                            else:
                                currentstatus = bool(StatusDeviceTuya('led_switch'))
                            nval = 1 if currentstatus else 0
                            if searchCode('bright_value_v2', StatusProperties):
                                dimtuya = brightness_to_pct(StatusProperties, 'bright_value_v2', int(StatusDeviceTuya('bright_value_v2')))
                            elif searchCode('bright_value', StatusProperties):
                                dimtuya = brightness_to_pct(StatusProperties, 'bright_value', int(StatusDeviceTuya('bright_value')))
                            else:
                                dimtuya = 100
                            svalue = str(dimtuya) if currentstatus else '0'
                            if str(unit.sValue) != svalue or unit.nValue != nval:
                                UpdateDomoticz(dev_id, 1, svalue, nval, 0)
                            if searchCode('Power', StatusProperties):
                                currentstatus = StatusDeviceTuya('Power')
                                UpdateDomoticz(dev_id, 2, bool(currentstatus), int(bool(currentstatus)), 0)
                            if searchCode('lightmode', StatusProperties):
                                currentmode = StatusDeviceTuya('lightmode')
                                for item in FunctionProperties:
                                    if item['code'] == 'lightmode':
                                        the_values = json.loads(item['values'])
                                        mode = ['off']
                                        if item['type'] == 'Bitmap':
                                            mode.extend(the_values['label'])
                                        else:
                                            mode.extend(the_values['range'])
                                if str(mode.index(str(currentmode)) * 10) != str(Devices[dev_id].Units[3].sValue):
                                    UpdateDomoticz(dev_id, 3, int(mode.index(str(currentmode)) * 10), 1, 0)

                            if searchCode('dp_mist_grade', StatusProperties):
                                currentmode = StatusDeviceTuya('dp_mist_grade')
                                for item in FunctionProperties:
                                    if item['code'] == 'dp_mist_grade':
                                        the_values = json.loads(item['values'])
                                        mode = ['off']
                                        if item['type'] == 'Bitmap':
                                            mode.extend(the_values['label'])
                                        else:
                                            mode.extend(the_values['range'])
                                if str(mode.index(str(currentmode)) * 10) != str(Devices[dev_id].Units[4].sValue):
                                    UpdateDomoticz(dev_id, 4, int(mode.index(str(currentmode)) * 10), 1, 0)

                        if dev_type == 'cover':
                            if searchCode('position', StatusProperties) or searchCode('percent_control', StatusProperties):
                                if searchCode('position', StatusProperties):
                                    currentposition = StatusDeviceTuya('position')
                                elif searchCode('percent_control', StatusProperties):
                                    currentposition = StatusDeviceTuya('percent_control')
                                if str(currentposition) == '0':
                                    UpdateDomoticz(dev_id, 1, currentposition, 0, 0)
                                if str(currentposition) == '100':
                                    UpdateDomoticz(dev_id, 1, currentposition, 1, 0)
                                if str(currentposition) != str(Devices[dev_id].Units[1].sValue):
                                    UpdateDomoticz(dev_id, 1, currentposition, 2, 0)
                            elif searchCode('mach_operate', StatusProperties):
                                currentstatus = StatusDeviceTuya('control')
                                if currentstatus == 'close':
                                    UpdateDomoticz(dev_id, 1, 'ZZ', 0, 0)
                                elif currentstatus == 'open':
                                    UpdateDomoticz(dev_id, 1, 'FZ', 1, 0)
                                elif currentstatus == 'stop':
                                    UpdateDomoticz(dev_id, 1, 'STOP', 1, 0)
                            elif searchCode('control', StatusProperties):
                                currentstatus = StatusDeviceTuya('control')
                                if currentstatus == 'close':
                                    UpdateDomoticz(dev_id, 1, 'Open', 0, 0)
                                elif currentstatus == 'open':
                                    UpdateDomoticz(dev_id, 1, 'Close', 1, 0)
                                elif currentstatus == 'stop':
                                    UpdateDomoticz(dev_id, 1, 'Stop', 1, 0)
                            if searchCode('position_2', StatusProperties) or searchCode('percent_control_2', StatusProperties):
                                if searchCode('position_2', StatusProperties):
                                    currentposition = StatusDeviceTuya('position_2')
                                elif searchCode('percent_control_2', StatusProperties):
                                    currentposition = StatusDeviceTuya('percent_control_2')
                                if str(currentposition) == '0':
                                    UpdateDomoticz(dev_id, 2, currentposition, 0, 0)
                                if str(currentposition) == '100':
                                    UpdateDomoticz(dev_id, 2, currentposition, 1, 0)
                                if str(currentposition) != str(Devices[dev_id].Units[2].sValue):
                                    UpdateDomoticz(dev_id, 2, currentposition, 2, 0)
                            elif searchCode('mach_operate_2', StatusProperties):
                                currentstatus = StatusDeviceTuya('control_2')
                                if currentstatus == 'close':
                                    UpdateDomoticz(dev_id, 2, 'ZZ', 0, 0)
                                elif currentstatus == 'open':
                                    UpdateDomoticz(dev_id, 2, 'FZ', 1, 0)
                                elif currentstatus == 'stop':
                                    UpdateDomoticz(dev_id, 2, 'STOP', 1, 0)
                            elif searchCode('control_2', StatusProperties):
                                currentstatus = StatusDeviceTuya('control_2')
                                if currentstatus == 'close':
                                    UpdateDomoticz(dev_id, 2, 'Open', 0, 0)
                                elif currentstatus == 'open':
                                    UpdateDomoticz(dev_id, 2, 'Close', 1, 0)
                                elif currentstatus == 'stop':
                                    UpdateDomoticz(dev_id, 2, 'Stop', 1, 0)

                        if dev_type == 'smartheatpump':
                            update_value_device('intemp', 2)
                            update_value_device('outtemp', 3)
                            update_value_device('whjtemp', 4)
                            update_value_device('cmptemp', 5)
                            update_value_device('wttemp', 6)
                            update_value_device('hqtemp', 7)
                            update_value_device('cmp_act_frep', 8)
                            update_value_device('cmp_cur', 9)
                            update_value_device('dc_fan_speed', 10)
                            update_value_device('ach_stemp', 11)
                            update_value_device('wth_stemp', 12)
                            update_value_device('aircond_temp_diff', 13)
                            update_value_device('wth_temp_diff', 14)
                            update_value_device('acc_stemp', 15)
                            update_select_device('mode', 16)
                            update_select_device('work_mode', 17)
                            # update_value_device('temp_current', 18)
                            update_value_device('temp_set', 19)
                            # update_value_device('water_set', 20)
                            update_value_device('temp_top', 21)
                            update_value_device('temp_bottom',22)
                            update_bool_device('compressor_state',23)
                            update_value_device('water_flow',24)

                        if dev_type == 'thermostat' or dev_type == 'heater' or dev_type == 'heatpump':
                            if update_bool_device('switch', 1):
                                pass
                            elif update_bool_device('switch_1', 1):
                                pass
                            elif update_bool_device('Power', 1):
                                pass
                            if update_bool_device('infared_switch', 1):
                                pass
                            if update_value_device('temp_current', 2):
                                pass
                            elif update_value_device('upper_temp', 2):
                                pass
                            elif update_value_device('c_temperature', 2):
                                pass
                            elif update_value_device('TempCurrent', 2):
                                pass
                            if update_value_device('temp_set', 3):
                                pass
                            elif update_value_device('set_temp', 3):
                                pass
                            elif update_value_device('temperature_c', 3):
                                pass
                            elif update_value_device('TempSet', 3):
                                pass
                            elif update_value_device('target_temp', 3):
                                pass
                            if update_select_device('running_mode', 4):
                                pass
                            elif update_select_device('work_mode', 4):
                                pass
                            elif update_select_device('Mode', 4):
                                pass
                            elif update_select_device('mode', 4):
                                pass
                            update_bool_device('window_check', 5)
                            update_bool_device('child_lock', 6)
                            update_bool_device('eco', 7)
                            update_value_device('temp_floor', 8)
                            if update_select_device('windspeed', 9):
                                pass
                            elif update_select_device('fan_level', 9):
                                pass
                            elif update_select_device('fan_speed_enum', 9):
                                pass
                            update_nvalue_device('humidity_current', 10)
                            if update_value_device('currentcurrent', 15, 'mA'):
                                pass
                            elif update_value_device('currentcurrent', 11):
                                pass
                            if update_value_device('cur_power',12):
                                pass
                            elif update_value_device('average_power', 12):
                                pass
                            update_value_device('cur_voltage', 13)
                            if update_power_device('cur_power', 14):
                                pass
                            elif update_power_device('average_power', 14):
                                pass
                            update_dualvalue_device('temp_current', 'humidity_current', 16)
                            update_bool_device('anti_bother', 17)
                            update_text_device('fault',18)
                            battery_device()

                        if dev_type in ('sensor', 'smartir', 'switch/sensor'):
                            if update_value_device('va_temperature', 1):
                                pass
                            elif update_value_device('temp_current', 1):
                                pass
                            elif update_value_device('local_temp', 1):
                                pass
                            elif update_value_device('Tin', 1):
                                pass
                            if update_nvalue_device('va_humidity', 2):
                                pass
                            elif update_nvalue_device('humidity_value', 2):
                                pass
                            elif update_nvalue_device('local_hum', 2):
                                pass
                            elif update_nvalue_device('humidity', 2):
                                pass
                            elif update_nvalue_device('Hin', 2):
                                pass
                            if update_dualvalue_device('va_temperature','va_humidity', 3):
                                pass
                            elif update_dualvalue_device('va_temperature','humidity_value', 3):
                                pass
                            elif update_dualvalue_device('temp_current','humidity', 3):
                                pass
                            elif update_dualvalue_device('temp_current','humidity_value', 3):
                                pass
                            elif update_dualvalue_device('local_temp','local_hum', 3):
                                pass
                            elif update_dualvalue_device('Tin','Hin', 3):
                                pass
                            update_value_device('co2_value', 4)
                            # update_value_device('air_quality_index', 5)
                            update_level_device('air_quality_index', 5, {"level_1": 1, "level_2": 2, "level_3": 4})
                            update_value_device('ch2o_value', 6)
                            update_value_device('voc_value', 7)
                            update_value_device('pm25_value', 8)
                            update_value_device('pm10', 9)
                            update_value_device('bright_value', 10)
                            update_bool_device('switch', 11)
                            update_value_device('ph_current', 12)
                            update_value_device('pro_current', 13)
                            update_value_device('orp_current', 14)
                            update_value_device('ph_warn_min', 15)
                            update_value_device('ph_warn_max', 16)
                            update_value_device('pro_warn_min', 17)
                            update_value_device('pro_warn_max', 18)
                            update_value_device('orp_warn_min', 19)
                            update_value_device('orp_warn_max', 20)
                            if update_value_device('sub1_temp', 21):
                                pass
                            elif update_value_device('ToutCh1', 21):
                                pass
                            if update_nvalue_device('sub1_hum', 22):
                                pass
                            elif update_value_device('HoutCh1', 22):
                                pass
                            if update_dualvalue_device('sub1_temp', 'sub1_hum', 23):
                                pass
                            elif update_dualvalue_device('ToutCh1', 'HoutCh1', 23):
                                pass
                            update_value_device('temp_warn_min', 24)
                            update_value_device('temp_warn_max', 25)
                            if update_value_device('sub2_temp', 31):
                                pass
                            elif update_value_device('ToutCh2', 31):
                                pass
                            if update_nvalue_device('sub2_hum', 32):
                                pass
                            elif update_value_device('HoutCh2', 32):
                                pass
                            if update_dualvalue_device('sub2_temp', 'sub2_hum', 33):
                                pass
                            elif update_dualvalue_device('ToutCh2', 'HoutCh2', 33):
                                pass
                            if update_value_device('sub3_temp', 41):
                                pass
                            elif update_value_device('ToutCh3', 41):
                                pass
                            if update_nvalue_device('sub3_hum', 42):
                                pass
                            elif update_value_device('HoutCh3', 42):
                                pass
                            if update_dualvalue_device('sub3_temp', 'sub3_hum', 43):
                                pass
                            elif update_dualvalue_device('ToutCh3', 'HoutCh3', 43):
                                pass
                            update_value_device('temp_current_2', 44)
                            update_value_device('cook_temperature', 45)
                            update_value_device('cook_temperature_2', 46)
                            update_value_device('atmosphere', 47)
                            update_value_device('temp_current_2', 44)
                            update_bool_device('pir', 48, 'none')
                            update_bool_device('pir_state', 48, 'none')
                            update_bool_device('temper_alarm', 49)
                            update_select_device('co_status', 50)
                            update_select_device('checking_result', 51)
                            for channel in range(1, 8):
                                unit_base = 50 + (channel * 3)  # Unit 51 => 71
                                if update_value_device(f"ch{channel}_temp", unit_base - 2):
                                    pass
                                if update_nvalue_device(f"ch{channel}_humi", unit_base - 1):
                                    pass
                                if update_dualvalue_device(f"ch{channel}_temp", f"ch{channel}_humi", unit_base):
                                    pass
                            update_level_device('liquid_state', 72, {"normal": 1, "lower_alarm": 4, "upper_alarm": 4})
                            update_value_device('liquid_level_percent', 73)
                            update_value_device('liquid_depth', 74)
                            battery_device()

                        if dev_type == 'doorbell':
                            update_bool_device('doorbell_active', 1, '')
                            update_bool_device('floodlight_switch', 2)
                            update_bool_device('motion_switch', 3)
                            update_bool_device('basic_indicator', 4)
                            update_bool_device('decibel_switch', 5)
                            update_bool_device('basic_private', 6)
                            update_bool_device('motion_area_switch', 7)
                            update_bool_device('motion_area_switch', 8)
                            update_bool_device('siren_switch', 9)
                            update_select_device('nightvision_mode', 10)
                            update_bool_device('floodlight_switch', 11)
                            update_value_device('ipc_siren_volume', 12)
                            update_value_device('ipc_siren_duration', 13)

                        if dev_type == 'fan':
                            update_bool_device('switch', 1)
                            update_select_device('mode', 2)
                            update_selectnum_device('fan_speed', 3)
                            update_value_device('temp_set', 4)
                            update_value_device('temp_current', 5)
                            update_text_device('fault', 6)
                            update_bool_device('light', 7)
                            update_bool_device('RH_switch', 8)
                            update_value_device('RH_threshold', 9)
                            update_value_device('RH_value', 10)
                            update_bool_device('anion', 11)
                            update_bool_device('free_cooling', 12)
                            update_bool_device('powerful', 13)

                        if dev_type == 'fanlight':
                            update_bool_device('fan_switch', 2)
                            update_selectnum_device('fan_speed', 3)
                            update_select_device('fan_direction', 4)

                        if dev_type == 'siren':
                            update_bool_device('AlarmSwitch', 1)
                            if update_select_device('Alarmtype', 2):
                                pass
                            elif update_select_device('alarm_state', 2):
                                pass
                            if update_selectnum_device('AlarmPeriod', 3):
                                pass
                            elif update_selectnum_device('alarm_volume', 3):
                                pass
                            battery_device()

                        if dev_type == 'powermeter':
                            update_power_device('CurrentA', 1)
                            update_power_device('CurrentB', 1)
                            update_power_device('CurrentC', 1)
                            update_value_device('Frequency', 2)
                            update_value_device('Temperature', 3)
                            update_value_device('Current', 4)
                            update_power_device('ActivePower', 5)
                            update_value_device('VoltageA', 11)
                            update_power_device('ActivePowerA', 12)
                            update_value_device('VoltageB', 21)
                            update_power_device('ActivePowerB', 22)
                            update_value_device('VoltageC', 31)
                            update_power_device('ActivePowerC', 32)
                            if searchCode('phase_a', StatusProperties):
                                base64_string = StatusDeviceTuya('phase_a')
                                # Decode base64 string
                                decoded_data = base64.b64decode(base64_string)
                                # Extract voltage, current, and power data
                                currentvoltage = int.from_bytes(decoded_data[:2], byteorder='big') * 0.1
                                currentcurrent = int.from_bytes(decoded_data[2:5], byteorder='big') * 0.001
                                currentpower = int.from_bytes(decoded_data[5:8], byteorder='big')
                                leakagecurrent = StatusDeviceTuya('leakage_current')
                                if product_id == 'ze8faryrxr0glqnn':
                                    if str(int.from_bytes(decoded_data[2:5], byteorder='big'))[-1:] == '1':
                                        currentcurrent = 0 - currentcurrent
                                        currentpower = 0 - currentpower
                                UpdateDomoticz(dev_id, 1, str(currentcurrent), 0, 0)
                                UpdateDomoticz(dev_id, 2, str(currentpower), 0, 0)
                                UpdateDomoticz(dev_id, 3, str(currentvoltage), 0, 0)
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[4].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev_id].Units[4].sValue if len(Devices[dev_id].Units[4].sValue) > 0 else '0;0'
                                UpdateDomoticz(dev_id, 4, f"{currentpower};{float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))}", 0, 0, 1)
                            update_bool_device('switch', 5)
                            update_text_device('fault', 6)
                            # 2 phase Meter with reverse
                            update_value_device('voltage_a', 1)
                            update_value_device('freq', 2)
                            update_power_device('total_power', 3)
                            update_value_device('power_a', 11)
                            update_value_device('current_a', 12)
                            update_value_device('direction_a', 13)
                            update_value_device('energy_forword_a', 14)
                            update_value_device('energy_reverse_a', 15)
                            update_value_device('power_b', 21)
                            update_value_device('current_b', 22)
                            update_value_device('direction_b', 23)
                            update_value_device('energy_forword_b', 24)
                            update_value_device('energy_reserse_b', 25)

                        if dev_type == 'powermeter' and (searchCode('switch', StatusProperties) or searchCode('switch_1', StatusProperties)) and not searchCode('phase_a', StatusProperties):
                            if update_bool_device('switch', 1):
                                pass
                            elif update_bool_device('switch_1', 1):
                                pass
                            update_value_device('cur_current', 2)
                            update_power_device('cur_power', 3)
                            update_value_device('cur_voltage', 4)
                            update_text_device('fault', 5)

                        if dev_type == 'gateway':
                            if update_value_device('master_state', 1):
                                pass
                            else:
                                UpdateDomoticz(dev_id, 1, 'Gateway only', 0, 0)

                        if dev_type == 'doorcontact':
                            update_bool_device('doorcontact_state', 1)
                            battery_device()

                        if dev_type == 'pirlight':
                            update_bool_device('switch_pir', 2)
                            update_select_device('device_mode', 3)
                            update_select_device('pir_sensitivity', 4)

                        if dev_type == 'smokedetector':
                            if update_bool_device('smoke_sensor_status', 2, 'normal'):
                                pass
                            elif update_bool_device('PIR', 2, 0):
                                pass
                            # if searchCode('smoke_sensor_status', StatusProperties):
                            #     currentstatus = StatusDeviceTuya('smoke_sensor_status')
                            #     if currentstatus == 'normal':
                            #         UpdateDomoticz(dev_id, 1, False, 0, 0)
                            #     elif currentstatus == 'alarm':
                            #         UpdateDomoticz(dev_id, 1, True, 1, 0)
                            #     UpdateDomoticz(dev_id, 2, currentstatus, 0, 0)
                            # if searchCode('PIR', StatusProperties):
                            #     currentstatus = StatusDeviceTuya('PIR')
                            #     if int(currentstatus) == 0:
                            #         UpdateDomoticz(dev_id, 1, False, 0, 0)
                            #     elif int(currentstatus) > 0:
                            #         UpdateDomoticz(dev_id, 1, True, 1, 0)
                            #     UpdateDomoticz(dev_id, 2, currentstatus, 0, 0)
                            battery_device()

                        if dev_type == 'garagedooropener':
                            update_bool_device('switch_1', 1)
                            update_bool_device('doorcontact_state', 2)
                            update_bool_device('door_control_1', 3)

                        if dev_type == 'feeder':
                            update_selectnum_device('manual_feed', 1)
                            update_select_device('feed_state', 2)
                            update_selectnum_device('feed_report', 3)
                            update_bool_device('light', 5)

                        if dev_type == 'waterleak':
                            update_bool_device('watersensor_state', 1, 'normal')
                            battery_device()

                        if dev_type == 'irrigation':
                            if update_bool_device('switch', 1):
                                pass
                            elif update_bool_device('switch_1', 1):
                                pass
                            update_select_device('work_state', 2)
                            update_bool_device('areaone', 3)
                            update_bool_device('areatwo', 4)
                            update_bool_device('areathree', 5)
                            update_bool_device('areafour', 6)
                            update_bool_device('areafive', 7)
                            update_bool_device('areasix', 8)
                            battery_device()

                        if dev_type == 'wswitch':
                            for x in range(1, 4):
                                if update_select_device(f"switch{x}_value", x):
                                    pass
                                elif update_select_device(f"switch_type_{x}", x):
                                    pass
                                elif update_select_device(f"switch_mode{x}", x):
                                    pass
                            battery_device()

                        if dev_type == 'starlight':
                            update_bool_device('switch_led', 1)
                            colortuya = StatusDeviceTuya('colour_data')
                            if currentstatus == True:
                                tuyacolor = ast.literal_eval(StatusDeviceTuya('colour_data'))
                                Color = Devices[dev_id].Units[1].Color
                                if Color == '':
                                    Color = {'b':255,'cw':0,'g':255,'m':3,'r':255,'t':0,'ww':0}
                                h, s, v = tuyacolor['h'], tuyacolor['s'], tuyacolor['v']
                                r, g, b = hsv_to_rgb_v2(h, s, v)
                                colorupdate = {'b':b,'cw':0,'g':g,'m':3,'r':r,'t':0,'ww':0}
                                # {'b':0,'cw':0,'g':3,'m':3,'r':255,'t':0,'ww':0}
                                if (Color['r'] != r or Color['g'] != g or Color['b'] != b ):
                                    UpdateDomoticz(dev_id, 1, json.dumps(colorupdate), 1, 0)
                                    UpdateDomoticz(dev_id, 1, brightness_to_pct(StatusProperties, 'bright_value', int(v * 0.255)), 1, 0)
                            update_bool_device('colour_switch', 2)
                            if searchCode('laser_switch', StatusProperties):
                                currentstatus = StatusDeviceTuya('laser_switch')
                                currentdim = brightness_to_pct(StatusProperties, 'laser_bright', int(StatusDeviceTuya('laser_bright')))
                                if bool(currentstatus) == False or currentdim == 0:
                                    UpdateDomoticz(dev_id, 3, False, 0, 0)
                                elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev_id].Units[3].sValue):
                                    UpdateDomoticz(dev_id, 3, True, 1, 0)
                                    UpdateDomoticz(dev_id, 3, currentdim, 1, 0)
                            if searchCode('fan_switch', StatusProperties):
                                currentstatus = StatusDeviceTuya('fan_switch')
                                currentdim = brightness_to_pct(StatusProperties, 'fan_speed', int(StatusDeviceTuya('fan_speed')))
                                if bool(currentstatus) == False or currentdim == 0:
                                    UpdateDomoticz(dev_id, 4, False, 0, 0)
                                elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev_id].Units[4].sValue):
                                    UpdateDomoticz(dev_id, 4, True, 1, 0)
                                    UpdateDomoticz(dev_id, 4, currentdim, 1, 0)

                        if dev_type == 'smartlock':
                            if update_bool_device('lock_motor_state', 1):
                                pass
                            elif update_bool_device('rtc_lock', 1):
                                pass
                            update_select_device('alarm_lock', 2)
                            update_bool_device('unlock_ble', 3)
                            update_bool_device('unlock_card', 4)
                            battery_device()

                        if dev_type == 'dehumidifier':
                            update_bool_device('switch', 1)
                            if update_selectnum_device('dehumidify_set_value', 2):
                                pass
                            elif update_selectnum_device('dehumidify_set_enum', 2):
                                pass
                            update_select_device('fan_speed_enum', 3)
                            update_select_device('mode', 4)
                            update_value_device('fault', 5)
                            update_value_device('temp_indoor', 6)
                            update_nvalue_device('humidity_indoor', 7)
                            update_dualvalue_device('temp_indoor', 'humidity_indoor', 8)
                            update_bool_device('child_lock', 9)
                            update_bool_device('anion', 10)
                            update_bool_device('filter_reset', 11)
                            update_value_device('filter_life', 12)
                            update_bool_device('runtime_total_reset', 13)
                            update_value_device('type_of_equipment', 14)

                        if dev_type == 'vacuum':
                            update_bool_device('power_go', 1)
                            update_bool_device('switch_charge', 2)
                            update_select_device('mode', 3)
                            update_select_device('suction', 4)
                            update_select_device('cistern', 5)
                            update_text_device('status', 6)
                            update_value_device('electricity_left', 7)
                            update_value_device('edge_brush', 8)
                            update_value_device('roll_brush', 9)
                            update_value_device('filter', 10)
                            update_value_device('electricity_left', 7)
                            update_text_device('fault', 11)
                            battery_device

                        if dev_type == 'multifunctionalarm':
                            update_value_device('master_mode', 1)

                        if dev_type == 'purifier':
                            update_bool_device('switch', 1)
                            update_value_device('pm25', 2)
                            update_select_device('mode', 3)
                            update_select_device('speed', 4)
                            update_value_device('filter', 5)
                            update_value_device('air_quality', 6)

                        if dev_type == 'smartkettle':
                            update_bool_device('start', 1)
                            update_text_device('status', 2)
                            update_value_device('temperature', 3)
                            update_value_device('cook_temperature', 4)
                            update_text_device('fault', 5)

                        if dev_type == 'mower':
                            update_bool_device('MachineControlCmd', 1)
                            update_bool_device('MachineRainMode', 2)
                            update_select_device('MachineStatus', 3)
                            update_select_device('MachineWarning', 4)
                            update_select_device('MachineError', 5)
                            update_select_device('MachineWorkMode', 5)
                            battery_device()

                        if dev_type == 'human_presence':
                            update_bool_device('presence_state', 1, 'none')
                            update_selectnum_device('sensitivity', 2)
                            update_value_device('near_detection', 3)
                            update_value_device('far_detection', 4)
                            update_text_device('checking_result', 5)
                            update_value_device('target_dis_closest', 6)
                            update_select_device('presence_state', 10)

                        if dev_type == 'evcharger':
                            update_bool_device('switch', 1)
                            update_text_device('work_state', 2)
                            update_value_device('temp_current', 3)
                            update_value_device('power_total', 4)
                            update_value_device('charge_cur_set', 5)
                            update_value_device('forward_energy_total', 6)
                            update_text_device('online_state', 7)
                            # update_text_device('fault', 8)

                    except Exception as err:
                        DomoticzEx.Error(f"Device read failed: {dev.get('name', 'Unknown')} ({dev_id}) line {sys.exc_info()[-1].tb_lineno}")
                        DomoticzEx.Debug(f"handleThread: {err} line {sys.exc_info()[-1].tb_lineno}")

    except Exception as e:
        DomoticzEx.Error(str(e))
        DomoticzEx.Error(traceback.format_exc())

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            DomoticzEx.Debug(f"'{x}':'{Parameters[x]}'")
    DomoticzEx.Debug(f"Device count: {len(Devices)}")
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        DomoticzEx.Debug(f"Device Name:     '{getattr(Device, 'Name', Device.DeviceID)}'")
        DomoticzEx.Debug(f"--->Unit Count:      '{len(Device.Units)}'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            DomoticzEx.Debug(f"--->Unit:           {UnitNo}")
            DomoticzEx.Debug(f"--->Unit Name:     '{Unit.Name}'")
            DomoticzEx.Debug(f"--->Unit nValue:    {Unit.nValue}")
            DomoticzEx.Debug(f"--->Unit sValue:   '{Unit.sValue}'")
            DomoticzEx.Debug(f"--->Unit LastLevel: {Unit.LastLevel}")
    return

# Select device type from category
def DeviceType(category, product_id=None):
    'convert category to device type'
    'https://github.com/tuya/tuya-home-assistant/wiki/Supported-Device-Category'
    if product_id in {'uoa3mayicscacseb', 'igtakqsfhbr7qsp7'}:
        resultdev = 'cover'
    elif product_id in {'chfpey4klfcp1ipl'}:
        resultdev = 'dimmer'
    elif product_id in {'p6sqiuesvhmhvv4f'}:
        resultdev = 'doorcontact'
    elif category in {'kg', 'cz', 'pc', 'znjdq', 'szjqr', 'aqcz'}:
        resultdev = 'switch'
    elif category in {'tdq'}:
        resultdev = 'switch/sensor'
    elif category in {'dj', 'dd', 'dc', 'fwl', 'xdd', 'fwd', 'jsq', 'tyndj', 'tyd'}:
        resultdev = 'light'
    elif category in {'tgq', 'tgkg'}:
        resultdev = 'dimmer'
    elif category in {'cl', 'clkg', 'jdcljqr', 'mc'}:
        resultdev = 'cover'
    elif category in {'qn'}:
        resultdev = 'heater'
    elif category in {'wk', 'wkf', 'mjj', 'wkcz', 'kt','hwktwkq', 'ydkt', 'cjkg'}:
        resultdev = 'thermostat'
    elif category in {'wsdcg', 'co2bj', 'hjjcy', 'qxj', 'ldcg', 'swtz', 'zwjcy','pir','dgnbj','cobj', 'ywcgq'}:
        resultdev = 'sensor'
    elif category in {'rs'}:
        resultdev = 'heatpump'
    elif category in {'znrb'}:
        resultdev = 'smartheatpump'
    elif category in {'sp'}:
        resultdev = 'doorbell'
    elif category in {'fs'}:
        resultdev = 'fan'
    elif category in {'fsd'}:
        resultdev = 'fanlight'
    elif category in {'sgbj'}:
        resultdev = 'siren'
    elif category in {'wnykq'}:
        resultdev = 'smartir'
    elif category in {'zndb', 'dlq'}:
        resultdev = 'powermeter'
    elif category in {'wg2', 'wfcon'}:
        resultdev = 'gateway'
    elif category in {'mcs'}:
        resultdev = 'doorcontact'
    elif category in {'gyd'}:
        resultdev = 'pirlight'
    elif category in {'qt','ywbj'}:
        resultdev = 'smokedetector'
    elif category in {'ckmkzq'}:
        resultdev = 'garagedooropener'
    elif category in {'cwwsq'}:
        resultdev = 'feeder'
    elif category in {'sj'}:
        resultdev = 'waterleak'
    elif category in {'sfkzq'}:
        resultdev = 'irrigation'
    elif category in {'wxkg'}:
        resultdev = 'wswitch'
    elif category in {'xktyd'}:
        resultdev = 'starlight'
    elif category in {'ms','jtmspro'}:
        resultdev = 'smartlock'
    elif category in {'cs'}:
        resultdev = 'dehumidifier'
    elif category in {'sd'}:
        resultdev = 'vacuum'
    elif category in {'mal'}:
        resultdev = 'multifunctionalarm'
    elif category in {'kj'}:
        resultdev = 'purifier'
    elif category in {'bh'}:
        resultdev = 'smartkettle'
    elif category in {'gcj'}:
        resultdev = 'mower'
    elif category in {'hps'}:
        resultdev = 'human_presence'
    elif category in {'qccdz'}:
        resultdev = 'evcharger'
    elif category in {'infrared_ac'}:
        resultdev = 'infrared_ac'
    elif 'infrared_' in category: # keep it last
        resultdev = 'infrared'
    else:
        resultdev = 'unknown'
    return resultdev

def UpdateDomoticz(ID, Unit, sValue, nValue, TimedOut, AlwaysUpdate=0):

    if not checkDevice(ID, Unit):
        DomoticzEx.Debug(f"Device {ID} Unit {Unit} doesn't exist. Nothing to update")
        return

    unit = Devices[ID].Units[Unit]
    Name = Devices[ID].Units[Unit].Name

    # Detect color JSON explicitly
    is_color = False
    if isinstance(sValue, str):
        try:
            js = json.loads(sValue)
            if isinstance(js, dict) and 'm' in js:
                is_color = True
        except Exception:
            pass

    # Prevent unnecessary updates
    if (
        str(unit.sValue) == str(sValue)
        and str(unit.nValue) == str(nValue)
        and str(Devices[ID].TimedOut) == str(TimedOut)
        and not AlwaysUpdate
    ):
        return

    # Apply updates
    if sValue is not None:
        unit.sValue = str(sValue)

        if is_color:
            unit.Color = str(sValue)
        else:
            # numeric slider value
            try:
                unit.LastLevel = int(float(sValue))
            except Exception:
                pass

    unit.nValue = nValue
    Devices[ID].TimedOut = TimedOut
    unit.Update(Log=True)

    DomoticzEx.Log(f"Update device: {Name} Unit:{Unit} sValue:{sValue} nValue:{nValue} TimedOut={TimedOut}")

def StatusDeviceTuya(Function):
    if searchCode(Function, StatusProperties):
        valueRaw = [item['value'] for item in ResultValue if re.search(r'\b'+Function+r'\b', item['code']) != None][0]
    else:
        DomoticzEx.Debug(f"StatusDeviceTuya called {Function} not found ")
        return None
    if isinstance(valueRaw, (int, float)):
        valueT = get_scale(StatusProperties, Function, valueRaw)
    else:
        valueT = valueRaw
    return valueT

def SendCommandTuya(ID, CommandName, Status):
    sendfunction = properties[ID]['functions']
    if isinstance(CommandName, list):
        CommandName = CommandName[0] if CommandName else ''

    actual_function_name = CommandName
    actual_status = Status

    # Zoek juiste code
    for item in sendfunction:
        code = item.get('code', '')
        if CommandName == code:
            actual_function_name = code
            break
    else:
        for item in sendfunction:
            code = item.get('code', '')
            if code.startswith(f"{CommandName}_") or CommandName.startswith(f"{code}_"):
                actual_function_name = code
                break

    # Schaling (brightness, temp, numeric)
    if any(x in CommandName for x in ['bright_value', 'bright_value_v2', 'bright_value_1', 'bright_value_2', 'laser_bright']):
        actual_status = pct_to_brightness(sendfunction, actual_function_name, Status)
    elif any(x in CommandName for x in ['temp_value', 'temp_value_v2']):
        actual_status = temp_value_scale(sendfunction, actual_function_name, Status)
    elif isinstance(Status, (int, float)) and not isinstance(Status, bool):
        actual_status = set_scale(sendfunction, actual_function_name, Status)

    DomoticzEx.Debug(f"SendCommand: {ID} | {actual_function_name} = {actual_status}")

    # Get device name from devs list for all logging
    dev_name = next((d.get('name', 'Unknown') for d in devs if d.get('id') == ID), ID)

    #------ LOCAL TINYTUYA (non-blocking) ------
    if ID in localtuya and ID in dps_map:
        # prepare some values for immediate logging
        try:
            dp_id_preview = dps_map[ID]['by_code'].get(actual_function_name)
        except Exception:
            dp_id_preview = None

        # start background thread to avoid blocking Domoticz main loop
        def _do_send():
            try:
                dp_id = dps_map[ID]['by_code'].get(actual_function_name)
                if dp_id is None:
                    raise Exception(f"No dp_id for code {actual_function_name}")

                device_key = getConfigItem(ID, 'key')
                d = tinytuya.Device(
                    ID,
                    localtuya[ID]['ip'],
                    device_key
                )
                d.set_version(float(localtuya[ID].get('version', '3.3')))
                d.socketRetryLimit = 1
                d.socketRetryDelay = 1
                if hasattr(d, 'set_socketTimeout'):
                    d.set_socketTimeout(3)
                elif hasattr(d, 'set_timeout'):
                    d.set_timeout(3)
                elif hasattr(d, 'socketTimeout'):
                    d.socketTimeout = 3
                if hasattr(d, 'set_socketPersistent'):
                    d.set_socketPersistent(False)

                result = d.set_status(actual_status, int(dp_id))

                if not result or 'Error' in result or 'Err' in result:
                    raise Exception(result)

                DomoticzEx.Log(f"[LOCAL] Command sent: dp_id {dp_id} = {actual_status} ({dev_name})")
                return

            except Exception as e:
                DomoticzEx.Debug(f"[LOCAL FAILED] {dev_name}, fallback to cloud: {e}")
                # FALLBACK TO CLOUD (still in background)
                try:
                    if actual_function_name in ('PowerOff', 'PowerOn'):
                        uri = 'devices/'
                    else:
                        uri = 'iot-03/devices/'

                    if not testdata:
                        tuya.sendcommand(
                            ID,
                            {'commands': [{'code': actual_function_name, 'value': actual_status}]},
                            uri
                        )

                    DomoticzEx.Log(f"[CLOUD] Command sent to Tuya: {dev_name}, { {'commands': [{'code': actual_function_name, 'value': actual_status}]} }, {uri}")
                except Exception as ce:
                    DomoticzEx.Error(f"[CLOUD FAILED] {dev_name}: {ce}")

        threading.Thread(target=_do_send, daemon=True).start()
        DomoticzEx.Log(f"[LOCAL] Command queued: dp_id {dp_id_preview} = {actual_status} ({dev_name})")
        return

    #------ FALLBACK: TUYA CLOUD------
    if actual_function_name in ('PowerOff', 'PowerOn'):
        uri = 'devices/'
    else:
        uri = 'iot-03/devices/'

    if not testdata:
        tuya.sendcommand(
            ID,
            {'commands': [{'code': actual_function_name, 'value': actual_status}]},
            uri
        )

    DomoticzEx.Log(f"[CLOUD] Command sent to Tuya: {dev_name}, { {'commands': [{'code': actual_function_name, 'value': actual_status}]} }, {uri}")

def pct_to_brightness(device_functions, actual_function_name, pct):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min', 0))
                max_value = int(the_values.get('max', 1000))
                # DomoticzEx.Debug(round(min_value + (pct*(max_value - min_value)) / 100))
                return round(min_value + (pct*(max_value - min_value)) / 100)
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round(22.68 + (int(pct) * ((255 - 22.68) / 100)))

def brightness_to_pct(device_functions, actual_function_name, raw):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min', 0))
                max_value = int(the_values.get('max', 255))
                return round((100 / (max_value - min_value) * (int(raw) - min_value)))
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round((100 / (255 - 22.68) * (int(raw) - 22.68)))

def temp_value_scale(device_functions, actual_function_name, raw):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min', 0))
                max_value = int(the_values.get('max', 255))
                return round((255 / (max_value - min_value) * (int((max_value - raw)) - min_value)))
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round((int(max_value - raw)))

def set_scale(device_functions, actual_function_name, raw):
    scale = 0
    try:
        if device_functions and actual_function_name:
            for item in device_functions:
                if item['code'] == actual_function_name:
                    the_values = json.loads(item['values'])
                    scale = int(the_values.get('scale', 0))
                    # step = the_values.get('step', 0)
                    max = the_values.get('max', 0)
                    min = the_values.get('min', 0)
        if scale == 1:
            resultscale = int(raw * 10)
        elif scale == 2:
            resultscale = int(raw * 100)
        elif scale == 3:
            resultscale = int(raw * 1000)
        else:
            resultscale = int(raw)
        if product_id == 'IAYz2WK1th0cMLmL':
            resultscale = int(raw * 2)
        if resultscale > max:
            resultscale = int(max)
            DomoticzEx.Log('Value higher then maximum device')
        elif resultscale < min:
            resultscale = int(min)
            DomoticzEx.Log('Value lower then minium device')
    except:
        resultscale = str(raw)
    return resultscale

def get_scale(device_functions, actual_function_name, raw):
    scale = 0
    # if actual_function_name == 'temp_current': actual_function_name = 'temp_set'
    try:
        if device_functions and actual_function_name:
            for item in device_functions:
                if item['code'] == actual_function_name:
                    the_values = json.loads(item['values'])
                    scale = the_values.get('scale', 0 )
                    # step = the_values.get('step', 0)
                    unit = the_values.get('unit', 0)
                    max = the_values.get('max', 0)
        if scale == 0:
            if unit == 'V' and len(str(max)) >= 4:
                resultscale = float(raw / 10)
            elif unit == 'W' and len(str(max)) >= 5:
                resuresultscalelt = float(raw / 10)
            else:
                resultscale = int(raw)
        elif scale == 1:
            resultscale = float(raw / 10)
        elif scale == 2:
            resultscale = float(raw / 100)
        elif scale == 3:
            resultscale  = float(raw / 1000)
        else:
            resultscale = int(raw)
        if product_id == 'IAYz2WK1th0cMLmL':
            resultscale = float(raw / 2)
        if product_id == 'g9m7honkxjweukvt' and actual_function_name == 'temp_current':
            resultscale = float(raw / 10)
        if unit == 'm':
            resultscale = float(resultscale * 100)
    except:
        resultscale = raw
        DomoticzEx.Debug(f"Scale device:{actual_function_name} Value: {resultscale}")
    return resultscale

def get_unit(actual_function_name, device_functions):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                resultunit = the_values.get('unit', 0)
    return resultunit

def rgb_to_hsv(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h = int(h * 360)
    s = int(s * 255)
    v = int(v * 255)
    return h, s, v

def rgb_to_hsv_v2(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h = int(h * 360)
    s = int(s * 1000)
    v = int(v * 1000)
    return h, s, v

def hsv_to_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h / 360, s / 255, v / 255)
    r = round(r * 255)
    g = round(g * 255)
    b = round(b * 255)
    return r, g, b

def hsv_to_rgb_v2(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h / 360, s / 1000, v / 1000)
    r = round(r * 255)
    g = round(g * 255)
    b = round(b * 255)
    return r, g, b

def get_draw_tool_max_value(DeviceID):
    """Detect the max value (255 or 1000) for draw_tool brightness from device result"""
    try:
        bright_value = StatusDeviceTuya('bright_value')
        if bright_value and int(bright_value) == 1000:
            return 1000

        result_data = StatusDeviceTuya('draw_tool')
        if result_data:
            decoded = decode_draw_tool_status(result_data, 1)
            if decoded:
                return 1000
        return 255
    except Exception:
        return 255


def send_draw_tool_command(DeviceID, led_index, r, g, b, brightness, max_value=255):
    encoded_command = encode_draw_tool_command(led_index, r, g, b, brightness, max_value=max_value)
    DomoticzEx.Log(f"Multi-LED: Attempting local send for LED {led_index}")
    if send_draw_tool_command_local(DeviceID, encoded_command):
        DomoticzEx.Log(f"Multi-LED: Local send succeeded for LED {led_index}")
        return True

    DomoticzEx.Log(f"Multi-LED: Local send failed, fallback to cloud for LED {led_index}")
    # Fallback to cloud via SendCommandTuya
    SendCommandTuya(DeviceID, 'draw_tool', encoded_command)
    return False


def send_draw_tool_command_local(DeviceID, encoded_command):
    try:
        device_ip = getConfigItem(DeviceID, 'ip')
        device_key = getConfigItem(DeviceID, 'key')
        device_version = getConfigItem(DeviceID, 'version')
        if not device_ip or not device_key:
            return False

        device = tinytuya.OutletDevice(str(DeviceID), str(device_ip), str(device_key))
        if device_version and device_version != 'unknown':
            try:
                device.set_version(float(device_version))
            except ValueError:
                device.set_version(3.3)
        else:
            device.set_version(3.3)

        payload_data = encoded_command
        payload = device.generate_payload(tinytuya.CONTROL, {'20': True, '21': 'colour', '59': payload_data})
        device._send_receive(payload)
        return True
    except Exception as e:
        DomoticzEx.Debug(f"Local draw_tool send failed for {DeviceID}: {e}")
        return False


def encode_draw_tool_command(led_index, r, g, b, brightness, max_value=255):
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    brightness = max(0, min(100, brightness))

    h, s, v = rgb_to_hsv_v2(r, g, b)
    hue_hi = (h >> 8) & 0xFF
    hue_lo = h & 0xFF
    sat = max(0, min(100, int(round(s / 10))))
    brightness_hex = format(brightness, '02x')

    hex_string = f"010201{hue_hi:02x}{hue_lo:02x}{sat:02x}{brightness_hex}00008100{led_index:02x}"

    DomoticzEx.Log(f"Draw Tool: LED {led_index}, RGB({r},{g},{b}), Brightness {brightness}, HSV({h},{s},{v}), Hex: {hex_string}")

    try:
        byte_data = bytes.fromhex(hex_string)
        encoded = base64.b64encode(byte_data).decode('utf-8')
        DomoticzEx.Log(f"Draw Tool: Encoded command: {encoded}")
        return encoded
    except Exception as e:
        DomoticzEx.Debug(f"Error encoding draw_tool: {e}")
        return "AQIBAAAAAGQA"

def decode_draw_tool_status(base64_data, expected_led_count):
    result = {}
    try:
        byte_data = base64.b64decode(base64_data)
        data = bytes(byte_data)
        DomoticzEx.Debug(f"Draw_tool hex data: {data.hex()}")

        def hsv_to_led(hue, sat, brightness):
            r, g, b = hsv_to_rgb_v2(hue, sat * 10, brightness * 10)
            return {
                'on': brightness > 0,
                'brightness': brightness,
                'color': {'r': r, 'g': g, 'b': b}
            }

        if len(data) >= 12 and data[0] == 0x01 and data[1] == 0x02:
            # Per-LED frame (12 bytes each): 01 02 effect hue_hi hue_lo sat brightness white 00 81 00 spot
            for offset in range(0, len(data) - 11):
                if data[offset] != 0x01 or data[offset + 1] != 0x02:
                    continue
                if offset + 12 > len(data):
                    continue
                frame = data[offset:offset + 12]
                hue = (frame[3] << 8) | frame[4]
                sat = frame[5]
                brightness = frame[6]
                spot = frame[11]
                if spot not in result:
                    result[spot] = hsv_to_led(hue, sat, brightness)
        elif len(data) >= 9 and data[0] == 0x01 and data[1] == 0x01:
            # All-LED frame: 01 01 [effect] hue_hi hue_lo sat white brightness [trailing]
            hue = (data[3] << 8) | data[4]
            sat = data[5]
            b0, b1 = data[6], data[7]
            if b1 > 0:
                brightness, white = b1, b0
            else:
                brightness, white = b0, b1
            led_info = hsv_to_led(hue, sat, brightness)
            for spot in range(0, expected_led_count):
                if spot not in result:
                    result[spot] = dict(led_info)

    except Exception as e:
        DomoticzEx.Debug(f"Error decoding draw_tool data: {e}")

    return result

def get_led_color(device_id, unit_number):
    try:
        if device_id in Devices and unit_number in Devices[device_id].Units:
            s_value = Devices[device_id].Units[unit_number].sValue
            if s_value and ',' in s_value:
                parts = s_value.split(',')
                if len(parts) >= 3:
                    return {
                        'r': int(parts[0]),
                        'g': int(parts[1]),
                        'b': int(parts[2])
                    }
    except Exception as e:
        DomoticzEx.Debug(f"Error getting LED color: {e}")

    return {'r': 255, 'g': 255, 'b': 255}

def inv_pct(v):
    return 100 - v

def inv_val(v):
    return 255 - v

def rgb_temp(t,v):
    return int((t / 100) * v)

def temp_cw_ww(t):
    cw = t
    ww = 255 - t
    return cw, ww

def nextUnit(ID):
    unit = 1
    while unit in Devices[ID] and unit < 255:
        unit = unit + 1
    return unit

def checkDevice(Id, Unit):
    try:
        Devices[Id].Units[Unit]
        return True
    except:
        return False

def searchCode(Item, Function):
    if searchCodeActualFunction(Item, Function) is None:
        return False
    return True

def searchValue(Item, Function):
    ActualItem = searchCodeActualFunction(Item, Function)
    if not ActualItem:
        return 0

    # JSON-string → object
    if isinstance(Function, str):
        try:
            Function = json.loads(Function)
        except json.JSONDecodeError:
            return 0

    for Elem in Function:
        if isinstance(Elem, dict) and str(ActualItem) == str(Elem.get('code')):
            return Elem.get('value', 0)

    return 0

def searchCodeActualFunction(Item, Function):
    if not Function:
        return None

    # JSON-string → object
    if isinstance(Function, str):
        try:
            Function = json.loads(Function)
        except json.JSONDecodeError:
            return None

    # Expected: list of dicts
    if isinstance(Function, list):
        for OneItem in Function:
            if isinstance(OneItem, dict) and str(Item) == str(OneItem.get('code')):
                return OneItem.get('code')

    return None

def createDevice(ID, Unit):
    if ID in Devices:
        if Unit in Devices[ID].Units:
            value = False
        else:
            value = True
    else:
        value = True
    return value

def deleteDevice(ID, Unit):
    if ID in Devices:
        try:
            name = Devices[ID].Units[Unit].Name
        except Exception:
            name = getattr(Devices[ID], 'Name', ID)
        DomoticzEx.Log(f"Deleting device '{name}' Unit {Unit}.")
        Devices[ID].Units[Unit].Delete()
    else:
        DomoticzEx.Debug(f"Device with ID {ID} not found. Cannot delete.")

def updateDevice():
    templates = [
        {'name_suffix': ' (dehumidify)', 'unit': 2, 'dtype': 244, 'subtype': 62, 'switchtype': 18, 'image': 11},
        {'name_suffix': ' (dehumidify)', 'unit': 2, 'dtype': 242, 'subtype': 1, 'image': 11},
    ]

    def _matches_template(dev, tpl):
        try:
            if 'name_suffix' in tpl and not dev.Name.endswith(tpl['name_suffix']):
                return False
            if 'unit' in tpl and int(dev.Unit) != int(tpl['unit']):
                return False
            if 'dtype' in tpl and int(dev.Type) != int(tpl['dtype']):
                return False
            if 'subtype' in tpl and int(dev.SubType) != int(tpl['subtype']):
                return False
            if 'switchtype' in tpl and int(dev.SwitchType) != int(tpl['switchtype']):
                return False
            if 'image' in tpl and int(dev.Image) != int(tpl['image']):
                return False
            return True
        except Exception:
            return False
    for idx, dev in list(DomoticzEx.Devices.items()):
        for tpl in templates:
            if _matches_template(dev, tpl):
                DomoticzEx.Log(f"Removing device matching template: idx={idx} Name='{dev.Name}'")
                try:
                    DomoticzEx.Device(Unit=dev.Unit, DeviceID=dev.DeviceID).Delete()
                except Exception:
                    try:
                        DomoticzEx.Device(idx).Delete()
                    except Exception as e:
                        DomoticzEx.Log(f"Failed to remove device idx {idx}: {e}", DomoticzEx.ERROR)
                break
    return

def is_battery_device(StatusProperties):
    """Check if device has battery-related properties with type safety."""
    if isinstance(StatusProperties, str):
        # Search directly in the string
        battery_codes = [
            'battery_state',
            'battery',
            'va_battery',
            'battery_percentage',
            'residual_electricity'
        ]
        return any(code in StatusProperties.lower() for code in battery_codes)

    elif isinstance(StatusProperties, (dict, list)):
        # Handle dictionary or list (Tuya's StatusProperties is in practice
        # almost always a list of {'code':..., 'value':...} dicts -- the
        # original code only checked for dict here, so it silently fell
        # through to `return False` for every real device, meaning is_battery_device()
        # never correctly recognized a battery device. searchCode() already
        # handles lists correctly, so this one-word fix is enough.
        return any(
            searchCode(code, StatusProperties)
            for code in (
                'battery_state',
                'battery',
                'va_battery',
                'battery_percentage',
                'residual_electricity'
            )
        )

    return False

# Configuration Helpers
def getConfigItem(Key=None, Values=None):
    Value = {}
    try:
        Config = DomoticzEx.Configuration()
        if (Key != None):
            # DomoticzEx.Debug(Config[Key][Values])
            Value = Config[Key][Values]  # only return requested key if there was one
        else:
            Value = Config      # return the whole configuration if no key
    except KeyError:
        Value = {}
    except Exception as inst:
        DomoticzEx.Error(f"DomoticzEx.Configuration read failed: {inst}")
    return Value

def setConfigItem(Key=None, Value=None):
    Config = {}
    try:
        Config = DomoticzEx.Configuration()
        if (Key != None):
            Config[Key] = Value
        else:
            Config = Value  # set whole configuration if no key specified
        Config = DomoticzEx.Configuration(Config)
    except Exception as inst:
        DomoticzEx.Error(f"DomoticzEx.Configuration operation failed: {inst}")
    return Config

def version(ver):
    return tuple(map(int, (ver.split('.'))))