#!/bin/sh
#
# tuya_refresh_events.sh [counter] [event]
#
# Turns the packet counter from tuya-refresh.nft into a Domoticz custom event,
# so that dzVents can press the TinyTUYA Refresh button. Runs on the OpenWrt
# router (busybox ash). Every CHECK_EVERY seconds it reads the counter; when
# the counter has grown it sends one custom event with the number of new
# packets as data. Waiting and debouncing are left to the dzVents script.
#
# Start it from /etc/rc.local (before "exit 0"):
#   /root/tuya_refresh_events.sh &
# One copy runs per counter, so for a second device add a second counter and
# start the script again with its names:
#   /root/tuya_refresh_events.sh tuya_refresh2 tuyaActivity2 &
#
# Domoticz must accept the request without a login: add the router address
# to "Trusted Networks" in the Domoticz settings.

DOMOTICZ="http://192.168.1.20:8080"
COUNTER="${1:-tuya_refresh}"
EVENT="${2:-tuyaActivity}"
CHECK_EVERY=2

log() {
    logger -t tuya_refresh "$1"
}

read_counter() {
    nft list counter inet fw4 "$COUNTER" 2>/dev/null | sed -n 's/.*packets \([0-9][0-9]*\).*/\1/p'
}

# One copy per counter - a second loop would send every event twice
PIDFILE="/var/run/tuya_refresh_events.$COUNTER.pid"
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"; exit 0' INT TERM

log "watching counter $COUNTER, event $EVENT -> $DOMOTICZ"
previous=""
while :; do
    now=$(read_counter)
    if [ -z "$now" ]; then
        # No counter: firewall4 is reloading or the rule file is gone
        previous=""
        sleep 30
        continue
    fi

    # A smaller value means "fw4 reload" has reset the counter: it only
    # becomes the new starting point
    if [ -n "$previous" ] && [ "$now" -gt "$previous" ]; then
        wget -q -T 10 -O /dev/null "$DOMOTICZ/json.htm?type=command&param=customevent&event=$EVENT&data=$((now - previous))" ||
            log "Domoticz did not accept event $EVENT ($DOMOTICZ)"
    fi
    previous=$now
    sleep "$CHECK_EVERY"
done
