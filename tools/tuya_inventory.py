#!/usr/bin/env python3
"""
tuya_inventory.py
==================

Scans both the local network (LAN, via UDP broadcast) and the Tuya Cloud
(for all configured accounts) for Tuya devices, and reports per device:
name, Device ID, IP address, and whether the device is reachable locally
(LAN) and/or via Pulsar (Tuya's realtime cloud push service).

Account configuration
----------------------
Each account is configured via its own JSON file, shaped like:

    {
      "apiRegion": "eu",
      "apiKey": "p5tyuihbfregvrx84",
      "apiSecret": "324dfdfgrhjyuukie4687mjfgfg0817",
      "apiDeviceID": "bf51ty568792183p9"
    }

The script looks for:
  - tuya_creds.json                (account label: "default")
  - tuya_creds.json.<label>        (account label: "<label>", e.g. "gmail", "outlook")

These files are expected in the CURRENT directory by default (the
directory you run this script from). If they live elsewhere, use --dir
to point at that directory. No credential files at all is fine too --
in that case only the local LAN scan is run and reported.

Two files with an identical apiKey/apiSecret are treated as the same
account; the first one found is used and later duplicates are skipped
(and noted in the report) so each account is only queried once.

Requirements
------------
  pip3 install tinytuya --break-system-packages
Optional, only needed for the Pulsar check:
  pip3 install tuya-connector-python --break-system-packages

Usage
-----
  python3 tuya_inventory.py [--dir PATH] [--pulsar-seconds N] [--no-pulsar]
                             [--output FILE.txt]

  (--pulsar-seconds defaults to 30 if the option is not used; run with
  --help for full usage details)
"""

import argparse
import glob
import json
import os
import re
import sys
import threading
import time
from datetime import datetime

try:
    import tinytuya
except ImportError:
    print("ERROR: the 'tinytuya' package is not installed.")
    print("Install with: pip3 install tinytuya --break-system-packages")
    sys.exit(1)

try:
    from tuya_connector import TuyaOpenPulsar, TuyaCloudPulsarTopic
    PULSAR_AVAILABLE = True
except ImportError:
    PULSAR_AVAILABLE = False

# Same region endpoints the Domoticz plugin uses for Pulsar.
PULSAR_REGION_ENDPOINTS = {
    'eu': 'wss://mqe.tuyaeu.com:8285/',
    'us': 'wss://mqe.tuyaus.com:8285/',
    'cn': 'wss://mqe.tuyacn.com:8285/',
    'in': 'wss://mqe.tuyain.com:8285/',
}

REQUIRED_FIELDS = ['apiRegion', 'apiKey', 'apiSecret', 'apiDeviceID']

# Official Tuya Cloud "system error" codes (source: developer.tuya.com Open
# API error-code reference -- the layer tinytuya.Cloud() uses for token/
# signature/rate-limit/permission errors). Not exhaustive, but covers the
# errors most commonly seen with a misconfigured or expired account.
# Unknown codes get a clean fallback pointer to the official docs instead
# of a guessed explanation.
TUYA_BUSINESS_ERROR_CODES = {
    500: "System error -- the Tuya service is temporarily unreachable or the request timed out. Try again later.",
    1000: "The requested data does not exist. Check the parameters used.",
    1001: "Invalid 'secret' (Access Secret). Check the Access Secret in the Tuya IoT project.",
    1002: "access_token is missing/empty.",
    1003: "Invalid authorization type ('grant type').",
    1004: "Invalid signature. Usually a wrong Access Secret, or this host's system clock is too far off.",
    1005: "Invalid client_id (Access ID). Check the Access ID/Client ID in the Tuya IoT project.",
    1010: "The access token has EXPIRED. Normally refreshed automatically; if this keeps happening, check Access ID/Secret.",
    1011: "The access token is INVALID (e.g. after manually resetting the API key in the Tuya project).",
    1012: "The access token's status is invalid.",
    1013: "The request timestamp has expired or differs too much from the current time (check this host's system clock).",
    1100: "One or more required parameters are missing from the request.",
    1106: "Permission denied for this API or device -- check that the device is linked to this Tuya IoT project and that the right APIs are subscribed.",
    1114: "This request's IP address is not on this project's IP allowlist (IP allowlist is enabled on the Tuya IoT project).",
    1199: "Too many requests in a short time (rate limit). Try again later or increase the polling interval.",
    1400: "The access token is invalid.",
    2007: "This request's IP address belongs to a different Tuya data center (region) than the one this account is authorized for. Check that 'apiRegion' in the credential file is correct.",
    28841001: "No 'cloud development plan' is subscribed on this Tuya IoT project -- required to use the Cloud API.",
    28841002: "This project's 'cloud development plan' has expired.",
    28841003: "There is an outstanding bill for the cloud subscription.",
    28841004: "The free/trial edition quota has been used up.",
    28841101: "Not subscribed to this specific API.",
    28841102: "The subscription to this API has expired.",
    28841103: "There is an outstanding bill for this API.",
    28841104: "The quota for this API has been used up.",
    28841105: "This Tuya project is not authorized to use this API.",
}
_TUYA_ERROR_CODE_DOC_URL = "https://developer.tuya.com/en/docs/iot/open-api/api-reference/error-code"


