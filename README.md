# Domoticz-TinyTUYA-Plugin
TUYA Plugin for Domoticz home automation

Controls TUYA devices your network mainly on/off switches and Lights and in the future maybe more devices.

## Installation

The plugin make use of the project Tinytuya there for is a IoT Cloud Platform account needed, for setup up see https://github.com/jasonacox/tinytuya step 3 or see PDF https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf

Python version 3.8 or higher required & Domoticz version 2022.2 or greater.

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

* Enter your apiRegion, apiKey, apiSecret and Search deviceID (This id is used to detect all the other devices), keep the setting 'Data Timeout' disabled.
* A deviceID can be found on your IOT account of Tuya got to Cloud => your project => Devices => Pick one of you device ID.
* The initial setup of your devices should be done with the app and this plugin will detect/use the same settings and automatically find/add the devices into Domoticz.

## Usage

In the web UI, navigate to the Hardware page. In the hardware dropdown there will be an entry called "TinyTUYA" configure and add the hardware there.

## Test device

I had only a RGBWW light to fully test the script, if there is a fuction missing in the plugin and it is not noted on the TODO list you can provide the jsom data from you device by edit and running the debug_discovery.py in the tools directory and posted in issues.

## Change log

| Version | Information|
| ----- | ---------- |
| 1.0.0 | Initial upload version |
| 1.0.1 | Change heart beat to reduce API calls |
| 1.1.0 | Add Heater (Power, read and set temperature) |
| 1.2.0 | Add Thermostats, T&H devices, Covers/Blinds, multi switches and optimization code (Thanks for the testers!) |
| 1.2.1 | Fixed value scaling problem and mode detection and some other stuff |
| 1.2.2 | Add Doorbel |
| 1.2.3 | Fix for incorrect 'temp_set' selection |
| 1.2.4 | Fix Heater function |
| 1.2.5 | Add 'Window check' and 'child lock' to Heater function |
| 1.2.6 | Add Power readings to Switch, repair Dimmer devices and Light detection v2 fixed |
| 1.2.7 | Add 'battery percentage' and 'battery_state' to battery power devices |
| 1.2.8 | Fix for filament lamps |
| 1.2.9 | Fix bug in video doorbell |
| 1.3.0 | Add On/Off for Fan |
| 1.3.1 | Change temperature scaling get value from tuya defined from function |
| 1.3.2 | Add kWh logging for switch with powerreader, fix failed login detection |
| 1.3.3 | Add on/off and other functions Siren |
| 1.3.4 | Changed local network detection to prevend 'thread seems to have ended unexpectedly' and speedup hardware detection|