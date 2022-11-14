# The script is intended to get a list of all devices available via Tuya API endpoint.
import tinytuya

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
# c = tinytuya.Cloud()  # uses tinytuya.json 
c = tinytuya.Cloud(
        apiRegion=REGION, 
        apiKey=APIKEY, 
        apiSecret=APISECRET, 
        apiDeviceID=DEVICEID)

# Display list of devices
devices = c.getdevices()
print("Device List: %r" % devices)

# Display Properties of Device
result = c.getproperties(DEVICEID)
print("Properties of device:\n", result)

# Display Status of Device
result = c.getstatus(DEVICEID)
print("Status of device:\n", result)