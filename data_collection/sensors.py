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

import ACCESS_station_lib as access
import busio

##########

'''
this file should define 2 things
sensors: list with ALL the sensors of all types
            Any beseecher sensor connected to the station must be appended to
            this list
gps: unlike the sensors, the gps will be a unique variable with the gps
beseecher.

When initializing sensors, ALWAYS use a try-except block in case the RPi
fails to start the sensors at boot. The error beseecher class will store any
error information that comes up and will allow data-collection to report on
the error.
'''

# try building gps, GPS sensor is critical point of failure for system
try:
    gps = access.GPSbeseecherGPIO()  # only 1 GPS
except Exception:
    gps = access.ErrorBeseecher('gps', 'gps', 'Error initializing GPS at boot')

# list to keep all sensors
sensors = []

# initialize pm sensors
ports = ['/dev/ttyAMA0', '/dev/ttyAMA1']

for port in ports:
    try:
        sensors.append(access.NEXTPMbeseecher(port=port))
    except Exception as e:
        sensors.append(access.ErrorBeseecher('particulate_matter',
                                             'nextpm',
                                             str(e)))

# the air sensors need an I2C object
i2c = busio.I2C()

# initialize air sensors
# bme
try:
    sensors.append(access.BME280beseecher(i2c=i2c))
except Exception as e:
    error_msg = str(e)
    sensors.append(access.ErrorBeseecher('air_sensor', 'bme280', error_msg))
# ms8607
try:
    sensors.append(access.MS8607beseecher(i2c=i2c))
except Exception as e:
    error_msg = str(e)
    sensors.append(access.ErrorBeseecher('air_sensor', 'ms8607', error_msg))
# scd30
try:
    sensors.append(access.SCD30beseecher(i2c=i2c))
except Exception as e:
    error_msg = str(e)
    sensors.append(access.ErrorBeseecher('co2_sensor', 'scd30', error_msg))

'''
set up indeces for all sensors

DO NOT MODIFY THIS PART, ONLY MODIFY SENSOR DECLARATIONS ABOVE

these index set up is necessary for multithreading
we don't know which thread will finish first, these indeces will make sure
    the order of sensors is kept (we want the data collected by sensor i to
    always be the ith index in the data file)
'''
indeces = {}
for sensor in sensors:
    indeces[sensor.SENSOR] = indeces.get(sensor.SENSOR, -1) + 1
    sensor.index = indeces[sensor.SENSOR]
