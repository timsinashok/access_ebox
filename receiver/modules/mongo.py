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

import pymongo
import datetime
import modules.files as files

'''
This module will involve any method that has to do with uploading / reading
from mongo
Any pushing of new data or contacting Mongo should be done through here
'''

##########


class Mongo:
    '''
    This class will manage all interactions with a specific mongodb database
    Methods include authenticating a station, uploading data, and uploading
    diagnostics
    '''

    def __init__(self,
                 connection_ip: str,
                 connection_port: str,
                 db: str) -> None:
        '''
        connect to Mongo
        @param connection_ip ip address of mongo server
        @param connection_port port number of mongo server
        @param db specific database in that mongo server
        '''

        self.client = pymongo.MongoClient(connection_ip, connection_port)
        self.db = self.client[db]

    def test_connection(self) -> bool:
        '''
        Attempts to contact mongodb server to see if a connection is working
        '''
        try:
            self.client.server_info()
        except pymongo.errors.ServerSelectionTimeoutError:
            return False

        return True

    def is_auth(self, pi_id: str) -> bool:
        '''
        Verify if a pi's id is registered in the server
        @param pi_id
        @return true if verified
        '''

        return self.db['stations_info'].find_one({'id': pi_id}) is not None

    def register_station(self, id: str, email: str, config: dict) -> None:
        '''
        Registers a new email to a station and creates folder for that station
        @param auth hex string that identifies that station
        @param email string email to register to that station
        @return address to store data files of this station
        '''

        # get correct station number from id
        station_num = int(self.db['stations_info'].find_one(
            {'id': id})['station_num'])
        # mongo transforms numbers into decimals, needing to be converted back

        # add email to station-info
        self.db['station-info'].update_one({'id': id},
                                           {'$set': {'email': email,
                                                     'sensors': config}})
        # add email to the station's specific collection
        self.db[f'station{station_num}'].update_one({'config': True},
                                                    {'$set':
                                                     {'email': email,
                                                      'sensors': config}})

        # create folders for this new station to save data into
        files.make_storage_path(files.STORAGE_FOLDER, f'station{station_num}')
        files.make_storage_path(files.DIAGNOSTICS, f'station{station_num}')

    def __collect_gps__(self, gps_data: dict, upload_dict: dict) -> None:
        '''
        Collect gps data from station
        @param gps_data dictionary with key-values collected by gps sensor
        @param upload_dict dictionary with all modifications meant to be
            pushed to mongodb.
        Precondition: gps_data has date_time_position data collected by a
            station in the format specified by the ACCESS_station_lib
        Postcondition: upload_dict has the data in a format compatible with
            mongodb Mongo will be pushing the data into respective arrays
        '''

        # collect datetime
        upload_dict['datetime'] = datetime.datetime.strptime(
            f'{gps_data["date"]}T{gps_data["time"]}Z',
            '%Y-%m-%dT%H:%M:%SZ'
            )

        gps_dict = {}

        gps_dict['sensor'] = "gps"
        gps_dict['index'] = 0
        # collect long/lat
        gps_dict['position'] = \
            [gps_data['longitude'], gps_data['latitude']]
        
        # mongo has longitude always before latitude when dealing with position
        # data

        # collect other fields except the following:
        collected_fields = \
            ('date', 'time', 'latitude', 'longitude') #, 'alt_unit')
        # these have already been collected / postprocessed
        # lastly, alt_unit will be a single value rather than an array so it
        #   won't be pushed into mongo with the rest of the data.
        for field, value in gps_data.items():
            # skip these fields
            if field in collected_fields:
                continue

            gps_dict[f'{field}'] = value

        upload_dict['gps'] = gps_dict

    def __collect_sensor__(self, sensor_data: list,
                           sensor_name: str,
                           upload_dict: dict) -> None:
        '''
        Collect sensor information from a station
        Stations group information by
            sensor category -> individual sensor -> measurement.
        This method must change that to group data by
            sensor category -> measurement -> individual sensor
        @param sensor_data info collected by a specific sensor category
        @param sensor_name name of sensor category (i.e particulate_matter or
            air_sensor)
        @param upload_dict dictionary to be uploaded to mongodb
        '''

        for i, info in enumerate(sensor_data):
            # iterate through the dictionary and create the mongo nesting
            # scheme
            if info is None:
                self.format_null(sensor_name, i, upload_dict)
                continue

            # upload_dict.update(
            #     {f'{sensor_name}.{key}.{i}': value
            #      for key, value in info.items()}
            # )

            # remove sensor and type attributes (these aren't lists)
            # remove unwanted attributes

            sensor_dict = {}

            sensor_dict[f'sensor'] = sensor_name
            sensor_dict[f'index'] = i

            unwanted = ('diagnostics', 'sensor')

            for field, value in info.items():
                # skip these fields
                if field in unwanted:
                    continue

                sensor_dict[f'{field}'] = value

            upload_dict[f'{sensor_name}+{i}'] = sensor_dict

            # for unwanted in ('diagnostics'):
            #     upload_dict.pop(f'{sensor_name}.{unwanted}.{i}', None)

    def format_null(self, sensor_name: str, i: int, upload_dict: dict):

        sensor_dict = {'sensor' : sensor_name, 'index' : i}

        if sensor_name == "particulate_matter":
            sensor_dict.update({'type' : None, 
                           'PM1count' : None, 
                           'PM2,5count' : None, 
                           'PM10count': None,
                           'PM1mass' : None,
                           'PM2,5mass' : None,
                           'PM10mass' : None,
                           'sensor_T' : None,
                           'sensor_RH' : None})
            # upload_dict.update([(f'{sensor_name}+{i}.type', None), 
            #                     (f'{sensor_name}+{i}.PM1count', None), 
            #                     (f'{sensor_name}+{i}.PM2,5count', None), 
            #                     (f'{sensor_name}+{i}.PM10count', None), 
            #                     (f'{sensor_name}+{i}.PM1mass', None), 
            #                     (f'{sensor_name}+{i}.PM2,5mass', None), 
            #                     (f'{sensor_name}+{i}.PM10mass', None), 
            #                     (f'{sensor_name}+{i}.sensor_T', None), 
            #                     (f'{sensor_name}+{i}.sensor_RH', None)])
            
        elif sensor_name == "air_sensor":
            sensor_dict.update({'type' : None, 
                           'humidity' : None, 
                           'temperature' : None, 
                           'pressure': None})
            # upload_dict.update([(f'{sensor_name}+{i}.type', None), 
            #                     (f'{sensor_name}+{i}.humidity', None), 
            #                     (f'{sensor_name}+{i}.temperature', None), 
            #                     (f'{sensor_name}+{i}.pressure', None)])
            
        elif sensor_name == "co2_sensor":
            sensor_dict.update({'co2' : None})
            
        upload_dict[f'{sensor_name}+{i}'] = sensor_dict
            # upload_dict.update([(f'{sensor_name}+{i}.co2', None)])
        


    def __make_gps_template__(self, gps_data: dict, template: dict) -> None:
        '''
        Create the mongodb template for a gps sensor
        Since gps sensors are processed differently to the other sensors, this
            method handles those differences
        @param gps_data key - values collected by gps
        @param template dictionary to fill with placeholder values
        '''

        # set datetime and position arrays
        template['gps'] = {'datetime': [], 'position': []}
        # grab all keys collected by gps and make them empty lists
        template['gps'].update({key: [] for key in gps_data})

        # pop excess fields -> these are all covered by datetime and position
        for key in ['date', 'time', 'latitude', 'longitude']:
            template['gps'].pop(key)

        # alt_unit (altitude unit) is a constant and not an array
        template['gps']['alt_unit'] = gps_data['alt_unit']

    def __make_sensor_template__(self,
                                 sensor_name: str,
                                 sensor_list: dict,
                                 template: dict) -> None:
        '''
        Create the mongodb template for a data sensor in a station
        Station files store data as such:
            {
                <sensor>: [<sens1>, <sens2>, ...]
            }
            where <sens1> is a dictionary in the form of
                {
                    <measurement>: <value>
                }
        Our desired output will be:
            {
                <sensor>: {
                    <measurement>: {
                        0: [],
                        1: []
                    }
                }
            }
            where 0 will hold a list of measurements from <sens1> and 1 will
            hold a list of measurements from <sens2>
        '''
        # set up sensor template
        num_sens = len(sensor_list)
        template[sensor_name] = {}

        # get all possible attributes collected by sensors
        # since individual sensors can be from different types, they may
        #   collect one or two different attributes
        #   (i.e sps30 collects PM4count / PM4mass but nextpm does not)
        measurements = set()
        for s in sensor_list:
            if s is None:
                continue
            measurements.update(s.keys())

        # template for each measurement
        for measurement in measurements:
            # discard repeated info (sensor is more important on station side,
            # not on db)
            if measurement == 'sensor' or measurement == 'diagnostics':
                continue
            # type should NOT be an array since it is a constant value
            # because it is constant, it can be filled out at template phase
            elif measurement == 'type':
                template[sensor_name][measurement] = {
                    str(i): '' if sensor_list[i] is None else sensor_list[i][measurement]
                    for i in range(num_sens)
                }
                continue

            # add empty lists for every other attribute
            template[sensor_name][measurement] = {str(i): []
                                                  for i in range(num_sens)}

    def __create_template__(self,
                            month: str,
                            station: str,
                            station_data: dict) -> None:
        '''
        Create an empty template for the sensors. A template should look like
        this:
            {
                month: <MM-YYYY>
                <sensor_category_1>: {
                    <measurement_j>: {
                        0: []
                        1: []
                        ...
                        <i>: []
                    }
                    ...
                    type: {
                        0: <sensor_type>
                        1: <sensor_type>
                        ...
                        <i>: <sensor_type>
                    }
                }
                ...
                gps: {
                    datetime: []
                    position: []
                    altitude: []
                    alt_unit: <unit>
                    <measurement_j>: []
                }

            }
        In this template, each index in the measurments is the index of an
        individual sensor
        Measurements are lists of measurements collected through the month
        A few constants aren't lists, such as sensor_type and alt_unit in gps
        '''
        # Create empty template with correct month
        template = {'month': month}

        # create the specific templates for each sensor category:
        #   regular sensor or gps
        for sensor, sensor_list in station_data.items():
            # special case for gps
            if sensor == 'date_time_position':
                # for other sensors, sensor_list is a list of all the
                # individual sensors but for gps it is the data collected
                self.__make_gps_template__(sensor_list, template)
                continue

            # make templates for sensors
            self.__make_sensor_template__(sensor, sensor_list, template)

        # upload template
        self.db[station].insert_one(template)

    def upload_to_mongodb(self,
                          raw_json: dict,
                          month: str,
                          station_num: str) -> None:
        '''
        Reads json file sent by station and reformats it to upload to mongodb
        @param raw_json dictionary sent by station
        @param month string in the form MM-YYYY
        @param station_num string station<num> (i.e station2)
        '''
        # check if there is already a month or not, if not, create template
        # if self.db[station_num].find_one({'month': month}) is None:
        #     self.__create_template__(month, station_num, raw_json)

        data_to_upload = {}

        for sensor in raw_json:
            # special case for gps, collect its data differently
            if sensor == 'date_time_position':
                self.__collect_gps__(raw_json['date_time_position'],
                                     data_to_upload)
                continue

            # collect info for other sensors
            self.__collect_sensor__(raw_json[sensor], sensor, data_to_upload)

        # upload to mongo
        self.db[station_num].insert_one(data_to_upload)
        # self.db[station_num].update_one({'month': month}, {'$push':
        #                                                    data_to_upload})

    def upload_config(self, station_num: str, config_data: dict) -> None:
        '''
        Uploads config dictionary to mongo database
        @param station_num string in the shape station<n>
        @param config_data dictionary containing all configuration information
            for that pi
        '''
        self.db[station_num].insert_one(config_data)
        self.db['stations_info'].insert_one(config_data)  # all config files
        # will be saved to station-info collection
