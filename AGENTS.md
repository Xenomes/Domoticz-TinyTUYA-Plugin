# Domoticz TinyTUYA Plugin - Agent Documentation

## Project Overview

**Repository:** Domoticz-TinyTUYA-Plugin
**Main File:** plugin.py
**Purpose:** Domoticz plugin for Tuya IoT devices with hybrid local/cloud control
**Current Version:** 3.1.1
**Author:** Xenomes (xenomes@outlook.com)

## Architecture

### Hybrid Control System
- **Cloud Communication:** Used for initial device discovery, DPS mapping, and configuration
- **Local Communication:** Uses TinyTuya library for device control and status updates
- **Fallback:** Automatically falls back to cloud when local control is unavailable
- **Realtime Updates:** Tuya Pulsar websocket for push updates from devices

### Key Components
- **plugin.py:** Main plugin file with all device logic
- **TinyTuya:** Python library for local Tuya device communication
- **Tuya Cloud API:** Used for device discovery and configuration

## Device Categorization

### Main Device Types
- **switch/sensor:** Basic switches with optional sensor functionality
- **light:** RGB/RGBW/RGBWW lights, dimmers, fans with lights
- **thermostat/heater/heatpump:** Temperature control devices
- **cover:** Curtains, blinds, shutters
- **smartlock:** Door locks with multiple unlock methods
- **aromatherapy:** Aroma diffusers with light and mist control
- **dehumidifier:** Humidity control devices
- **sensor:** Motion sensors, temperature/humidity sensors
- **doorcontact:** Door/window contact sensors
- **Other:** Many specialized device types

### Special Categories
- **Category 'qt':** Ambiguous - can be smoke detector OR curtain switch (detected via product_name)
- **Category 'wnykq':** Smart IR devices (currently marked as unsupported)
- **Category 'jsq':** Aromatherapy devices
- **Category 'ms'/'jtmspro':** Smart locks

## Important Implementation Details

### Curtain Switch Support (Issue #208)
- Category 'qt' devices with "curtain" in product_name are treated as covers
- Status mapping: 1=Open, 2=Close, 3=Stop
- Command mapping: open→1, close→2, stop→3
- Other 'qt' devices remain smoke detectors

### SmartLock Support (Issue #205)
- Unit 1: Lock state (lock_motor_state/rtc_lock)
- Unit 2: Alarm status (alarm_lock selector)
- Units 3-11: Unlock methods (BLE, Card, Fingerprint, Password, App, Key, Face, Hand, Temporary)
- Compatibility maintained for existing unit numbers

### Aromatherapy Support (Issue #200)
- Unit 1: Power (main switch)
- Unit 2: Light (light switch)
- Unit 3: Lightmode (selector)
- Unit 4: Mist grade (small/big selector)
- Unit 5: Scene/Work mode (white/colour/scene/music selector)
- Unit 6: RGB (color control)

### RGBIC Light Support (Issue #200)
- Multi-LED devices with draw_tool support
- Automatic RGBW/RGBWW detection based on bright_value max
- White channel support for better color rendering
- Units 11+ for individual LED control

### Protocol 3.4 Cloud Fallback
- Specific fallback for protocol 3.4 devices to show correct online/offline status
- Rate-limited to avoid excessive cloud API calls
- Prevents devices from incorrectly showing TimedOut=1

## Build and Verification

### Syntax Check
```bash
python3 -m py_compile plugin.py
```

### Git Operations
```bash
# Check status
git status --short
git diff -- plugin.py

# Commit format
git commit -m "Description

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>"
```

## Code Conventions

### DeviceType Function
- Signature: `DeviceType(category, product_id=None, product_name=None)`
- Returns device type string based on category and product information
- Special handling for ambiguous categories (e.g., 'qt' with product_name)

### Device Creation
- Uses `createDevice(dev_id, unit)` to check if device exists
- Pattern: `if createDevice(dev_id, unit) and searchCode('code', Properties):`
- Unit numbering: maintain compatibility for existing devices

### Status Updates
- Helper functions: `update_bool_device()`, `update_select_device()`, `update_value_device()`
- Pattern: check code, get value, update if changed
- Battery devices handled separately

### Command Handling
- Pattern: check function code, send command, update Domoticz
- Special cases for dimmers, colors, multi-channel devices

## Known Issues and Solutions

### Category Mismatches
- **Category 'qt':** Can be smoke detector OR curtain switch → use product_name detection
- **Category 'wnykq':** Smart IR devices with limited functionality → mark as unsupported
- **Category 'jsq':** Aromatherapy devices → treat as dedicated type

