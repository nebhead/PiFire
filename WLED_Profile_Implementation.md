# WLED Profile-Based Control Implementation

## Overview
This implementation adds a **Profile-Based Control** system to PiFire's WLED integration. Instead of sending direct color/effect commands, PiFire now pushes complete LED profiles directly to the WLED device and then activates them by profile number. This approach provides several advantages:

1. **User Customization**: Users can modify the profiles directly on their WLED device after they're pushed
2. **Better Performance**: Profile activation is faster than sending complex effect commands
3. **Consistency**: Profiles ensure the same lighting behavior across different WLED versions
4. **No Conflicts**: Uses profile numbers 200-211 to avoid conflicts with existing user profiles

## Implementation Details

### Core Components

#### 1. Profile Definitions (`notify/wled_profiles.py`)
- **WLED_PROFILE_DEFINITIONS**: Contains the complete profile configurations for each PiFire state
- **Profile Names**: Follow "PiFire - {name}" naming convention
- **Profile Numbers**: Use 200+ range to avoid conflicts with user profiles
- **LED Behaviors**: Match the specification table exactly

#### 2. Profile Manager (`notify/wled_profiles.py` - WLEDProfileManager class)
- **Device Communication**: Handles WLED HTTP API calls
- **Profile Creation**: Pushes profiles to WLED devices using `/json/state` endpoint
- **Profile Activation**: Triggers profiles by number
- **Error Handling**: Comprehensive error reporting and logging

#### 3. Updated WLED Handler (`notify/wled_handler.py`)
- **Multi-Mode Support**: Supports profile-based, suggested presets, and traditional modes
- **Profile Integration**: Uses profile manager for profile-based control
- **Backward Compatibility**: Maintains support for existing systems

#### 4. Web Interface (`blueprints/settings/templates/settings/index.html`)
- **Profile Configuration**: UI to configure profile numbers
- **Push Button**: "Push Profiles to WLED" button to send profiles to device
- **Test Function**: Test profile activation
- **Status Feedback**: Real-time status updates during profile operations

#### 5. API Endpoints (`blueprints/api/routes.py`)
- **POST /api/wled_push_profiles**: Push all profiles to WLED device
- **POST /api/wled_test_profile**: Test a specific profile activation

### Profile Specifications

Each profile follows this structure and matches the original requirements:

| PiFire State        | Profile # | LED Behavior                              | WLED Implementation                    |
|-------------------- |-----------|-------------------------------------------|----------------------------------------|
| **Idle**            | 200       | Dim white solid glow                      | Solid effect, white, 20% brightness   |
| **Booting**         | 201       | Slow white pulse (1s fade in/out)        | Breathe effect, white, slow speed      |
| **Preheat**         | 202       | Orange slow pulse (1s fade in/out)       | Breathe effect, orange, slow speed     |
| **Cooking**         | 203       | Solid blue or green (user-selectable)    | Solid effect, blue/green, full brightness |
| **Cooldown**        | 204       | Fade from orange → blue over 10s         | Fade effect, orange→blue transition    |
| **Target Reached**  | 205       | Green flash (3x, 0.5s each)              | Blink effect, green, fast speed        |
| **Overshoot Alarm** | 206       | Rapid red strobe (5x, 0.2s each)         | Strobe effect, red, very fast          |
| **Probe Alarm**     | 207       | Red/white alternating flash (5s)         | Blink effect, red/white alternating    |
| **Low Pellets**     | 208       | Yellow pulse (1s fade, every 10s)        | Breathe effect, yellow, slow speed     |
| **Timer Done**      | 209       | Rainbow chase (2s)                        | Rainbow chase effect, medium speed     |
| **Error/Fault**     | 210       | Solid red                                 | Solid effect, red, full brightness     |
| **Night Mode**      | 211       | Very dim amber glow                       | Solid effect, amber, 10% brightness    |

### Settings Structure

```json
{
  "notify_services": {
    "wled": {
      "enabled": true,
      "device_address": "192.168.1.100",
      "use_profiles": true,                    // NEW: Enable profile-based control
      "use_suggested_presets": false,          // Legacy mode (disabled when using profiles)
      "profile_numbers": {                     // NEW: Customizable profile numbers
        "idle": 200,
        "booting": 201,
        "preheat": 202,
        "cooking": 203,
        "cooldown": 204,
        "target_reached": 205,
        "overshoot_alarm": 206,
        "probe_alarm": 207,
        "low_pellets": 208,
        "timer_done": 209,
        "error_fault": 210,
        "night_mode": 211
      },
      "suggested_config": {
        "cooking_color": "blue",
        "idle_brightness": 20,
        "night_mode": false,
        "led_count": 6
      },
      "notify_duration": 120
    }
  }
}
```

## Usage Instructions

### For Users

1. **Enable Profile Mode**: Go to Settings → Notifications → WLED → Enable "Profile-Based Control"
2. **Configure Device**: Enter your WLED device IP address
3. **Customize Profile Numbers**: Adjust profile numbers if needed (default 200-211 range)
4. **Push Profiles**: Click "Push Profiles to WLED" to send all PiFire profiles to your device
5. **Test**: Use "Test Profile" to verify the cooking profile works
6. **Customize** (Optional): Use WLED web interface to modify colors/effects while keeping profile numbers

### For Developers

1. **Profile Definitions**: Modify `WLED_PROFILE_DEFINITIONS` in `notify/wled_profiles.py`
2. **State Mapping**: Update state mappings in `WLEDProfileManager.get_profile_number_for_state()`
3. **Event Mapping**: Update event mappings in `WLEDProfileManager.get_profile_number_for_event()`
4. **Default Settings**: Modify `default_notify_services()` in `common/common.py`

## API Usage

### Push Profiles
```bash
curl -X POST http://localhost:8000/api/wled_push_profiles \
  -H "Content-Type: application/json" \
  -d '{
    "device_address": "192.168.1.100",
    "profile_numbers": {
      "idle": 200,
      "cooking": 203
    }
  }'
```

### Test Profile
```bash
curl -X POST http://localhost:8000/api/wled_test_profile \
  -H "Content-Type: application/json" \
  -d '{
    "device_address": "192.168.1.100", 
    "profile_number": 203
  }'
```

## Migration from Suggested Presets

Existing users with "suggested presets" enabled will automatically have the system migrated:
- `use_profiles` will be set to `true` by default for new installations
- `use_suggested_presets` will be disabled when profiles are enabled
- Existing configurations remain functional until manually migrated
- No breaking changes to existing APIs or functionality

## Error Handling

- **Device Connectivity**: Graceful handling of offline WLED devices
- **Profile Conflicts**: Warnings when overwriting existing profiles
- **API Errors**: Detailed error messages with troubleshooting suggestions
- **Validation**: Input validation for profile numbers (1-250 range)
- **Timeouts**: 5-second timeouts for WLED API calls
- **Logging**: Comprehensive logging for debugging and monitoring

## Testing

Run the test script to verify the implementation:
```bash
cd /usr/local/bin/pifire
python test_wled_profiles.py
```

This will test:
- Profile manager creation
- Device connectivity  
- Profile pushing
- Profile activation
- Handler integration
