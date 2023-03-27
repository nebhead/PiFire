'''
Utility to update the saved Fuzzy object, which can be computationally complex.  

This utility will overwrite the fuzzy.pickle file, we a new version.  

Ideally this should be run on a sufficiently power PC, so that the fuzzy object
can simply be called by the Raspberry Pi when running.  
'''

import controller.fuzzy as controller 
from common import read_settings

settings = read_settings()

config = {}

fuzzy_object = controller.Controller(config, 'F', settings['cycle_data'])

print(f'Creating new fuzzy.pickle...')

fuzzy_object.create_controller(plot=True)  # Change plot=False if you do not want to get the plots for the different member functions

print(f'Finished.')

