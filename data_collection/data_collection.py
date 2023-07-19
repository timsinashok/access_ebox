'''
Copyright (C) 2022 Francesco Paparella, Pedro Velasquez

This file is part of "ACCESS IOT Stations".

"ACCESS IOT Stations" is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

"ACCESS IOT Stations" is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
"ACCESS IOT Stations". If not, see <https://www.gnu.org/licenses/>.
'''

##########

import time
import datetime
import json
import os
import sensors as sens
from shutil import disk_usage
from gpiozero import CPUTemperature
import station_id as station
import packages.modules as modules
from werkzeug.utils import secure_filename
import threading
from ACCESS_station_lib import Beseecher

##########

# Constants

SAMPLING_INTERVAL = 600  # in seconds
MAX_SAMPLES = 1

##########

# Global variables

data_to_save = {}  # dictionary to place data collected
lock = threading.Lock()
threads = [None] * len(sens.sensors)

##########

# functions

def format_null(sensor: str, index: int = 0, sens_type: str = "") -> dict:
    """    
    Creates a dictionary with predefined keys and None values tailored to different sensor types.
    @param sensor: specific sensor identifier (e.g. "co2_sensor, "air_sensor", "particulate_matter").
                   "gps" can be passed as sensor to return a dictionary with gps keys and None values
    @param index: index of the sensor, if required   
    @param sens_type: model of the sensor (e.g., "scd30," "bme280," "nextpm"), if required
    @return: dictionary with predefined keys and None values                      
    """ 
    data = {
        'type': sens_type,
        'sensor': f"{sensor}{index}",
    }

    if sensor == "co2_sensor":
        data.update({
            'co2': None,
        })
    elif sensor == "air_sensor":
        data.update({
            'humidity': None,
            'temperature': None,
            'pressure': None,
        })
    elif sensor == "particulate_matter":
        data.update({
            'PM1count': None,
            'PM2,5count': None,
            'PM10count': None,
            'PM1mass': None,
            'PM2,5mass': None,
            'PM10mass': None,
            'sensor_T': None,
            'sensor_RH': None,
            'diagnostics': {
                'Degraded': None,
                'Notready': None,
                'Eccess_RH': None,
                'T_RH_off': None,
                'Fan_error': None,
                'Mem_error': None,
                'Las_error': None,
            },
        })
    elif sensor == 'gps':
        CPUdate, CPUtime = datetime.datetime.utcnow().isoformat().split('T')
        data = {
            'date': CPUdate,
            'time': CPUtime.split('.')[0],
            'latitude': None,
            'lat_dir': None,
            'longitude': None,
            'lon_dir': None,
            'altitude': None,
            'alt_unit': None,
            'num_sats': None,
            'PDOP': None,
            'HDOP': None,
            'VDOP': None,
        }

    return data


def write_diag(error_name: str, error: str) -> None:
    '''
    Writes an occured error into the diagnostics file located at /home/pi/
    @param error_name: error type (air sensor, cpu temperature, exception...)
    @param error: string info describing error
    appends errors to file until diagnostics sends them
    '''

    # open diagnostics file to add error info
    with open(
              os.path.join(modules.HOME,
                           f'station{station.station_num}_diagnostics.txt'),
              'a') as f:

        # timestamp data
        now = datetime.datetime.now()
        f.write(f'{now.strftime("%Y-%m-%d %H:%M:%S")}\n')

        # clean up error
        error = clean_str(error)

        f.write(f'{error_name}\n{error}\n\n')


def clean_str(string: str) -> str:
    '''
    Cleans a string by removing special characters and double spaces
    @param string original string to clean
    @return cleaned version of string
    '''

    # clean special characters
    string = string.replace('\n', ' ')
    string = string.replace('\r', '')
    string = string.replace('\t', ' ')

    # replace double spaces with single spaces
    while '  ' in string:
        string = string.replace('  ', ' ')

    return string


def write_temp_disk(temp: str, disk: str) -> None:
    '''
    Writes the cpu temperature and disk space in use into the diagnostic file
        the file is located in /home/pi/
    Takes arguments as string and writes them to a file
    @param temp Temperature of cpu
    @param disk Proportion of free space in RPi's storage
    '''

    # open diagnostics file to add info to
    with open(os.path.join(modules.HOME,
              f'station{station.station_num}_diagnostics.txt'), 'a') as f:

        # timestamp data
        now = datetime.datetime.now()
        f.write(f'{now.strftime("%Y-%m-%d %H:%M:%S")}\n')

        # write error info
        f.write(f'cpu\n{temp}\nmemory\n{disk}\n\n')


def measure(sensor: Beseecher, sensor_category: str, index: int) -> None:
    '''
    Multi-threaded collection of data
    Requests data from sensor and checks if sensor provides diagnostics
    Manages synchronization for updating global data
    Handles exceptions raised by data collection
    @param sensor Beesecher object to request data from
    @param sensor_category Measurements this sensor collects
        (i.e particulate_matter)
    @index that sensor's specific index
        data_to_save holds lists of every sensor_category
        to ensure all data collection is consistent, this method will
        always have the same sensor place its measurements in the same
        index
    '''

    # collect data from sensor
    try:  # in case any sensor fails or is disconnected, the whole system
        # won't crash
        data = sensor.measure()
    except Exception as e:  # must catch all exceptions as each sensor may
        # raise its own from package library
        data = format_null(sensor.SENSOR, sensor.index, sensor.TYPE)
        modules.log(f'Error collecting info for {sensor_category}{index}, ' +
                    f'{sensor.TYPE}')
        write_diag(f'{sensor_category}{index}', str(e))

    # check if there are any diagnostics to report
    if 'diagnostics' in data.keys():
        check_data_diagnostics(data['sensor'], data['diagnostics'])

    # synchronization for thread writing
    global lock, data_to_save
    lock.acquire()
    data_to_save[sensor_category][index] = data
    lock.release()

    return None


