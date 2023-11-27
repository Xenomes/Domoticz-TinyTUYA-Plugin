# Domoticz TUYA Plugin
#
# Author: Xenomes (xenomes@outlook.com)
#
"""
<plugin key="tinytuya" name="TinyTUYA (Cloud)" author="Xenomes" version="1.6.6" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git">
    <description>
        Support forum: <a href="https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441">https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441</a><br/>
        <br/>
        <h2>TinyTUYA Plugin version 1.6.6</h2><br/>
        The plugin make use of IoT Cloud Platform account for setup up see https://github.com/jasonacox/tinytuya step 3 or see PDF https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Auto-detection of devices on network</li>
            <li>On/Off control, state and available status display</li>
            <li>Scene activation support</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>All devices that have on/off state should be supported</li>
        </ul>
        <h3>Configuration</h3>
        <ul style="list-style-type:square">
        <li>Enter your Region, Access ID/Client ID, Access Secret/Client Secret and a Search deviceID from your Tuya IOT Account, keep the setting 'Data Timeout' disabled.</li>
        <li>A deviceID can be found on your IOT account of Tuya got to Cloud => your project => Devices => Pick one of you device ID. (This id is used to detect all the other devices) </li>
        <li>The initial setup of your devices should be done with the app and this plugin will detect/use the same settings and automatically find/add the devices into Domoticz.<br/></li>
        </ul>
        Is your subscription to cloud development plan expired, you can extend it <a href="https://iot.tuya.com/cloud/products/apply-extension"> HERE</a><br/>

    </description>
    <params>
        <param field="Mode1" label="Region" width="150px" required="true" default="EU">
            <options>
                <option label="EU" value="eu" default="true" />
                <option label="US" value="us"/>
                <option label="CN" value="cn"/>
            </options>
        </param>
        <param field="Username" label="Access ID" width="300px" required="true" default="" />
        <param field="Password" label="Access Secret" width="300px" required="true" default="" password="true" />
        <param field="Mode2" label="Search DeviceID" width="300px" required="true" />
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
try:
    import DomoticzEx as Domoticz
except ImportError:
    import fakeDomoticz as Domoticz
import tinytuya
import os
import sys
import ast
import json
import colorsys
import time
import re
import base64

class BasePlugin:
    enabled = False
    def __init__(self):
        return

    def onStart(self):
        Domoticz.Log('TinyTUYA ' + Parameters['Version'] + ' plugin started')
        Domoticz.Log('TinyTuyaVersion:' + tinytuya.version )
        if Parameters['Mode6'] != '0':
            Domoticz.Debugging(int(Parameters['Mode6']))
            # Domoticz.Log('Debugger started, use 'telnet 0.0.0.0 4444' to connect')
            # import rpdb
            # rpdb.set_trace()
            DumpConfigToLog()

        global testData
        if os.path.isfile(Parameters['HomeFolder'] + '/debug_devices.json'):
            testData = True
            Domoticz.Heartbeat(5)
            Domoticz.Error('!! Warning Plugin overruled by local json files !!')
        else:
            testData = False
            Domoticz.Heartbeat(10)

        onHandleThread(True)

    def onStop(self):
        try:
            devs = Devices
            for dev in devs:
                # Delete device is not reconised
                if Devices[dev].Units[1].sValue == 'This device is not reconised, edit and run the debug_discovery with python from the tools directory and receate a issue report at https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/issues so the device can be added.':
                    Devices[dev].Units[1].Delete()
        except:
            Domoticz.Log('onStop called')

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log('onConnect called')

    def onMessage(self, Connection, Data):
        Domoticz.Log('onMessage called')

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Domoticz.Debug("onCommand called for Device " + str(DeviceID) + " Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level) + "', Color: " + str(Color))

        # device for the Domoticz
        dev = Devices[DeviceID].Units[Unit]
        Domoticz.Debug('Device ID: ' + str(DeviceID))

        Domoticz.Debug('nValue: ' + str(dev.nValue))
        Domoticz.Debug('sValue: ' + str(dev.sValue) + ' Type ' + str(type(dev.sValue)))
        Domoticz.Debug('LastLevel: ' + str(dev.LastLevel))

        if Error is not None:
            Domoticz.Error(Error['Payload'])
        else:
            # Control device and update status in Domoticz
            dev_type = getConfigItem(DeviceID, 'category')
            # scalemode = getConfigItem(DeviceID, 'scalemode')
            product_id = getConfigItem(DeviceID, 'product_id')
            # if len(properties) == 0:
            #     properties = {}
            #     for dev in devs:
            #         properties[dev['id']] = tuya.getproperties(dev['id'])['result']

            function = properties[DeviceID]['functions']
            if len(Color) != 0: Color = ast.literal_eval(Color)

            if dev_type == 'switch':
                if searchCode('switch', function):
                    if Command == 'Off':
                        SendCommandCloud(DeviceID, 'switch', False)
                        UpdateDevice(DeviceID, Unit, 'Off', 0, 0)
                    elif Command == 'On':
                        SendCommandCloud(DeviceID, 'switch', True)
                        UpdateDevice(DeviceID, Unit, 'On', 1, 0)
                    elif Command == 'Set Level':
                        SendCommandCloud(DeviceID, 'switch', True)
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if not searchCode('switch', function):
                    if Command == 'Off':
                        SendCommandCloud(DeviceID, 'switch_' + str(Unit), False)
                        UpdateDevice(DeviceID, Unit, 'Off', 0, 0)
                    elif Command == 'On':
                        SendCommandCloud(DeviceID, 'switch_' + str(Unit), True)
                        UpdateDevice(DeviceID, Unit, 'On', 1, 0)
                    elif Command == 'Set Level':
                        SendCommandCloud(DeviceID, 'switch_' + str(Unit), True)
                        UpdateDevice(DeviceID, Unit, Level, 1, 0)

            elif dev_type in ('dimmer'):
                if Command == 'Off':
                    SendCommandCloud(DeviceID, 'switch_led_' + str(Unit), False)
                    UpdateDevice(DeviceID, Unit, 'Off', 0, 0)
                elif Command == 'On':
                    SendCommandCloud(DeviceID, 'switch_led_' + str(Unit), True)
                    UpdateDevice(DeviceID, Unit, 'On', 1, 0)
                elif Command == 'Set Level':
                    SendCommandCloud(DeviceID, 'bright_value_' + str(Unit), Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)

            elif dev_type in ('light') or ((dev_type in ('fanlight') or dev_type in ('pirlight')) and Unit == 1):
                switch = 'led_switch' if searchCode('led_switch', function) else 'switch_led'
                if Command == 'Off':
                    SendCommandCloud(DeviceID, switch, False)
                    UpdateDevice(DeviceID, 1, 'Off', 0, 0)
                elif Command == 'On':
                    SendCommandCloud(DeviceID, switch, True)
                    UpdateDevice(DeviceID, 1, 'On', 1, 0)
                elif Command == 'Set Level':
                    if searchCode('bright_value_v2', function):
                        SendCommandCloud(DeviceID, switch, True)
                        SendCommandCloud(DeviceID, 'bright_value_v2', Level)
                    else:
                        SendCommandCloud(DeviceID, switch, True)
                        SendCommandCloud(DeviceID, 'bright_value', Level)
                    UpdateDevice(DeviceID, 1, Level, 1, 0)
                elif (Command == 'Set Color' or Command == 'Set Level') and len(Color) != 0:
                    if Color['m'] == 2:
                        SendCommandCloud(DeviceID, switch, True)
                        SendCommandCloud(DeviceID, 'work_mode', 'white')
                        if searchCode('bright_value_v2', function):
                            SendCommandCloud(DeviceID, 'bright_value_v2', Level)
                            SendCommandCloud(DeviceID, 'temp_value_v2', int(Color['t']))
                        else:
                            SendCommandCloud(DeviceID, 'bright_value', Level)
                            SendCommandCloud(DeviceID, 'temp_value', int(Color['t']))
                        UpdateDevice(DeviceID, 1, Level, 1, 0)
                        UpdateDevice(DeviceID, 1, Color, 1, 0)
                    # elif Color['m'] == 3:
                    #     if scalemode == 'v2':
                    #         h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                    #         hvs = {'h':h, 's':s, 'v':Level * 10}
                    #         SendCommandCloud(DeviceID, switch, True)
                    #         SendCommandCloud(DeviceID, 'colour_data', hvs)
                    #     else:
                    #         h, s, v = rgb_to_hsv(int(Color['r']), int(Color['g']), int(Color['b']))
                    #         hvs = {'h':h, 's':s, 'v':Level * 2.55}
                    #         SendCommandCloud(DeviceID, switch, True)
                    #         SendCommandCloud(DeviceID, 'colour_data', hvs)
                    #     UpdateDevice(DeviceID, 1, Level, 1, 0)
                    #     UpdateDevice(DeviceID, 1, Color, 1, 0)
                    elif Color['m'] == 3:
                        rgbcolor = format(rgb_temp(Color['r'], Level), '02x') + format(rgb_temp(Color['g'], Level), '02x') + format(rgb_temp(Color['b'], Level), '02x') + '0000ffff'
                        SendCommandCloud(DeviceID, switch, True)
                        SendCommandCloud(DeviceID, 'work_mode', 'colour')
                        if searchCode('colour_data_v2', function):
                            SendCommandCloud(DeviceID, 'colour_data_v2', rgbcolor)
                        else:
                            SendCommandCloud(DeviceID, 'colour_data', rgbcolor)
                        UpdateDevice(DeviceID, 1, Level, 1, 0)
                        UpdateDevice(DeviceID, 1, Color, 1, 0)

            if dev_type == ('cover'):
                if Command == 'Open':
                    if searchCode('mach_operate', function):
                        SendCommandCloud(DeviceID, 'mach_operate', 'FZ')
                    else:
                        SendCommandCloud(DeviceID, 'control', 'open')
                    UpdateDevice(DeviceID, 1, 'Open', 0, 0)
                elif Command == 'Close':
                    if searchCode('mach_operate', function):
                        SendCommandCloud(DeviceID, 'mach_operate', 'ZZ')
                    else:
                        SendCommandCloud(DeviceID, 'control', 'close')
                    UpdateDevice(DeviceID, 1, 'Close', 1, 0)
                elif Command == 'Stop':
                    if searchCode('mach_operate', function):
                        SendCommandCloud(DeviceID, 'mach_operate', 'STOP')
                    else:
                        SendCommandCloud(DeviceID, 'control', 'stop')
                    UpdateDevice(DeviceID, 1, 'Stop', 1, 0)
                elif Command == 'Set Level':
                    SendCommandCloud(DeviceID, 'position', Level)
                    UpdateDevice(DeviceID, 1, Level, 1, 0)

            elif dev_type == 'thermostat' or dev_type == 'heater'or dev_type == 'heatpump':
                if searchCode('switch_1', function):
                    switch = 'switch_1'
                else:
                    switch = 'switch'
                if searchCode('temp_set', function):
                    switch3 = 'temp_set'
                elif searchCode('set_temp', function):
                    switch3 = 'set_temp'
                elif searchCode('temperature_c', function):
                    switch3 = 'temperature_c'
                Domoticz.Debug('Debug switch Temp ' + str(switch))
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, switch, False)
                    UpdateDevice(DeviceID, 1, 'Off', 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, switch, True)
                    UpdateDevice(DeviceID, 1, 'On', 1, 0)
                elif Command == 'Set Level' and Unit  == 3:
                    SendCommandCloud(DeviceID, switch3, Level)
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 4, Level, 1, 0)
                if Command == 'Off' and Unit == 5:
                    SendCommandCloud(DeviceID, 'window_check', False)
                    UpdateDevice(DeviceID, 5, 'Off', 0, 0)
                elif Command == 'On' and Unit == 5:
                    SendCommandCloud(DeviceID, 'window_check', True)
                    UpdateDevice(DeviceID, 5, 'On', 1, 0)
                if Command == 'Off' and Unit == 6:
                    SendCommandCloud(DeviceID, 'child_lock', False)
                    UpdateDevice(DeviceID, 6, 'Off', 0, 0)
                elif Command == 'On' and Unit == 6:
                    SendCommandCloud(DeviceID, 'child_lock', True)
                    UpdateDevice(DeviceID, 6, 'On', 1, 0)
                if Command == 'Off' and Unit == 7:
                    SendCommandCloud(DeviceID, 'eco', False)
                    UpdateDevice(DeviceID, 7, 'Off', 0, 0)
                elif Command == 'On' and Unit == 7:
                    SendCommandCloud(DeviceID, 'eco', True)
                    UpdateDevice(DeviceID, 7, 'On', 1, 0)

            if dev_type == 'fan':
                if Command == 'Off':
                    SendCommandCloud(DeviceID, 'switch', False)
                    UpdateDevice(DeviceID, Unit, 'Off', 0, 0)
                elif Command == 'On':
                    SendCommandCloud(DeviceID, 'switch', True)
                    UpdateDevice(DeviceID, Unit, 'On', 1, 0)

            if dev_type == 'fanlight':
                if Command == 'Off' and Unit == 2:
                    SendCommandCloud(DeviceID, 'fan_switch', False)
                    UpdateDevice(DeviceID, 2, 'Off', 0, 0)
                elif Command == 'On' and Unit == 2:
                    SendCommandCloud(DeviceID, 'fan_switch', True)
                    UpdateDevice(DeviceID, 2, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'fan_speed', int(mode[int(Level / 10)]))
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'fan_direction', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 4, Level, 1, 0)

            if dev_type == 'siren':
                if Command == 'Off':
                    SendCommandCloud(DeviceID, 'AlarmSwitch', False)
                    UpdateDevice(DeviceID, Unit, 'Off', 0, 0)
                elif Command == 'On':
                    SendCommandCloud(DeviceID, 'AlarmSwitch', True)
                    UpdateDevice(DeviceID, Unit, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 2:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 2, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                # Other Type of alarm with same code
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'muffling', False)
                    UpdateDevice(DeviceID, 1, 'Off', 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'muffling', True)
                    UpdateDevice(DeviceID, 1, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 2:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'alarm_state', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 2, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'alarm_volume', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 3, Level, 1, 0)

            if dev_type == 'pirlight':
                if Command == 'Off' and Unit == 2:
                    SendCommandCloud(DeviceID, 'switch_pir', False)
                    UpdateDevice(DeviceID, 2, 'Off', 0, 0)
                elif Command == 'On' and Unit == 2:
                    SendCommandCloud(DeviceID, 'switch_pir', True)
                    UpdateDevice(DeviceID, 2, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'device_mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'pir_sensitivity', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 4, Level, 1, 0)

            if dev_type == 'garagedooropener':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch_1', False)
                    UpdateDevice(DeviceID, 1, 'Off', 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch_1', True)
                    UpdateDevice(DeviceID, 1, 'On', 1, 0)

            if dev_type == 'feeder':
                if Command == 'Off' and Unit == 5:
                    SendCommandCloud(DeviceID, 'light', False)
                    UpdateDevice(DeviceID, 5, 'Off', 0, 0)
                elif Command == 'On' and Unit == 5:
                    SendCommandCloud(DeviceID, 'light', True)
                    UpdateDevice(DeviceID, 5, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 1:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'manual_feed', int(mode[int(Level / 10)]))
                    UpdateDevice(DeviceID, 1, Level, 1, 0)

            if dev_type == 'irrigation':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', False)
                    UpdateDevice(DeviceID, 1, 'Off', 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', True)
                    UpdateDevice(DeviceID, 1, 'On', 1, 0)

            if dev_type == 'wswitch':
                if Command == 'Set Level':
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'switch' + str(Unit) +'_value', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)

            if dev_type == 'starlight':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch_led', False)
                    SendCommandCloud(DeviceID, 'colour_switch', False)
                    UpdateDevice(DeviceID, 1, 'Off', 0, 0)
                    UpdateDevice(DeviceID, 2, 'Off', 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch_led', True)
                    SendCommandCloud(DeviceID, 'colour_switch', True)
                    UpdateDevice(DeviceID, 1, 'On', 1, 0)
                    UpdateDevice(DeviceID, 2, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 1:
                    Color = Devices[DeviceID].Units[1].Color
                    if Color == '': Color ={"b":255,"cw":0,"g":255,"m":3,"r":255,"t":0,"ww":0}
                    h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                    hvs = {'h':h, 's':s, 'v':Level * 10}
                    SendCommandCloud(DeviceID, 'colour_data', hvs)
                    SendCommandCloud(DeviceID, 'colour_switch', True)
                    UpdateDevice(DeviceID, 1, Color, 1, 0)
                elif Command == 'Set Color' and Unit == 1: #
                    h, s, v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                    hvs = {'h':h, 's':s, 'v':Level * 10}
                    SendCommandCloud(DeviceID, 'colour_data', hvs)
                    SendCommandCloud(DeviceID, 'colour_switch', True)
                    UpdateDevice(DeviceID, 1, Color, 1, 0)
                if Command == 'Off' and Unit == 2:
                    SendCommandCloud(DeviceID, 'colour_switch', False)
                    UpdateDevice(DeviceID, 2, 'Off', 0, 0)
                    UpdateDevice(DeviceID, 1, 'Off', 0, 0)
                elif Command == 'On' and Unit == 2:
                    SendCommandCloud(DeviceID, 'colour_switch', True)
                    UpdateDevice(DeviceID, 2, 'On', 1, 0)
                    UpdateDevice(DeviceID, 1, 'On', 1, 0)
                if Command == 'Off' and Unit == 3:
                    SendCommandCloud(DeviceID, 'laser_switch', False)
                    UpdateDevice(DeviceID, 3, 'Off', 0, 0)
                elif Command == 'On' and Unit == 3:
                    SendCommandCloud(DeviceID, 'laser_switch', True)
                    UpdateDevice(DeviceID, 3, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    SendCommandCloud(DeviceID, 'laser_switch', True)
                    SendCommandCloud(DeviceID, 'laser_bright', 21.25 + ((Level / 100) * 78.75)) # 21.25 + ((Level / 100) * 78.75) ) * 10
                    UpdateDevice(DeviceID, 3, 'On', 1, 0)
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                if Command == 'Off' and Unit == 4:
                    SendCommandCloud(DeviceID, 'fan_switch', False)
                    UpdateDevice(DeviceID, 4, 'Off', 0, 0)
                elif Command == 'On' and Unit == 4:
                    SendCommandCloud(DeviceID, 'fan_switch', True)
                    UpdateDevice(DeviceID, 4, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    SendCommandCloud(DeviceID, 'fan_switch', True)
                    SendCommandCloud(DeviceID, 'fan_speed', Level)
                    UpdateDevice(DeviceID, 4, 'On', 1, 0)
                    UpdateDevice(DeviceID, 4, Level, 1, 0)

            # if dev_type == 'smartlock':
            #     if Command == 'Off' and Unit == 3:
            #         SendCommandCloud(DeviceID, 'switch', False)
            #         UpdateDevice(DeviceID, 1, 10, 0, 0)
            #     elif Command == 'On' and Unit == 3:
            #         SendCommandCloud(DeviceID, 'switch', True)
            #         UpdateDevice(DeviceID, 1, 0, 1, 0)

            if dev_type == 'dehumidifier':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', False)
                    UpdateDevice(DeviceID, Unit, 'Off', 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', True)
                    UpdateDevice(DeviceID, Unit, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 2:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'fan_speed_enum', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Off' and Unit == 5:
                    SendCommandCloud(DeviceID, 'switch', False)
                    UpdateDevice(DeviceID, Unit, 'Off', 0, 0)
                elif Command == 'On' and Unit == 5:
                    SendCommandCloud(DeviceID, 'switch', True)
                    UpdateDevice(DeviceID, Unit, 'On', 1, 0)

            if dev_type == 'vacuum':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'power_go', False)
                    UpdateDevice(DeviceID, Unit, 'Off', 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'power_go', True)
                    UpdateDevice(DeviceID, Unit, 'On', 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'suction', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 5:
                    mode = Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'cistern', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)


    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log('Notification: ' + Name + ', ' + Subject + ', ' + Text + ', ' + Status + ', ' + str(Priority) + ', ' + Sound + ', ' + ImageFile)

    def onDeviceRemoved(self, DeviceID, Unit):
        Domoticz.Log('onDeviceDeleted called')

    def onDisconnect(self, Connection):
        Domoticz.Log('onDisconnect called')

    def onHeartbeat(self):
        Domoticz.Debug('onHeartbeat called')
        if time.time() - last_update < 60 and testData == False:
            Domoticz.Debug("onHeartbeat called skipped")
            return
        Domoticz.Debug("onHeartbeat called last run: " + str(time.time() - last_update))
        if testData == False:
            if Error is not None:
                Domoticz.Error(Error['Payload'])
            else:
                onHandleThread(False)
        else:
            onHandleThread(False)

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

def onHandleThread(startup):
    # Run for every device on startup and heartbeat
    try:
        if startup == True:
            global tuya
            global devs
            global properties
            global ResultValue
            global FunctionProperties
            global StatusProperties
            global Error
            global scan
            global last_update
            global product_id
            global t
            last_update = time.time()
            if testData == True:
                tuya = Domoticz.Log
                with open(Parameters['HomeFolder'] + '/debug_devices.json') as dFile:
                    devs = json.load(dFile)
                token = 'Fake'
                Error = None
                properties = {}
                with open(Parameters['HomeFolder'] + '/debug_functions.json') as fFile:
                    for dev in devs:
                        properties[dev['id']] = json.load(fFile)['result']
                        try:
                            properties[dev['id']]['functions']
                        except:
                            properties[dev['id']]['functions'] = []
                            Domoticz.Error('!! Warning Functions data is missing !!')
                        try:
                            properties[dev['id']]['status']
                        except:
                            properties[dev['id']]['status'] = []
                            Domoticz.Error('!! Warning Status data is missing !!')
                # Domoticz.Debug(properties[dev['id']])

            else:
                # if version(tinytuya.version) >= version('1.11.0'):
                #     tuya = tinytuya.Cloud(apiRegion=Parameters['Mode1'], apiKey=Parameters['Username'], apiSecret=Parameters['Password'])
                # else:
                tuya = tinytuya.Cloud(apiRegion=Parameters['Mode1'], apiKey=Parameters['Username'], apiSecret=Parameters['Password'], apiDeviceID=Parameters['Mode2'])
                tuya.use_old_device_list = True
                tuya.new_sign_algorithm = True
                Error = tuya.error

                if Error is not None:
                    raise Exception(Error['Payload'])
                devs = []
                i = 0
                while len(devs) == 0 and i < 4:
                    devs = tuya.getdevices()
                    Domoticz.Log('No device data returned for Tuya. Trying again!')
                    i += 1
                if i > 4:
                    raise Exception('No device data returned for Tuya. Check if subscription cloud development plan has expired!')
                token = tuya.token

                # # Check credentials
                # if 'sign invalid' in str(devs) or token == None:
                #     login = False
                #     raise Exception('Credentials are incorrect!')

                # # Check ID search device is valid
                # if 'permission deny' in str(devs):
                #     login = False
                #     raise Exception('ID search device not found!')

                properties = {}
                for dev in devs:
                    properties[dev['id']] = tuya.getproperties(dev['id'])['result']
                    try:
                        properties[dev['id']]['functions']
                    except:
                        properties[dev['id']]['functions'] = []
                    try:
                        properties[dev['id']]['status']
                    except:
                        properties[dev['id']]['status'] = []

            Domoticz.Log('Scanning for tuya devices on network...')
            if testData == False:
                scan = tinytuya.deviceScan(verbose=False, maxretry=None, byID=True)

        # Initialize/Update devices from TUYA API
        run = 0
        for dev in devs:
            run += 1
            Domoticz.Debug( 'Device name=' + str(dev['name']) + ' id=' + str(dev['id']) + ' category=' + str(DeviceType(dev['category'])))
            try:
                last_update = time.time()
                if testData == True:
                    online = True
                else:
                    online = tuya.getconnectstatus(dev['id'])
                # Set last update
                FunctionProperties = properties[dev['id']]['functions']
                dev_type = DeviceType(properties[dev['id']]['category'])
                StatusProperties = properties[dev['id']]['status']
            except:
                raise Exception('Credentials are incorrect or tuya subscription has expired!')
                return
            if testData == True:
                with open(Parameters['HomeFolder'] + '/debug_result.json') as rFile:
                    rData = json.load(rFile)
                    ResultValue = rData['result']
                    t = rData['t']
            else:
                ResultValue = tuya.getstatus(dev['id'])['result']
                t = tuya.getstatus(dev['id'])['t']

            product_id = getConfigItem(dev['id'],'product_id')
            # Define scale mode
            # if '_v2' in str(FunctionProperties):
            #     scalemode = 'v2'
            # else:
            #     scalemode = 'v1'
            # Domoticz.Debug( 'functions= ' + str(functions))
            # Domoticz.Debug( 'Device name= ' + str(dev['name']) + ' id= ' + str(dev['id']) + ' result= ' + ResultValue)
            # Domoticz.Debug( 'Device name= ' + str(dev['name']) + ' id= ' + str(dev['id']) + ' FunctionProperties= ' + str(properties[dev['id']]))

            # Create devices
            if startup == True:
                if run == 1:
                    Domoticz.Debug('Run Startup script')
                try:
                    deviceinfo = scan[dev['id']]
                except:
                    deviceinfo = {'ip': None, 'version': 3.3}

                if dev_type in ('light', 'fanlight', 'pirlight') and createDevice(dev['id'], 1):
                    # for localcontol: and deviceinfo['ip'] != None
                    if (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (searchCode('temp_value', StatusProperties) or searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        Domoticz.Log('Create device Light RGBWW')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=4, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and 'dc' == str(properties[dev['id']]['category']) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)):
                        Domoticz.Log('Create device Light Stringlight')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=4, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        Domoticz.Log('Create device Light RGBW')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=1, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        Domoticz.Log('Create device Light RGB')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=2, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (searchCode('temp_value', StatusProperties) or searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        Domoticz.Log('Create device Light WWCW')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=8, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (searchCode('bright_value', StatusProperties) or searchCode('bright_value_v2', StatusProperties)):
                        Domoticz.Log('Create device Light Dimmer')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)) and not searchCode('work_mode', StatusProperties) and not (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)) and (not searchCode('temp_value', StatusProperties) or not searchCode('temp_value_v2', StatusProperties)) and (not searchCode('bright_value', StatusProperties) or not searchCode('bright_value_v2', StatusProperties)):
                        Domoticz.Log('Create device Light On/Off')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=7, Used=1).Create()
                    else:
                        Domoticz.Log('Create device Light On/Off (Unknown Light Device)')
                        Domoticz.Unit(Name=dev['name'] + ' (Unknown Light Device)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=7, Used=1).Create()

                if dev_type == 'dimmer':
                    if  createDevice(dev['id'], 1) and searchCode('switch_led_1', FunctionProperties) and not searchCode('switch_led_2', FunctionProperties):
                        Domoticz.Log('Create device Dimmer')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                    if searchCode('switch_led_2', FunctionProperties):
                        if createDevice(dev['id'], 1):
                            Domoticz.Unit(Name=dev['name'] + ' (Dimmer 1)', DeviceID=dev['id'], Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                        if createDevice(dev['id'], 2):
                            Domoticz.Unit(Name=dev['name'] + ' (Dimmer 2)', DeviceID=dev['id'], Unit=2, Type=241, Subtype=3, Switchtype=7, Used=1).Create()

                if dev_type == 'switch':
                    if  createDevice(dev['id'], 1) and (searchCode('switch_1', FunctionProperties) or searchCode('switch', FunctionProperties)) and not searchCode('switch_2', FunctionProperties):
                        Domoticz.Log('Create device Switch')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if searchCode('switch_2', FunctionProperties):
                        Domoticz.Log('Create device Switch')
                        if createDevice(dev['id'], 1):
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 1)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 2):
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 2)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('switch_3', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 3)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('switch_4', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 4)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('switch_5', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 5)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 11) and ((searchCode('cur_current', ResultValue) and get_unit('cur_current', StatusProperties) == 'A') or searchCode('phase_a', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 12) and (searchCode('cur_power', ResultValue) or searchCode('phase_a', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (W)', DeviceID=dev['id'], Unit=12, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 13) and (searchCode('cur_voltage', ResultValue) or searchCode('phase_a', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=13, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 14) and (searchCode('cur_power', ResultValue) or searchCode('phase_a', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=29, Used=1).Create()
                        #UpdateDevice(dev['id'], 14, '0;0', 0, 0, 1)
                    if createDevice(dev['id'], 15) and (searchCode('cur_current', ResultValue) and get_unit('cur_current', StatusProperties) == 'mA' or searchCode('leakage_current', ResultValue)):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' (mA)', DeviceID=dev['id'], Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 16) and searchCode('temp_current', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=16, Type=80, Subtype=5, Used=1).Create()

                if dev_type == 'cover' and createDevice(dev['id'], 1):
                    Domoticz.Log('Create device Cover')
                    if searchCode('position', StatusProperties):
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=21, Used=1).Create()
                    else:
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=14, Used=1).Create()

                if dev_type == 'thermostat' or dev_type == 'heater' or dev_type == 'heatpump':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Thermostat/heater/heatpump')
                        if searchCode('switch', FunctionProperties) or searchCode('switch_1', FunctionProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        else:
                            Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=0).Create()
                    if searchCode('set_temp', FunctionProperties) or searchCode('temp_set', FunctionProperties) or searchCode('temperature_c', FunctionProperties):
                        if createDevice(dev['id'], 2):
                            Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=2, Type=80, Subtype=5, Used=1).Create()
                        if createDevice(dev['id'], 3):
                            Domoticz.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev['id'], Unit=3, Type=242, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('mode', FunctionProperties) and product_id != 'al8g1qdamyu5cfcc':
                        if dev_type == 'thermostat':
                            image = 16
                        elif dev_type == 'heater':
                            image = 15
                        else:
                            image = 7
                        for item in FunctionProperties:
                            if searchCode('work_mode', FunctionProperties):
                                mode = 'work_mode'
                            else:
                                mode = 'mode'
                            if item['code'] == mode:
                                # if product_id == 'al8g1qdamyu5cfcc':
                                #     options = {}
                                #     options['LevelOffHidden'] = 'true'
                                #     options['LevelActions'] = ''
                                #     options['LevelNames'] = 'off|auto|a_silent|a_powerful|heat|h_powerful|h_silent|cool|c_powerful|c_silent'
                                #     options['SelectorStyle'] = '1'
                                # else:
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=image, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('window_check', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Window check)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('child_lock', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Child lock)', DeviceID=dev['id'], Unit=6, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('child_lock', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Eco)', DeviceID=dev['id'], Unit=7, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 11) and ((searchCode('cur_current', ResultValue) and get_unit('cur_current', StatusProperties) == 'A') or searchCode('phase_a', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 12) and (searchCode('cur_power', ResultValue) or searchCode('phase_a', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (W)', DeviceID=dev['id'], Unit=12, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 13) and (searchCode('cur_voltage', ResultValue) or searchCode('phase_a', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=13, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 14) and (searchCode('cur_power', ResultValue) or searchCode('phase_a', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=29, Used=1).Create()
                        #UpdateDevice(dev['id'], 14, '0;0', 0, 0, 1)
                    if createDevice(dev['id'], 15) and (searchCode('cur_current', ResultValue) and get_unit('cur_current', StatusProperties) == 'mA' or searchCode('leakage_current', ResultValue)):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' (mA)', DeviceID=dev['id'], Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()

                if dev_type in ('temperaturehumiditysensor', 'smartir'):
                    Domoticz.Log('Create device T&H Sensor')
                    if createDevice(dev['id'], 1) and (searchCode('va_temperature', ResultValue) or searchCode('temp_current', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=1, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev['id'], 2) and (searchCode('va_humidity', ResultValue) or searchCode('humidity_value', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev['id'], Unit=2, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 3) and ((searchCode('va_temperature', ResultValue) and searchCode('va_humidity', ResultValue)) or (searchCode('temp_current', ResultValue) and searchCode('humidity_value', ResultValue))):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev['id'], Unit=3, Type=82, Subtype=5, Used=1).Create()

                if createDevice(dev['id'], 1) and dev_type == 'doorbell':
                    if searchCode('basic_indicator', FunctionProperties):
                        Domoticz.Log('Create device Doorbell')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create() # Switchtype=1 is doorbell

                if dev_type == 'fan':
                    if createDevice(dev['id'], 1) and searchCode('switch', FunctionProperties):
                        Domoticz.Log('Create device Fan')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()

                if dev_type == 'fanlight':
                    if createDevice(dev['id'], 2) and searchCode('fan_switch', FunctionProperties):
                        Domoticz.Log('Create device Fanlight')
                        Domoticz.Unit(Name=dev['name'] + ' (Fan Power)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('fan_speed', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'fan_speed':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Fan Speed)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('fan_direction', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'fan_direction':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Fan Direction)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()

                if dev_type == 'siren':
                    if createDevice(dev['id'], 1) and searchCode('AlarmSwitch', FunctionProperties):
                        Domoticz.Log('Create device Siren')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('Alarmtype', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'Alarmtype':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '1'
                                Domoticz.Unit(Name=dev['name'] + ' (Alarmtype)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=8, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('AlarmPeriod', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'AlarmPeriod':
                                the_values = json.loads(item['values'])
                                mode = []
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'false'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '1'
                                Domoticz.Unit(Name=dev['name'] + ' (AlarmPeriod)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    # Other type of alarm with same code
                    if createDevice(dev['id'], 1) and searchCode('muffling', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Muffling)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=8, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('alarm_state', FunctionProperties):
                        Domoticz.Log('Create device Siren')
                        for item in FunctionProperties:
                            if item['code'] == 'alarm_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '1'
                                Domoticz.Unit(Name=dev['name'] + ' (State)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('alarm_volume', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'alarm_volume':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '1'
                                Domoticz.Unit(Name=dev['name'] + ' (Volume)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=8, Used=1).Create()

                if dev_type == 'powermeter':
                    if createDevice(dev['id'], 1) and searchCode('Current', ResultValue):
                        Domoticz.Log('Create device Powermeter')
                        Domoticz.Unit(Name=dev['name'] + ' (3P A)', DeviceID=dev['id'], Unit=1, Type=89, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('Current', ResultValue):
                        options = {}
                        options['Custom'] = '1;Hz'
                        Domoticz.Unit(Name=dev['name'] + ' (Hz)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('Temperature', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=3, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('Current', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=4, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('ActivePower', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 11) and searchCode('ActivePowerA', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' L1 (V)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 12) and searchCode('ActivePowerA', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' L1 (kWh)', DeviceID=dev['id'], Unit=12, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 21) and searchCode('ActivePowerB', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' L2 (V)', DeviceID=dev['id'], Unit=21, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 22) and searchCode('ActivePowerB', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' L2 (kWh)', DeviceID=dev['id'], Unit=22, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 31) and searchCode('ActivePowerC', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' L3 (V)', DeviceID=dev['id'], Unit=31, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 32) and searchCode('ActivePowerC', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' L3 (kWh)', DeviceID=dev['id'], Unit=32, Type=243, Subtype=29, Used=1).Create()

                if dev_type == 'powermeter':
                    if createDevice(dev['id'], 1) and searchCode('phase_a', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=1, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('phase_a', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (W)', DeviceID=dev['id'], Unit=2, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('phase_a', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=3, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('phase_a', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=4, Type=243, Subtype=29, Used=1).Create()

                if dev_type == 'powermeter' and searchCode('direction_a', ResultValue):
                    if createDevice(dev['id'], 1) and searchCode('voltage_a', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=1, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('freq', ResultValue):
                        options = {}
                        options['Custom'] = '1;Hz'
                        Domoticz.Unit(Name=dev['name'] + ' (Hz)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('total_power', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' Total (W)', DeviceID=dev['id'], Unit=3, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 11) and searchCode('power_a', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' A (W)', DeviceID=dev['id'], Unit=11, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 12) and searchCode('current_a', ResultValue):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' A (mA)', DeviceID=dev['id'], Unit=12, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 13) and searchCode('direction_a', ResultValue):
                        Domoticz.Unit(Name=dev['name']+ ' A (Direction)', DeviceID=dev['id'], Unit=13, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 14) and searchCode('energy_forword_a', ResultValue):
                        # Domoticz.Unit(Name=dev['name'] + ' A Forward (kWh)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' A Forward (kWh)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 15) and searchCode('energy_reverse_a', ResultValue):
                        # Domoticz.Unit(Name=dev['name'] + ' A Reverse (kWh)', DeviceID=dev['id'], Unit=15, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' A Reverse (kWh)', DeviceID=dev['id'], Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 21) and searchCode('power_b', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' B (W)', DeviceID=dev['id'], Unit=21, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 22) and searchCode('current_b', ResultValue):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' B (mA)', DeviceID=dev['id'], Unit=22, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 23) and searchCode('direction_b', ResultValue):
                        Domoticz.Unit(Name=dev['name']+ ' B (Direction)', DeviceID=dev['id'], Unit=23, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 24) and searchCode('energy_forword_b', ResultValue):
                        # Domoticz.Unit(Name=dev['name'] + ' B Forward (kWh)', DeviceID=dev['id'], Unit=24, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' B Forward (kWh)', DeviceID=dev['id'], Unit=24, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 25) and searchCode('energy_reserse_b', ResultValue):
                        # Domoticz.Unit(Name=dev['name'] + ' B Reverse (kWh)', DeviceID=dev['id'], Unit=25, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' B Reverse (kWh)', DeviceID=dev['id'], Unit=25, Type=243, Subtype=31, Options=options, Used=1).Create()

                if dev_type == 'gateway':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Gateway')
                        if searchCode('master_state', ResultValue):
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=1).Create()
                        else:
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=0).Create()

                if dev_type == ('co2sensor'):
                    if createDevice(dev['id'], 1) and searchCode('temp_current', ResultValue):
                        Domoticz.Log('Create device co2 Sensor')
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=1, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev['id'], 2) and searchCode('humidity_value', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev['id'], Unit=2, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 3) and searchCode('temp_current', ResultValue) and searchCode('humidity_value', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev['id'], Unit=3, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('co2_value', ResultValue):
                        options = {}
                        options['Custom'] = '1;ppm'
                        Domoticz.Unit(Name=dev['name'] + ' (CO2)', DeviceID=dev['id'], Unit=4, Type=243, Subtype=31, Options=options, Used=1).Create()

                if dev_type == 'doorcontact':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Doorcontact')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                if dev_type == 'pirlight':
                    if createDevice(dev['id'], 2) and searchCode('switch_pir', FunctionProperties):
                        Domoticz.Log('Create device Pirlight')
                        Domoticz.Unit(Name=dev['name'] + ' (Pir State)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=8, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('device_mode', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'device_mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('pir_sensitivity', FunctionProperties):
                        for item in FunctionProperties:
                            if item['code'] == 'pir_sensitivity':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Sensitivity)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'smokedetector':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Smokedetector')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=5, Used=1).Create()
                        Domoticz.Unit(Name=dev['name'] + ' (Alarm)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=19, Used=1).Create()

                if dev_type == 'garagedooropener':
                    if createDevice(dev['id'], 1) and searchCode('switch_1', FunctionProperties):
                        Domoticz.Log('Create device Garage door opener')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=5, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('doorcontact_state', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (Contact state)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('door_control_1', ResultValue):
                        Domoticz.Unit(Name=dev['name'] + ' (State)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                if dev_type == 'feeder':
                    if createDevice(dev['id'], 1) and searchCode('manual_feed', FunctionProperties):
                        Domoticz.Log('Create device Feeder')
                        for item in FunctionProperties:
                            if item['code'] == 'manual_feed':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '1'
                                Domoticz.Unit(Name=dev['name'] + ' (Manual)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('feed_state', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'feed_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('feed_report', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'feed_report':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '1'
                                Domoticz.Unit(Name=dev['name'] + ' (Report)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('light', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Light)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Used=1).Create()

                if dev_type == 'waterleak':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device water leak sesor')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                if dev_type == 'presence':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device PIR sensor')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Used=1).Create()

                if dev_type == 'irrigation':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Irrigation')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('work_state', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'work_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=22, Used=1).Create()

                if dev_type == 'wswitch':
                    # if createDevice(dev['id'], 1) and searchCode('switch1_value', StatusProperties):
                    #     Domoticz.Unit(Name=dev['name'] + ' single click (Switch 1)', DeviceID=dev['id'], Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    #     Domoticz.Unit(Name=dev['name'] + ' double click (Switch 1)', DeviceID=dev['id'], Unit=12, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    #     Domoticz.Unit(Name=dev['name'] + ' long press (Switch 1)', DeviceID=dev['id'], Unit=13, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    for x in range(1, 9):
                        if createDevice(dev['id'], x) and searchCode('switch' + str(x) + '_value', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'switch' + str(x) + '_value':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    options['SelectorStyle'] = '0'
                                    Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'lightsensor':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device light sensor')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=246, Subtype=1, Switchtype=11, Used=1).Create()

                if dev_type == 'starlight':
                    if createDevice(dev['id'], 1) and searchCode('switch_led', FunctionProperties):
                        Domoticz.Log('Create device Starlight')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=2, Switchtype=7, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('colour_switch', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Colour)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('laser_switch', FunctionProperties) and searchCode('laser_bright', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Laser)', DeviceID=dev['id'], Unit=3, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('fan_switch', FunctionProperties) and searchCode('fan_speed', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Fan)', DeviceID=dev['id'], Unit=4, Type=241, Subtype=3, Switchtype=7, Image=7, Used=1).Create()

                if dev_type == 'smartlock':
                    if createDevice(dev['id'], 1) and searchCode('lock_motor_state', StatusProperties):
                        Domoticz.Log('Create device smart lock')
                        Domoticz.Unit(Name=dev['name'] + ('State'), DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                    # if createDevice(dev['id'], 3):
                    #     Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=19, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('alarm_lock', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'alarm_lock':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=13, Used=1).Create()

                if dev_type == 'dehumidifier':
                    if createDevice(dev['id'], 1) and searchCode('switch', FunctionProperties):
                        Domoticz.Log('Create device Dehumidifier')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('dehumidify_set_value', FunctionProperties):
                        Domoticz.Log('Create device Feeder')
                        for item in FunctionProperties:
                            if item['code'] == 'dehumidify_set_value':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '1'
                                Domoticz.Unit(Name=dev['name'] + ' (dehumidify)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=11, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('fan_speed_enum', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'fan_speed_enum':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (fan speed)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (mode)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('anion', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (anion)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 6) and (searchCode('temp_indoor', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=6, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev['id'], 7) and (searchCode('humidity_indoor', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev['id'], Unit=7, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 8) and ((searchCode('temp_indoor', ResultValue) and searchCode('humidity_indoor', ResultValue))):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev['id'], Unit=8, Type=82, Subtype=5, Used=1).Create()

                if dev_type == 'vacuum':
                    if createDevice(dev['id'], 1) and searchCode('power_go', FunctionProperties):
                        Domoticz.Log('Create device Robot vacuum')
                        Domoticz.Unit(Name=dev['name'] + ' Running', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('switch_charge', FunctionProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Charge)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create() #Image=7,
                    if createDevice(dev['id'], 4) and searchCode('suction', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'suction':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Suction)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('cistern', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'cistern':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0'
                                Domoticz.Unit(Name=dev['name'] + ' (Cistern)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('status', ResultValue):
                            Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=6, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('electricity_left', ResultValue):
                            Domoticz.Unit(Name=dev['name'] + ' (Electricity left)', DeviceID=dev['id'], Unit=7, Type=243, Subtype=6, Used=1).Create()
                    if createDevice(dev['id'], 8) and searchCode('edge_brush', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hour'
                        Domoticz.Unit(Name=dev['name'] + ' (Edge brush))', DeviceID=dev['id'], Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 9) and searchCode('roll_brush', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hour'
                        Domoticz.Unit(Name=dev['name'] + ' (Roll brush))', DeviceID=dev['id'], Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 10) and searchCode('filter', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hour'
                        Domoticz.Unit(Name=dev['name'] + ' (Filter))', DeviceID=dev['id'], Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 11) and searchCode('fault', ResultValue):
                            Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=19, Used=1).Create()

                if dev_type == 'infrared':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Infrared device: ' + str(dev['name']))
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=0).Create()
                        UpdateDevice(dev['id'], 1, 'Infrared devices are not able to contoled by the plugin (yet)', 0, 0)

                if createDevice(dev['id'], 1):
                    Domoticz.Log('No controls found for device: ' + str(dev['name']))
                    Domoticz.Unit(Name=dev['name'] + ' (Unknown Device)', DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=1).Create()
                    UpdateDevice(dev['id'], 1, 'This device is not reconised, edit and run the debug_discovery with python from the tools directory and receate a issue report at https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/issues so the device can be added.', 0, 0)

                # Set extra info
                setConfigItem(dev['id'], {'key': dev['key'], 'category': dev_type, 'mac': dev['mac'], 'ip': deviceinfo['ip'], 'product_id': dev['product_id'], 'version': deviceinfo['version']})  #, 'scalemode': scalemode})
                # Domoticz.Debug('ConfigItem:' + str(getConfigItem()))

            # Check device is removed
            if dev['id'] not in str(Devices) or len(Devices) == 0:
                raise Exception('Device not found in Domoticz! Device is removed or Accept New Hardware not enabled?')

            #update devices in Domoticz
            if run == 1:
                Domoticz.Log('Update devices in Domoticz')
            if bool(online) == False and Devices[dev['id']].TimedOut == 0:
                UpdateDevice(dev['id'], 1, 'Off', 0, 1)
            elif online == True and Devices[dev['id']].TimedOut == 1:
                UpdateDevice(dev['id'], 1, None, 0, 0)
            elif bool(online) == True and Devices[dev['id']].TimedOut == 0:
                try:
                    # status Domoticz
                    sValue = Devices[dev['id']].Units[1].sValue
                    nValue = Devices[dev['id']].Units[1].nValue
                    product_id = getConfigItem(dev['id'],'product_id')

                    if dev_type == 'switch':
                        if searchCode('switch_1', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch_1')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        elif searchCode('switch', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)

                        if searchCode('switch_2', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch_2')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 2, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 2, 'On', 1, 0)

                        if searchCode('switch_3', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch_3')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 3, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 3, 'On', 1, 0)

                        if searchCode('switch_4', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch_4')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 4, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 4, 'On', 1, 0)

                        if searchCode('switch_5', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch_5')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 5, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 5, 'On', 1, 0)

                        if searchCode('cur_current', ResultValue):
                            currentcurrent = StatusDeviceTuya('cur_current')
                            currentpower = StatusDeviceTuya('cur_power')
                            currentvoltage = StatusDeviceTuya('cur_voltage')

                            if get_unit('cur_current', StatusProperties) == 'mA':
                                UpdateDevice(dev['id'], 15, str(currentcurrent), 0, 0)
                            else:
                                UpdateDevice(dev['id'], 11, str(currentcurrent), 0, 0)

                            UpdateDevice(dev['id'], 12, str(currentpower), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[14].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev['id']].Units[14].sValue if len(Devices[dev['id']].Units[14].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 14, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)

                            UpdateDevice(dev['id'], 13, str(currentvoltage), 0, 0)

                        if searchCode('phase_a', ResultValue):
                            base64_string = StatusDeviceTuya('phase_a')
                            # Decode base64 string
                            decoded_data = base64.b64decode(base64_string)

                            # Extract voltage, current, and power data
                            currentvoltage = int.from_bytes(decoded_data[:2], byteorder='big') * 0.1
                            currentcurrent = int.from_bytes(decoded_data[2:5], byteorder='big') * 0.001
                            currentpower = int.from_bytes(decoded_data[5:8], byteorder='big')
                            leakagecurrent = StatusDeviceTuya('leakage_current')
                            UpdateDevice(dev['id'], 11, str(currentcurrent), 0, 0)
                            UpdateDevice(dev['id'], 12, str(currentpower), 0, 0)
                            UpdateDevice(dev['id'], 13, str(currentvoltage), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[14].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev['id']].Units[14].sValue if len(Devices[dev['id']].Units[14].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 14, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)
                            UpdateDevice(dev['id'], 15, str(leakagecurrent), 0, 0)
                        if searchCode('temp_current', ResultValue):
                            currenttemp = StatusDeviceTuya('temp_current')
                            if str(currenttemp) != str(Devices[dev['id']].Units[16].sValue):
                                UpdateDevice(dev['id'], 16, currenttemp, 0, 0)

                    if dev_type == 'dimmer':
                        if searchCode('switch_led_1', StatusProperties):
                            currentstatus = StatusDeviceTuya('switch_led_1')
                            currentdim = brightness_to_pct(StatusProperties, 'bright_value_1', int(StatusDeviceTuya('bright_value_1')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True and  currentdim > 0 and str(currentdim) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, currentdim, 1, 0)

                        if searchCode('switch_led_2', StatusProperties):
                            currentstatus = StatusDeviceTuya('switch_led_2')
                            currentdim = brightness_to_pct(StatusProperties, 'bright_value_2', int(StatusDeviceTuya('bright_value_2')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDevice(dev['id'], 2, 'Off', 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, currentdim, 1, 0)

                    if dev_type in ('light','fanlight'):
                        if searchCode('switch_led', StatusProperties):
                            currentstatus = StatusDeviceTuya('switch_led')
                        else:
                            currentstatus = StatusDeviceTuya('led_switch')
                        if bool(currentstatus) == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif bool(currentstatus) == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        workmode = StatusDeviceTuya('work_mode')
                        BrightnessControl = False
                        if searchCode('bright_value', StatusProperties):
                            BrightnessControl = True
                            dimtuya = brightness_to_pct(StatusProperties, 'bright_value', int(StatusDeviceTuya('bright_value')))
                        elif searchCode('bright_value_v2', StatusProperties):
                            BrightnessControl = True
                            dimtuya = brightness_to_pct(StatusProperties, 'bright_value_v2', int(StatusDeviceTuya('bright_value_v2')))
                        dimlevel = Devices[dev['id']].Units[1].sValue
                        if (searchCode('colour_data', StatusProperties) or searchCode('colour_data_v2', StatusProperties)):
                            if searchCode('colour_data', StatusProperties):
                                colortuya = StatusDeviceTuya('colour_data')
                            else:
                                colortuya = StatusDeviceTuya('colour_data_v2')
                        if BrightnessControl == False:
                            if (bool(currentstatus) == False and bool(nValue) != False):
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif (bool(currentstatus) == True and bool(nValue) != True):
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if BrightnessControl == True:
                            if (bool(currentstatus) == False and bool(nValue) != False) or (int(dimtuya) == 0 and bool(nValue) != False):
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif (bool(currentstatus) == True and bool(nValue) != True) or (str(dimtuya) != str(sValue) and bool(nValue) != False):
                                UpdateDevice(dev['id'], 1, dimtuya, 1, 0)

                        if currentstatus == True and workmode == 'white':
                            if searchCode('temp_value', StatusProperties):
                                color = ast.literal_eval(Devices[dev['id']].Units[1].Color)
                                temptuya = {'b':0,'cw':0,'g':0,'m':2,'r':0,'t':int(inv_val(round(StatusDeviceTuya('temp_value')))),'ww':0}
                                # Domoticz.Debug(temptuya['t'])
                                # Domoticz.Debug(color['t'])
                                Domoticz.Debug('temptuya: ' + str(temptuya))
                                if int((temptuya['t'])) != int(color['t']):
                                    # Domoticz.Debug(str((temptuya['t'])) + ' ' + str(color['t']))
                                    UpdateDevice(dev['id'], 1, dimtuya, 1, 0)
                                    UpdateDevice(dev['id'], 1, temptuya, 1, 0)

                        if currentstatus == True and workmode == 'colour':
                            Domoticz.Debug('Colordata = ' + str(Devices[dev['id']].Units[1].Color))
                            Domoticz.Debug('Tuya colour_data = ' + str(StatusDeviceTuya('colour_data')))
                            if len(Devices[dev['id']].Units[1].Color) != 0:
                                color = ast.literal_eval(Devices[dev['id']].Units[1].Color)
                                Domoticz.Debug('Colordata = ' + str(color))
                                if searchCode('colour_data_v2', StatusProperties):
                                    # colorupdate = {'r':int('0x' + colortuya[0:-12],0),'g':int('0x' + colortuya[2:-10],0),'b':int('0x' + colortuya[4:-8],0)}
                                    h,s,level = rgb_to_hsv_v2(int('0x' + colortuya[0:-12],0),int('0x' + colortuya[2:-10],0),int('0x' + colortuya[4:-8],0))
                                    r,g,b = hsv_to_rgb_v2(h, s, 1000)
                                else:
                                    # colorupdate = {'r':int('0x' + colortuya[0:-12],0),'g':int('0x' + colortuya[2:-10],0),'b':int('0x' + colortuya[4:-8],0)}
                                    h,s,level = rgb_to_hsv(int('0x' + colortuya[0:-12],0),int('0x' + colortuya[2:-10],0),int('0x' + colortuya[4:-8],0))
                                    r,g,b = hsv_to_rgb(h, s, 100)
                                colorupdate = {'b':b,'cw':0,'g':g,'m':3,'r':r,'t':0,'ww':0}
                                Domoticz.Debug('levelupdate: ' + str(level))
                                Domoticz.Debug('Colorupdate = ' + str(colorupdate))
                                # {"b":0,"cw":0,"g":3,"m":3,"r":255,"t":0,"ww":0}
                                if (color['r'] != r or color['g'] != g or color['b'] != b ) or len(Devices[dev['id']].Units[1].Color) == 0:
                                    Domoticz.Debug('Colorupdate = ' + str(colorupdate))
                                    UpdateDevice(dev['id'], 1, colorupdate, 1, 0)
                                    UpdateDevice(dev['id'], 1, brightness_to_pct(StatusProperties, 'bright_value', int(inv_val(level))), 1, 0)
                            else:
                                color = {}

                    if dev_type == 'cover':
                        if searchCode('position', StatusProperties):
                            currentposition = StatusDeviceTuya('position')
                            if str(currentposition) == '0':
                                UpdateDevice(dev['id'], 1, currentposition, 1, 0)
                            if str(currentposition) == '100':
                                UpdateDevice(dev['id'], 1, currentposition, 0, 0)
                            if str(currentposition) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, currentposition, 2, 0)
                        if searchCode('mach_operate', StatusProperties):
                            currentstatus = StatusDeviceTuya('control')
                            if currentstatus == 'close':
                                UpdateDevice(dev['id'], 1, 'ZZ', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDevice(dev['id'], 1, 'FZ', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDevice(dev['id'], 1, 'STOP', 1, 0)
                        if searchCode('control', StatusProperties):
                            currentstatus = StatusDeviceTuya('control')
                            if currentstatus == 'close':
                                UpdateDevice(dev['id'], 1, 'Open', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDevice(dev['id'], 1, 'Close', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDevice(dev['id'], 1, 'Stop', 1, 0)

                    if dev_type == 'thermostat' or dev_type == 'heater' or dev_type == 'heatpump':
                        if searchCode('switch', ResultValue):
                            currentstatus = StatusDeviceTuya('switch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if searchCode('temp_current', ResultValue) or searchCode('upper_temp', ResultValue) or searchCode('c_temperature', ResultValue):
                            if searchCode('temp_current', ResultValue):
                                currenttemp = StatusDeviceTuya('temp_current')
                            elif searchCode('upper_temp', ResultValue):
                                currenttemp = StatusDeviceTuya('upper_temp')
                            elif searchCode('c_temperature', ResultValue):
                                currenttemp = StatusDeviceTuya('c_temperature')
                            else:
                                currenttemp = 0
                            if str(currenttemp) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, currenttemp, 0, 0)
                        if searchCode('temp_set', ResultValue) or searchCode('set_temp', ResultValue) or searchCode('temperature_c', ResultValue):
                            if searchCode('temp_set', ResultValue):
                                currenttemp_set = StatusDeviceTuya('temp_set')
                            elif searchCode('set_temp', ResultValue):
                                currenttemp_set = StatusDeviceTuya('set_temp')
                            elif searchCode('temperature_c', ResultValue):
                                currenttemp_set = StatusDeviceTuya('temperature_c')
                            if str(currenttemp_set) != str(Devices[dev['id']].Units[3].sValue):
                                    UpdateDevice(dev['id'], 3, currenttemp_set, 0, 0)
                        if searchCode('mode', ResultValue) and checkDevice(dev['id'],4):
                            currentmode = StatusDeviceTuya('mode')
                            for item in FunctionProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[4].sValue):
                                UpdateDevice(dev['id'], 4, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('cur_current', ResultValue):
                            currentcurrent = StatusDeviceTuya('cur_current')
                            currentpower = StatusDeviceTuya('cur_power')
                            currentvoltage = StatusDeviceTuya('cur_voltage')
                            if get_unit('cur_current', StatusProperties) == 'mA':
                                UpdateDevice(dev['id'], 15, str(currentcurrent), 0, 0)
                            else:
                                UpdateDevice(dev['id'], 11, str(currentcurrent), 0, 0)
                            UpdateDevice(dev['id'], 12, str(currentpower), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[14].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev['id']].Units[14].sValue if len(Devices[dev['id']].Units[14].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 14, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)

                            UpdateDevice(dev['id'], 13, str(currentvoltage), 0, 0)

                        if searchCode('window_check', ResultValue):
                            currentstatus = StatusDeviceTuya('window_check')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 5, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 5, 'On', 1, 0)
                        if searchCode('child_lock', ResultValue):
                            currentstatus = StatusDeviceTuya('child_lock')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 6, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 6, 'On', 1, 0)
                        if searchCode('eco', ResultValue):
                            currentstatus = StatusDeviceTuya('eco')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 7, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 7, 'On', 1, 0)
                        if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
                            if searchCode('battery_state', ResultValue):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('battery', ResultValue):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', ResultValue):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', ResultValue):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()

                    if dev_type in ('temperaturehumiditysensor', 'smartir'):
                        if searchCode('va_temperature', ResultValue):
                            currenttemp = StatusDeviceTuya('va_temperature')
                            if str(currenttemp) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, currenttemp, 0, 0)
                        if searchCode('temp_current', ResultValue):
                            currenttemp = StatusDeviceTuya('temp_current')
                            if str(currenttemp) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, currenttemp, 0, 0)
                        if  searchCode('va_humidity', ResultValue):
                            currenthumi = StatusDeviceTuya('va_humidity')
                            if str(currenthumi) != str(Devices[dev['id']].Units[2].nValue):
                                UpdateDevice(dev['id'], 2, 0, currenthumi, 0)
                        if  searchCode('humidity_value', ResultValue):
                            currenthumi = StatusDeviceTuya('humidity_value')
                            if str(currenthumi) != str(Devices[dev['id']].Units[2].nValue):
                                UpdateDevice(dev['id'], 2, 0, currenthumi, 0)
                        if searchCode('va_temperature', ResultValue) and searchCode('va_humidity', ResultValue):
                            currentdomo = Devices[dev['id']].Units[3].sValue
                            if str(currenttemp) != str(currentdomo.split(';')[0]) or str(currenthumi) != str(currentdomo.split(';')[1]):
                                UpdateDevice(dev['id'], 3, str(currenttemp ) + ';' + str(currenthumi) + ';0', 0, 0)
                        if searchCode('temp_current', ResultValue) and searchCode('humidity_value', ResultValue):
                            currentdomo = Devices[dev['id']].Units[3].sValue
                            if str(currenttemp) != str(currentdomo.split(';')[0]) or str(currenthumi) != str(currentdomo.split(';')[1]):
                                UpdateDevice(dev['id'], 3, str(currenttemp ) + ';' + str(currenthumi) + ';0', 0, 0)
                        if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
                            if searchCode('battery_state', ResultValue):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('battery', ResultValue):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', ResultValue):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', ResultValue):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()

                    if dev_type == 'doorbell':
                        if searchCode('basic_indicator', ResultValue):
                            datetimestamp = StatusDeviceTuya('doorbell_active')
                            timestamp = int(time.mktime(time.strptime(Devices[dev['id']].Units[1].LastUpdate, '%Y-%m-%d %H:%M:%S')))
                            if (int(timestamp) - int(datetimestamp)) < 61:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                            else:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)

                    if dev_type == 'fan':
                        if searchCode('switch', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)

                    if dev_type == 'fanlight':
                        if searchCode('fan_switch', FunctionProperties):
                            currentstatus = StatusDeviceTuya('fan_switch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 2, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 2, 'On', 1, 0)
                        if searchCode('fan_speed', ResultValue):
                            currentmode = StatusDeviceTuya('fan_speed')
                            for item in FunctionProperties:
                                if item['code'] == 'fan_speed':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values.get('min'),the_values.get('max') + 1):
                                        mode.extend([str(num)])
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('fan_direction', ResultValue):
                            currentmode = StatusDeviceTuya('fan_direction')
                            for item in FunctionProperties:
                                if item['code'] == 'fan_direction':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[4].sValue):
                                UpdateDevice(dev['id'], 4, int(mode.index(str(currentmode)) * 10), 1, 0)

                    if dev_type == 'siren':
                        if searchCode('AlarmSwitch', FunctionProperties):
                            currentstatus = StatusDeviceTuya('AlarmSwitch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if searchCode('Alarmtype', ResultValue):
                            currentmode = StatusDeviceTuya('Alarmtype')
                            for item in FunctionProperties:
                                if item['code'] == 'Alarmtype':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('AlarmPeriod', ResultValue):
                            currentmode = StatusDeviceTuya('AlarmPeriod')
                            for item in FunctionProperties:
                                if item['code'] == 'AlarmPeriod':
                                    the_values = json.loads(item['values'])
                                    for num in range(the_values.get('min'),the_values.get('max') + 1):
                                        mode.extend([str(num)])
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('BatteryStatus', ResultValue):
                            if int(StatusDeviceTuya('BatteryStatus')) == 1:
                                currentbattery = 100
                            elif int(StatusDeviceTuya('BatteryStatus')) == 2:
                                currentbattery = 50
                            elif int(StatusDeviceTuya('BatteryStatus')) == 3:
                                currentbattery = 5
                            else:
                                currentbattery = 255
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()
                        # Other type of Alarm with same code
                        if searchCode('AlarmSwitch', FunctionProperties):
                            currentstatus = StatusDeviceTuya('AlarmSwitch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if searchCode('alarm_state', ResultValue):
                            currentmode = StatusDeviceTuya('alarm_state')
                            for item in FunctionProperties:
                                if item['code'] == 'alarm_state':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('alarm_volume', ResultValue):
                            currentmode = StatusDeviceTuya('alarm_volume')
                            for item in FunctionProperties:
                                if item['code'] == 'alarm_volume':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, int(mode.index(str(currentmode)) * 10), 1, 0)

                    if dev_type == 'powermeter':
                        if searchCode('Current', ResultValue):
                            currentcurrent = StatusDeviceTuya('Current')
                            currentpower = StatusDeviceTuya('ActivePower')
                            currentFrequency = StatusDeviceTuya('Frequency')
                            currentTemperature = StatusDeviceTuya('Temperature')

                            UpdateDevice(dev['id'], 2, str(currentFrequency), 0, 0)
                            UpdateDevice(dev['id'], 3, str(currentTemperature), 0, 0)
                            UpdateDevice(dev['id'], 4, str(currentcurrent), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[5].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev['id']].Units[5].sValue if len(Devices[dev['id']].Units[5].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 5, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)

                        if searchCode('CurrentA', ResultValue):
                            currentcurrentA = StatusDeviceTuya('CurrentA')
                            currentpowerA = StatusDeviceTuya('ActivePowerA')
                            currentvoltageA = StatusDeviceTuya('VoltageA')

                            lastvalue3PA = Devices[dev['id']].Units[1].sValue if len(Devices[dev['id']].Units[1].sValue) > 0 else '0;0;0'
                            UpdateDevice(dev['id'], 1, str(currentcurrentA) + ';' + str(float(lastvalue3PA.split(';')[1])) + ';' + str(float(lastvalue3PA.split(';')[2])) , 0, 0, 1)

                            lastupdateA = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[12].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalueA = Devices[dev['id']].Units[12].sValue if len(Devices[dev['id']].Units[12].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 12, str(currentpowerA) + ';' + str(float(lastvalueA.split(';')[1]) + ((currentpowerA) * (lastupdateA / 3600))) , 0, 0, 1)

                            UpdateDevice(dev['id'], 11, str(currentvoltageA), 0, 0)
                        if searchCode('CurrentB', ResultValue):
                            currentcurrentB = StatusDeviceTuya('CurrentB')
                            currentpowerB = StatusDeviceTuya('ActivePowerB')
                            currentvoltageB = StatusDeviceTuya('VoltageB')

                            lastvalue3PB = Devices[dev['id']].Units[1].sValue if len(Devices[dev['id']].Units[1].sValue) > 0 else '0;0;0'
                            UpdateDevice(dev['id'], 1, str(float(lastvalue3PB.split(';')[0])) + ';' + str(currentcurrentB) + ';' + str(float(lastvalue3PB.split(';')[2])) , 0, 0, 1)

                            lastupdateB = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[22].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalueB = Devices[dev['id']].Units[22].sValue if len(Devices[dev['id']].Units[22].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 22, str(currentpowerB) + ';' + str(float(lastvalueB.split(';')[1]) + ((currentpowerB) * (lastupdateB / 3600))) , 0, 0, 1)

                            UpdateDevice(dev['id'], 21, str(currentvoltageB), 0, 0)
                        if searchCode('CurrentC', ResultValue):
                            currentcurrentC = StatusDeviceTuya('CurrentC')
                            currentpowerC = StatusDeviceTuya('ActivePowerC')
                            currentvoltageC = StatusDeviceTuya('VoltageC')

                            lastvalue3PC = Devices[dev['id']].Units[1].sValue if len(Devices[dev['id']].Units[1].sValue) > 0 else '0;0;0'
                            UpdateDevice(dev['id'], 1, str(float(lastvalue3PC.split(';')[0])) + ';' + str(float(lastvalue3PC.split(';')[1])) + ';' + str(currentcurrentC) , 0, 0, 1)

                            lastupdateC = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[32].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalueC = Devices[dev['id']].Units[32].sValue if len(Devices[dev['id']].Units[32].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 32, str(currentpowerC) + ';' + str(float(lastvalueC.split(';')[1]) + ((currentpowerC) * (lastupdateC / 3600))) , 0, 0, 1)

                            UpdateDevice(dev['id'], 31, str(currentvoltageC), 0, 0)

                        # 1 phase_a Meter
                        if searchCode('phase_a', ResultValue):
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
                            UpdateDevice(dev['id'], 1, str(currentcurrent), 0, 0)
                            UpdateDevice(dev['id'], 2, str(currentpower), 0, 0)
                            UpdateDevice(dev['id'], 3, str(currentvoltage), 0, 0)

                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[4].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev['id']].Units[4].sValue if len(Devices[dev['id']].Units[4].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 4, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)

                        # 2 phase Meter with reverse
                        if searchCode('direction_a', ResultValue):
                            currentVoltage = StatusDeviceTuya('voltage_a')
                            currentFrequency = StatusDeviceTuya('freq')
                            currentPower = StatusDeviceTuya('total_power')
                            currentPowerA = StatusDeviceTuya('power_a')
                            currentCurrentA = StatusDeviceTuya('current_a')
                            currentDirectionA = StatusDeviceTuya('direction_a').capitalize()
                            currentForwardA = StatusDeviceTuya('energy_forword_a')
                            currentReverseA = StatusDeviceTuya('energy_reverse_a')
                            currentPowerB = StatusDeviceTuya('power_b')
                            currentCurrentB = StatusDeviceTuya('current_b')
                            currentDirectionB = StatusDeviceTuya('direction_b').capitalize()
                            currentForwardB = StatusDeviceTuya('energy_forword_b')
                            currentReverseB = StatusDeviceTuya('energy_reserse_b')

                            UpdateDevice(dev['id'], 1, str(currentVoltage), 0, 0)
                            UpdateDevice(dev['id'], 2, str(currentFrequency), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[3].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev['id']].Units[3].sValue if len(Devices[dev['id']].Units[3].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 3, str(currentPower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentPower) * (lastupdate / 3600))) , 0, 0, 1)


                            UpdateDevice(dev['id'], 11, str(currentPowerA), 0, 0)
                            UpdateDevice(dev['id'], 12, str(currentCurrentA), 0, 0)
                            UpdateDevice(dev['id'], 13, str(currentDirectionA), 0, 0)
                            UpdateDevice(dev['id'], 14, str(currentForwardA), 0, 0)
                            UpdateDevice(dev['id'], 15, str(currentReverseA), 0, 0)

                            UpdateDevice(dev['id'], 21, str(currentPowerB), 0, 0)
                            UpdateDevice(dev['id'], 22, str(currentCurrentB), 0, 0)
                            UpdateDevice(dev['id'], 23, str(currentDirectionB), 0, 0)
                            UpdateDevice(dev['id'], 24, str(currentForwardB), 0, 0)
                            UpdateDevice(dev['id'], 25, str(currentReverseB), 0, 0)


                    if dev_type == 'gateway':
                        if searchCode('master_state', ResultValue):
                            UpdateDevice(dev['id'], 1, StatusDeviceTuya('master_state'), 0, 0)
                        else:
                            UpdateDevice(dev['id'], 1, 'Gateway only', 0, 0)

                    if dev_type == ('co2sensor'):
                        if searchCode('temp_current', ResultValue):
                            currenttemp = StatusDeviceTuya('temp_current')
                            if str(currenttemp) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, currenttemp, 0, 0)
                        if  searchCode('humidity_value', ResultValue):
                            currenthumi = StatusDeviceTuya('humidity_value')
                            if str(currenthumi) != str(Devices[dev['id']].Units[2].nValue):
                                UpdateDevice(dev['id'], 2, 0, currenthumi, 0)
                        if searchCode('temp_current', ResultValue) and searchCode('humidity_value', ResultValue):
                            currentdomo = Devices[dev['id']].Units[3].sValue
                            if str(currenttemp) != str(currentdomo.split(';')[0]) or str(currenthumi) != str(currentdomo.split(';')[1]):
                                UpdateDevice(dev['id'], 3, str(currenttemp ) + ';' + str(currenthumi) + ';0', 0, 0)
                        if  searchCode('co2_value', ResultValue):
                            currentco2 = StatusDeviceTuya('co2_value')
                            if str(currentco2) != str(Devices[dev['id']].Units[4].nValue):
                                UpdateDevice(dev['id'], 4, str(currentco2), 0, 0)

                    if dev_type == 'doorcontact':
                        if searchCode('doorcontact_state', ResultValue):
                            currentstatus = StatusDeviceTuya('doorcontact_state')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
                            if searchCode('battery_state', ResultValue):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('battery', ResultValue):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', ResultValue):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', ResultValue):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()

                    if dev_type == 'pirlight':
                        if searchCode('switch_pir', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch_pir')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 2, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 2, 'On', 1, 0)
                        if searchCode('device_mode', ResultValue):
                            currentmode = StatusDeviceTuya('device_mode')
                            for item in FunctionProperties:
                                if item['code'] == 'device_mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('pir_sensitivity', ResultValue):
                            currentmode = StatusDeviceTuya('pir_sensitivity')
                            for item in FunctionProperties:
                                if item['code'] == 'pir_sensitivity':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[4].sValue):
                                UpdateDevice(dev['id'], 4, int(mode.index(str(currentmode)) * 10), 1, 0)

                    if dev_type == 'smokedetector':
                        if searchCode('smoke_sensor_status', ResultValue):
                            currentstatus = StatusDeviceTuya('smoke_sensor_status')
                            if currentstatus == 'normal':
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif currentstatus == 'alarm':
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                            UpdateDevice(dev['id'], 2, currentstatus, 0, 0)
                        if searchCode('PIR', ResultValue):
                            currentstatus = StatusDeviceTuya('PIR')
                            if int(currentstatus) == 0:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif int(currentstatus) > 0:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                            UpdateDevice(dev['id'], 2, currentstatus, 0, 0)
                        # if searchCode('PIR', ResultValue):
                        #     currentmode = StatusDeviceTuya('PIR')
                        #     for item in StatusProperties:
                        #         if item['code'] == 'PIR':
                        #             the_values = json.loads(item['values'])
                        #             mode = ['off']
                        #             mode.extend(the_values.get('range'))
                        #     if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[2].sValue):
                        #         UpdateDevice(dev['id'], 2, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
                            if searchCode('battery_state', ResultValue):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('battery', ResultValue):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', ResultValue):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', ResultValue):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()

                    if dev_type == 'garagedooropener':
                        if searchCode('switch_1', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch_1')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if searchCode('doorcontact_state', ResultValue):
                            currentstatus = StatusDeviceTuya('doorcontact_state')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 2, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 2, 'On', 1, 0)
                        if searchCode('door_control_1', ResultValue):
                            currentstatus = StatusDeviceTuya('door_control_1')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 3, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 3, 'On', 1, 0)

                    if dev_type == 'feeder':
                        if searchCode('manual_feed', ResultValue):
                            currentmode = StatusDeviceTuya('manual_feed')
                            for item in FunctionProperties:
                                if item['code'] == 'manual_feed':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values.get('min'),the_values.get('max') + 1):
                                        mode.extend([str(num)])
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('feed_state', ResultValue):
                            currentmode = StatusDeviceTuya('feed_state')
                            for item in StatusProperties:
                                if item['code'] == 'feed_state':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('feed_report', ResultValue):
                            currentmode = StatusDeviceTuya('feed_report')
                            for item in StatusProperties:
                                if item['code'] == 'feed_report':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values.get('min'),the_values.get('max') + 1):
                                        mode.extend([str(num)])
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('light', FunctionProperties):
                            currentstatus = StatusDeviceTuya('light')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 5, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 5, 'On', 1, 0)

                    if dev_type == 'waterleak':
                        if searchCode('watersensor_state', ResultValue):
                            currentstatus = StatusDeviceTuya('watersensor_state')
                            if currentstatus == 'normal':
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif currentstatus == 'alarm':
                                    UpdateDevice(dev['id'], 1, 'On', 1, 0)
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
                            if searchCode('battery_state', ResultValue):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('battery', ResultValue):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', ResultValue):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', ResultValue):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()

                    if dev_type == 'presence':
                        if searchCode('watersensor_state', ResultValue):
                            currentstatus = StatusDeviceTuya('watersensor_state')
                            if currentstatus == 'none':
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif currentstatus == 'pir':
                                    UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
                            if searchCode('battery_state', ResultValue):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('battery', ResultValue):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', ResultValue):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', ResultValue):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()

                    if dev_type == 'irrigation':
                        if searchCode('switch', FunctionProperties):
                            currentstatus = StatusDeviceTuya('switch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if searchCode('work_state', ResultValue):
                            currentmode = StatusDeviceTuya('work_state')
                            for item in StatusProperties:
                                if item['code'] == 'work_state':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
                            if searchCode('battery_state', ResultValue):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('battery', ResultValue):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', ResultValue):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', ResultValue):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()

                    if dev_type == 'wswitch':
                        timestamp = int(time.mktime(time.localtime()) * 1000)
                        if (int(timestamp) - int(t)) < 61000:
                            for x in range(1, 9):
                                if searchCode('switch' + str(x) + '_value', ResultValue):
                                    currentmode = StatusDeviceTuya('switch' + str(x) + '_value')
                                    for item in StatusProperties:
                                        if item['code'] == 'switch' + str(x) + '_value':
                                            the_values = json.loads(item['values'])
                                            mode = ['off']
                                            mode.extend(the_values.get('range'))
                                if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[x].sValue):
                                    UpdateDevice(dev['id'], x, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
                            if searchCode('battery_state', ResultValue):
                                if StatusDeviceTuya('battery_state') == 'high':
                                    currentbattery = 100
                                if StatusDeviceTuya('battery_state') == 'middle':
                                    currentbattery = 50
                                if StatusDeviceTuya('battery_state') == 'low':
                                    currentbattery = 5
                            if searchCode('battery', ResultValue):
                                currentbattery = StatusDeviceTuya('battery') * 10
                            if searchCode('va_battery', ResultValue):
                                currentbattery = StatusDeviceTuya('va_battery')
                            if searchCode('battery_percentage', ResultValue):
                                currentbattery = StatusDeviceTuya('battery_percentage')
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()

                    if dev_type == 'lightsensor':
                        if searchCode('bright_value', ResultValue):
                            currentbright= StatusDeviceTuya('bright_value')
                            UpdateDevice(dev['id'], 1, float(currentbright),1, 0)

                    if dev_type == 'starlight':
                        currentstatus = StatusDeviceTuya('switch_led')
                        if bool(currentstatus) == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif bool(currentstatus) == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        colortuya = StatusDeviceTuya('colour_data')
                        if currentstatus == True:
                            tuyacolor = ast.literal_eval(StatusDeviceTuya('colour_data'))
                            color = Devices[dev['id']].Units[1].Color
                            if color == '': color = {"b":255,"cw":0,"g":255,"m":3,"r":255,"t":0,"ww":0}
                            h, s, v = tuyacolor['h'], tuyacolor['s'], tuyacolor['v']
                            Domoticz.Debug('TEst: ' + str(v))
                            r, g, b = hsv_to_rgb_v2(h, s, v)
                            colorupdate = {'b':b,'cw':0,'g':g,'m':3,'r':r,'t':0,'ww':0}
                            # {"b":0,"cw":0,"g":3,"m":3,"r":255,"t":0,"ww":0}
                            if (color['r'] != r or color['g'] != g or color['b'] != b ):
                                UpdateDevice(dev['id'], 1, colorupdate, 1, 0)
                                UpdateDevice(dev['id'], 1, brightness_to_pct(StatusProperties, 'bright_value', int(v * 0.255)), 1, 0)
                        if searchCode('colour_switch', FunctionProperties):
                            currentstatus = StatusDeviceTuya('colour_switch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 2, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 2, 'On', 1, 0)
                        if searchCode('laser_switch', StatusProperties):
                            currentstatus = StatusDeviceTuya('laser_switch')
                            currentdim = brightness_to_pct(StatusProperties, 'laser_bright', int(StatusDeviceTuya('laser_bright')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDevice(dev['id'], 3, 'Off', 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, 'On', 1, 0)
                                UpdateDevice(dev['id'], 3, currentdim, 1, 0)
                        if searchCode('fan_switch', StatusProperties):
                            currentstatus = StatusDeviceTuya('fan_switch')
                            currentdim = brightness_to_pct(StatusProperties, 'fan_speed', int(StatusDeviceTuya('fan_speed')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDevice(dev['id'], 4, 'Off', 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev['id']].Units[4].sValue):
                                Domoticz.Debug(Devices[dev['id']].Units[4].sValue)
                                UpdateDevice(dev['id'], 4, 'On', 1, 0)
                                UpdateDevice(dev['id'], 4, currentdim, 1, 0)

                    if dev_type == 'smartlock':
                        if searchCode('lock_motor_state', ResultValue):
                            currentstatus = StatusDeviceTuya('lock_motor_state')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            else:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        # if searchCode('unlock_temporary', ResultValue):
                        #     currentstatus = StatusDeviceTuya('unlock_temporary')
                        #     if currentstatus == 0:
                        #         UpdateDevice(dev['id'], 3, 'Off', 1, 0)
                        #     else:
                        #         UpdateDevice(dev['id'], 3, 'On', 0, 0)
                        if searchCode('alarm_lock', ResultValue):
                            currentmode = StatusDeviceTuya('alarm_lock')
                            for item in StatusProperties:
                                if item['code'] == 'alarm_lock':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('residual_electricity', ResultValue):
                            currentbattery = StatusDeviceTuya('residual_electricity')
                        for unit in Devices[dev['id']].Units:
                            if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                Devices[dev['id']].Units[unit].Update()

                    if dev_type == 'dehumidifier':
                        currentstatus = StatusDeviceTuya('switch')
                        if bool(currentstatus) == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif bool(currentstatus) == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if searchCode('dehumidify_set_value', ResultValue):
                            currentmode = StatusDeviceTuya('dehumidify_set_value')
                            for item in FunctionProperties:
                                if item['code'] == 'dehumidify_set_value':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values.get('min'),the_values.get('max') + 1):
                                        mode.extend([str(num)])
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('fan_speed_enum', ResultValue):
                            currentmode = StatusDeviceTuya('fan_speed_enum')
                            for item in StatusProperties:
                                if item['code'] == 'fan_speed_enum':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('mode', ResultValue):
                            currentmode = StatusDeviceTuya('mode')
                            for item in StatusProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[4].sValue):
                                UpdateDevice(dev['id'], 4, int(mode.index(str(currentmode)) * 10), 1, 0)
                        currentstatus = StatusDeviceTuya('anion')
                        if bool(currentstatus) == False:
                            UpdateDevice(dev['id'], 5, 'Off', 0, 0)
                        elif bool(currentstatus) == True:
                            UpdateDevice(dev['id'], 5, 'On', 1, 0)
                        if searchCode('temp_indoor', ResultValue):
                            currenttemp = StatusDeviceTuya('temp_indoor')
                            if str(currenttemp) != str(Devices[dev['id']].Units[6].sValue):
                                UpdateDevice(dev['id'], 6, currenttemp, 0, 0)
                        if  searchCode('humidity_indoor', ResultValue):
                            currenthumi = StatusDeviceTuya('humidity_indoor')
                            if str(currenthumi) != str(Devices[dev['id']].Units[7].nValue):
                                UpdateDevice(dev['id'], 7, 0, currenthumi, 0)
                        if searchCode('temp_indoor', ResultValue) and searchCode('humidity_indoor', ResultValue):
                            currentdomo = Devices[dev['id']].Units[8].sValue
                            if str(currenttemp) != str(currentdomo.split(';')[0]) or str(currenthumi) != str(currentdomo.split(';')[1]):
                                UpdateDevice(dev['id'], 8, str(currenttemp ) + ';' + str(currenthumi) + ';0', 0, 0)

                    if dev_type == 'vacuum':
                        currentstatus = StatusDeviceTuya('power_go')
                        if bool(currentstatus) == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif bool(currentstatus) == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        currentstatus = StatusDeviceTuya('switch_charge')
                        if bool(currentstatus) == False:
                            UpdateDevice(dev['id'], 2, 'Off', 0, 0)
                        elif bool(currentstatus) == True:
                            UpdateDevice(dev['id'], 2, 'On', 1, 0)
                        if searchCode('mode', ResultValue):
                            currentmode = StatusDeviceTuya('mode')
                            for item in StatusProperties:
                                if item['code'] == 'mode':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('suction', ResultValue):
                            currentmode = StatusDeviceTuya('suction')
                            for item in StatusProperties:
                                if item['code'] == 'suction':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[4].sValue):
                                UpdateDevice(dev['id'], 4, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('cistern', ResultValue):
                            currentmode = StatusDeviceTuya('cistern')
                            for item in StatusProperties:
                                if item['code'] == 'cistern':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('range'))
                            if str(mode.index(str(currentmode)) * 10) != str(Devices[dev['id']].Units[5].sValue):
                                UpdateDevice(dev['id'], 5, int(mode.index(str(currentmode)) * 10), 1, 0)
                        if searchCode('status', ResultValue):
                            UpdateDevice(dev['id'], 6, StatusDeviceTuya('status').capitalize(), 0, 0)
                        if searchCode('electricity_left', ResultValue):
                            UpdateDevice(dev['id'], 7, StatusDeviceTuya('electricity_left'), 0, 0)
                        if searchCode('edge_brush', ResultValue):
                            UpdateDevice(dev['id'], 8, StatusDeviceTuya('edge_brush'), 0, 0)
                        if searchCode('roll_brush', ResultValue):
                            UpdateDevice(dev['id'], 9, StatusDeviceTuya('roll_brush'), 0, 0)
                        if searchCode('filter', ResultValue):
                            UpdateDevice(dev['id'], 10, StatusDeviceTuya('filter'), 0, 0)
                        # if searchCode('fault', ResultValue):
                        #     UpdateDevice(dev['id'], 11, StatusDeviceTuya('fault'), 0, 0)
                        if searchCode('fault', ResultValue):
                            currentmode = StatusDeviceTuya('fault')
                            for item in StatusProperties:
                                if item['code'] == 'fault':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    mode.extend(the_values.get('label'))
                            if str(mode[currentmode]).lower() != str(Devices[dev['id']].Units[11].sValue).lower():
                                UpdateDevice(dev['id'], 11, str(mode[currentmode]).capitalize(), 0, 0)



                except Exception as err:
                    Domoticz.Error('Device read failed: ' + str(dev['id']))
                    Domoticz.Debug('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

    except Exception as err:
        Domoticz.Error('handleThread: ' + str(err))
        Domoticz.Debug('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        Domoticz.Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Debug("--->Unit:           " + str(UnitNo))
            Domoticz.Debug("--->Unit Name:     '" + Unit.Name + "'")
            Domoticz.Debug("--->Unit nValue:    " + str(Unit.nValue))
            Domoticz.Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            Domoticz.Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return

# Select device type from category
def DeviceType(category):
    'convert category to device type'
    'https://github.com/tuya/tuya-home-assistant/wiki/Supported-Device-Category'
    if category in {'kg', 'cz', 'pc', 'dlq', 'bh', 'tdq', 'znjdq'}:
        result = 'switch'
    elif category in {'dj', 'dd', 'dc', 'fwl', 'xdd', 'fwd', 'jsq', 'tyndj'}:
        result = 'light'
    elif category in {'tgq', 'tgkg'}:
        result = 'dimmer'
    elif category in {'cl', 'clkg', 'jdcljqr'}:
        result = 'cover'
    elif category in {'qn'}:
        result = 'heater'
    elif category in {'wk', 'wkf', 'mjj', 'wkcz'}:
        result = 'thermostat'
    elif category in {'wsdcg'}:
        result = 'temperaturehumiditysensor'
    elif category in {'rs'}:
        result = 'heatpump'
    elif category in {'sp'}:
        result = 'doorbell'
    elif category in {'fs'}:
        result = 'fan'
    elif category in {'fsd'}:
        result = 'fanlight'
    elif category in {'sgbj'}:
        result = 'siren'
    elif category in {'wnykq'}:
        result = 'smartir'
    elif category in {'zndb'}:
        result = 'powermeter'
    elif category in {'wg2', 'wfcon'}:
        result = 'gateway'
    elif category in {'co2bj'}:
        result = 'co2sensor'
    elif category in {'mcs'}:
        result = 'doorcontact'
    elif category in {'gyd'}:
        result = 'pirlight'
    elif category in {'qt','ywbj'}:
        result = 'smokedetector'
    elif category in {'ckmkzq'}:
        result = 'garagedooropener'
    elif category in {'cwwsq'}:
        result = 'feeder'
    elif category in {'sj'}:
        result = 'waterleak'
    elif category in {'pir'}:
        result = 'presence'
    elif category in {'sfkzq'}:
        result = 'irrigation'
    elif category in {'wxkg'}:
        result = 'wswitch'
    elif category in {'dgnbj'}:
        result = 'lightsensor'
    elif category in {'xktyd'}:
        result = 'starlight'
    elif category in {'ms'}:
        result = 'smartlock'
    elif category in {'cs'}:
        result = 'dehumidifier'
    elif category in {'sd'}:
        result = 'vacuum'
    elif 'infrared_' in category: # keep it last
        result = 'infrared'
    else:
        result = 'unknown'
    return result

def UpdateDevice(ID, Unit, sValue, nValue, TimedOut, AlwaysUpdate = 0):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if checkDevice(ID,Unit):
        if str(Devices[ID].Units[Unit].sValue) != str(sValue) or str(Devices[ID].Units[Unit].nValue) != str(nValue) or str(Devices[ID].TimedOut) != str(TimedOut) or AlwaysUpdate == 1:
            if sValue == None:
                sValue = Devices[ID].Units[Unit].sValue
            Devices[ID].Units[Unit].sValue = str(sValue)
            if type(sValue) == int or type(sValue) == float:
                Devices[ID].Units[Unit].LastLevel = sValue
            elif type(sValue) == dict:
                Devices[ID].Units[Unit].Color = json.dumps(sValue)
            Devices[ID].Units[Unit].nValue = nValue
            Devices[ID].TimedOut = TimedOut
            Devices[ID].Units[Unit].Update(Log=True)

            Domoticz.Debug('Update device value: ' + str(ID) + ' Unit: ' + str(Unit) + ' sValue: ' +  str(sValue) + ' nValue: ' + str(nValue) + ' TimedOut=' + str(TimedOut))
    else:
        Domoticz.Debug('Device: ' + str(ID) + ' Unit: ' + str(Unit) + ' doesn\'t exsist. Nothing to update')
    return

def StatusDeviceTuya(Function):
    if searchCode(Function, ResultValue):
        valueRaw = [item['value'] for item in ResultValue if re.search(r'\b'+Function+r'\b', item['code']) != None][0]
    else:
        Domoticz.Debug('StatusDeviceTuya called ' + Function + ' not found ')
        return None
    if type(valueRaw) == int:
        valueT = get_scale(StatusProperties, Function, valueRaw)
    else:
        valueT = valueRaw
    return valueT

def SendCommandCloud(ID, CommandName, Status):
    sendfunction = properties[ID]['functions']
    actual_function_name = CommandName
    CommandName = list([CommandName])
    actual_status = Status
    # Domoticz.Debug("device_functions:" + str(sendfunction))
    # Domoticz.Debug("CommandName:" + str(CommandName))
    # Domoticz.Debug("Status:" + str(Status))
    for item in sendfunction:
        if str(CommandName) in str(item['code']):
            actual_function_name = str(item['code'])
    if 'bright_value' in CommandName or 'bright_value_v2' in CommandName or 'bright_value_1' in CommandName or 'bright_value_2' in CommandName or 'laser_bright' in CommandName:
        actual_status = pct_to_brightness(sendfunction, actual_function_name, Status)
    elif 'temp_value' in CommandName or 'temp_value_v2' in CommandName:
        actual_status = temp_value_scale(sendfunction, actual_function_name, Status)
    elif type(actual_status) == int or type(actual_status) == float:
        actual_status = set_scale(sendfunction, actual_function_name, Status)

    # Domoticz.Debug("actual_function_name:" + str(actual_function_name))
    # Domoticz.Debug("actual_status:" + str(actual_status))
    if testData != True:
        tuya.sendcommand(ID, {'commands': [{'code': actual_function_name, 'value': actual_status}]})
    Domoticz.Debug('Command send to tuya :' + str(ID) + ", " + str({'commands': [{'code': actual_function_name, 'value': actual_status}]}))

def pct_to_brightness(device_functions, actual_function_name, pct):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min', 0))
                max_value = int(the_values.get('max', 1000))
                # Domoticz.Debug(round(min_value + (pct*(max_value - min_value)) / 100))
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
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                scale = int(the_values.get('scale', 0))
                # step = the_values.get('step', 0)
                max = the_values.get('max', 0)
                min = the_values.get('min', 0)

    if scale == 1:
        result = int(raw * 10)
    elif scale == 2:
        result = int(raw * 100)
    elif scale == 3:
        result = int(raw * 1000)
    else:
        result = int(raw)

    if product_id == 'IAYz2WK1th0cMLmL':
        result = int(raw * 2)

    if result > max:
        result = int(max)
        Domoticz.Log('Value higher then maximum device')
    elif result < min:
        result = int(min)
        Domoticz.Log('Value lower then minium device')

    return result

def get_scale(device_functions, actual_function_name, raw):
    scale = 0
    # if actual_function_name == 'temp_current': actual_function_name = 'temp_set'
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                scale = the_values.get('scale', 0)
                # step = the_values.get('step', 0)
                unit = the_values.get('unit', 0)
                max = the_values.get('max', 0)
    if scale == 0:
        if unit == 'V' and len(str(max)) >= 4:
            result = float(raw / 10)
        elif unit == 'W' and len(str(max)) >= 5:
            result = float(raw / 10)
        else:
            result = int(raw)
    elif scale == 1:
        result = float(raw / 10)
    elif scale == 2:
        result = float(raw / 100)
    elif scale == 3:
        result = float(raw / 1000)
    else:
        result = int(raw)

    if product_id == 'IAYz2WK1th0cMLmL':
        result = float(raw / 2)

    return result

def get_unit(actual_function_name, device_functions):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                result = the_values.get('unit', 0)
    return result

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
    result = 100 - v
    return result

def inv_val(v):
    result = 255 - v
    return result

def rgb_temp(t,v):
    result = int((t / 100) * v)
    return result

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
    flag = 0
    ActualItem = searchCodeActualFunction(Item, Function)
    if ActualItem:
        for Elem in Function:
            if str(ActualItem) == str(Elem['code']):
                flag = Elem['value']
    return flag

def searchCodeActualFunction(Item, Function):
    for OneItem in Function:
        if str(Item) == str(OneItem['code']):
            return str(OneItem['code'])
    # Domoticz.Debug("searchCodeActualFunction unable to find " + str(Item) + " in " + str(Function))
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

# Configuration Helpers
def getConfigItem(Key=None, Values=None):
    Value = {}
    try:
        Config = Domoticz.Configuration()
        if (Key != None):
            # Domoticz.Debug(Config[Key][Values])
            Value = Config[Key][Values]  # only return requested key if there was one
        else:
            Value = Config      # return the whole configuration if no key
    except KeyError:
        Value = {}
    except Exception as inst:
        Domoticz.Error('Domoticz.Configuration read failed: ' + str(inst))
    return Value

def setConfigItem(Key=None, Value=None):
    Config = {}
    try:
        Config = Domoticz.Configuration()
        if (Key != None):
            Config[Key] = Value
        else:
            Config = Value  # set whole configuration if no key specified
        Config = Domoticz.Configuration(Config)
    except Exception as inst:
        Domoticz.Error('Domoticz.Configuration operation failed: ' + str(inst))
    return Config

def version(v):
    return tuple(map(int, (v.split("."))))