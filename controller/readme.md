## Plugabble Controllers

While the standard PID is good enough for most needs, it's been the desire of some to develop other control methods, or even other PIDs that may be tuned slightly differently.  

In an effort to allow for more choice and options for the core controller of PiFire, a new feature called pluggable controllers has been introduced.  This feature allows for the ability to add/utilize different controller types for the HOLD mode of PiFire, other than the included PID.  

### Implementation 

Controllers are now encapsulated in a class object, which allows you to pass configuration data into the object, for setup, and provides standard interface functions for the main control script / work cycle to call into for temperature control via the auger cycle time.

The below example is an 'empty' controller, with the basic structure required for minimum operation.  This could be adapted to create a new controller type.  Choose a unique name for the file, and place in the './controller' folder.  


```python
#!/usr/bin/env python3

'''
*****************************************
 PiFire Controller Class Object
*****************************************

 Description: Class object for the controller.  
 
*****************************************
'''

'''
Imported Libraries
'''
import time

'''
Class Definition
'''

class Controller:
	def __init__(self, config, units, cycle_data):
		self.config = config
		self.units = units
		self.cycle_data = cycle_data 

	def update(self, current):
		'''
		Input:
	        current :: Current temperature
	  Output:
          cycle_ratio(u) :: Raw Cycle Ratio
	  '''
		return 0.0

	def set_target(self, set_point):
		'''
		Input:
	    set_point :: Temperature Target
	  '''
		self.set_point = set_point
		self.last_update = time.time()
	
	def get_config(self):
		return self.config

	def supported_functions(self):
		function_list = [
			'update', 
	        'set_target', 
	        'get_config'
        ]
		return function_list
```

During the HOLD cycle, PiFire will call the 'update' function of the controller with the current temperature every N number of seconds where N is the cycle time.  The controller will do some calculations and provide the cycle ratio out.  This is the amount of time the Auger should be ON, in the cycle N.  For example, if the cycle time is 10s, and the cycle ratio is 0.5, then the Auger should be ON for 5s in the next cycle.    

```note
Important: PiFire has cycle settings that are separate from the controller, and will define the cycle time, and the min/max cycle ratios.  So if the controller provides a raw cycle ratio output of 0.1, but the minimum cycle ratio is 0.2, then the 0.2 cycle ratio will be used.
```

*Inputs:* 
- Set Point / Target (Controller.set_target(*target_temp*))
- Current Temperature (Controller.update(*current_temp*))

*Outputs:*
- Cycle Ratio (Auger On Time / Auger Off Time) (output from Controller.update())

### User Configuration, Registering the Controller

There is a controller JSON ('./controller/controllers.json') that contains the metadata for all of the available controllers and settings information.  This allows for the user to be able to select and configure the controller via the WebUI settings page (Work Cycle Settings).

For Example (excerpt from controllers.json):

```JSON
{
    "metadata" : {
        "example" : {
            "friendly_name" : "Example Controller Name",
            "module_name" : "example",
            "image" : "",
            "description" : "This is a description of the controller.  Here we talk about what it is, how it works, and what it's based on.  We can even call out the authors, the contributors or the modules used here.  Try to provide information that will be helpful to the user.",
            "author" : "Your Name",
            "link" : "https://github.com", 
            "contributors" : ["John Doe", "Jane Doe"],
            "attributions" : ["Python Foundation", "Flask, Copyright 2023, MIT License"],
            "recommendations" : {
                "cycle" : { 
                    "cycle_time" : 25,
                    "cycle_ratio_min" : 0.1,
                    "cycle_ratio_max" : 0.9
                }   
            },
            "config" : [
                {
                    "option_name" : "test_option_00",
                    "option_friendly_name" : "Integer Option", 
                    "option_description" : "This is an integer option with type 'int'.  It must include min, max and step (as integers).  If you don't want to have a min or a max, you can use null instead of a number.",
                    "option_type" : "int",
                    "option_default" : 10,
                    "option_min" : 0,
                    "option_max" : 20, 
                    "option_step" : 1,
                    "hidden" : false
                },
                {
                    "option_name" : "test_option_01",
                    "option_friendly_name" : "Boolean Option", 
                    "option_description" : "This is a boolean option, which means it can be True or False.",
                    "option_type" : "bool",
                    "option_default" : true,
                    "hidden" : false
                },
                {
                    "option_name" : "test_option_02",
                    "option_friendly_name" : "Floating Point Option", 
                    "option_description" : "This is an integer option with type 'float'.  It must include min, max and step (as floats).  If you don't want to have a min or a max, you can use null instead of a number.",
                    "option_type" : "float",
                    "option_default" : 1.1,
                    "option_min" : -2,
                    "option_max" : 2, 
                    "option_step" : 0.1,
                    "hidden" : false
                },
                {
                    "option_name" : "test_option_03",
                    "option_friendly_name" : "List/Select Option", 
                    "option_description" : "This is the list or select option type.  Option_list must be populated as a list of strings.  The option_list_labels will correspond to the option_list, and will be the options displayed int he drop down.  The option_default should match an option in the option_list.",
                    "option_type" : "list",
                    "option_default" : "a",
                    "option_list" : ["a", "b", "c", "d", "e"],
                    "option_list_labels" : ["A", "B", "C", "D", "E"],
                    "hidden" : false
                },
                {
                    "option_name" : "test_option_04",
                    "option_friendly_name" : "String Option", 
                    "option_description" : "This is a string/text freeform field.",
                    "option_type" : "string",
                    "option_default" : "teststring",
                    "hidden" : false
                },
                {
                    "option_name" : "test_option_05",
                    "option_friendly_name" : "Hidden Option", 
                    "option_description" : "If the hidden flag is set, then this option will not be displayed in the settings menu.  However, a value can be set as a default, and may be used by the controller.  This is helpful if you have an option that doesn't need to be displayed in settings, but needs to be set in the configuration.",
                    "option_type" : "string",
                    "option_default" : "You can't see me.",
                    "hidden" : true
                },                
                {
                    "option_name" : "test_option_06",
                    "option_friendly_name" : "Number List Option", 
                    "option_description" : "Same as the list option above, but the values are stored as a float by default.  You'll notice that the numbers in the option_list and in the option_default are not surrounded by quotes.  However the option_list_labels are strings, so that they can be displayed properly",
                    "option_type" : "numlist",
                    "option_default" : 2,
                    "option_list" : [1, 2, 3.3, 4, -123.1],
                    "option_list_labels" : ["1", "2", "3.3", "4", "-123.1"],
                    "hidden" : false
                }
            ]
        }
    }
}
```

### Settings

The settings JSON contains the both the selected controller name and the configuration data for all controllers(under the key ['controller']).  Settings for any available controller would be managed via the WebUI settings page.  

For Example (excerpt from settings.json):

```JSON
"controller": {
    "config": {
      "fuzzy": {},
      "pid": {
        "PB": 60.0,
        "Td": 45.0,
        "Ti": 180.0,
        "center": 0.5
      }
    },
    "selected": "pid"
  }
```

### Creating a New Controller Type

If you want to build a new controller, you will need to do two things:

1. Create the new class object (class name 'Controller') in a separate file in the './controller' folder.  Per the base example above, create that file with a unique name in the controller folder then...
2. Edit the './controller/controllers.json' metadata to provide information about the new controller, including the configuration information that would be needed for operation.  The 'key' of this controller metadata should match the filename (minus the .py extension).  

Lastly, share your work on GitHub!  If it's something you think others will want to try in the main repository, feel free to raise a pull request on the development branch!  
