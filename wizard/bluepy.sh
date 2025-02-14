#!/bin/bash

# This file will add the cap_net_raw,cap_net_admin+eip capability to the bluepy-helper file to ensure proper permissions

# Find all bluepy-helper executables in various possible locations
BLUEPY_HELPERS=$(find /usr/local/bin/pifire/lib/ -path "*/bluepy/bluepy-helper" 2>/dev/null)

if [ -z "$BLUEPY_HELPERS" ]; then
    echo "No bluepy-helper found in the standard Python library locations"
    exit 1
fi

# Apply capabilities to each found bluepy-helper
for helper in $BLUEPY_HELPERS; do
    echo "Setting capabilities for $helper"
    sudo setcap "cap_net_raw,cap_net_admin+eip" "$helper"
    
    # Verify the capabilities were set
    getcap "$helper"
done

echo "All bluepy-helper executables have been configured"