def check_data_diagnostics(sensor_id: str, diag_info: dict) -> None:
    '''
    Loops through all diagnostic information in a dictionary
    If any of the diagnostic flags are marked True, report the problem for
    diagnostics.py to send
    @param sensor_id unique identifier of that sensor (sensor category + index)
        For example, air_sensor1
    @param diag_info dictionary of diagnostics fields reported by a sensor
    '''
    for diag, value in diag_info.items():
        # if diagnostic flag is true, write down for diagnostics to send
        if value:
            write_diag(sensor_id, diag)


def data_init() -> None:
    '''
    Counts all the sensors connected to the RPi
    Initializes global variable data_to_save with appropriate list lengths for
    all threads to have a place to save their data
    '''
    global data_to_save

    # count sensors
    for sensor in sens.sensors:
        # get sensor type
        sensor = sensor.SENSOR

        # if data_to_save already has a list for this sensor type, add slot
        #   for new sensor
        if data_to_save.get(sensor, []):  # if theres already a list, it'll be
            # of length > 0
            data_to_save[sensor].append(None)
        else:
            # new list for first sensor of this type
            data_to_save[sensor] = [None]


def init_threads() -> None:
    '''
    Sends out all threads to interrogate each sensor
    '''

    global threads

    # start all threads
    for i, sensor in enumerate(sens.sensors):
        threads[i] = threading.Thread(target=measure, args=(sensor,
                                                            sensor.SENSOR,
                                                            sensor.index))

        threads[i].start()


def collect_gps_data() -> dict:
    '''
    Interrogates the gps sensor and does error management
    @return dictionary of gps information
    '''

    global lock
    gps_data = format_null(sensor="gps") # initialize gps data
    try:
        gps_data = sens.gps.fix()

        # aquire lock to save data
        lock.acquire()
        data_to_save['date_time_position'] = gps_data
        lock.release()

        # check for gps unable to get a fix
        if gps_data['latitude'] is None:  # GPS has no fix
            raise Exception('Could not fix GPS')

    except Exception as e:
        modules.log('Error collecting gps data')
        write_diag('gps', str(e))

    return gps_data


def save_time_date(gps_info: dict) -> None:
    '''
    Save date and time info for the diagnostics file to use
    Since this script is using the gps, other scripts are unable to use it for
    date and time.
    Saves the info in a tmep file for diagnostics to access later
    '''
    # collect date and time for naming files
    curr_time = gps_info['time']
    curr_date = gps_info['date']

    with open(os.path.join(modules.HOME, 'time.txt'), 'w') as out_f:
        out_f.write(f'{curr_time}\n{curr_date}')


def collect_diag() -> None:
    '''
    Collects general info about the current cpu and temp and saves it for
    diagnostics to later collect and send
    @return (date, time)
    '''

    # collect percentage of disk storage available
    t, u, _ = disk_usage('/')
    disk = u / t

    # measure cpu temp
    temp = CPUTemperature().temperature

    # check for critical levels of either
    if temp > 70:
        write_diag('temp', str(temp))
    if disk > 0.8:
        write_diag('disk_space', str(disk))

    # write info for general diagnostics
    write_temp_disk(str(temp), str(disk))


def join_threads() -> None:
    '''
    Wait for all threads to finish data collection and then collect them
    '''

    global threads

    for thread in threads:
        thread.join()


def save_data(date: str, time: str, data: dict) -> None:
    '''
    Save date collected by the sensors into a file and call sender to send it
    @param date Date data was collected, to be used in file name
    @param time Time data was collected, to be used in file name
    @param data Dict to save
    '''

    # construct secure file name
    f_name = secure_filename(f'station{station.station_num}_{date}T{time}Z' +
                             '.json')

    # dump data into file
    with open(os.path.join(modules.HOME, 'data_logs', f_name), 'w') as f:
        json.dump(data, f, indent=4)

    # send the file to server
    os.system(f'python3 {os.path.join(modules.HOME, "sender.py")}')


##########


def main():
    while True:
        # collect start time
        start_measurement_cycle = time.time()

        global data_to_save
        data_to_save = {}  # reset data to save in case it holds data from prev
        modules.log('Starting data collection')

        # count how many of each sensor
        # initialize all lists within data_to_save
        data_init()

        # set up data_to_save for data collection
        init_threads()

        # collect GPS data while other threads collect sensor data
        modules.log('collecting GPS data')
        gps_data = collect_gps_data()

        # save data and time for diagnostics purposes
        # Since only one python script can make use of the gps at any time, the
        # diagnostics file has no access to it
        save_time_date(gps_data)

        # collect diagnostics
        modules.log('Collecting diagnostics')
        collect_diag()

        join_threads()

        # save file and call sender to dispatch
        save_data(gps_data['date'], gps_data['time'], data_to_save)

        elapsed_time = time.time() - start_measurement_cycle
        time.sleep(max(0, SAMPLING_INTERVAL - elapsed_time))  # protect from
        # possible case where sensor stalls past 10 minutes

    return 0  # should never run


if __name__ == '__main__':
    main()
