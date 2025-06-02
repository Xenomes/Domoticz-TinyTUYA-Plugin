# Domoticz TUYA Plugin
#
# Author: Xenomes (xenomes@outlook.com)
#
"""
<plugin key="tinytuya" name="TinyTUYA (Cloud)" author="Xenomes" version="3.0.0" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin.git">
    <description>
        Support forum: <a href="https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441">https://www.domoticz.com/forum/viewtopic.php?f=65&amp;t=39441</a><br/>
        <br/>
        <h2>TinyTUYA Plugin version 3.0.0</h2><br/>
        The plugin make use of IoT Cloud Platform account for setup up see https://github.com/jasonacox/tinytuya step 3 or see PDF https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Auto-detection of devices on network</li>
            <li>On/Off control, state and available status display</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>Many devices are supported.</li>
        </ul>
        <h3>Configuration</h3>
        <ul style="list-style-type:square">
        <li>Enter your Region, Access ID/Client ID, Access Secret/Client Secret, and a Search deviceID from your Tuya IOT Account. Synchronizing time: Tuya has changed the total number of pulses an account can make. Very old accounts can use a 1-minute interval, while others are advised to use a 15-minute interval. Keep the 'Data Timeout' setting disabled.</li>
        <li>A deviceID can be found in your Tuya IOT account. Go to Cloud => your project => Devices => Select one of your device IDs. (This ID is used to detect all the other devices.)</li>
        <li>Complete the initial setup of your devices using the app, and this plugin will automatically detect and use the same settings to find and add the devices into Domoticz.<br/></li>
        <li>When Pulsar is used, the tuya-connector-python module meets to be installed and the message service on iot.tuya.com needs to be enabled!</li>
        <li>Set the API polling interval in order not to exhaust your calls allocation before the end of the period.</li>
        </ul>
        If your subscription to the cloud development plan has expired, you can extend it &nbsp; <a href="https://iot.tuya.com/cloud/products/apply-extension">HERE</a><br/>
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
        <param field="Mode4" label="Calling service" width="300px" required="true" default="Default">
            <options>
                <option label="Default" value="Default" />
                <option label="Pulsar" value="Pulsar" />
            </options>
        </param>
        <param field="Mode3" label="API Polling interval" width="150px" required="true" default="15 minutes">
            <options>
                <option label="1 minute" value="60" />
                <option label="5 minutes" value="300" />
                <option label="10 minutes" value="600" />
                <option label="15 minutes" value="900"  default="true"/>
                <option label="30 minutes" value="1800" />
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
import queue
import threading

try:
    import DomoticzEx as Domoticz
except ImportError:
    import fakeDomoticz as Domoticz
try:
    import tinytuya
except ImportError:
    Domoticz.Error('No tinytuya module installed')
try:
    from tuya_connector import TuyaOpenAPI, TuyaOpenPulsar, TuyaCloudPulsarTopic
except ImportError:
    Domoticz.Error('No tuya-connector-python module installed')

class BasePlugin:
    def __init__(self):
        self.enabled = True
        global messageQueue
        # Start the worker thread
        messageQueue = queue.Queue()
        self.messageThread = threading.Thread(name="QueueThread", target=BasePlugin.handleMessage, args=(self,))
        return

    # Worker function to process messages
    def handleMessage(self):
        global open_pulsar
        Domoticz.Debug("Initializing Pulsar client")
        # Initialize tuya-connector
        openapi = TuyaOpenAPI("https://openapi.tuya" + Parameters['Mode1'] + ".com", Parameters['Username'], Parameters['Password'])
        openapi.connect()

        # Call any API from Tuya
        response = openapi.get("/v1.0/statistics-datas-survey", dict())

        # Init Message Queue
        open_pulsar = TuyaOpenPulsar(
            Parameters['Username'], Parameters['Password'], "wss://mqe.tuya" + Parameters['Mode1'] + ".com:8285/", TuyaCloudPulsarTopic.PROD
        )
        # Add Message Queue listener
        open_pulsar.add_message_listener(messageQueue.put)

        # Start Message Queue
        open_pulsar.start()

    def onStart(self):
        if Parameters['Mode6'] != '0':
            Domoticz.Debugging(int(Parameters['Mode6']))
            # Domoticz.Log('Debugger started, use 'telnet 0.0.0.0 4444' to connect')
            # import rpdb
            # rpdb.set_trace()
            DumpConfigToLog()

        Domoticz.Log('TinyTUYA ' + Parameters['Version'] + ' plugin started')
        Domoticz.Log('TinyTuyaVersion: ' + tinytuya.version )

        global pulsaractive, testData, Error

        if Parameters['Mode4'] == 'Pulsar':
            Domoticz.Log('Pulsar Active')
            pulsaractive = True
            testData = False
            Error = None
            self.messageThread.start()
        else:
            pulsaractive = False

        if os.path.isfile(Parameters['HomeFolder'] + '/debug_devices.json'):
            testData = True
            Domoticz.Heartbeat(5)
            Domoticz.Error('!!! Warning Plugin overruled by local json files !!!')
        else:
            testData = False
            if pulsaractive:
                Domoticz.Heartbeat(2)
            else:
                Domoticz.Heartbeat(10)
        onHandleThread(True)

    def onStop(self):
        Domoticz.Log('onStop called')

        try:
            # Cleanup devices that are not recognized
            devs = Devices
            for dev in devs:
                if 'This device is not recognized.' in Devices[dev].Units[1].sValue:
                    Devices[dev].Units[1].Delete()
        except Exception as e:
            Domoticz.Log(f"Error during device cleanup: {e}")

        # Start the shutdown process
        start_time = time.time()

        try:
            if len(str(open_pulsar)) != 0:
                # Attempt to stop Pulsar gracefully
                Domoticz.Log("Stopping Pulsar message queue...")
                open_pulsar.stop()
        except:
            return

        # Polling for active threads and timeout mechanism
        while True:
            # Get active threads excluding the current thread
            active_threads = [thread for thread in threading.enumerate() if thread.name != threading.current_thread().name]

            # Check if no active threads remain
            if len(active_threads) == 0:
                Domoticz.Log("No active threads left, exiting plugin.")
                break

            # Check if we've exceeded the timeout
            if time.time() - start_time > 60:  # 60 seconds timeout
                Domoticz.Log("Timeout reached, some threads may not have finished. Exiting plugin.")
                break

            # Log number of threads still running
            Domoticz.Log(f"{len(active_threads)} threads still running, waiting...")

            # Sleep for a while to avoid constant polling
            time.sleep(5.0)

        Domoticz.Log("Exiting plugin.")


    def onConnect(self, Connection, Status, Description):
        Domoticz.Log('onConnect called')

    def onMessage(self, Connection, Data):
        Domoticz.Log('onMessage called')

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Domoticz.Debug("onCommand called for Device " +
                       str(DeviceID) + " Unit " +
                       str(Unit) + ": Parameter '" +
                       str(Command) + "', Level: " +
                       str(Level) + "', Color: " +
                       str(Color))

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
            # product_id = getConfigItem(DeviceID, 'product_id')
            function = properties[DeviceID]['functions']
            # status = properties[DeviceID]['status']
            if len(Color) != 0: Color = ast.literal_eval(Color)

            if dev_type == 'switch':
                if searchCode('switch', function):
                    if Command == 'Off':
                        SendCommandCloud(DeviceID, 'switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandCloud(DeviceID, 'switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)
                else:
                    if Command == 'Off':
                        SendCommandCloud(DeviceID, 'switch_' + str(Unit), False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandCloud(DeviceID, 'switch_' + str(Unit), True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)

            if dev_type == 'wswitch':
                if Command == 'Set Level':
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    if searchCode('switch' + str(Unit) + '_value', function):
                        SendCommandCloud(DeviceID, 'switch' + str(Unit) + '_value', mode[int(Level / 10)])
                    if searchCode('switch_type_' + str(Unit), function):
                        SendCommandCloud(DeviceID, 'switch_type_' + str(Unit), mode[int(Level / 10)])
                    if searchCode('switch_mode' + str(Unit), function):
                        SendCommandCloud(DeviceID, 'switch_mode' + str(Unit), mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)

            elif dev_type in ('dimmer'):
                if Command == 'Off':
                    SendCommandCloud(DeviceID, 'switch_led_' + str(Unit), False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'Set Level':
                    SendCommandCloud(DeviceID, 'switch_led_' + str(Unit), True)
                    SendCommandCloud(DeviceID, 'bright_value_' + str(Unit), Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)

            elif dev_type in ('light') or ((dev_type in ('fanlight') or dev_type in ('pirlight')) and Unit == 1):
                switch = 'led_switch' if searchCode('led_switch', function) else 'switch_led'
                if Command == 'Off':
                    SendCommandCloud(DeviceID, switch, False)
                    UpdateDevice(DeviceID, 1, False, 0, 0)
                elif Command == 'On':
                    SendCommandCloud(DeviceID, switch, True)
                    UpdateDevice(DeviceID, 1, True, 1, 0)
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
                ext = '_' + str(Unit) if Unit > 1 else ''
                if Command == 'Open':
                    if searchCode('mach_operate' + ext, function):
                        SendCommandCloud(DeviceID, 'mach_operate' + ext, 'FZ')
                    else:
                        SendCommandCloud(DeviceID, 'control' + ext, 'open')
                    UpdateDevice(DeviceID, Unit, 'Open', 0, 0)
                elif Command == 'Close':
                    if searchCode('mach_operate' + ext, function):
                        SendCommandCloud(DeviceID, 'mach_operate' + ext, 'ZZ')
                    else:
                        SendCommandCloud(DeviceID, 'control' + ext, 'close')
                    UpdateDevice(DeviceID, Unit, 'Close', 1, 0)
                elif Command == 'Stop':
                    if searchCode('mach_operate' + ext, function):
                        SendCommandCloud(DeviceID, 'mach_operate' + ext, 'STOP')
                    else:
                        SendCommandCloud(DeviceID, 'control' + ext, 'stop')
                    UpdateDevice(DeviceID, Unit, 'Stop', 1, 0)
                elif Command == 'Set Level':
                    if searchCode('percent_control' + ext, function):
                        control = 'percent_control' + ext
                    elif searchCode('position' + ext, function):
                        control = 'position' + ext
                    SendCommandCloud(DeviceID, control, Level)
                    UpdateDevice(DeviceID, 1, Level, 1, 0)

            elif dev_type == 'smartheatpump' :
                if searchCode('switch', function):
                    switch = 'switch'
                    if Command == 'Off' and Unit == 1:
                        SendCommandCloud(DeviceID, switch, False)
                        UpdateDevice(DeviceID, 1, False, 0, 0)
                    elif Command == 'On' and Unit == 1:
                        SendCommandCloud(DeviceID, switch, True)
                        UpdateDevice(DeviceID, 1, True, 1, 0)
                if searchCode('ach_stemp', function):
                    switch = 'ach_stemp'
                    if Command == 'Set Level' and Unit  == 11:
                        SendCommandCloud(DeviceID, switch, Level)
                        UpdateDevice(DeviceID, 11, Level, 1, 0)
                if searchCode('wth_stemp', function):
                    switch = 'wth_stemp'
                    if Command == 'Set Level' and Unit  == 12:
                        SendCommandCloud(DeviceID, switch, Level)
                        UpdateDevice(DeviceID, 12, Level, 1, 0)
                if searchCode('aircond_temp_diff', function):
                    switch = 'aircond_temp_diff'
                    if Command == 'Set Level' and Unit  == 13:
                        SendCommandCloud(DeviceID, switch, Level)
                        UpdateDevice(DeviceID, 13, Level, 1, 0)
                if searchCode('wth_temp_diff', function):
                    switch = 'wth_temp_diff'
                    if Command == 'Set Level' and Unit  == 14:
                        SendCommandCloud(DeviceID, switch, Level)
                        UpdateDevice(DeviceID, 14, Level, 1, 0)
                if searchCode('acc_stemp', function):
                    switch = 'acc_stemp'
                    if Command == 'Set Level' and Unit  == 15:
                        SendCommandCloud(DeviceID, switch, Level)
                        UpdateDevice(DeviceID, 15, Level, 1, 0)
                if searchCode('mode', function):
                    if Command == 'Set Level' and Unit == 16:
                        mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 16, Level, 1, 0)
                if searchCode('work_mode', function):
                    if Command == 'Set Level' and Unit == 17:
                        mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 'work_mode', mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 17, Level, 1, 0)
                if searchCode('temp_set', function):
                    switch = 'temp_set'
                    if Command == 'Set Level' and Unit  == 19:
                        SendCommandCloud(DeviceID, switch, Level)
                        UpdateDevice(DeviceID, 19, Level, 1, 0)
                # if searchCode('water_set', function):
                #     switch = 'water_set'
                #     if Command == 'Set Level' and Unit  == 20:
                #         SendCommandCloud(DeviceID, switch, Level)
                #         UpdateDevice(DeviceID, 20, Level, 1, 0)
                if searchCode('compressor_state', function):
                    switch = 'compressor_state'
                    if Command == 'Off' and Unit == 24:
                        SendCommandCloud(DeviceID, switch, False)
                        UpdateDevice(DeviceID, 24, False, 0, 0)
                    elif Command == 'On' and Unit == 24:
                        SendCommandCloud(DeviceID, switch, True)
                        UpdateDevice(DeviceID, 24, True, 1, 0)

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
                    SendCommandCloud(DeviceID, switch, False)
                    UpdateDevice(DeviceID, 1, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, switch, True)
                    UpdateDevice(DeviceID, 1, True, 1, 0)
                elif Command == 'Set Level' and Unit  == 3:
                    SendCommandCloud(DeviceID, switch3, Level)
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, switch4, mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 4, Level, 1, 0)
                if Command == 'Off' and Unit == 5:
                    SendCommandCloud(DeviceID, 'window_check', False)
                    UpdateDevice(DeviceID, 5, False, 0, 0)
                elif Command == 'On' and Unit == 5:
                    SendCommandCloud(DeviceID, 'window_check', True)
                    UpdateDevice(DeviceID, 5, True, 1, 0)
                if Command == 'Off' and Unit == 6:
                    SendCommandCloud(DeviceID, 'child_lock', False)
                    UpdateDevice(DeviceID, 6, False, 0, 0)
                elif Command == 'On' and Unit == 6:
                    SendCommandCloud(DeviceID, 'child_lock', True)
                    UpdateDevice(DeviceID, 6, True, 1, 0)
                if Command == 'Off' and Unit == 7:
                    SendCommandCloud(DeviceID, 'eco', False)
                    UpdateDevice(DeviceID, 7, False, 0, 0)
                elif Command == 'On' and Unit == 7:
                    SendCommandCloud(DeviceID, 'eco', True)
                    UpdateDevice(DeviceID, 7, True, 1, 0)
                elif Command == 'Set Level' and Unit  == 9:
                    if searchCode('fan_level', function) or searchCode('fan_speed_enum', function):
                        mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                        SendCommandCloud(DeviceID, 9, mode[int(Level / 10)])
                        UpdateDevice(DeviceID, 9, Level, 1, 0)
                    else:
                        wind = 'windspeed'
                        SendCommandCloud(DeviceID, wind, Level)
                        UpdateDevice(DeviceID, 9, Level, 1, 0)
                if Command == 'Off' and Unit == 17:
                    SendCommandCloud(DeviceID, 'anti_bother', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 17:
                    SendCommandCloud(DeviceID, 'anti_bother', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)

            if dev_type == 'sensor':
                if Command == 'Set Level' and Unit == 15:
                    SendCommandCloud(DeviceID, 'ph_warn_min', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 16:
                    SendCommandCloud(DeviceID, 'ph_warn_max', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 17:
                    SendCommandCloud(DeviceID, 'pro_warn_min', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 18:
                    SendCommandCloud(DeviceID, 'pro_warn_max', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 19:
                    SendCommandCloud(DeviceID, 'orp_warn_min', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 20:
                    SendCommandCloud(DeviceID, 'orp_warn_max', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 24:
                    SendCommandCloud(DeviceID, 'temp_warn_min', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 25:
                    SendCommandCloud(DeviceID, 'temp_warn_max', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 45:
                    SendCommandCloud(DeviceID, 'cook_temperature', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Set Level' and Unit == 46:
                    SendCommandCloud(DeviceID, 'cook_temperature_2', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                # if Command == 'Off' and Unit == 47:
                #     SendCommandCloud(DeviceID, 'alarm_switch', False)
                #     UpdateDevice(DeviceID, Unit, False, 0, 0)
                # elif Command == 'On' and Unit == 47:
                #     SendCommandCloud(DeviceID, 'alarm_switch', True)
                #     UpdateDevice(DeviceID, Unit, True, 1, 0)

            if dev_type == 'doorbell':
                if Command == 'Off' and Unit == 2:
                    SendCommandCloud(DeviceID, 'floodlight_switch', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 2:
                    SendCommandCloud(DeviceID, 'floodlight_switch', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)

            if dev_type == 'fan':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                elif Command == 'Set Level' and Unit == 2:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'fan_speed', int(mode[int(Level / 10)]))
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit  == 4:
                    SendCommandCloud(DeviceID, 'set_temp', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                if Command == 'Off' and Unit == 7:
                    SendCommandCloud(DeviceID, 'light', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 7:
                    SendCommandCloud(DeviceID, 'light', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                if Command == 'Off' and Unit == 8:
                    SendCommandCloud(DeviceID, 'RH_switch', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 8:
                    SendCommandCloud(DeviceID, 'RH_switch', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                if Command == 'Off' and Unit == 11:
                    SendCommandCloud(DeviceID, 'anion', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 11:
                    SendCommandCloud(DeviceID, 'anion', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                if Command == 'Off' and Unit == 12:
                    SendCommandCloud(DeviceID, 'free_cooling', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 12:
                    SendCommandCloud(DeviceID, 'free_cooling', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                if Command == 'Off' and Unit == 13:
                    SendCommandCloud(DeviceID, 'powerful', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 13:
                    SendCommandCloud(DeviceID, 'powerful', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)

            if dev_type == 'fanlight':
                if Command == 'Off' and Unit == 2:
                    SendCommandCloud(DeviceID, 'fan_switch', False)
                    UpdateDevice(DeviceID, 2, False, 0, 0)
                elif Command == 'On' and Unit == 2:
                    SendCommandCloud(DeviceID, 'fan_switch', True)
                    UpdateDevice(DeviceID, 2, True, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'fan_speed', int(mode[int(Level / 10)]))
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'fan_direction', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 4, Level, 1, 0)

            if dev_type == 'powermeter' and searchCode('switch', function):
                if Command == 'Off':
                    SendCommandCloud(DeviceID, 'switch', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On':
                    SendCommandCloud(DeviceID, 'switch', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)

            if dev_type == 'powermeter' and searchCode('switch_1', function):
                if Command == 'Off':
                    SendCommandCloud(DeviceID, 'switch_1', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On':
                    SendCommandCloud(DeviceID, 'switch_1', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)

            if dev_type == 'siren':
                if Command == 'Off':
                    SendCommandCloud(DeviceID, 'AlarmSwitch', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On':
                    SendCommandCloud(DeviceID, 'AlarmSwitch', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                elif Command == 'Set Level' and Unit == 2:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 2, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'Alarmtype', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                # Other Type of alarm with same code
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'muffling', False)
                    UpdateDevice(DeviceID, 1, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'muffling', True)
                    UpdateDevice(DeviceID, 1, True, 1, 0)
                elif Command == 'Set Level' and Unit == 2:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'alarm_state', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 2, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'alarm_volume', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 3, Level, 1, 0)

            if dev_type == 'pirlight':
                if Command == 'Off' and Unit == 2:
                    SendCommandCloud(DeviceID, 'switch_pir', False)
                    UpdateDevice(DeviceID, 2, False, 0, 0)
                elif Command == 'On' and Unit == 2:
                    SendCommandCloud(DeviceID, 'switch_pir', True)
                    UpdateDevice(DeviceID, 2, True, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'device_mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'pir_sensitivity', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 4, Level, 1, 0)

            if dev_type == 'garagedooropener':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch_1', False)
                    UpdateDevice(DeviceID, 1, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch_1', True)
                    UpdateDevice(DeviceID, 1, True, 1, 0)

            if dev_type == 'feeder':
                if Command == 'Off' and Unit == 5:
                    SendCommandCloud(DeviceID, 'light', False)
                    UpdateDevice(DeviceID, 5, False, 0, 0)
                elif Command == 'On' and Unit == 5:
                    SendCommandCloud(DeviceID, 'light', True)
                    UpdateDevice(DeviceID, 5, True, 1, 0)
                elif Command == 'Set Level' and Unit == 1:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'manual_feed', int(mode[int(Level / 10)]))
                    UpdateDevice(DeviceID, 1, Level, 1, 0)

            if dev_type == 'irrigation':
                if searchCode('switch_1', function):
                    switch = 'switch_1'
                else:
                    switch = 'switch'
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, switch, False)
                    UpdateDevice(DeviceID, 1, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, switch, True)
                    UpdateDevice(DeviceID, 1, True, 1, 0)
                if Command == 'Off' and Unit == 3:
                    SendCommandCloud(DeviceID, 'areaone', False)
                    UpdateDevice(DeviceID, 3, False, 0, 0)
                elif Command == 'On' and Unit == 3:
                    SendCommandCloud(DeviceID, 'areaone', True)
                    UpdateDevice(DeviceID, 3, True, 1, 0)
                if Command == 'Off' and Unit == 4:
                    SendCommandCloud(DeviceID, 'areatwo', False)
                    UpdateDevice(DeviceID, 4, False, 0, 0)
                elif Command == 'On' and Unit == 4:
                    SendCommandCloud(DeviceID, 'areatwo', True)
                    UpdateDevice(DeviceID, 4, True, 1, 0)
                if Command == 'Off' and Unit == 5:
                    SendCommandCloud(DeviceID, 'areathree', False)
                    UpdateDevice(DeviceID, 5, False, 0, 0)
                elif Command == 'On' and Unit == 5:
                    SendCommandCloud(DeviceID, 'areathree', True)
                    UpdateDevice(DeviceID, 5, True, 1, 0)
                if Command == 'Off' and Unit == 6:
                    SendCommandCloud(DeviceID, 'areafour', False)
                    UpdateDevice(DeviceID, 6, False, 0, 0)
                elif Command == 'On' and Unit == 6:
                    SendCommandCloud(DeviceID, 'areafour', True)
                    UpdateDevice(DeviceID, 6, True, 1, 0)
                if Command == 'Off' and Unit == 7:
                    SendCommandCloud(DeviceID, 'areafive', False)
                    UpdateDevice(DeviceID, 7, False, 0, 0)
                elif Command == 'On' and Unit == 7:
                    SendCommandCloud(DeviceID, 'areafive', True)
                    UpdateDevice(DeviceID, 7, True, 1, 0)
                if Command == 'Off' and Unit == 8:
                    SendCommandCloud(DeviceID, 'areasix', False)
                    UpdateDevice(DeviceID, 8, False, 0, 0)
                elif Command == 'On' and Unit == 8:
                    SendCommandCloud(DeviceID, 'areasix', True)
                    UpdateDevice(DeviceID, 8, True, 1, 0)

            if dev_type == 'starlight':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch_led', False)
                    SendCommandCloud(DeviceID, 'colour_switch', False)
                    UpdateDevice(DeviceID, 1, False, 0, 0)
                    UpdateDevice(DeviceID, 2, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch_led', True)
                    SendCommandCloud(DeviceID, 'colour_switch', True)
                    UpdateDevice(DeviceID, 1, True, 1, 0)
                    UpdateDevice(DeviceID, 2, True, 1, 0)
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
                    UpdateDevice(DeviceID, 2, False, 0, 0)
                    UpdateDevice(DeviceID, 1, False, 0, 0)
                elif Command == 'On' and Unit == 2:
                    SendCommandCloud(DeviceID, 'colour_switch', True)
                    UpdateDevice(DeviceID, 2, True, 1, 0)
                    UpdateDevice(DeviceID, 1, True, 1, 0)
                if Command == 'Off' and Unit == 3:
                    SendCommandCloud(DeviceID, 'laser_switch', False)
                    UpdateDevice(DeviceID, 3, False, 0, 0)
                elif Command == 'On' and Unit == 3:
                    SendCommandCloud(DeviceID, 'laser_switch', True)
                    UpdateDevice(DeviceID, 3, True, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    SendCommandCloud(DeviceID, 'laser_switch', True)
                    SendCommandCloud(DeviceID, 'laser_bright', 21.25 + ((Level / 100) * 78.75)) # 21.25 + ((Level / 100) * 78.75) ) * 10
                    UpdateDevice(DeviceID, 3, True, 1, 0)
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                if Command == 'Off' and Unit == 4:
                    SendCommandCloud(DeviceID, 'fan_switch', False)
                    UpdateDevice(DeviceID, 4, False, 0, 0)
                elif Command == 'On' and Unit == 4:
                    SendCommandCloud(DeviceID, 'fan_switch', True)
                    UpdateDevice(DeviceID, 4, True, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    SendCommandCloud(DeviceID, 'fan_switch', True)
                    SendCommandCloud(DeviceID, 'fan_speed', Level)
                    UpdateDevice(DeviceID, 4, True, 1, 0)
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
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                elif Command == 'Set Level' and Unit == 2:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    if searchCode('dehumidify_set_value', function):
                        tdev = 'dehumidify_set_value'
                    elif searchCode('dehumidify_set_enum', function):
                        tdev = 'dehumidify_set_enum'
                    SendCommandCloud(DeviceID, tdev, mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'fan_speed_enum', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)

            if dev_type == 'vacuum':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'power_go', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'power_go', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'suction', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 5:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'cistern', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)

            if dev_type == 'purifier':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'switch', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'mode', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'speed', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)

            if dev_type == 'smartkettle':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'start', False)
                    UpdateDevice(DeviceID, Unit, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'start', True)
                    UpdateDevice(DeviceID, Unit, True, 1, 0)
                elif Command == 'Set Level' and Unit  == 4:
                    SendCommandCloud(DeviceID, 'cook_temperature', Level)
                    UpdateDevice(DeviceID, 4, Level, 1, 0)

            if dev_type == 'mower':
                if Command == 'Set Level' and Unit == 1:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'MachineControlCmd', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 1, Level, 1, 0)
                if Command == 'Off' and Unit == 2:
                    SendCommandCloud(DeviceID, 'MachineRainMode', False)
                    UpdateDevice(DeviceID, 2, False, 0, 0)
                elif Command == 'On' and Unit == 2:
                    SendCommandCloud(DeviceID, 'MachineRainMode', True)
                    UpdateDevice(DeviceID, 2, True, 1, 0)

            if dev_type == 'human_presence':
                if Command == 'Set Level' and Unit == 2:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'sensitivity', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit  == 3:
                    SendCommandCloud(DeviceID, 'near_detection', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)
                elif Command == 'Set Level' and Unit  == 4:
                    SendCommandCloud(DeviceID, 'far_detection', Level)
                    UpdateDevice(DeviceID, Unit, Level, 1, 0)

            if dev_type == 'evcharger':
                if searchCode('switch', function):
                    if Command == 'Off':
                        SendCommandCloud(DeviceID, 'switch', False)
                        UpdateDevice(DeviceID, Unit, False, 0, 0)
                    elif Command == 'On':
                        SendCommandCloud(DeviceID, 'switch', True)
                        UpdateDevice(DeviceID, Unit, True, 1, 0)

            if dev_type == 'infrared_ac':
                if Command == 'Off' and Unit == 1:
                    SendCommandCloud(DeviceID, 'PowerOff', 'PowerOff')
                    UpdateDevice(DeviceID, 1, False, 0, 0)
                elif Command == 'On' and Unit == 1:
                    SendCommandCloud(DeviceID, 'PowerOn', 'PowerOn')
                    UpdateDevice(DeviceID, 1, True, 1, 0)
                elif Command == 'Set Level' and Unit  == 2:
                    SendCommandCloud(DeviceID, 'T', Level)
                    UpdateDevice(DeviceID, 2, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 3:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'M', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 3, Level, 1, 0)
                elif Command == 'Set Level' and Unit == 4:
                    mode = getConfigItem(DeviceID + '-' + str(Unit), 'mode') if not None else Devices[DeviceID].Units[Unit].Options['LevelNames'].split('|')
                    SendCommandCloud(DeviceID, 'F', mode[int(Level / 10)])
                    UpdateDevice(DeviceID, 4, Level, 1, 0)

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log('Notification: ' + Name + ', ' + Subject + ', ' + Text + ', ' + Status + ', ' + str(Priority) + ', ' + Sound + ', ' + ImageFile)

    def onDeviceRemoved(self, DeviceID, Unit):
        Domoticz.Log('onDeviceDeleted called')

    def onDisconnect(self, Connection):
        Domoticz.Log('onDisconnect called')

    def onHeartbeat(self):
        Domoticz.Debug('onHeartbeat called')
        if time.time() - last_update < synctime and testData == False and pulsaractive == False:
            Domoticz.Debug("onHeartbeat called skipped, " +  str(int(time.time() - last_update)) + " < " + str(synctime) + " seconds")
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
            global tuya, devs, properties, result, FunctionProperties, StatusProperties, ResultValue, Error, last_update, product_id, t, synctime
            last_update = time.time()
            try:
                synctime = int(Parameters['Mode3'])
            except ValueError:
                synctime = 900
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
                if 'tuya' not in globals():
                    tuya = tinytuya.Cloud(apiRegion=Parameters['Mode1'], apiKey=Parameters['Username'], apiSecret=Parameters['Password'], apiDeviceID=Parameters['Mode2'])
                tuya.use_old_device_list = True
                tuya.new_sign_algorithm = True
                Error = tuya.error

                if Error is not None:
                    raise Exception(Error['Payload'])
                if 'devs' not in globals():
                    devs = []
                    i = 0
                    while len(devs) == 0 and i < 4:
                        try:
                            devs = tuya.getdevices()
                        except:
                            devs = ''
                        if i > 1:
                            Domoticz.Log('No device data returned for Tuya. Trying again!')
                        i += 1
                    if i > 4:
                        raise Exception('No device data returned for Tuya. Check if subscription cloud development plan has expired!')
                    token = tuya.token

                    properties = {}
                    result = {}
                    for dev in devs:
                        try:
                            properties[dev['id']] = tuya.getproperties(dev['id'])['result']
                            try:
                                properties[dev['id']]['functions']
                            except:
                                properties[dev['id']]['functions'] = []
                            try:
                                properties[dev['id']]['status']
                            except:
                                properties[dev['id']]['status'] = []

                            result[dev['id']] = tuya.getstatus(dev['id'])
                        except:
                            Domoticz.Log('No device data returned for Tuya! Check if subscription cloud plan has expired!')

            # Domoticz.Log('Scanning for tuya devices on network...')
            # if testData == False:
            #     scan = tinytuya.deviceScan(verbose=False, maxretry=None, byID=True)

        # Initialize/Update devices from TUYA API
        last_update = time.time()
        run = 0
        if pulsaractive == True and startup == False and testData == False:
            Domoticz.Debug('Running Pulsar')
            ResultValuePulsar = []
            if not messageQueue.empty():
                ResultValuePulsar = json.loads(messageQueue.get())
                Domoticz.Debug('Pulsar message: ' + str(ResultValuePulsar))
                if 'status' in ResultValuePulsar and isinstance(ResultValuePulsar['status'], list) and len(ResultValuePulsar['status']) > 0:
                    Domoticz.Log('Update device: ' + str(ResultValuePulsar['devId']) + ' Switch: ' + str(ResultValuePulsar['status'][0]['code']) + ' Value: '+ str(ResultValuePulsar['status'][0]['value']))
                messageQueue.task_done()
        for dev in devs:
            run += 1
            try:
                Domoticz.Debug( 'Device name=' + str(dev['name']) + ' id=' + str(dev['id']) + ' category=' + str(DeviceType(dev['category'], str(dev['product_id']))))
                if testData == True:
                    online = True
                else:
                    online = tuya.getconnectstatus(dev['id'])
                # Set last update
                FunctionProperties = properties[dev['id']]['functions']
                dev_type = DeviceType(properties[dev['id']]['category'], dev['product_id'])
                StatusProperties = properties[dev['id']]['status']

                if testData == True:
                    with open(Parameters['HomeFolder'] + '/debug_result.json') as rFile:
                        rData = json.load(rFile)
                        ResultValue = rData['result']
                        t = rData['t']
                elif pulsaractive == True and startup == False:
                    if isinstance(ResultValuePulsar, dict):
                        if 'status' in ResultValuePulsar and isinstance(ResultValuePulsar['status'], list) and len(ResultValuePulsar['status']) > 0:
                            if str(ResultValuePulsar['devId']) == str(dev['id']):
                                t = ResultValuePulsar['status'][0]['t']
                                for status_item in ResultValuePulsar['status']:
                                    for result_item in result[dev['id']]['result']:
                                        if result_item['code'] == status_item['code']:
                                            result_item['value'] = status_item['value']
                                            print(f"Updated {status_item['code']} to {status_item['value']}")
                                            break

                                # for item in result[dev['id']]['result']:
                                #     if item['code'] == ResultValuePulsar['status'][0]['code']:
                                #         item['value'] = ResultValuePulsar['status'][0]['value']
                                #         break
                                ResultValue = result[dev['id']]['result']
                            else:
                                continue
                        else:
                            continue
                    else:
                        continue
                else:
                    Result = tuya.getstatus(dev['id'])
                    ResultValue = Result['result']
                    t = Result['t']

                product_id = getConfigItem(dev['id'],'product_id')

                Domoticz.Debug('Device name= ' + str(dev['name']) + ' id= ' + str(dev['id']) + ' FunctionProperties= ' + str(properties[dev['id']]['functions']) + '\n')
                Domoticz.Debug('Device name= ' + str(dev['name']) + ' id= ' + str(dev['id']) + ' StatusProperties= ' + str(properties[dev['id']]['status']) + '\n')
                Domoticz.Debug('Device name= ' + str(dev['name']) + ' id= ' + str(dev['id']) + ' result= ' + str(ResultValue) + '\n')
            except:
                raise Exception('Credentials are incorrect or tuya subscription has expired!')
                return

            # Create devices
            if startup == True:
                if run == 1:
                    Domoticz.Debug('Run Startup script')
                # try:
                #     deviceinfo = scan[dev['id']]
                # except:
                #     deviceinfo = {'version': 3.3}

                # Set extra info
                setConfigItem(dev['id'], {'key': dev['key'], 'category': dev_type, 'mac': dev['mac'], 'product_id': dev['product_id']})  # , 'version': deviceinfo['version'], 'scalemode': scalemode})

                if dev_type in ('light', 'fanlight', 'pirlight') and createDevice(dev['id'], 1):
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
                    elif (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)):
                        Domoticz.Log('Create device Light On/Off (Unknown Light Device)')
                        Domoticz.Unit(Name=dev['name'] + ' (Unknown Light Device)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=7, Used=1).Create()
                    # elif not (searchCode('switch_led', StatusProperties) or searchCode('led_switch', StatusProperties)):
                    #     deleteDevice(dev['id'],1)

                if dev_type == 'dimmer':
                    if  createDevice(dev['id'], 1) and searchCode('switch_led_1', StatusProperties) and not searchCode('switch_led_2', StatusProperties):
                        Domoticz.Log('Create device Dimmer')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                    if searchCode('switch_led_2', StatusProperties):
                        if createDevice(dev['id'], 1):
                            Domoticz.Unit(Name=dev['name'] + ' (Dimmer 1)', DeviceID=dev['id'], Unit=1, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                        # elif not createDevice(dev['id'], 1) and not searchCode('switch_led_1', FunctionProperties):
                        #     deleteDevice(dev['id'],1)
                        if createDevice(dev['id'], 2):
                            Domoticz.Unit(Name=dev['name'] + ' (Dimmer 2)', DeviceID=dev['id'], Unit=2, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                        # elif not createDevice(dev['id'], 2) and not searchCode('switch_led_2', FunctionProperties):
                        #     deleteDevice(dev['id'],2)

                if dev_type == 'switch':
                    if  createDevice(dev['id'], 1) and (searchCode('switch_1', StatusProperties) or searchCode('switch', StatusProperties)) and not searchCode('switch_2', StatusProperties):
                        Domoticz.Log('Create device Switch')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if searchCode('switch_2', StatusProperties):
                        Domoticz.Log('Create device Switch')
                        if createDevice(dev['id'], 1):
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 1)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        if createDevice(dev['id'], 2):
                            Domoticz.Unit(Name=dev['name'] + ' (Switch 2)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('switch_3', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 3)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('switch_4', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 4)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('switch_5', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 5)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('switch_6', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 6)', DeviceID=dev['id'], Unit=6, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('switch_7', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 7)', DeviceID=dev['id'], Unit=7, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 8) and searchCode('switch_8', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 8)', DeviceID=dev['id'], Unit=8, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 9) and searchCode('switch_9', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 9)', DeviceID=dev['id'], Unit=9, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 11) and ((searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'A') or searchCode('phase_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 12) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (W)', DeviceID=dev['id'], Unit=12, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 13) and (searchCode('cur_voltage', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=13, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 14) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=29, Used=1).Create()
                        #UpdateDevice(dev['id'], 14, '0;0', 0, 0, 1)
                    if createDevice(dev['id'], 15) and (searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'mA' or searchCode('leakage_current', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' (mA)', DeviceID=dev['id'], Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 16) and searchCode('temp_current', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=16, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 17) and (searchCode('out_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' outpower (W)', DeviceID=dev['id'], Unit=17, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 18) and (searchCode('out_power', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' outpower (kWh)', DeviceID=dev['id'], Unit=18, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 19) and (searchCode('power_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' Reverse A(kWh)', DeviceID=dev['id'], Unit=19, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 20) and (searchCode('power_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' Forward A(kWh)', DeviceID=dev['id'], Unit=20, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 21) and (searchCode('power_b', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' Reverse B(kWh)', DeviceID=dev['id'], Unit=21, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 22) and (searchCode('power_b', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' Forward B(kWh)', DeviceID=dev['id'], Unit=22, Type=243, Subtype=29, Used=1).Create()

                if dev_type == 'cover' and createDevice(dev['id'], 1):
                    Domoticz.Log('Create device Cover')
                    if searchCode('position', StatusProperties) or searchCode('percent_control', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 1)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=21, Used=1).Create()
                    else:
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=14, Used=1).Create()
                    if searchCode('position_2', StatusProperties) or searchCode('percent_control_2', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch 2)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=21, Used=1).Create()

                if dev_type == 'smartheatpump':
                    if createDevice(dev['id'], 1) and searchCode('switch', StatusProperties):
                        Domoticz.Log('Create device Smartheatpump')
                        Domoticz.Unit(Name=dev['name'] + ' (On/Off)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('intemp', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (INtemp)', DeviceID=dev['id'], Unit=2, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('outtemp', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (OUTtemp)', DeviceID=dev['id'], Unit=3, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('whjtemp', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (AMBtemp)', DeviceID=dev['id'], Unit=4, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('cmptemp', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (COMPRtemp)', DeviceID=dev['id'], Unit=5, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('wttemp', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (DHWtemp)', DeviceID=dev['id'], Unit=6, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('hqtemp', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (rGAStemp)', DeviceID=dev['id'], Unit=7, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 8) and searchCode('cmp_act_frep', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hz'
                        Domoticz.Unit(Name=dev['name'] + ' (COMPfrq)', DeviceID=dev['id'], Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 9) and searchCode('cmp_cur', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (COMPRcur)', DeviceID=dev['id'], Unit=9, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 10) and searchCode('dc_fan_speed', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Speed'
                        Domoticz.Unit(Name=dev['name'] + ' (FANspeed)', DeviceID=dev['id'], Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 11) and searchCode('ach_stemp', StatusProperties):
                        for item in StatusProperties:
                            temp = 'ach_stemp'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (HEATtemp)', DeviceID=dev['id'], Unit=11, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 12) and searchCode('wth_stemp', StatusProperties):
                        for item in StatusProperties:
                            temp = 'wth_stemp'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (DHWtemp)', DeviceID=dev['id'], Unit=12, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 13) and searchCode('aircond_temp_diff', StatusProperties):
                        for item in StatusProperties:
                            temp = 'aircond_temp_diff'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (HE/COtemp-diff)', DeviceID=dev['id'], Unit=13, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 14) and searchCode('wth_temp_diff', StatusProperties):
                        for item in StatusProperties:
                            temp = 'wth_temp_diff'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (DHWtemp-diff)', DeviceID=dev['id'], Unit=14, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 15) and searchCode('acc_stemp', StatusProperties):
                        for item in StatusProperties:
                            temp = 'acc_stemp'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (ACCtemp)', DeviceID=dev['id'], Unit=15, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 16) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-16', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=16, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 17) and searchCode('work_mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'work_mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-17', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (WorkMode)', DeviceID=dev['id'], Unit=17, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if not(createDevice(dev['id'], 18)):
                    # if createDevice(dev['id'], 18) and searchCode('temp_current', StatusProperties):
                        # Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=18, Type=80, Subtype=5, Used=1).Create()
                        Devices[dev['id']].Unit['18'].delete()
                    if createDevice(dev['id'], 19) and searchCode('temp_set', StatusProperties):
                        for item in StatusProperties:
                            temp = 'temp_set'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev['id'], Unit=19, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if not(createDevice(dev['id'], 20)):
                    # if createDevice(dev['id'], 20) and searchCode('water_set', StatusProperties):
                        # for item in StatusProperties:
                        #     temp = 'water_set'
                        #     if item['code'] == temp:
                        #         the_values = json.loads(item['values'])
                        #         options = {}
                        #         options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                        #         options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                        #         options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                        #         options['ValueUnit'] = the_values.get('unit')
                        # Domoticz.Unit(Name=dev['name'] + ' (Water Thermostat)', DeviceID=dev['id'], Unit=20, Type=242, Subtype=1, Options=options, Used=1).Create()
                        Devices[dev['id']].Unit['20'].delete()
                    if createDevice(dev['id'], 21) and searchCode('temp_top', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temp Top)', DeviceID=dev['id'], Unit=21, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 22) and searchCode('temp_bottom', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temp Bottom)', DeviceID=dev['id'], Unit=22, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 23) and searchCode('switch', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Defrost)', DeviceID=dev['id'], Unit=23, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 24) and searchCode('water_flow', StatusProperties):
                        options = {}
                        options['Custom'] = '1;L/Min'
                        Domoticz.Unit(Name=dev['name'] + ' (L/Min)', DeviceID=dev['id'], Unit=24, Type=243, Subtype=31, Options=options, Used=1).Create()

                if dev_type == 'thermostat' or dev_type == 'heater' or dev_type == 'heatpump':
                    temp = searchCode('temp_current', StatusProperties) or searchCode('upper_temp', StatusProperties) or searchCode('c_temperature', StatusProperties) or searchCode('TempCurrent', StatusProperties)
                    hum = searchCode('humidity_current', StatusProperties)
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Thermostat/heater/heatpump')
                        if searchCode('switch', StatusProperties) or searchCode('switch_1', StatusProperties) or searchCode('Power', StatusProperties) or searchCode('infared_switch', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                        else:
                            Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=0).Create()
                    if createDevice(dev['id'], 2) and temp:
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=2, Type=80, Subtype=5, Used=0 if hum else 1).Create()
                    if createDevice(dev['id'], 3) and (searchCode('set_temp', StatusProperties) or searchCode('temp_set', StatusProperties) or searchCode('temperature_c', StatusProperties) or searchCode('TempSet', StatusProperties) or searchCode('target_temp', StatusProperties)):
                        if searchCode('temp_set', StatusProperties):
                            temp = 'temp_set'
                        elif searchCode('set_temp', StatusProperties):
                            temp = 'set_temp'
                        elif searchCode('temperature_c', StatusProperties):
                            temp = 'temperature_c'
                        elif searchCode('TempSet', StatusProperties):
                            temp = 'TempSet'
                        elif searchCode('target_temp', StatusProperties):
                            temp = 'target_temp'
                        for item in StatusProperties:
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev['id'], Unit=3, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 4) and (searchCode('mode', StatusProperties) or searchCode('Mode', StatusProperties)) and product_id != 'al8g1qdamyu5cfcc':
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
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(str(dev['id']) + '-4', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=image, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('window_check', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Window check)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('child_lock', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Child lock)', DeviceID=dev['id'], Unit=6, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('Eco', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Eco)', DeviceID=dev['id'], Unit=7, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    # elif not createDevice(dev['id'], 7) and not searchCode('Eco', FunctionProperties):
                    #     deleteDevice(dev['id'],7)
                    if createDevice(dev['id'], 8) and searchCode('temp_floor', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=8, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 9) and (searchCode('windspeed', StatusProperties) or searchCode('fan_level', StatusProperties) or searchCode('fan_speed_enum', StatusProperties)):
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
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-9', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                Domoticz.Unit(Name=dev['name'] + ' (' + wind.capitalize().replace("_", " ") +')', DeviceID=dev['id'], Unit=9, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 10) and hum:
                        Domoticz.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev['id'], Unit=10, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 11) and ((searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'A') or searchCode('phase_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 12) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties) or searchCode('average_power', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (W)', DeviceID=dev['id'], Unit=12, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 13) and (searchCode('cur_voltage', StatusProperties) or searchCode('phase_a', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=13, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 14) and (searchCode('cur_power', StatusProperties) or searchCode('phase_a', StatusProperties) or searchCode('average_power', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 15) and (searchCode('cur_current', StatusProperties) and get_unit('cur_current', StatusProperties) == 'mA' or searchCode('leakage_current', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' (mA)', DeviceID=dev['id'], Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 16) and temp and hum:
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev['id'], Unit=16, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 17) and searchCode('anti_bother', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Anti bother)', DeviceID=dev['id'], Unit=17, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 18) and searchCode('fault', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=18, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type in ('sensor', 'smartir'):
                    temp = searchCode('va_temperature', StatusProperties) or searchCode('temp_current', StatusProperties) or searchCode('local_temp', StatusProperties) or searchCode('Tin', StatusProperties)
                    hum = searchCode('va_humidity', StatusProperties) or searchCode('humidity_value', StatusProperties) or searchCode('local_hum', StatusProperties) or searchCode('humidity', StatusProperties) or searchCode('Hin', StatusProperties)
                    if createDevice(dev['id'], 1) and temp:
                        Domoticz.Log('Create Sensor device')
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=1, Type=80, Subtype=5, Used=0 if hum else 1).Create()
                    if createDevice(dev['id'], 2) and hum:
                        Domoticz.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev['id'], Unit=2, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 3) and temp and hum:
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev['id'], Unit=3, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('co2_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;ppm'
                        Domoticz.Unit(Name=dev['name'] + ' (CO2)', DeviceID=dev['id'], Unit=4, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('air_quality_index', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Index)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('ch2o_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mg/m3'
                        Domoticz.Unit(Name=dev['name'] + ' (CH2O)', DeviceID=dev['id'], Unit=6, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('voc_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mg/m3'
                        Domoticz.Unit(Name=dev['name'] + ' (VOC)', DeviceID=dev['id'], Unit=7, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 8) and searchCode('pm25_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;µg/m3'
                        Domoticz.Unit(Name=dev['name'] + ' (PM2.5)', DeviceID=dev['id'], Unit=8, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 9) and searchCode('pm10', StatusProperties):
                        options = {}
                        options['Custom'] = '1;µg/m3'
                        Domoticz.Unit(Name=dev['name'] + ' (PM10)', DeviceID=dev['id'], Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 10) and searchCode('bright_value', StatusProperties):
                        options = {}
                        options['Custom'] = '1;lux'
                        Domoticz.Unit(Name=dev['name'] + ' (Lux)', DeviceID=dev['id'], Unit=10, Type=243, Subtype=31, Options=options, Image=19, Used=1).Create()
                    if createDevice(dev['id'], 11) and searchCode('switch', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Switch)', DeviceID=dev['id'], Unit=11, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 12) and searchCode('ph_current', ResultValue):
                        options = {}
                        options['Custom'] = '1;pH'
                        Domoticz.Unit(Name=dev['name'] + ' (pH)', DeviceID=dev['id'], Unit=12, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 13) and searchCode('pro_current', ResultValue):
                        options = {}
                        options['Custom'] = '1;kPa'
                        Domoticz.Unit(Name=dev['name'] + ' (kPa)', DeviceID=dev['id'], Unit=13, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 14) and searchCode('orp_current', ResultValue):
                        options = {}
                        options['Custom'] = '1;ORP'
                        Domoticz.Unit(Name=dev['name'] + ' (ORP)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=31, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 15) and searchCode('ph_warn_min', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'ph_warn_min'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Min pH)', DeviceID=dev['id'], Unit=15, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 16) and searchCode('ph_warn_max', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'ph_warn_max'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Max pH)', DeviceID=dev['id'], Unit=16, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 17) and searchCode('pro_warn_min', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'pro_warn_min'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Min kPa)', DeviceID=dev['id'], Unit=17, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 18) and searchCode('pro_warn_max', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'pro_warn_max'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Max kPa)', DeviceID=dev['id'], Unit=18, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 19) and searchCode('orp_warn_min', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'orp_warn_min'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Min ORP)', DeviceID=dev['id'], Unit=19, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 20) and searchCode('orp_warn_max', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'orp_warn_max'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Max ORP)', DeviceID=dev['id'], Unit=20, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 21) and (searchCode('sub1_temp', ResultValue) or searchCode('ToutCh1', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + '_ext1 (Temperature)', DeviceID=dev['id'], Unit=21, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev['id'], 22) and (searchCode('sub1_hum', StatusProperties) or searchCode('HoutCh1', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + '_ext1 (Humidity)', DeviceID=dev['id'], Unit=22, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 23) and ((searchCode('sub1_temp', StatusProperties) and searchCode('sub1_hum', StatusProperties)) or (searchCode('ToutCh1', StatusProperties) and searchCode('HoutCh1', StatusProperties))):
                        Domoticz.Unit(Name=dev['name'] + '_ext1 (Temperature + Humidity)', DeviceID=dev['id'], Unit=23, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 24) and searchCode('temp_warn_min', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'temp_warn_min'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Min Temp)', DeviceID=dev['id'], Unit=24, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 25) and searchCode('temp_warn_max', FunctionProperties):
                        for item in FunctionProperties:
                            temp = 'temp_warn_max'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Max Temp)', DeviceID=dev['id'], Unit=25, Type=242, Subtype=1, Options=options, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 31) and (searchCode('sub2_temp', ResultValue) or searchCode('ToutCh2', ResultValue)):
                        Domoticz.Unit(Name=dev['name'] + '_ext2 (Temperature)', DeviceID=dev['id'], Unit=31, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev['id'], 32) and (searchCode('sub2_hum', StatusProperties) or searchCode('HoutCh2', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + '_ext2 (Humidity)', DeviceID=dev['id'], Unit=32, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 33) and ((searchCode('sub2_temp', StatusProperties) and searchCode('sub2_hum', StatusProperties)) or (searchCode('ToutCh2', StatusProperties) and searchCode('HoutCh2', StatusProperties))):
                        Domoticz.Unit(Name=dev['name'] + '_ext2 (Temperature + Humidity)', DeviceID=dev['id'], Unit=33, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 41) and (searchCode('sub3_temp', StatusProperties) or searchCode('ToutCh3', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + '_ext3 (Temperature)', DeviceID=dev['id'], Unit=41, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev['id'], 42) and (searchCode('sub3_hum', StatusProperties) or searchCode('HoutCh3', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + '_ext3 (Humidity)', DeviceID=dev['id'], Unit=42, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 43) and ((searchCode('sub3_temp', StatusProperties) and searchCode('sub3_hum', StatusProperties)) or (searchCode('ToutCh3', StatusProperties) and searchCode('HoutCh3', StatusProperties))):
                        Domoticz.Unit(Name=dev['name'] + '_ext3 (Temperature + Humidity)', DeviceID=dev['id'], Unit=43, Type=82, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 44) and searchCode('temp_current_2', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature 2)', DeviceID=dev['id'], Unit=44, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 45) and searchCode('cook_temperature', StatusProperties):
                        for item in StatusProperties:
                            temp = 'cook_temperature'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Cook temperature)', DeviceID=dev['id'], Unit=45, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 46) and searchCode('cook_temperature_2', StatusProperties):
                        for item in StatusProperties:
                            temp = 'cook_temperature_2'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Cook temperature 2)', DeviceID=dev['id'], Unit=46, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 47) and searchCode('atmosphere', StatusProperties):
                        options = {}
                        options['Custom'] = '1;inHg'
                        Domoticz.Unit(Name=dev['name'] + ' (inHg)', DeviceID=dev['id'], Unit=47, Type=243, Subtype=31, Options=options, Image=19, Used=1).Create()
                    if createDevice(dev['id'], 48) and searchCode('pir', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Pir)', DeviceID=dev['id'], Unit=48, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 49) and searchCode('temper_alarm', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temper alarm)', DeviceID=dev['id'], Unit=49, Type=244, Subtype=73, Switchtype=0, Image=13, Used=1).Create()
                    # if createDevice(dev['id'], 47) and searchCode('alarm_switch', FunctionProperties):
                    #     Domoticz.Unit(Name=dev['name'] + ' (Alarm)', DeviceID=dev['id'], Unit=47, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()

                    if dev_type in ('smartir') and dev['id'] not in str(Devices):
                        Domoticz.Log('Infrared device: ' + str(dev['name']))
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=0).Create()
                        UpdateDevice(dev['id'], 1, 'Infrared devices are not yet able to be controlled by the plugin.', 0, 0)

                if dev_type == 'doorbell':
                    if createDevice(dev['id'], 1) and searchCode('doorbell_active', StatusProperties):
                        Domoticz.Log('Create device Doorbell')
                        #Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=1).Create()
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create() # Switchtype=1 is doorbell
                    if createDevice(dev['id'], 2) and searchCode('floodlight_switch', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Light switch)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and (searchCode('motion_switch', StatusProperties) or searchCode('movement_detect_pic', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (Motion switch)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('basic_indicator', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Indicator)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()

                if dev_type == 'fan':
                    if createDevice(dev['id'], 1) and searchCode('switch', StatusProperties):
                        Domoticz.Log('Create device Fan')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-2', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('fan_speed', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'fan_speed':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Fan Speed)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('temp_set', StatusProperties):
                        for item in StatusProperties:
                            temp = 'temp_set'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev['id'], Unit=4, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('temp_current', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=5, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('fault', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=6, Type=243, Subtype=19, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('light', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Light)', DeviceID=dev['id'], Unit=7, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 8) and searchCode('switch', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (RH Switch)', DeviceID=dev['id'], Unit=8, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 9) and (searchCode('RH_threshold', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;RH'
                        Domoticz.Unit(Name=dev['name'] + ' (RH Threshold)', DeviceID=dev['id'], Unit=9, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 10) and (searchCode('RH_value', StatusProperties)):
                        options = {}
                        options['Custom'] = '1;RH'
                        Domoticz.Unit(Name=dev['name'] + ' (RH Value)', DeviceID=dev['id'], Unit=10, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 11) and searchCode('anion', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Anion)', DeviceID=dev['id'], Unit=11, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 12) and searchCode('anion', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Free Cooling)', DeviceID=dev['id'], Unit=12, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 13) and searchCode('anion', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Powerful)', DeviceID=dev['id'], Unit=13, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()

                if dev_type == 'fanlight':
                    if createDevice(dev['id'], 2) and searchCode('fan_switch', StatusProperties):
                        Domoticz.Log('Create device Fanlight')
                        Domoticz.Unit(Name=dev['name'] + ' (Fan Power)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('fan_speed', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'fan_speed':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Fan Speed)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('fan_direction', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'fan_direction':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(str(dev['id']) + '-4', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Fan Direction)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()

                if dev_type == 'siren':
                    if createDevice(dev['id'], 1) and searchCode('AlarmSwitch', StatusProperties):
                        Domoticz.Log('Create device Siren')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=13, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('Alarmtype', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'Alarmtype':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-2', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Alarmtype)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=8, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('AlarmPeriod', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'AlarmPeriod':
                                the_values = json.loads(item['values'])
                                mode = []
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'false'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (AlarmPeriod)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    # Other type of alarm with same code
                    if createDevice(dev['id'], 1) and searchCode('muffling', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Muffling)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=8, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('alarm_state', StatusProperties):
                        Domoticz.Log('Create device Siren')
                        for item in StatusProperties:
                            if item['code'] == 'alarm_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-2', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (State)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('alarm_volume', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'alarm_volume':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Volume)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=8, Used=1).Create()

                if dev_type == 'powermeter' and searchCode('Current', StatusProperties):
                    if createDevice(dev['id'], 1) :
                        Domoticz.Log('Create device Powermeter')
                        Domoticz.Unit(Name=dev['name'] + ' (3P A)', DeviceID=dev['id'], Unit=1, Type=89, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('Current', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hz'
                        Domoticz.Unit(Name=dev['name'] + ' (Hz)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('Temperature', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=3, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('Current', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=4, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('ActivePower', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 11) and searchCode('ActivePowerA', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' L1 (V)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 12) and searchCode('ActivePowerA', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' L1 (kWh)', DeviceID=dev['id'], Unit=12, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 21) and searchCode('ActivePowerB', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' L2 (V)', DeviceID=dev['id'], Unit=21, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 22) and searchCode('ActivePowerB', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' L2 (kWh)', DeviceID=dev['id'], Unit=22, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 31) and searchCode('ActivePowerC', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' L3 (V)', DeviceID=dev['id'], Unit=31, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 32) and searchCode('ActivePowerC', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' L3 (kWh)', DeviceID=dev['id'], Unit=32, Type=243, Subtype=29, Used=1).Create()

                if dev_type == 'powermeter' and searchCode('phase_a', StatusProperties):
                    if createDevice(dev['id'], 1):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=1, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('phase_a', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (W)', DeviceID=dev['id'], Unit=2, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('phase_a', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=3, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('phase_a', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=4, Type=243, Subtype=29, Used=1).Create()
                    if  createDevice(dev['id'], 5) and searchCode('switch', StatusProperties):
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('fault', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=6, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'powermeter' and searchCode('direction_a', StatusProperties):
                    if createDevice(dev['id'], 1) and searchCode('voltage_a', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=1, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('freq', StatusProperties):
                        options = {}
                        options['Custom'] = '1;Hz'
                        Domoticz.Unit(Name=dev['name'] + ' (Hz)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('total_power', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' Total (W)', DeviceID=dev['id'], Unit=3, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 11) and searchCode('power_a', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' A (W)', DeviceID=dev['id'], Unit=11, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 12) and searchCode('current_a', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' A (mA)', DeviceID=dev['id'], Unit=12, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 13) and searchCode('direction_a', StatusProperties):
                        Domoticz.Unit(Name=dev['name']+ ' A (Direction)', DeviceID=dev['id'], Unit=13, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 14) and searchCode('energy_forword_a', StatusProperties):
                        # Domoticz.Unit(Name=dev['name'] + ' A Forward (kWh)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' A Forward (kWh)', DeviceID=dev['id'], Unit=14, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 15) and searchCode('energy_reverse_a', StatusProperties):
                        # Domoticz.Unit(Name=dev['name'] + ' A Reverse (kWh)', DeviceID=dev['id'], Unit=15, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' A Reverse (kWh)', DeviceID=dev['id'], Unit=15, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 21) and searchCode('power_b', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' B (W)', DeviceID=dev['id'], Unit=21, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 22) and searchCode('current_b', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' B (mA)', DeviceID=dev['id'], Unit=22, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 23) and searchCode('direction_b', StatusProperties):
                        Domoticz.Unit(Name=dev['name']+ ' B (Direction)', DeviceID=dev['id'], Unit=23, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 24) and searchCode('energy_forword_b', StatusProperties):
                        # Domoticz.Unit(Name=dev['name'] + ' B Forward (kWh)', DeviceID=dev['id'], Unit=24, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' B Forward (kWh)', DeviceID=dev['id'], Unit=24, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 25) and searchCode('energy_reserse_b', StatusProperties):
                        # Domoticz.Unit(Name=dev['name'] + ' B Reverse (kWh)', DeviceID=dev['id'], Unit=25, Type=243, Subtype=29, Used=1).Create()
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' B Reverse (kWh)', DeviceID=dev['id'], Unit=25, Type=243, Subtype=31, Options=options, Used=1).Create()

                if dev_type == 'powermeter' and (searchCode('switch_1', StatusProperties) or searchCode('switch', StatusProperties)) and not searchCode('phase_a', StatusProperties):
                    if  createDevice(dev['id'], 1) and (searchCode('switch_1', StatusProperties) or searchCode('switch', StatusProperties)):
                        Domoticz.Log('Create device Switch')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('cur_current', StatusProperties):
                        options = {}
                        options['Custom'] = '1;mA'
                        Domoticz.Unit(Name=dev['name'] + ' (mA)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('cur_power', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=3, Type=243, Subtype=29, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('cur_voltage', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=4, Type=243, Subtype=8, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('fault', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'gateway':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Gateway')
                        if searchCode('master_state', StatusProperties):
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=1).Create()
                        else:
                            Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=0).Create()

                if dev_type == 'doorcontact':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Doorcontact')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                if dev_type == 'pirlight':
                    if createDevice(dev['id'], 2) and searchCode('switch_pir', StatusProperties):
                        Domoticz.Log('Create device Pirlight')
                        Domoticz.Unit(Name=dev['name'] + ' (Pir State)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=8, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('device_mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'device_mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('pir_sensitivity', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'pir_sensitivity':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(str(dev['id']) + '-4', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Sensitivity)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'smokedetector':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Smokedetector')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=5, Used=1).Create()
                        Domoticz.Unit(Name=dev['name'] + ' (Alarm)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=19, Used=1).Create()

                if dev_type == 'garagedooropener':
                    if createDevice(dev['id'], 1) and searchCode('switch_1', StatusProperties):
                        Domoticz.Log('Create device Garage door opener')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=5, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('doorcontact_state', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Contact state)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('door_control_1', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (State)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=11, Used=1).Create()

                if dev_type == 'feeder':
                    if createDevice(dev['id'], 1) and searchCode('manual_feed', StatusProperties):
                        Domoticz.Log('Create device Feeder')
                        for item in StatusProperties:
                            if item['code'] == 'manual_feed':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Manual)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('feed_state', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'feed_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-2', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
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
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Report)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('light', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Light)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Used=1).Create()

                if dev_type == 'waterleak':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device water leak sesor')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=22, Switchtype=0, Image=11, Used=1).Create()

                if dev_type == 'presence':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device PIR sensor')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Used=1).Create()

                if dev_type == 'irrigation':
                    if createDevice(dev['id'], 1) and (searchCode('switch', StatusProperties) or searchCode('switch_1', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('work_state', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'work_state':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-2', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=22, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('areaone', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Area One)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('areatwo', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Area Two)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('areathree', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Area Three)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('areafour', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Area Four)', DeviceID=dev['id'], Unit=6, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('areafive', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Area Five)', DeviceID=dev['id'], Unit=7, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()
                    if createDevice(dev['id'], 8) and searchCode('areasix', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Area Six)', DeviceID=dev['id'], Unit=8, Type=244, Subtype=73, Switchtype=0, Image=22, Used=1).Create()

                if dev_type == 'wswitch':
                    for x in range(1, 10):
                        if createDevice(dev['id'], x) and searchCode('switch' + str(x) + '_value', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'switch' + str(x) + '_value':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values.get('label'))
                                    else:
                                        mode.extend(the_values.get('range'))
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    setConfigItem(dev['id'] + '-' + str(x), {'mode': mode})
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            Domoticz.Unit(Name=dev['name'] + ' (Switch ' + str(x) + ')', DeviceID=dev['id'], Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev['id'], x) and searchCode('switch_type_' + str(x), StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'switch_type_' + str(x):
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values.get('label'))
                                    else:
                                        mode.extend(the_values.get('range'))
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    setConfigItem(dev['id'] + '-' + str(x), {'mode': mode})
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            Domoticz.Unit(Name=dev['name'] + ' (Switch ' + str(x) + ')', DeviceID=dev['id'], Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                        if createDevice(dev['id'], x) and searchCode('switch_mode' + str(x), StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'switch_mode' + str(x):
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values.get('label'))
                                    else:
                                        mode.extend(the_values.get('range'))
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    setConfigItem(dev['id'] + '-' + str(x), {'mode': mode})
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            Domoticz.Unit(Name=dev['name'] + ' (Switch ' + str(x) + ')', DeviceID=dev['id'], Unit=x, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'starlight':
                    if createDevice(dev['id'], 1) and searchCode('switch_led', StatusProperties):
                        Domoticz.Log('Create device Starlight')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=241, Subtype=2, Switchtype=7, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('colour_switch', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Colour)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('laser_switch', StatusProperties) and searchCode('laser_bright', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Laser)', DeviceID=dev['id'], Unit=3, Type=241, Subtype=3, Switchtype=7, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('fan_switch', StatusProperties) and searchCode('fan_speed', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Fan)', DeviceID=dev['id'], Unit=4, Type=241, Subtype=3, Switchtype=7, Image=7, Used=1).Create()

                if dev_type == 'smartlock':
                    if createDevice(dev['id'], 1) and searchCode('lock_motor_state', StatusProperties):
                        Domoticz.Log('Create device smart lock')
                        Domoticz.Unit(Name=dev['name'] + ('State'), DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('alarm_lock', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'alarm_lock':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-2', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=13, Used=1).Create()
                    # if createDevice(dev['id'], 3):
                    #     Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=3, Type=244, Subtype=73, Switchtype=19, Used=1).Create()

                if dev_type == 'dehumidifier':
                    if createDevice(dev['id'], 1) and searchCode('switch', StatusProperties):
                        Domoticz.Log('Create device Dehumidifier')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and (searchCode('dehumidify_set_value', StatusProperties) or searchCode('dehumidify_set_enum', StatusProperties)):
                        Domoticz.Log('Create device Feeder')
                        if searchCode('dehumidify_set_value', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'dehumidify_set_value':
                                    the_values = json.loads(item['values'])
                                    mode = ['0']
                                    for num in range(the_values.get('min'),the_values.get('max') + 1):
                                        mode.extend([str(num)])
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    setConfigItem(dev['id'] + '-2', {'mode': mode})
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                            Domoticz.Unit(Name=dev['name'] + ' (dehumidify)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=11, Used=1).Create()
                        elif searchCode('dehumidify_set_enum', StatusProperties):
                            for item in StatusProperties:
                                if item['code'] == 'dehumidify_set_enum':
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values.get('label'))
                                    else:
                                        mode.extend(the_values.get('range'))
                                    options = {}
                                    options['LevelOffHidden'] = 'true'
                                    options['LevelActions'] = ''
                                    options['LevelNames'] = '|'.join(mode)
                                    setConfigItem(dev['id'] + '-2', {'mode': mode})
                                    options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (dehumidify)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=11, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('fan_speed_enum', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'fan_speed_enum':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (fan speed)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                Domoticz.Unit(Name=dev['name'] + ' (Fan)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('fault', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'infrared_ac':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Create device Infrared AC')
                        Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('temp', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Thermostat)', DeviceID=dev['id'], Unit=2, Type=242, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('wind', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'wind':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(str(dev['id']) + '-4', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                                Domoticz.Unit(Name=dev['name'] + ' (Fan)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('anion', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (anion)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 6) and (searchCode('temp_indoor', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=6, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev['id'], 7) and (searchCode('humidity_indoor', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (Humidity)', DeviceID=dev['id'], Unit=7, Type=81, Subtype=1, Used=0).Create()
                    if createDevice(dev['id'], 8) and ((searchCode('temp_indoor', StatusProperties) and searchCode('humidity_indoor', StatusProperties))):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature + Humidity)', DeviceID=dev['id'], Unit=8, Type=82, Subtype=5, Used=1).Create()

                if dev_type == 'vacuum':
                    if createDevice(dev['id'], 1) and searchCode('power_go', StatusProperties):
                        Domoticz.Log('Create device Robot vacuum')
                        Domoticz.Unit(Name=dev['name'] + ' Running', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('switch_charge', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Charge)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Mode)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create() #Image=7,
                    if createDevice(dev['id'], 4) and searchCode('suction', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'suction':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(str(dev['id']) + '-4', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Suction)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('cistern', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'cistern':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-5', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Cistern)', DeviceID=dev['id'], Unit=5, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('status', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=6, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('electricity_left', StatusProperties):
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
                    if createDevice(dev['id'], 11) and searchCode('fault', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=11, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'multifunctionalarm':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Multifunction alarm: ' + str(dev['name']))
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=0).Create()
                        UpdateDevice(dev['id'], 1, 'update wait', 0, 0)

                if dev_type == 'purifier':
                    if createDevice(dev['id'], 1) and searchCode('switch', StatusProperties):
                        Domoticz.Log('Create purifier device')
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('pm25', StatusProperties):
                        options = {}
                        options['Custom'] = '1;µg/m3'
                        Domoticz.Unit(Name=dev['name'] + ' (PM2.5)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('mode', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'mode':
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-3', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (mode)', DeviceID=dev['id'], Unit=3, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('speed', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'speed':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(str(dev['id']) + '-4', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (speed)', DeviceID=dev['id'], Unit=4, Type=244, Subtype=62, Switchtype=18, Options=options, Image=7, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('filter', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Filter)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=6, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('air_quality', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Index)', DeviceID=dev['id'], Unit=6, Type=243, Subtype=19, Used=1).Create()

                if dev_type == 'smartkettle':
                    if createDevice(dev['id'], 1) and searchCode('start', StatusProperties):
                        Domoticz.Log('Create device Smart Kettle')
                        Domoticz.Unit(Name=dev['name'] + ' (Start)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('status', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'status':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-2', {'mode': mode})
                                options['SelectorStyle'] = 0
                        Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 3) and (searchCode('temperature', StatusProperties)):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=3, Type=80, Subtype=5, Used=0).Create()
                    if createDevice(dev['id'], 4) and (searchCode('cook_temperature', StatusProperties)):
                        for item in StatusProperties:
                            temp = 'cook_temperature'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Cook Temperature)', DeviceID=dev['id'], Unit=4, Type=242, Subtype=1, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('fault', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'mower':
                    if createDevice(dev['id'], 1) and searchCode('MachineControlCmd', StatusProperties):
                        Domoticz.Log('Create device Smart Mower')
                        for item in StatusProperties:
                            if item['code'] == 'MachineControlCmd':
                                the_values = json.loads(item['values'])
                                mode = ['off']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-1', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Control)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=62, Switchtype=18, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('MachineRainMode', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Rain Mode)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('MachineStatus', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Status)', DeviceID=dev['id'], Unit=3, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('MachineWarning', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Warnig)', DeviceID=dev['id'], Unit=4, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('MachineError', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Error)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=19, Used=1).Create()

                if dev_type == 'human_presence':
                    if createDevice(dev['id'], 1) and searchCode('presence_state', StatusProperties):
                        Domoticz.Log('Create device Human presence sensor')
                        Domoticz.Unit(Name=dev['name'] + ' (Presence)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('sensitivity', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'sensitivity':
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                                options = {}
                                options['LevelOffHidden'] = 'true'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-2', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Sensitivity)', DeviceID=dev['id'], Unit=2, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 3) and (searchCode('near_detection', StatusProperties)):
                        for item in StatusProperties:
                            temp = 'near_detection'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Near detection)', DeviceID=dev['id'], Unit=3, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 4) and (searchCode('far_detection', StatusProperties)):
                        for item in StatusProperties:
                            temp = 'far_detection'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Far detection)', DeviceID=dev['id'], Unit=4, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('checking_result', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Result)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 6) and (searchCode('target_dis_closest', StatusProperties)):
                        for item in StatusProperties:
                            temp = 'target_dis_closest'
                            if item['code'] == temp:
                                the_values = json.loads(item['values'])
                                options = {}
                                options['ValueStep'] = get_scale(StatusProperties, temp, the_values.get('step'))
                                options['ValueMin'] = get_scale(StatusProperties, temp, the_values.get('min'))
                                options['ValueMax'] = get_scale(StatusProperties, temp, the_values.get('max'))
                                options['ValueUnit'] = the_values.get('unit')
                        Domoticz.Unit(Name=dev['name'] + ' (Target)', DeviceID=dev['id'], Unit=6, Type=242, Subtype=1, Options=options, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 10) and searchCode('presence_state', StatusProperties):
                        for item in StatusProperties:
                            if item['code'] == 'presence_state':
                                the_values = json.loads(item['values'])
                                mode = []
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                else:
                                    mode.extend(the_values.get('range'))
                                options = {}
                                options['LevelOffHidden'] = 'false'
                                options['LevelActions'] = ''
                                options['LevelNames'] = '|'.join(mode)
                                setConfigItem(dev['id'] + '-10', {'mode': mode})
                                options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                        Domoticz.Unit(Name=dev['name'] + ' (Presence state)', DeviceID=dev['id'], Unit=10, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create()

                if dev_type == 'evcharger':
                    if createDevice(dev['id'], 1) and searchCode('switch', StatusProperties):
                        Domoticz.Log('Create EVcharger')
                        Domoticz.Unit(Name=dev['name'] + ' (Power)', DeviceID=dev['id'], Unit=1, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
                    if createDevice(dev['id'], 2) and searchCode('work_state', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Work state)', DeviceID=dev['id'], Unit=2, Type=243, Subtype=19, Used=1).Create()
                    if createDevice(dev['id'], 3) and searchCode('temp_current', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (Temperature)', DeviceID=dev['id'], Unit=3, Type=80, Subtype=5, Used=1).Create()
                    if createDevice(dev['id'], 4) and searchCode('power_total', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (W)', DeviceID=dev['id'], Unit=4, Type=248, Subtype=1, Used=1).Create()
                    if createDevice(dev['id'], 5) and searchCode('charge_cur_set', StatusProperties):
                        Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=5, Type=243, Subtype=23, Used=1).Create()
                    if createDevice(dev['id'], 6) and searchCode('forward_energy_total', StatusProperties) :
                        options = {}
                        options['Custom'] = '1;kWh'
                        Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'], Unit=6, Type=243, Subtype=31, Options=options, Used=1).Create()
                    if createDevice(dev['id'], 7) and searchCode('online_state', StatusProperties):
                            Domoticz.Unit(Name=dev['name'] + ' (Online state)', DeviceID=dev['id'], Unit=7, Type=243, Subtype=19, Used=1).Create()
                    # if createDevice(dev['id'], 8) and searchCode('fault', StatusProperties):
                    #         Domoticz.Unit(Name=dev['name'] + ' (Fault)', DeviceID=dev['id'], Unit=8, Type=243, Subtype=19, Image=13, Used=1).Create()

                if dev_type == 'infrared':
                    if createDevice(dev['id'], 1):
                        Domoticz.Log('Infrared device: ' + str(dev['name']))
                        Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=0).Create()
                        UpdateDevice(dev['id'], 1, 'Infrared devices are not yet able to be controlled by the plugin.', 0, 0)

                if createDevice(dev['id'], 1) and dev['id'] not in str(Devices):
                    Domoticz.Log('No controls found for device: ' + str(dev['name']))
                    Domoticz.Unit(Name=dev['name'] + ' (Unknown Device)', DeviceID=dev['id'], Unit=1, Type=243, Subtype=19, Used=1).Create()
                    UpdateDevice(dev['id'], 1, 'This device is not recognized. Please run the debug_discovery with Python from the tools directory and create an issue report at https://github.com/Xenomes/Domoticz-TinyTUYA-Plugin/issues so that the device can be added.', 0, 0)

                # Domoticz.Debug('ConfigItem:' + str(getConfigItem()))

            # Check device is removed
            if dev['id'] not in str(Devices) or len(Devices) == 0:
                raise Exception('Device not found in Domoticz! Has the device been removed, or is the "Accept New Hardware" option not enabled?')

            #update devices in Domoticz
            if run == 1:
                Domoticz.Log('Update devices in Domoticz')
            if not bool(online) and Devices[dev['id']].TimedOut == 0:
                UpdateDevice(dev['id'], 1, False, 0, 1)
            elif bool(online) and Devices[dev['id']].TimedOut == 1:
                UpdateDevice(dev['id'], 1, None, 0, 0)
            elif bool(online) and Devices[dev['id']].TimedOut == 0:
                try:
                    def update_bool_device(code, unit, value=None):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev['id'], unit):
                            return False
                        # Get the current status of the device
                        if value is None:
                            currentstatus = StatusDeviceTuya(code)
                        else:
                            currentstatus = False if value == StatusDeviceTuya(code) else True
                        UpdateDevice(dev['id'], unit, bool(currentstatus), int(bool(currentstatus)), 0)
                        return True

                    def update_value_device(code, unit, codeunit=None):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not get_unit(code, StatusProperties) not in [codeunit, None] or not checkDevice(dev['id'], unit):
                            return False
                        # Get the current value of the device
                        currentvalue = StatusDeviceTuya(code)
                        if str(currentvalue) != str(Devices[dev['id']].Units[unit].sValue):
                            UpdateDevice(dev['id'], unit, currentvalue, 0, 0)
                        return True

                    def update_nvalue_device(code, unit, codeunit=None):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not get_unit(code, StatusProperties) not in [codeunit, None] or not checkDevice(dev['id'], unit):
                            return False
                        # Get the current value of the device
                        currentvalue = StatusDeviceTuya(code)
                        if str(currentvalue) != str(Devices[dev['id']].Units[unit].nValue):
                            UpdateDevice(dev['id'], unit, 0, currentvalue, 0)
                        return True

                    def update_dualvalue_device(code1, code2, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code1, StatusProperties) or not searchCode(code2, StatusProperties) or not checkDevice(dev['id'], unit):
                            return False
                        # Get the current value of the device
                        currentvalue1 = StatusDeviceTuya(code1)
                        currentvalue2 = StatusDeviceTuya(code2)
                        currentdomo = Devices[dev['id']].Units[unit].sValue
                        if str(currentvalue1) != str(currentdomo.split(';')[0]) or str(currentvalue2) != str(currentdomo.split(';')[1]):
                            UpdateDevice(dev['id'], unit, str(currentvalue1 ) + ';' + str(currentvalue2) + ';0', 0, 0)
                        return True

                    def update_power_device(code, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev['id'], unit):
                            return False
                        # Get the power value of the device
                        currentpower = StatusDeviceTuya(code)
                        lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[unit].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                        lastvalue = Devices[dev['id']].Units[unit].sValue if len(Devices[dev['id']].Units[unit].sValue) > 0 else '0;0'
                        # Calculating the Power Difference in an time interval
                        UpdateDevice(dev['id'], unit, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)
                        return True

                    def update_select_device(code, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev['id'], unit):
                            return False
                        # Get the current mode of the device
                        currentmode = StatusDeviceTuya(code)
                        # Get the mode configuration once
                        mode = getConfigItem(dev['id'] + '-' + str(unit), 'mode')
                        if mode is None:
                            # Loop through StatusProperties to set the mode
                            for item in StatusProperties:
                                if item['code'] == code:
                                    # Parse values based on item type
                                    the_values = json.loads(item['values'])
                                    mode = ['off']
                                    if item['type'] == 'Bitmap':
                                        mode.extend(the_values.get('label'))
                                    else:
                                        mode.extend(the_values.get('range'))
                                    setConfigItem(dev['id'] + '-' + unit, {'mode': mode})
                                    break  # Exit the loop once we find the code
                        # Calculate the new value
                        new_value = mode.index(str(currentmode)) * 10
                        # Only update if the new value differs from the current value
                        if str(new_value) != str(Devices[dev['id']].Units[unit].sValue):
                            UpdateDevice(dev['id'], unit, int(new_value), 1, 0)
                        return True

                    def update_selectnum_device(code, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev['id'], unit):
                            return False
                        # Get the current mode of the device
                        current = StatusDeviceTuya(code)
                        # Loop through StatusProperties to set the mode
                        for item in StatusProperties:
                            if item['code'] == code:
                                the_values = json.loads(item['values'])
                                mode = ['0']
                                for num in range(the_values.get('min'),the_values.get('max') + 1):
                                    mode.extend([str(num)])
                        # Only update if the new value differs from the current value
                        if str(mode.index(str(current)) * 10) != str(Devices[dev['id']].Units[unit].sValue):
                            UpdateDevice(dev['id'], unit, int(mode.index(str(current)) * 10), 1, 0)
                        return True

                    def update_text_device(code, unit):
                        # Check if the given code is present and device is valid
                        if not searchCode(code, StatusProperties) or not checkDevice(dev['id'], unit):
                            return False
                        # Get the current mode of the device
                        value = StatusDeviceTuya(code)
                        # Loop through StatusProperties to set the mode
                        for item in StatusProperties:
                            if item['code'] == code:
                                the_values = json.loads(item['values'])
                                mode = ['No fault']
                                if item['type'] == 'Bitmap':
                                    mode.extend(the_values.get('label'))
                                    currentmode = mode[value].replace("_", " ").capitalize()
                                else:
                                    mode.extend(the_values.get('range'))
                                    currentmode = mode[value].replace("_", " ").capitalize()
                        # Only update if the new value differs from the current value
                        if str(currentmode) != str(Devices[dev['id']].Units[unit].nValue):
                            UpdateDevice(dev['id'], unit, str(currentmode), 1, 0)
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
                            for unit in Devices[dev['id']].Units:
                                if str(currentbattery) != str(Devices[dev['id']].Units[unit].BatteryLevel):
                                    Devices[dev['id']].Units[unit].BatteryLevel = currentbattery
                                    Devices[dev['id']].Units[unit].Update()
                        return
                    # status Domoticz
                    try:
                        sValue = Devices[dev['id']].Units[1].sValue
                        nValue = Devices[dev['id']].Units[1].nValue
                    except:
                        pass

                    if dev_type == 'switch':
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
                            UpdateDevice(dev['id'], 11, str(currentcurrent), 0, 0)
                            UpdateDevice(dev['id'], 12, str(currentpower), 0, 0)
                            UpdateDevice(dev['id'], 13, str(currentvoltage), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[14].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev['id']].Units[14].sValue if len(Devices[dev['id']].Units[14].sValue) > 0 else '0;0'
                            currentEle = StatusDeviceTuya('add_ele')
                        update_value_device('leakage_current', 15)
                        update_value_device('temp_current', 16)
                        update_power_device('out_power', 17)
                        update_power_device('out_power', 18)
                        if searchCode('power_a', StatusProperties):
                            powerA = StatusDeviceTuya('power_a')
                            dirA = StatusDeviceTuya('direction_a')
                            if dirA == 'REVERSE':
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[19].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev['id']].Units[19].sValue if len(Devices[dev['id']].Units[19].sValue) > 0 else '0;0'
                                lastvalueR = Devices[dev['id']].Units[20].sValue if len(Devices[dev['id']].Units[20].sValue) > 0 else '0;0'
                                UpdateDevice(dev['id'], 19, str(powerA) + ';' + str(float(lastvalue.split(';')[1]) + ((powerA) * (lastupdate / 3600))) , 0, 0, 1)
                                UpdateDevice(dev['id'], 20, '0;' + str(float(lastvalueR.split(';')[1])) , 0, 0, 1)
                            if dirA == 'FORWARD':
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[20].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev['id']].Units[20].sValue if len(Devices[dev['id']].Units[20].sValue) > 0 else '0;0'
                                lastvalueR = Devices[dev['id']].Units[19].sValue if len(Devices[dev['id']].Units[19].sValue) > 0 else '0;0'
                                UpdateDevice(dev['id'], 20, str(powerA) + ';' + str(float(lastvalue.split(';')[1]) + ((powerA) * (lastupdate / 3600))) , 0, 0, 1)
                                UpdateDevice(dev['id'], 19, '0;' + str(float(lastvalueR.split(';')[1])) , 0, 0, 1)
                        if searchCode('power_b', StatusProperties):
                            powerB = StatusDeviceTuya('power_b')
                            dirB = StatusDeviceTuya('direction_b')
                            if dirB == 'REVERSE':
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[21].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev['id']].Units[21].sValue if len(Devices[dev['id']].Units[21].sValue) > 0 else '0;0'
                                lastvalueR = Devices[dev['id']].Units[22].sValue if len(Devices[dev['id']].Units[22].sValue) > 0 else '0;0'
                                UpdateDevice(dev['id'], 21, str(powerB) + ';' + str(float(lastvalue.split(';')[1]) + ((powerB) * (lastupdate / 3600))) , 0, 0, 1)
                                UpdateDevice(dev['id'], 22, '0;' + str(float(lastvalueR.split(';')[1])) , 0, 0, 1)
                            if dirB == 'FORWARD':
                                lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[22].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                                lastvalue = Devices[dev['id']].Units[22].sValue if len(Devices[dev['id']].Units[22].sValue) > 0 else '0;0'
                                lastvalueR = Devices[dev['id']].Units[21].sValue if len(Devices[dev['id']].Units[21].sValue) > 0 else '0;0'
                                UpdateDevice(dev['id'], 22, str(powerB) + ';' + str(float(lastvalue.split(';')[1]) + ((powerB) * (lastupdate / 3600))) , 0, 0, 1)
                                UpdateDevice(dev['id'], 21, '0;' + str(float(lastvalueR.split(';')[1])) , 0, 0, 1)
                        battery_device()

                    if dev_type == 'dimmer':
                        if searchCode('switch_led_1', StatusProperties):
                            currentstatus = StatusDeviceTuya('switch_led_1')
                            currentdim = brightness_to_pct(StatusProperties, 'bright_value_1', int(StatusDeviceTuya('bright_value_1')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDevice(dev['id'], 1, False, 0, 0)
                            elif bool(currentstatus) == True and  currentdim > 0 and str(currentdim) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, currentdim, 1, 0)

                        if searchCode('switch_led_2', StatusProperties):
                            currentstatus = StatusDeviceTuya('switch_led_2')
                            currentdim = brightness_to_pct(StatusProperties, 'bright_value_2', int(StatusDeviceTuya('bright_value_2')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDevice(dev['id'], 2, False, 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, currentdim, 1, 0)

                    if dev_type in ('light','fanlight'):
                        if searchCode('switch_led', StatusProperties):
                            currentstatus = StatusDeviceTuya('switch_led')
                        else:
                            currentstatus = StatusDeviceTuya('led_switch')
                        # UpdateDevice(dev['id'], 1, bool(currentstatus), int(bool(currentstatus)), 0)
                        if searchCode('work_mode', StatusProperties):
                            workmode = StatusDeviceTuya('work_mode')
                        else:
                            workmode = 'white'
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
                                UpdateDevice(dev['id'], 1, False, 0, 0)
                            elif (bool(currentstatus) == True and bool(nValue) != True):
                                UpdateDevice(dev['id'], 1, True, 1, 0)
                        if BrightnessControl == True:
                            if (bool(currentstatus) == False and bool(nValue) != False) or (int(dimtuya) == 0 and bool(nValue) != False):
                                UpdateDevice(dev['id'], 1, False, 0, 0)
                            elif (bool(currentstatus) == True and bool(nValue) != True) or (str(dimtuya) != str(sValue) and bool(nValue) != False):
                                UpdateDevice(dev['id'], 1, dimtuya, 1, 0)
                        if currentstatus == True and workmode == 'white':
                            color = Devices[dev['id']].Units[1].Color
                            if len(color) != 0:
                                color = ast.literal_eval(color)
                                if searchCode('temp_value_v2', StatusProperties):
                                    temptuya = {'b':0,'cw':0,'g':0,'m':2,'r':0,'t':int(inv_val(round(StatusDeviceTuya('temp_value_v2') / 10))),'ww':0}
                                else:
                                    temptuya = {'b':0,'cw':0,'g':0,'m':2,'r':0,'t':int(round(StatusDeviceTuya('temp_value'))),'ww':0}
                                if int((temptuya['t'])) != int(color['t']):
                                    UpdateDevice(dev['id'], 1, dimtuya, 1, 0)
                                    UpdateDevice(dev['id'], 1, temptuya, 1, 0)
                        if currentstatus == True and workmode == 'colour':
                            color = Devices[dev['id']].Units[1].Color
                            if len(color) == 0:
                                color = {'m': 3, 't': 0, 'r': 0, 'g': 0, 'b': 0, 'cw': 0, 'ww': 0}
                            if colortuya:
                                if isinstance(color, str):
                                    color = ast.literal_eval(color)  # Convert string to dictionary if needed

                                # Extract RGB values correctly from colortuya
                                r_in = int(colortuya[0:2], 16)
                                g_in = int(colortuya[2:4], 16)
                                b_in = int(colortuya[4:6], 16)

                                if searchCode('colour_data_v2', StatusProperties):
                                    h, s, level = rgb_to_hsv_v2(r_in, g_in, b_in)
                                    r, g, b = hsv_to_rgb_v2(h, s, 1000)  # Adjusted scale to 1000 if needed
                                else:
                                    h, s, level = rgb_to_hsv(r_in, g_in, b_in)
                                    r, g, b = hsv_to_rgb(h, s, 100)

                                # Preserve 'cw' and 'ww' values from existing color struct
                                colorupdate = {
                                    'm': 3,        # Color mode remains 3 (assuming this means RGB mode)
                                    't': color.get('t', 0),  # Retain temperature if applicable
                                    'r': r,
                                    'g': g,
                                    'b': b,
                                    'cw': color.get('cw', 0),  # Preserve Cold White level
                                    'ww': color.get('ww', 0),  # Preserve Warm White level
                                }
                                # Check if RGB values have changed before updating the device
                                if r_in != colorupdate['r'] or g_in != colorupdate['g'] or b_in != colorupdate['b']:#or not Devices[dev['id']].Units[1].get("Color"):
                                    UpdateDevice(dev['id'], 1, colorupdate, 1, 0)
                                    # UpdateDevice(dev['id'], 1, brightness_to_pct(StatusProperties, 'bright_value', int(inv_val(level))), 1, 0)

                    if dev_type == 'cover':
                        if searchCode('position', StatusProperties) or searchCode('percent_control', StatusProperties):
                            if searchCode('position', StatusProperties):
                                currentposition = StatusDeviceTuya('position')
                            elif searchCode('percent_control', StatusProperties):
                                currentposition = StatusDeviceTuya('percent_control')
                            if str(currentposition) == '0':
                                UpdateDevice(dev['id'], 1, currentposition, 0, 0)
                            if str(currentposition) == '100':
                                UpdateDevice(dev['id'], 1, currentposition, 1, 0)
                            if str(currentposition) != str(Devices[dev['id']].Units[1].sValue):
                                UpdateDevice(dev['id'], 1, currentposition, 2, 0)
                        elif searchCode('mach_operate', StatusProperties):
                            currentstatus = StatusDeviceTuya('control')
                            if currentstatus == 'close':
                                UpdateDevice(dev['id'], 1, 'ZZ', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDevice(dev['id'], 1, 'FZ', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDevice(dev['id'], 1, 'STOP', 1, 0)
                        elif searchCode('control', StatusProperties):
                            currentstatus = StatusDeviceTuya('control')
                            if currentstatus == 'close':
                                UpdateDevice(dev['id'], 1, 'Open', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDevice(dev['id'], 1, 'Close', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDevice(dev['id'], 1, 'Stop', 1, 0)
                        if searchCode('position_2', StatusProperties) or searchCode('percent_control_2', StatusProperties):
                            if searchCode('position_2', StatusProperties):
                                currentposition = StatusDeviceTuya('position_2')
                            elif searchCode('percent_control_2', StatusProperties):
                                currentposition = StatusDeviceTuya('percent_control_2')
                            if str(currentposition) == '0':
                                UpdateDevice(dev['id'], 2, currentposition, 0, 0)
                            if str(currentposition) == '100':
                                UpdateDevice(dev['id'], 2, currentposition, 1, 0)
                            if str(currentposition) != str(Devices[dev['id']].Units[2].sValue):
                                UpdateDevice(dev['id'], 2, currentposition, 2, 0)
                        elif searchCode('mach_operate_2', StatusProperties):
                            currentstatus = StatusDeviceTuya('control_2')
                            if currentstatus == 'close':
                                UpdateDevice(dev['id'], 2, 'ZZ', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDevice(dev['id'], 2, 'FZ', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDevice(dev['id'], 2, 'STOP', 1, 0)
                        elif searchCode('control_2', StatusProperties):
                            currentstatus = StatusDeviceTuya('control_2')
                            if currentstatus == 'close':
                                UpdateDevice(dev['id'], 2, 'Open', 0, 0)
                            elif currentstatus == 'open':
                                UpdateDevice(dev['id'], 2, 'Close', 1, 0)
                            elif currentstatus == 'stop':
                                UpdateDevice(dev['id'], 2, 'Stop', 1, 0)

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
                        elif update_dualvalue_device('local_temp','local_hum', 3):
                            pass
                        elif update_dualvalue_device('Tin','Hin', 3):
                            pass
                        update_value_device('co2_value', 4)
                        update_value_device('air_quality_index', 5)
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
                        update_bool_device('temper_alarm', 49)
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
                            UpdateDevice(dev['id'], 1, str(currentcurrent), 0, 0)
                            UpdateDevice(dev['id'], 2, str(currentpower), 0, 0)
                            UpdateDevice(dev['id'], 3, str(currentvoltage), 0, 0)
                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[4].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
                            lastvalue = Devices[dev['id']].Units[4].sValue if len(Devices[dev['id']].Units[4].sValue) > 0 else '0;0'
                            UpdateDevice(dev['id'], 4, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)
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
                            UpdateDevice(dev['id'], 1, 'Gateway only', 0, 0)

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
                        #         UpdateDevice(dev['id'], 1, False, 0, 0)
                        #     elif currentstatus == 'alarm':
                        #         UpdateDevice(dev['id'], 1, True, 1, 0)
                        #     UpdateDevice(dev['id'], 2, currentstatus, 0, 0)
                        # if searchCode('PIR', StatusProperties):
                        #     currentstatus = StatusDeviceTuya('PIR')
                        #     if int(currentstatus) == 0:
                        #         UpdateDevice(dev['id'], 1, False, 0, 0)
                        #     elif int(currentstatus) > 0:
                        #         UpdateDevice(dev['id'], 1, True, 1, 0)
                        #     UpdateDevice(dev['id'], 2, currentstatus, 0, 0)
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
                            color = Devices[dev['id']].Units[1].Color
                            if color == '': color = {"b":255,"cw":0,"g":255,"m":3,"r":255,"t":0,"ww":0}
                            h, s, v = tuyacolor['h'], tuyacolor['s'], tuyacolor['v']
                            r, g, b = hsv_to_rgb_v2(h, s, v)
                            colorupdate = {'b':b,'cw':0,'g':g,'m':3,'r':r,'t':0,'ww':0}
                            # {"b":0,"cw":0,"g":3,"m":3,"r":255,"t":0,"ww":0}
                            if (color['r'] != r or color['g'] != g or color['b'] != b ):
                                UpdateDevice(dev['id'], 1, colorupdate, 1, 0)
                                UpdateDevice(dev['id'], 1, brightness_to_pct(StatusProperties, 'bright_value', int(v * 0.255)), 1, 0)
                        update_bool_device('colour_switch', 2)
                        if searchCode('laser_switch', StatusProperties):
                            currentstatus = StatusDeviceTuya('laser_switch')
                            currentdim = brightness_to_pct(StatusProperties, 'laser_bright', int(StatusDeviceTuya('laser_bright')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDevice(dev['id'], 3, False, 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev['id']].Units[3].sValue):
                                UpdateDevice(dev['id'], 3, True, 1, 0)
                                UpdateDevice(dev['id'], 3, currentdim, 1, 0)
                        if searchCode('fan_switch', StatusProperties):
                            currentstatus = StatusDeviceTuya('fan_switch')
                            currentdim = brightness_to_pct(StatusProperties, 'fan_speed', int(StatusDeviceTuya('fan_speed')))
                            if bool(currentstatus) == False or currentdim == 0:
                                UpdateDevice(dev['id'], 4, False, 0, 0)
                            elif bool(currentstatus) == True and currentdim > 0 and str(currentdim) != str(Devices[dev['id']].Units[4].sValue):
                                UpdateDevice(dev['id'], 4, True, 1, 0)
                                UpdateDevice(dev['id'], 4, currentdim, 1, 0)

                    if dev_type == 'smartlock':
                        update_bool_device('lock_motor_state', 1)
                        update_select_device('alarm_lock', 2)
                        # if searchCode('unlock_temporary', StatusProperties):
                        #     currentstatus = StatusDeviceTuya('unlock_temporary')
                        #     if currentstatus == 0:
                        #         UpdateDevice(dev['id'], 3, False, 0, 0)
                        #     else:
                        #         UpdateDevice(dev['id'], 3, True, 1, 0)
                        battery_device()

                    if dev_type == 'dehumidifier':
                        update_bool_device('switch', 1)
                        if update_selectnum_device('dehumidify_set_value', 2):
                            pass
                        elif update_selectnum_device('dehumidify_set_enum', 2):
                            pass
                        update_select_device('mode', 3)
                        update_select_device('fan_speed_enum', 4)
                        # update_bool_device('anion', 5)
                        # update_value_device('temp_indoor', 6)
                        # update_nvalue_device('humidity_indoor', 7)
                        # update_dualvalue_device('temp_indoor', 'humidity_indoor', 8)
                        update_text_device('fault', 5)

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
                        update_bool_device('MachineRainMode', 2)
                        update_value_device('MachineStatus', 3)
                        update_value_device('MachineWarning', 4)
                        update_value_device('MachineError', 5)
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
                    Domoticz.Error('Device read failed: ' + str(dev['id']))
                    Domoticz.Debug('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

    except Exception as err:
        Domoticz.Error('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

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
def DeviceType(category, product_id=None):
    'convert category to device type'
    'https://github.com/tuya/tuya-home-assistant/wiki/Supported-Device-Category'
    if product_id == 'uoa3mayicscacseb' or product_id == 'igtakqsfhbr7qsp7':
        result = 'cover'
    elif product_id == 'chfpey4klfcp1ipl':
        result = 'dimmer'
    elif product_id == 'x3o8epevyeo3z3oa':
        result = 'sensor'
    elif product_id == 'p6sqiuesvhmhvv4f':
        result = 'doorcontact'
    elif category in {'kg', 'cz', 'pc', 'tdq', 'znjdq', 'szjqr', 'aqcz'}:
        result = 'switch'
    elif category in {'dj', 'dd', 'dc', 'fwl', 'xdd', 'fwd', 'jsq', 'tyndj', 'tyd'}:
        result = 'light'
    elif category in {'tgq', 'tgkg'}:
        result = 'dimmer'
    elif category in {'cl', 'clkg', 'jdcljqr'}:
        result = 'cover'
    elif category in {'qn'}:
        result = 'heater'
    elif category in {'wk', 'wkf', 'mjj', 'wkcz', 'kt','hwktwkq', 'ydkt', 'cjkg'}:
        result = 'thermostat'
    elif category in {'wsdcg', 'co2bj', 'hjjcy', 'qxj', 'ldcg', 'swtz', 'zwjcy','pir','dgnbj'}:
        result = 'sensor'
    elif category in {'rs'}:
        result = 'heatpump'
    elif category in {'znrb'}:
        result = 'smartheatpump'
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
    elif category in {'zndb', 'dlq'}:
        result = 'powermeter'
    elif category in {'wg2', 'wfcon'}:
        result = 'gateway'
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
    elif category in {'sfkzq'}:
        result = 'irrigation'
    elif category in {'wxkg'}:
        result = 'wswitch'
    elif category in {'xktyd'}:
        result = 'starlight'
    elif category in {'ms'}:
        result = 'smartlock'
    elif category in {'cs'}:
        result = 'dehumidifier'
    elif category in {'sd'}:
        result = 'vacuum'
    elif category in {'mal'}:
        result = 'multifunctionalarm'
    elif category in {'kj'}:
        result = 'purifier'
    elif category in {'bh'}:
        result = 'smartkettle'
    elif category in {'gcj'}:
        result = 'mower'
    elif category in {'hps'}:
        result = 'human_presence'
    elif category in {'qccdz'}:
        result = 'evcharger'
    elif category in {'infrared_ac'}:
        result = 'infrared_ac'
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
            if isinstance(sValue, (int, float)):
                Devices[ID].Units[Unit].LastLevel = int(sValue)
            elif isinstance(sValue, (dict)):
                Devices[ID].Units[Unit].Color = sValue
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
    if isinstance(valueRaw, (int, float)):
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
    elif isinstance(Status, (int, float)) and not isinstance(Status, bool):
        actual_status = set_scale(sendfunction, actual_function_name, Status)
    # Domoticz.Debug("actual_function_name:" + str(actual_function_name))
    # Domoticz.Debug("actual_status:" + str(actual_status))
    if actual_function_name in ('PowerOff', 'PowerOn'):
        uri='devices/'
    else:
        uri='iot-03/devices/'
    if testData != True:
        tuya.sendcommand(ID, {'commands': [{'code': actual_function_name, 'value': actual_status}]}, uri)
    Domoticz.Debug('Command send to tuya :' + str(ID) + ", " + str({'commands': [{'code': str(actual_function_name), 'value': str(actual_status)}]}) + ", " + str(uri))

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
    except:
        result = str(raw)
    return result

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
        if product_id == 'g9m7honkxjweukvt' and actual_function_name == 'temp_current':
            result = float(raw / 10)
    except:
        result = raw
        Domoticz.Debug('except ' + str(result))
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

def deleteDevice(ID, Unit):
    if ID in Devices:
        Domoticz.Log("Deleting device with ID " + str(ID) + " Unit " + str(Unit) + ".")
        Devices[ID].Units[Unit].Delete()
    else:
        Domoticz.Debug("Device with ID " + str(ID) + " not found. Cannot delete.")

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

def version(ver):
    return tuple(map(int, (ver.split("."))))