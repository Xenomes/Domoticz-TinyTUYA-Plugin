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
* Add the next lines to your customstart.sh file after the 'apt-get -qq update' command.

#### Bullseye
```
echo 'install tinytuya'
apt install libffi-dev build-essential pkg-config libssl-dev -y
pip3 install cryptography==3.4.8 requests==2.23.0 charset-normalizer==3.0.1 tinytuya -U
```
#### Bookworm
```
echo 'install tinytuya'
pip3 install tinytuya PyCryptodome==3.21.0 chardet==3.0.4 requests==2.23.0 charset-normalizer==3.0.1 --break-system-packages
```
#### Trixie
```
echo 'install tinytuya'
pip3 install tinytuya PyCryptodome chardet requests charset-normalizer urllib3 --break-system-packages
```

* Rebuild the Domoticz Docker container.
```
docker compose down
docker compose up -d
```
* Monitor the install this can take some time. ```docker logs -f domoticz```

## Updating

> [!IMPORTANT]
> **The API polling interval setting** has been added to the plugin interface for updates to **newer versions** from versions prior to 2.0.8.


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

## Refresh button (optional)

To stay within the API quota the polling interval is usually long, so a change made on the device itself or in the Tuya app shows up in Domoticz only at the next poll. For the device IDs entered in **Refresh button for device IDs** (comma separated) the plugin adds a push button "*device name* (Refresh)". Pressing it reads just that device from the cloud (2 API calls) and updates its units right away; the regular polling interval is not affected. With the field left empty nothing changes.

The button is meant to be pressed by something outside the plugin, for example:
* a dzVents script: ```domoticz.devices('Irrigation controller (Refresh)').switchOn()```
* the JSON API: ```http://<domoticz>:8080/json.htm?type=command&param=switchlight&idx=<idx of the button>&switchcmd=On```

The buttons are created when the plugin starts, so press Update on the Hardware page after changing the field; "Accept new Hardware Devices" must be enabled in the Domoticz settings at that moment.

[examples/refresh-button](examples/refresh-button) shows how to press the button whenever an OpenWrt router sees the device talk to the Tuya cloud: an nftables counter, a small script on the router and a dzVents script.

## Test device

I had only a RGBWW light to fully test the script, if there is a fuction missing in the plugin you can provide the json data for you device by edit and running the debug_discovery.py in the tools directory and posted in issues on Github.

## Change log

| Version | Information|
| ----- | ---------- |
| 2.3.8 | Add EPT ultrasonic sensor 3m #194 |
| 2.3.9 | Add Siren function to Camera #195 |
| 2.4.0 | Add Add CKM-01 device #196 |
| 2.4.1 | Fix color (de)coding #199 |
| 2.4.2 | Fix issue with 'tdq' catagory devices #201 |

 [The full Change log](CHANGELOG.md)

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/xenomes)
