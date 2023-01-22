#!/usr/bin/env python3

# The script is intended to get a list of all devices available via Tuya API endpoint.
import tinytuya
import json
import os
import sys

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

# Connect to Tuya Cloud
try:
        c = tinytuya.Cloud(
                apiRegion=REGION,
                apiKey=APIKEY,
                apiSecret=APISECRET,
                apiDeviceID=DEVICEID
                )

        token = c.token
        # Check credentials
        if token == None:
                raise Exception('Credentials are incorrect!')

        if (os.path.exists("dump.json")):
                f = open("dump.json", "r+")
        else:
                f = open("dump.json", "w")

        # Display list of devices
        devices = c.getdevices()
        for i in range(len(devices)):
                devices[i - 1]['key'] = 'Deleted'

        print("List of devices: \n", json.dumps(devices, indent=2))
        f.write("List of devices: \n" + json.dumps(devices, indent=2))

        for d in devices:
                # Display Functions of Device
                result = c.getfunctions(d["id"])
                print("\nFunctions of device: " + d["id"] + "\n", json.dumps(result, indent=2))
                f.write("\nFunctions of device: " + d["id"] + "\n" + json.dumps(result, indent=2))

                # Display Properties of Device
                result = c.getproperties (d["id"])
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