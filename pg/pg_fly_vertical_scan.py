'''
    FlyScan for Sector 2-BM

'''
from __future__ import print_function

import sys
import json
import time
from epics import PV
import h5py
import shutil
import os
import imp
import traceback
import numpy as np

from pg_lib import *

global variableDict

variableDict = {
        'ExposureTime': 0.1,
        'ExposureTime_flat': 0.1,
        'SampleRotStart': 0.0,
        'SampleRotEnd': 180.0,
        'Projections': 1500,
        'SampleXIn': 0.0,
        'SampleXOut': 5,
        'NumDarkImages': 20,
        'NumWhiteImages': 20,
        'ShutterOpenDelay': 0.00,
        'IOC_Prefix': '2bmbPG3:', # options: 1. PointGrey: '2bmbPG3:', 2. Gbe '2bmbSP1:' 
        'FileWriteMode': 'Stream',
        'CCD_Readout': 0.05,
        'Station': '2-BM-B'
        'Recursive_Filter_Enabled': True,
        'Recursive_Filter_N_Images': 4,
        'StartSleep_min': 0,
        'SampleYStart': 0,
        'SampleYStepSize': 0.1,
        'SampleYNumSteps': 10,
        }

global_PVs = {}


def getVariableDict():
    global variableDict
    return variableDict


def get_calculated_num_projections(variableDict):
    delta = ((float(variableDict['SampleRotEnd']) - float(variableDict['SampleRotStart'])) / \
            (float(variableDict['Projections'])))
    slew_speed = (float(variableDict['SampleRotEnd']) - float(variableDict['SampleRotStart'])) / \
                 (float(variableDict['Projections']) * (float(variableDict['ExposureTime']) + \
                  float(variableDict['CCD_Readout'])))
    print('  *** *** start_pos',float(variableDict['SampleRotStart']))
    print('  *** *** end pos', float(variableDict['SampleRotEnd']))

    global_PVs['Fly_StartPos'].put(float(variableDict['SampleRotStart']), wait=True)
    global_PVs['Fly_EndPos'].put(float(variableDict['SampleRotEnd']), wait=True)
    global_PVs['Fly_SlewSpeed'].put(slew_speed, wait=True)
    global_PVs['Fly_ScanDelta'].put(delta, wait=True)
    time.sleep(3.0)
    calc_num_proj = global_PVs['Fly_Calc_Projections'].get()

    if calc_num_proj == None:
        print('  *** ***   *** *** Error getting fly calculated number of projections!')
        calc_num_proj = global_PVs['Fly_Calc_Projections'].get()
    if calc_num_proj != int(variableDict['Projections']):
        print('  *** ***   *** *** Updating number of projections from:', variableDict['Projections'], ' to: ', calc_num_proj)
        variableDict['Projections'] = int(calc_num_proj)
    print('  *** *** num projections = ',int(variableDict['Projections']), ' fly calc triggers = ', calc_num_proj)


def fly_scan(variableDict):
    theta = []
    # Estimate the time needed for the flyscan
    flyscan_time_estimate = (float(variableDict['Projections']) * (float(variableDict['ExposureTime']) + \
                      float(variableDict['CCD_Readout'])) ) + 30
    print(' ')
    print('  *** Fly Scan Time Estimate: %f minutes' % (flyscan_time_estimate/60.))
    global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime']) )

    num_images = int(variableDict['Projections'])
    global_PVs['Cam1_FrameType'].put(FrameTypeData, wait=True)
    
    global_PVs['Cam1_NumImages'].put(num_images, wait=True)
    global_PVs['Cam1_TriggerMode'].put('Overlapped', wait=True)
    # start acquiring
    global_PVs['Cam1_Acquire'].put(DetectorAcquire)
    wait_pv(global_PVs['Cam1_Acquire'], 1)

    print(' ')
    print('  *** Fly Scan: Start!')
    global_PVs['Fly_Run'].put(1, wait=True)
    # wait for acquire to finish 
    wait_pv(global_PVs['Fly_Run'], 0)

    # if the fly scan wait times out we should call done on the detector
    if False == wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle, flyscan_time_estimate):
        global_PVs['Cam1_Acquire'].put(DetectorIdle)
    
    print('  *** Fly Scan: Done!')
    # set trigger mode to internal for post dark and white
    global_PVs['Cam1_TriggerMode'].put('Internal')
    theta = global_PVs['Theta_Array'].get(count=int(variableDict['Projections']))
    return theta


