import time
import epics
import numpy as np
import os
import Tkinter
import tkMessageBox as mbox

from pco_lib import *


global variableDict


variableDict = {
        'StartY': 0,
        'EndY': 96,
        'StepSize': 1,
        'StartSleep_s': 180,              # wait time (s) before starting data collection; usefull to stabilize sample environment 
        'SampleXIn': 0,              # to use X change the sampleInOutVertical = False
        'SampleXOut': 0.7,
        # 'SampleYIn': 0,                 # to use Y change the sampleInOutVertical = True
        # 'SampleYOut': -4,
        'SampleMoveEnabled': False,       # False to freeze sample motion during white field data collection
        'SampleInOutVertical': False,     # False: use X to take the white field; keep False if using the furnace
        'SampleRotStart': 0.0,
        'SampleRotEnd': 180.0,
        'Projections': 750,
        'NumWhiteImages': 20,
        'NumDarkImages': 20,
        # ####################### DO NOT MODIFY THE PARAMETERS BELOW ###################################
        'Station': '2-BM-A',
        'ExposureTime': 0.040,             # to use this as default value comment the variableDict['ExposureTime'] = global_PVs['Cam1_AcquireTime'].get() line
        'roiSizeX': 2560,                 # to use this as default value comment the variableDict['roiSizeX'] = global_PVs['Cam1_SizeX_RBV'].get() line
        'roiSizeY': 2160,                 # to use this as default value comment the variableDict['roiSizeY'] = global_PVs['Cam1_SizeY_RBV'].get() line
        'SlewSpeed': 1.0,                  # to use this as default value comment the calc_blur_pixel(global_PVs, variableDict) function below
        'AcclRot': 1.0,
        'IOC_Prefix': 'PCOIOC3:',         # options: 1. DIMAX: 'PCOIOC2:', 2. EDGE: 'PCOIOC3:'
        'FileWriteMode': 'Stream',
        'CCD_Readout': 0.03,
        'ShutterOpenDelay': 0.00,
        'UseFurnace': True,               # True: moves the furnace to FurnaceYOut position to take white field: 
                                          #       Note: this flag is active ONLY when both 1. and 2. are met:
                                          #           1. SampleMoveEnabled = True
                                          #           2. SampleInOutVertical = False  
        'FurnaceYIn': 0.0,  
        'FurnaceYOut': 43.0,
        }

global_PVs = {}

def getVariableDict():
    global variableDict
    return variableDict


def main():

    tic =  time.time()
    update_variable_dict(variableDict)
    init_general_PVs(global_PVs, variableDict)
    
    try: 
        model = global_PVs['Cam1_Model'].get()
        if model == None:
            print('*** The Point Grey Camera with EPICS IOC prefix %s is down' % variableDict['IOC_Prefix'])
            print('  *** Failed!')
        else:
            print ('*** The %s is on' % (model))            # get sample file name
            start = variableDict['StartY']
            end = variableDict['EndY']
            step_size = variableDict['StepSize']
    
            # calling global_PVs['Cam1_AcquireTime'] to replace the default 'ExposureTime' with the one set in the camera
            variableDict['ExposureTime'] = global_PVs['Cam1_AcquireTime'].get()
            # calling global_PVs['roiSizeX/Y'] to replace the default 'roiSizeX/Y' with the one set in the camera
            variableDict['roiSizeX'] = global_PVs['Cam1_SizeX_RBV'].get()
            variableDict['roiSizeY'] = global_PVs['Cam1_SizeY_RBV'].get()

            # calling calc_blur_pixel() to replace the default 'SlewSpeed' with its optinal value 
            blur_pixel, rot_speed, scan_time = calc_blur_pixel(global_PVs, variableDict)
            variableDict['SlewSpeed'] = rot_speed

            variableDict['SampleMoveEnabled'] = False
            for i in np.arange(start, end, step_size):
                print('*** Sample Move Enabled: %s ' % variableDict['SampleMoveEnabled'])                
                print ('     ')
                print ('*** New data set: %s of %s ' % (i+1, end))
                time.sleep(.5)
                edgeInit(global_PVs, variableDict)     
                edgeTest(global_PVs, variableDict)
                setPSO(global_PVs, variableDict)

                fname = global_PVs['HDF1_FileName'].get(as_string=True)
                print('  *** File name: %s' % fname)
                edgeSet(global_PVs, variableDict, fname)

                open_shutters(global_PVs, variableDict)
                edgeAcquisition(global_PVs, variableDict)
                edgeAcquireFlat(global_PVs, variableDict) 
                close_shutters(global_PVs, variableDict)
                edgeAcquireDark(global_PVs, variableDict) 
                if ((i+1)!=end):
                    print('          *** Wait (s): %s ' % str(variableDict['StartSleep_s']))
                    time.sleep(variableDict['StartSleep_s']) 

            if (variableDict['UseFurnace']):
                global_PVs['Motor_FurnaceY'].put(str(variableDict['FurnaceYOut']), wait=True, timeout=1000.0)
            global_PVs['Motor_SampleX'].put(str(variableDict['SampleXIn']), wait=True, timeout=1000.0)

            print(' ')
            print('  *** Total scan time: %s minutes' % str((time.time() - tic)/60.))
            print('  *** Data file: %s' % global_PVs['HDF1_FullFileName_RBV'].get(as_string=True))
            print('  *** Done!')

    except  KeyError:
        print('  *** Some PV assignment failed!')
        pass

   
    
    
if __name__ == '__main__':
    main()