### Indentation Issues
- Complex try/except blocks in status updates can cause indentation errors
- Solution: Carefully match indentation levels when adding new device types

### Color Control
- RGB vs RGBW vs RGBWW format differences
- Solution: Detect type from bright_value max and use appropriate encoding
- draw_tool commands need special base64 encoding

### Local Connection Issues
- Protocol 3.4 devices may not respond to local queries
- Solution: Cloud fallback with rate limiting
- Prevents devices from appearing as TimedOut

## Branch Information

### Main Branches
- **Master:** Stable version with latest features

### Version Differences
- **3.x:** Hybrid local/cloud control with Pulsar realtime updates

## Recent Work

### Latest Changes (Version 3.1.1)
- Added RGBW/RGBWW white channel support to draw_tool commands
- Improved SmartLock unlock methods
- Added Aromatherapy device support
- Protocol 3.4 cloud fallback for correct online/offline status
- Translated Dutch comments to English
- Fixed product_name usage in device detection

### Important Commits
- `3.1.0`: Add aromatherapy device #200
- `3.0.9`: Add SmartLock unlock methods #205
- `3.0.8`: Fix battery device detection, remove dead code
- `3.0.7`: Fix local status fetch for Tuya v3.4 devices
- `3.0.6`: Cloud fallback for non-local devices in local poll path (fixes covers timing out after 3 minutes)
- `3.0.5`: Add missing DeviceModelMapping() helper (fix NameError during cloud-init for all devices)
- `3.0.4`: DPS mapping robustness: skip schema entries without dp_id, add DeviceModelMapping fallback for DPs missing from getdps()
- `3.0.3`: fix: prevent IR/sub-devices from crashing the whole poll run
- `3.0.2`: Fix infrared device support and command handling bugs
- `3.0.1`: Fix for category detection of 'tdq'
- `3.0.0`: Release of hybrid version
- `3.0.0-rc.3`: Weather station barometer/rain units (PR #210) and multi-zone irrigation support (PR #209)
- `3.0.0-rc.2`: Add refresh button functionality (Mode5) from PR #211
- `3.0.0-rc.1`: Merge Master branch changes (2.4.0-2.4.5) into Hybrid
## Testing Approach

### Device Testing
1. Add device to Domoticz
2. Check device creation (correct units?)
3. Test commands (On/Off, Set Level, Set Color)
4. Verify status updates
5. Check logs for errors

### Syntax Verification
Always run `python3 -m py_compile plugin.py` after changes

### Log Analysis
- Debug level shows detailed device communication
- Look for "Cloud fallback" messages for protocol issues
- Check "Multi-LED" logs for draw_tool problems

## Dependencies

### Required
- Python 3.8+
- tinytuya library (pip3 install tinytuya)
- Domoticz with plugin support

### Optional
- tuyawizard library (for QR code login wizard feature)

## File Structure

- **plugin.py:** Main plugin file (all logic)
- **CHANGELOG.md:** Version history
- **README.md:** User documentation
- **tools/**: Debug and utility scripts
- **backup/**: Backup files
- **examples/**: Example configurations
- **.devin/**: Devin agent configuration

## Important Functions

### Device Detection
- `DeviceType(category, product_id=None, product_name=None)` - Classify devices
- `createDevice(dev_id, unit)` - Check if device unit exists
- `searchCode(code, properties)` - Search for specific Tuya DP codes

### Communication
- `SendCommandTuya(DeviceID, switch, value)` - Send cloud command
- `StatusDeviceTuya(code)` - Get current device status
- `UpdateDomoticz(dev_id, unit, sValue, nValue, TimedOut)` - Update Domoticz device

### RGBIC Light Support
- `encode_draw_tool_command()` - Encode multi-LED commands
- `decode_draw_tool_status()` - Decode LED status
- `detect_white_channel_type()` - Detect RGBW vs RGB
- `send_draw_tool_command_local()` - Local LED command sending

## User Notes

### Device Not Working?
1. Check if device is in correct category
2. Verify device has proper DPS mapping
3. Check logs for error messages
4. Test with tinytuya directly if possible

### Protocol Issues
- Protocol 3.4 devices may need cloud fallback
- Check device version in device properties
- Enable debug logging for detailed communication logs

### Color Problems
- Check if device is RGB, RGBW, or RGBWW
- Verify bright_value max in device properties
- Enable debug logging to see draw_tool commands