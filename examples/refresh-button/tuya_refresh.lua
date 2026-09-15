-- Press the TinyTUYA Refresh button of a device when the router reports that
-- the device talked to the Tuya cloud (custom event from
-- tuya_refresh_events.sh). See README.md in this directory.
--
-- Why wait: the router sees the start of the exchange - e.g. the command from
-- the app on its way to the device - before the device has reported its new
-- state to the cloud. In my setup 3 s was enough: a zone switched on in the app
-- showed up in Domoticz 4 s after the command passed the router (the router
-- script adds up to 2 s). If the cloud is not there yet, the second press is.
--
-- Why twice: with flow offloading the router sees only the first packet after
-- a few seconds of silence, so a second change right after the first one sends
-- no new event. The press after 60 s catches it. Every new event cancels the
-- pending presses and schedules both again; each press costs 2 API calls.

local BUTTON = 'Irrigation controller (Refresh)' -- '<device name> (Refresh)' or its idx
local FIRST_S = 3
local SECOND_S = 60

return {
    on = {
        customEvents = { 'tuyaActivity' },
    },
    logging = {
        level = domoticz.LOG_INFO,
        marker = 'TuyaRefresh: ',
    },
    execute = function(domoticz, item)
        local button = domoticz.devices(BUTTON)
        if button == nil then
            domoticz.log('No device "' .. BUTTON .. '" - is the device ID in "Refresh button for device IDs"?', domoticz.LOG_ERROR)
            return
        end

        -- Push On button: every switchOn() is one refresh, its state does not matter
        button.cancelQueuedCommands()
        button.switchOn().afterSec(FIRST_S)
        button.switchOn().afterSec(SECOND_S)

        domoticz.log('Device activity (' .. tostring(item.data) .. ' packets) - refresh in '
            .. FIRST_S .. ' and ' .. SECOND_S .. ' s', domoticz.LOG_INFO)
    end
}
