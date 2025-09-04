# PiFire System Control Fix for Raspberry Pi

## Problem Description
The reboot, restart, and shutdown commands in PiFire were not working properly on Raspberry Pi 3/4 systems. This was due to several issues:

1. **Systemd vs SysV**: Modern Raspberry Pi systems use systemd, but PiFire was using older SysV-style commands
2. **Permission Issues**: The PiFire user didn't have proper sudo permissions for system control commands
3. **Error Handling**: No fallback mechanisms when commands failed
4. **Blocking Operations**: Commands were blocking the web interface

## Solution Implemented

### 1. Updated System Control Functions (`common/common.py`)

The following functions were completely rewritten with modern systemd support:

- `reboot_system()` - Now uses `systemctl reboot` with fallback to `reboot`
- `shutdown_system()` - Now uses `systemctl poweroff` with fallback to `shutdown -h now`
- `restart_scripts()` - Now uses `systemctl restart supervisor` with fallback to `service supervisor restart`

#### Key Improvements:
- **Modern systemd commands**: Uses `systemctl` first, falls back to legacy commands
- **Background execution**: Commands run in separate threads to avoid blocking the web interface
- **Better error handling**: Captures and logs errors, provides multiple fallback options
- **Timeout protection**: Commands have 10-second timeouts to prevent hanging

### 2. Enhanced Mobile Interface (`blueprints/mobile/socket_io.py`)

Updated the mobile socket interface to use the improved functions with better error handling.

### 3. Sudo Permissions Setup Script

Created `setup_pifire_permissions.sh` to automatically configure the necessary sudo permissions:

```bash
sudo ./setup_pifire_permissions.sh
```

This script creates `/etc/sudoers.d/pifire` with the necessary NOPASSWD entries for:
- System reboot and shutdown commands
- Supervisor service control
- Legacy service commands

## Installation and Setup

### For New Installations
The fix is automatically included in the updated PiFire code.

### For Existing Installations

1. **Apply the code changes** (already done if you have the updated files)

2. **Set up sudo permissions**:
   ```bash
   cd /usr/local/bin/pifire
   sudo ./setup_pifire_permissions.sh
   ```

3. **Test the functionality**:
   ```bash
   cd /usr/local/bin/pifire
   python test_system_simple.py
   ```

4. **Restart PiFire services**:
   ```bash
   sudo systemctl restart supervisor
   ```

## Testing

Run the test script to verify everything works:
```bash
cd /usr/local/bin/pifire
python test_system_simple.py
```

Expected output should show:
- ✓ All system control commands available
- ✓ Sudo permissions working
- ✓ Supervisor service active
- ✓ All system control functions should work

## How It Works

### Reboot Process
1. User clicks "Reboot" in PiFire interface
2. Function runs in background thread
3. Waits 3 seconds for web response to be sent
4. Tries `sudo systemctl reboot`
5. Falls back to `sudo reboot` if systemctl fails
6. System reboots cleanly

### Shutdown Process
1. User clicks "Shutdown" in PiFire interface
2. Function runs in background thread
3. Waits 3 seconds for web response to be sent
4. Tries `sudo systemctl poweroff`
5. Falls back to `sudo shutdown -h now` if systemctl fails
6. System shuts down cleanly

### Restart Process
1. User clicks "Restart Server" in PiFire interface
2. Function runs in background thread
3. Tries `sudo systemctl restart supervisor`
4. Falls back to `sudo service supervisor restart` if needed
5. PiFire services restart without system reboot

## Troubleshooting

### "Permission denied" errors
Run the setup script:
```bash
sudo ./setup_pifire_permissions.sh
```

### Commands still not working
1. Check if your user is in the sudo group:
   ```bash
   groups $USER
   ```

2. Verify supervisor is installed and running:
   ```bash
   sudo systemctl status supervisor
   ```

3. Test sudo permissions manually:
   ```bash
   sudo -n systemctl status supervisor
   ```

### Web interface becomes unresponsive
The new implementation runs commands in background threads, so this should no longer happen. If it does, try:
```bash
sudo systemctl restart supervisor
```

## Compatibility

This fix is compatible with:
- Raspberry Pi 3/4/5
- Raspbian/Raspberry Pi OS (Bookworm, Bullseye, Buster)
- Other Debian-based systems with systemd
- Legacy SysV systems (via fallback commands)

## Files Modified

- `common/common.py` - Updated system control functions
- `blueprints/mobile/socket_io.py` - Enhanced error handling
- `setup_pifire_permissions.sh` - New sudo permissions setup script
- `test_system_simple.py` - Test script for verification

## Security Notes

The sudo permissions are configured to only allow specific system control commands without passwords. This is a standard practice for system service management and follows the principle of least privilege.

The sudoers file `/etc/sudoers.d/pifire` only grants permissions for:
- System reboot/shutdown commands
- Supervisor service control
- No general sudo access is granted