def explain_tuya_error(err_field, error_text):
    """Builds, where possible, an extra explanation line for a Tuya Cloud
    error: both the meaning of tinytuya's own error code (the number in
    'Err', e.g. 913) and -- if present in the error message -- the
    meaning of the underlying Tuya error code itself (e.g. 'Code 1010'
    for an expired token). Returns None if nothing useful is known."""
    lines = []

    try:
        tinytuya_code = int(err_field)
        tinytuya_meaning = tinytuya.error_codes.get(tinytuya_code)
        if tinytuya_meaning:
            lines.append(f"tinytuya error code {tinytuya_code}: {tinytuya_meaning}")
    except (ValueError, TypeError):
        pass

    if error_text:
        m = re.search(r"Code '?(-?\d+)'?", error_text)
        if m:
            tuya_code = int(m.group(1))
            meaning = TUYA_BUSINESS_ERROR_CODES.get(tuya_code)
            if meaning:
                lines.append(f"Tuya error code {tuya_code}: {meaning}")
            else:
                lines.append(f"Tuya error code {tuya_code}: meaning not in the built-in list -- see {_TUYA_ERROR_CODE_DOC_URL}")

    if not lines:
        return None
    return "; ".join(lines)

# Compact, non-exhaustive translation of Tuya category codes to a
# readable type, purely for information in the report.
CATEGORY_LABELS = {
    'kg': 'switch', 'cz': 'switch (socket)', 'pc': 'switch (socket)',
    'tdq': 'switch/sensor', 'znjdq': 'switch', 'szjqr': 'switch', 'aqcz': 'switch',
    'dj': 'light', 'dd': 'light strip', 'dc': 'light strip', 'fwl': 'light',
    'xdd': 'ceiling light', 'fwd': 'light', 'jsq': 'light', 'tyndj': 'light', 'tyd': 'light',
    'tgq': 'dimmer', 'tgkg': 'dimmer',
    'cl': 'cover/curtain', 'clkg': 'cover/curtain', 'jdcljqr': 'cover/curtain', 'mc': 'cover/curtain',
    'qn': 'heater', 'rs': 'heatpump', 'znrb': 'smart heatpump',
    'wk': 'thermostat', 'wkf': 'thermostat', 'mjj': 'thermostat', 'wkcz': 'thermostat',
    'kt': 'thermostat', 'hwktwkq': 'thermostat', 'ydkt': 'thermostat', 'cjkg': 'thermostat',
    'wsdcg': 'sensor', 'co2bj': 'sensor', 'hjjcy': 'sensor', 'qxj': 'sensor',
    'ldcg': 'sensor', 'swtz': 'sensor', 'zwjcy': 'sensor', 'pir': 'motion sensor',
    'dgnbj': 'sensor', 'cobj': 'sensor', 'ywcgq': 'sensor',
    'mcs': 'doorcontact', 'sp': 'doorbell', 'qt': 'smokedetector/curtain',
}


