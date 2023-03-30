'''
Utility to update the saved Fuzzy object, which can be computationally complex.  

This utility will overwrite the fuzzy.pickle file, with a new version.  

Ideally this should be run on a sufficiently power PC, so that the fuzzy object
can simply be called by the Raspberry Pi when running.  
'''

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import pickle
import argparse

def create_fuzzy_pickle(plot=False):
    print(f'Creating new fuzzy.pickle...')
    '''
        Create fuzzy controller & save to pickle 
    '''
    # New Antecedent/Consequent objects hold universe variables and membership
    # functions.  Temperature ranges are in F for now, but could be scaled for C
    delta = ctrl.Antecedent(np.arange(-25, 25, 0.1), 'delta')  # The range of delta from the setpoint we care about
    current = ctrl.Antecedent(np.arange(0, 600, 1), 'current')  # The range of temperatures that we expect are possible/reasonable
    cycleratio = ctrl.Consequent(np.arange(0, 1, 0.01), 'cycleratio')  # The ratio of Auger On / Auger Off time within the time cycle (default 20s cycle)

    # Membership Function for Delta of SetPoint - Current 
    delta['pSmall'] = fuzz.trimf(delta.universe, [1,2,3])  # trimf(variable, [a,b,c] )
    delta['nSmall'] = fuzz.trimf(delta.universe, [-3,-2,-1])  # trimf(variable, [a,b,c] )

    delta['zAligned'] = fuzz.trimf(delta.universe, [-1,0,1])  # trimf(variable, [a,b,c] )
    delta['nMed'] = fuzz.gbellmf(delta.universe, 4, 2, -8)  # gbellmf(variable, width, slope, center)
    delta['pMed'] = fuzz.gbellmf(delta.universe, 4, 2, 8)  # gbellmf(variable, width, slope, center)
    delta['nLarge'] = fuzz.zmf(delta.universe, -12, -10)  # zmf(variable, foot, ceiling)
    delta['pLarge'] = fuzz.smf(delta.universe, 10, 12)  # smf(variable, foot, ceiling)

    # Membership Function for Current Temperature 
    current['Low'] = fuzz.zmf(current.universe, 200, 210)  # zmf(variable, foot, ceiling)
    current['High'] = fuzz.smf(current.universe, 200, 210)  # smf(variable, foot, ceiling)

    # Custom membership functions can be built interactively with a familiar,
    # Pythonic API
    cycleratio['Tiny'] = fuzz.zmf(cycleratio.universe, 0, 0.2)
    cycleratio['Short'] = fuzz.trimf(cycleratio.universe, [0.2, 0.25, 0.3])
    cycleratio['Medium'] = fuzz.trimf(cycleratio.universe, [0.3, 0.4, 0.5])
    #cycleratio['Long'] = fuzz.trimf(cycleratio.universe, [0.5, 0.7, 0.9])
    cycleratio['Long'] = fuzz.gbellmf(cycleratio.universe, 0.2, 8, 0.7)
    cycleratio['Max'] =fuzz.smf(cycleratio.universe, 0.9, 1.0)

    # Setup Rules List
    rules = [] 

    # Rules for ramping up 
    rules.append(ctrl.Rule(delta['pLarge'], cycleratio['Max']))
    rules.append(ctrl.Rule(delta['pMed'], cycleratio['Medium']))

    # Rules for centering 
    rules.append(ctrl.Rule(delta['pSmall'] & current['High'], cycleratio['Medium']))
    rules.append(ctrl.Rule(delta['pSmall'] & current['Low'], cycleratio['Short']))
    rules.append(ctrl.Rule(delta['nSmall'] & (current['High'] | current['Low']), cycleratio['Tiny']))
    rules.append(ctrl.Rule(delta['zAligned'] & (current['High'] | current['Low']), cycleratio['Tiny']))

    # Rules for ramping down 
    rules.append(ctrl.Rule(delta['nLarge'] & current['High'], cycleratio['Tiny']))
    rules.append(ctrl.Rule(delta['nLarge'] & current['Low'], cycleratio['Tiny']))
    rules.append(ctrl.Rule(delta['nMed'] & current['High'], cycleratio['Short']))
    rules.append(ctrl.Rule(delta['nMed'] & current['Low'], cycleratio['Tiny']))

    # Setup System
    system = ctrl.ControlSystem(rules)
    fuzzy_controller = ctrl.ControlSystemSimulation(system)

    with open('fuzzy.pickle', 'wb') as pickle_file:
        pickle.dump(fuzzy_controller, pickle_file)

    print(f'Finished.')

    if plot:
        print(f'Showing plots...')
        from matplotlib import pyplot  # Require to display plots
        delta.view()
        current.view()
        cycleratio.view()
        pyplot.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fuzzy Logic Controller Updater')
    parser.add_argument('-p', '--plot', action="store_true", required=False, help="Show Plots")
    args = parser.parse_args()
    
    plot = True if args.plot else False
    
    create_fuzzy_pickle(plot=plot)
    
