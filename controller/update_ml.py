'''
Utility to update the dataset from which the controller learns from.  

This utility will overwrite the ml_model.joblib file, with a new version.  

Ideally this should be run on a sufficiently powered PC, so that the ml object
can simply be called by the Raspberry Pi when running.  
'''

import pandas as pd 
import argparse
from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from joblib import dump, load

def create_new_model(infile='ml_dataset.csv', outfile='ml_model.joblib', test=False):
    print(f' - Loading dataset from {infile}')
    try: 
        ml_dataset = pd.read_csv(infile)
    except: 
        print(f' - ERROR: Failed to read file {infile}')
        return
    X = ml_dataset.drop(columns=['cycle_ratio'])
    y = ml_dataset['cycle_ratio']

    #model = KNeighborsRegressor(n_neighbors=4)
    model = LinearRegression()

    # pipe = Pipeline([
    #     ("scale", StandardScaler()),
    #     ("model", KNeighborsRegressor())
    #     ])

    print(f' - Training model against dataset.  Please wait.')
    # pipe.fit(X.values, y.values)
    # dump(pipe, outfile)
    model.fit(X.values, y.values)
    dump(model, outfile)
    #print(X.values)

    print(f' - Finished training model. Saving to {outfile}.')

    if test:
        start_current = 110
        set_point = 165
        rate_of_change = 1 
        range_of_values = 100

        for index in range(range_of_values):
            # prediction = pipe.predict([[110+index, 165, 1]])
            prediction = model.predict([[start_current+index, set_point, rate_of_change]])
            print(f'{start_current+index}, {set_point}, {rate_of_change}, {prediction[0]}')
        
def update_model(infile='ml_model.joblib', test=False):
    print(f' - Loading model from {infile}')
    try:
        model = load(infile)
    except:
        print(f' - ERROR: Failed to read file {infile}')
        return
    print(f' - Finished loading model.')
    #TODO: Add data to model

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Machine Learning Controller Updater')
    parser.add_argument('-c', '--create', action="store_true", required=False, help="Create a new model, with input CSV data.")
    parser.add_argument('-u', '--update', action="store_true", required=False, help="Update existing model, with input csv data.")
    parser.add_argument('-t', '--test', action="store_true", required=False, help="Test model.")

    args = parser.parse_args()
    
    if args.create:
        create_new_model(test=args.test)
    elif args.update:
        update_model(test=args.test)
    
