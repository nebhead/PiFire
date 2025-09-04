#!/bin/bash
# 
# PiFire System Permissions Setup Script
# This script sets up the necessary sudo permissions for PiFire system operations
#

# Get the current user (the one running PiFire)
PIFIRE_USER=${USER}
if [ "$PIFIRE_USER" = "root" ]; then
    echo "Warning: Running as root. Checking for pifire user..."
    if id "pifire" &>/dev/null; then
        PIFIRE_USER="pifire"
    elif id "pi" &>/dev/null; then
        PIFIRE_USER="pi"
    else
        echo "Error: Could not determine PiFire user. Please run this script as the PiFire user."
        exit 1
    fi
fi

echo "Setting up sudo permissions for user: $PIFIRE_USER"

# Create sudoers file for PiFire
SUDOERS_FILE="/etc/sudoers.d/pifire"

# Check if we're running with sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script needs to be run with sudo privileges."
    echo "Please run: sudo $0"
    exit 1
fi

# Create the sudoers configuration
cat > "$SUDOERS_FILE" << EOF
# PiFire system control permissions
# Allows PiFire user to run system control commands without password

# System reboot and shutdown
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl reboot
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl halt
$PIFIRE_USER ALL=(ALL) NOPASSWD: /sbin/reboot
$PIFIRE_USER ALL=(ALL) NOPASSWD: /sbin/shutdown
$PIFIRE_USER ALL=(ALL) NOPASSWD: /sbin/halt
$PIFIRE_USER ALL=(ALL) NOPASSWD: /sbin/poweroff

# Supervisor control
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart supervisor
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start supervisor
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop supervisor
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl restart *
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl start *
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl stop *
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/sbin/service supervisor *

# Legacy service commands
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/sbin/service supervisor restart
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/sbin/service supervisor start
$PIFIRE_USER ALL=(ALL) NOPASSWD: /usr/sbin/service supervisor stop
EOF

# Set proper permissions on the sudoers file
chmod 440 "$SUDOERS_FILE"

# Validate the sudoers file
if visudo -c -f "$SUDOERS_FILE"; then
    echo "✓ Successfully created PiFire sudoers configuration at $SUDOERS_FILE"
    echo "✓ User '$PIFIRE_USER' now has permission to run system control commands"
    echo ""
    echo "You can now use the following commands without password:"
    echo "  - System reboot/shutdown"
    echo "  - Supervisor service control"
    echo ""
    echo "Test the configuration with:"
    echo "  sudo -u $PIFIRE_USER sudo systemctl status supervisor"
else
    echo "❌ Error: Invalid sudoers configuration created. Removing..."
    rm -f "$SUDOERS_FILE"
    exit 1
fi

echo "Setup complete!"
