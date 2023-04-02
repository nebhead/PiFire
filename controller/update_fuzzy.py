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
    rate_of_change = ctrl.Antecedent(np.arange(0, 1, 0.01), 'rate_of_change')  # The range rate of change of temperature since last 
    cycleratio = ctrl.Consequent(np.arange(0, 1, 0.01), 'cycleratio')  # The ratio of Auger On / Auger Off time within the time cycle (default 20s cycle)

    # Membership Function for Delta of SetPoint - Current 
    delta['pSmall'] = fuzz.trimf(delta.universe, [1,2.5,5])  # trimf(variable, [a,b,c] )
    delta['nSmall'] = fuzz.trimf(delta.universe, [-5,-2.5,-1])  # trimf(variable, [a,b,c] )

    delta['zAligned'] = fuzz.trimf(delta.universe, [-1,0,1])  # trimf(variable, [a,b,c] )
    delta['nMed'] = fuzz.gbellmf(delta.universe, 4, 2, -10)  # gbellmf(variable, width, slope, center)
    delta['pMed'] = fuzz.gbellmf(delta.universe, 4, 2, 10)  # gbellmf(variable, width, slope, center)
    delta['nLarge'] = fuzz.zmf(delta.universe, -14, -12)  # zmf(variable, foot, ceiling)
    delta['pLarge'] = fuzz.smf(delta.universe, 12, 14)  # smf(variable, foot, ceiling)

    # Membership Function for Current Temperature 
    current['Low'] = fuzz.zmf(current.universe, 200, 210)  # zmf(variable, foot, ceiling)
    current['MediumLow'] = fuzz.gbellmf(current.universe, 40, 8, 225)  # gbellmf(variable, width, slope, center)
    current['MediumHigh'] = fuzz.gbellmf(current.universe, 60, 8, 320)  # gbellmf(variable, width, slope, center)
    current['High'] = fuzz.smf(current.universe, 350, 360)  # smf(variable, foot, ceiling)

    # Membership Function for Rate of Change 
    rate_of_change['Low'] = fuzz.zmf(rate_of_change.universe, 0, 0.01)  # zmf(variable, foot, ceiling)
    rate_of_change['Medium'] = fuzz.gbellmf(rate_of_change.universe, 0.1, 10, 0.15)
    rate_of_change['High'] = fuzz.smf(rate_of_change.universe, 0.2, 0.25)

    # Custom membership functions can be built interactively with a familiar,
    # Pythonic API
    cycleratio['Tiny'] = fuzz.zmf(cycleratio.universe, 0, 0.2)
    cycleratio['Short'] = fuzz.trimf(cycleratio.universe, [0.2, 0.25, 0.3])
    cycleratio['Medium'] = fuzz.trimf(cycleratio.universe, [0.3, 0.4, 0.5])
    cycleratio['Long'] = fuzz.gbellmf(cycleratio.universe, 0.2, 8, 0.7)
    cycleratio['Max'] =fuzz.smf(cycleratio.universe, 0.9, 1.0)

    # Setup Rules List
    rules = [] 

    # Rules for ramping up 
    rules.append(ctrl.Rule(delta['pLarge'], cycleratio['Max']))
    rules.append(ctrl.Rule(delta['pMed'] & 
                           current['Low'] & rate_of_change['Low'], cycleratio['Max']))
    rules.append(ctrl.Rule(delta['pMed'] & 
                           (current['MediumLow'] | current['MediumHigh'] | current['High']) &
                           (rate_of_change['Medium'] | rate_of_change['Low']), cycleratio['Max']))
    rules.append(ctrl.Rule(delta['pMed'] & 
                           (current['MediumLow'] | current['MediumHigh'] | current['High']) &
                           rate_of_change['High'], cycleratio['Medium']))
    rules.append(ctrl.Rule(delta['pMed'] & 
                           current['Low'] & 
                           (rate_of_change['Medium'] | rate_of_change['High']), cycleratio['Medium']))


    rules.append(ctrl.Rule(delta['pMed'] & current['Low'], cycleratio['Medium']))
    rules.append(ctrl.Rule(delta['pMed'] & (current['MediumLow'] | current['MediumHigh'] | current['High']), cycleratio['Max']))


    # Rules for centering 
    rules.append(ctrl.Rule(delta['pSmall'] & current['High'], cycleratio['Long']))
    rules.append(ctrl.Rule(delta['pSmall'] & current['MediumHigh'], cycleratio['Medium']))
    rules.append(ctrl.Rule(delta['pSmall'] & current['MediumLow'], cycleratio['Short']))
    rules.append(ctrl.Rule(delta['pSmall'] & current['Low'], cycleratio['Short']))

    rules.append(ctrl.Rule(delta['zAligned'] & (current['High'] | current['Low']), cycleratio['Tiny']))

    rules.append(ctrl.Rule(delta['nSmall'] & current['High'], cycleratio['Short']))
    rules.append(ctrl.Rule(delta['nSmall'] & current['MediumHigh'], cycleratio['Short']))
    rules.append(ctrl.Rule(delta['nSmall'] & current['MediumLow'], cycleratio['Tiny']))
    rules.append(ctrl.Rule(delta['nSmall'] & current['Low'], cycleratio['Tiny']))

    # Rules for ramping down 
    rules.append(ctrl.Rule(delta['nLarge'] & current['High'], cycleratio['Tiny']))
    rules.append(ctrl.Rule(delta['nLarge'] & current['MediumHigh'], cycleratio['Tiny']))
    rules.append(ctrl.Rule(delta['nLarge'] & current['MediumLow'], cycleratio['Tiny']))
    rules.append(ctrl.Rule(delta['nLarge'] & current['Low'], cycleratio['Tiny']))
    rules.append(ctrl.Rule(delta['nMed'] & current['High'], cycleratio['Short']))
    rules.append(ctrl.Rule(delta['nMed'] & current['MediumHigh'], cycleratio['Short']))
    rules.append(ctrl.Rule(delta['nMed'] & current['MediumLow'], cycleratio['Tiny']))
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
        rate_of_change.view()
        pyplot.show()

