# Domoticz-TinyTUYA-Plugin
TUYA Plugin for Domoticz home automation

Controls TUYA devices your network mainly on/off switches and Lights and in the future maybe more devices.

## Installation

The plugin make use of the project Tinytuya there for is a IoT Cloud Platform account needed, for setup up see https://github.com/jasonacox/tinytuya step 3 or see PDF https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf

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
| 1.3.4 | Changed local network detection to prevend 'thread seems to have ended unexpectedly' and speedup hardware detection |
| 1.3.5 | Add Fan's with lights |
| 1.3.6 | Add Smart IR T&H readouts not IR Devices to complex to recreate |
| 1.3.7 | Add 3 phase Power meter |
| 1.3.8 | Changed scaling for result |
| 1.3.9 | Add Gateway and CO2 Sensor |
| 1.4.0 | Add Ledstrip with deviating config |
| 1.4.1 | Add Doorsensor, Motionsensor with light and moddifed the subscription has expired detection |
| 1.4.2 | Add Tempsensor, Compatible with T&H standard and DP mode |
| 1.4.3 | Add Heatpump |
| 1.4.4 | Fix changed lights control |
| 1.4.5 | Add Zigbee Gateway (no reporting from device), Garage door opener, Fix changed temp control |
| 1.4.6 | Update for Tinytuya 1.11.0 and higher no need for search ID |
| 1.4.7 | Sub device added for Powermesument if mA is detectect, small bug fix and update install info to work with Docker |
| 1.4.8 | Added a new config for Thermostats and bug fix restart of the plugin see 'Updating' |
| 1.4.9 | Added a new configuration for power reading |
| 1.5.0 | Bug fix for tinytuya 1.12.3 |
| 1.5.1 | Added feeder |
| 1.5.2 | Changed the detection of a faulty login credentials or expired subscription |
| 1.5.3 | Some optimize, cleanup, turn down chattiness |
| 1.5.4 | Add new Curtain, heater control and custom scale for thermostat with deviant behavior |
| 1.5.5 | Add min/max for set devices |
| 1.5.6 | Fixed colour control and added Energy breaker switch|
| 1.5.7 | Add water leak sensor and presence sensors |
| 1.5.8 | Add Irrigation Control and smokesensor |
| 1.5.9 | Add new switch device |
| 1.6.0 | Add Starlight and Smart Wireless Switch M4 device |
| 1.6.1 | Add PJ2101A 1P WiFi Smart Meter device |
| 1.6.2 | Add Smart Siren and boiler device |
| 1.6.3 | Add Smart lock |
| 1.6.4 | Add Dehumidifier |
| 1.6.5 | Add Robot vacuum cleaner |
| 1.6.6 | Add WIFI Dual Meter |
| 1.6.7 | Add Air quality sensor |

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/xenomes)