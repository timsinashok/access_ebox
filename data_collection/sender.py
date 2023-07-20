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

import requests as rqs
import os
import hashlib
import packages.modules as modules

try:
    import station_id as station
except ModuleNotFoundError:
    raise ModuleNotFoundError('Pi ID could not be found')


##########

# constants declaration
URL = 'https://<ip>:<port>/upload/'
FOLDER = '/home/pi/data_logs/'
DEST_FOLDER = '/home/pi/sent_files/'
VERIFY = os.path.join(modules.HOME, 'cert.pem')

##########


def get_dest_path(f_name: str) -> str:
    '''
    Data files sent all contain date info
    Precondition: the file name is station<n>_YYYY-MM-DDT<...>Z.json
    Will use the date to construct the dest path and make sure it exists
    @param filename
    @return dest folder string in the form {DEST_FOLDER}/YYYY-MM
    '''

    # collect [YYYY, MM, ...]
    date = f_name.split('/')[-1].split('_')[1].split('-')

    # make dest path and see if it exists
    dest_path = os.path.join(DEST_FOLDER, f'{date[0]}-{date[1]}')

    # check if exists
    if not os.path.isdir(dest_path):
        os.mkdir(dest_path)

    return dest_path


def auth_sender(http_headers: dict) -> str:
    '''
    Send authentication message to server
    Authentication will fail if server does not respond or if response does
    not have 301
    @param http_headers headers to pass to server. They must contain the pi_id
    @return response from server, if it is not '301 <rand_string>' then
        authentication failed
    '''

    # send request to server
    try:
        response = rqs.get(URL,
                           headers=http_headers,
                           verify=VERIFY).text.strip()
    except rqs.exceptions.RequestException:
        modules.log(f'{URL} can\'t be reached, stopping sender')
        return '500'

    return response


def check_folders(*args: list) -> bool:
    '''
    Loops through a list of folders and files and makes sure they all exist
    @param *args list of folders and files
    @return True if all of them exist
    '''

    for dest_name in args:
        if not (os.path.isdir(dest_name) or os.path.isfile(dest_name)):
            return False

    return True


def calc_hash256(f_name: str, path: str = '') -> str:
    '''
    Calculates the hash256 checksum of a given file
    Precondition: File exists, the method will not check
    @param f_name name of file
    @param path Path to file if found in a different directory
    @return computed checksum
    '''

    # open file to get checksum
    with open(os.path.join(path, f_name), 'rb') as in_f:
        return hashlib.sha256(in_f.read()).hexdigest()


def send_to_server(url: str, headers: dict, files: dict) -> bool:
    '''
    Sends a file to the server
    @param url Dest url to send file to
    @param headers Headers info for http request
    @param files Dict of files to send in https request
    @return True if send was successful
    '''

    # send request
    try:
        rsp = rqs.post(url,
                       files=files,
                       headers=headers,
                       verify=VERIFY).text.strip()
    except rqs.exceptions.RequestException:
        modules.log(f'{url} can\'t be reached')
        return False

    # check if code is success
    if rsp == '200':
        return True

    return False


##########


def main():
    # check if necessary directories exist and are valid
    if not check_folders(FOLDER, DEST_FOLDER, VERIFY):
        modules.log('Failed to find all needed folders and files')
        return -1

    # construct headers for https request
    headers = {'pi_id': station.secret, 'pi_num': station.station_num}

    # auth pi to send data
    # success -> response = '301 <rand_str>'
    auth_response = auth_sender(headers)
    if '301' not in auth_response:  # exit if failed authentication
        return -1

    # collect files to send
    dir_list = sorted(os.listdir(FOLDER))
    num_files = len(dir_list)

    # collect url from the response 301 new_url
    url = os.path.join(URL, auth_response.strip().split(' ')[1])

    # loop through all files
    modules.log('Sending files')
    for send_file in dir_list:
        # calculate files left to send
        headers['num_files'] = str(num_files)

        # get hash256 of file
        headers['checksum'] = calc_hash256(send_file, FOLDER)

        # collect file
        files = {'sensor_data_file': open(os.path.join(FOLDER, send_file),
                                          'rb')}

        # send the file to the server
        if not send_to_server(url, headers, files):
            modules.log(f'{send_file} could not be sent')
            files['sensor_data_file'].close()
            num_files -= 1
            continue

        # close the sent file
        files['sensor_data_file'].close()

        # move succesfully sent file to other directory
        dest_path = get_dest_path(send_file)

        # move file to new location
        os.system(f'mv {os.path.join(FOLDER, send_file)} {dest_path}')

        modules.log(f'{send_file} sent')

        num_files -= 1

    return 0


if __name__ == "__main__":
    main()
