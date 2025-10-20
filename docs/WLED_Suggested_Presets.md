# WLED Suggested Presets Feature

## Overview

The WLED Suggested Presets feature provides predefined LED lighting behaviors that automatically match grill states and events in PiFire. This eliminates the need for manual preset configuration and provides optimal visual feedback for different cooking scenarios.

## Feature Description

When enabled, PiFire will use direct color and effect commands to control your WLED device instead of relying on manually configured presets. The system follows a priority-based lighting scheme:

**Priority Order: Alarms > Warnings > General Status > Idle**

## LED Behavior Mapping

| PiFire State        | LED Behavior (6 LEDs)                          | Notes / Purpose                                  |
|---------------------|------------------------------------------------|--------------------------------------------------|
| **Idle (no cook)**  | Dim white solid glow                           | Shows device is powered on / ready               |
| **Booting**         | Slow white pulse (1s fade in/out)              | Visual feedback during PiFire startup            |
| **Preheat**         | Orange slow pulse (1s fade in/out)             | Grill warming up                                |
| **Cooking (active)**| Solid blue or green (user-selectable)          | Indicates an active cook in progress             |
| **Cool-down**       | Fade from orange → blue over 10s               | Visual indication grill is shutting down         |
| **Target Reached**  | Green flash (3x, 0.5s each)                    | Confirmation that probe target temp is met       |
| **Overshoot Alarm** | Rapid red strobe (5x, 0.2s each), then revert  | Alerts cook exceeded setpoint                   |
| **Probe Alarm**     | Red/white alternating flash (5s)               | Distinct warning for probe disconnect/trigger    |
| **Low Pellets**     | Yellow pulse (1s fade, every 10s)              | Gentle periodic reminder                         |
| **Timer Done**      | Rainbow chase (2s)                             | Fun celebratory effect                           |
| **Error / Fault**   | Solid red                                      | Critical error condition                         |
| **Night Mode**      | Very dim amber glow                            | Minimal non-distracting background status        |

## Configuration Options

### Basic Settings
- **Enable/Disable**: Toggle WLED integration on/off
- **Device Address**: IP address or hostname of your WLED device (static IP recommended)
- **Notification Duration**: How long event notifications stay active (default: 120 seconds)

### Suggested Preset Settings
- **Use Suggested Presets**: Enable the automatic lighting behaviors
- **Cooking Color**: Choose between blue or green for active cooking indicator
- **Idle Brightness**: Set brightness percentage for idle state (1-100%)
- **LED Count**: Number of LEDs on your strip (1-1000)
- **Night Mode**: Use dim amber glow instead of normal colors for minimal distraction

## Implementation Details

### Technology
- Uses WLED JSON API (`/json/state`) for direct device control
- Sends HTTP POST requests with color, brightness, and effect commands
- Supports both RGB color values and named colors
- Implements various WLED effects (solid, blink, breathe, strobe, rainbow, etc.)

### State Mapping
The system maps PiFire modes to visual states:
- **Stop** → Idle
- **Startup/Prime** → Booting  
- **Reignite** → Preheat
- **Smoke/Hold** → Cooking
- **Shutdown** → Cool-down

### Event Handling
Different notification events trigger appropriate lighting:
- Temperature achievements → Target reached effect
- Timer expiration → Rainbow celebration
- Low pellets → Yellow pulse warning
- Errors → Solid red alarm
- Probe alarms → Red/white strobe

### Smart Features
- **Mode Change Detection**: Only updates when grill mode actually changes
- **Cooldown Management**: Prevents notification spam with configurable delays  
- **Night Mode Support**: Reduces brightness and uses amber tones
- **Error Resilience**: Gracefully handles network/device connection issues
- **Fallback Support**: Can switch back to traditional preset mode

## Setup Instructions

1. **Configure WLED Device**
   - Set up your WLED device on your network
   - Note the IP address (static IP recommended)
   - Ensure the device is accessible from your PiFire system

2. **Enable in PiFire**
   - Go to Settings → Notifications → WLED
   - Enable WLED notifications
   - Enter your device address
   - Enable "Use PiFire Suggested LED Behaviors"

3. **Customize Settings**
   - Choose your preferred cooking color (blue/green)
   - Set idle brightness to your preference
   - Configure LED count to match your strip
   - Enable night mode if desired

4. **Test the Setup**
   - Use the "Send Test Notification" button
   - Verify LEDs respond as expected
   - Start a cook to see mode transitions

## Compatibility

- **WLED Version**: Compatible with WLED 0.10.0 and newer
- **Hardware**: Works with any ESP8266/ESP32 running WLED
- **LED Types**: Supports all WLED-compatible addressable LED strips
- **Network**: Requires WiFi connectivity between PiFire and WLED device

## Troubleshooting

### Common Issues
- **No LED Response**: Check device address and network connectivity
- **Delayed Updates**: Verify notification duration settings
- **Wrong Colors**: Ensure suggested presets is enabled and cooking color is set
- **Flickering**: Check network stability and LED power supply

### Debugging
- Check PiFire logs for WLED communication errors
- Verify WLED device is accessible via web browser
- Test with traditional presets to isolate issues
- Use WLED's built-in API testing tools

## Advanced Usage

### Custom Color Schemes
While the suggested presets provide optimal defaults, you can modify the color mappings by editing the WLED handler configuration or switching back to traditional preset mode for full customization.

### Integration with Home Automation
The WLED device can be integrated with home automation systems while still receiving PiFire notifications. The suggested presets will override automation commands during active notifications.

### Multiple LED Zones
For advanced setups with multiple LED segments, the suggested presets work with the entire strip. Use WLED's segment configuration for zone-specific effects.

## Files Modified

This feature adds/modifies the following files:
- `notify/wled_handler.py` - Enhanced with direct color/effect control
- `common/common.py` - Updated default settings structure  
- `blueprints/settings/routes.py` - Added configuration handling
- `blueprints/settings/templates/settings/index.html` - Added UI controls

## Future Enhancements

Potential improvements for future versions:
- Custom color selection for all states
- Advanced effect timing controls
- Multi-zone LED support
- Sound-reactive lighting integration
- Temperature-based color gradients
