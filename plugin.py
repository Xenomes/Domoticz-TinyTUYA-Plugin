# Domoticz TUYA Plugin
#
# Author: Xenomes (xenomes@outlook.com)
#
"""
<<<<<<< HEAD
<plugin key="tinytuya" name="TinyTUYA (Cloud)" author="Xenomes" version="1.2.0" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git">
=======
<plugin key="tinytuya" name="TinyTUYA (Cloud)" author="Xenomes" version="1.0.1" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git">
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1
    <description>
        Support forum: <a href="https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441">https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441</a><br/>
        Support forum Dutch: <a href="https://contactkring.nl/phpbb/viewtopic.php?f=60&amp;t=846">https://contactkring.nl/phpbb/viewtopic.php?f=60&amp;t=846</a><br/>
        <br/>
<<<<<<< HEAD
        <h2>TinyTUYA Plugin v.1.2.0</h2><br/>
=======
        <h2>TinyTUYA Plugin v.1.0.1</h2><br/>
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1
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
        <li>Enter your apiRegion, apiKey, apiSecret and Search deviceID (This id is used to detect all the other devices), keep the setting 'Data Timeout' disabled.</li>
        <li>A deviceID can be found on your IOT account of Tuya got to Cloud => your project => Devices => Pick one of you device ID.</li>
        <li>The initial setup of your devices should be done with the app and this plugin will detect/use the same settings and automatically find/add the devices into Domoticz.</li>
        </ul>
    </description>
    <params>
        <param field="Mode1" label="apiRegion" width="150px" required="true" default="EU">
            <options>
                <option label="EU" value="eu" default="true" />
                <option label="US" value="us"/>
                <option label="CN" value="cn"/>
            </options>
        </param>
        <param field="Username" label="apiKey" width="300px" required="true" default=""/>
        <param field="Password" label="apiSecret" width="300px" required="true" default="" password="true"/>
        <param field="Mode2" label="Search DeviceID" width="300px" />
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
import json

class BasePlugin:
    enabled = False
    def __init__(self):
        return

    def onStart(self):
        Domoticz.Log('TinyTUYA plugin started')
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
<<<<<<< HEAD
            testData = False
            Domoticz.Heartbeat(60)

=======
            Domoticz.Log('onStart called')
<<<<<<< HEAD
        # Domoticz.Heartbeat(1)
>>>>>>> Master
=======
        Domoticz.Heartbeat(60)
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1
        onHandleThread(True)

    def onStop(self):
        Domoticz.Log('onStop called')

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log('onConnect called')

    def onMessage(self, Connection, Data):
        Domoticz.Log('onMessage called')

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Domoticz.Debug("onCommand called for Device " + str(DeviceID) + " Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+ "', Color: " + str(Color))

        # device for the Domoticz
        dev = Devices[DeviceID].Units[Unit]
        Domoticz.Debug('Device ID: ' + str(DeviceID))

        Domoticz.Debug('nValue: ' + str(dev.nValue))
        Domoticz.Debug('sValue: ' + str(dev.sValue) + ' Type ' + str(type(dev.sValue)))
        Domoticz.Debug('LastLevel: ' + str(dev.LastLevel))

        # Control device and update status in Domoticz
        dev_type = getConfigItem(DeviceID, 'category')
        scalemode = getConfigItem(DeviceID, 'scalemode')
        if len(Color) != 0: Color = ast.literal_eval(Color)
<<<<<<< HEAD

        if dev_type == 'switch':
            unit = Unit
=======
        Domoticz.Log(dev_type)
        if dev_type in ('switch', 'unknown'):
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1
            if Command == 'Off':
                SendCommandCloud(DeviceID, 'switch_' + str(unit), False)
                UpdateDevice(DeviceID, unit, 'Off', 0, 0)
            elif Command == 'On':
                SendCommandCloud(DeviceID, 'switch_' + str(unit), True)
                UpdateDevice(DeviceID, unit, 'On', 1, 0)
            elif Command == 'Set Level':
                SendCommandCloud(DeviceID, 'switch_' + str(unit), True)
                UpdateDevice(DeviceID, unit, Level, 1, 0)

<<<<<<< HEAD
        elif dev_type in ('light'):
=======
        elif dev_type in ('light', 'dimmer'):
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1
            if Command == 'Off':
                SendCommandCloud(DeviceID, 'switch_led', False)
                UpdateDevice(DeviceID, 1, 'Off', 0, 0)
            elif Command == 'On':
                SendCommandCloud(DeviceID, 'switch_led', True)
                UpdateDevice(DeviceID, 1, 'On', 1, 0)
            elif Command == 'Set Level':
<<<<<<< HEAD
                SendCommandCloud(DeviceID, 'bright_value', Level)
=======
                # Set new level also light on
                SendCommandCloud(DeviceID, 'switch_led', True)
                SendCommandCloud(DeviceID, 'bright_value', Level)
                # Update status of Domoticz device
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1
                UpdateDevice(DeviceID, 1, Level, 1, 0)
            elif Command == 'Set Color':
<<<<<<< HEAD
=======
                # Update status of Domoticz device
>>>>>>> Master
                UpdateDevice(DeviceID, 1, Level, 1, 0)
                if Color['m'] == 2:
<<<<<<< HEAD
                    SendCommandCloud(DeviceID, 'bright_value', Level)
                    SendCommandCloud(DeviceID, 'temp_value', int(Color['t']))
=======
                    Domoticz.Debug(Color)
                    # Set new level
                    SendCommandCloud(DeviceID, 'temp_value', inv_val(Color['t']))
                    SendCommandCloud(DeviceID, 'bright_value', Level)
                    # Update status of Domoticz device
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1
                    UpdateDevice(DeviceID, 1, Level, 1, 0)
                    UpdateDevice(DeviceID, 1, Color, 1, 0)
                elif Color['m'] == 3:
                    if scalemode == 'v2':
                        h,s,v = rgb_to_hsv_v2(int(Color['r']), int(Color['g']), int(Color['b']))
                        hvs = {'h':h,'s':s,'v':Level * 10}
                        SendCommandCloud(DeviceID, 'colour_data', hvs)
                    else:
                        h,s,v = rgb_to_hsv(int(Color['r']), int(Color['g']), int(Color['b']))
                        hvs = {'h':h,'s':s,'v':Level * 2.55}
                        SendCommandCloud(DeviceID, 'colour_data', hvs)
                    UpdateDevice(DeviceID, 1, Level, 1, 0)
                    UpdateDevice(DeviceID, 1, Color, 1, 0)

        if dev_type == ('cover'):
            if Command == 'Open':
                SendCommandCloud(DeviceID, 'mach_operate', 'FZ')
                UpdateDevice(DeviceID, 1, 'Open', 0, 0)
            elif Command == 'Close':
                SendCommandCloud(DeviceID, 'mach_operate', 'ZZ')
                UpdateDevice(DeviceID, 1, 'Close', 1, 0)
            elif Command == 'Stop':
                SendCommandCloud(DeviceID, 'mach_operate', 'STOP')
                UpdateDevice(DeviceID, 1, 'Stop', 1, 0)
            elif Command == 'Set Level':
                SendCommandCloud(DeviceID, 'position', Level)
                UpdateDevice(DeviceID, 1, Level, 1, 0)

        elif dev_type == 'thermostat':
            if Command == 'Off':
                SendCommandCloud(DeviceID, 'switch', False)
                UpdateDevice(DeviceID, 1, 'Off', 0, 0)
            elif Command == 'On':
                SendCommandCloud(DeviceID, 'switch', True)
                UpdateDevice(DeviceID, 1, 'On', 1, 0)
            elif Command == 'Set Level' and Unit  == 3:
                SendCommandCloud(DeviceID, 'temp_set', Level)
                UpdateDevice(DeviceID, 3, Level, 1, 0)
            elif Command == 'Set Level' and Unit == 4:
                if Level == 10:
                    LevelName = 'auto'
                elif Level == 20:
                    LevelName = 'hot'
                elif Level == 30:
                    LevelName = 'eco'
                elif Level == 40:
                    LevelName = 'cold'
                SendCommandCloud(DeviceID, 'mode', LevelName)
                UpdateDevice(DeviceID, 4, Level, 1, 0)

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log('Notification: ' + Name + ', ' + Subject + ', ' + Text + ', ' + Status + ', ' + str(Priority) + ', ' + Sound + ', ' + ImageFile)

    def onDeviceRemoved(self, DeviceID, Unit):
        Domoticz.Log('onDeviceDeleted called')
<<<<<<< HEAD
=======
        # device for the Domoticz
        Devices[DeviceID].Units[Unit].Delete
        Domoticz.Debug('Device ID: ' + str(DeviceID) + ' delete')
>>>>>>> Master

    def onDisconnect(self, Connection):
        Domoticz.Log('onDisconnect called')

    def onHeartbeat(self):
        Domoticz.Log('onHeartbeat called')
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
            global result
            global functions
            global function
            global scalemode
            if testData == True:
                tuya = Domoticz.Log
                with open(Parameters['HomeFolder'] + '/debug_devices.json') as dFile:
                    devs = json.load(dFile)
                token = 'Fake'
                functions = {}
                with open(Parameters['HomeFolder'] + '/debug_functions.json') as fFile:
                    for dev in devs:
                        functions[dev['id']] = json.load(fFile)['result']
            else:
                tuya = tinytuya.Cloud(apiRegion=Parameters['Mode1'], apiKey=Parameters['Username'], apiSecret=Parameters['Password'], apiDeviceID=Parameters['Mode2'])
                devs = tuya.getdevices(verbose=False)
                token = tuya.token
                functions = {}
                for dev in devs:
                    functions[dev['id']] = tuya.getfunctions(dev['id'])['result']

            # Check credentials
            if 'sign invalid' in str(token) or token == None:
                raise Exception('Credentials are incorrect!')

            # Check ID search device is valid
            if 'permission deny' in str(devs):
                raise Exception('ID search device not found!')

        # Initialize/Update devices from TUYA API
        for dev in devs:
<<<<<<< HEAD
            Domoticz.Debug( 'Device name=' + str(dev['name']) + ' id=' + str(dev['id']) + ' category=' + str(DeviceType(dev['category'])))
            if testData == True:
                online = True
            else:
                online = tuya.getconnectstatus(dev['id'])
            function = functions[dev['id']]['functions'] if not functions[dev['id']]['functions'] == '[]' else None
            dev_type = DeviceType(functions[dev['id']]['category'])
            if testData == True:
                with open(Parameters['HomeFolder'] + '/debug_result.json') as rFile:
                    result = json.load(rFile)['result']
            else:
                result = tuya.getstatus(dev['id'])['result']
            # Define scale mode
            if '\"scale\":1' in str(function) or '_v2"' in str(function):
                scalemode = 'v2'
            else:
                scalemode = 'v1'
            # Domoticz.Debug( 'functions= ' + str(functions))
            # Domoticz.Debug( 'Device name= ' + str(dev['name']) + ' id= ' + str(dev['id']) + ' result= ' + str(result))
            # Domoticz.Debug( 'Device name= ' + str(dev['name']) + ' id= ' + str(dev['id']) + ' function= ' + str(functions[dev['id']]))
=======
            Domoticz.Debug( 'Device name=' + str(dev['name']) + ' id=' + str(dev['id']))
            functions = tuya.getfunctions(dev['id'])['result']['functions']
            online = tuya.getconnectstatus(dev['id'])
            result = tuya.getstatus(dev['id'])['result']
            dev_type = DeviceType(tuya.getfunctions(dev['id'])['result']['category'])
>>>>>>> Master

            # Create devices
            if startup == True:
                Domoticz.Debug('Run Startup script')
                deviceinfo = tinytuya.find_device(dev['id'])
<<<<<<< HEAD
=======

>>>>>>> Master
                if dev['id'] not in Devices:
<<<<<<< HEAD
                    if dev_type == 'light':
                        # for localcontol: and deviceinfo['ip'] != None
                        if 'switch_led' in str(function) and 'colour' in str(function) and 'white' in str(function) and 'temp_value' in str(function) and 'bright_value' in str(function):
                            Domoticz.Log('Create device Light RGBWW')
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=4, Switchtype=7,  Used=1).Create()
                        elif 'switch_led' in str(function) and 'dc' == str(functions[dev['id']]['category']) and 'colour' in str(function) and 'white' in str(function):
                            Domoticz.Log('Create device Light Stringlight')
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=4, Switchtype=7,  Used=1).Create()
                        elif 'switch_led' in str(function) and 'colour' in str(function) and 'white' in str(function) and 'temp_value' not in str(function) and 'bright_value' in str(function):
                            Domoticz.Log('Create device Light RGBW')
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=1, Switchtype=7,  Used=1).Create()
                        elif 'switch_led' in str(function) and 'colour' in str(function) and not 'white' in str(function) and 'temp_value' not in str(function) and 'bright_value' in str(function):
                            Domoticz.Log('Create device Light RGB')
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=2, Switchtype=7,  Used=1).Create()
                        elif 'switch_led' in str(function) and 'colour' not in str(function) and not 'white' in str(function) and 'temp_value' in str(function) and 'bright_value' in str(function):
                            Domoticz.Log('Create device Light WWCW')
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=8, Switchtype=7,  Used=1).Create()
                        elif 'switch_led' in str(function) and 'colour' not in str(function) and not 'white' in str(function) and 'temp_value' not in str(function) and 'bright_value' in str(function):
                            Domoticz.Log('Create device Light Dimmer')
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=3, Switchtype=7,  Used=1).Create()
                        elif 'switch_led' in str(function) and 'colour' not in str(function) and 'white' not in str(function) and 'temp_value' not in str(function) and 'bright_value' not in str(function):
                            Domoticz.Log('Create device Light On/Off')
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=7,  Used=1).Create()

                    elif dev_type == 'cover':
                        Domoticz.Log('Create device Cover')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=21, Used=1).Create()

                    elif dev_type == 'switch':
                        if 'switch_1' in str(function) and 'switch_2' not in str(function):
                            Domoticz.Log('Create device Switch')
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if 'switch_2' in str(function):
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 1)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 2)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if 'switch_3' in str(function):
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 3)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if 'switch_4' in str(function):
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 4)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if 'switch_5' in str(function):
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 5)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        # if 'cur_current'in str(function):
                        #     Domoticz.Unit(Name=dev['name'] + '(A)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=23, Used=1).Create()
                        # if 'cur_power'in str(function):
                        #     Domoticz.Unit(Name=dev['name'] + '(kWh)', DeviceID=dev['id'], Unit=12, Type=243, Subtype=29, Used=1).Create()
                        # if 'cur_voltage'in str(function):
                        #     Domoticz.Unit(Name=dev['name'] + '(V)', DeviceID=dev['id'], Unit=13, Type=243, Subtype=8, Used=1).Create()

                    elif dev_type == 'thermostat':
                        Domoticz.Log('Create device Thermostat')
                        Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=2, Type=80, Subtype=5, Used=1).Create()
                        Domoticz.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev['id'], Unit=3, Type=242, Subtype=1, Used=1).Create()
                        if 'mode' in str(function):
                            options = {}
                            options['LevelOffHidden'] = 'true'
                            options['LevelActions'] = ''
                            options['LevelNames'] = '|'.join(['Off','Auto', 'Hot', 'Eco', 'Cold'])
                            options['SelectorStyle'] = '0'
                            Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=15, Used=1).Create()

                    elif dev_type == 'temperaturehumiditysensor':
                        Domoticz.Log('Create device T&H Sensor')
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=1, Type=80, Subtype=5, Used=1).Create()
                        Domoticz.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev['id'], Unit=2, Type=81, Subtype=1, Used=1).Create()
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev['id'], Unit=3, Type=82, Subtype=5, Used=1).Create()
=======
                    if dev_type == 'light' or dev_type == 'dimmer': # for localcontol: and deviceinfo['ip'] != None
                        #if 'colour' in [item['values'] for item in functions if item['code'] == 'work_mode'][0]:
                        if 'switch_led' in str(functions) and 'colour' in str(functions) and 'white' in str(functions) and 'temp_value' in str(functions) and 'bright_value' in str(functions):
                            # Light Color and White temperature contol (RGBWW)
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=4, Switchtype=7,  Used = 1).Create()
                        elif 'switch_led' in str(functions) and 'colour' in str(functions) and 'white' in str(functions) and 'temp_value' not in str(functions) and 'bright_value' in str(functions):
                            # Light Color control (RGBW)
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=1, Switchtype=7,  Used = 1).Create()
                        elif 'switch_led' in str(functions) and 'colour' in str(functions) and not 'white' in str(functions) and 'temp_value' not in str(functions) and 'bright_value' in str(functions):
                            # Light Color control (RGB)
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=2, Switchtype=7,  Used = 1).Create()
                        elif 'switch_led' in str(functions) and 'colour' not in str(functions) and 'white' in str(functions) and 'temp_value' in str(functions) and 'bright_value' in str(functions):
                            # Light White temperature control
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=8, Switchtype=7,  Used = 1).Create()
                        elif 'switch_led' in str(functions) and 'colour' not in str(functions) and 'white' in str(functions) and 'temp_value' not in str(functions) and 'bright_value' in str(functions):
                            # Light Brightness control
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=3, Switchtype=7,  Used = 1).Create()
                        elif 'switch_led' in str(functions) and 'colour' not in str(functions) and 'white' not in str(functions) and 'temp_value' not in str(functions) and 'bright_value' not in str(functions):
                            # Light On/Off control
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=7,  Used = 1).Create()
                        elif 'switch_led' in str(functions) and 'colour' not in str(functions) and 'temp_value' not in str(functions) and 'bright_value' in str(functions):
                            # Light Brightness control
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=3, Switchtype=7,  Used = 1).Create()
                        else:
                            # Error
                            Domoticz.Error('No controls found for your light device!')
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1
                    # elif dev_type == 'climate':
                    #     Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=16, Used=1).Create()
                    # elif dev_type == 'fan':
                    #     Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    # elif dev_type == 'lock':
                    #     Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                    else:
                        Domoticz.Log('No controls found for device: ' + str(dev['name']))
                        Domoticz.Unit(Name=dev['name'] + ' (Unknown Device)', DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=1).Create()
                        UpdateDevice(dev['id'], 1, 'This device is not reconised, edit and run the debug_discovery with python from the tools directory and receate a issue report at https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/issues so the device can be added.', 0, 0)

                # Set extra info
                setConfigItem(dev['id'], {'key': dev['key'], 'category': dev_type,  'mac': dev['mac'], 'ip': deviceinfo['ip'], 'version': deviceinfo['version'] , 'scalemode': scalemode})
                Domoticz.Debug('ConfigItem:' + str(getConfigItem()))

            # Check device is removed
            if dev['id'] not in str(Devices):
                raise Exception('Device not found in Domoticz! Device is removed or Accept New Hardware not enabled?')

            #update devices in Domoticz
            Domoticz.Debug('Update devices in Domoticz')
<<<<<<< HEAD
            if bool(online) == False and Devices[dev['id']].TimedOut == 0:
                UpdateDevice(dev['id'], 1, 'Off', 0, 1)
            elif bool(online) == True and Devices[dev['id']].TimedOut == 1:
                UpdateDevice(dev['id'], 1, 'Off' if bool(StatusDeviceTuya('switch_led')) == False else 'On', 0, 0)
            elif bool(online) == True and Devices[dev['id']].TimedOut == 0:
                try:
=======
            # Domoticz.Debug('Test script:' + str(getConfigItem(dev['id'])))

            if online == False and Devices[dev['id']].TimedOut == 0:
                UpdateDevice(dev['id'], 1, 'Off', 0, 1)
            elif online == True and Devices[dev['id']].TimedOut == 1:
                UpdateDevice(dev['id'], 1, 'Off' if StatusDeviceTuya(dev['id'], 'switch_led') == False else 'On', 0, 0)
            elif online == True and Devices[dev['id']].TimedOut == 0:
                try:
                    # Status Tuya
                    # Domoticz.Debug(StatusDeviceTuya(dev['id'], 'temp_value') / 2.55)
                    currentstatusswitch = StatusDeviceTuya(dev['id'], 'switch_1')
                    currentstatuslight = StatusDeviceTuya(dev['id'], 'switch_led')

                    workmode = StatusDeviceTuya(dev['id'], 'work_mode')
                    if 'bright_value' in str(result):
                        device_functions = tuya.getfunctions(dev['id'])['result']['functions']
                        dimtuya = brightness_to_pct(device_functions, 'bright_value', str(StatusDeviceTuya(dev['id'], 'bright_value')))
                    '''
                    Finding other way to detect
                    if 'temp_value' in str(result):
                        temptuya = {'m': 2, 't': int(inv_val(round(StatusDeviceTuya(dev['id'], 'temp_value'))))}
                    if 'colour_data' in str(result):
                        colortuya = ast.literal_eval(StatusDeviceTuya(dev['id'], 'colour_data'))
                        rtuya, gtuya, btuya = hsv_to_rgb(colortuya['h'],colortuya['s'],colortuya['v'])
                        colorupdate = {'m': 3, 'r': rtuya, 'g': gtuya, 'b': btuya}
                    '''
>>>>>>> Master
                    # status Domoticz
                    sValue = Devices[dev['id']].Units[1].sValue
                    nValue = Devices[dev['id']].Units[1].nValue

                    if dev_type == 'switch':
<<<<<<< HEAD
                        if 'switch_1' in str(function):
                            currentstatus = StatusDeviceTuya('switch_1')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        elif 'switch' in str(function):
                            currentstatus = StatusDeviceTuya('switch')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 1, 'On', 1, 0)

                        if 'switch_2' in str(function):
                            currentstatus = StatusDeviceTuya('switch_2')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 2, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 2, 'On', 1, 0)

                        if 'switch_3' in str(function):
                            currentstatus = StatusDeviceTuya('switch_3')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 3, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 3, 'On', 1, 0)

                        if 'switch_4' in str(function):
                            currentstatus = StatusDeviceTuya('switch_4')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 4, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 4, 'On', 1, 0)

                        if 'switch_5' in str(function):
                            currentstatus = StatusDeviceTuya('switch_5')
                            if bool(currentstatus) == False:
                                UpdateDevice(dev['id'], 5, 'Off', 0, 0)
                            elif bool(currentstatus) == True:
                                UpdateDevice(dev['id'], 5, 'On', 1, 0)

                    if dev_type == ('light'):
                        # workmode = StatusDeviceTuya('work_mode')
                        currentstatus = StatusDeviceTuya('switch_led')
                        if 'bright_value' in str(function):
                            dimtuya = brightness_to_pct(function, 'bright_value', str(StatusDeviceTuya('bright_value')))
                        '''
                        Finding other way to detect
                        dimlevel = Devices[dev['id']].Units[1].sValue if type(Devices[dev['id']].Units[1].sValue) == int else dimtuya
                        color = Devices[dev['id']].Units[1].Color

                        if 'temp_value' in str(function):
                            temptuya = {'m': 2, 't': int(inv_val(round(StatusDeviceTuya('temp_value'))))}
                        if 'colour_data' in str(function):
                            colortuya = ast.literal_eval(StatusDeviceTuya('colour_data'))
                            rtuya, gtuya, btuya = hsv_to_rgb(colortuya['h'],colortuya['s'],colortuya['v'])
                            colorupdate = {'m': 3, 'r': rtuya, 'g': gtuya, 'b': btuya}
                        '''
                        if (bool(currentstatus) == False and bool(nValue) != False) or (int(dimtuya) == 0 and bool(nValue) != False):
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif (bool(currentstatus) == True and bool(nValue) != True) or (str(dimtuya) != str(sValue) and bool(nValue) != False):
                            UpdateDevice(dev['id'], 1, dimtuya, 1, 0)
=======
                        if currentstatusswitch == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif currentstatusswitch == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)

                    if dev_type in ('light', 'dimmer'):
                        if (currentstatuslight == False and bool(nValue) != False) or (int(dimtuya) == 0 and bool(nValue) != False):
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif (currentstatuslight == True and bool(nValue) != True) or (str(dimtuya) != str(sValue) and bool(nValue) != False):
                                UpdateDevice(dev['id'], 1, int(dimtuya), 1, 0)
>>>>>>> Master
                        '''
                        elif currentstatus == True and workmode == 'white':
                            Domoticz.Debug(temptuya['t'])
                            Domoticz.Debug(color['t'])
                            if int((temptuya['t'])) != int(color['t']):
                                Domoticz.Debug(str((temptuya['t'])) + ' ' + str(color['t']))
                                UpdateDevice(dev['id'], 1, dimtuya, 1, 0)
                                UpdateDevice(dev['id'], 1, temptuya, 1, 0)
                        elif currentstatus == True and workmode == 'colour':
                            if type(color) == dict and (color['r'] != rtuya or color['g'] != gtuya or color['b'] != btuya ):
                                UpdateDevice(dev['id'], 1, colorupdate, 1, 0)
                        '''
                    if dev_type == 'cover':
                        currentposition = StatusDeviceTuya('position')
                        if str(currentposition) == '0':
                            UpdateDevice(dev['id'], 1, currentposition, 1, 0)
                        if str(currentposition) == '100':
                            UpdateDevice(dev['id'], 1, currentposition, 0, 0)
                        if str(currentposition) != str(Devices[dev['id']].Units[1].sValue):
                            UpdateDevice(dev['id'], 1, currentposition, 2, 0)

                    if dev_type == 'thermostat':
                        currentstatus = StatusDeviceTuya('switch')
                        if bool(currentstatus) == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif bool(currentstatus) == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if 'temp_current' in str(result):
                            currenttemp = StatusDeviceTuya('temp_current')
                            if str(currenttemp) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, currenttemp, 0, 0)
                        if 'temp_set' in str(result):
                            currenttemp_set = StatusDeviceTuya('temp_set')
                            if str(currenttemp_set) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, currenttemp_set, 0, 0)
                        if 'mode' in str(result):
                            currentmode = StatusDeviceTuya('mode')
                            if currentmode == 'auto':
                                currentmodeval = 10
                            elif currentmode == 'hot':
                                currentmodeval = 20
                            elif currentmode == 'eco':
                                currentmodeval = 30
                            elif currentmode == 'cold':
                                currentmodeval = 40
                            if str(currentmodeval) != str(Devices[dev['id']].Units[4].sValue):
                                UpdateDevice(dev['id'], 4, currentmodeval, 1, 0)

                    if dev_type == 'temperaturehumiditysensor':
                        if 'va_temperature' in str(result):
                            currenttemp = StatusDeviceTuya('va_temperature') / 10
                            if str(currenttemp) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, currenttemp, 0, 0)
                        if 'va_humidity' in str(result):
                            currenthumi = StatusDeviceTuya('va_humidity')
                            if str(currenthumi) != str(Devices[dev['id']].Units[2].nValue):
                                UpdateDevice(dev['id'], 2, 0, currenthumi, 0)
                        if 'va_temperature' in str(result) and 'va_humidity' in str(result):
                            currentdomo = Devices[dev['id']].Units[3].sValue
                            if str(currenttemp) != str(currentdomo.split(';')[0]) or str(currenthumi) != str(currentdomo.split(';')[1]):
                                UpdateDevice(dev['id'], 3, str(currenttemp ) + ';' + str(currenthumi) + ';0', 0, 0)
                    Domoticz
                except Exception as err:
                    Domoticz.Log('Device read failed: ' + str(dev['id']))
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
    if category in {'kg', 'cz', 'pc', 'dlq', 'bh','tdq'}:
        result = 'switch'
    elif category in {'dj', 'dd', 'dc', 'fwl', 'xdd', 'fsd', 'fwd', 'gyd', 'jsq', 'tyndj', 'ykq', 'tgq', 'tgkg'}:
        result = 'light'
    elif category in {'cl', 'clkg', 'jdcljqr'}:
        result = 'cover'
    elif category in {'wk', 'wkf', 'qn'}:
        result = 'thermostat'
    elif category in {'wsdcg'}:
        result = 'temperaturehumiditysensor'
    # elif 'infrared_' in category: # keep it last
    #     result = 'infrared_id'
    else:
        result = 'unknown'
    return result

def UpdateDevice(ID, Unit, sValue, nValue, TimedOut):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if ID in Devices:
        if str(Devices[ID].Units[Unit].sValue) != str(sValue) or str(Devices[ID].Units[Unit].nValue) != str(nValue) or str(Devices[ID].TimedOut) != str(TimedOut):
            Devices[ID].Units[Unit].sValue = str(sValue)
            if type(sValue) == int or type(sValue) == float:
                Devices[ID].Units[Unit].LastLevel = sValue
            elif type(sValue) == dict:
                Devices[ID].Units[Unit].Color = json.dumps(sValue)
            Devices[ID].Units[Unit].nValue = nValue
            Devices[ID].TimedOut = TimedOut
            Devices[ID].Units[Unit].Update()

            Domoticz.Debug('Update device value:' + str(ID) + ' Unit: ' + str(Unit) + ' sValue: ' +  str(sValue) + ' nValue: ' + str(nValue) + ' TimedOut=' + str(TimedOut))
    return

<<<<<<< HEAD
def StatusDeviceTuya(Function):
    if Function in str(result):
        valueRaw = [item['value'] for item in result if Function in item['code']][0]
    else:
        Domoticz.Debug('StatusDeviceTuya caled ' + Function + ' not found ')
        return None
    if scalemode == 'v2' and type(valueRaw) == int:
        valueT = valueRaw / 10
    else:
        valueT = valueRaw
    return valueT

def SendCommandCloud(ID, CommandName, Status):
    Domoticz.Debug("device_functions:" + str(function))
    Domoticz.Debug("CommandName:" + str(CommandName))
    Domoticz.Debug("Status:" + str(Status))
    actual_function_name = CommandName
    actual_status = Status
    for item in function:
        if CommandName in str(item['code']):
            actual_function_name = str(item['code'])
    if 'bright_value' in CommandName:
        actual_status = pct_to_brightness(function, actual_function_name, Status)
    if 'temp_value' in CommandName:
        actual_status = temp_value_scale(function, actual_function_name, Status)
    if 'temp_set' in CommandName:
        actual_status = set_temp_scale(Status)
    Domoticz.Debug("actual_function_name:" + str(actual_function_name))
    Domoticz.Debug("actual_status:" + str(actual_status))
    if testData != True:
        tuya.sendcommand(ID, {'commands': [{'code': actual_function_name, 'value': actual_status}]})
    Domoticz.Debug('Command send to tuya :' + str(ID) + ", " + str({'commands': [{'code': actual_function_name, 'value': actual_status}]}))
=======
def StatusDeviceTuya(ID, Function):
    if Function in str(tuya.getstatus(ID)['result']):
        valueT = [item['value'] for item in tuya.getstatus(ID)['result'] if Function in item['code']][0]
    else:
        valueT = None
        Domoticz.Debug('StatusDeviceTuya called ' + Function + ' not found ')
    return valueT

def SendCommandCloud(ID, CommandName, Status):
    device_functions = tuya.getfunctions(ID)['result']['functions']
    Domoticz.Debug("device_functions:"+str(device_functions))
    Domoticz.Debug("CommandName:"+str(CommandName))
    Domoticz.Debug("Status:"+str(Status))
    actual_function_name = CommandName
    actual_status = Status
    for item in device_functions:
        if CommandName in str(item['code']):
            actual_function_name = str(item['code'])
    if "bright_value" in CommandName:
        actual_status = pct_to_brightness(device_functions, actual_function_name, Status)
    Domoticz.Debug("actual_function_name:"+str(actual_function_name))
    Domoticz.Debug("actual_status:"+str(actual_status))
    tuya.sendcommand(ID, {'commands': [{'code': actual_function_name, 'value': actual_status}]})
    Domoticz.Debug('Command send to tuya :' + str(ID) +","+ str({'commands': [{'code': actual_function_name, 'value': actual_status}]}))
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1

def pct_to_brightness(device_functions, actual_function_name, pct):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min',0))
<<<<<<< HEAD
                max_value = int(the_values.get('max',1000))
                return round(min_value + (pct*(max_value - min_value)) / 100)
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
<<<<<<< HEAD
    return round(22.68 + (int(pct) * ((255 - 22.68) / 100)))

def brightness_to_pct(device_functions, actual_function_name, raw):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min',0))
                max_value = int(the_values.get('max',1000))
                return round((100 / (max_value - min_value) * (int(raw) - min_value)))
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round((100 / (255 - 22.68) * (int(raw) - 22.68)))

def temp_value_scale(device_functions, actual_function_name, raw):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min',0))
                max_value = int(the_values.get('max',1000))
                return round((255 / (max_value - min_value) * (int((max_value - raw)) - min_value)))
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round((int(max_value - raw)))

def set_temp_scale(raw):
    if scalemode == 'v2':
        value = int(raw * 10)
    else:
        value = int(raw)
    return value
=======
    result = round(22.68 + (int(p) * ((255 - 22.68) / 100)))
    return result

def brightness_to_pct(v):
    # Convert a raw to a percentage value 25 = 1% => 255 = 100%
    result = round((100 / (255 - 22.68) * (int(v) - 22.68)))
    return result
>>>>>>> Master
=======
                max_value = int(the_values.get('max',255))
                return round(min_value+(pct*(max_value - min_value))/100)
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    return round(22.68 + (int(pct) * ((255 - 22.68) / 100)))

def brightness_to_pct(device_functions, actual_function_name, level):
    if device_functions and actual_function_name:
        for item in device_functions:
            if item['code'] == actual_function_name:
                the_values = json.loads(item['values'])
                min_value = int(the_values.get('min',0))
                max_value = int(the_values.get('max',255))
                return round((level-min_value)*100/(max_value-min_value))
    # Convert a raw to a percentage value 25 = 1% => 255 = 100%
    return round((100 / (255 - 22.68) * (int(level) - 22.68)))
>>>>>>> 37672d7aaa2ceebda4000b82fe4a9e2a2cf1b0f1

def rgb_to_hsv(r, g, b):
    h,s,v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h = int(h * 360)
    s = int(s * 255)
    v = int(v * 255)
    return h, s, v

def rgb_to_hsv_v2(r, g, b):
    h,s,v = colorsys.rgb_to_hsv(r / 1000, g / 1000, b / 1000)
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
    r = round(r * 1000)
    g = round(g * 1000)
    b = round(b * 1000)
    return r, g, b

def inv_pct(v):
    result = 100 - v
    return result

def temp_cw_ww(t):
    cw = t
    ww = 255 - t
    return cw, ww

# Configuration Helpers
def getConfigItem(Key=None, Values=None):
    Value = {}
    try:
        Config = Domoticz.Configuration()
        if (Key != None):
            Domoticz.Debug(Config[Key][Values])
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
