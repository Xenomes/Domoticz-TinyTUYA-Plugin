# Domoticz-TinyTUYA-Plugin

TUYA plugin for Domoticz home automation.

This plugin provides **hybrid local (LAN) and cloud-based control** for Tuya devices.
Whenever possible, devices are controlled **locally using TinyTuya**, with automatic
fallback to the **Tuya IoT Cloud** when local communication is not available.

The Tuya Cloud is primarily used for **initial device discovery, DPS mapping and configuration**.

> ## **⚠️ IMPORTANT WARNING - Version 3.0+ Update**
>
> This is version **3.0+** (Hybrid version) which is a **major update** from version 2.* (Cloud version).
> Devices may behave differently after updating:
>
> - **Architecture change**: Version 3.* uses hybrid local/cloud control instead of cloud-only
> - **Device detection**: Device type detection has been improved and may reclassify some devices
> - **Local control**: Devices will now try to communicate locally first, falling back to cloud if unavailable
> - **Performance**: Response times are generally faster due to local communication
> - **Network requirements**: Devices must be on the same network for optimal local control
> - **Device re-creation**: Some devices may need to be recreated if they were incorrectly classified in version 2.*
>
> **Recommendation**: After updating, verify all devices are working correctly. Some devices may need to be recreated if they show unexpected behavior.
>
> ### Devices created empty after the update?
>
> Some unit numbers differ from 2.*: the weather station barometer and rain are units 75 and 76 (81 and 82
> in 2.4.5), the liquid sensors 72-74 (70-72). Domoticz tells devices apart by unit number, so those come
> back as new, empty devices next to the old ones, which keep the history.
>
> Domoticz can move the history across: **Setup → Devices**, select the **old** device, press **Replace**
> and point it at the new one. The old idx keeps its history and takes over the new unit, and the duplicate
> disappears. Device types have to match, which they do in these cases. Scripts that refer to the device by
> idx or by name keep working, since it is the old device that survives.
>
> ### Update fails? (git pull error)
>
> If `git pull` gives an error (for example about local changes, divergent branches,
> or a dirty working tree), you can force your local copy to match the latest
> version from GitHub.
>
> Run these commands in the plugin folder:
>
> ```bash
> cd ~/domoticz/plugins/Domoticz-TinyTUYA-Plugin
> git fetch
> git reset --hard origin/master
> ```
---

## Features

- Automatic discovery of Tuya devices via Tuya IoT Cloud
- Automatic DPS (data point) detection and mapping
- Local LAN control using TinyTuya (fast and reliable)
- Automatic fallback to Tuya Cloud when devices are not reachable locally
- On/Off control, dimming, color temperature and device-specific features
- Cached cloud status to reduce API usage
- Configurable **API polling interval** and **IP scan interval**
- **Realtime push updates** via Tuya Pulsar (optional, requires `tuya-connector-python`)
  - Automatic fall-back to polling when Pulsar is not available
  - Pulsar updates are automatically skipped for locally reachable devices to prioritize LAN communication
- **Cloud usage tracking**: daily counters for API calls and Pulsar messages, with week/month totals, a month forecast and warning thresholds
- **Two 'credits' Custom Sensor devices** per hardware instance showing month-to-date API calls and Pulsar messages
- **Extended logging**: every LAN and Pulsar message is logged with the device name, DP code and value; TinyTuya error codes are translated with a hint
- **Realtime devices overview** at startup: which devices are covered by Pulsar, which are missing in Domoticz, and which are orphaned

---

## Installation / Updating

This plugin uses the **TinyTuya** project.
A **Tuya IoT Cloud Platform account** is required for initial setup.

Cloud setup instructions:

- https://github.com/jasonacox/tinytuya (step 3)
- PDF: https://github.com/jasonacox/tinytuya/files/12836816/Tuya.IoT.API.Setup.v2.pdf

### Optional: Realtime Push Updates

For **realtime device status updates** via Tuya Pulsar (push notifications instead of polling):

```bash
pip3 install tuya-connector-python #--break-system-packages # if needed
```

This is optional - the plugin will automatically fall back to regular polling if this package is not installed.

> For best compatibility, set your devices to **"DP instruction"**
> in the device settings on https://iot.tuya.com

---

## Installation Native Domoticz
Go in your Domoticz directory using a command line and open the plugins directory.
```bash
cd ~/domoticz/plugins
sudo pip3 install tinytuya cryptography>=3.1 pycryptodomex -U #--break-system-packages # if needed
# for installing
git clone https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git
# for updating
git pull
```
Restart Domoticz.

