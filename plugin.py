# Domoticz TUYA Plugin
#
# Author: Xenomes (xenomes@outlook.com)
#
"""
<plugin key="tinytuya" name="TinyTUYA (Cloud)" author="Xenomes" version="1.0.0" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git">
    <description>
        Support forum: <a href="https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441">https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441</a><br/>
        Support forum Dutch: <a href="https://contactkring.nl/phpbb/viewtopic.php?f=60&amp;t=846">https://contactkring.nl/phpbb/viewtopic.php?f=60&amp;t=846</a><br/>
        <br/>
        <h2>TinyTUYA Plugin v.1.0.0</h2><br/>
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
import sys
import ast
import json
import colorsys

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
        else:
            Domoticz.Log('onStart called')
        # Domoticz.Heartbeat(1)
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
        for DeviceID in Devices:
            dev = Devices[DeviceID].Units[Unit]
            Domoticz.Debug('Device ID: ' + str(DeviceID))

        # If we didn't find it, leave (probably disconnected at this time)
        if dev == None:
            Domoticz.Debug('Command for DeviceID=' + str(DeviceID) + ' but device is not available.')
            return

        if Devices[DeviceID].TimedOut:
            Domoticz.Debug('Command for DeviceID=' + str(DeviceID) + ' but device is offline.')
            return

        Domoticz.Log('nValue: ' + str(dev.nValue))
        Domoticz.Log('sValue: ' + str(dev.sValue))
        Domoticz.Log('LastLevel: ' + str(dev.LastLevel))

        # Control device and update status in Domoticz
        dev_type = getConfigItem(DeviceID, 'category')
        if len(Color) != 0: Color = ast.literal_eval(Color)
        Domoticz.Log(dev_type)
        if dev_type in ('switch', 'dimmer', 'unknown'):
            if Command == 'Off':
                # Set new state
                SendCommandCloud(DeviceID, 'switch_1', False)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'Off', 0, 0)
            elif Command == 'On':
                # Set new state
                SendCommandCloud(DeviceID, 'switch_1', True)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'On', 1, 0)
            elif Command == 'Set Level':
                # Set new state
                SendCommandCloud(DeviceID, 'switch_1', True)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, Level, 1, 0)

        elif dev_type == 'light':
            if Command == 'Off':
                # Set new level
                SendCommandCloud(DeviceID, 'switch_led', False)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'Off', 0, 0)
            elif Command == 'On':
                # Set new level
                SendCommandCloud(DeviceID, 'switch_led', True)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'On', 1, 0)
            elif Command == 'Set Level':
                # Set new level
                SendCommandCloud(DeviceID, 'bright_value', pct_to_brightness(Level))
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, Level, 1, 0)
            elif Command == 'Set Color':
                # Update status of Domoticz device 
                UpdateDevice(DeviceID, 1, Level, 1, 0)
                if Color['m'] == 2:
                    Domoticz.Debug(Color)
                    # Set new level
                    SendCommandCloud(DeviceID, 'temp_value', inv_val(Color['t']))
                    SendCommandCloud(DeviceID, 'bright_value', pct_to_brightness(Level))
                    # Update status of Domoticz device
                    UpdateDevice(DeviceID, 1, Level, 1, 0)
                    UpdateDevice(DeviceID, 1, Color, 1, 0)
                elif Color['m'] == 3:
                    h,s,v = rgb_to_hsv(int(Color['r']), int(Color['g']), int(Color['b']))
                    hvs = {'h':h,'s':s,'v':Level * 2.55}
                    # Set new level
                    SendCommandCloud(DeviceID, 'colour_data', hvs)
                    # Update status of Domoticz device
                    UpdateDevice(DeviceID, 1, Level, 1, 0)
                    UpdateDevice(DeviceID, 1, Color, 1, 0) 

        if dev_type == ('cover'):
            if Command == 'Open':
                # Set new state
                SendCommandCloud(DeviceID, 'switch_1', False)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'Open', 0, 0)
            elif Command == 'Close':
                # Set new state
                SendCommandCloud(DeviceID, 'switch_1', True)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'Close', 1, 0)
            elif Command == 'Stop':
                # Set new state
                SendCommandCloud(DeviceID, 'switch_1', True)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'Stop', 1, 0)
            elif Command == 'Set Level':
                # Set new state
                SendCommandCloud(DeviceID, 'switch_1', True)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, Level, 1, 0)
                
        elif dev_type == 'Heater':
            if Command == 'Off':
                # Set new level
                SendCommandCloud(DeviceID, 'switch', False)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'Off', 0, 0)
            elif Command == 'On':
                # Set new level
                SendCommandCloud(DeviceID, 'switch', True)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 1, 'On', 1, 0)
            elif Command == 'Set Level':
                # Set new level
                SendCommandCloud(DeviceID, 'temp_set', Level)
                # Update status of Domoticz device
                UpdateDevice(DeviceID, 3, Level, 1, 0)

        # Set last update
        # self.last_update = time.time()

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log('Notification: ' + Name + ', ' + Subject + ', ' + Text + ', ' + Status + ', ' + str(Priority) + ', ' + Sound + ', ' + ImageFile)

    def onDeviceRemoved(self, DeviceID, Unit):
        Domoticz.Log('onDeviceDeleted called')
        # device for the Domoticz
        Devices[DeviceID].Units[Unit].Delete
        Domoticz.Debug('Device ID: ' + str(DeviceID) + ' delete')
    
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
            tuya = tinytuya.Cloud(apiRegion=Parameters['Mode1'], apiKey=Parameters['Username'], apiSecret=Parameters['Password'], apiDeviceID=Parameters['Mode2'])
            devs = tuya.getdevices()
            token = tuya.token
            # Check credentials
            if 'sign invalid' in str(token):
                raise Exception('Credentials are incorrect!')

            # Check ID search device is valid
            if 'permission deny' in str(devs):
                raise Exception('ID search device not found!')

        # Initialize/Update devices from TUYA API
        devs = tuya.getdevices(verbose=False)
        for dev in devs:
            Domoticz.Debug( 'Device name=' + str(dev['name']) + ' id=' + str(dev['id']))
            functions = tuya.getfunctions(dev['id'])['result']['functions']
            online = tuya.getconnectstatus(dev['id'])
            result = tuya.getstatus(dev['id'])['result']
            dev_type = DeviceType(tuya.getfunctions(dev['id'])['result']['category'])
            
            # Create devices
            if startup == True:
                Domoticz.Debug('Create devices')
                deviceinfo = tinytuya.find_device(dev['id'])
                
                if dev['id'] not in Devices:
                    if dev_type == 'light':
                        # for localcontol: and deviceinfo['ip'] != None
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
                        else:
                            # Error
                            Domoticz.Error('No controls found for your light device!')
                    # elif dev_type == 'climate':
                    #     Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=16, Used = 1).Create()
                    # elif dev_type == 'fan':
                    #     Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=7, Used = 1).Create()
                    # elif dev_type == 'lock':
                    #     Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=11, Used = 1).Create()
                    elif dev_type == 'cover':
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=3, Used = 1).Create()
                    elif dev_type == 'switch':
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used = 1).Create()
                    elif dev_type == 'heater':
                        Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=15, Used = 1).Create()
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=2, Type=80, Subtype=5, Used = 1).Create()
                        Domoticz.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev['id'], Unit=3, Type=242, Subtype=1, Used = 1).Create()
                        
                    else:
                        Domoticz.Error('No controls found for your device!')
                # Set extra info
                setConfigItem(dev['id'], {'key': dev['key'], 'category': dev_type,  'mac': dev['mac'], 'ip': deviceinfo['ip'], 'version': deviceinfo['version'] })

            # Check device is removed
            if dev['id'] not in str(Devices):
                raise Exception('Device not found! Device removed or Accept New Hardware not active?')

            #update devices in Domoticz
            Domoticz.Debug('Update devices in Domoticz')
            # Domoticz.Debug('Test script:' + str(getConfigItem(dev['id'])))
            
            if online == False and Devices[dev['id']].TimedOut == 0:
                UpdateDevice(dev['id'], 1, 'Off', 0, 1)
            elif online == True and Devices[dev['id']].TimedOut == 1:
                UpdateDevice(dev['id'], 1, 'Off' if StatusDeviceTuya(dev['id'], 'switch_led') == False else 'On', 0, 0)                
            elif online == True and Devices[dev['id']].TimedOut == 0:
                try:
                    # Status Tuya
                    if 'switch_led' in str(result):
                        currentstatus = StatusDeviceTuya(dev['id'], 'switch_led')
                    elif 'switch_1' in str(result):
                        currentstatus = StatusDeviceTuya(dev['id'], 'switch_1')
                    elif 'switch' in str(result):
                        currentstatus = StatusDeviceTuya(dev['id'], 'switch')

                    # workmode = StatusDeviceTuya(dev['id'], 'work_mode')
                    if 'bright_value' in str(result):
                        dimtuya = brightness_to_pct(str(StatusDeviceTuya(dev['id'], 'bright_value')))
                    '''
                    Finding other way to detect
                    if 'temp_value' in str(result):
                        temptuya = {'m': 2, 't': int(inv_val(round(StatusDeviceTuya(dev['id'], 'temp_value'))))}
                    if 'colour_data' in str(result):
                        colortuya = ast.literal_eval(StatusDeviceTuya(dev['id'], 'colour_data'))
                        rtuya, gtuya, btuya = hsv_to_rgb(colortuya['h'],colortuya['s'],colortuya['v'])
                        colorupdate = {'m': 3, 'r': rtuya, 'g': gtuya, 'b': btuya}
                    '''
                    # status Domoticz
                    sValue = Devices[dev['id']].Units[1].sValue
                    nValue = Devices[dev['id']].Units[1].nValue
                    '''
                    dimlevel = Devices[dev['id']].Units[1].sValue if type(Devices[dev['id']].Units[1].sValue) == int else dimtuya
                    color = Devices[dev['id']].Units[1].Color
                    '''

                    if dev_type == 'switch':
                        if currentstatus == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif currentstatus == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)

                    if dev_type in ('light', 'dimmer'):
                        if (currentstatus == False and bool(nValue) != False) or int(dimtuya) == 0:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif (currentstatus == True and bool(nValue) != True) or str(dimtuya) != str(sValue):
                                UpdateDevice(dev['id'], 1, int(dimtuya), 1, 0)
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
                        if currentstatus == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif currentstatus == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)

                    if dev_type == 'heater':
                        if currentstatus == False:
                            UpdateDevice(dev['id'], 1, 'Off', 0, 0)
                        elif currentstatus == True:
                            UpdateDevice(dev['id'], 1, 'On', 1, 0)
                        if 'temp_current' in str(result):
                            currenttemp = StatusDeviceTuya(dev['id'], 'temp_current')
                            UpdateDevice(dev['id'], 2, currenttemp, 1, 0)
                        if 'temp_set' in str(result):
                            currenttemp_set = StatusDeviceTuya(dev['id'], 'temp_set')
                            UpdateDevice(dev['id'], 2, currenttemp_set, 1, 0)

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
    if category in {'kg', 'cz', 'pc', 'dlq', 'bh'}:
        result = 'switch'
    elif category in {'tgq', 'tgkg'}:
        result = 'dimmer'
    elif category in {'dj', 'dd', 'fwl', 'dc', 'xdd', 'fsd', 'fwd', 'gyd', 'jsq', 'tyndj', 'ykq'}:
        result = 'light'
    elif category in {'cl', 'clkg', 'jdcljqr'}:
        result = 'cover'
    elif category in {'qn'}:
        result = 'heater'
    else:
        result = 'unknown'
    return result

def UpdateDevice(ID, Unit, sValue, nValue, TimedOut):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    Domoticz.Debug(type(sValue))
    if ID in Devices:
        if Devices[ID].Units[Unit].sValue != sValue or Devices[ID].Units[Unit].nValue != nValue or Devices[ID].TimedOut != TimedOut:
            Devices[ID].Units[Unit].sValue = str(sValue)
            if type(sValue) == int:
                Devices[ID].Units[Unit].LastLevel = sValue
            elif type(sValue) == dict:
                Devices[ID].Units[Unit].Color = json.dumps(sValue)
            Devices[ID].Units[Unit].nValue = nValue
            Devices[ID].TimedOut = TimedOut
            Devices[ID].Units[Unit].Update()

    Domoticz.Debug('Update device value:' + str(ID) + ' Unit: ' + str(Unit) + ' sValue: ' +  str(sValue) + ' nValue: ' + str(nValue) + ' TimedOut=' + str(TimedOut))
    return

def StatusDeviceTuya(ID, Function):
    if Function in str(tuya.getstatus(ID)['result']):
        valueT = [item['value'] for item in tuya.getstatus(ID)['result'] if item['code'] == Function][0]
    else:
        valueT = None
        Domoticz.Debug('StatusDeviceTuya caled ' + Function + ' not found ')
    return valueT

def SendCommandCloud(ID, Name, Status):
    tuya.sendcommand(ID, {'commands': [{'code': Name, 'value': Status}]})
    Domoticz.Debug('Command send to tuya :' + str({'commands': [{'code': Name, 'value': Status}]}))

def pct_to_brightness(p):
    # Convert a percentage to a raw value 1% = 25 => 100% = 255
    result = round(22.68 + (int(p) * ((255 - 22.68) / 100)))
    return result
    
def brightness_to_pct(v):
    # Convert a raw to a percentage value 25 = 1% => 255 = 100%
    result = round((100 / (255 - 22.68) * (int(v) - 22.68)))
    return result

def rgb_to_hsv(r, g, b):
    h,s,v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h = int(h * 360)
    s = int(s * 255)
    v = int(v * 255)
    return h, s, v

def hsv_to_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h / 360, s / 255, v / 255) 
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