def test_fuzzy_system():
    try: 
        with open('fuzzy.pickle', 'rb') as pickle_file:
            fuzzy_controller = pickle.load(pickle_file)
        print('Fuzzy Pickle Successfully Opened.')
    except: 
        print('Fuzzy Pickle file could not be opened')
        return 
    
    print('Outputting test data to "fuzzy_test_data.csv"...')
    with open('fuzzy_test_data.csv', 'w') as fuzzy_csv_file:
        fuzzy_csv_file.write('set_point, current_temp, delta, cycle_ratio,\n')
        set_points = [165, 225, 250, 300, 350, 400, 450]
        rate_of_change = 0.5

        # rate_of_change = current - previous / cycle_time  (Change/Second)
        for set_point in set_points:
            for current in range(set_point-100, set_point+50):
                delta = set_point - current
                fuzzy_controller.input['delta'] = delta  # Delta = Set Point - Current Temperature
                fuzzy_controller.input['current'] = current  # Current temperature
                fuzzy_controller.input['rate_of_change'] = rate_of_change  # Current rate of change in temperature
                fuzzy_controller.compute()
                cycle_ratio = fuzzy_controller.output['cycleratio']
                fuzzy_csv_file.write(f'{set_point}, {current}, {delta}, {cycle_ratio},\n')
    print('Finished writing test data.')
    return 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fuzzy Logic Controller Updater')
    parser.add_argument('-p', '--plot', action="store_true", required=False, help="Show plots of member functions.")
    parser.add_argument('-t', '--test', action="store_true", required=False, help="Save CSV of test output.")

    args = parser.parse_args()
    
    plot = True if args.plot else False

    create_fuzzy_pickle(plot=plot)

    if args.test:
        test_fuzzy_system()

