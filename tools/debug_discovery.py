#!/usr/bin/env python3

# The script is intended to get a list of all devices available via Tuya API endpoint.
import tinytuya
import json
import os
import sys
import time

# TUYA ACCOUNT - Set up a Tuya Account (see PDF Instructions):
# https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf

# CHANGE THIS - BEGINING
REGION = "eu" # cn, eu, us
APIKEY = "xxxxxxxxxxxxxxxxxxxx"
APISECRET = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# Select a Device ID to Test
DEVICEID = "xxxxxxxxxxxxxxxxxxxx"
# CHANGE THIS - END

# NO NEED TO CHANGE ANYTHING BELOW

if APIKEY == "xxxxxxxxxxxxxxxxxxxx" or APISECRET == "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" or DEVICEID == "xxxxxxxxxxxxxxxxxxxx":
        print("""Tuya Plugin Configuration Error:

ERROR: Invalid or missing values for Tuya account configuration.

Please ensure the following information is correctly provided:

REGION: [Enter your Tuya region, e.g., us, eu, cn]
APIKEY: [Enter your Tuya API key]
APISECRET: [Enter your Tuya API secret]
DEVICEID: [Enter your Tuya device ID]

Instructions:
1. REGION: Specify the Tuya region associated with your account (e.g., us, eu, cn).
2. APIKEY: Enter the correct Tuya API key linked to your account.
3. APISECRET: Provide the correct Tuya API secret corresponding to your API key.
4. DEVICEID: Specify the correct Tuya device ID for your device.

Example:
REGION: us
APIKEY: abcdef1234567890
APISECRET: xyz7890123456789
DEVICEID: tuya_device_001

Ensure accurate information before attempting to configure the Tuya plugin again.
""")
        exit()

# Connect to Tuya Cloud
try:
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

        if (os.path.exists("dump.json")):
                f = open("dump.json", "r+")
        else:
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