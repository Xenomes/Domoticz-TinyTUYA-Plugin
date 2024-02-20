#!/usr/bin/env python3

# The script is intended to get a list of all devices available via Tuya API endpoint.
import argparse
import tinytuya
import json
import os
import sys
import time

class TuyaDeviceManager:
    def __init__(self, region, apikey, apisecret, deviceid):
        self.region = region
        self.apikey = apikey
        self.apisecret = apisecret
        self.deviceid = deviceid
        self.token = None

    def connect_to_cloud(self):
        try:
            c = tinytuya.Cloud(
                apiRegion=self.region,
                apiKey=self.apikey,
                apiSecret=self.apisecret,
                apiDeviceID=self.deviceid
            )
            c.use_old_device_list = True
            c.new_sign_algorithm = True

            if c.error is not None:
                raise Exception(c.error['Payload'])

            self.token = c.token

            if self.token is None:
                raise Exception('Credentials are incorrect!')

            return c

        except Exception as err:
            print('Error connecting to Tuya Cloud:', str(err))
            return None

    def get_device_list(self):
        try:
            tuya_cloud = self.connect_to_cloud()
            if tuya_cloud:
                devices = []
                while len(devices) == 0:
                    devices = tuya_cloud.getdevices()
                    print('Script is running, please wait!')
                    time.sleep(10)

                for device in devices:
                    device['key'] = 'Deleted'

                return devices

        except Exception as err:
            print('Error getting device list:', str(err))
            return None

    def dump_device_list_to_file(self):
        try:
            devices = self.get_device_list()
            if devices:
                with open("dump.json", "w") as f:
                    f.write("List of devices: \n" + json.dumps(devices, indent=2))
                print('dump.json is created!')

        except Exception as err:
            print('Error dumping device list to file:', str(err))

def parse_arguments():
    parser = argparse.ArgumentParser(description='Get a list of all devices available via Tuya API endpoint.')
    parser.add_argument('--region', help='Tuya region associated with your account (e.g., us, eu, cn). Must be enclosed in quotes.', required=True)
    parser.add_argument('--apikey', help='Tuya API key linked to your account. Must be enclosed in quotes.', required=True)
    parser.add_argument('--apisecret', help='Tuya API secret corresponding to your API key. Must be enclosed in quotes.', required=True)
    parser.add_argument('--deviceid', help='Tuya device ID for your device. Must be enclosed in quotes.', required=True)
    parser.add_argument('--h', action='help', help='Show this help message and exit')
    parser.epilog = "TUYA ACCOUNT - Set up a Tuya Account: https://github.com/jasonacox/tinytuya/files/8145832/Tuya.IoT.API.Setup.pdf"
    return parser.parse_args()

def main():
    args = parse_arguments()
    manager = TuyaDeviceManager(args.region, args.apikey, args.apisecret, args.deviceid)
    manager.dump_device_list_to_file()

if __name__ == "__main__":
    main()