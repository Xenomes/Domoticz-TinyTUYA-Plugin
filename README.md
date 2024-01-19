# Domoticz-TinyTUYA-Plugin
TUYA Plugin for Domoticz home automation

Controls TUYA devices your network mainly on/off switches and Lights and in the future maybe more devices.

## Installation

The plugin make use of the project Tinytuya there for is a IoT Cloud Platform account needed, for setup up see https://github.com/jasonacox/tinytuya step 3 or see PDF https://github.com/jasonacox/tinytuya/files/12836816/Tuya.IoT.API.Setup.v2.pdf
for the best compatibility, set your devices to 'DP instruction' in the device settings under iot.tuya.com.

Python version 3.8 or higher required & Domoticz version 2022.2 or greater.

To install:
* Go in your Domoticz directory using a command line and open the plugins directory.
* ```cd ~/domoticz/plugins``` for most user or go to the Docker volume mount plugins directory.
* The plugin required Python library tinytuya ```sudo pip3 install requests==2.23.0 charset-normalizer==3.0.1 tinytuya -U```
* Run: ```git clone https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git```
* Restart Domoticz.

## Updating

To update:
* Upgrade the tinytuya library ```sudo pip3 install tinytuya -U```
* Go in your Domoticz directory using a command line and open the plugins directory then the Domoticz-TinyTUYA-Plugin directory.
* ```cd ~/domoticz/plugins/Domoticz-TinyTUYA-Plugin``` for most user or go to the Docker volume mount plugins/Domoticz-TinyTUYA-Plugin directory.
* Run: ```git pull```
* Restart Domoticz.

## Subscription expired
Is your subscription to cloud development plan expired, you can extend it <a href="https://iot.tuya.com/cloud/products/apply-extension"> HERE</a><br/>

## Configuration

Enter your apiRegion, apiKey, apiSecret and Search deviceID (This id is used to detect all the other devices), keep the setting 'Data Timeout' disabled.
A deviceID can be found on your IOT account of Tuya got to Cloud => your project => Devices => Pick one of you device ID.
The initial setup of your devices should be done with the app and this plugin will detect/use the same settings and automatically find/add the devices into Domoticz.

## Usage

In the web UI, navigate to the Hardware page. In the hardware dropdown there will be an entry called "TinyTUYA" configure and add the hardware there.

## Test device

I had only a RGBWW light to fully test the script, if there is a fuction missing in the plugin you can provide the json data for you device by edit and running the debug_discovery.py in the tools directory and posted in issues on Github.

## Change log

| Version | Information|
| ----- | ---------- |
| 1.7.0 | Add Scene remote
| 1.7.1 | Add Switch Robot and lux meter
| 1.7.2 | Add Smart Kettle and update Thermostat to 2024.1+

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/xenomes)