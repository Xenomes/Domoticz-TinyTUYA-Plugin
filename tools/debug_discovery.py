#!/usr/bin/env python3

import json
import os
import sys
import time

try:
    import tinytuya
except Exception:
    print("tinytuya not installed")
    sys.exit(1)

CRED_CANDIDATES = ["tuya_creds.json", "cred.json", "creds.json"]


# -------------------------
# Credential handling
# -------------------------

def load_credentials():
    for path in CRED_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r") as fh:
                data = json.load(fh)
                creds = {
                    "apiRegion": data.get("apiRegion") or data.get("REGION"),
                    "apiKey": data.get("apiKey") or data.get("APIKEY"),
                    "apiSecret": data.get("apiSecret") or data.get("APISECRET"),
                    "apiDeviceID": data.get("apiDeviceID") or data.get("DEVICEID"),
                }
                if None not in creds.values():
                    return creds, path
        except Exception:
            pass
    return None, None


def save_credentials(creds, path="tuya_creds.json"):
    with open(path, "w") as fh:
        json.dump(creds, fh, indent=2)
    os.chmod(path, 0o400)
    return path


def prompt_for_credentials(existing=None):
    if existing is None:
        existing = {}

    try:
        creds = {
            "apiRegion": input("Tuya region (cn, eu, us): "),
            "apiKey": input("Tuya API key: "),
        }

        try:
            import getpass
            creds["apiSecret"] = getpass.getpass("Tuya API secret (hidden): ")
        except Exception:
            creds["apiSecret"] = input("Tuya API secret: ")

        creds["apiDeviceID"] = input("Tuya Device ID: ")
        return creds

    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(1)


# -------------------------
# Helpers
# -------------------------

def safe_json(obj):
    """JSON-serialiseerbaar maken, nooit crashen."""
    try:
        return json.dumps(obj, indent=2, default=str)
    except Exception:
        return json.dumps(str(obj), indent=2)


def write_block(fh, title, data):
    fh.write(f"\n{title}\n")
    fh.write(safe_json(data))
    fh.write("\n")


def is_sub_device(d):
    """IR-devices, hubs en andere sub-devices hebben geen eigen WiFi radio."""
    if d.get("sub") is True:
        return True
    if d.get("category") in ("infrared_ac", "infrared_tv", "wnykq"):
        return True
    # Geen MAC en geen sn => vrijwel zeker sub-device / virtueel
    if not d.get("mac") and not d.get("sn"):
        return True
    return False


# -------------------------
# Load credentials
# -------------------------

creds, cred_path = load_credentials()
if creds:
    print(f"Loaded credentials from {cred_path}")
else:
    print("No valid credentials found, prompting…")
    creds = prompt_for_credentials()
    save_credentials(creds)

REGION = creds["apiRegion"]
APIKEY = creds["apiKey"]
APISECRET = creds["apiSecret"]
DEVICEID = creds["apiDeviceID"]

# -------------------------
# Tunables
# -------------------------
SLEEP_BETWEEN_CALLS = 0.3     # pauze tussen cloud API-calls binnen één device
SLEEP_BETWEEN_DEVICES = 1.0   # pauze tussen devices (rate limiting)
LOCAL_SCAN_RETRIES = 3        # nooit None gebruiken

# -------------------------
# Connect to Tuya Cloud
# -------------------------

cloud = None
devices = []
local_devices = {}

try:
    cloud = tinytuya.Cloud(
        apiRegion=REGION,
        apiKey=APIKEY,
        apiSecret=APISECRET,
        apiDeviceID=DEVICEID,
    )
    cloud.use_old_device_list = True
    cloud.new_sign_algorithm = True

    if cloud.error:
        raise Exception(cloud.error)
    if not cloud.token:
        raise Exception("Invalid credentials")

    # -------------------------
    # Get devices
    # -------------------------
    while not devices:
        devices = cloud.getdevices()
        if not devices:
            print("No devices returned, retrying in 10s…")
            time.sleep(10)

    # -------------------------
    # Local scan
    # -------------------------
    print("Scanning local network for Tuya devices…")
    try:
        local_devices = tinytuya.deviceScan(
            verbose=False,
            maxretry=LOCAL_SCAN_RETRIES,
            byID=True,
        ) or {}
    except Exception as e:
        print(f"Local scan failed: {e}")
        local_devices = {}

    print(f"Local devices found: {len(local_devices)}")

    # Sanitize: verplaats echte keys naar local_devices, verwijder uit cloud-lijst
    for d in devices:
        did = d.get("id")
        if did and did in local_devices:
            local_devices[did]["key"] = d.get("key")
        d["key"] = "Deleted"