Alternative and better is to make use of Python Virtual Environment, install the modules in that environment and add the definition for the PYTHONPATH environment variable in the script which automatically starts Domoticz.
See for instructions (written for the Zigbee4Domoticz but could be used for any plugin): https://zigbeefordomoticz.github.io/wiki/en-eng/HowTo_PythonVirtualEnv.html

## Installation Domoticz Docker

```bash
cd <your-domoticz-docker>/plugins
# for installing
git clone https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git
# for updating
git pull
```
Add the next lines to your customstart.sh file after the 'apt-get -qq update' command.
```bash
echo 'install tinytuya'
pip3 install tinytuya cryptography>=3.1 pycryptodomex -U
```
Docker configuration (IMPORTANT)
When running Domoticz Docker:
--host mode is necessary for device scanning and caching all outputs.
Use environment variables to set the web ports instead of -p 8088:8080 -p 443:443:
```bash
--network host \
-e WWW_PORT=8080 \
-e SSL_PORT=443 \
```
Default ports are 8080 (HTTP) and 8443 (HTTPS). Change them to your preferred ports instead."
Example docker-compose.yml snippet:
```bash
services:
  domoticz:
    container_name: domoticz
    image: domoticz/domoticz:latest
    network_mode: "host"        # Needed for device scanning
    environment:
      - WWW_PORT=8080
      - SSL_PORT=443
    volumes:
      - ./config:/opt/domoticz/userdata
```
Rebuilt the Domoticz Docker container.
```bash
docker compose down
docker compose up -d
```
* Monitor the install this can take some time. ```docker logs -f --tail 0 domoticz```

## Configuration

In the Domoticz hardware configuration, enter:

- **Region**
- **Access ID / Client ID**
- **Access Secret / Client Secret**
- **Search Device ID**
  - Used only to discover all devices
  - Found in Tuya IoT Platform:
    Cloud → Project → Devices → select any device

### Important settings

- **API Polling Interval**
  - Recommended: **900 seconds (15 minutes)**

- **IP Scan Interval**
  - Defines how often device IP addresses are refreshed
  - Default: **86400 seconds (24 hours)**

- **Data Timeout**
  - Keep this **disabled**

After initial setup, the plugin minimizes cloud usage and prefers local LAN control.

---

## Usage

1. Open the Domoticz web interface
2. Go to **Hardware**
3. Add a new hardware device
4. Select **TinyTUYA**
5. Configure and add

Devices will be created automatically after discovery.

## Local connection (LAN)

Devices that answer on the LAN are not opened and closed on every cycle: the plugin keeps one connection
open to each of them with its local key. What a device reports there - the replies to a status query and
the pushes it sends by itself when something changes - is picked up as it arrives, so a change made on the
device shows up in Domoticz within seconds instead of at the next poll.

There is nothing to configure. A device is connected once the IP scan has found it and its local key is
known from the cloud, which also means Domoticz has to sit in the same network segment as the devices:
the scan listens for their UDP broadcasts. A device that does not answer locally - out of range, a battery
device asleep, one behind a gateway - is read from the cloud at the API polling interval, exactly as before.

Two lines in the log tell you where a device stands:

| Line | Meaning |
|---|---|
| `Local connection to X established` | the connection is open and X is reporting |
| `Local connection to X lost: ...` | the connection dropped, with the reason; the plugin reconnects by itself |
| `X sends every value its units read over the LAN, leaving it out of the cloud poll` | X costs no API calls for as long as that holds |
| `X is back in the cloud poll: ...` | with the reason - either a value only the cloud brings, or the connection is gone |
| `Skipping local listener for X (v3.1: single-connection protocol)` | see *Protocol v3.1 devices* below |

The timing is set by four constants at the top of `plugin.py`. The defaults suit a normal home network and
are worth changing only if yours is unusual:

| Constant | Default | What it does |
|---|---|---|
| `LOCAL_BEAT` | 20 s | heartbeat that keeps the connection open - devices drop it around 30 s after the last packet from the client, and their own pushes do not count towards that |
| `LOCAL_REFRESH` | 300 s | how often the full status is read again over the same connection |
| `LOCAL_RETRY` | 60 s | pause before reconnecting after a connection is lost |
| `LOCAL_TIMEOUT` | 5 s | socket timeout |

A value a device does not send locally keeps whatever the cloud last gave it. Each connection starts with
an empty set of values, so right after a reconnect a device has only what it has re-sent since.

### Devices that stop costing API calls

A device whose connection delivers every value its own Domoticz units read is left out of the cloud poll
while that holds: reading it from the cloud would bring nothing new. Only the values the units actually
read are counted, so the spare channels a device reports but nobody displays - the empty extra sensor
slots of a weather station, for instance - do not keep it in the poll. As soon as something is missing,
the connection drops, or a device reconnects and has not re-sent everything yet, it is read from the cloud
again; each change is in the log with its reason.

