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
import datetime
from flask import Flask, request
from werkzeug.datastructures import FileStorage
from random import choice
from string import ascii_letters
from pymongo.errors import ConnectionFailure
# for safety and consistency, we should change to Flask-PyMongo
import modules.files as files
import modules.mongo as mongo
import secret

'''
From https://flask.palletsprojects.com/en/2.0.x/patterns/fileuploads/
with modifications.

One can upload a file with curl using the command line:

curl -F 'sensor_data_file=@<filename.txt>' -F
    'checksum=@<chechsumfilename.sha256>' <web page address>

where:
<filename> is the name of the file to be uploaded.
<chechsumfilename> is the name of the textfile produced by running sha256sum
                   in binary mode on <filename.txt>
                   (e.g.: sha256sum -b pippo.txt > pippo.sha256).
<web page address> is the url of the upload page, e.g. http://127.0.0.1:5000/
'''


##########

# constants definitions

# how long urls will be
URL_LEN = 20
# mongo connection info
MONGO_ADDR = '10.224.83.51'
MONGO_PORT = 27017
DATABASE = 'stations'

##########

# global variable definitions
urls = mongodb = None


def log(msg: str) -> None:
    '''
    Write any logging information into the appropriate log file
    Log files are separated by month
    @param msg message to write
    '''

    # get current time
    now = datetime.datetime.now()
    year = now.year
    month = now.month

    # change to db
    with open(f'logs/{year}_{month}.txt', 'a', encoding='utf-8') as f:
        f.write(now.strftime('[%Y-%m-%d %H:%M:%S] '))
        f.write(f'{msg}\n')


def gen_rand_string(length: int = URL_LEN) -> str:
    '''
    Generate a unique random string of specified length
    @param length defaults to URL_LEN constant
    '''
    rand_str = ''.join([choice(ascii_letters) for i in range(length)])

    # make sure rand_str is unique
    global urls
    while urls.get(rand_str, None) is not None:
        rand_str = ''.join([choice(ascii_letters) for i in range(length)])

    return rand_str


def init_data() -> None:
    '''
    Check if all necessary dependencies are working
    These are: mongo, storage folder, and diagnostics folder
    '''

    # check folders
    if not (os.path.isdir(files.STORAGE_FOLDER) and
            os.path.isdir(files.DIAGNOSTICS)):
        log('Error finding folders')
        raise NotADirectoryError(f'Missing {files.STORAGE_FOLDER} or ' +
                                 f'{files.DIAGNOSTICS}')

    # check mongo
    if not mongodb.test_connection():
        log('Error connecting to mongodb')
        raise ConnectionFailure


def authenticate_request(pi_id: str,
                         headers: list = [],
                         check_files: bool = False,
                         rqs_file: FileStorage = None) -> str:
    '''
    Checks that all the passed arguments not none and are present in the
    request
    @param pi_id hex string to pass to mongo for verification
    @param headers list of headers to check the values of
    @param check_files boolean to indicate files where passed for checking
    @param rqs_file if request passes files, also check those. These need to
        be checked for accepted data types as well
    @return appropriate error code if error is encountered, empty string if
        everything is okay
    '''

    # check pi_id
    if pi_id is None or (not mongodb.is_auth(pi_id)):
        log('Unauthorized access, rejected')
        return '401'

    # check headers and files for None
    for header in headers:
        if header is None:
            log('Required data not in request')
            return '412'

    # early return if no files to check
    if not check_files:
        return ''

    # Checking file

    # check empty file name
    if rqs_file is None or rqs_file.filename == '':
        log('Empty file')
        return '412'

    # check for supported file type
    elif not files.allowed_file(rqs_file.filename):
        log('Unsupported file type')
        return '415'

    # all tests passed, return empty string
    return ''


##########

# dictionary to keep mapping of random urls to pi ids
urls = {}

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 128  # max file size (in KB)

mongodb = mongo.Mongo(MONGO_ADDR,
                      MONGO_PORT,
                      DATABASE)

# check if all necessary folders / connections work
init_data()


log('Server running')

##########


