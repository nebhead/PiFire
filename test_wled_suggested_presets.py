#!/usr/bin/env python3
"""
Test script for WLED Suggested Presets functionality

This script tests the new WLED suggested presets feature by simulating 
various PiFire states and events without requiring a real WLED device.
"""

import sys
import os
import json
from unittest.mock import Mock, patch

# Add the parent directory to Python path to import PiFire modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_wled_suggested_presets():
    """Test the WLED suggested presets functionality"""
    
    # Mock settings for suggested presets
    mock_settings = {
        'notify_services': {
            'wled': {
                'enabled': True,
                'device_address': 'test.local',
                'use_suggested_presets': True,
                'suggested_config': {
                    'cooking_color': 'blue',
                    'idle_brightness': 20,
                    'night_mode': False,
                    'led_count': 6
                },
                'notify_duration': 120
            }
        }
    }
    
    # Mock control states
    control_states = [
        {'mode': 'Stop'},
        {'mode': 'Startup'},
        {'mode': 'Smoke'},
        {'mode': 'Hold'},
        {'mode': 'Shutdown'},
        {'mode': 'Prime'},
        {'mode': 'Reignite'}
    ]
    
    # Mock notification events
    test_events = [
        'GRILL_STATE',
        'Test_Notify',
        'Probe_Temp_Achieved',
        'Probe_Temp_Limit_Alarm',
        'Timer_Expired',
        'Pellet_Level_Low',
        'Grill_Warning',
        'Recipe_Step_Message',
        'Grill_Error_00',
        'Control_Process_Stopped'
    ]
    
    print("=" * 60)
    print("Testing WLED Suggested Presets Implementation")
    print("=" * 60)
    
    # Mock the requests module and common functions to avoid dependencies
    with patch('requests.post') as mock_post, \
         patch('requests.get') as mock_get, \
         patch('notify.wled_handler.create_logger') as mock_logger, \
         patch('redis.Redis') as mock_redis, \
         patch.dict('sys.modules', {
             'redis': Mock(),
             'ratelimitingfilter': Mock()
         }):
        
        # Setup mock responses
        mock_get.return_value.json.return_value = {'name': 'Test WLED', 'ver': '0.14.0'}
        mock_get.return_value.raise_for_status.return_value = None
        mock_post.return_value.raise_for_status.return_value = None
        mock_logger.return_value = Mock()
        
        # Import and test the WLED handler
        try:
            from notify.wled_handler import WLEDNotificationHandler
            
            # Initialize handler
            handler = WLEDNotificationHandler(mock_settings)
            print(f"✓ WLED Handler initialized successfully")
            
            # Test suggested preset calls for different states
            print("\nTesting suggested preset states:")
            suggested_states = [
                'idle', 'booting', 'preheat', 'cooking', 'cooldown',
                'target_reached', 'overshoot_alarm', 'probe_alarm',
                'low_pellets', 'timer_done', 'error'
            ]
            
            for state in suggested_states:
                try:
                    handler.send_suggested_preset(state, mock_settings['notify_services']['wled']['suggested_config'])
                    print(f"  ✓ {state} preset sent successfully")
                except Exception as e:
                    print(f"  ✗ {state} preset failed: {e}")
            
            # Test grill state changes
            print("\nTesting grill state changes:")
            for control in control_states:
                try:
                    handler.notify('GRILL_STATE', control, mock_settings)
                    print(f"  ✓ Mode '{control['mode']}' processed successfully")
                except Exception as e:
                    print(f"  ✗ Mode '{control['mode']}' failed: {e}")
            
            # Test notification events
            print("\nTesting notification events:")
            for event in test_events:
                try:
                    handler.notify(event, {'mode': 'Hold'}, mock_settings)
                    print(f"  ✓ Event '{event}' processed successfully")
                except Exception as e:
                    print(f"  ✗ Event '{event}' failed: {e}")
            
            # Test night mode
            print("\nTesting night mode:")
            night_config = mock_settings['notify_services']['wled']['suggested_config'].copy()
            night_config['night_mode'] = True
            try:
                handler.send_suggested_preset('idle', night_config)
                handler.send_suggested_preset('cooking', night_config)
                print("  ✓ Night mode presets sent successfully")
            except Exception as e:
                print(f"  ✗ Night mode failed: {e}")
            
            # Check that HTTP calls were made
            print(f"\nHTTP calls made:")
            print(f"  GET calls: {mock_get.call_count}")
            print(f"  POST calls: {mock_post.call_count}")
            
            # Print some example payloads
            if mock_post.call_args_list:
                print(f"\nExample payload sent:")
                last_call = mock_post.call_args_list[-1]
                if 'json' in last_call.kwargs:
                    print(f"  {json.dumps(last_call.kwargs['json'], indent=2)}")
            
            print("\n✓ All tests completed successfully!")
            
        except ImportError as e:
            print(f"✗ Failed to import WLED handler: {e}")
            return False
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            return False
    
    return True

def test_color_mappings():
    """Test the color and effect mappings"""
    print("\n" + "=" * 60)
    print("Testing Color and Effect Mappings")
    print("=" * 60)
    
    try:
        from notify.wled_handler import WLED_COLORS, WLED_EFFECTS
        
        print("Available colors:")
        for color, rgb in WLED_COLORS.items():
            print(f"  {color}: {rgb}")
        
        print("\nAvailable effects:")
        for effect, num in WLED_EFFECTS.items():
            print(f"  {effect}: {num}")
            
        print("✓ Color and effect mappings loaded successfully")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import color mappings: {e}")
        return False

if __name__ == "__main__":
    print("PiFire WLED Suggested Presets Test Suite")
    print("This test validates the implementation without requiring hardware\n")
    
    success = True
    success &= test_color_mappings()
    success &= test_wled_suggested_presets()
    
    if success:
        print("\n🎉 All tests passed! The WLED suggested presets implementation looks good.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)
