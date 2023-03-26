#
#   Fake Domoticz - Domoticz Python plugin stub
#
#   With thanks to Frank Fesevur, 2017
#
#   Very simple module to make local testing easier
#   It "emulates" Domoticz.Log(), Domoticz.Error and Domoticz.Debug()
#   It also emulates the Device and Unit from the Ex framework
#
class Domoticz:
    def __init__(self):
        self.Units = []
        self.Devices = dict()
        return

    def Log(self, s):
        print(s)

    def Status(self, s):
        print(s)

    def Error(self, s):
        print(s)

    def Debug(self, s):
        print(s)
