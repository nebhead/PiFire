#!/usr/bin/env python3
"""
Bluetooth BLE diagnostic script for PiFire.
Run this on the Raspberry Pi to identify why BLE scanning may not be working.
Usage: sudo python3 bt_diag.py   (or with venv: sudo /path/to/.venv/bin/python3 bt_diag.py)
"""

import subprocess
import sys
import os

SCAN_TIMEOUT = 5  # seconds

def section(title):
    print(f'\n{"="*60}')
    print(f'  {title}')
    print(f'{"="*60}')

def run_cmd(cmd, shell=False):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=shell, timeout=10)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return '', 'TIMEOUT', -1
    except FileNotFoundError:
        return '', f'Command not found: {cmd[0] if not shell else cmd}', -1

# ── 1. System info ────────────────────────────────────────────────────────────
section('1. System Info')
for cmd in [['uname', '-a'], ['cat', '/etc/os-release']]:
    out, err, rc = run_cmd(cmd)
    print(out or err)

# ── 2. BlueZ version ──────────────────────────────────────────────────────────
section('2. BlueZ Version')
out, err, rc = run_cmd(['bluetoothd', '--version'])
print(f'bluetoothd version: {out or err}')
out, err, rc = run_cmd(['dpkg', '-l', 'bluez'])
print(out or err)

# ── 3. Bluetooth adapter status ───────────────────────────────────────────────
section('3. Bluetooth Adapter (hciconfig)')
out, err, rc = run_cmd(['hciconfig', '-a'])
if rc != 0:
    print(f'hciconfig error: {err}')
else:
    print(out)

section('4. Bluetooth Adapter (hciconfig hci0 lescan check)')
out, err, rc = run_cmd(['hcitool', 'dev'])
print(f'hcitool dev: {out or err}')

# ── 5. bluetoothctl show ──────────────────────────────────────────────────────
section('5. bluetoothctl show')
out, err, rc = run_cmd(['bluetoothctl', 'show'])
print(out or err)

# ── 6. Check if bluetooth service is running ──────────────────────────────────
section('6. bluetooth service status')
out, err, rc = run_cmd(['systemctl', 'is-active', 'bluetooth'])
print(f'bluetooth service: {out or err}')
out, err, rc = run_cmd(['systemctl', 'status', 'bluetooth', '--no-pager', '-l'])
print(out or err)

# ── 7. Process capabilities ───────────────────────────────────────────────────
section('7. bluepy-helper capabilities')
out, err, rc = run_cmd(['find', '/', '-name', 'bluepy-helper', '-type', 'f'], shell=False)
# find may be slow; use a targeted search instead
out2, err2, rc2 = run_cmd('find /usr /home /root -name "bluepy-helper" -type f 2>/dev/null', shell=True)
helpers = out2.strip().splitlines()
if helpers:
    for h in helpers:
        cap_out, cap_err, _ = run_cmd(['getcap', h])
        print(f'{h}: {cap_out or "(no capabilities set)"}')
        # Also check file owner/permissions
        stat_out, _, _ = run_cmd(['ls', '-la', h])
        print(f'  {stat_out}')
else:
    print('No bluepy-helper found. Is bluepy installed in this Python environment?')

# ── 8. Current user / running as root? ───────────────────────────────────────
section('8. Current user & effective capabilities')
print(f'Running as: {os.getenv("USER", "unknown")} (uid={os.getuid()}, euid={os.geteuid()})')
out, err, rc = run_cmd(['capsh', '--print'])
print(out or err)

# ── 9. Python & bluepy version ────────────────────────────────────────────────
section('9. Python & bluepy version')
print(f'Python: {sys.version}')
print(f'Executable: {sys.executable}')
try:
    import bluepy
    try:
        import importlib.metadata
        bp_version = importlib.metadata.version('bluepy')
    except Exception:
        bp_version = 'unknown'
    print(f'bluepy version: {bp_version}')
    print(f'bluepy location: {bluepy.__file__}')
except ImportError as e:
    print(f'bluepy import failed: {e}')
    sys.exit(1)

# ── 10. Raw hcitool lescan (5 seconds) ───────────────────────────────────────
section('10. Raw hcitool lescan (5 seconds) — requires root/CAP_NET_RAW')
print('Running: sudo timeout 5 hcitool lescan')
out, err, rc = run_cmd('sudo timeout 5 hcitool lescan 2>&1 || true', shell=True)
print(out or '(no output)')

# ── 11. bleak BleakScanner.discover() ────────────────────────────────────────
section(f'11. bleak scan ({SCAN_TIMEOUT}s)')
try:
    import asyncio
    from bleak import BleakScanner

    async def _scan():
        print(f'  Calling BleakScanner.discover(timeout={SCAN_TIMEOUT})...')
        devices = await BleakScanner.discover(timeout=SCAN_TIMEOUT, return_adv=True)
        return devices

    found = asyncio.run(_scan())
    print(f'  Scan completed. Found {len(found)} device(s):')
    for addr, (dev, adv) in found.items():
        print(f'    {dev.name or "Unknown"} ({dev.address}) rssi={adv.rssi}')
    if not found:
        print('  !! No devices found.')
except ImportError:
    print('  bleak is not installed. Run: pip install bleak')
except Exception as e:
    print(f'  bleak scan FAILED: {type(e).__name__}: {e}')

print('\nDiagnostic complete.')
