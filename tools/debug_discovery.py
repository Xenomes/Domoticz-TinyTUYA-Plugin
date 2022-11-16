#!/usr/bin/env python3

# The script is intended to get a list of all devices available via Tuya API endpoint.
import tinytuya
import json
import os

# TUYA ACCOUNT - Set up a Tuya Account (see PDF Instructions): 
# https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf

# CHANGE THIS - BEGINING
REGION = "eu" # cn, eu, us
APIKEY = "xxxxxxxxxxxxxxxxxxxx"                 
APISECRET = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  
# Select a Device ID to Test
DEVICEID = "xxxxxxxxxxxxxxxxxxID"
# CHANGE THIS - END

# NO NEED TO CHANGE ANYTHING BELOW

# Connect to Tuya Cloud
c = tinytuya.Cloud(
        apiRegion=REGION, 
        apiKey=APIKEY, 
        apiSecret=APISECRET, 
        apiDeviceID=DEVICEID
        )

if (os.path.exists("dump.json")):
        f = open("dump.json", "r+")
else:
        f = open("dump.json", "w")
        
# Display list of devices
devices = c.getdevices()
for i in range(len(devices)):
        devices[i - 1]['key'] = 'Deleted'

print("List of devices: \n", devices)
f.write("List of devices: \n" + json.dumps(devices, indent=2))

for d in devices:
        # Display Properties of Device
        result = c.getfunctions(d["id"])
        print("\nFunctions of device: " + d["id"] + "\n", result)
        f.write("\nFunctions of device: " + d["id"] + "\n" + json.dumps(result, indent=2))

        # Display Status of Device
        result = c.getstatus(d["id"])
        print("\nStatus of device: " + d["id"] + "\n", result)
        f.write("\nStatus of device: " + d["id"] + "\n" + json.dumps(result, indent=2))

f.close()