def log(msg=""):
    print(msg)


# ---------------------------------------------------------------------------
# Reading account configuration
# ---------------------------------------------------------------------------

def account_label(path):
    base = os.path.basename(path)
    prefix = 'tuya_creds.json'
    if base == prefix:
        return 'default'
    if base.startswith(prefix + '.'):
        return base[len(prefix) + 1:]
    return base


def find_credential_files(directory):
    pattern = os.path.join(directory, 'tuya_creds.json*')
    return sorted(glob.glob(pattern))


def load_accounts(directory, report_lines):
    """Reads all tuya_creds.json(.label) files, and filters out duplicates
    (identical apiKey/apiSecret). Returns a list of account dicts."""
    files = find_credential_files(directory)
    accounts = []
    seen = {}  # (apiKey, apiSecret) -> label of the first file found

    if not files:
        report_lines.append(f"No tuya_creds.json(.<label>) files found in '{directory}'.")
        report_lines.append("Only the local LAN scan will be run; cloud/Pulsar information will be missing.")
        return accounts

    report_lines.append(f"Credential files found in '{directory}':")
    for path in files:
        label = account_label(path)
        base = os.path.basename(path)

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            report_lines.append(f"  - {base:<28} (account: {label}) [SKIPPED: could not read/parse -- {e}]")
            continue

        missing = [field for field in REQUIRED_FIELDS if not data.get(field)]
        if missing:
            report_lines.append(f"  - {base:<28} (account: {label}) [SKIPPED: missing fields {missing}]")
            continue

        key = (data['apiKey'], data['apiSecret'])
        if key in seen:
            report_lines.append(f"  - {base:<28} (account: {label}) [SKIPPED: duplicate of account '{seen[key]}', same apiKey/apiSecret]")
            continue

        seen[key] = label
        report_lines.append(f"  - {base:<28} (account: {label}, region: {data['apiRegion']})")
        accounts.append({
            'label': label,
            'path': path,
            'apiRegion': data['apiRegion'],
            'apiKey': data['apiKey'],
            'apiSecret': data['apiSecret'],
            'apiDeviceID': data['apiDeviceID'],
        })

    return accounts


# ---------------------------------------------------------------------------
# Local LAN scan
# ---------------------------------------------------------------------------

def scan_lan(report_lines):
    """One-off UDP broadcast scan (account-independent). Returns a dict
    {device_id: {'ip':.., 'version':..}}."""
    report_lines.append("Starting local LAN scan (UDP broadcast, may take a few seconds)...")
    start = time.time()
    try:
        localtuya = tinytuya.deviceScan(verbose=False, maxretry=None, byID=True) or {}
    except Exception as e:
        elapsed = time.time() - start
        report_lines.append(f"Local LAN scan FAILED after {elapsed:.1f}s: [{type(e).__name__}] {e}")
        report_lines.append("Possible cause: UDP ports 6666/6667/6668 blocked by a firewall, this "
                             "host on a different subnet/VLAN than the devices, or a network interface issue.")
        return {}
    elapsed = time.time() - start
    report_lines.append(f"Local LAN scan completed in {elapsed:.1f}s: {len(localtuya)} device(s) found on the local network.")
    return localtuya


# ---------------------------------------------------------------------------
# Cloud device list per account
# ---------------------------------------------------------------------------

def fetch_cloud_devices(account):
    """Returns (devices_list, error_message_or_None). devices_list is a
    list of raw Tuya device dicts as returned by the Cloud API."""
    try:
        cloud = tinytuya.Cloud(
            apiRegion=account['apiRegion'],
            apiKey=account['apiKey'],
            apiSecret=account['apiSecret'],
            apiDeviceID=account['apiDeviceID'],
        )
        result = cloud.getdevices()
    except Exception as e:
        return [], f"exception during cloud call: [{type(e).__name__}] {e}"

    if isinstance(result, dict) and result.get('Error'):
        err_field = result.get('Err', '?')
        error_text = result.get('Error')
        msg = f"Tuya Cloud API error: {error_text} (Err {err_field})"
        explanation = explain_tuya_error(err_field, error_text)
        if explanation:
            msg += f"\n    Explanation: {explanation}"
        return [], msg
    if not isinstance(result, list):
        return [], f"unexpected response from Tuya Cloud (not a device list): {result}"
    return result, None