@app.route('/', methods=['GET'])
def home() -> str:
    '''
    Home page for users to search for info regarding different stations
    Should have a search bar to explore the data from various stations
    '''
    return 'Temporarily out of order'


@app.route('/view/<station>')
def view_station(station: str) -> str:
    '''
    Display page for users to plot and explore data from different stations
    @param station string in the form "station<n>"
    '''
    return 'Temporarily out of order'


@app.route('/register/', methods=['POST'])
def register() -> str:
    '''
    Route to register a new station
    Stations call this route when they first connect to the internet when first
    deployed
    This route needs to add a user's email to the database as well as the
    sensors config file which will be in the request
    '''
    # collect headers
    auth = request.headers.get('pi_id', None)
    email = request.headers.get('email', None)
    checksum = request.headers.get('checksum', None)
    datafile = request.files.get('sensor_config', None)

    # check if all requirements are valid
    rsp = authenticate_request(auth, [email, checksum], check_files=True,
                               rqs_file=datafile)

    if rsp != '':  # empty string means no error
        return rsp  # return error code

    log('register is auth!')

    # do not register if checksum fails
    if not files.verify_checksum(datafile, checksum):
        return '500'

    log('checksum approved')
    log(files.stream_to_json(datafile))

    # upload to mongodb
    mongodb.register_station(auth, email, files.stream_to_json(datafile))

    return '200'  # succesfully saved file


@app.route('/upload/', methods=['GET'])
def authenticate() -> str:
    '''
    Main channel to receive data. This route constantly listens to all stations
    and when contacted, authenticats the station and creates a temporary
    dedicated url for that station to send data through
    @return "301 <rand_str>" if successfully verified, "<error_code>" otherwise
    The temporary url created will have the form "/upload/<rand_str>"
    '''
    # collect headers from request
    auth = request.headers.get('pi_id', None)

    rsp = authenticate_request(auth)
    if rsp != '':
        return rsp

    # generate random url for data transfer
    url = gen_rand_string()
    log(f'New request from {auth}, opening /upload/{url}')

    # store mapping of id to random url
    urls[url] = auth

    return f'301 {url}'


@app.route('/upload/<url>', methods=['POST'])
def get_data(url: str) -> str:
    '''
    Dedicated route for data transfer
    @param url random string created in the /upload/ route
    This route will verify that it is being contacted by a station and not a
    third party
    Then it will verify that url has been assigned to the station contacting
    and will only then attempt to recive the files
    Any file downloaded will have its checksum verified
    Once no files are left to download, this method must pop url from the
    global variable urls
    '''

    # collect headers and files for authentication
    auth = request.headers.get('pi_id', None)
    checksum = request.headers.get('checksum', None)
    station_num = request.headers.get('pi_num', None)
    # collect files
    datafile = request.files.get('sensor_data_file', None)
    # check how many remaining files
    # all arguments are in string form
    num_files = request.headers.get('num_files', '1')

    # authenticate all information received is okay
    rsp = authenticate_request(auth, [checksum, station_num], check_files=True,
                               rqs_file=datafile)

    if rsp != '':
        return rsp

    if num_files == '1':
        # remove url - pi pair from existing urls
        urls.pop(url)

    # modify station_num for easier use later on the file
    station_num = f'station{station_num}'

    # create storage path for the files to store
    if 'diagnostics' in datafile.filename:
        storage_path = files.make_storage_path(files.DIAGNOSTICS, station_num)

        # store and do not upload to mongo
        if files.verify_save_file(datafile,
                                  checksum,
                                  storage_path,
                                  store_chkm=True):
            return '200'
        else:
            return '500'

    storage_path = \
        files.make_storage_path(files.STORAGE_FOLDER,
                                station_num,
                                files.get_date(datafile.filename))

    # make sure checksum matches the file transfered
    if not files.verify_save_file(datafile,
                                  checksum,
                                  storage_path,
                                  store_chkm=True):
        return '500'

    # if checksum matched, upload to mongo
    mongodb.upload_to_mongodb(files.stream_to_json(datafile),
                              files.get_date(datafile.filename),
                              station_num)
    
    return '200'