def start_scan(variableDict, fname):
    print(' ')
    print('  *** start_scan')
    def cleanup(signal, frame):
        stop_scan(global_PVs, variableDict)
        sys.exit(0)
    signal.signal(signal.SIGINT, cleanup)
    if variableDict.has_key('StopTheScan'):
        stop_scan(global_PVs, variableDict)
        return
    get_calculated_num_projections(variableDict)
    global_PVs['Fly_ScanControl'].put('Custom')

    # Start scan sleep in min so min * 60 = sec
    time.sleep(float(variableDict['StartSleep_min']) * 60.0)
    print(' ')
    print('  *** Taxi before starting capture')
    global_PVs['Fly_Taxi'].put(1, wait=True)
    wait_pv(global_PVs['Fly_Taxi'], 0)
    print('  *** Taxi before starting capture: Done!')

    setup_detector(global_PVs, variableDict) #####
    setup_hdf_writer(global_PVs, variableDict, fname)

    move_sample_in(global_PVs, variableDict)

    open_shutters(global_PVs, variableDict)

    # run fly scan
    theta = fly_scan(variableDict)

    if int(variableDict['NumWhiteImages']) > 0:
        print('Capturing Post White Field')
        global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime_flat']) )
        move_sample_out(global_PVs, variableDict)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['NumWhiteImages']), FrameTypeWhite)
        global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime']) )
    if int(variableDict['NumDarkImages']) > 0:
        print('Capturing Post Dark Field')
        close_shutters(global_PVs, variableDict)
        time.sleep(2)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['NumDarkImages']), FrameTypeDark)
    close_shutters(global_PVs, variableDict)
    time.sleep(0.25)
    wait_pv(global_PVs["HDF1_Capture_RBV"], 0, 600)
    add_theta(global_PVs, variableDict, theta)
    global_PVs['Fly_ScanControl'].put('Standard')
    if False == wait_pv(global_PVs['HDF1_Capture'], 0, 10):
        global_PVs['HDF1_Capture'].put(0)
    reset_CCD(global_PVs, variableDict)


def main():
    tic =  time.time()
    update_variable_dict(variableDict)
    init_general_PVs(global_PVs, variableDict)
    

    SampleYEnd = variableDict['SampleYStart'] + variableDict['SampleYStepSize'] * variableDict['SampleYNumSteps']

    for sample_y in np.arange(variableDict['SampleYStart'], SampleYEnd, variableDict['SampleYStepSize']):
        print ('*** The sample vertical position is at %s mm' % (sample_y))
        global_PVs['Motor_SampleY'].put(sample_y, wait=True)

        try: 
            detector_sn = global_PVs['Cam1_SerialNumber'].get()
            if detector_sn == None:
                print('*** The Point Grey Camera with EPICS IOC prefix %s is down' % variableDict['IOC_Prefix'])
                print('  *** Failed!')
            else:
                print ('*** The Point Grey Camera with EPICS IOC prefix %s and serial number %s is on' \
                            % (variableDict['IOC_Prefix'], detector_sn))
                # get sample file name
                fname = global_PVs['HDF1_FileName'].get(as_string=True)
                print('  *** Moving rotary stage to start position')
                global_PVs["Motor_SampleRot"].put(0, wait=True, timeout=600.0)
                print('  *** Moving rotary stage to start position: Done!')
                start_scan(variableDict, fname)
                print(' ')
                print('  *** Total scan time: %s minutes' % str((time.time() - tic)/60.))
                print('  *** Data file: %s' % global_PVs['HDF1_FullFileName_RBV'].get(as_string=True))
                print('  *** Done!')

        except  KeyError:
            print('  *** Some PV assignment failed!')
            pass
    
        
        

if __name__ == '__main__':
    main()
