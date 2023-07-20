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

import os
import hashlib
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
import json

'''
This module contains methods centered around file manipulations including
checksum verifying, checking file extensions, and so on
'''

##########

# constants definitions

STORAGE_FOLDER = './received_files/'
DIAGNOSTICS = './diagnostics/'
# only accept txt and sha256 files
ALLOWED_EXTENSIONS = ('txt', 'json', 'csv')

##########


def allowed_file(filename: str) -> bool:
    '''
    check file extension for validity
    @param filename name of file to check
    @return True if allowed file
    '''
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def verify_checksum(file_data: FileStorage, chksm: str) -> True:
    '''
    check the checksum of a file matches one in args
    @param fname name of file to calculate checksum
    @param chksm checksum to compare to
    @return True if chksm matches the checksum of fname
    '''

    # get file stream data
    #p7
    file_stream = file_data.stream
    file_stream.seek(0)

    return hashlib.sha256(file_stream.read()).hexdigest() == chksm


def get_date(fname: str, reverse: bool = False) -> str:
    '''
    Collects the date from the file's name
    @param file_str expected to be in the form
        station<n>_YYYY-MM-DDTXXXXXXZ.json
    @param reverse boolean to get string in opposite order (MM-YYYY)
    @return string formatted YYYY-MM
    '''

    date = fname.split('_')[1].split('-')
    year = date[0]
    month = date[1]

    if reverse:
        return f'{month}_{year}'
    else:
        return f'{year}_{month}'


def get_station_num(fname: str) -> str:
    '''
    Gets the station number from a filename
    Assumes file name is in the format station<n>_YYYY-MM-DDTXXXXXXZ.json
    @param fname file name
    @return string in the form station<n>
    '''
    return fname.split('_')[0]


def verify_save_file(data_file: FileStorage,
                     checksum: str,
                     storage_name: str,
                     store_chkm: bool = False) -> bool:
    '''
    Saves a file to a specified directory
    Computes the checksum of saved file to that in parameters
    Deletes file if they don't match
    Precondition: storage_dir is a valid directory, this function will not
        check
    @param data_file File to save
    @param checksum to compare with checksum computed
    @param storage_name directory to store file
    @param store_chkm ask to save the checksum as its own file
    @return dictionary with the data from saved file
    @return True if file is saved and verified with passed checksum
        False otherwise
    Postcondition: data_file is saved IF AND ONLY IF its computed checksum
        matches the one in parameters
    '''

    # make sure checksum is verified
    if not verify_checksum(data_file, checksum):
        return False

    # make sure filename is secure to save
    storage_name = os.path.join(storage_name,
                                secure_filename(data_file.filename))

    # save file
    data_file.stream.seek(0)
    data_file.save(storage_name)

    # check to save checksum
    if store_chkm:
        save_checksum(checksum, storage_name)

    return True


def save_checksum(checksum: str, storage_name: str) -> None:
    '''
    Saves a checksum file in the appropriate format
    Precondition storage_name has only a single '.' to specify file type
    @param checksum value of checksum
    @param storage_name full path (relative or absolute) of file who's
        checksum belongs to. Method will use this to construct its own name
    '''

    # create name of checksum
    checksum_full_f_name = '.'.join(storage_name.split('.')[:-1]) + '.sha256'

    # get just name of data file
    data_file_name = storage_name.split('/')[-1]

    # write the checksum into memory
    with open(checksum_full_f_name, 'w', encoding='utf-8') as out_f:
        out_f.write(f'{checksum} {data_file_name}')


def make_storage_path(*args: str) -> str:
    '''
    Uses all arguments to create a folder path and verifies folder exists. If
    it does not exists, creates it
    Precondition: when *args is more than 1 folder level, AT LEAST all but the
        last level must already exist or the function will crash
        i.e if pasing (data, tree, month_1) then ./data/tree must already exist
    @param *args strings to connect into path
    '''

    # check if dir exists
    if not os.path.isdir(full_path := os.path.join(*args)):
        os.mkdir(full_path)

    return full_path


def stream_to_json(data: FileStorage) -> dict:
    '''
    Takes the bytes from a file storage and returns a json dictionary of the
    file
    Precondition: the file passed through follows the json format
    @param data FileStorage object to read and extract data from
    @return dictionary containing the data
    '''

    # read the bytes from the file
    my_file = data.stream
    my_file.seek(0)

    # read the json data from the bytestream
    return json.load(my_file)
