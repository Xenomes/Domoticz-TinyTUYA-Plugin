#!/usr/bin/env python3

# The script is intended to get a list of all devices available via Tuya API endpoint.
try:
        import tinytuya
except Exception:
        tinytuya = None
import json
import os
import sys
import time

# TUYA ACCOUNT - Set up a Tuya Account (see PDF Instructions):
# https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf

CRED_CANDIDATES = ['tuya_creds.json', 'cred.json', 'creds.json']

def load_credentials():
        """Try loading credentials from a set of candidate files.
        Returns a tuple (creds, path) or (None, None) if none found."""
        for path in CRED_CANDIDATES:
                if not os.path.exists(path):
                        continue
                try:
                        with open(path, 'r') as fh:
                                data = json.load(fh)
                                # Normalize keys to expected names
                                creds = {
                                        'apiRegion': data.get('apiRegion') or data.get('REGION'),
                                        'apiKey': data.get('apiKey') or data.get('APIKEY'),
                                        'apiSecret': data.get('apiSecret') or data.get('APISECRET'),
                                        'apiDeviceID': data.get('apiDeviceID') or data.get('DEVICEID'),
                                }
                                if None in creds.values():
                                        # Not a valid credentials file
                                        continue
                                return creds, path
                except Exception:
                        continue
        return None, None


def load_credentials_from_path(path):
        """Load credentials from a specific path. Returns (creds, path) or (None, None)."""
        if not os.path.exists(path):
                return None, None
        try:
                with open(path, 'r') as fh:
                        data = json.load(fh)
                        creds = {
                                'apiRegion': data.get('apiRegion') or data.get('REGION'),
                                'apiKey': data.get('apiKey') or data.get('APIKEY'),
                                'apiSecret': data.get('apiSecret') or data.get('APISECRET'),
                                'apiDeviceID': data.get('apiDeviceID') or data.get('DEVICEID'),
                        }
                        if None in creds.values():
                                return None, None
                        return creds, path
        except Exception:
                return None, None


# We prompt interactively for credentials every run (use existing file values as defaults).


def save_credentials(creds, path=None):
        """Save credentials dict to a JSON file. If path not provided, choose the first non-conflicting candidate."""
        if path is None:
                # Prefer tuya_creds.json so we don't overwrite existing token-style cred.json
                path = 'tuya_creds.json'
        with open(path, 'w') as fh:
                json.dump(creds, fh, indent=2)
        return path


def prompt_for_credentials(existing=None):
        """Prompt user for any missing credentials. Returns a complete creds dict."""
        if existing is None:
                existing = {}
        creds = {}
        try:
                # apiRegion
                default_region = existing.get('apiRegion')
                region = input(f"Tuya region (cn, eu, us): ")
                creds['apiRegion'] = region

                # apiKey
                default_key = existing.get('apiKey')
                key = input(f"Tuya API key: ")
                creds['apiKey'] = key

                # apiSecret (don't echo if possible)
                default_secret = existing.get('apiSecret')
                try:
                        import getpass
                        secret = getpass.getpass('Tuya API secret (input hidden): ')
                        if not secret:
                                secret = default_secret
                except Exception:
                        secret = input(f"Tuya API secret: ")
                creds['apiSecret'] = secret

                # apiDeviceID
                default_dev = existing.get('apiDeviceID')
                devid = input(f"Tuya Device ID: ")
                creds['apiDeviceID'] = devid

                return creds
        except KeyboardInterrupt:
                print('\nInput cancelled by user')
                sys.exit(1)


# Try loading credentials from disk first (prefer tuya_creds.json). If not found, prompt the user.
creds, cred_path = load_credentials()
if creds is not None:
        print(f"Loaded credentials from {cred_path}")
else:
        print('No valid credential file found; prompting for Tuya credentials.')
        creds = prompt_for_credentials()
        # Save to tuya_creds.json by default to make subsequent runs non-interactive
        saved_path = save_credentials(creds, path='tuya_creds.json')
        print(f"Saved credentials to {saved_path}")

# Expose vars expected later in the script
REGION = creds['apiRegion']
APIKEY = creds['apiKey']
APISECRET = creds['apiSecret']
DEVICEID = creds['apiDeviceID']

# Connect to Tuya Cloud
try:
        if tinytuya is None:
                print('The "tinytuya" Python module is not available. Credentials have been prepared; install "tinytuya" (pip install tinytuya) to run discovery.')
                sys.exit(0)
        c = tinytuya.Cloud(
                apiRegion=REGION,
                apiKey=APIKEY,
                apiSecret=APISECRET,
                apiDeviceID=DEVICEID
                )
        c.use_old_device_list = True
        c.new_sign_algorithm = True
        if c.error is not None:
                raise Exception(c.error['Payload'])
        token = c.token
        # Check credentials
        if token == None:
                raise Exception('Credentials are incorrect!')

        # Always overwrite dump.json with fresh discovery results
        f = open("dump.json", "w")

        # Display list of devices
        devices = []
        while len(devices) == 0:
                devices = c.getdevices()
                print('No device data returnd for Tuya. Trying again!')
                time.sleep(10)

        for i in range(len(devices)):
                devices[i - 1]['key'] = 'Deleted'

        print("List of devices: \n", json.dumps(devices, indent=2))
        f.write("List of devices: \n" + json.dumps(devices, indent=2))

        for d in devices:
                # Display Properties of Device
                result = c.getproperties(d["id"])
                print("\nProperties of device: " + d["id"] + "\n", json.dumps(result, indent=2))
                f.write("\nProperties of device: " + d["id"] + "\n" + json.dumps(result, indent=2))

                # Display Status of Device
                result = c.getstatus(d["id"])
                print("\nStatus of device: " + d["id"] + "\n", json.dumps(result, indent=2))
                f.write("\nStatus of device: " + d["id"] + "\n" + json.dumps(result, indent=2))

        f.close()

except Exception as err:
        print('debug_discovery: ' + str(err) + ' line ' + format(sys.exc_info()[-1].tb_lineno))

if (os.path.exists("dump.json")):
        print('\n\ndump.json is created!')