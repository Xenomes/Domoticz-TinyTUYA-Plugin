# DomoticzEx TUYA Plugin
#
# Author: Xenomes (xenomes@outlook.com)
#
"""
<plugin key="tinytuya" name="TinyTUYA" author="Xenomes" version="3.0.0" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git">
    <description>
        Support forum:
        <a href="https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441">
            https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441
        </a>
        <br/><br/>

        <h2>TinyTuya Plugin - Hybrid Local / Cloud Control version 3.0.0</h2><br/>

        This plugin uses the Tuya IoT Cloud Platform <b>only for initial device discovery, DPS mapping and configuration</b>.
        Once devices are configured, commands and status updates are handled locally using <b>TinyTuya</b> whenever possible.
        If a device is not reachable locally, the plugin automatically falls back to Tuya Cloud control.
        <br/><br/>

        Cloud setup instructions can be found here:<br/>
        https://github.com/jasonacox/tinytuya (step 3)<br/>
        or via PDF:<br/>
        https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf
        <br/><br/>

        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Automatic discovery of Tuya devices using the Tuya IoT Cloud</li>
            <li>Automatic DPS (data point) detection and mapping</li>
            <li>Local device control via TinyTuya (LAN)</li>
            <li>Automatic fallback to Tuya Cloud when local control is unavailable</li>
            <li>On/Off control, dimming, color temperature and device-specific features</li>
            <li>Status updates from local devices when available</li>
        </ul>

        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>Most Tuya-based WiFi devices are supported</li>
            <li>Support depends on available DPS provided by the device</li>
        </ul>

        <h3>Configuration</h3>
        <ul style="list-style-type:square">
            <li>
                Enter your <b>Region</b>, <b>Access ID / Client ID</b>,
                <b>Access Secret / Client Secret</b> and a <b>Search Device ID</b>
                from your Tuya IoT account.
            </li>
            <li>
                A Device ID can be found in the Tuya IoT platform:
                Cloud → Your Project → Devices → select a device.
                This Device ID is only used to discover all other devices.
            </li>
            <li>
                Complete the initial setup of your devices using the official Tuya app.
                The plugin will automatically import device settings, DPS mapping and local keys.
            </li>
            <li>
                Set the API polling interval carefully.
                Due to Tuya API rate limits, a <b>15-minute interval</b> is recommended for most accounts.
                Keep the <b>Data Timeout</b> option disabled.
            </li>
            <li>
                After setup, the plugin minimizes cloud usage and prefers local LAN communication.
            </li>
        </ul>

        If your Tuya Cloud development subscription has expired, you can extend it
        <a href="https://iot.tuya.com/cloud/products/apply-extension">HERE</a>.
    </description>
    <params>
        <param field="Mode1" label="Region" width="150px" required="true" default="EU">
            <options>
                <option label="EU" value="eu" default="true" />
                <option label="US" value="us"/>
                <option label="CN" value="cn"/>
                <option label="IND" value="in"/>
            </options>
        </param>
        <param field="Username" label="Access ID" width="300px" required="true" default="" />
        <param field="Password" label="Access Secret" width="300px" required="true" default="" password="true" />
        <param field="Mode2" label="Search DeviceID" width="300px" required="true" />
        <param field="Mode3" label="API Polling interval" width="150px" required="true" default="15 minutes">
            <options>
                <option label="1 minute" value="60" />
                <option label="5 minutes" value="300" />
                <option label="10 minutes" value="600" />
                <option label="15 minutes" value="900" />
                <option label="30 minutes" value="1800" default="true"/>
                <option label="1 hour" value="3600" />
                <option label="2 hour" value="7200" />
                <option label="3 hour" value="10800" />
                <option label="6 hour" value="21600" />
                <option label="12 hour" value="21600" />
            </options>
        </param>
        <param field="Mode4" label="Local IP rescan interval" width="200px" required="true" default="3600">
            <options>
                <option label="1 hour" value="3600"/>
                <option label="6 hours" value="21600"/>
                <option label="12 hours" value="43200"/>
                <option label="24 hours" value="86400" default="true"/>
                <option label="Static (no rescan)" value="0"/>
            </options>
        </param>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic + Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections + Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
import os
import sys
import ast
import json
import colorsys
import time
import re
import base64
import traceback

# Runtime timing 
synctime = 900
ip_scan_interval = 3600
last_update = 0
last_ip_scan = 0

try:
    import DomoticzEx
except ImportError:
    import fakeDomoticz as DomoticzEx
try:
    import tinytuya
except ImportError:
    print('No tinytuya module installed')
    SystemExit
print(f'Tinytuya version: {tinytuya.version}')
class BasePlugin:
    def __init__(self):
        self.enabled = True
        return

    def onStart(self):
        if Parameters['Mode6'] != '0':
            DomoticzEx.Debugging(int(Parameters['Mode6']))
            # DomoticzEx.Log('Debugger started, use 'telnet 0.0.0.0 4444' to connect')
            # import rpdb
            # rpdb.set_trace()
            DumpConfigToLog()

        DomoticzEx.Log('TinyTUYA ' + Parameters['Version'] + ' plugin started')
        DomoticzEx.Log('TinyTuya Version: ' + tinytuya.version )

        global testdata, Error, fulllocal

        if os.path.isfile(Parameters['HomeFolder'] + '/debug_devices.json'):
            testdata = True
            fulllocal = False
            DomoticzEx.Error('!!! Warning Plugin overruled by local json files !!!')
        elif os.path.isfile(Parameters['HomeFolder'] + '/tuya-raw.json'):
            testdata = False
            fulllocal = True
            DomoticzEx.Debug('Plugin is full local mode from tuya-raw.json')
        else:
            testdata = False
            fulllocal = False
        # DomoticzEx.Heartbeat(2)
        onHandleThread(True, False)

    def onStop(self):
        DomoticzEx.Log('onStop called')

        try:
            # Cleanup devices that are not recognized
            devs = Devices
            for dev in devs:
                if 'This device is not recognized.' in Devices[dev].Units[1].sValue:
                    Devices[dev].Units[1].Delete()
        except Exception as e:
            DomoticzEx.Error(f'Error during device cleanup: {e}')

        # Start the shutdown process
        start_time = time.time()

        DomoticzEx.Log('Exiting plugin.')

    def onConnect(self, Connection, Status, Description):
        DomoticzEx.Log('onConnect called')

    def onMessage(self, Connection, Data):
        DomoticzEx.Log('onMessage called')

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        DomoticzEx.Debug("onCommand called for Device " +
                       str(DeviceID) + " Unit " +
                       str(Unit) + ": Parameter '" +
                       str(Command) + "', Level: " +
                       str(Level) + "', Color: " +
                       str(Color))

        # device for the DomoticzEx
        dev = Devices[DeviceID].Units[Unit]
        DomoticzEx.Debug('Device ID: ' + str(DeviceID))
        DomoticzEx.Debug('nValue: ' + str(dev.nValue))
        DomoticzEx.Debug('sValue: ' + str(dev.sValue) + ' Type ' + str(type(dev.sValue)))
        DomoticzEx.Debug('LastLevel: ' + str(dev.LastLevel))

        try:
            if Error is not None:
                DomoticzEx.Error(Error['Payload'])
            else:
                # Control device and update status in DomoticzEx
                dev_type = getConfigItem(DeviceID, 'category')
                # scalemode = getConfigItem(DeviceID, 'scalemode')
                product_id = getConfigItem(DeviceID, 'product_id')
                # if len(properties) == 0:
                #     properties = {}
                #     for dev in devs:
                #         properties[dev_id] = tuya.getproperties(dev_id)['result']

                function = properties[DeviceID]['functions']
                status = properties[DeviceID]['status']
                if len(Color) != 0: 
                    Color = ast.literal_eval(Color)

                if dev_type in ('switch', 'switch/sensor'):
                    if searchCode('switch', function):
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, 'switch', False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, 'switch', True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    else:
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, 'switch_' + str(Unit), False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, 'switch_' + str(Unit), True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'wswitch':
                    if Command == 'Set Level':
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        if searchCode('switch' + str(Unit) + '_value', status):
                            SendCommandTuya(DeviceID, 'switch' + str(Unit) + '_value', mode[int(Level / 10)])
                        if searchCode('switch_type_' + str(Unit), status):
                            SendCommandTuya(DeviceID, 'switch_type_' + str(Unit), mode[int(Level / 10)])
                        if searchCode('switch_mode' + str(Unit), status):
                            SendCommandTuya(DeviceID, 'switch_mode' + str(Unit), mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type in ('dimmer'):
                    if Command == 'Off':
                        SendCommandTuya(DeviceID, 'switch_led_' + str(Unit), False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'Set Level':
                        SendCommandTuya(DeviceID, 'switch_led_' + str(Unit), True)
                        SendCommandTuya(DeviceID, 'bright_value_' + str(Unit), Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if (dev_type in ('light') or dev_type in ('fanlight') or dev_type in ('pirlight')) and Unit == 1:
                    if searchCode('led_switch', function):
                        switch = 'led_switch'
                    elif searchCode('switch_led', function):
                        switch = 'switch_led'
                    elif searchCode('Light', function):
                        switch = 'Light'

                    if Command == 'Off':
                        SendCommandTuya(DeviceID, switch, False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandTuya(DeviceID, switch, True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level':
                        if searchCode('bright_value_v2', function):
                            SendCommandTuya(DeviceID, switch, True)
                            SendCommandTuya(DeviceID, 'bright_value_v2', Level)
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                        elif searchCode('bright_value', function):
                            SendCommandTuya(DeviceID, switch, True)
                            SendCommandTuya(DeviceID, 'bright_value', Level)
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif (Command == 'Set Color' or Command == 'Set Level') and len(Color) != 0:
                        SendCommandTuya(DeviceID, switch, True)
                        if Color['m'] == 2:
                            SendCommandTuya(DeviceID, 'work_mode', 'white')
                            if searchCode('bright_value_v2', function):
                                SendCommandTuya(DeviceID, 'bright_value_v2', Level)
                                SendCommandTuya(DeviceID, 'temp_value_v2', int(Color['t']))
                                # UpdateDomoticz(DeviceID, Unit, json.dumps(Color), 1, 0)
                                # UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                            elif searchCode('bright_value', function):
                                SendCommandTuya(DeviceID, 'bright_value', Level)
                                SendCommandTuya(DeviceID, 'temp_value', int(Color['t']))
                                # UpdateDomoticz(DeviceID, Unit, json.dumps(Color), 1, 0)
                                # UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                        elif Color['m'] == 3:
                            SendCommandTuya(DeviceID, 'work_mode', 'colour')
                            rgbcolor = format(rgb_temp(Color['r'], Level), '02x') + format(rgb_temp(Color['g'], Level), '02x') + format(rgb_temp(Color['b'], Level), '02x') + '0000ffff'
                            if searchCode('colour_data_v2', function):
                                SendCommandTuya(DeviceID, 'colour_data_v2', rgbcolor)
                                # UpdateDomoticz(DeviceID, Unit, json.dumps(Color), 1, 0)
                                # UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                            elif searchCode('colour_data', function):
                                SendCommandTuya(DeviceID, 'colour_data', rgbcolor)
                                # UpdateDomoticz(DeviceID, Unit, json.dumps(Color), 1, 0)
                                # UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                if dev_type in ('light') and Unit == 2:
                    if searchCode('Power', function):
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, 'Power', False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, 'Power', True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                if dev_type in ('light') and Unit == 3:
                    if searchCode('lightmode', function):
                        switch = 'lightmode'
                        if Command == 'Set Level' and Unit  == 3:
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, switch, mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                if dev_type in ('light') and Unit == 4:
                    if searchCode('dp_mist_grade', function):
                        switch = 'dp_mist_grade'
                        if Command == 'Set Level' and Unit  == 4:
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, switch, mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type == ('cover'):
                    ext = '_' + str(Unit) if Unit > 1 else ''
                    if Command == 'Open':
                        if searchCode('mach_operate' + ext, function):
                            SendCommandTuya(DeviceID, 'mach_operate' + ext, 'FZ')
                        elif searchCode('status' + ext , function):
                            SendCommandTuya(DeviceID, 'status', '1')
                        else:
                            SendCommandTuya(DeviceID, 'control' + ext, 'open')
                        UpdateDomoticz(DeviceID, Unit, 'Open', 0, 0)
                    elif Command == 'Close':
                        if searchCode('mach_operate' + ext, function):
                            SendCommandTuya(DeviceID, 'mach_operate' + ext, 'ZZ')
                        elif searchCode('status' + ext , function):
                            SendCommandTuya(DeviceID, 'status', '2')
                        else:
                            SendCommandTuya(DeviceID, 'control' + ext, 'close')
                        UpdateDomoticz(DeviceID, Unit, 'Close', 1, 0)
                    elif Command == 'Stop':
                        if searchCode('mach_operate' + ext, function):
                            SendCommandTuya(DeviceID, 'mach_operate' + ext, 'STOP')
                        elif searchCode('status' + ext , function):
                            SendCommandTuya(DeviceID, 'status', '3')
                        else:
                            SendCommandTuya(DeviceID, 'control' + ext, 'stop')
                        UpdateDomoticz(DeviceID, Unit, 'Stop', 1, 0)
                    elif Command == 'Set Level':
                        if searchCode('percent_control' + ext, function):
                            control = 'percent_control' + ext
                        elif searchCode('position' + ext, function):
                            control = 'position' + ext
                        SendCommandTuya(DeviceID, control, Level)
                        UpdateDomoticz(DeviceID, 1, Level, 1, 0)

                elif dev_type == 'smartheatpump' :
                    if searchCode('switch', function):
                        switch = 'switch'
                        if Command == 'Off' and Unit == 1:
                            SendCommandTuya(DeviceID, switch, False)
                            UpdateDomoticz(DeviceID, 1, False, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandTuya(DeviceID, switch, True)
                            UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    if searchCode('ach_stemp', function):
                        switch = 'ach_stemp'
                        if Command == 'Set Level' and Unit  == 11:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 11, Level, 1, 0)
                    if searchCode('wth_stemp', function):
                        switch = 'wth_stemp'
                        if Command == 'Set Level' and Unit  == 12:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 12, Level, 1, 0)
                    if searchCode('aircond_temp_diff', function):
                        switch = 'aircond_temp_diff'
                        if Command == 'Set Level' and Unit  == 13:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 13, Level, 1, 0)
                    if searchCode('wth_temp_diff', function):
                        switch = 'wth_temp_diff'
                        if Command == 'Set Level' and Unit  == 14:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 14, Level, 1, 0)
                    if searchCode('acc_stemp', function):
                        switch = 'acc_stemp'
                        if Command == 'Set Level' and Unit  == 15:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 15, Level, 1, 0)
                    if searchCode('mode', function):
                        if Command == 'Set Level' and Unit == 16:
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, 16, Level, 1, 0)
                    if searchCode('work_mode', function):
                        if Command == 'Set Level' and Unit == 17:
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, 'work_mode', mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, 17, Level, 1, 0)
                    if searchCode('temp_set', function):
                        switch = 'temp_set'
                        if Command == 'Set Level' and Unit  == 19:
                            SendCommandTuya(DeviceID, switch, Level)
                            UpdateDomoticz(DeviceID, 19, Level, 1, 0)
                    # if searchCode('water_set', function):
                    #     switch = 'water_set'
                    #     if Command == 'Set Level' and Unit  == 20:
                    #         SendCommandTuya(DeviceID, switch, Level)
                    #         UpdateDomoticz(DeviceID, 20, Level, 1, 0)
                    if searchCode('compressor_state', function):
                        switch = 'compressor_state'
                        if Command == 'Off' and Unit == 24:
                            SendCommandTuya(DeviceID, switch, False)
                            UpdateDomoticz(DeviceID, 24, False, 0, 0)
                        elif Command == 'On' and Unit == 24:
                            SendCommandTuya(DeviceID, switch, True)
                            UpdateDomoticz(DeviceID, 24, True, 1, 0)

                elif dev_type == 'thermostat' or dev_type == 'heater'or dev_type == 'heatpump':
                    if searchCode('switch_1', function):
                        switch = 'switch_1'
                    elif searchCode('Power', function):
                        switch = 'Power'
                    elif searchCode('infared_switch', function):
                        switch = 'infared_switch'
                    else:
                        switch = 'switch'
                    if searchCode('temp_set', function):
                        switch3 = 'temp_set'
                    elif searchCode('set_temp', function):
                        switch3 = 'set_temp'
                    elif searchCode('temperature_c', function):
                        switch3 = 'temperature_c'
                    elif searchCode('TempSet', function):
                        switch3 = 'TempSet'
                    elif searchCode('target_temp', function):
                        switch3 = 'target_temp'
                    if searchCode('Mode', function):
                        switch4 = 'Mode'
                    elif searchCode('mode', function):
                        switch4 = 'mode'
                    #Disabled for isseu #147
                    # elif searchCode('work_mode', function):
                    #     switch4 = 'work_mode'
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, switch, False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, switch, True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 3:
                        SendCommandTuya(DeviceID, switch3, Level)
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = getConfigItem(str(DeviceID) + '-4', 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, switch4, mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)
                    if Command == 'Off' and Unit == 5:
                        SendCommandTuya(DeviceID, 'window_check', False)
                        UpdateDomoticz(DeviceID, 5, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandTuya(DeviceID, 'window_check', True)
                        UpdateDomoticz(DeviceID, 5, True, 1, 0)
                    if Command == 'Off' and Unit == 6:
                        SendCommandTuya(DeviceID, 'child_lock', False)
                        UpdateDomoticz(DeviceID, 6, False, 0, 0)
                    elif Command == 'On' and Unit == 6:
                        SendCommandTuya(DeviceID, 'child_lock', True)
                        UpdateDomoticz(DeviceID, 6, True, 1, 0)
                    if Command == 'Off' and Unit == 7:
                        SendCommandTuya(DeviceID, 'eco', False)
                        UpdateDomoticz(DeviceID, 7, False, 0, 0)
                    elif Command == 'On' and Unit == 7:
                        SendCommandTuya(DeviceID, 'eco', True)
                        UpdateDomoticz(DeviceID, 7, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 9:
                        if searchCode('fan_level', function) or searchCode('fan_speed_enum', function):
                            mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                            SendCommandTuya(DeviceID, 9, mode[int(Level / 10)])
                            UpdateDomoticz(DeviceID, 9, Level, 1, 0)
                        else:
                            wind = 'windspeed'
                            SendCommandTuya(DeviceID, wind, Level)
                            UpdateDomoticz(DeviceID, 9, Level, 1, 0)
                    if Command == 'Off' and Unit == 17:
                        SendCommandTuya(DeviceID, 'anti_bother', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 17:
                        SendCommandTuya(DeviceID, 'anti_bother', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'sensor':
                    if Command == 'Set Level' and Unit == 15:
                        SendCommandTuya(DeviceID, 'ph_warn_min', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 16:
                        SendCommandTuya(DeviceID, 'ph_warn_max', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 17:
                        SendCommandTuya(DeviceID, 'pro_warn_min', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 18:
                        SendCommandTuya(DeviceID, 'pro_warn_max', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 19:
                        SendCommandTuya(DeviceID, 'orp_warn_min', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 20:
                        SendCommandTuya(DeviceID, 'orp_warn_max', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 24:
                        SendCommandTuya(DeviceID, 'temp_warn_min', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 25:
                        SendCommandTuya(DeviceID, 'temp_warn_max', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 45:
                        SendCommandTuya(DeviceID, 'cook_temperature', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Set Level' and Unit == 46:
                        SendCommandTuya(DeviceID, 'cook_temperature_2', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    # if Command == 'Off' and Unit == 47:
                    #     SendCommandTuya(DeviceID, 'alarm_switch', False)
                    #     UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    # elif Command == 'On' and Unit == 47:
                    #     SendCommandTuya(DeviceID, 'alarm_switch', True)
                    #     UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'doorbell':
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'floodlight_switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'floodlight_switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'fan':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'fan_speed', int(mode[int(Level / 10)]))
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit  == 4:
                        SendCommandTuya(DeviceID, 'set_temp', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Off' and Unit == 7:
                        SendCommandTuya(DeviceID, 'light', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 7:
                        SendCommandTuya(DeviceID, 'light', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 8:
                        SendCommandTuya(DeviceID, 'RH_switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 8:
                        SendCommandTuya(DeviceID, 'RH_switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 11:
                        SendCommandTuya(DeviceID, 'anion', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 11:
                        SendCommandTuya(DeviceID, 'anion', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 12:
                        SendCommandTuya(DeviceID, 'free_cooling', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 12:
                        SendCommandTuya(DeviceID, 'free_cooling', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 13:
                        SendCommandTuya(DeviceID, 'powerful', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 13:
                        SendCommandTuya(DeviceID, 'powerful', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'fanlight':
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'fan_switch', False)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'fan_switch', True)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'fan_speed', int(mode[int(Level / 10)]))
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'fan_direction', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'powermeter' and searchCode('switch', function):
                    if Command == 'Off':
                        SendCommandTuya(DeviceID, 'switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandTuya(DeviceID, 'switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'powermeter' and searchCode('switch_1', function):
                    if Command == 'Off':
                        SendCommandTuya(DeviceID, 'switch_1', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandTuya(DeviceID, 'switch_1', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'siren':
                    if Command == 'Off':
                        SendCommandTuya(DeviceID, 'AlarmSwitch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandTuya(DeviceID, 'AlarmSwitch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    # Other Type of alarm with same code
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'muffling', False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'muffling', True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'alarm_state', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'alarm_volume', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)

                if dev_type == 'pirlight':
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'switch_pir', False)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'switch_pir', True)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'device_mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'pir_sensitivity', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'garagedooropener':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch_1', False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch_1', True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)

                if dev_type == 'feeder':
                    if Command == 'Off' and Unit == 5:
                        SendCommandTuya(DeviceID, 'light', False)
                        UpdateDomoticz(DeviceID, 5, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandTuya(DeviceID, 'light', True)
                        UpdateDomoticz(DeviceID, 5, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 1:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'manual_feed', int(mode[int(Level / 10)]))
                        UpdateDomoticz(DeviceID, 1, Level, 1, 0)

                if dev_type == 'irrigation':
                    if searchCode('switch_1', function):
                        switch = 'switch_1'
                    else:
                        switch = 'switch'
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, switch, False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, switch, True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    if Command == 'Off' and Unit == 3:
                        SendCommandTuya(DeviceID, 'areaone', False)
                        UpdateDomoticz(DeviceID, 3, False, 0, 0)
                    elif Command == 'On' and Unit == 3:
                        SendCommandTuya(DeviceID, 'areaone', True)
                        UpdateDomoticz(DeviceID, 3, True, 1, 0)
                    if Command == 'Off' and Unit == 4:
                        SendCommandTuya(DeviceID, 'areatwo', False)
                        UpdateDomoticz(DeviceID, 4, False, 0, 0)
                    elif Command == 'On' and Unit == 4:
                        SendCommandTuya(DeviceID, 'areatwo', True)
                        UpdateDomoticz(DeviceID, 4, True, 1, 0)
                    if Command == 'Off' and Unit == 5:
                        SendCommandTuya(DeviceID, 'areathree', False)
                        UpdateDomoticz(DeviceID, 5, False, 0, 0)
                    elif Command == 'On' and Unit == 5:
                        SendCommandTuya(DeviceID, 'areathree', True)
                        UpdateDomoticz(DeviceID, 5, True, 1, 0)
                    if Command == 'Off' and Unit == 6:
                        SendCommandTuya(DeviceID, 'areafour', False)
                        UpdateDomoticz(DeviceID, 6, False, 0, 0)
                    elif Command == 'On' and Unit == 6:
                        SendCommandTuya(DeviceID, 'areafour', True)
                        UpdateDomoticz(DeviceID, 6, True, 1, 0)
                    if Command == 'Off' and Unit == 7:
                        SendCommandTuya(DeviceID, 'areafive', False)
                        UpdateDomoticz(DeviceID, 7, False, 0, 0)
                    elif Command == 'On' and Unit == 7:
                        SendCommandTuya(DeviceID, 'areafive', True)
                        UpdateDomoticz(DeviceID, 7, True, 1, 0)
                    if Command == 'Off' and Unit == 8:
                        SendCommandTuya(DeviceID, 'areasix', False)
                        UpdateDomoticz(DeviceID, 8, False, 0, 0)
                    elif Command == 'On' and Unit == 8:
                        SendCommandTuya(DeviceID, 'areasix', True)
                        UpdateDomoticz(DeviceID, 8, True, 1, 0)

                if dev_type == 'starlight':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch_led', False)
                        SendCommandTuya(DeviceID, 'colour_switch', False)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch_led', True)
                        SendCommandTuya(DeviceID, 'colour_switch', True)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 1:
                        Color = Devices[DeviceID].Units[1].Color
                        if Color == '':
                            Color ={'b':255,'cw':0,'g':255,'m':3,'r':255,'t':0,'ww':0}
                        h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                        hvs = {'h':h, 's':s, 'v':Level * 10}
                        SendCommandTuya(DeviceID, 'colour_data', hvs)
                        SendCommandTuya(DeviceID, 'colour_switch', True)
                        UpdateDomoticz(DeviceID, 1, json.dumps(Color), 1, 0)
                    elif Command == 'Set Color' and Unit == 1: #
                        h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                        hvs = {'h':h, 's':s, 'v':Level * 10}
                        SendCommandTuya(DeviceID, 'colour_data', hvs)
                        SendCommandTuya(DeviceID, 'colour_switch', True)
                        UpdateDomoticz(DeviceID, 1, json.dumps(Color), 1, 0)
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'colour_switch', False)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'colour_switch', True)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    if Command == 'Off' and Unit == 3:
                        SendCommandTuya(DeviceID, 'laser_switch', False)
                        UpdateDomoticz(DeviceID, 3, False, 0, 0)
                    elif Command == 'On' and Unit == 3:
                        SendCommandTuya(DeviceID, 'laser_switch', True)
                        UpdateDomoticz(DeviceID, 3, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        SendCommandTuya(DeviceID, 'laser_switch', True)
                        SendCommandTuya(DeviceID, 'laser_bright', 21.25 + ((Level / 100) * 78.75)) # 21.25 + ((Level / 100) * 78.75) ) * 10
                        UpdateDomoticz(DeviceID, 3, True, 1, 0)
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    if Command == 'Off' and Unit == 4:
                        SendCommandTuya(DeviceID, 'fan_switch', False)
                        UpdateDomoticz(DeviceID, 4, False, 0, 0)
                    elif Command == 'On' and Unit == 4:
                        SendCommandTuya(DeviceID, 'fan_switch', True)
                        UpdateDomoticz(DeviceID, 4, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        SendCommandTuya(DeviceID, 'fan_switch', True)
                        SendCommandTuya(DeviceID, 'fan_speed', Level)
                        UpdateDomoticz(DeviceID, 4, True, 1, 0)
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'smartlock':
                    if searchCode('lock_motor_state', function):
                        if Command == 'Off' and Unit == 1:
                            SendCommandTuya(DeviceID, 'lock_motor_state', False)
                            UpdateDomoticz(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandTuya(DeviceID, 'lock_motor_state', True)
                            UpdateDomoticz(DeviceID, 1, 0, 1, 0)
                    elif searchCode('rtc_lock', function):
                        if Command == 'Off' and Unit == 1:
                            SendCommandTuya(DeviceID, 'rtc_lock', 0)
                            UpdateDomoticz(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandTuya(DeviceID, 'rtc_lock', 1)
                            UpdateDomoticz(DeviceID, 1, 0, 1, 0)
                    else:
                        if Command == 'Off' and Unit == 1:
                            SendCommandTuya(DeviceID, 'switch', False)
                            UpdateDomoticz(DeviceID, 1, 10, 0, 0)
                        elif Command == 'On' and Unit == 1:
                            SendCommandTuya(DeviceID, 'switch', True)
                            UpdateDomoticz(DeviceID, 1, 0, 1, 0)

                if dev_type == 'dehumidifier':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 2:
                        if searchCode('dehumidify_set_value', function):
                            tdev = 'dehumidify_set_value'
                        elif searchCode('dehumidify_set_enum', function):
                            tdev = 'dehumidify_set_enum'
                        SendCommandTuya(DeviceID, tdev, Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'fan_speed_enum', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    if Command == 'Off' and Unit == 9:
                        SendCommandTuya(DeviceID, 'child_lock', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 9:
                        SendCommandTuya(DeviceID, 'child_lock', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 10:
                        SendCommandTuya(DeviceID, 'anion', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 10:
                        SendCommandTuya(DeviceID, 'anion', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 11:
                        SendCommandTuya(DeviceID, 'filter_life', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 11:
                        SendCommandTuya(DeviceID, 'filter_life', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    if Command == 'Off' and Unit == 13:
                        SendCommandTuya(DeviceID, 'runtime_total_reset', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 13:
                        SendCommandTuya(DeviceID, 'anruntime_total_resetion', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'vacuum':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'power_go', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'power_go', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'suction', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 5:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'cistern', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'purifier':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'switch', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'speed', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'smartkettle':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'start', False)
                        UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'start', True)
                        UpdateDomoticz(DeviceID, Unit, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 4:
                        SendCommandTuya(DeviceID, 'cook_temperature', Level)
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)

                if dev_type == 'mower':
                    if Command == 'Set Level' and Unit == 1:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'MachineControlCmd', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 1, Level, 1, 0)
                    if Command == 'Off' and Unit == 2:
                        SendCommandTuya(DeviceID, 'MachineRainMode', False)
                        UpdateDomoticz(DeviceID, 2, False, 0, 0)
                    elif Command == 'On' and Unit == 2:
                        SendCommandTuya(DeviceID, 'MachineRainMode', True)
                        UpdateDomoticz(DeviceID, 2, True, 1, 0)
                    if Command == 'Set Level' and Unit == 6:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'MachineWorkMode', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 6, Level, 1, 0)

                if dev_type == 'human_presence':
                    if Command == 'Set Level' and Unit == 2:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'sensitivity', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit  == 3:
                        SendCommandTuya(DeviceID, 'near_detection', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)
                    elif Command == 'Set Level' and Unit  == 4:
                        SendCommandTuya(DeviceID, 'far_detection', Level)
                        UpdateDomoticz(DeviceID, Unit, Level, 1, 0)

                if dev_type == 'evcharger':
                    if searchCode('switch', function):
                        if Command == 'Off':
                            SendCommandTuya(DeviceID, 'switch', False)
                            UpdateDomoticz(DeviceID, Unit, False, 0, 0)
                        elif Command == 'On':
                            SendCommandTuya(DeviceID, 'switch', True)
                            UpdateDomoticz(DeviceID, Unit, True, 1, 0)

                if dev_type == 'infrared_ac':
                    if Command == 'Off' and Unit == 1:
                        SendCommandTuya(DeviceID, 'PowerOff', 'PowerOff')
                        UpdateDomoticz(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandTuya(DeviceID, 'PowerOn', 'PowerOn')
                        UpdateDomoticz(DeviceID, 1, True, 1, 0)
                    elif Command == 'Set Level' and Unit  == 2:
                        SendCommandTuya(DeviceID, 'T', Level)
                        UpdateDomoticz(DeviceID, 2, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 3:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'M', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 3, Level, 1, 0)
                    elif Command == 'Set Level' and Unit == 4:
                        mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandTuya(DeviceID, 'F', mode[int(Level / 10)])
                        UpdateDomoticz(DeviceID, 4, Level, 1, 0)
        except Exception as e:
            DomoticzEx.Error('onCommand ERROR: {}'.format(str(e)))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        DomoticzEx.Log('Notification: ' + Name + ', ' + Subject + ', ' + Text + ', ' + Status + ', ' + str(Priority) + ', ' + Sound + ', ' + ImageFile)

    def onDeviceRemoved(self, DeviceID, Unit):
        DomoticzEx.Log('onDeviceDeleted called')

    def onDisconnect(self, Connection):
        DomoticzEx.Log('onDisconnect called')

    def onHeartbeat(self):
        DomoticzEx.Debug('onHeartbeat called')

        onHandleThread(False, True)

        DomoticzEx.Debug(f'Heartbeat check for sync {time.time() - last_update} >= {synctime} and fulllocal={fulllocal}')
        if time.time() - last_update >= synctime and not fulllocal:
            onHandleThread(False, False)

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onHandleThread(startup, local):
    global tuya, devs, properties, dps_map, result, product_id, Error
    global last_update, last_ip_scan, localtuya, testdata
    global cloud_status_cache, cloud_status_time
    global FunctionProperties, StatusProperties, ResultValue, dev_type, line

    try:
        # INIT (startup only) 
        if startup and not local:
            DomoticzEx.Log('Initializing Tuya plugin')

            last_update = 0
            last_ip_scan = 0

            devs = []
            snap = []
            ResultValue = []
            properties = {}
            dps_map = {}
            result = {}
            localtuya = {}
            cloud_status_cache = {}
            cloud_status_time = {}
            online = True
            Error = None
            line = 0

            global synctime, ip_scan_interval

            synctime = int(Parameters.get('Mode3') or 900)
            ip_scan_interval = int(Parameters.get('Mode4') or 86400)

            if not fulllocal:
                # Cloud init 
                DomoticzEx.Log('Cloud mode: fetching device data from Tuya cloud')
                if 'tuya' not in globals():
                    try:
                        tuya = tinytuya.Cloud(
                            apiRegion=Parameters['Mode1'],
                            apiKey=Parameters['Username'],
                            apiSecret=Parameters['Password'],
                            apiDeviceID=Parameters['Mode2']
                        )
                    except Exception as e:
                        DomoticzEx.Error(f"Tuya initialization failed: {e}")
                        return

                # Stop script immediately if Tuya reports an error
                if hasattr(tuya, 'error') and tuya.error:
                    error_msg = tuya.error.get('Payload', tuya.error)
                    DomoticzEx.Error(f"Tuya API error: {error_msg}")
                    return

                tuya.use_old_device_list = True
                tuya.new_sign_algorithm = True

                # Fetch devices 
                for attempt in range(4):
                    try:
                        devs = tuya.getdevices()
                        if devs:
                            break
                    except:
                        DomoticzEx.Log('No device data returned, retrying...')
                        time.sleep(1)

                if not devs:
                    raise Exception('No device data returned from Tuya cloud')
                
                # Fetch schemas 
                for dev in devs:
                    dev_id = dev['id']

                    props = tuya.getproperties(dev_id).get('result', {})
                    props.setdefault('functions', [])
                    props.setdefault('status', [])
                    properties[dev_id] = props

                    result[dev_id] = tuya.getstatus(dev_id).get('result', {})

                    dps_map[dev_id] = {'by_code': {}, 'by_id': {}}
                    schema = tuya.getdps(dev_id)
                    if schema['success']:
                        for f in schema['result'].get('status', []):
                            dps_map[dev_id]['by_code'][f['code']] = f['dp_id']
                            dps_map[dev_id]['by_id'][f['dp_id']] = f['code']
            elif fulllocal:
                DomoticzEx.Log('Full local mode: loading device data from files')
                with open(Parameters['HomeFolder'] + '/tuya-raw.json') as dFile:
                    raw = json.load(dFile)
                    
                devs = raw.get('result', [])
                DomoticzEx.Debug(f'Loading {len(devs)} devices from tuya-raw.json')

                with open(Parameters['HomeFolder'] + '/snapshot.json') as eFile:
                    raw = json.load(eFile)
                snap = raw.get('devices', [])

                for dev in devs:
                    dev_id = dev['id']

                    if not dev.get('mapping'):
                        DomoticzEx.Error(f"!! Warning Mapping data is missing for {dev_id} !!")
                        continue

                    # ensure properties entry exists
                    properties.setdefault(dev_id, {'functions': [], 'status': []})
                    localtuya.setdefault(dev_id, {})

                    # fix mismatched fieldsproperties
                    dev['results'] = dev['status']
                    dev.pop('status', None)
                    dev['key'] = dev['local_key']
                    dev.pop('local_key', None)
                    for snap_dev in snap:
                        if snap_dev.get('id') == dev_id:
                            dev['ip'] = snap_dev.get('ip', dev.get('ip', '127.0.0.1'))
                            dev['version'] = snap_dev.get('ver', '3.3')
                            break
                    # mapping => functions/status
                    schema_list = []
                    for item in dev.get('mapping', {}).values():
                        raw_values = item.get('values', {})

                        if isinstance(raw_values, str):
                            # values is al JSON-string → eerst normaliseren
                            try:
                                raw_values = json.loads(raw_values)
                            except json.JSONDecodeError:
                                raw_values = {}

                        values_json = json.dumps(
                            raw_values,
                            ensure_ascii=False,
                            separators=(',', ':')
                        )

                        schema_list.append({
                            'code': item['code'],
                            'desc': values_json,
                            'name': '',
                            'type': item['type'],
                            'values': values_json
                        })
                    properties[dev_id] = dev

                    properties[dev_id]['functions'] = json.dumps(schema_list, ensure_ascii=False, separators=(',', ':'))
                    dev['functions'] = schema_list
                    properties[dev_id]['status'] = json.dumps(schema_list, ensure_ascii=False, separators=(',', ':'))
                    dev['status'] = schema_list
                    
                    # DPS map (offline replacement for tuya.getdps)
                    dps_map[dev_id] = {'by_code': {}, 'by_id': {}}
                    for dp_id, item in dev.get('mapping', {}).items():
                        dp_id = int(dp_id)
                        code = item['code']
                        dps_map[dev_id]['by_code'][code] = dp_id
                        dps_map[dev_id]['by_id'][dp_id] = code

                    # remove unused fields
                    dev.pop('mapping', None)

                    # status values
                    result[dev_id] = json.dumps(dev['results'], ensure_ascii=False, separators=(',', ':'))

                    localtuya[dev_id] = dev

                    # DomoticzEx.Debug(f'Convert {json.dumps(devs, indent=2)}')
                    # DomoticzEx.Debug(f'Localtuya {localtuya}')
                    # DomoticzEx.Debug(f'Loaded device {dev} from snapshot')
                    # DomoticzEx.Debug(f'Loaded device {dev_id} with properties {properties[dev_id]} and result {result[dev_id]}')

            # Active testdata loop 
            if testdata:
                tuya = DomoticzEx.Log
                # Devices
                with open(Parameters['HomeFolder'] + '/debug_devices.json') as dFile:
                    devs = json.load(dFile)

                # Functies / status
                properties = {}

                with open(Parameters['HomeFolder'] + '/debug_functions.json') as fFile:
                    raw = json.load(fFile)

                for dev in devs:
                    dev_id = dev['id']
                    properties[dev_id] = raw['result']

                    if not properties[dev_id].get('functions'):
                        DomoticzEx.Error(f"!! Warning Functions data is missing for {dev_id} !!")

                    if not properties[dev_id].get('status'):
                        DomoticzEx.Error(f"!! Warning Status data is missing for {dev_id} !!")
            # Initial local scan 
            if not testdata and not fulllocal:
                try:
                    DomoticzEx.Log('Initial Tuya IP scan, Please wait...')
                    localtuya = tinytuya.deviceScan(verbose=False, maxretry=None, byID=True)
                    last_ip_scan = time.time()
                except:
                    localtuya = {}

        # Periodic IP scan 
        if (not startup and not testdata and ip_scan_interval > 0 and time.time() - last_ip_scan > ip_scan_interval) and not fulllocal :
            try:
                DomoticzEx.Log('Periodic Tuya IP scan, Please wait...')
                localtuya = tinytuya.deviceScan(verbose=False, maxretry=None, byID=True)
                last_ip_scan = time.time()
            except:
                pass

        # Main loop 
        
        for dev in devs:
            # Default values (offline-safe)
            t = 0
            StatusProperties   = properties.get(dev['id'], {}).get('status', [])
            FunctionProperties = properties.get(dev['id'], {}).get('functions', [])
            ResultValue        = result.get(dev['id'], [])
            product_id         = getConfigItem(dev['id'], 'product_id') or ''
            category           = properties.get(dev['id'], {}).get('category', 'unknown')
            dev_type           = DeviceType(category, product_id)
            dev_name           = dev.get('name', 'Unknown Device')
            dev_id             = dev.get('id', 'Unknown ID')
            online             = False  
            now = time.time()
            # LOCAL FIRST 
            try:
                if testdata:
                    DomoticzEx.Debug(f'Testdata mode: loading status for device {dev["name"]} id {dev["id"]}')
                    with open(Parameters['HomeFolder'] + '/debug_result.json') as rFile:
                        rData = json.load(rFile)
                        ResultValue = rData['result']
                        t = rData['t']
                    online = True
                elif local:
                    DomoticzEx.Debug(f'Attempting local connection to device {dev["name"]} id {dev["id"]}')
                    if dev_id in localtuya and localtuya[dev_id].get('ip', '') != '':
                        DomoticzEx.Debug(f'Local connection to device {dev["name"]} id {dev["id"]} using IP {localtuya[dev_id].get("ip", "unknown")} and version {localtuya[dev_id].get("version", "unknown")}')
                        d = tinytuya.Device(dev_id, localtuya[dev_id].get('ip'), dev['key'], version=localtuya.get(dev_id, {}).get('version', '3.3'))
                        d.socketRetryLimit = 1
                        d.socketRetryDelay = 1
                        d.detect_available_dps()
                        adps = d.detect_available_dps() # Two times for detection bulb devices
                        if adps:
                            status = d.status()
                            online = True

                            # ONLINE check
                            if (
                                not status
                                or 'Error' in status
                                or 'Err' in status
                                or 'dps' not in status
                            ):
                                online = False
                            else:
                                online = True
                            if 'dps' in status:
                                for dp_id, value in status['dps'].items():
                                    code = dps_map[dev_id]['by_id'].get(int(dp_id))

                                    if not code:
                                        if dp_id not in dps_map[dev_id]['by_id']:
                                            # DomoticzEx.Debug(f"[LOCAL] Ignoring unknown dp_id {dp_id}")
                                            dps_map[dev_id]['by_id'][int(dp_id)] = 'None'
                                            dps_map[dev_id]['by_code']['None'] = int(dp_id)
                                            continue

                                    if isinstance(ResultValue, str):
                                        try:
                                            ResultValue = json.loads(ResultValue)
                                        except json.JSONDecodeError:
                                            # DomoticzEx.Error("[LOCAL] ResultValue invalid JSON, resetting")
                                            ResultValue = []

                                    if not isinstance(ResultValue, list):
                                        # DomoticzEx.Error(f"[LOCAL] ResultValue unexpected type: {type(ResultValue)}")
                                        ResultValue = []

                                    # Search existing code
                                    item_found = False

                                    for item in ResultValue:
                                        if not isinstance(item, dict):
                                            continue

                                        if item.get('code') == code:
                                            item['value'] = value
                                            item_found = True
                                            break

                                    if not item_found:
                                        ResultValue.append({
                                            "code": code,
                                            "value": value
                                        })

                                    result[dev_id] = ResultValue
                                ResultValue = list(result.get(dev_id, []))

                        else:
                            DomoticzEx.Debug(f"[LOCAL] No DPS detected for device {dev['name']} id {dev}, skipping local status fetch")
                            online = False

                elif ((not local and not startup) or (not fulllocal)):
                    last_update = time.time()
                    DomoticzEx.Debug(f'Cloud connection to device {dev["name"]} id {dev["id"]} synctime {now - cloud_status_time.get(dev_id, 0)}')
                    try:
                        cloud = tuya.getstatus(dev_id)
                        ResultValue = cloud.get('result', [])
                        online = True
                        cloud_status_time[dev_id] = now
                    except:
                        online = False
                else:
                    DomoticzEx.Debug(f'Skipping status fetch for device {dev["name"]} id {dev["id"]} in full local mode')
                    online = False

                # DomoticzEx.Debug(f'Device {dev["name"]} is online = {online}')
                # DomoticzEx.Debug(f'Device {dev["name"]} id {dev["id"]} FunctionProperties={properties[dev["id"]]["functions"]}')
                # DomoticzEx.Debug(f'Device {dev["name"]} id {dev["id"]} StatusProperties={properties[dev["id"]]["status"]}')
                # DomoticzEx.Debug(f'Device {dev["name"]} id {dev["id"]} ResultValue={result[dev["id"]]}')
                # DomoticzEx.Debug(f'Device {dev["name"]} id {dev["id"]} DPSMap={dps_map[dev_id]}')
                
            except Exception as err:
                # Device unreachable fallback
                ResultValue = []       
                DomoticzEx.Error('Error line ' + format(sys.exc_info()[-1].tb_lineno))
                DomoticzEx.Debug('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

            # Create devices
            if startup:
                deviceinfo = localtuya.get(dev_id, {'ip': '127.0.0.1', 'version': 'unknown'})
                product_id = getConfigItem(dev_id, 'product_id') or ''
                if dev_type in ('light', 'fanlight', 'pirlight') and createDevice(dev_id, 1):
                    if (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (searchCode('temp_value', StatusProperties) or searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        DomoticzEx.Log('Create device Light RGBWW')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=4, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and 'dc' == str(properties[dev_id]['category']) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)):
                        DomoticzEx.Log('Create device Light Stringlight')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=4, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        DomoticzEx.Log('Create device Light RGBW')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=1, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        DomoticzEx.Log('Create device Light RGB')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=2, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (searchCode('temp_value', StatusProperties) or searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        DomoticzEx.Log('Create device Light WWCW')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=8, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        DomoticzEx.Log('Create device Light Dimmer')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (not searchCode('bright_value', StatusProperties) or not searchCode('bright_value_v2', StatusProperties)):
                        DomoticzEx.Log('Create device Light On/Off')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)):
                        DomoticzEx.Log('Create device Light On/Off (Unknown Light Device)')
                        DomoticzEx.Unit(Name=dev['name'] + ' (Unknown Light Device)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=7, Used=1).Create()
                    # elif not (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)):
                    #     deleteDevice(dev_id,1)

                if dev_type == 'dimmer':
                    if  createDevice(dev_id, 1) and searchCode('switch_led_1', FunctionProperties) and not searchCode('switch_led_2', FunctionProperties):
                        DomoticzEx.Log('Create device Dimmer')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                    # elif not createDevice(dev_id, 1) and not searchCode('switch_led_1', FunctionProperties) and not searchCode('switch_led_2', FunctionProperties):
                    #     deleteDevice(dev_id,1)
                    if searchCode('switch_led_2', FunctionProperties):
                        if createDevice(dev_id, 1):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Dimmer 1)', DeviceID=dev_id, Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                        # elif not createDevice(dev_id, 1) and not searchCode('switch_led_1', FunctionProperties):
                        #     deleteDevice(dev_id,1)
                        if createDevice(dev_id, 2):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Dimmer 2)', DeviceID=dev_id, Unit=2, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                        # elif not createDevice(dev_id, 2) and not searchCode('switch_led_2', FunctionProperties):
                        #     deleteDevice(dev_id,2)

                if dev_type in ('switch', 'switch/sensor'):
                    if  createDevice(dev_id, 1) and (searchCode('switch_1', FunctionProperties) or searchCode('switch', FunctionProperties)) and not searchCode('switch_2', FunctionProperties):
                        DomoticzEx.Log('Create device Switch')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if searchCode('switch_2', FunctionProperties):
                        DomoticzEx.Log('Create device Switch')
                        if createDevice(dev_id, 1):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Switch 1)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev_id, 2):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Switch 2)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('switch_3', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 3)', DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('switch_4', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 4)', DeviceID=dev_id, Unit=4, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('switch_5', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 5)', DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('switch_6', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 6)', DeviceID=dev_id, Unit=6, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 7) and searchCode('switch_7', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 7)', DeviceID=dev_id, Unit=7, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 8) and searchCode('switch_8', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 8)', DeviceID=dev_id, Unit=8, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 9) and searchCode('switch_9', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 9)', DeviceID=dev_id, Unit=9, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 11) and ((searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'A') or searchCode('phase_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (A)', DeviceID=dev_id, Unit=11, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev_id, 12) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (W)', DeviceID=dev_id, Unit=12, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 13) and (searchCode('cur_voltage', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (V)', DeviceID=dev_id, Unit=13, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev_id, 14) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev_id, Unit=14, Type=243, Subtype=29, Used=1).Create()
                        #UpdateDomoticz(dev_id, 14, '0;0', 0, 0, 1)
                    if createDevice(dev_id, 15) and (searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'mA' or searchCode('leakage_current', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;mA'
                        DomoticzEx.Unit(Name=dev['name'] + ' (mA)', DeviceID=dev_id, Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 16) and searchCode('temp_current', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=16, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 17) and (searchCode('out_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' outpower (W)', DeviceID=dev_id, Unit=17, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 18) and (searchCode('out_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' outpower (kWh)', DeviceID=dev_id, Unit=18, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 19) and (searchCode('power_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' Reverse A(kWh)', DeviceID=dev_id, Unit=19, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 20) and (searchCode('power_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' Forward A(kWh)', DeviceID=dev_id, Unit=20, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 21) and (searchCode('power_b', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' Reverse B(kWh)', DeviceID=dev_id, Unit=21, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 22) and (searchCode('power_b', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' Forward B(kWh)', DeviceID=dev_id, Unit=22, Type=243, Subtype=29, Used=1).Create()

                if dev_type == 'cover' and createDevice(dev_id, 1):
                    DomoticzEx.Log('Create device Cover')
                    if searchCode('position', StatusProperties) or searchCode('percent_control', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 1)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=21, Used=1).Create()
                    else:
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=14, Used=1).Create()
                    if searchCode('position_2', StatusProperties) or searchCode('percent_control_2', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch 2)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=21, Used=1).Create()

                if dev_type == 'smartheatpump':
                    if createDevice(dev_id, 1) and searchCode('switch', FunctionProperties):
                        DomoticzEx.Log('Create device Smartheatpump')
                        DomoticzEx.Unit(Name=dev['name'] + ' (On/Off)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('intemp', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (INtemp)', DeviceID=dev_id, Unit=2, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('outtemp', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (OUTtemp)', DeviceID=dev_id, Unit=3, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('whjtemp', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (AMBtemp)', DeviceID=dev_id, Unit=4, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('cmptemp', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (COMPRtemp)', DeviceID=dev_id, Unit=5, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('wttemp', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (DHWtemp)', DeviceID=dev_id, Unit=6, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 7) and searchCode('hqtemp', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (rGAStemp)', DeviceID=dev_id, Unit=7, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 8) and searchCode('cmp_act_frep', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hz'
                        DomoticzEx.Unit(Name=dev['name'] + ' (COMPfrq)', DeviceID=dev_id, Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 9) and searchCode('cmp_cur', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (COMPRcur)', DeviceID=dev_id, Unit=9, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev_id, 10) and searchCode('dc_fan_speed', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Speed'
                        DomoticzEx.Unit(Name=dev['name'] + ' (FANspeed)', DeviceID=dev_id, Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 11) and searchCode('ach_stemp', StatusProperties):
                        for item in StatusProperties:
                            temp = 'ach_stemp'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (HEATtemp)', DeviceID=dev_id, Unit=11, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 12) and searchCode('wth_stemp', StatusProperties):
                        for item in StatusProperties:
                            temp = 'wth_stemp'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (DHWtemp)', DeviceID=dev_id, Unit=12, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 13) and searchCode('aircond_temp_diff', StatusProperties):
                        for item in StatusProperties:
                            temp = 'aircond_temp_diff'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (HE/COtemp-diff)', DeviceID=dev_id, Unit=13, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 14) and searchCode('wth_temp_diff', StatusProperties):
                        for item in StatusProperties:
                            temp = 'wth_temp_diff'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (DHWtemp-diff)', DeviceID=dev_id, Unit=14, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 15) and searchCode('acc_stemp', StatusProperties):
                        for item in StatusProperties:
                            temp = 'acc_stemp'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (ACCtemp)', DeviceID=dev_id, Unit=15, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 16) and searchCode('mode', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev_id, Unit=16, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 17) and searchCode('work_mode', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'work_mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (WorkMode)', DeviceID=dev_id, Unit=17, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if not(createDevice(dev_id, 18)):
                    # if createDevice(dev_id, 18) and searchCode('temp_current', StatusProperties):
                        # DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=18, Type=80, Subtype=5, Used=1).Create()
                        Devices[dev_id].Unit['18'].delete()
                    if createDevice(dev_id, 19) and searchCode('temp_set', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'temp_set'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev_id, Unit=19, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if not(createDevice(dev_id, 20)):
                    # if createDevice(dev_id, 20) and searchCode('water_set', FunctionProperties):
                        # for item in FunctionProperties:
                        #     temp = 'water_set'
                        #     if item['code'] == temp:
                        #         the_values = json.loads(item['values'])
                        #         options = {}
                        #         options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                        #         options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                        #         options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                        #         options['ValueUnit'] = the_values['unit']
                        # DomoticzEx.Unit(Name=dev['name'] + ' (Water Thermostat)', DeviceID=dev_id, Unit=20, Type=242, Subtype=1, Options=options, Used=1).Create()
                        Devices[dev_id].Unit['20'].delete()
                    if createDevice(dev_id, 21) and searchCode('temp_top', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temp Top)', DeviceID=dev_id, Unit=21, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 22) and searchCode('temp_bottom', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temp Bottom)', DeviceID=dev_id, Unit=22, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 23) and searchCode('switch', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Defrost)', DeviceID=dev_id, Unit=23, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 24) and searchCode('water_flow', StatusProperties):
                        options = {}
                        options['Custom'] = '1;L/Min'
                        DomoticzEx.Unit(Name=dev['name'] + ' (L/Min)', DeviceID=dev_id, Unit=24, Type=243, Subtype=31, Options=options, Used=1).Create()

                if dev_type == 'thermostat' or dev_type == 'heater' or dev_type == 'heatpump':
                    temp = searchCode('temp_current', StatusProperties) or searchCode('upper_temp', StatusProperties) or searchCode('c_temperature', StatusProperties) or searchCode('TempCurrent', StatusProperties)
                    hum = searchCode('humidity_current', StatusProperties)
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Create device Thermostat/heater/heatpump')
                        if searchCode('switch', FunctionProperties) or searchCode('switch_1', FunctionProperties) or searchCode('Power', FunctionProperties) or searchCode('infared_switch', FunctionProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        else:
                            DomoticzEx.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=0).Create()
                    if createDevice(dev_id, 2) and temp:
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=2, Type=80, Subtype=5, Used=0 if hum else 1).Create()
                    if createDevice(dev_id, 3) and (searchCode('set_temp', FunctionProperties) or searchCode('temp_set', FunctionProperties) or searchCode('temperature_c', FunctionProperties) or searchCode('TempSet', FunctionProperties) or searchCode('target_temp', FunctionProperties)):
                        if searchCode('temp_set', FunctionProperties):
                            temp = 'temp_set'
                        elif searchCode('set_temp', FunctionProperties):
                            temp = 'set_temp'
                        elif searchCode('temperature_c', FunctionProperties):
                            temp = 'temperature_c'
                        elif searchCode('TempSet', FunctionProperties):
                            temp = 'TempSet'
                        elif searchCode('target_temp', FunctionProperties):
                            temp = 'target_temp'
                        for item in StatusProperties:
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev_id, Unit=3, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 4) and (searchCode('mode', StatusProperties) or searchCode('Mode', StatusProperties)) and product_id != 'al8g1qdamyu5cfcc':
                        if dev_type == 'thermostat':
                            image = 16
                        elif dev_type == 'heater':
                            image = 15
                        else:
                            image = 7
                        for item in StatusProperties:
                            if searchCode('Mode', StatusProperties):
                                mode = 'Mode'
                            else:
                                mode = 'mode'
                            if item['code'] == mode:
                                the_values = json.loads(item['values'])
                                mode_list = []
                                
                                # Bepaal de off/standby modus
                                if item['type'] == 'Bitmap':
                                    mode_list.extend(the_values['label'])
                                else:
                                    mode_list.extend(the_values['range'])
                                
                                # Prioriteitenlijst voor uit/standby modi (van hoog naar laag prioriteit)
                                standby_options = ['standby', 'off', 'none', 'close', 'stop', 'idle', 'sleep', 'auto_off']
                                
                                # Bepaal de beste uit/standby modus
                                standby_mode = 'off'  # Default fallback
                                for option in standby_options:
                                    if option in mode_list:
                                        standby_mode = option
                                        break
                                
                                # Maak de finale lijst met standby/uit modus als eerste
                                mode_final = [standby_mode]
                                
                                # Voeg de rest van de modi toe, maar filter 'standby' of 'off' uit als ze al aanwezig zijn
                                for mode_item in mode_list:
                                    if mode_item not in ['off', 'standby']:
                                        mode_final.append(mode_item)
                                
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode_final)
                                setConfigItem(str(dev_id) + '-4', {'mode': mode_final})
                                options['SelectorStyle'] = '0' if len(mode_final) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=image, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('window_check', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Window check)', DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('child_lock', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Child lock)', DeviceID=dev_id, Unit=6, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 7) and searchCode('eco', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Eco)', DeviceID=dev_id, Unit=7, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    # elif not createDevice(dev_id, 7) and not searchCode('Eco', FunctionProperties):
                    #     deleteDevice(dev_id,7)
                    if createDevice(dev_id, 8) and searchCode('temp_floor', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=8, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 9) and (searchCode('windspeed', StatusProperties) or searchCode('fan_level', StatusProperties) or searchCode('fan_speed_enum', StatusProperties)):
                        if searchCode('fan_level', StatusProperties):
                            wind = 'fan_level'
                        elif searchCode('fan_speed_enum', StatusProperties):
                            wind = 'fan_speed_enum'
                        else:
                            wind = 'windspeed'
                        for item in StatusProperties:
                            if item['code'] == wind:
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                DomoticzEx.Unit(Name=dev['name'] + ' (' + wind.capitalize().replace('_', ' ') +')', DeviceID=dev_id, Unit=9, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 10) and hum:
                        DomoticzEx.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev_id, Unit=10, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev_id, 11) and ((searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'A') or searchCode('phase_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (A)', DeviceID=dev_id, Unit=11, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev_id, 12) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties) or searchCode('average_power', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (W)', DeviceID=dev_id, Unit=12, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 13) and (searchCode('cur_voltage', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (V)', DeviceID=dev_id, Unit=13, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev_id, 14) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties) or searchCode('average_power', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev_id, Unit=14, Type=243, Subtype=29, Used=1).Create()
                        #UpdateDomoticz(dev_id, 14, '0;0', 0, 0, 1)
                    if createDevice(dev_id, 15) and (searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'mA' or searchCode('leakage_current', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;mA'
                        DomoticzEx.Unit(Name=dev['name'] + ' (mA)', DeviceID=dev_id, Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 16) and temp and hum:
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev_id, Unit=16, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 17) and searchCode('anti_bother', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Anti bother)', DeviceID=dev_id, Unit=17, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 18) and searchCode('fault', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=18, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type in ('sensor', 'smartir'):
                    temp = searchCode('va_temperature', StatusProperties) or searchCode('temp_current', StatusProperties) or searchCode('local_temp', StatusProperties) or searchCode('Tin', StatusProperties)
                    hum = searchCode('va_humidity', StatusProperties) or searchCode('humidity_value', StatusProperties) or searchCode('local_hum', StatusProperties) or searchCode('humidity', StatusProperties) or searchCode('Hin', StatusProperties)
                    if createDevice(dev_id, 1) and temp:
                        DomoticzEx.Log('Create Sensor device')
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=1, Type=80, Subtype=5, Used=0 if hum else 1).Create()
                    if createDevice(dev_id, 2) and hum:
                        DomoticzEx.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev_id, Unit=2, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev_id, 3) and temp and hum:
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev_id, Unit=3, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('co2_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;ppm'
                        DomoticzEx.Unit(Name=dev['name'] + ' (CO2)', DeviceID=dev_id, Unit=4, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('air_quality_index', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Index)', DeviceID=dev_id, Unit=5, Type=243, Subtype=22, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('ch2o_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mg/m3'
                        DomoticzEx.Unit(Name=dev['name'] + ' (CH2O)', DeviceID=dev_id, Unit=6, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 7) and searchCode('voc_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mg/m3'
                        DomoticzEx.Unit(Name=dev['name'] + ' (VOC)', DeviceID=dev_id, Unit=7, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 8) and searchCode('pm25_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;µg/m3'
                        DomoticzEx.Unit(Name=dev['name'] + ' (PM2.5)', DeviceID=dev_id, Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 9) and searchCode('pm10', StatusProperties):
                        options = {}
                        options['Custom'] = '1;µg/m3'
                        DomoticzEx.Unit(Name=dev['name'] + ' (PM10)', DeviceID=dev_id, Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 10) and searchCode('bright_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;lux'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Lux)', DeviceID=dev_id, Unit=10, Type=243, Subtype=31, Options=options, Image=19, Used=1).Create()
                    if createDevice(dev_id, 11) and searchCode('switch', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Switch)', DeviceID=dev_id, Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 12) and searchCode('ph_current', StatusProperties):
                        options = {}
                        options['Custom'] = '1;pH'
                        DomoticzEx.Unit(Name=dev['name'] + ' (pH)', DeviceID=dev_id, Unit=12, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 13) and searchCode('pro_current', StatusProperties):
                        options = {}
                        options['Custom'] = '1;kPa'
                        DomoticzEx.Unit(Name=dev['name'] + ' (kPa)', DeviceID=dev_id, Unit=13, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 14) and searchCode('orp_current', StatusProperties):
                        options = {}
                        options['Custom'] = '1;ORP'
                        DomoticzEx.Unit(Name=dev['name'] + ' (ORP)', DeviceID=dev_id, Unit=14, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 15) and searchCode('ph_warn_min', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'ph_warn_min'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Min pH)', DeviceID=dev_id, Unit=15, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 16) and searchCode('ph_warn_max', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'ph_warn_max'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Max pH)', DeviceID=dev_id, Unit=16, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 17) and searchCode('pro_warn_min', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'pro_warn_min'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Min kPa)', DeviceID=dev_id, Unit=17, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 18) and searchCode('pro_warn_max', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'pro_warn_max'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Max kPa)', DeviceID=dev_id, Unit=18, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 19) and searchCode('orp_warn_min', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'orp_warn_min'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Min ORP)', DeviceID=dev_id, Unit=19, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 20) and searchCode('orp_warn_max', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'orp_warn_max'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Max ORP)', DeviceID=dev_id, Unit=20, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 21) and (searchCode('sub1_temp', StatusProperties) or searchCode('ToutCh1', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext1 (Temperature)', DeviceID=dev_id, Unit=21, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev_id, 22) and (searchCode('sub1_hum', StatusProperties) or searchCode('HoutCh1', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext1 (Humidity)', DeviceID=dev_id, Unit=22, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev_id, 23) and ((searchCode('sub1_temp', StatusProperties) and searchCode('sub1_hum', StatusProperties)) or (searchCode('ToutCh1', StatusProperties) and searchCode('HoutCh1', StatusProperties))):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext1 (Temperature + Humidity)', DeviceID=dev_id, Unit=23, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 24) and searchCode('temp_warn_min', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'temp_warn_min'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Min Temp)', DeviceID=dev_id, Unit=24, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 25) and searchCode('temp_warn_max', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'temp_warn_max'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Max Temp)', DeviceID=dev_id, Unit=25, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 31) and (searchCode('sub2_temp', StatusProperties) or searchCode('ToutCh2', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext2 (Temperature)', DeviceID=dev_id, Unit=31, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev_id, 32) and (searchCode('sub2_hum', StatusProperties) or searchCode('HoutCh2', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext2 (Humidity)', DeviceID=dev_id, Unit=32, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev_id, 33) and ((searchCode('sub2_temp', StatusProperties) and searchCode('sub2_hum', StatusProperties)) or (searchCode('ToutCh2', StatusProperties) and searchCode('HoutCh2', StatusProperties))):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext2 (Temperature + Humidity)', DeviceID=dev_id, Unit=33, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 41) and (searchCode('sub3_temp', StatusProperties) or searchCode('ToutCh3', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext3 (Temperature)', DeviceID=dev_id, Unit=41, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev_id, 42) and (searchCode('sub3_hum', StatusProperties) or searchCode('HoutCh3', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext3 (Humidity)', DeviceID=dev_id, Unit=42, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev_id, 43) and ((searchCode('sub3_temp', StatusProperties) and searchCode('sub3_hum', StatusProperties)) or (searchCode('ToutCh3', StatusProperties) and searchCode('HoutCh3', StatusProperties))):
                        DomoticzEx.Unit(Name=dev['name'] + '_ext3 (Temperature + Humidity)', DeviceID=dev_id, Unit=43, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 44) and searchCode('temp_current_2', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature 2)', DeviceID=dev_id, Unit=44, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 45) and searchCode('cook_temperature', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'cook_temperature'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Cook temperature)', DeviceID=dev_id, Unit=45, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 46) and searchCode('cook_temperature_2', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'cook_temperature_2'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Cook temperature 2)', DeviceID=dev_id, Unit=46, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 47) and searchCode('atmosphere', StatusProperties):
                        options = {}
                        options['Custom'] = '1;inHg'
                        DomoticzEx.Unit(Name=dev['name'] + ' (inHg)', DeviceID=dev_id, Unit=47, Type=243, Subtype=31, Options=options, Image=19, Used=1).Create()
                    if createDevice(dev_id, 48) and (searchCode('pir', StatusProperties) or searchCode('pir_state', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Pir)', DeviceID=dev_id, Unit=48, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 49) and searchCode('temper_alarm', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temper alarm)', DeviceID=dev_id, Unit=49, Type=244, Subtype=73, Switchtype=0, Image=13, Used=1).Create()
                    if createDevice(dev_id, 50) and searchCode('co_status', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'co_status':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (CO status)', DeviceID=dev_id, Unit=50, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev_id, 51) and searchCode('checking_result', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'checking_result':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Checking result)', DeviceID=dev_id, Unit=51, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    # Create devices for channels 1-7
                    for channel in range(1, 8):
                        temp = searchCode(f'ch{channel}_temp', ResultValue)
                        hum = searchCode(f'ch{channel}_humi', ResultValue)
                        unit_base = 50 + (channel * 3)  # Unit 51, 54, 57, 60, 63, 66, 69
                        
                        # Get current values to check if they're valid
                        current_temp = StatusDeviceTuya(f'ch{channel}_temp') if temp else None
                        current_hum = StatusDeviceTuya(f'ch{channel}_humi') if hum else None
                        
                        # Check if temperature is valid (not -40)
                        temp_valid = temp and current_temp is not None and current_temp != -40
                        # Check if humidity is valid (not 0)
                        hum_valid = hum and current_hum is not None and current_hum != 0
                        
                        if createDevice(dev_id, unit_base - 2) and temp_valid:
                            DomoticzEx.Log(f'Create Temperature Sensor device for channel {channel}')
                            DomoticzEx.Unit(Name=dev['name'] + f' (CH{channel} Temperature)', DeviceID=dev_id, Unit=unit_base - 2, Type=80, Subtype=5, Used=0 if hum_valid else 1).Create()
                        
                        if createDevice(dev_id, unit_base - 1) and hum_valid:
                            DomoticzEx.Log(f'Create Humidity Sensor device for channel {channel}')
                            DomoticzEx.Unit(Name=dev['name'] + f' (CH{channel} Humidity)', DeviceID=dev_id, Unit=unit_base - 1, Type=81, Subtype=1, Used=0).Create()
                        
                        if createDevice(dev_id, unit_base) and temp_valid and hum_valid:
                            DomoticzEx.Log(f'Create Combined Sensor device for channel {channel}')
                            DomoticzEx.Unit(Name=dev['name'] + f' (CH{channel} Temperature + Humidity)', DeviceID=dev_id, Unit=unit_base, Type=82, Subtype=5, Used=1).Create()
                    # if createDevice(dev_id, 47) and searchCode('alarm_switch', FunctionProperties):
                    #     DomoticzEx.Unit(Name=dev['name'] + ' (Alarm)', DeviceID=dev_id, Unit=47, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()

                    if dev_type in ('smartir') and dev_id not in str(Devices):
                        DomoticzEx.Log('Infrared device: ' + str(dev['name']))
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=0).Create()
                        UpdateDomoticz(dev_id, 1, 'Infrared devices are not yet able to be controlled by the plugin.', 0, 0)

                if dev_type == 'doorbell':
                    if createDevice(dev_id, 1) and searchCode('doorbell_active', StatusProperties):
                        DomoticzEx.Log('Create device Doorbell')
                        #DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=1).Create()
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create() # Switchtype=1 is doorbell
                    if createDevice(dev_id, 2) and searchCode('floodlight_switch', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Light switch)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and (searchCode('motion_switch', StatusProperties) or searchCode('movement_detect_pic', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Motion switch)', DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('basic_indicator', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Indicator)', DeviceID=dev_id, Unit=4, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()

                if dev_type == 'fan':
                    if createDevice(dev_id, 1) and searchCode('switch', FunctionProperties):
                        DomoticzEx.Log('Create device Fan')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('mode', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('fan_speed', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'fan_speed':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values['min'],the_values['max'] + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fan Speed)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('temp_set', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'temp_set'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev_id, Unit=4, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('temp_current', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=5, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('fault', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=6, Type=243, Subtype=19, Image=13, Used=1).Create()
                    if createDevice(dev_id, 7) and searchCode('light', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Light)', DeviceID=dev_id, Unit=7, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev_id, 8) and searchCode('switch', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (RH Switch)', DeviceID=dev_id, Unit=8, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev_id, 9) and (searchCode('RH_threshold', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;RH'
                        DomoticzEx.Unit(Name=dev['name'] + ' (RH Threshold)', DeviceID=dev_id, Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 10) and (searchCode('RH_value', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;RH'
                        DomoticzEx.Unit(Name=dev['name'] + ' (RH Value)', DeviceID=dev_id, Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 11) and searchCode('anion', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Anion)', DeviceID=dev_id, Unit=11, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev_id, 12) and searchCode('anion', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Free Cooling)', DeviceID=dev_id, Unit=12, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev_id, 13) and searchCode('anion', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Powerful)', DeviceID=dev_id, Unit=13, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()

                if dev_type == 'fanlight':
                    if createDevice(dev_id, 2) and searchCode('fan_switch', FunctionProperties):
                        DomoticzEx.Log('Create device Fanlight')
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fan Power)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('fan_speed', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'fan_speed':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values['min'],the_values['max'] + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fan Speed)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('fan_direction', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'fan_direction':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fan Direction)', DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()

                if dev_type == 'siren':
                    if createDevice(dev_id, 1) and searchCode('AlarmSwitch', FunctionProperties):
                        DomoticzEx.Log('Create device Siren')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=13, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('Alarmtype', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'Alarmtype':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Alarmtype)', DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=8, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('AlarmPeriod', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'AlarmPeriod':
                                the_values = json.loads(item['values'])
                                mode = []
                                for num in range(the_values['min'],the_values['max'] + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'false'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (AlarmPeriod)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    # Other type of alarm with same code
                    if createDevice(dev_id, 1) and searchCode('muffling', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Muffling)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=8, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('alarm_state', FunctionProperties):
                        DomoticzEx.Log('Create device Siren')
                        for item in FunctionProperties:
                            if item['code'] == 'alarm_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (State)', DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('alarm_volume', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'alarm_volume':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Volume)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=8, Used=1).Create()

                if dev_type == 'powermeter' and searchCode('Current', StatusProperties):
                    if createDevice(dev_id, 1) :
                        DomoticzEx.Log('Create Powermeter')
                        DomoticzEx.Unit(Name=dev['name'] + ' (3P A)', DeviceID=dev_id, Unit=1, Type=89, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('Current', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hz'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Hz)', DeviceID=dev_id, Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('Temperature', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=3, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('Current', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (A)', DeviceID=dev_id, Unit=4, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('ActivePower', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev_id, Unit=5, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 11) and searchCode('ActivePowerA', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' L1 (V)', DeviceID=dev_id, Unit=11, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev_id, 12) and searchCode('ActivePowerA', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' L1 (kWh)', DeviceID=dev_id, Unit=12, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 21) and searchCode('ActivePowerB', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' L2 (V)', DeviceID=dev_id, Unit=21, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev_id, 22) and searchCode('ActivePowerB', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' L2 (kWh)', DeviceID=dev_id, Unit=22, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 31) and searchCode('ActivePowerC', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' L3 (V)', DeviceID=dev_id, Unit=31, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev_id, 32) and searchCode('ActivePowerC', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' L3 (kWh)', DeviceID=dev_id, Unit=32, Type=243, Subtype=29, Used=1).Create()

                if dev_type == 'powermeter' and searchCode('phase_a', StatusProperties):
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Create Powermeter')
                        DomoticzEx.Unit(Name=dev['name'] + ' (A)', DeviceID=dev_id, Unit=1, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('phase_a', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (W)', DeviceID=dev_id, Unit=2, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('phase_a', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (V)', DeviceID=dev_id, Unit=3, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('phase_a', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev_id, Unit=4, Type=243, Subtype=29, Used=1).Create()
                    if  createDevice(dev_id, 5) and searchCode('switch', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('fault', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=6, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'powermeter' and (searchCode('direction_a', StatusProperties) or searchCode('power_direction_a', StatusProperties)):
                    if createDevice(dev_id, 1) and (searchCode('voltage_a', StatusProperties) or searchCode('f_ac_v', StatusProperties)):
                        DomoticzEx.Log('Create Powermeter')
                        DomoticzEx.Unit(Name=dev['name'] + ' (V)', DeviceID=dev_id, Unit=1, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev_id, 2) and (searchCode('freq', StatusProperties) or searchCode('f_ac_line_freq', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;Hz'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Hz)', DeviceID=dev_id, Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('total_power', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' Total (W)', DeviceID=dev_id, Unit=3, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 11) and searchCode('power_a', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' A (W)', DeviceID=dev_id, Unit=11, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 12) and searchCode('current_a', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mA'
                        DomoticzEx.Unit(Name=dev['name'] + ' A (mA)', DeviceID=dev_id, Unit=12, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 13) and searchCode('direction_a', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name']+ ' A (Direction)', DeviceID=dev_id, Unit=13, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev_id, 14) and (searchCode('energy_forword_a', StatusProperties) or searchCode('forward_energy_a', StatusProperties)):
                        # DomoticzEx.Unit(Name=dev['name'] + ' A Forward (kWh)', DeviceID=dev_id, Unit=14, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        DomoticzEx.Unit(Name=dev['name'] + ' A Forward (kWh)', DeviceID=dev_id, Unit=14, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 15) and (searchCode('energy_reverse_a', StatusProperties) or searchCode('reverse_energy_a', StatusProperties)):
                        # DomoticzEx.Unit(Name=dev['name'] + ' A Reverse (kWh)', DeviceID=dev_id, Unit=15, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        DomoticzEx.Unit(Name=dev['name'] + ' A Reverse (kWh)', DeviceID=dev_id, Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 21) and searchCode('power_b', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' B (W)', DeviceID=dev_id, Unit=21, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 22) and searchCode('current_b', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mA'
                        DomoticzEx.Unit(Name=dev['name'] + ' B (mA)', DeviceID=dev_id, Unit=22, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 23) and searchCode('direction_b', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name']+ ' B (Direction)', DeviceID=dev_id, Unit=23, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev_id, 24) and (searchCode('energy_forword_b', StatusProperties) or searchCode('forward_energy_b', StatusProperties)):
                        # DomoticzEx.Unit(Name=dev['name'] + ' B Forward (kWh)', DeviceID=dev_id, Unit=24, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        DomoticzEx.Unit(Name=dev['name'] + ' B Forward (kWh)', DeviceID=dev_id, Unit=24, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 25) and (searchCode('energy_reverse_b', StatusProperties) or searchCode('reverse_energy_b', StatusProperties)):
                        # DomoticzEx.Unit(Name=dev['name'] + ' B Reverse (kWh)', DeviceID=dev_id, Unit=25, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        DomoticzEx.Unit(Name=dev['name'] + ' B Reverse (kWh)', DeviceID=dev_id, Unit=25, Type=243, Subtype=31, Options=options, Used=1).Create()

                if dev_type == 'powermeter' and (searchCode('switch_1', StatusProperties) or searchCode('switch', StatusProperties)) and not searchCode('phase_a', StatusProperties):
                    if  createDevice(dev_id, 1) and (searchCode('switch_1', StatusProperties) or searchCode('switch', StatusProperties)):
                        DomoticzEx.Log('Create Powermeter')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('cur_current', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mA'
                        DomoticzEx.Unit(Name=dev['name'] + ' (mA)', DeviceID=dev_id, Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('cur_power', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev_id, Unit=3, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('cur_voltage', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (V)', DeviceID=dev_id, Unit=4, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('fault', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'gateway':
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Create device Gateway')
                        if searchCode('master_state', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=1).Create()
                        else:
                            DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=0).Create()

                if dev_type == 'doorcontact':
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Create device Doorcontact')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                if dev_type == 'pirlight':
                    if createDevice(dev_id, 2) and searchCode('switch_pir', FunctionProperties):
                        DomoticzEx.Log('Create device Pirlight')
                        DomoticzEx.Unit(Name=dev['name'] + ' (Pir State)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=8, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('device_mode', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'device_mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('pir_sensitivity', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'pir_sensitivity':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Sensitivity)', DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'smokedetector':
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Create device Smokedetector')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=5, Used=1).Create()
                        DomoticzEx.Unit(Name=dev['name'] + ' (Alarm)', DeviceID=dev_id, Unit=2, Type=243, Subtype=19, Used=1).Create()

                if dev_type == 'garagedooropener':
                    if createDevice(dev_id, 1) and searchCode('switch_1', FunctionProperties):
                        DomoticzEx.Log('Create device Garage door opener')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=5, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('doorcontact_state', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Contact state)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('door_control_1', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (State)', DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                if dev_type == 'feeder':
                    if createDevice(dev_id, 1) and searchCode('manual_feed', FunctionProperties):
                        DomoticzEx.Log('Create device Feeder')
                        for item in FunctionProperties:
                            if item['code'] == 'manual_feed':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values['min'],the_values['max'] + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Manual)', DeviceID=dev_id, Unit=1, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('feed_state', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'feed_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('feed_report', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'feed_report':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values['min'],the_values['max'] + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Report)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('light', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Light)', DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Used=1).Create()

                if dev_type == 'waterleak':
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Create device water leak sesor')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=22, Switchtype=0, Image=11, Used=1).Create()

                if dev_type == 'presence':
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Create device PIR sensor')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Used=1).Create()

                if dev_type == 'irrigation':
                    if createDevice(dev_id, 1) and (searchCode('switch', FunctionProperties) or searchCode('switch_1', FunctionProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('work_state', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'work_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=22, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('areaone', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Area One)', DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('areatwo', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Area Two)', DeviceID=dev_id, Unit=4, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('areathree', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Area Three)', DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('areafour', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Area Four)', DeviceID=dev_id, Unit=6, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev_id, 7) and searchCode('areafive', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Area Five)', DeviceID=dev_id, Unit=7, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev_id, 8) and searchCode('areasix', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Area Six)', DeviceID=dev_id, Unit=8, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()

                if dev_type == 'wswitch':
                    # if createDevice(dev_id, 1) and searchCode('switch1_value', StatusProperties):
                    #     DomoticzEx.Unit(Name=dev['name'] + ' single click (Switch 1)', DeviceID=dev_id, Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    #     DomoticzEx.Unit(Name=dev['name'] + ' double click (Switch 1)', DeviceID=dev_id, Unit=12, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    #     DomoticzEx.Unit(Name=dev['name'] + ' long press (Switch 1)', DeviceID=dev_id, Unit=13, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    for x in range(1, 10):
                        if createDevice(dev_id, x) and searchCode('switch' + str(x) + '_value', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'switch' + str(x) + '_value':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=dev['name'] + ' (Switch ' + str(x) + ')', DeviceID=dev_id, Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, x) and searchCode('switch_type_' + str(x), StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'switch_type_' + str(x):
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=dev['name'] + ' (Switch ' + str(x) + ')', DeviceID=dev_id, Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev_id, x) and searchCode('switch_mode' + str(x), StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'switch_mode' + str(x):
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            DomoticzEx.Unit(Name=dev['name'] + ' (Switch ' + str(x) + ')', DeviceID=dev_id, Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'starlight':
                    if createDevice(dev_id, 1) and searchCode('switch_led', FunctionProperties):
                        DomoticzEx.Log('Create device Starlight')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=2, Switchtype=7, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('colour_switch', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Colour)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('laser_switch', FunctionProperties) and searchCode('laser_bright', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Laser)', DeviceID=dev_id, Unit=3, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('fan_switch', FunctionProperties) and searchCode('fan_speed', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fan)', DeviceID=dev_id, Unit=4, Type=241, Subtype=3, Switchtype=7, Image=7, Used=1).Create()

                if dev_type == 'smartlock':
                    if createDevice(dev_id, 1) and (searchCode('lock_motor_state', StatusProperties) or searchCode('rtc_lock', StatusProperties)):
                        DomoticzEx.Log('Create device smart lock')
                        DomoticzEx.Unit(Name=dev['name'] + ' (State)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    # if createDevice(dev_id, 3):
                    #     DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=19, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('alarm_lock', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'alarm_lock':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('unlock_ble', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (unlock ble)', DeviceID=dev_id, Unit=3, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('unlock_card', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (unlock card)', DeviceID=dev_id, Unit=4, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                if dev_type == 'dehumidifier':
                    if createDevice(dev_id, 1) and searchCode('switch', FunctionProperties):
                        DomoticzEx.Log('Create device Dehumidifier')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and (searchCode('dehumidify_set_value', FunctionProperties) or searchCode('dehumidify_set_enum', FunctionProperties)):
                        if searchCode('dehumidify_set_value', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'dehumidify_set_value':
                                    the_values = json.loads(item['values'])
                                    options = {'ValueStep':the_values['step'], 'ValueMin':the_values['min'], 'ValueMax':the_values['max'], 'ValueUnit':'%'}
                            DomoticzEx.Unit(Name=dev['name'] + ' (dehumidify)', DeviceID=dev_id, Unit=2, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                        elif searchCode('dehumidify_set_enum', FunctionProperties):
                            for item in FunctionProperties:
                                if item['code'] == 'dehumidify_set_enum':
                                    the_values = json.loads(item['values'])
                                    options = {'ValueStep':the_values['step'], 'ValueMin':the_values['min'], 'ValueMax':the_values['max'], 'ValueUnit':'%'}
                            DomoticzEx.Unit(Name=dev['name'] + ' (dehumidify)', DeviceID=dev_id, Unit=2, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('fan_speed_enum', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'fan_speed_enum':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (fan speed)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                DomoticzEx.Unit(Name=dev['name'] + ' (Fan)', DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('fault', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()
                    if createDevice(dev_id, 6) and (searchCode('temp_indoor', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=6, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev_id, 7) and (searchCode('humidity_indoor', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev_id, Unit=7, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev_id, 8) and ((searchCode('temp_indoor', StatusProperties) and searchCode('humidity_indoor', StatusProperties))):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev_id, Unit=8, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 9) and searchCode('child_lock', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Child lock)', DeviceID=dev_id, Unit=9, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 10) and searchCode('switch', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name']+ ' (Anion)', DeviceID=dev_id, Unit=10, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 11) and searchCode('filter_reset', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name']+ ' (Filter reset)', DeviceID=dev_id, Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 12) and searchCode('filter_life', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name']+ ' (Filter life)', DeviceID=dev_id, Unit=12, Type=243, Subtype=6, Used=1).Create()
                    if createDevice(dev_id, 13) and searchCode('runtime_total_reset', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name']+ ' (Runtime total Reset)', DeviceID=dev_id, Unit=13, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 14) and searchCode('type_of_equipment', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hour'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Runtime)', DeviceID=dev_id, Unit=14, Type=243, Subtype=31, Options=options, Used=1).Create()

                if dev_type == 'infrared_ac':
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Create device Infrared AC')
                        DomoticzEx.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('temp', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev_id, Unit=2, Type=242, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values['min'],the_values['max'] + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                DomoticzEx.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('wind', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'wind':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values['min'],the_values['max'] + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                DomoticzEx.Unit(Name=dev['name'] + ' (Fan)', DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('anion', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (anion)', DeviceID=dev_id, Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 6) and (searchCode('temp_indoor', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=6, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev_id, 7) and (searchCode('humidity_indoor', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev_id, Unit=7, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev_id, 8) and ((searchCode('temp_indoor', StatusProperties) and searchCode('humidity_indoor', StatusProperties))):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev_id, Unit=8, Type=82, Subtype=5, Used=1).Create()

                if dev_type == 'vacuum':
                    if createDevice(dev_id, 1) and searchCode('power_go', FunctionProperties):
                        DomoticzEx.Log('Create device Robot vacuum')
                        DomoticzEx.Unit(Name=dev['name'] + ' Running', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('switch_charge', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Charge)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('mode', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create() #Image=7,
                    if createDevice(dev_id, 4) and searchCode('suction', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'suction':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Suction)', DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('cistern', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'cistern':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Cistern)', DeviceID=dev_id, Unit=5, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('status', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev_id, Unit=6, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev_id, 7) and searchCode('electricity_left', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Electricity left)', DeviceID=dev_id, Unit=7, Type=243, Subtype=6, Used=1).Create()
                    if createDevice(dev_id, 8) and searchCode('edge_brush', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hour'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Edge brush))', DeviceID=dev_id, Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 9) and searchCode('roll_brush', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hour'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Roll brush))', DeviceID=dev_id, Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 10) and searchCode('filter', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hour'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Filter))', DeviceID=dev_id, Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 11) and searchCode('fault', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=11, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'multifunctionalarm':
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Multifunction alarm: ' + str(dev['name']))
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=0).Create()
                        UpdateDomoticz(dev_id, 1, 'update wait', 0, 0)

                if dev_type == 'purifier':
                    if createDevice(dev_id, 1) and searchCode('switch', FunctionProperties):
                        DomoticzEx.Log('Create purifier device')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('pm25', StatusProperties):
                        options = {}
                        options['Custom'] = '1;µg/m3'
                        DomoticzEx.Unit(Name=dev['name'] + ' (PM2.5)', DeviceID=dev_id, Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (mode)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('speed', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'speed':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (speed)', DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('filter', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Filter)', DeviceID=dev_id, Unit=5, Type=243, Subtype=6, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('air_quality', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Index)', DeviceID=dev_id, Unit=6, Type=243, Subtype=19, Used=1).Create()

                if dev_type == 'smartkettle':
                    if createDevice(dev_id, 1) and searchCode('start', StatusProperties):
                        DomoticzEx.Log('Create device Smart Kettle')
                        DomoticzEx.Unit(Name=dev['name'] + ' (Start)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('status', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'status':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = 0
                        DomoticzEx.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev_id, 3) and (searchCode('temperature', StatusProperties)):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=3, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev_id, 4) and (searchCode('cook_temperature', StatusProperties)):
                        # options={'ValueStep':'0.5', ' ValueMin':'-200', 'ValueMax':'200', 'ValueUnit':'°C'}
                        for item in StatusProperties:
                            temp = 'cook_temperature'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Cook Temperature)', DeviceID=dev_id, Unit=4, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('fault', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'mower':
                    if createDevice(dev_id, 1) and searchCode('MachineControlCmd', FunctionProperties):
                        DomoticzEx.Log('Create device Smart Mower')
                        for item in FunctionProperties:
                            if item['code'] == 'MachineControlCmd':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Control)', DeviceID=dev_id, Unit=1, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('MachineRainMode', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Rain Mode)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('MachineStatus', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev_id, Unit=3, Type=243, Subtype=19, Image=13, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('MachineWarning', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Warnig)', DeviceID=dev_id, Unit=4, Type=243, Subtype=19, Image=13, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('MachineError', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Error)', DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('MachineWorkMode', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'MachineWorkMode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (WorkMode)', DeviceID=dev_id, Unit=6, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()

                if dev_type == 'human_presence':
                    if createDevice(dev_id, 1) and searchCode('presence_state', StatusProperties):
                        DomoticzEx.Log('Create device Human presence sensor')
                        DomoticzEx.Unit(Name=dev['name'] + ' (Presence)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('sensitivity', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'sensitivity':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values['min'],the_values['max'] + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Sensitivity)', DeviceID=dev_id, Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and (searchCode('near_detection', StatusProperties)):
                        for item in StatusProperties:
                            temp = 'near_detection'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Near detection)', DeviceID=dev_id, Unit=3, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 4) and (searchCode('far_detection', StatusProperties)):
                        for item in StatusProperties:
                            temp = 'far_detection'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Far detection)', DeviceID=dev_id, Unit=4, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('checking_result', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Result)', DeviceID=dev_id, Unit=5, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev_id, 6) and (searchCode('target_dis_closest', StatusProperties)):
                        for item in StatusProperties:
                            temp = 'target_dis_closest'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values['step'])
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values['min'])
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values['max'])
                                options['ValueUnit'] = the_values['unit']
                        DomoticzEx.Unit(Name=dev['name'] + ' (Target)', DeviceID=dev_id, Unit=6, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 10) and searchCode('presence_state', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'presence_state':
                                the_values = json.loads(item['values'])
                                mode = []
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'false'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Presence state)', DeviceID=dev_id, Unit=10, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'evcharger':
                    if createDevice(dev_id, 1) and searchCode('switch', StatusProperties):
                        DomoticzEx.Log('Create EVcharger')
                        DomoticzEx.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('work_state', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Work state)', DeviceID=dev_id, Unit=2, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('temp_current', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev_id, Unit=3, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('power_total', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (W)', DeviceID=dev_id, Unit=4, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev_id, 5) and searchCode('charge_cur_set', StatusProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (A)', DeviceID=dev_id, Unit=5, Type=243, Subtype=23, Used=1).Create()
                    # if createDevice(dev_id, 6) and searchCode('forward_energy_total', StatusProperties) :
                    #     DomoticzEx.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev_id, Unit=6, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev_id, 6) and searchCode('forward_energy_total', StatusProperties) :
                        options = {}
                        options['Custom'] = '1;kWh'
                        DomoticzEx.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev_id, Unit=6, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev_id, 7) and searchCode('online_state', StatusProperties):
                            DomoticzEx.Unit(Name=dev['name'] + ' (Online state)', DeviceID=dev_id, Unit=7, Type=243, Subtype=19, Used=1).Create()
                    # if createDevice(dev_id, 8) and searchCode('fault', StatusProperties):
                    #         DomoticzEx.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev_id, Unit=8, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type in ('light'):
                    if createDevice(dev_id, 1) and searchCode('Light', FunctionProperties) and searchCode('work_mode', FunctionProperties) and (searchCode('colour_data', FunctionProperties) or searchCode('colour_data_v2', FunctionProperties)):
                        DomoticzEx.Log('Create device Light RGBW')
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=241, Subtype=1, Switchtype=7, Used=1).Create()
                    if createDevice(dev_id, 2) and searchCode('Power', FunctionProperties):
                        DomoticzEx.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev_id, Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev_id, 3) and searchCode('lightmode', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'lightmode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Lightmode)', DeviceID=dev_id, Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev_id, 4) and searchCode('dp_mist_grade', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'dp_mist_grade':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                else:
                                    mode.extend(the_values['range'])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        DomoticzEx.Unit(Name=dev['name'] + ' (Mist grade)', DeviceID=dev_id, Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'infrared':
                    if createDevice(dev_id, 1):
                        DomoticzEx.Log('Infrared device: ' + str(dev['name']))
                        DomoticzEx.Unit(Name=dev['name'], DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=0).Create()
                        UpdateDomoticz(dev_id, 1, 'Infrared devices are not yet able to be controlled by the plugin.', 0, 0)

                if createDevice(dev_id, 1) and dev_id not in str(Devices):
                    DomoticzEx.Log('No controls found for device: ' + str(dev['name']))
                    DomoticzEx.Unit(Name=dev['name'] + ' (Unknown Device)', DeviceID=dev_id, Unit=1, Type=243, Subtype=19, Used=1).Create()
                    UpdateDomoticz(dev_id, 1, 'This device is not recognized. Please run the debug_discovery with Python from the tools directory and create an issue report at https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/issues so that the device can be added.', 0, 0)

                setConfigItem(
                    dev_id,
                    {
                        'key': dev['key'],
                        'category': dev_type,
                        'mac': dev.get('mac', '00:00:00:00:00:00'),
                        'ip': deviceinfo.get('ip', '127.0.0.1'),
                        'product_id': dev['product_id'],
                        'version': deviceinfo.get('version', '3.3')
                    }
                )

            battery = is_battery_device(StatusProperties)

            if not battery:
                if online and Devices[dev_id].TimedOut == 1:
                    UpdateDomoticz(dev_id, 1, None, 0, 0)
                elif not online and Devices[dev_id].TimedOut == 0:
                    UpdateDomoticz(dev_id, 1, False, 0, 1)
            else:
                # Battery devices never timeout
                if Devices[dev_id].TimedOut == 1:
                    UpdateDomoticz(dev_id, 1, None, 0, 0)
            if online:
                try:
                    def update_bool_device(code, unit, value=None):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                            return False
                        # Get the current status of the device
                        if value is None:
                            currentstatus = StatusDeviceTuya(code)
                        else:
                            currentstatus = False if value == StatusDeviceTuya(code) else True
                        UpdateDomoticz(dev_id, unit, bool(currentstatus), int(bool(currentstatus)), 0)
                        return True

                    def update_value_device(code, unit, codeunit=None):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not get_unit(code, StatusProperties) not in [codeunit, None] or not checkDevice(dev_id, unit):
                            return False
                        # Get the current value of the device
                        currentvalue = StatusDeviceTuya(code)
                        if str(currentvalue) != str(Devices[dev_id].Units[unit].sValue):
                            UpdateDomoticz(dev_id, unit, currentvalue, 0, 0)
                        return True

                    def update_nvalue_device(code, unit, codeunit=None):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not get_unit(code, StatusProperties) not in [codeunit, None] or not checkDevice(dev_id, unit):
                            return False
                        # Get the current value of the device
                        value = StatusDeviceTuya(code)
                        if isinstance(value, (int, float)):
                            currentvalue = int(value)
                        else:
                            currentvalue = value
                        if str(currentvalue) != str(Devices[dev_id].Units[unit].nValue):
                            UpdateDomoticz(dev_id, unit, 0, currentvalue, 0)
                        return True

                    def update_dualvalue_device(code1, code2, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code1, StatusProperties) or not searchCode(code2, StatusProperties) or not checkDevice(dev_id, unit):
                            return False
                        # Get the current value of the device
                        currentvalue1 = StatusDeviceTuya(code1)
                        currentvalue2 = StatusDeviceTuya(code2)
                        currentdomo = Devices[dev_id].Units[unit].sValue
                        if str(currentvalue1) != str(currentdomo.split(';')[0]) or str(currentvalue2) != str(currentdomo.split(';')[1]):
                            UpdateDomoticz(dev_id, unit, str(currentvalue1 ) + ';' + str(currentvalue2) + ';0', 0, 0)
                        return True

                    def update_power_device(code, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                            return False
                        # Get the power value of the device
                        currentpower = StatusDeviceTuya(code)
                        lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[unit].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                        lastvalue = Devices[dev_id].Units[unit].sValue if len(Devices[dev_id].Units[unit].sValue) > 0 else '0;0'
                        # Calculating the Power Difference in an time interval
                        UpdateDomoticz(dev_id, unit, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)
                        return True

                    def update_select_device(code, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                            return False
                        # Get the current mode of the device
                        currentmode = StatusDeviceTuya(code)
                        # Get the mode configuration once
                        mode = getConfigItem(dev_id + '-' + str(unit), 'mode')
                        if mode is None or mode == {}:
                            # Loop through StatusProperties to set the mode
                            for item in StatusProperties:
                                if item['code'] == code:
                                    DomoticzEx.Debug('code: ' + str(item['code']))
                                    # Parse values based on item type
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                                    setConfigItem(dev_id + '-' + str(unit), {'mode': mode})
                                    break  # Exit the loop once we find the code
                        # Calculate the new value
                        try:
                            new_value = mode.index(str(currentmode)) * 10
                        except:
                            mode.append(currentmode)
                            Devices[dev_id].Units[unit].Options={'LevelNames': '|'.join(mode)}
                            setConfigItem(str(dev_id) + '-' + str(unit), {'mode': mode})
                            Devices[dev_id].Units[unit].Update(UpdateOptions=True)
                            new_value = mode.index(str(currentmode)) * 10
                        # Only update if the new value differs from the current value
                        if str(new_value) != str(Devices[dev_id].Units[unit].sValue):
                            UpdateDomoticz(dev_id, unit, int(new_value), 1, 0)
                        return True

                    def update_selectnum_device(code, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                            return False
                        # Get the current mode of the device
                        current = StatusDeviceTuya(code)
                        if str(current) != str(Devices[dev_id].Units[unit].sValue):
                            UpdateDomoticz(dev_id, unit, current, 1, 0)
                        return True
                    
                    def update_level_device(code, unit, level_mapping):
                        # Validate code, unit, and device
                        if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                            return False
                        # Get current level code from Tuya
                        currentlevel = StatusDeviceTuya(code)
                        # Map Tuya level to Domoticz level
                        level = level_mapping.get(currentlevel)
                        if level is None:
                            return False
                        # Update only if changed
                        if str(currentlevel) != str(Devices[dev_id].Units[unit].sValue):
                            UpdateDomoticz(dev_id, unit, str(currentlevel), level, 0)
                        return True

                    def update_text_device(code, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev_id, unit):
                            return False
                        # Get the current mode of the device
                        value = StatusDeviceTuya(code)
                        # Loop through StatusProperties to set the mode
                        for item in StatusProperties:
                            if item['code'] == code:
                                the_values = json.loads(item['values'])
                                mode = ['No fault']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values['label'])
                                    currentmode = mode[value].replace('_', ' ').capitalize()
                                else:
                                    mode.extend(the_values['range'])
                                    currentmode = mode[value].replace('_', ' ').capitalize()
                        # Only update if the new value differs from the current value
                        if str(currentmode) != str(Devices[dev_id].Units[unit].nValue):
                            UpdateDomoticz(dev_id, unit, str(currentmode), 1, 0)
                        return True

                    def battery_device():
                        # Battery_device
                        if searchCode('battery_state', StatusProperties) or searchCode('battery', StatusProperties) or searchCode('va_battery', StatusProperties) or searchCode('battery_percentage', StatusProperties):
                            if searchCode('battery_state', StatusProperties):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('BatteryStatus', StatusProperties):
                                if int(StatusDeviceTuya('BatteryStatus')) == 1:
                                    currentbattery = 100
                                elif int(StatusDeviceTuya('BatteryStatus')) == 2:
                                    currentbattery = 50
                                elif int(StatusDeviceTuya('BatteryStatus')) == 3:
                                    currentbattery = 5
                                else:
                                    currentbattery = 100
                            if searchCode('battery', StatusProperties):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', StatusProperties):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', StatusProperties):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            if searchCode('residual_electricity', StatusProperties):
                                currentbattery = StatusDeviceTuya('residual_electricity')
                            for unit in Devices[dev_id].Units:
                                if str(currentbattery) != str(Devices[dev_id].Units[unit].BatteryLevel):
                                    Devices[dev_id].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev_id].Units[unit].Update()
                        return
                    # status DomoticzEx
                    try:
                        sValue = Devices[dev_id].Units[1].sValue
                        nValue = Devices[dev_id].Units[1].nValue
                    except:
                        pass

                    if dev_type in ('switch', 'switch/sensor'):
                        if update_bool_device('switch_1', 1):
                            pass
                        elif update_bool_device('switch', 1):
                            pass

                        for switch_number in range(2, 9):
                            update_bool_device(f'switch_{switch_number}', switch_number)
                        if update_value_device('cur_current', 15, 'mA'):
                            pass
                        elif update_value_device('cur_current', 11):
                            pass
                        update_value_device('cur_power', 12)
                        update_value_device('cur_voltage', 13)
                        update_power_device('cur_power', 14)
                        if searchCode('phase_a', StatusProperties):
                            base64_string = StatusDeviceTuya('phase_a')
                            # Decode base64 string
                            decoded_data = base64.b64decode(base64_string)
                            # Extract voltage, current, and power data
                            currentvoltage = int.from_bytes(decoded_data[:2], byteorder='big') * 0.1
                            currentcurrent = int.from_bytes(decoded_data[2:5], byteorder='big') * 0.001
                            currentpower = int.from_bytes(decoded_data[5:8], byteorder='big')
                            UpdateDomoticz(dev_id, 11, str(currentcurrent), 0, 0)
                            UpdateDomoticz(dev_id, 12, str(currentpower), 0, 0)
                            UpdateDomoticz(dev_id, 13, str(currentvoltage), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[14].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev_id].Units[14].sValue if len(Devices[dev_id].Units[14].sValue) > 0 else '0;0'
                            currentEle = StatusDeviceTuya('add_ele')
                        update_value_device('leakage_current', 15)
                        update_value_device('temp_current', 16)
                        update_power_device('out_power', 17)
                        update_power_device('out_power', 18)
                        if searchCode('power_a', StatusProperties):
                            powerA = StatusDeviceTuya('power_a')
                            dirA = StatusDeviceTuya('direction_a')
                            if dirA == 'REVERSE':
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[19].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev_id].Units[19].sValue if len(Devices[dev_id].Units[19].sValue) > 0 else '0;0'
                                lastvalueR = Devices[dev_id].Units[20].sValue if len(Devices[dev_id].Units[20].sValue) > 0 else '0;0'
                                UpdateDomoticz(dev_id, 19, str(powerA) + ';' + str(float(lastvalue.split(';')[1]) + ((powerA) * (lastupdate / 3600))) , 0, 0, 1)
                                UpdateDomoticz(dev_id, 20, '0;' + str(float(lastvalueR.split(';')[1])) , 0, 0, 1)
                            if dirA == 'FORWARD':
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[20].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev_id].Units[20].sValue if len(Devices[dev_id].Units[20].sValue) > 0 else '0;0'
                                lastvalueR = Devices[dev_id].Units[19].sValue if len(Devices[dev_id].Units[19].sValue) > 0 else '0;0'
                                UpdateDomoticz(dev_id, 20, str(powerA) + ';' + str(float(lastvalue.split(';')[1]) + ((powerA) * (lastupdate / 3600))) , 0, 0, 1)
                                UpdateDomoticz(dev_id, 19, '0;' + str(float(lastvalueR.split(';')[1])) , 0, 0, 1)
                        if searchCode('power_b', StatusProperties):
                            powerB = StatusDeviceTuya('power_b')
                            dirB = StatusDeviceTuya('direction_b')
                            if dirB == 'REVERSE':
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[21].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev_id].Units[21].sValue if len(Devices[dev_id].Units[21].sValue) > 0 else '0;0'
                                lastvalueR = Devices[dev_id].Units[22].sValue if len(Devices[dev_id].Units[22].sValue) > 0 else '0;0'
                                UpdateDomoticz(dev_id, 21, str(powerB) + ';' + str(float(lastvalue.split(';')[1]) + ((powerB) * (lastupdate / 3600))) , 0, 0, 1)
                                UpdateDomoticz(dev_id, 22, '0;' + str(float(lastvalueR.split(';')[1])) , 0, 0, 1)
                            if dirB == 'FORWARD':
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[22].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev_id].Units[22].sValue if len(Devices[dev_id].Units[22].sValue) > 0 else '0;0'
                                lastvalueR = Devices[dev_id].Units[21].sValue if len(Devices[dev_id].Units[21].sValue) > 0 else '0;0'
                                UpdateDomoticz(dev_id, 22, str(powerB) + ';' + str(float(lastvalue.split(';')[1]) + ((powerB) * (lastupdate / 3600))) , 0, 0, 1)
                                UpdateDomoticz(dev_id, 21, '0;' + str(float(lastvalueR.split(';')[1])) , 0, 0, 1)
                        battery_device()

                    if dev_type == 'dimmer':
                        if searchCode('switch_led_1', StatusProperties):
                            currentstatus = StatusDeviceTuya('switch_led_1')
                            currentdim = brightness_to_pct(StatusProperties, 'bright_value_1', int(StatusDeviceTuya('bright_value_1')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDomoticz(dev_id, 1, False, 0, 0)
                            elif bool(currentstatus) == True and  currentdim > 0 and str(currentdim) != str(Devices[dev_id].Units[1].sValue):
                                UpdateDomoticz(dev_id, 1, currentdim, 1, 0)

                        if searchCode('switch_led_2', StatusProperties):
                            currentstatus = StatusDeviceTuya('switch_led_2')
                            currentdim = brightness_to_pct(StatusProperties, 'bright_value_2', int(StatusDeviceTuya('bright_value_2')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDomoticz(dev_id, 2, False, 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev_id].Units[2].sValue):
                                UpdateDomoticz(dev_id, 2, currentdim, 1, 0)

                    if dev_type in ('light','fanlight'):
                        unit = Devices[dev_id].Units[1]
                        if searchCode('switch_led', StatusProperties):
                            currentstatus = bool(StatusDeviceTuya('switch_led'))
                        else:
                            currentstatus = bool(StatusDeviceTuya('led_switch'))
                        nval = 1 if currentstatus else 0
                        if searchCode('bright_value_v2', StatusProperties):
                            dimtuya = brightness_to_pct(StatusProperties, 'bright_value_v2', int(StatusDeviceTuya('bright_value_v2')))
                        elif searchCode('bright_value', StatusProperties):
                            dimtuya = brightness_to_pct(StatusProperties, 'bright_value', int(StatusDeviceTuya('bright_value')))
                        else:
                            dimtuya = 100
                        svalue = str(dimtuya) if currentstatus else '0'
                        if str(unit.sValue) != svalue or unit.nValue != nval:
                            UpdateDomoticz(dev_id, 1, svalue, nval, 0)
                        if searchCode('Power', StatusProperties):
                            currentstatus = StatusDeviceTuya('Power')
                            UpdateDomoticz(dev_id, 2, bool(currentstatus), int(bool(currentstatus)), 0)
                        if searchCode('lightmode', StatusProperties):
                            currentmode = StatusDeviceTuya('lightmode')
                            for item in FunctionProperties:
                                if item['code'] == 'lightmode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev_id].Units[3].sValue):
                                UpdateDomoticz(dev_id, 3, int(mode.index(str(currentmode)) * 10), 1, 0)

                        if searchCode('dp_mist_grade', StatusProperties):
                            currentmode = StatusDeviceTuya('dp_mist_grade')
                            for item in FunctionProperties:
                                if item['code'] == 'dp_mist_grade':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values['label'])
                                    else:
                                        mode.extend(the_values['range'])
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev_id].Units[4].sValue):
                                UpdateDomoticz(dev_id, 4, int(mode.index(str(currentmode)) * 10), 1, 0)

                    if dev_type == 'cover':
                        if searchCode('position', StatusProperties) or searchCode('percent_control', StatusProperties):
                            if searchCode('position', StatusProperties):
                                currentposition = StatusDeviceTuya('position')
                            elif searchCode('percent_control', StatusProperties):
                                currentposition = StatusDeviceTuya('percent_control')
                            if str(currentposition) == '0':
                                UpdateDomoticz(dev_id, 1, currentposition, 0, 0)
                            if str(currentposition) == '100':
                                UpdateDomoticz(dev_id, 1, currentposition, 1, 0)
                            if str(currentposition) != str(Devices[dev_id].Units[1].sValue):
                                UpdateDomoticz(dev_id, 1, currentposition, 2, 0)
                        elif searchCode('mach_operate', StatusProperties):
                            currentstatus = StatusDeviceTuya('control')
                            if currentstatus == 'close':
                                UpdateDomoticz(dev_id, 1, 'ZZ', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDomoticz(dev_id, 1, 'FZ', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDomoticz(dev_id, 1, 'STOP', 1, 0)
                        elif searchCode('control', StatusProperties):
                            currentstatus = StatusDeviceTuya('control')
                            if currentstatus == 'close':
                                UpdateDomoticz(dev_id, 1, 'Open', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDomoticz(dev_id, 1, 'Close', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDomoticz(dev_id, 1, 'Stop', 1, 0)
                        if searchCode('position_2', StatusProperties) or searchCode('percent_control_2', StatusProperties):
                            if searchCode('position_2', StatusProperties):
                                currentposition = StatusDeviceTuya('position_2')
                            elif searchCode('percent_control_2', StatusProperties):
                                currentposition = StatusDeviceTuya('percent_control_2')
                            if str(currentposition) == '0':
                                UpdateDomoticz(dev_id, 2, currentposition, 0, 0)
                            if str(currentposition) == '100':
                                UpdateDomoticz(dev_id, 2, currentposition, 1, 0)
                            if str(currentposition) != str(Devices[dev_id].Units[2].sValue):
                                UpdateDomoticz(dev_id, 2, currentposition, 2, 0)
                        elif searchCode('mach_operate_2', StatusProperties):
                            currentstatus = StatusDeviceTuya('control_2')
                            if currentstatus == 'close':
                                UpdateDomoticz(dev_id, 2, 'ZZ', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDomoticz(dev_id, 2, 'FZ', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDomoticz(dev_id, 2, 'STOP', 1, 0)
                        elif searchCode('control_2', StatusProperties):
                            currentstatus = StatusDeviceTuya('control_2')
                            if currentstatus == 'close':
                                UpdateDomoticz(dev_id, 2, 'Open', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDomoticz(dev_id, 2, 'Close', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDomoticz(dev_id, 2, 'Stop', 1, 0)

                    if dev_type == 'smartheatpump':
                        update_value_device('intemp', 2)
                        update_value_device('outtemp', 3)
                        update_value_device('whjtemp', 4)
                        update_value_device('cmptemp', 5)
                        update_value_device('wttemp', 6)
                        update_value_device('hqtemp', 7)
                        update_value_device('cmp_act_frep', 8)
                        update_value_device('cmp_cur', 9)
                        update_value_device('dc_fan_speed', 10)
                        update_value_device('ach_stemp', 11)
                        update_value_device('wth_stemp', 12)
                        update_value_device('aircond_temp_diff', 13)
                        update_value_device('wth_temp_diff', 14)
                        update_value_device('acc_stemp', 15)
                        update_select_device('mode', 16)
                        update_select_device('work_mode', 17)
                        # update_value_device('temp_current', 18)
                        update_value_device('temp_set', 19)
                        # update_value_device('water_set', 20)
                        update_value_device('temp_top', 21)
                        update_value_device('temp_bottom',22)
                        update_bool_device('compressor_state',23)
                        update_value_device('water_flow',24)

                    if dev_type == 'thermostat' or dev_type == 'heater' or dev_type == 'heatpump':
                        if update_bool_device('switch', 1):
                            pass
                        elif update_bool_device('switch_1', 1):
                            pass
                        elif update_bool_device('switch_1', 1):
                            pass
                        elif update_bool_device('Power', 1):
                            pass
                        if update_bool_device('infared_switch', 1):
                            pass
                        if update_value_device('temp_current', 2):
                            pass
                        elif update_value_device('upper_temp', 2):
                            pass
                        elif update_value_device('c_temperature', 2):
                            pass
                        elif update_value_device('TempCurrent', 2):
                            pass
                        if update_value_device('temp_set', 3):
                            pass
                        elif update_value_device('set_temp', 3):
                            pass
                        elif update_value_device('temperature_c', 3):
                            pass
                        elif update_value_device('TempSet', 3):
                            pass
                        elif update_value_device('target_temp', 3):
                            pass
                        if update_select_device('running_mode', 4):
                            pass
                        elif update_select_device('work_mode', 4):
                            pass
                        elif update_select_device('Mode', 4):
                            pass
                        elif update_select_device('mode', 4):
                            pass
                        update_bool_device('window_check', 5)
                        update_bool_device('child_lock', 6)
                        update_bool_device('eco', 7)
                        update_value_device('temp_floor', 8)
                        if update_select_device('windspeed', 9):
                            pass
                        elif update_select_device('fan_level', 9):
                            pass
                        elif update_select_device('fan_speed_enum', 9):
                            pass
                        update_nvalue_device('humidity_current', 10)
                        if update_value_device('currentcurrent', 15, 'mA'):
                            pass
                        elif update_value_device('currentcurrent', 11):
                            pass
                        if update_value_device('cur_power',12):
                            pass
                        elif update_value_device('average_power', 12):
                            pass
                        update_value_device('cur_voltage', 13)
                        if update_power_device('cur_power', 14):
                            pass
                        elif update_power_device('average_power', 14):
                            pass
                        update_dualvalue_device('temp_current', 'humidity_current', 16)
                        update_bool_device('anti_bother', 17)
                        update_text_device('fault',18)
                        battery_device()

                    if dev_type in ('sensor', 'smartir'):
                        if update_value_device('va_temperature', 1):
                            pass
                        elif update_value_device('temp_current', 1):
                            pass
                        elif update_value_device('local_temp', 1):
                            pass
                        elif update_value_device('Tin', 1):
                            pass
                        if update_nvalue_device('va_humidity', 2):
                            pass
                        elif update_nvalue_device('humidity_value', 2):
                            pass
                        elif update_nvalue_device('local_hum', 2):
                            pass
                        elif update_nvalue_device('humidity', 2):
                            pass
                        elif update_nvalue_device('Hin', 2):
                            pass
                        if update_dualvalue_device('va_temperature','va_humidity', 3):
                            pass
                        elif update_dualvalue_device('va_temperature','humidity_value', 3):
                            pass
                        elif update_dualvalue_device('temp_current','humidity', 3):
                            pass
                        elif update_dualvalue_device('temp_current','humidity_value', 3):
                            pass
                        elif update_dualvalue_device('local_temp','local_hum', 3):
                            pass
                        elif update_dualvalue_device('Tin','Hin', 3):
                            pass
                        update_value_device('co2_value', 4)
                        # update_value_device('air_quality_index', 5)
                        update_level_device('air_quality_index', 5, {"level_1": 1, "level_2": 2, "level_3": 4})
                        update_value_device('ch2o_value', 6)
                        update_value_device('voc_value', 7)
                        update_value_device('pm25_value', 8)
                        update_value_device('pm10', 9)
                        update_value_device('bright_value', 10)
                        update_bool_device('switch', 11)
                        update_value_device('ph_current', 12)
                        update_value_device('pro_current', 13)
                        update_value_device('orp_current', 14)
                        update_value_device('ph_warn_min', 15)
                        update_value_device('ph_warn_max', 16)
                        update_value_device('pro_warn_min', 17)
                        update_value_device('pro_warn_max', 18)
                        update_value_device('orp_warn_min', 19)
                        update_value_device('orp_warn_max', 20)
                        if update_value_device('sub1_temp', 21):
                            pass
                        elif update_value_device('ToutCh1', 21):
                            pass
                        if update_nvalue_device('sub1_hum', 22):
                            pass
                        elif update_value_device('HoutCh1', 22):
                            pass
                        if update_dualvalue_device('sub1_temp', 'sub1_hum', 23):
                            pass
                        elif update_dualvalue_device('ToutCh1', 'HoutCh1', 23):
                            pass
                        update_value_device('temp_warn_min', 24)
                        update_value_device('temp_warn_max', 25)
                        if update_value_device('sub2_temp', 31):
                            pass
                        elif update_value_device('ToutCh2', 31):
                            pass
                        if update_nvalue_device('sub2_hum', 32):
                            pass
                        elif update_value_device('HoutCh2', 32):
                            pass
                        if update_dualvalue_device('sub2_temp', 'sub2_hum', 33):
                            pass
                        elif update_dualvalue_device('ToutCh2', 'HoutCh2', 33):
                            pass
                        if update_value_device('sub3_temp', 41):
                            pass
                        elif update_value_device('ToutCh3', 41):
                            pass
                        if update_nvalue_device('sub3_hum', 42):
                            pass
                        elif update_value_device('HoutCh3', 42):
                            pass
                        if update_dualvalue_device('sub3_temp', 'sub3_hum', 43):
                            pass
                        elif update_dualvalue_device('ToutCh3', 'HoutCh3', 43):
                            pass
                        update_value_device('temp_current_2', 44)
                        update_value_device('cook_temperature', 45)
                        update_value_device('cook_temperature_2', 46)
                        update_value_device('atmosphere', 47)
                        update_value_device('temp_current_2', 44)
                        update_bool_device('pir', 48, 'none')
                        update_bool_device('pir_state', 48, 'none')
                        update_bool_device('temper_alarm', 49)
                        update_select_device('co_status', 50)
                        update_select_device('checking_result', 51)
                        for channel in range(1, 8):
                            unit_base = 50 + (channel * 3)  # Unit 51 => 71
                            if update_value_device(f'ch{channel}_temp', unit_base - 2):
                                pass
                            if update_nvalue_device(f'ch{channel}_humi', unit_base - 1):
                                pass
                            if update_dualvalue_device(f'ch{channel}_temp', f'ch{channel}_humi', unit_base):
                                pass
                        battery_device()

                    if dev_type == 'doorbell':
                        update_bool_device('doorbell_active', 1, '')
                        update_bool_device('floodlight_switch', 2)
                        if update_bool_device('motion_switch', 3):
                            pass
                        elif update_bool_device('movement_detect_pic', 3, '$'):
                            pass
                        update_bool_device('basic_indicator', 4)

                    if dev_type == 'fan':
                        update_bool_device('switch', 1)
                        update_select_device('mode', 2)
                        update_selectnum_device('fan_speed', 3)
                        update_value_device('temp_set', 4)
                        update_value_device('temp_current', 5)
                        update_text_device('fault', 6)
                        update_bool_device('light', 7)
                        update_bool_device('RH_switch', 8)
                        update_value_device('RH_threshold', 9)
                        update_value_device('RH_value', 10)
                        update_bool_device('anion', 11)
                        update_bool_device('free_cooling', 12)
                        update_bool_device('powerful', 13)

                    if dev_type == 'fanlight':
                        update_bool_device('fan_switch', 2)
                        update_selectnum_device('fan_speed', 3)
                        update_select_device('fan_direction', 4)

                    if dev_type == 'siren':
                        update_bool_device('AlarmSwitch', 1)
                        if update_select_device('Alarmtype', 2):
                            pass
                        elif update_select_device('alarm_state', 2):
                            pass
                        if update_selectnum_device('AlarmPeriod', 3):
                            pass
                        elif update_selectnum_device('alarm_volume', 3):
                            pass
                        battery_device()

                    if dev_type == 'powermeter':
                        update_power_device('CurrentA', 1)
                        update_power_device('CurrentB', 1)
                        update_power_device('CurrentC', 1)
                        update_value_device('Frequency', 2)
                        update_value_device('Temperature', 3)
                        update_value_device('Current', 4)
                        update_power_device('ActivePower', 5)
                        update_value_device('VoltageA', 11)
                        update_power_device('ActivePowerA', 12)
                        update_value_device('VoltageB', 21)
                        update_power_device('ActivePowerB', 22)
                        update_value_device('VoltageC', 31)
                        update_power_device('ActivePowerC', 32)
                        if searchCode('phase_a', StatusProperties):
                            base64_string = StatusDeviceTuya('phase_a')
                            # Decode base64 string
                            decoded_data = base64.b64decode(base64_string)
                            # Extract voltage, current, and power data
                            currentvoltage = int.from_bytes(decoded_data[:2], byteorder='big') * 0.1
                            currentcurrent = int.from_bytes(decoded_data[2:5], byteorder='big') * 0.001
                            currentpower = int.from_bytes(decoded_data[5:8], byteorder='big')
                            leakagecurrent = StatusDeviceTuya('leakage_current')
                            if product_id == 'ze8faryrxr0glqnn':
                                if str(int.from_bytes(decoded_data[2:5], byteorder='big'))[-1:] == '1':
                                    currentcurrent = 0 - currentcurrent
                                    currentpower = 0 - currentpower
                            UpdateDomoticz(dev_id, 1, str(currentcurrent), 0, 0)
                            UpdateDomoticz(dev_id, 2, str(currentpower), 0, 0)
                            UpdateDomoticz(dev_id, 3, str(currentvoltage), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev_id].Units[4].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev_id].Units[4].sValue if len(Devices[dev_id].Units[4].sValue) > 0 else '0;0'
                            UpdateDomoticz(dev_id, 4, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)
                        update_bool_device('switch', 5)
                        update_text_device('fault', 6)
                        # 2 phase Meter with reverse
                        update_value_device('voltage_a', 1)
                        update_value_device('freq', 2)
                        update_power_device('total_power', 3)
                        update_value_device('power_a', 11)
                        update_value_device('current_a', 12)
                        update_value_device('direction_a', 13)
                        update_value_device('energy_forword_a', 14)
                        update_value_device('energy_reverse_a', 15)
                        update_value_device('power_b', 21)
                        update_value_device('current_b', 22)
                        update_value_device('direction_b', 23)
                        update_value_device('energy_forword_b', 24)
                        update_value_device('energy_reserse_b', 25)

                    if dev_type == 'powermeter' and (searchCode('switch', StatusProperties) or searchCode('switch_1', StatusProperties)) and not searchCode('phase_a', StatusProperties):
                        if update_bool_device('switch', 1):
                            pass
                        elif update_bool_device('switch_1', 1):
                            pass
                        update_value_device('cur_current', 2)
                        update_power_device('cur_power', 3)
                        update_value_device('cur_voltage', 4)
                        update_text_device('fault', 5)

                    if dev_type == 'gateway':
                        if update_value_device('master_state', 1):
                            pass
                        else:
                            UpdateDomoticz(dev_id, 1, 'Gateway only', 0, 0)

                    if dev_type == 'doorcontact':
                        update_bool_device('doorcontact_state', 1)
                        battery_device()

                    if dev_type == 'pirlight':
                        update_bool_device('switch_pir', 2)
                        update_select_device('device_mode', 3)
                        update_select_device('pir_sensitivity', 4)

                    if dev_type == 'smokedetector':
                        if update_bool_device('smoke_sensor_status', 2, 'normal'):
                            pass
                        elif update_bool_device('PIR', 2, 0):
                            pass
                        # if searchCode('smoke_sensor_status', StatusProperties):
                        #     currentstatus = StatusDeviceTuya('smoke_sensor_status')
                        #     if currentstatus == 'normal':
                        #         UpdateDomoticz(dev_id, 1, False, 0, 0)
                        #     elif currentstatus == 'alarm':
                        #         UpdateDomoticz(dev_id, 1, True, 1, 0)
                        #     UpdateDomoticz(dev_id, 2, currentstatus, 0, 0)
                        # if searchCode('PIR', StatusProperties):
                        #     currentstatus = StatusDeviceTuya('PIR')
                        #     if int(currentstatus) == 0:
                        #         UpdateDomoticz(dev_id, 1, False, 0, 0)
                        #     elif int(currentstatus) > 0:
                        #         UpdateDomoticz(dev_id, 1, True, 1, 0)
                        #     UpdateDomoticz(dev_id, 2, currentstatus, 0, 0)
                        battery_device()

                    if dev_type == 'garagedooropener':
                        update_bool_device('switch_1', 1)
                        update_bool_device('doorcontact_state', 2)
                        update_bool_device('door_control_1', 3)

                    if dev_type == 'feeder':
                        update_selectnum_device('manual_feed', 1)
                        update_select_device('feed_state', 2)
                        update_selectnum_device('feed_report', 3)
                        update_bool_device('light', 5)

                    if dev_type == 'waterleak':
                        update_bool_device('watersensor_state', 1, 'normal')
                        battery_device()

                    if dev_type == 'irrigation':
                        if update_bool_device('switch', 1):
                            pass
                        elif update_bool_device('switch_1', 1):
                            pass
                        update_select_device('work_state', 2)
                        update_bool_device('areaone', 3)
                        update_bool_device('areatwo', 4)
                        update_bool_device('areathree', 5)
                        update_bool_device('areafour', 6)
                        update_bool_device('areafive', 7)
                        update_bool_device('areasix', 8)
                        battery_device()

                    if dev_type == 'wswitch':
                        for x in range(1, 4):
                            if update_select_device('switch' + str(x) + '_value', x):
                                pass
                            elif update_select_device('switch_type_' + str(x), x):
                                pass
                            elif update_select_device('switch_mode' + str(x), x):
                                pass
                        battery_device()

                    if dev_type == 'starlight':
                        update_bool_device('switch_led', 1)
                        colortuya = StatusDeviceTuya('colour_data')
                        if currentstatus == True:
                            tuyacolor = ast.literal_eval(StatusDeviceTuya('colour_data'))
                            Color = Devices[dev_id].Units[1].Color
                            if Color == '':
                                Color = {'b':255,'cw':0,'g':255,'m':3,'r':255,'t':0,'ww':0}
                            h, s, v = tuyacolor['h'], tuyacolor['s'], tuyacolor['v']
                            r, g, b = hsv_to_rgb_v2(h, s, v)
                            colorupdate = {'b':b,'cw':0,'g':g,'m':3,'r':r,'t':0,'ww':0}
                            # {'b':0,'cw':0,'g':3,'m':3,'r':255,'t':0,'ww':0}
                            if (Color['r'] != r or Color['g'] != g or Color['b'] != b ):
                                UpdateDomoticz(dev_id, 1, json.dumps(colorupdate), 1, 0)
                                UpdateDomoticz(dev_id, 1, brightness_to_pct(StatusProperties, 'bright_value', int(v * 0.255)), 1, 0)
                        update_bool_device('colour_switch', 2)
                        if searchCode('laser_switch', StatusProperties):
                            currentstatus = StatusDeviceTuya('laser_switch')
                            currentdim = brightness_to_pct(StatusProperties, 'laser_bright', int(StatusDeviceTuya('laser_bright')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDomoticz(dev_id, 3, False, 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev_id].Units[3].sValue):
                                UpdateDomoticz(dev_id, 3, True, 1, 0)
                                UpdateDomoticz(dev_id, 3, currentdim, 1, 0)
                        if searchCode('fan_switch', StatusProperties):
                            currentstatus = StatusDeviceTuya('fan_switch')
                            currentdim = brightness_to_pct(StatusProperties, 'fan_speed', int(StatusDeviceTuya('fan_speed')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDomoticz(dev_id, 4, False, 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev_id].Units[4].sValue):
                                UpdateDomoticz(dev_id, 4, True, 1, 0)
                                UpdateDomoticz(dev_id, 4, currentdim, 1, 0)

                    if dev_type == 'smartlock':
                        if update_bool_device('lock_motor_state', 1):
                            pass
                        elif update_bool_device('rtc_lock', 1):
                            pass
                        update_select_device('alarm_lock', 2)
                        update_bool_device('unlock_ble', 3)
                        update_bool_device('unlock_card', 4)
                        battery_device()

                    if dev_type == 'dehumidifier':
                        update_bool_device('switch', 1)
                        if update_selectnum_device('dehumidify_set_value', 2):
                            pass
                        elif update_selectnum_device('dehumidify_set_enum', 2):
                            pass
                        update_select_device('fan_speed_enum', 3)
                        update_select_device('mode', 4)
                        update_value_device('fault', 5)
                        update_value_device('temp_indoor', 6)
                        update_nvalue_device('humidity_indoor', 7)
                        update_dualvalue_device('temp_indoor', 'humidity_indoor', 8)
                        update_bool_device('child_lock', 9)
                        update_bool_device('anion', 10)
                        update_bool_device('filter_reset', 11)
                        update_value_device('filter_life', 12)
                        update_bool_device('runtime_total_reset', 13)
                        update_value_device('type_of_equipment', 14)

                    if dev_type == 'vacuum':
                        update_bool_device('power_go', 1)
                        update_bool_device('switch_charge', 2)
                        update_select_device('mode', 3)
                        update_select_device('suction', 4)
                        update_select_device('cistern', 5)
                        update_text_device('status', 6)
                        update_value_device('electricity_left', 7)
                        update_value_device('edge_brush', 8)
                        update_value_device('roll_brush', 9)
                        update_value_device('filter', 10)
                        update_value_device('electricity_left', 7)
                        update_text_device('fault', 11)
                        battery_device

                    if dev_type == 'multifunctionalarm':
                        update_value_device('master_mode', 1)

                    if dev_type == 'purifier':
                        update_bool_device('switch', 1)
                        update_value_device('pm25', 2)
                        update_select_device('mode', 3)
                        update_select_device('speed', 4)
                        update_value_device('filter', 5)
                        update_value_device('air_quality', 6)

                    if dev_type == 'smartkettle':
                        update_bool_device('start', 1)
                        update_text_device('status', 2)
                        update_value_device('temperature', 3)
                        update_value_device('cook_temperature', 4)
                        update_text_device('fault', 5)

                    if dev_type == 'mower':
                        update_bool_device('MachineControlCmd', 1)
                        update_bool_device('MachineRainMode', 2)
                        update_select_device('MachineStatus', 3)
                        update_select_device('MachineWarning', 4)
                        update_select_device('MachineError', 5)
                        update_select_device('MachineWorkMode', 5)
                        battery_device()

                    if dev_type == 'human_presence':
                        update_bool_device('presence_state', 1, 'none')
                        update_selectnum_device('sensitivity', 2)
                        update_value_device('near_detection', 3)
                        update_value_device('far_detection', 4)
                        update_text_device('checking_result', 5)
                        update_value_device('target_dis_closest', 6)
                        update_select_device('presence_state', 10)

                    if dev_type == 'evcharger':
                        update_bool_device('switch', 1)
                        update_text_device('work_state', 2)
                        update_value_device('temp_current', 3)
                        update_value_device('power_total', 4)
                        update_value_device('charge_cur_set', 5)
                        update_value_device('forward_energy_total', 6)
                        update_text_device('online_state', 7)
                        # update_text_device('fault', 8)

                except Exception as err:
                    DomoticzEx.Error('Device read failed: ' + str(dev_id) + ' line ' + format(sys.exc_info()[-1].tb_lineno))
                    DomoticzEx.Debug('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

    except Exception as e:
        DomoticzEx.Error(str(e))
        DomoticzEx.Error(traceback.format_exc())

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            DomoticzEx.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    DomoticzEx.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        DomoticzEx.Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        DomoticzEx.Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            DomoticzEx.Debug("--->Unit:           " + str(UnitNo))
            DomoticzEx.Debug("--->Unit Name:     '" + Unit.Name + "'")
            DomoticzEx.Debug("--->Unit nValue:    " + str(Unit.nValue))
            DomoticzEx.Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            DomoticzEx.Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return

# Select device type from category
def DeviceType(category, product_id=None):
    'convert category to device type'
    'https://github.com/tuya/tuya-home-assistant/wiki/Supported-Device-Category'
    if product_id in {'uoa3mayicscacseb', 'igtakqsfhbr7qsp7'}:
        resultdev = 'cover'
    elif product_id in {'chfpey4klfcp1ipl'}:
        resultdev = 'dimmer'
    elif product_id in {'p6sqiuesvhmhvv4f'}:
        resultdev = 'doorcontact'
    elif category in {'kg', 'cz', 'pc', 'tdq', 'znjdq', 'szjqr', 'aqcz'}:
        resultdev = 'switch'
    elif category in {'tdq'}:
        resultdev = 'switch/sensor'
    elif category in {'dj', 'dd', 'dc', 'fwl', 'xdd', 'fwd', 'jsq', 'tyndj', 'tyd'}:
        resultdev = 'light'
    elif category in {'tgq', 'tgkg'}:
        resultdev = 'dimmer'
    elif category in {'cl', 'clkg', 'jdcljqr', 'mc'}:
        resultdev = 'cover'
    elif category in {'qn'}:
        resultdev = 'heater'
    elif category in {'wk', 'wkf', 'mjj', 'wkcz', 'kt','hwktwkq', 'ydkt', 'cjkg'}:
        resultdev = 'thermostat'
    elif category in {'wsdcg', 'co2bj', 'hjjcy', 'qxj', 'ldcg', 'swtz', 'zwjcy','pir','dgnbj','cobj'}:
        resultdev = 'sensor'
    elif category in {'rs'}:
        resultdev = 'heatpump'
    elif category in {'znrb'}:
        resultdev = 'smartheatpump'
    elif category in {'sp'}:
        resultdev = 'doorbell'
    elif category in {'fs'}:
        resultdev = 'fan'
    elif category in {'fsd'}:
        resultdev = 'fanlight'
    elif category in {'sgbj'}:
        resultdev = 'siren'
    elif category in {'wnykq'}:
        resultdev = 'smartir'
    elif category in {'zndb', 'dlq'}:
        resultdev = 'powermeter'
    elif category in {'wg2', 'wfcon'}:
        resultdev = 'gateway'
    elif category in {'mcs'}:
        resultdev = 'doorcontact'
    elif category in {'gyd'}:
        resultdev = 'pirlight'
    elif category in {'qt','ywbj'}:
        resultdev = 'smokedetector'
    elif category in {'ckmkzq'}:
        resultdev = 'garagedooropener'
    elif category in {'cwwsq'}:
        resultdev = 'feeder'
    elif category in {'sj'}:
        resultdev = 'waterleak'
    elif category in {'sfkzq'}:
        resultdev = 'irrigation'
    elif category in {'wxkg'}:
        resultdev = 'wswitch'
    elif category in {'xktyd'}:
        resultdev = 'starlight'
    elif category in {'ms','jtmspro'}:
        resultdev = 'smartlock'
    elif category in {'cs'}:
        resultdev = 'dehumidifier'
    elif category in {'sd'}:
        resultdev = 'vacuum'
    elif category in {'mal'}:
        resultdev = 'multifunctionalarm'
    elif category in {'kj'}:
        resultdev = 'purifier'
    elif category in {'bh'}:
        resultdev = 'smartkettle'
    elif category in {'gcj'}:
        resultdev = 'mower'
    elif category in {'hps'}:
        resultdev = 'human_presence'
    elif category in {'qccdz'}:
        resultdev = 'evcharger'
    elif category in {'infrared_ac'}:
        resultdev = 'infrared_ac'
    elif 'infrared_' in category: # keep it last
        resultdev = 'infrared'
    else:
        resultdev = 'unknown'
    return resultdev

def UpdateDomoticz(ID, Unit, sValue, nValue, TimedOut, AlwaysUpdate=0):

    if not checkDevice(ID, Unit):
        DomoticzEx.Debug(
            f"Device {ID} Unit {Unit} doesn't exist. Nothing to update"
        )
        return

    unit = Devices[ID].Units[Unit]

    # Detect color JSON explicitly
    is_color = False
    if isinstance(sValue, str):
        try:
            js = json.loads(sValue)
            if isinstance(js, dict) and 'm' in js:
                is_color = True
        except Exception:
            pass

    # Prevent unnecessary updates
    if (
        str(unit.sValue) == str(sValue)
        and str(unit.nValue) == str(nValue)
        and str(Devices[ID].TimedOut) == str(TimedOut)
        and not AlwaysUpdate
    ):
        return

    # Apply updates
    if sValue is not None:
        unit.sValue = str(sValue)

        if is_color:
            unit.Color = str(sValue)
        else:
            # numeric slider value
            try:
                unit.LastLevel = int(float(sValue))
            except Exception:
                pass

    unit.nValue = nValue
    Devices[ID].TimedOut = TimedOut
    unit.Update(Log=True)

    DomoticzEx.Log(f"Update device value: {ID} Unit:{Unit} sValue:{sValue} nValue:{nValue} TimedOut={TimedOut}"
    )

def StatusDeviceTuya(Function):
    if searchCode(Function, StatusProperties):
        valueRaw = [item['value'] for item in ResultValue if re.search(r'\b'+Function+r'\b', item['code']) != None][0]
    else:
        DomoticzEx.Debug('StatusDeviceTuya called ' + Function + ' not found ')
        return None
    if isinstance(valueRaw, (int, float)):
        valueT = get_scale(StatusProperties, Function, valueRaw)
    else:
        valueT = valueRaw
    return valueT

def SendCommandTuya(ID, CommandName, Status):
    sendfunction = properties[ID]['functions']
    actual_function_name = CommandName
    CommandName = list([CommandName])
    actual_status = Status

    # Zoek juiste code
    for item in sendfunction:
        if str(CommandName) in str(item['code']):
            actual_function_name = str(item['code'])

    # Schaling (brightness, temp, numeric)
    if any(x in CommandName for x in ['bright_value', 'bright_value_v2', 'bright_value_1', 'bright_value_2', 'laser_bright']):
        actual_status = pct_to_brightness(sendfunction, actual_function_name, Status)
    elif any(x in CommandName for x in ['temp_value', 'temp_value_v2']):
        actual_status = temp_value_scale(sendfunction, actual_function_name, Status)
    elif isinstance(Status, (int, float)) and not isinstance(Status, bool):
        actual_status = set_scale(sendfunction, actual_function_name, Status)

    DomoticzEx.Debug(f"SendCommand: {ID} | {actual_function_name} = {actual_status}")

    #------ LOCAL TINYTUYA------
    if ID in localtuya and ID in dps_map:
        try:
            dp_id = dps_map[ID]['by_code'].get(actual_function_name)
            if dp_id is None:
                raise Exception(f"No dp_id for code {actual_function_name}")

            device_key = getConfigItem(ID, 'key')
            d = tinytuya.Device(
                ID,
                localtuya[ID]['ip'],
                device_key
            )
            d.set_version(float(localtuya[ID]['version']))
            d.socketRetryLimit = 1
            d.socketRetryDelay = 1

            result = d.set_status(actual_status, int(dp_id))

            if not result or 'Error' in result or 'Err' in result:
                raise Exception(result)

            DomoticzEx.Log(f"[LOCAL] Command sent: dp_id {dp_id} = {actual_status} ({ID})")
            return

        except Exception as e:
            DomoticzEx.Debug(f"[LOCAL FAILED] {ID}, fallback to cloud: {e}")

    #------ FALLBACK: TUYA CLOUD------
    if actual_function_name in ('PowerOff', 'PowerOn'):
        uri = 'devices/'
    else:
        uri = 'iot-03/devices/'

    if not testdata:
        tuya.sendcommand(
            ID,
            {'commands': [{'code': actual_function_name, 'value': actual_status}]},
            uri
        )

    DomoticzEx.Log(f"[CLOUD] Command sent to Tuya: {ID}, { {'commands': [{'code': actual_function_name, 'value': actual_status}]} }, {uri}")

def pct_to_brightness(device_functions, actual_function_name, pct):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min', 0))
                max_value = int(the_values.get('max', 1000))
                # DomoticzEx.Debug(round(min_value + (pct*(max_value - min_value)) / 100))
                return round(min_value + (pct*(max_value - min_value)) / 100)
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round(22.68 + (int(pct) * ((255 - 22.68) / 100)))

def brightness_to_pct(device_functions, actual_function_name, raw):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min', 0))
                max_value = int(the_values.get('max', 255))
                return round((100 / (max_value - min_value) * (int(raw) - min_value)))
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round((100 / (255 - 22.68) * (int(raw) - 22.68)))

def temp_value_scale(device_functions, actual_function_name, raw):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min', 0))
                max_value = int(the_values.get('max', 255))
                return round((255 / (max_value - min_value) * (int((max_value - raw)) - min_value)))
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round((int(max_value - raw)))

def set_scale(device_functions, actual_function_name, raw):
    scale = 0
    try:
        if device_functions and actual_function_name:
            for item in device_functions:
                if item['code'] == actual_function_name:
                    the_values = json.loads(item['values'])
                    scale = int(the_values.get('scale', 0))
                    # step = the_values.get('step', 0)
                    max = the_values.get('max', 0)
                    min = the_values.get('min', 0)
        if scale == 1:
            resultscale = int(raw * 10)
        elif scale == 2:
            resultscale = int(raw * 100)
        elif scale == 3:
            resultscale = int(raw * 1000)
        else:
            resultscale = int(raw)
        if product_id == 'IAYz2WK1th0cMLmL':
            resultscale = int(raw * 2)
        if resultscale > max:
            resultscale = int(max)
            DomoticzEx.Log('Value higher then maximum device')
        elif resultscale < min:
            resultscale = int(min)
            DomoticzEx.Log('Value lower then minium device')
    except:
        resultscale = str(raw)
    return resultscale

def get_scale(device_functions, actual_function_name, raw):
    scale = 0
    # if actual_function_name == 'temp_current': actual_function_name = 'temp_set'
    try:
        if device_functions and actual_function_name:
            for item in device_functions:
                if item['code'] == actual_function_name:
                    the_values = json.loads(item['values'])
                    scale = the_values.get('scale', 0 )
                    # step = the_values.get('step', 0)
                    unit = the_values.get('unit', 0)
                    max = the_values.get('max', 0)
        if scale == 0:
            if unit == 'V' and len(str(max)) >= 4:
                resultscale = float(raw / 10)
            elif unit == 'W' and len(str(max)) >= 5:
                resuresultscalelt = float(raw / 10)
            else:
                resultscale = int(raw)
        elif scale == 1:
            resultscale = float(raw / 10)
        elif scale == 2:
            resultscale = float(raw / 100)
        elif scale == 3:
            resultscale  = float(raw / 1000)
        else:
            resultscale = int(raw)
        if product_id == 'IAYz2WK1th0cMLmL':
            resultscale = float(raw / 2)
        if product_id == 'g9m7honkxjweukvt' and actual_function_name == 'temp_current':
            resultscale = float(raw / 10)
    except:
        resultscale = raw
        DomoticzEx.Debug('Scale device:' + str(actual_function_name) + ' Value: ' + str(resultscale))
    return resultscale

def get_unit(actual_function_name, device_functions):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                resultunit = the_values.get('unit', 0)
    return resultunit

def rgb_to_hsv(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h = int(h * 360)
    s = int(s * 255)
    v = int(v * 255)
    return h, s, v

def rgb_to_hsv_v2(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 1000, g / 1000, b / 1000)
    h = int(h * 360)
    s = int(s * 1000)
    v = int(v * 1000)
    return h, s, v

def hsv_to_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h / 360, s / 255, v / 255)
    r = round(r * 255)
    g = round(g * 255)
    b = round(b * 255)
    return r, g, b

def hsv_to_rgb_v2(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h / 360, s / 1000, v / 1000)
    r = round(r * 255)
    g = round(g * 255)
    b = round(b * 255)
    return r, g, b

def inv_pct(v):
    return 100 - v

def inv_val(v):
    return 255 - v

def rgb_temp(t,v):
    return int((t / 100) * v)

def temp_cw_ww(t):
    cw = t
    ww = 255 - t
    return cw, ww

def nextUnit(ID):
    unit = 1
    while unit in Devices(ID) and unit < 255:
        unit = unit + 1
    return unit

def checkDevice(Id, Unit):
    try:
        Devices[Id].Units[Unit]
        return True
    except:
        return False

def searchCode(Item, Function):
    if searchCodeActualFunction(Item, Function) is None:
        return False
    return True

def searchValue(Item, Function):
    ActualItem = searchCodeActualFunction(Item, Function)
    if not ActualItem:
        return 0

    # JSON-string → object
    if isinstance(Function, str):
        try:
            Function = json.loads(Function)
        except json.JSONDecodeError:
            return 0

    for Elem in Function:
        if isinstance(Elem, dict) and str(ActualItem) == str(Elem.get('code')):
            return Elem.get('value', 0)

    return 0

def searchCodeActualFunction(Item, Function):
    if not Function:
        return None

    # JSON-string → object
    if isinstance(Function, str):
        try:
            Function = json.loads(Function)
        except json.JSONDecodeError:
            return None

    # Verwacht: lijst van dicts
    if isinstance(Function, list):
        for OneItem in Function:
            if isinstance(OneItem, dict) and str(Item) == str(OneItem.get('code')):
                return OneItem.get('code')

    return None

def createDevice(ID, Unit):
    if ID in Devices:
        if Unit in Devices[ID].Units:
            value = False
        else:
            value = True
    else:
        value = True
    return value

def deleteDevice(ID, Unit):
    if ID in Devices:
        DomoticzEx.Log('Deleting device with ID ' + str(ID) + ' Unit ' + str(Unit) + '.')
        Devices[ID].Units[Unit].Delete()
    else:
        DomoticzEx.Debug('Device with ID ' + str(ID) + ' not found. Cannot delete.')

def updateDevice():
    templates = [
        {'name_suffix': ' (dehumidify)', 'unit': 2, 'dtype': 244, 'subtype': 62, 'switchtype': 18, 'image': 11},
        {'name_suffix': ' (dehumidify)', 'unit': 2, 'dtype': 242, 'subtype': 1, 'image': 11},
    ]

    def _matches_template(dev, tpl):
        try:
            if 'name_suffix' in tpl and not dev.Name.endswith(tpl['name_suffix']):
                return False
            if 'unit' in tpl and int(dev.Unit) != int(tpl['unit']):
                return False
            if 'dtype' in tpl and int(dev.Type) != int(tpl['dtype']):
                return False
            if 'subtype' in tpl and int(dev.SubType) != int(tpl['subtype']):
                return False
            if 'switchtype' in tpl and int(dev.SwitchType) != int(tpl['switchtype']):
                return False
            if 'image' in tpl and int(dev.Image) != int(tpl['image']):
                return False
            return True
        except Exception:
            return False
    for idx, dev in list(DomoticzEx.Devices.items()):
        for tpl in templates:
            if _matches_template(dev, tpl):
                DomoticzEx.Log("Removing device matching template: idx={} Name='{}'".format(idx, dev.Name))
                try:
                    DomoticzEx.Device(Unit=dev.Unit, DeviceID=dev.DeviceID).Delete()
                except Exception:
                    try:
                        DomoticzEx.Device(idx).Delete()
                    except Exception as e:
                        DomoticzEx.Log('Failed to remove device idx {}: {}'.format(idx, e), DomoticzEx.LOG_ERROR)
                break
    return

def is_battery_device(StatusProperties):
    """Check if device has battery-related properties with type safety."""
    if isinstance(StatusProperties, str):
        # Search directly in the string
        battery_codes = [
            'battery_state',
            'battery', 
            'va_battery',
            'battery_percentage',
            'residual_electricity'
        ]
        return any(code in StatusProperties.lower() for code in battery_codes)
    
    elif isinstance(StatusProperties, dict):
        # Handle dictionary
        return any(
            searchCode(code, StatusProperties)
            for code in (
                'battery_state',
                'battery',
                'va_battery',
                'battery_percentage',
                'residual_electricity'
            )
        )
    
    return False

# Configuration Helpers
def getConfigItem(Key=None, Values=None):
    Value = {}
    try:
        Config = DomoticzEx.Configuration()
        if (Key != None):
            # DomoticzEx.Debug(Config[Key][Values])
            Value = Config[Key][Values]  # only return requested key if there was one
        else:
            Value = Config      # return the whole configuration if no key
    except KeyError:
        Value = {}
    except Exception as inst:
        DomoticzEx.Error('DomoticzEx.Configuration read failed: ' + str(inst))
    return Value

def setConfigItem(Key=None, Value=None):
    Config = {}
    try:
        Config = DomoticzEx.Configuration()
        if (Key != None):
            Config[Key] = Value
        else:
            Config = Value  # set whole configuration if no key specified
        Config = DomoticzEx.Configuration(Config)
    except Exception as inst:
        DomoticzEx.Error('DomoticzEx.Configuration operation failed: ' + str(inst))
    return Config

def version(ver):
    return tuple(map(int, (ver.split('.'))))