Nothing has to be configured for this, and the polling interval still applies to every device the LAN does
not cover.

### Protocol v3.1 devices

A v3.1 device accepts only one TCP connection at a time. A permanent listener would hold the only slot,
and the short-lived socket used to send a command would then be accepted but silently ignored - no error,
the device just does not act. Those devices therefore get no listener: they are polled and controlled
through the same short-lived socket, as they were before. You can tell which protocol a device speaks from
the IP scan lines in the log.

---

## Refresh button (optional)

To stay within the API quota the polling interval is usually long, so a change made on the device itself or in the Tuya app shows up in Domoticz only at the next poll. For the device IDs entered in **Refresh button for device IDs** (comma separated) the plugin adds a push button "*device name* (Refresh)". Pressing it reads just that device from the cloud (2 API calls) and updates its units right away; the regular polling interval is not affected. With the field left empty nothing changes.

The button is meant to be pressed by something outside the plugin, for example:
* a dzVents script: ```domoticz.devices('Irrigation controller (Refresh)').switchOn()```
* the JSON API: ```http://<domoticz>:8080/json.htm?type=command&param=switchlight&idx=<idx of the button>&switchcmd=On```

The buttons are created when the plugin starts, so press Update on the Hardware page after changing the field; "Accept new Hardware Devices" must be enabled in the Domoticz settings at that moment.

[examples/refresh-button](examples/refresh-button) shows how to press the button whenever an OpenWrt router sees the device talk to the Tuya cloud: an nftables counter, a small script on the router and a dzVents script.

---

## Cloud usage / credits

Tuya Cloud has a monthly budget per account. The plugin keeps its own counters so you can see how much
of it *this* plugin is using, without having to open the Tuya console.

### The two 'credits' devices

On startup the plugin creates two **Custom Sensor** devices per hardware instance:

| Device | Unit | Shows |
|---|---|---|
| `<hardware name> API Credits` | 1 | API calls sent to Tuya **this month** |
| `<hardware name> Message Credits` | 2 | Pulsar messages received **this month** |

They live under `DeviceID = CloudCredits`, which can never collide with a real Tuya device ID (those are
long alphanumeric strings). Renaming them in the Domoticz UI is fine - the plugin addresses them by
DeviceID/Unit, never by name.

The values are refreshed **once an hour**, so the `LastUpdate` on the tile also tells you the plugin is
alive. The counters are stored in the plugin configuration and survive a Domoticz restart.

> **Bar Ranges are not set by the plugin.** That Domoticz feature is very recent and its internal storage
> format could not be verified, so setting it blind would risk silently doing nothing. Set it once by hand
> if you want the bar-chart indicator on the Dashboard:
> **Setup → Devices → edit the device → bar-chart icon**, and enter your own ranges (e.g. 0–10000, 10000–20000,
> 20000–30000 for the API credits). It is saved with the device and survives restarts.

### What the counters do and do not cover

The counters count only what **this plugin** sends and receives. Other tools or projects on the same
Tuya Cloud account are not included, so the Tuya console (*Cloud → Usage*) can show a higher number than
the credits devices do.

The plugin counts every HTTP request that goes through `tinytuya.Cloud._tuyaplatform()`, which covers
token refreshes, device list, status reads and commands. On very old tinytuya versions that method does
not exist, and the plugin falls back to counting public method calls, which can be *lower* than what
Tuya actually bills.

### Midnight report and month forecast

Every night at 00:00 the plugin logs a `Status`-level report with:

- the **final totals** of the day that just ended (API calls and Pulsar messages)
- the number of **Tuya devices** against the account maximum (`50`), with a warning when you are close
- the **month forecast**: how much was used through yesterday, the average per day, the expected month
  total and - if a shortage is expected - the date the maximum is likely to be reached

On the first of the month the report shows the **final result of the month that just ended** instead of a
forecast, since there is no complete day of data yet for the new month.

Warnings are repeated as an `Error` line, so they show up in red in the Domoticz log.

An **INFO summary** is logged once an hour with the current day/week/month totals:

```
Tuya cloud usage - API calls: today 42, this week 310, this month 1240 |
Pulsar messages: today 8, this week 55, this month 210
```

### Tuning

The limits and thresholds are constants at the top of `plugin.py`:

| Constant | Default | Meaning |
|---|---|---|
| `USAGE_LIMITS` | `{'api': 30000, 'msg': 140000}` | monthly maximums of the Tuya account |
| `USAGE_MAX_DEVICES` | `50` | maximum number of Tuya devices per account |
| `USAGE_WARN_FRACTION` | `0.9` | fraction of the maximum from which a forecast is reported as a warning |
| `USAGE_KEEP_DAYS` | `100` | how many days of history are kept in the configuration |
| `USAGE_SAVE_INTERVAL` | `60` | seconds between writes of the counter store (throttled) |
| `USAGE_LOG_INTERVAL` | `3600` | seconds between the hourly INFO summaries |
| `USAGE_DEVICE_UPDATE_INTERVAL` | `3600` | seconds between credits-device updates |

