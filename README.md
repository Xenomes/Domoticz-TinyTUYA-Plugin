# Domoticz-TinyTUYA-Plugin
TUYA Plugin for Domoticz home automation

Controls TUYA devices your network mainly on/off switches and Lights and in the future maybe more devices.

## Installation

The plugin make use of the project Tinytuya there for is a IoT Cloud Platform account needed, for setup up see https://github.com/jasonacox/tinytuya step 3 or see PDF https://github.com/jasonacox/tinytuya/files/12836816/Tuya.IoT.API.Setup.v2.pdf
for the best compatibility, set your devices to 'DP instruction' in the device settings under iot.tuya.com.

### Native Domoticz
Python version 3.8 or higher required & Domoticz version 2022.2 or greater.

To install:
* Go in your Domoticz directory using a command line and open the plugins directory.
* ```cd ~/domoticz/plugins``` for most user plugins directory.
* The plugin required Python library tinytuya ```sudo pip3 install requests==2.23.0 charset-normalizer==3.0.1 tinytuya -U```
* Run: ```git clone https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git```
* Restart Domoticz.

### Domoticz Docker
To install:
* Go in your Domoticz Docker directory using a command line and open the plugins directory.
* Run: ```git clone https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git```
* Add to your customstart.sh file the next lines after the 'apt-get -qq update' command.
```
echo 'install tinytuya'
apt install libffi-dev build-essential pkg-config libssl-dev -y
pip3 install cryptography==3.4.8 requests==2.23.0 charset-normalizer==3.0.1 tinytuya -U
```
* Rebuilt the Domoticz Docker container.
```
docker compose down
docker compose up -d
```
* Monitor the install this can take some time. ```docker logs -f domoticz```

## Updating
To update:
### Native Domoticz
* Upgrade the tinytuya library ```sudo pip3 install tinytuya -U```
* Go in your Domoticz directory using a command line and open the plugins directory then the Domoticz-TinyTUYA-Plugin directory.
* ```cd ~/domoticz/plugins/Domoticz-TinyTUYA-Plugin``` for most user or go to the Docker volume mount plugins/Domoticz-TinyTUYA-Plugin directory.
* Run: ```git pull```
* Restart Domoticz.

### Domoticz Docker
* Go in your Domoticz Docker directory using a command line and open the plugins directory.
* Run: ```git pull```
* Rebuilt the Domoticz Docker container.
```
docker compose down
docker compose up -d
```
* Monitor the install this can take some time. ```docker logs -f domoticz```

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
| 1.7.2 | Add Smart Kettle and update Thermostat to 2024.1+ |
| 1.7.3 | Add SETTI+ weather station |
| 1.7.4 | Bug fixing |
| 1.7.5 | Update for Debian Bookworm Python 3.11.2 |
| 1.7.6 | Add WiFi Din Rail Switch with power metering |

 [The full Change log](CHANGELOG.md)

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/xenomes)