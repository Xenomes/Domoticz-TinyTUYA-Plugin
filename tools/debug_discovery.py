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
# Tunables (pas aan indien nodig)
# -------------------------
SLEEP_BETWEEN_CALLS = 0.3     # pauze tussen cloud API-calls binnen één device
SLEEP_BETWEEN_DEVICES = 1.0   # pauze tussen devices (rate limiting)
LOCAL_SCAN_RETRIES = 3        # NOOIT None gebruiken, anders hangt het script

# -------------------------
# Connect to Tuya Cloud
# -------------------------

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

    devices = []
    while not devices:
        devices = cloud.getdevices()
        if not devices:
            print("No devices returned, retrying in 10s…")
            time.sleep(10)

    # -------------------------
    # Local scan (FIX: maxretry begrensd, verbose uit)
    # -------------------------
    print("Scanning local network for Tuya devices…")
    try:
        local_devices = tinytuya.deviceScan(
            verbose=False,
            maxretry=LOCAL_SCAN_RETRIES,
            byID=True,
        )
    except Exception as e:
        print(f"Local scan failed: {e}")
        local_devices = {}

    print(f"Local devices found: {len(local_devices)}")

    # Sanitize keys — verwijder echte keys uit de cloud-lijst
    for d in devices:
        if d["id"] in local_devices:
            local_devices[d["id"]]["key"] = d.get("key")
        d["key"] = "Deleted"

    # -------------------------
    # Write everything to dump.json
    # -------------------------

    with open("dump.json", "w") as f:

        def write_block(title, data):
            f.write(f"\n{title}\n")
            f.write(json.dumps(data, indent=2))
            f.write("\n")

        print("List of devices:")
        print(json.dumps(devices, indent=2))
        write_block("List of devices:", devices)

        for d in devices:
            device_id = d["id"]

            # FIX 2: per-device try/except, zodat één fout niet alles stopt
            try:
                props = cloud.getproperties(device_id)
                time.sleep(SLEEP_BETWEEN_CALLS)   # FIX 3

                status_cloud = cloud.getstatus(device_id)
                time.sleep(SLEEP_BETWEEN_CALLS)   # FIX 3

                print(f"\nProperties of device {device_id}")
                print(json.dumps(props, indent=2))
                write_block(f"Properties of device {device_id}:", props)

                print(f"\nStatus of device {device_id}")
                print(json.dumps(status_cloud, indent=2))
                write_block(f"Status of device {device_id}:", status_cloud)

                # -------------------------
                # DPS map
                # -------------------------
                dps_map = {"by_code": {}, "by_id": {}}
                schema = cloud.getdps(device_id)
                time.sleep(SLEEP_BETWEEN_CALLS)   # FIX 3

                if schema and schema.get("success"):
                    for s in schema["result"].get("status", []):
                        dps_map["by_code"][s["code"]] = s["dp_id"]
                        dps_map["by_id"][s["dp_id"]] = s["code"]

                    print(f"\nDPS map of device {device_id}")
                    print(json.dumps(dps_map, indent=2))
                    write_block(f"DPS map of device {device_id}:", dps_map)

                # -------------------------
                # Local device status — FIX 4
                # -------------------------
                ld = local_devices.get(device_id)
                if ld and ld.get("ip"):
                    try:
                        dev = tinytuya.Device(
                            str(device_id),
                            str(ld.get("ip")),
                            str(ld.get("key", "0000000000000000")),
                            version=ld.get("version", 3.3),
                        )
                        dev.detect_available_dps()
                        dev.detect_available_dps()  # bulbs need two passes

                        local_status = dev.status()

                        print(f"\nLocal status of device {device_id}")
                        print(json.dumps(local_status, indent=2))
                        write_block(f"Local status of device {device_id}:", local_status)

                    except Exception as e:
                        print(f"\nLocal status failed for {device_id}: {e}")
                        write_block(f"Local status error for device {device_id}:", str(e))

                else:
                    print(f"\nNo local status of device {device_id}, possibly no WiFi device found.")
                    write_block(
                        f"No local status of device {device_id},",
                        "No data, possibly no Wifi device found.",
                    )

            except Exception as e:
                # FIX 2: log de fout, ga door naar het volgende device
                print(f"\n[SKIP] device {device_id} failed: {e}")
                write_block(f"Error for device {device_id}:", str(e))

            finally:
                # FIX 3: altijd even pauzeren tussen devices, ook bij een fout
                time.sleep(SLEEP_BETWEEN_DEVICES)

    print("\n\ndump.json is created!")

except Exception as err:
    print(
        f"debug_discovery: {err} line {sys.exc_info()[-1].tb_lineno}"
    )