Change them to match your Tuya subscription tier.

---

## Logging

From version 3.2.0 the plugin logs every message it sends or receives, so you can see exactly what is
happening without enabling full debug mode.

### LAN messages

Every message arriving from a device over the LAN is logged at **INFO** level with the device name, the
IP, what kind of message it is, and the data points it contains:

```
Local message from Living room light (bf1234...) at 192.168.1.42 [pushed by device]:
switch_led (DP 20) = true, bright_value_v2 (DP 22) = 750
```

The `[...]` part says where the message came from:

| Source | Meaning |
|---|---|
| `status reply on connect` | the first status read after the connection opens |
| `periodic status reply` | the full status read every `LOCAL_REFRESH` seconds |
| `heartbeat reply` | the answer to the keep-alive heartbeat |
| `pushed by device` | the device reporting a change on its own |
| `status reply, single query` | a one-off status read outside the persistent connection |
| `status reply to wake-up ping` | the answer to the battery-device wake-up ping |

Values longer than 80 characters (e.g. base64 blobs from LED strips or cameras) are shortened with a
`... (N chars)` suffix.

### Pulsar messages

Every message arriving via Tuya Pulsar is logged at **INFO** level **before** the plugin decides what to
do with it, in both supported shapes (legacy `status` and IoT Core `bizData`):

```
Pulsar message from Front door (bf1234...) [property report, bizCode devicePropertyMessage]:
doorcontact_state = true
Pulsar message from Living room light (bf1234...) [status update]:
switch_led = true -- will be ignored, device is reachable locally at 192.168.1.42
```

The trailing note tells you whether the plugin will act on the message or not.

### TinyTuya error codes

When a device answers with an error instead of data, the plugin translates the TinyTuya error code into
plain language and adds a hint. The first occurrence per device and per error code is logged at **ERROR**
level; repeats within the next hour go to **Debug** level, so a device with a permanent problem does not
fill the log every cycle.

| Code | Meaning | Hint |
|---|---|---|
| 901 | network error, could not connect | check that the device is powered and reachable on the LAN |
| 902 | timeout, no answer from device | device may be offline, asleep or busy with another connection |
| 904 | unexpected payload, could not decode the answer | check the device key and protocol version |
| 905 | device unreachable (no route to host) | check that the IP address is still correct, rescan the LAN |
| 914 | answer could not be decrypted | the device was probably re-paired (new local key) or the protocol version is wrong; refresh the device data from the cloud and check the version with `python3 -m tinytuya scan` |

### Realtime devices overview at startup

When the Pulsar listener starts, the plugin logs a short overview of the devices that are covered by the
realtime fast path (door contacts, motion sensors and doorbells):

```
Realtime (Pulsar) updates active for 3 device(s):
  - OK: Front door (bf1234...) [door contact]
  - OK: Hallway motion (bf5678...) [motion sensor]
  - OK: Driveway doorbell (bf9012...) [doorbell (multiple units)]
MISMATCH: 1 device(s) known to Tuya, but not yet created in Domoticz (will appear after the next regular poll):
  - Garden motion (bf3456...) [motion sensor]
MISMATCH: 1 orphaned device(s) found in Domoticz (present here, but Tuya no longer reports this ID -- likely after re-pairing/resetting the physical device):
  - Old kitchen door (bf0000...)
```

The three categories mean:

| Category | Meaning |
|---|---|
| **OK** | Tuya reports it and Domoticz has it: realtime updates apply correctly |
| **not yet created in Domoticz** | Tuya reports it but Domoticz has not created the device yet, e.g. right after startup before the first poll has run |
| **orphaned in Domoticz** | Domoticz has a device whose ID Tuya no longer reports at all - typically after a re-pair or factory reset, the old device stops receiving updates and can be removed manually |

### Date format

Dates in log lines and reports follow the locale of the system Domoticz runs on (e.g. `28-09-2026` on a
Dutch system). Without a usable system locale the ISO format is used, since the C/POSIX default is the
ambiguous US format.

---

## Test Devices

Testing has been primarily done with **RGBWW light**.

If functionality is missing for your device:

1. Run `debug_discovery.py` from the `tools` directory
2. Provide the generated JSON data
3. Open an issue on GitHub

---

## Subscription Expired

If your Tuya Cloud development subscription has expired, you can extend it here:

https://iot.tuya.com/cloud/products/apply-extension

---

Support development:

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/xenomes)