# ---------------------------------------------------------------------------
# Pulsar (realtime cloud messages) check
# ---------------------------------------------------------------------------

def _extract_dev_id(raw_msg):
    """Same two message shapes the Domoticz plugin supports."""
    try:
        data = json.loads(raw_msg)
    except Exception:
        return None
    if 'bizData' in data:
        return data.get('bizData', {}).get('devId')
    return data.get('devId')


def _listen_one_account(account, seconds, results, errors):
    """Runs in its own thread: opens a Pulsar connection for this account,
    listens for 'seconds', and collects which device IDs sent at least one
    status message during that window."""
    endpoint = PULSAR_REGION_ENDPOINTS.get(account['apiRegion'])
    if not endpoint:
        errors[account['label']] = f"unknown region '{account['apiRegion']}'"
        return

    seen_ids = set()

    def _on_msg(msg):
        dev_id = _extract_dev_id(msg)
        if dev_id:
            seen_ids.add(dev_id)

    client = None
    try:
        client = TuyaOpenPulsar(account['apiKey'], account['apiSecret'], endpoint, TuyaCloudPulsarTopic.PROD)
        client.add_message_listener(_on_msg)
        client.start()
        time.sleep(seconds)
    except Exception as e:
        errors[account['label']] = f"[{type(e).__name__}] {e}"
    finally:
        if client is not None:
            try:
                client.stop()
            except Exception:
                pass

    results[account['label']] = seen_ids


