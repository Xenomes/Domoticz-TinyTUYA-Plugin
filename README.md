# Domoticz-TinyTUYA-Plugin
TUYA Plugin for Domoticz home automation

Controls TUYA devices your network mainly on/off switches and Lights and in the future maybe more devices. 

## Installation

The plugin make use of the project Tinytuya there for is a IoT Cloud Platform account needed, for setup up see https://github.com/jasonacox/tinytuya step 3 or see PDF https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf

Python version 3.6 or higher required & Domoticz version 2022.2 or greater.

To install:
* Go in your Domoticz directory using a command line and open the plugins directory.
* The plugin required Python library tinytuya ```sudo pip3 install tinytuya```
* Run: ```git clone https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git```
* Restart Domoticz.

## Updating

To update:
* Upgrade the tinytuya library ```sudo pip3 install tinytuya --upgrade```
* Go in your Domoticz directory using a command line and open the plugins directory then the Domoticz-TUYA directory.
* Run: ```git pull```
* Restart Domoticz.

## Configuration

* Enter your apiRegion, apiKey, apiSecret and Search deviceID (This id is used to detect all the other devices) from your IoT Cloud Platform account, keep the setting 'Data Timeout' disabled.
* A deviceID can be found on your IOT account of Tuya got to Cloud => your project => Devices => Pick one of you device ID.
* The initial setup of your devices should be done with the app and this plugin will detect/use the same settings and automatically find/add the devices into Domoticz.

## Usage

In the web UI, navigate to the Hardware page. In the hardware dropdown there will be an entry called "TinyTUYA" -- configure and add the hardware there. 

## Test device

I had only a RGBWW light to fully test the script, if there is missing a fuction in the plugin and it is not noted on the TODO list you can provide the data from you device by edit and running the debug_discovery.py in the tools dirictory.

## Change log

| Version | Information|
| ----- | ---------- |
| 1.0.0 | Initial upload version |