except Exception as err:
    print(f"Fatal error during setup: {err}")
    sys.exit(1)

# -------------------------
# Write dump.json — altijd, ook bij fouten per device
# -------------------------

with open("dump.json", "w") as f:

    print("List of devices:")
    print(safe_json(devices))
    write_block(f, "List of devices:", devices)

    for d in devices:
        device_id = d.get("id")
        name = d.get("name", "?")

        if not device_id:
            write_block(f, "Device without id:", d)
            continue

        try:
            # -------- Cloud properties --------
            props = None
            try:
                props = cloud.getproperties(device_id)
            except Exception as e:
                props = {"error": str(e)}
            time.sleep(SLEEP_BETWEEN_CALLS)

            print(f"\nProperties of device {device_id} ({name})")
            print(safe_json(props))
            write_block(f, f"Properties of device {device_id}:", props)

            # -------- Cloud status --------
            status_cloud = None
            try:
                status_cloud = cloud.getstatus(device_id)
            except Exception as e:
                status_cloud = {"error": str(e)}
            time.sleep(SLEEP_BETWEEN_CALLS)

            print(f"\nStatus of device {device_id} ({name})")
            print(safe_json(status_cloud))
            write_block(f, f"Status of device {device_id}:", status_cloud)

            # -------- DPS map (defensief) --------
            dps_map = {"by_code": {}, "by_id": {}}
            try:
                schema = cloud.getdps(device_id)
            except Exception as e:
                schema = {"error": str(e)}
            time.sleep(SLEEP_BETWEEN_CALLS)

            if isinstance(schema, dict) and schema.get("success"):
                result = schema.get("result") or {}
                status_list = result.get("status") or []
                for s in status_list:
                    code = s.get("code")
                    dp_id = s.get("dp_id")
                    if code is None or dp_id is None:
                        continue
                    dps_map["by_code"][code] = dp_id
                    dps_map["by_id"][dp_id] = code

            if dps_map["by_code"]:
                print(f"\nDPS map of device {device_id} ({name})")
                print(safe_json(dps_map))
                write_block(f, f"DPS map of device {device_id}:", dps_map)
            else:
                msg = "No DPS schema returned (IR/sub-device or empty result)."
                print(f"\n{msg} [{device_id}]")
                write_block(f, f"DPS map of device {device_id}:", msg)

            # -------- Local status --------
            if is_sub_device(d):
                msg = "Sub-device / IR (no WiFi radio). No local status possible."
                print(f"\n{msg} [{device_id}]")
                write_block(f, f"No local status of device {device_id},", msg)
            else:
                ld = local_devices.get(device_id)
                if ld and ld.get("ip"):
                    try:
                        dev = tinytuya.Device(
                            str(device_id),
                            str(ld.get("ip")),
                            str(ld.get("key", "0000000000000000")),
                            version=ld.get("version", 3.3),
                        )
                        # bulbs / devices met meerdere passes
                        dev.detect_available_dps()
                        dev.detect_available_dps()

                        local_status = dev.status()

                        print(f"\nLocal status of device {device_id} ({name})")
                        print(safe_json(local_status))
                        write_block(f, f"Local status of device {device_id}:", local_status)

                    except Exception as e:
                        print(f"\nLocal status failed for {device_id}: {e}")
                        write_block(f, f"Local status error for device {device_id}:", str(e))
                else:
                    msg = "No data, possibly no Wifi device found."
                    print(f"\nNo local status of device {device_id}, {msg}")
                    write_block(f, f"No local status of device {device_id},", msg)

        except Exception as e:
            # Vangt alles per device, zodat de rest doorgaat
            print(f"\n[SKIP] device {device_id} ({name}) failed: {e}")
            write_block(f, f"Error for device {device_id}:", str(e))

        finally:
            time.sleep(SLEEP_BETWEEN_DEVICES)

print("\n\ndump.json is created!")