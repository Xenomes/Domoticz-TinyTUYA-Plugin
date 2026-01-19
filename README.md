# Domoticz-TinyTUYA-Plugin

TUYA plugin for Domoticz home automation.

This plugin provides **hybrid local (LAN) and cloud-based control** for Tuya devices.
Whenever possible, devices are controlled **locally using TinyTuya**, with automatic
fallback to the **Tuya IoT Cloud** when local communication is not available.

The Tuya Cloud is primarily used for **initial device discovery, DPS mapping and configuration**.

---

## Features

- Automatic discovery of Tuya devices via Tuya IoT Cloud
- Automatic DPS (data point) detection and mapping
- Local LAN control using TinyTuya (fast and reliable)
- Automatic fallback to Tuya Cloud when devices are not reachable locally
- On/Off control, dimming, color temperature and device-specific features
- Cached cloud status to reduce API usage
- Configurable **API polling interval** and **IP scan interval**

---

## Installation / Updating

This plugin uses the **TinyTuya** project.  
A **Tuya IoT Cloud Platform account** is required for initial setup.

Cloud setup instructions:

- https://github.com/jasonacox/tinytuya (step 3)
- PDF: https://github.com/jasonacox/tinytuya/files/12836816/Tuya.IoT.API.Setup.v2.pdf

> For best compatibility, set your devices to **“DP instruction”**
> in the device settings on https://iot.tuya.com

---

## Installation Native Domoticz
Go in your Domoticz directory using a command line and open the plugins directory.
```bash
cd ~/domoticz/plugins
sudo pip3 install tinytuya -U #--break-system-packages # if needed
# for installing
git clone https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git
# for updating
git pull
```
Restart Domoticz.

Alternative and better is to make use of Python Virtual Environment, install the modules in that environment and add the definition for the PYTHONPATH environment variable in the script which automatically starts Domoticz.
See for instructions (written for the Zigbee4Domoticz but could be used for any plugin): https://zigbeefordomoticz.github.io/wiki/en-eng/HowTo_PythonVirtualEnv.html 

## Installation Domoticz Docker

```bash
cd <your-domoticz-docker>/plugins
# for installing
git clone https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git
# for updating
git pull
```
Add the next lines to your customstart.sh file after the 'apt-get -qq update' command.
```bash
echo 'install tinytuya'
pip3 install tinytuya -U
```
Docker configuration (IMPORTANT)
When running Domoticz Docker:
--host mode is necessary for device scanning and caching all outputs.
Use environment variables to set the web ports instead of -p 8088:8080 -p 443:443:
```bash
-e WWW_PORT=8080 \
-e SSL_PORT=443 \
```
Default ports are 8080 (HTTP) and 8443 (HTTPS). Change them to your preferred ports instead."
Example docker-compose.yml snippet:
```bash
services:
  domoticz:
    container_name: domoticz
    image: domoticz/domoticz:latest
    network_mode: "host"        # Needed for device scanning
    environment:
      - WWW_PORT=8080
      - SSL_PORT=443
    volumes:
      - ./config:/opt/domoticz/userdata
```
Rebuilt the Domoticz Docker container.
```bash
docker compose down
docker compose up -d
```
* Monitor the install this can take some time. ```docker logs -f --tail 0 domoticz```

This way:

- Scanning works (`--host` is enabled)
- Web ports are still configurable via environment variables
- Full guide ready for Markdrop formatting  

If you want, I can **also add a TinyTUYA plugin verification step** inside Domoticz so you know the plugin is loaded correctly. Do you want me to do that?

## Configuration

In the Domoticz hardware configuration, enter:

- **Region**
- **Access ID / Client ID**
- **Access Secret / Client Secret**
- **Search Device ID**
  - Used only to discover all devices
  - Found in Tuya IoT Platform:  
    Cloud → Project → Devices → select any device

### Important settings

- **API Polling Interval**
  - Recommended: **900 seconds (15 minutes)**

- **IP Scan Interval**
  - Defines how often device IP addresses are refreshed
  - Default: **86400 seconds (24 hours)**

- **Data Timeout**
  - Keep this **disabled**

After initial setup, the plugin minimizes cloud usage and prefers local LAN control.

---

## Usage

1. Open the Domoticz web interface
2. Go to **Hardware**
3. Add a new hardware device
4. Select **TinyTUYA**
5. Configure and add

Devices will be created automatically after discovery.

---

## Test Devices

Testing has been primarily done with **RGBWW light**.

If functionality is missing for your device:

1. Run `debug_discovery.py` from the `tools` directory
2. Provide the generated JSON data
3. Open an issue on GitHub

---

## Subscription Expired

If your Tuya Cloud development subscription has expired, you can extend it here:

https://iot.tuya.com/cloud/products/apply-extension

---

## Change Log

| Version | Information |
|--------|-------------|
| 3.0.0  | Release of hybrid version |

Support development:

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/xenomes)