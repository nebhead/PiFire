#!/usr/bin/env python3

# *****************************************
# PiFire Module Settings Editor
# *****************************************
#
# Description: This script used during install to setup module settings
#
# *****************************************


# *****************************************
# Imported Libraries
# *****************************************

from common import ReadSettings, WriteSettings  # Common Library for writing settings
import argparse 

# Options
#  GrillPlatform - Update Grill Platform
#  ADC - Update ADC 
#  Display - Update Display
#  Range - Update Distance
#  Version - Update Server Version

#==============================================================================
#                                   Main Program
#==============================================================================

print('PiFire Module Settings Editor Tool')
print('Copyright 2021, MIT License, Ben Parmeter')

parser = argparse.ArgumentParser(description='Modify settings file.')
parser.add_argument('-g','--grillplat',type=str, help='Update the grill platform module setting.',required=False)
parser.add_argument('-a','--adc',type=str, help='Update the ADC platform module setting.',required=False)
parser.add_argument('-d','--display',type=str, help='Update the Display platform module setting.',required=False)
parser.add_argument('-r','--range',type=str, help='Update the Range platform module setting.',required=False)
parser.add_argument('-v','--version',type=str, help='Update the server version.',required=False)

args = parser.parse_args()

settings = ReadSettings()

if(args.grillplat):
    grillplat = args.grillplat
    print(f"\n * Modifying Grill Platform from {settings['modules']['grillplat']} to {grillplat}")
    settings['modules']['grillplat'] = grillplat 
    WriteSettings(settings)

if(args.adc):
    adc = args.adc
    print(f"\n * Modifying ADC from {settings['modules']['adc']} to {adc}")
    settings['modules']['adc'] = adc 
    WriteSettings(settings)

if(args.display):
    display = args.display
    print(f"\n * Modifying Display from {settings['modules']['display']} to {display}")
    settings['modules']['display'] = display 
    WriteSettings(settings)

if(args.range):
    range = args.range
    print(f"\n * Modifying Range Sensor from {settings['modules']['dist']} to {range}")
    settings['modules']['dist'] = range 
    WriteSettings(settings)

if(args.version):
    version = args.version
    print(f"\nModifying Server Version {settings['versions']['server']} to {version}")
    settings['versions']['server'] = version
    WriteSettings(settings)

print('\nDone.\n')