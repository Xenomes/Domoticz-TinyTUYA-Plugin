# Refresh button triggered by an OpenWrt router

With a long API polling interval, a change made on the device, in the Tuya app
or by the device itself (e.g. a countdown that ends) reaches Domoticz only at
the next poll. A Tuya Wi-Fi device keeps one MQTT/TLS connection to the Tuya
cloud on port 8883 and every change travels over it. The router between the
device and the internet sees that traffic, so it can tell Domoticz "this device
just did something", and Domoticz refreshes that one device right away with the
[Refresh button](../../README.md#refresh-button-optional).

It also works for devices that do not answer on the LAN; in my case an
irrigation controller (category `sfkzq`).

```
device <-> Tuya cloud, MQTT/TLS on port 8883
  -> nft counter on the router, only packets >= 120 B    tuya-refresh.nft
    -> script on the router, checks the counter every 2 s  tuya_refresh_events.sh
      -> Domoticz custom event "tuyaActivity" (JSON API)
        -> dzVents presses the button after 3 s and 60 s    tuya_refresh.lua
          -> TinyTUYA reads this device: getconnectstatus + getstatus
```

## Requirements

* OpenWrt 22.03 or newer (firewall4, nftables) as the gateway of the device.
  Traffic that is only bridged, e.g. by a dumb access point, does not pass the
  forward hook.
* A static DHCP lease for the device.
* Domoticz with dzVents custom events; the router address in **Trusted
  Networks** (Setup > Settings > System), because the router sends the event
  without a login.
* TinyTUYA with the device ID in **Refresh button for device IDs**.

## 1. Measure the threshold

Check that the device keeps its cloud connection on port 8883
(192.168.1.50 is the device in all examples here):

```
grep 192.168.1.50 /proc/net/nf_conntrack | grep 8883
```

The device sends a small keep-alive every few minutes; a change is a bigger
packet. Log the packet sizes with a temporary chain:

```
nft add chain inet fw4 tuya_measure '{ type filter hook forward priority filter - 10; }'
nft add rule inet fw4 tuya_measure ip saddr 192.168.1.50 tcp dport 8883 log prefix '"tuya up: "'
nft add rule inet fw4 tuya_measure ip daddr 192.168.1.50 tcp sport 8883 log prefix '"tuya dn: "'
logread -f | grep tuya
```

Leave it idle for a few minutes, then switch something in the app and on the
device. `LEN=` in each line is the size that `meta length` compares. Pick a
threshold between the keep-alive and the changes. My irrigation controller:

| Event | First packet | `LEN=` |
|---|---|---|
| keep-alive, every 120 s | device -> cloud | 71 |
| command from the app | cloud -> device | 207 |
| button on the device | device -> cloud | 210-211 |

With 120 B there were no false events in 30 minutes and no change was missed.
Remove the chain afterwards:

```
nft flush chain inet fw4 tuya_measure
nft delete chain inet fw4 tuya_measure
```

## 2. Router

Put the device address and your threshold into `tuya-refresh.nft` and the
Domoticz address into `tuya_refresh_events.sh`, then:

```
scp -O tuya-refresh.nft root@192.168.1.1:/etc/nftables.d/20-tuya-refresh.nft
scp -O tuya_refresh_events.sh root@192.168.1.1:/root/
```

On the router:

```
chmod +x /root/tuya_refresh_events.sh
fw4 reload
nft list counter inet fw4 tuya_refresh
```

Add `/root/tuya_refresh_events.sh &` to `/etc/rc.local` before `exit 0`, and
both files to `/etc/sysupgrade.conf` so they survive a sysupgrade:

```
/etc/nftables.d/20-tuya-refresh.nft
/root/tuya_refresh_events.sh
```

Test that Domoticz accepts the event from the router; the answer should
contain `"status" : "OK"`:

```
wget -q -O - "http://192.168.1.20:8080/json.htm?type=command&param=customevent&event=tuyaActivity&data=1"
```

## 3. Domoticz

* Enter the device ID in **Refresh button for device IDs** and press Update on
  the Hardware page; the "*device name* (Refresh)" button appears.
* Add a dzVents script with the contents of `tuya_refresh.lua` and set `BUTTON`
  to the name (or idx) of that button.

Switch something in the app: the counter on the router grows, and the Domoticz
log shows `TuyaRefresh: Device activity (1 packets) - refresh in 3 and 60 s`,
followed by the updated device.

## Limitations

* **Flow offloading.** With software or hardware flow offloading the router
  passes an established connection through the fast path, which skips the
  forward hook. The rule then sees only the first packet after the connection
  has been quiet for a few seconds (4-6 s on my MT7621 router with hardware
  offloading). A second change right after the first one sends no event; the
  press after 60 s catches it. In my test a zone switched on in the app was in
  Domoticz 4 s after the command; switching it off again a few seconds later
  sent no event, and the press after 60 s brought the change. Without
  offloading every packet over the
  threshold is counted; the script sends one event per check and the dzVents
  script turns a burst into two presses.
* **Cost.** Each press is 2 API calls, so 4 per change. Commands sent from
  Domoticz go through the cloud too and also end in a refresh, which only
  confirms the state.
* **More devices.** Add a second counter and chain to the nft file, start the
  script a second time with its names
  (`tuya_refresh_events.sh tuya_refresh2 tuyaActivity2 &`) and add a second
  dzVents script for `tuyaActivity2`.