def run_pulsar_listeners(accounts, seconds, report_lines):
    """Starts a concurrent Pulsar listener thread for each account, so the
    total wait time stays ~seconds instead of seconds * number of
    accounts. Returns {label: set(device_ids)}."""
    results = {}
    errors = {}

    if seconds <= 0:
        report_lines.append("Pulsar check skipped (--pulsar-seconds is 0 or --no-pulsar was used).")
        return results

    if not PULSAR_AVAILABLE:
        report_lines.append("Pulsar check skipped: the 'tuya-connector-python' package is not installed.")
        report_lines.append("Install with: pip3 install tuya-connector-python --break-system-packages")
        return results

    report_lines.append(f"Pulsar listen window of {seconds}s started for {len(accounts)} account(s)...")
    threads = []
    for account in accounts:
        t = threading.Thread(target=_listen_one_account, args=(account, seconds, results, errors), daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join(seconds + 10)

    for label, err in errors.items():
        report_lines.append(f"  - Pulsar account '{label}': ERROR -- {err}")
    for label, ids in results.items():
        report_lines.append(f"  - Pulsar account '{label}': connected successfully, {len(ids)} device(s) sent a message during the window.")

    return results


# ---------------------------------------------------------------------------
# Building the report
# ---------------------------------------------------------------------------

def format_table(headers, rows):
    """Builds a simple, space-aligned text table."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt_row(cells):
        return "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells))

    lines = [fmt_row(headers), "  ".join('-' * w for w in widths)]
    for row in rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def build_report(directory, pulsar_seconds):
    report_lines = []
    report_lines.append("=" * 78)
    report_lines.append(" TUYA DEVICE INVENTORY REPORT")
    report_lines.append(f" Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 78)
    report_lines.append("")

    accounts = load_accounts(directory, report_lines)
    report_lines.append("")

    report_lines.append("-" * 78)
    report_lines.append("Local LAN scan")
    report_lines.append("-" * 78)
    localtuya = scan_lan(report_lines)
    report_lines.append("")

    # Fetch cloud device lists per account
    all_devices = {}  # dev_id -> merged info
    account_errors = {}
    for account in accounts:
        report_lines.append("-" * 78)
        report_lines.append(f"Account: {account['label']} ({os.path.basename(account['path'])}, region: {account['apiRegion']})")
        report_lines.append("-" * 78)
        devices, err = fetch_cloud_devices(account)
        if err:
            report_lines.append(f"Cloud device list: ERROR -- {err}")
            account_errors[account['label']] = err
            report_lines.append("")
            continue
        report_lines.append(f"Cloud device list: OK, {len(devices)} device(s) found.")
        report_lines.append("")
        for dev in devices:
            dev_id = dev.get('id')
            if not dev_id:
                continue
            if dev_id not in all_devices:
                all_devices[dev_id] = {
                    'name': dev.get('name', 'Unknown'),
                    'category': dev.get('category', ''),
                    'online': dev.get('online'),
                    'accounts': [],
                    'pulsar_accounts': set(),
                }
            all_devices[dev_id]['accounts'].append(account['label'])

    # Pulsar listen window (only for accounts whose cloud list succeeded)
    working_accounts = [a for a in accounts if a['label'] not in account_errors]
    report_lines.append("-" * 78)
    report_lines.append("Pulsar (realtime cloud messages) check")
    report_lines.append("-" * 78)
    if not working_accounts and accounts:
        report_lines.append("Pulsar check skipped: no account had a working cloud device list.")
        pulsar_results = {}
    else:
        pulsar_results = run_pulsar_listeners(working_accounts, pulsar_seconds, report_lines)
    report_lines.append("")

    for label, dev_ids in pulsar_results.items():
        for dev_id in dev_ids:
            if dev_id in all_devices:
                all_devices[dev_id]['pulsar_accounts'].add(label)

    # Merge in LAN scan results; also show local devices that didn't
    # appear in any cloud list (e.g. no accounts configured, or the
    # device belongs to an account that wasn't supplied) separately.
    for dev_id, dev_info in localtuya.items():
        if dev_id not in all_devices:
            all_devices[dev_id] = {
                'name': '(unknown -- not in any cloud device list)',
                'category': '',
                'online': None,
                'accounts': [],
                'pulsar_accounts': set(),
            }

    report_lines.append("=" * 78)
    report_lines.append(" COMBINED OVERVIEW -- ALL UNIQUE DEVICES")
    report_lines.append("=" * 78)

    if not all_devices:
        report_lines.append("No devices found (no local devices and no working cloud accounts).")
    else:
        headers = ["Name", "Device ID", "Account(s)", "Type", "Online(cloud)", "Local", "Pulsar*", "IP address"]
        rows = []
        local_count = 0
        pulsar_count = 0
        for dev_id, info in sorted(all_devices.items(), key=lambda kv: kv[1]['name'].lower()):
            local_info = localtuya.get(dev_id)
            is_local = local_info is not None
            ip = local_info.get('ip', '-') if local_info else '-'
            version = local_info.get('version') if local_info else None
            local_str = f"yes (v{version})" if (is_local and version) else ("yes" if is_local else "no")
            pulsar_str = "seen" if info['pulsar_accounts'] else "not seen"
            online_str = {True: 'yes', False: 'no', None: '?'}.get(info['online'], '?')
            category = info['category']
            type_label = CATEGORY_LABELS.get(category, category or '?')
            accounts_str = ', '.join(info['accounts']) if info['accounts'] else '-'

            if is_local:
                local_count += 1
            if info['pulsar_accounts']:
                pulsar_count += 1

            rows.append([info['name'], dev_id, accounts_str, type_label, online_str, local_str, pulsar_str, ip])

        report_lines.append(format_table(headers, rows))
        report_lines.append("")
        report_lines.append("* Pulsar 'seen' means the device actually sent a status message during")
        report_lines.append("  the listen window. 'Not seen' does NOT mean Pulsar doesn't work for this")
        report_lines.append("  device -- it just means no status change happened within the window.")
        report_lines.append("  Increase --pulsar-seconds or change the device's status while this script")
        report_lines.append("  is running for a more reliable test.")
        report_lines.append("")
        report_lines.append(f"Total: {len(all_devices)} unique device(s), of which {local_count} reachable "
                             f"locally and {pulsar_count} seen via Pulsar during this window.")

    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(
        prog='tuya_inventory.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Scan both the local LAN (UDP broadcast) and the Tuya Cloud for Tuya "
            "devices, across one or more accounts, and print a combined, "
            "human-readable inventory report: device name, Device ID, IP address, "
            "and whether each device is reachable locally (LAN) and/or via Pulsar "
            "(Tuya's realtime cloud push service)."
        ),
        epilog=(
            "Credential files:\n"
            "  Each Tuya account is configured via its own JSON file:\n"
            "      tuya_creds.json            -> account label 'default'\n"
            "      tuya_creds.json.<label>    -> account label '<label>' (e.g. tuya_creds.json.gmail)\n"
            "  Required fields in each file: apiRegion, apiKey, apiSecret, apiDeviceID.\n"
            "  Example:\n"
            "      {\n"
            "        \"apiRegion\": \"eu\",\n"
            "        \"apiKey\": \"p5tyuihbfregvrx84\",\n"
            "        \"apiSecret\": \"324dfdfgrhjyuukie4687mjfgfg0817\",\n"
            "        \"apiDeviceID\": \"bf51ty568792183p9\"\n"
            "      }\n\n"
            "  By default these credential files are expected in the CURRENT working\n"
            "  directory (the directory you run this script from). If they live\n"
            "  somewhere else, point the script there with --dir. No credential files\n"
            "  at all is fine too -- in that case only the local LAN scan is run and\n"
            "  reported.\n\n"
            "  Two files with an identical apiKey/apiSecret are treated as the same\n"
            "  account; the first one found is used and later duplicates are skipped\n"
            "  (and noted in the report) so each account is only queried once.\n\n"
            "Examples:\n"
            "  python3 tuya_inventory.py\n"
            "      Look for credential files in the current directory, scan the LAN,\n"
            "      query the cloud for every account found, and listen for Pulsar\n"
            "      messages for 30 seconds per account.\n\n"
            "  python3 tuya_inventory.py --dir /etc/tuya --pulsar-seconds 60 --output report.txt\n"
            "      Look for credential files in /etc/tuya, listen for Pulsar messages\n"
            "      for 60 seconds, and also save the report to report.txt.\n\n"
            "  python3 tuya_inventory.py --no-pulsar\n"
            "      Skip the Pulsar check entirely (LAN scan + cloud device list only).\n"
        ),
    )
    parser.add_argument(
        '--dir', default='.', metavar='PATH',
        help=(
            "Directory to look for tuya_creds.json(.<label>) files in. "
            "Defaults to the CURRENT directory -- if your credential files live "
            "elsewhere, you must pass this option to point at that directory."
        ),
    )
    parser.add_argument(
        '--pulsar-seconds', type=int, default=30, metavar='N',
        help=(
            "How many seconds to listen for Tuya Pulsar (realtime cloud push) "
            "messages per account, run in parallel across accounts. "
            "Only devices that report a status change during this window will "
            "show as 'seen' via Pulsar. Default: 30. Use 0 to disable (same as "
            "--no-pulsar)."
        ),
    )
    parser.add_argument(
        '--no-pulsar', action='store_true',
        help="Skip the Pulsar check entirely, regardless of --pulsar-seconds.",
    )
    parser.add_argument(
        '--output', default=None, metavar='FILE',
        help="Also write the report to this text file, in addition to printing it.",
    )
    args = parser.parse_args()

    pulsar_seconds = 0 if args.no_pulsar else max(0, args.pulsar_seconds)

    report = build_report(os.path.abspath(args.dir), pulsar_seconds)
    print(report)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report + "\n")
            print(f"\nReport also written to: {args.output}")
        except OSError as e:
            print(f"\nCould not write report to {args.output}: {e}")


if __name__ == '__main__':
    main()