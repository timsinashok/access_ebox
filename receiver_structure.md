# ACCESS Lab IoT Structural Documentation

The ACCESS IoT project is a project that aims to create a wide reaching network of stations that independently collect data and make that data is accessible publicly and globally. Each station consists of a Raspberry Pi with its own configuration of sensors that collects data, generates files, and then uploads those files to a central computer, which then parses the files and uploads the data to a MongoDB database running locally on the same machine. 

[Comprehensive setup instructions and documentation](https://github.com/ACCESS-NYUAD/access_ebox#readme) can be found on the [project's GitHub](https://github.com/ACCESS-NYUAD/access_ebox). This document intends to explain the flow and structure of how the data is collected from the sensor, sent to the central machine, uploaded to the MongoDB database, and then displayed on [the dashboard](http://91.230.41.39:3600).

## The Stations

[See this folder structure for the stations](https://github.com/ACCESS-NYUAD/access_ebox#station-files)

### Data Collection
Each station's *data_collection.py* file runs continuously. When the data collection file first runs, it imports *sensors.py*, which creates a list of the appropriate Beseecher classes from *ACCESS_station_lib.py* for each sensor connected to the Pi. 

    For example, Station 1 initializes a GPSBeseecher object, two NextPMBeseecher objects, one BME280Beseecher object, and one MS8607Beseecher object. Any sensor that fails to initialize becomes an ErrorBeseecher object instead.

This list of objects is then passed into the main loop of *data_collection.py*. Every ten minutes, threads are created for each of the Beseechers, and the .measure() function is called on each thread to collect data from each sensor simultaneously. The data collection loop collects this data into a json file, named in the format: 
"station{station number}_{YYYY}-{MM}-{DD}T{SSSSSS}Z.json" and saves it to the */data_logs/* folder.

    For Station 1, the file generated on July 27th, 2023 might be named station1_2023-07-23T215554Z.json

[See this sample file](https://github.com/ACCESS-NYUAD/access_ebox#station-files)
    

The particulate_matter, air_sensor, and similar enviromental sensor objects are lists of the data each sensor of that type. The date_time_position object is a dictionary of the recorded GPS values.



### Sender
The data collection loop then calls the *sender.py* file, which connects to the flask web app on the central machine in order to send the files. The sender makes a get request to the flask URL (```<ip>:<port>/upload/```) with its station information, checksum, and the https certificate. Once verified by the flask app, the receiver returns a random string which serves as the address for the sender to upload the files (```<ip>:<port>/upload/<rand_str>```). The sender iterates through and uploads every file in the */data_logs/* folder, and then moves those files to the appropriate */sent_files/YYYY_MM/* folder.

The *data_collection.py* and *sender.py* files log their process and errors in the */logs/* folder. 

## The Receiver

[See this folder structure for the central machine.](https://github.com/ACCESS-NYUAD/access_ebox#folder-structure)

The files responsible for the receiver running are:
- receiver.py : The Flask app
- modules/files.py : A module that includes functions used by *receiver.py* that verify and save files.
- modules/mongo.py : A module with a Mongo class initialized by *receiver.py* that connects to the database and handles uploading the data to the database.

### Web Addresses

*receiver.py* is a runs continuously on the primary machien and is responsible for bridging the stations and the database. It currently uses port 3500.
It has the following addresses:
- ```<ip>:3500/``` : The default address. Returns a "Temporarily Out of Service" resposne.
-  ```<ip>:3500/register/``` : During the station setup process, the station will contact this addresss, and if successfully verified, a config file will created in the stations_info collection of the db, and a station-specific folder will be created in */received_files/* and */diagonistics/* folders.
- ```<ip>:3500/upload/``` : The authenticiation address of the receiver. Stations will contact this address and the server will verify that the certificate matches the receiver's, as well as check that the pi_ip matches the config file in the ```stations_info``` collection in the database. If the station information and file contents are successfully verified, the receiver will generate a random string that serves as an address for the station to upload to.
- ```<ip>:3500/upload/<rand_str>``` : The generated upload address. The receiver verifies the checksum again, and if valid, saves the data file and the checksum file to /received_files/station{num}/YYYY_MM/. Then, the data file is reformatted and uploaded to the station's colllection on MongoDB database by the *modules/mongo.py* file.


A list of response codes and errors can be found on the [documentation](https://github.com/ACCESS-NYUAD/access_ebox#response-codes).

### Steps to Set-Up

Here are the steps for hosting the receiver. While in the ACCESS folder of [this structure](https://github.com/ACCESS-NYUAD/access_ebox#folder-structure), run:
```console
$ export FLASK_APP=receiver.py
```
```
$ flask run --host=0.0.0.0 --port=3500 --cert=cert.pem --key=key.pem
```
--host=0.0.0.0 will run the app on all available interfaces, including the public IP of the machine.

The *cert.pem* and *key.pem* files are already on the machine and distributed to the stations. If the files need to be re-generated, this can be done with this command:

```
$ openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 3652
```
Then fill out the prompt as follows:
```console
    Generating a RSA private key
    ....++++
    .........................................................................................................................................++++
    writing new private key to 'key.pem'
    -----
    You are about to be asked to enter information that will be incorporated
    into your certificate request.
    What you are about to enter is what is called a Distinguished Name or a DN.
    There are quite a few fields but you can leave some blank
    For some fields there will be a default value,
    If you enter '.', the field will be left blank.
    -----
    Country Name (2 letter code) [AU]:AE
    State or Province Name (full name) [Some-State]:Abu Dhabi
    Locality Name (eg, city) []:Abu Dhabi
    Organization Name (eg, company) [Internet Widgits Pty Ltd]:Access
    Organizational Unit Name (eg, section) []:Access
    Common Name (e.g. server FQDN or YOUR name) []:public_ip
    Email Address []:
```
This will generate a new *cert.pem* and *key.pem* file. Note that this new *cert.pem* file will need to be distributed to all of the stations, and the receiver will need to be rehosted with the new certificate and key.

### Ending the receiver

If you need to kill the receiver process, you can run:
```console
ps aux | grep receiver
```
Then get the PID of the *receiver.py* process, and run:
```console
kill <PID>
```

## The MongoDB Database

The MongoDB database is called *stations* and hosted locally on the central machine. You can access the database through mongoshell on the machine by running

```console
$ mongosh "localhost":27017
```
```console
<test> use stations
```
Then from here you can find, update, insert, or delete files through commands like:
```console
<stations> db.station1.findOne({'datetime' : {$gt: ISODate("2023-07-01)}})
```
Which will find a single file in the station1 collection whose datetime is value is after July 1, 2023.


### Database Structure
The ```stations``` database houses a ```stations_info``` collection which contains config files of [this format for each station](https://github.com/ACCESS-NYUAD/access_ebox/blob/main/README.md#sample-documents)

It also contains a single config file for the dashboard of the following format:
```json
{
    "voila" : true,
    "station1": ISODate("2023-07-01T00:00:00.000Z"),
    "station2": ISODate("2023-06-01T29:00:10.000Z"),
    ...,
    "station<n>": IsoDate("<date str>")
}
```
The ```station<n>``` fields in this document indicate the last time the download files on the dashboard were updated.

The database also contains a collection for each station, named ```station<n>```. The station collections contain a document for each data file uploaded to the receiver (excluding the diagonistics files). The files are processed by *modules/mongo.py* in the receiver flask app, and then restructured into [this format](https://github.com/ACCESS-NYUAD/access_ebox/blob/main/README.md#sample-documents).

The datafiles are primarily queried by their "datetime" field, which is a unique ISODate object. Here is a sample structure of the ```station1``` collection in the database, displaying three documents.
```json
"db.station1":
#document1 {
    "_id": ObjectId("64b7f0b4c1e292e1031d7960"),
    "datetime": ISODate("2023-06-01T00:00:10.000Z"),
    "particulate_matter+0": {
      "sensor": "particulate_matter",
      "index": 0,
      "type": "nextpm",
      "PM1count": 352,
      "PM2,5count": 356,
      ...,
    },
    "particulate_matter+1": {
      "sensor": "particulate_matter",
      "index": 1,
      "type": "nextpm",
      ...,
    },
    "air_sensor+0": {
      "sensor": "air_sensor",
      "index": 0,
      "type": "bme280",
      "humidity": 66.47275681439535,
      ...,
    },
    "air_sensor+1": {
      ...,
    },
    "gps": {
      "sensor": "gps",
      "index": 0,
      ...,
    }
},
#document2 {
    "_id": ObjectId("64b7f0b4c1e292e1031d7962"),
    "datetime": ISODate("2023-06-01T00:20:11.000Z"),
    "particulate_matter+0": {
      "sensor": "particulate_matter",
      "index": 0,
      "type": "nextpm",
      ...,
    },
    "particulate_matter+1": {
      ...,
    },
    "air_sensor+0": {
      ...,
    },
    "air_sensor+1": {
      ...,
    },
    "gps": {
      ...,
    }
},
#document3 {
    "_id": ObjectId("64b7f0b4c1e292e1031d7962"),
    "datetime": ISODate("2023-06-01T00:20:11.000Z"),
    "particulate_matter+0": {
      "sensor": "particulate_matter",
      "index": 0,
      "type": "nextpm",
      ...,
    },
    "particulate_matter+1": {
      ...,
    },
    "air_sensor+0": {
      "sensor": "air_sensor",
      "index" : 0,
      "type": null,
      "humidity": null,
      "temperature": null,
      "pressure": null
    },
    "air_sensor+1": {
      ...,
    },
    "gps": {
      ...,
    }
},
...,
#document<n> {
    "_id" : ObjectId("..."),
    ...,
}
```

Note that air_sensor+0 on document 3 displays what happens when a sensor fails to record readings, the processing in *modules/mongo.py* replaces all of its values with null values. All sensors do the same, aside from the GPS, which instead looks like the following:
```json
gps: {
      "sensor": "gps",
      "index": 0,
      "position": [ null, null ],
      "lat_dir": null,
      "lon_dir": null,
      "altitude": null,
      "alt_unit": null,
      "PDOP": 99.99,
      "HDOP": 99.99,
      "VDOP": 99.99
    }
```

All of the collections follow this exact structure, with the exception of ```stations_info```.

Note, station0, or the prototype station, changed data formatting, sensors, and how it handles uploads multiple times across the first year of its operation. Thus, documents have missing and extra fields. For these reasons, it has been omitted from the dashboard and likely all future projects. Its data is still collected and stored on the database and in the received files folder.

## The Dashboard

The dashboard is the visualization of the data collected, uploaded, and stored in the IoT project. The dashboard is a Jupyter Notebook that is hosted publicly using voila. 

The dashboard, as can be seen, consists of an about tab, a visualization tab for each sensor in the database (excluding station 0), and a tab to download all of the data as .csv or .nc files.



### Visualization Tabs
The dashboard file, *iot_data_dashboard.ipynb*, consists of the following classes responsible for the visualization tabs:

- ```DataStore(db, station_num)``` : A DataStore object is generated for each station and it is responsible for collecting all of the data from the given station's collection in the database. On initializaiton, the class runs an aggregation pipeline to query for all the data in the collection, and then loads that data into a pandas dataframe. This dataframe is then accessed by the following classes for the purposes of visualization. 

- - The DataStore object also contains methods for generating .csv and .nc files containing the data from its dataframe. On initialization, the class checks the voila config file in the ```stations_info``` to see when the station's files were last updated, and then regenerated the files past that point to ensure they are all up to date. For example, if station1's files were last updated on 06-12-2023, and the DataStore object is initialized on 07-02-2023, it will generated a .csv and .nc file for June 2023 and July 2023. This feature is non-essential for the running of the dashboard, and the *update_files* method can be safely removed, though the files would have to be updated by some other means.


- ```Date Range Slider```: A slider widget (found in the ipywidgets module) is generated for each station containing a date for each day the station has been uploading values. This slider controls the range of data displayed on the plot

- ```Plotter(datetime_series, date_range_slider)```: A Plotter object is created for each station to control the plot which displays the data graphically. It creates the plot and configures its settings. The 

- ```Button List(DataStore, Plotter)```: A Button List object is initialized for each station. It connects the data from the DataStore object to the plot in the Plotter object. On initialization, it gets a list of measurements from the DataStore object, and then creates a toggle button for each measurement. When a button is pressed, the Button List updates all the measurements currently toggled, and then runs *Plotter.add_plot* for each of those measurements to graph the average of each measurement on the plot. 
- - For example, if the humidity button is toggled, the average of the two humidity values would be plotted on the graph as one series. If the button is deselected, that measurement is cleared from the list of toggled buttons and removed from the plot. If multiple buttons are selected, the series' are plotted over top each other in different colors. 

Upon being accessed, the dashboard will check the ```stations_info``` collection in the database, and for each config file in that collection (excluding station 0), it will generate a DataStore object, Date Range Slider widget, Plotter object, and Button List object, which will then get collected and displayed onto a tab.

### Download Tab

Upon being accessed, the dashboard will load all of the .nc and .csv files in the directory, then group them by Station number and file type, and then sort them by date from earliest to latest based on their filename. These files get displayed as FileLink objects on the download tab. The files and their contents are updated by the DataStore object used by the visualization tab, thus they should be fully up to date whenever the page is accessed. The *gen_files.py* file will fully regenerate all of the files without having to access the dashboard.

### Set-Up

While in the ACCESS/voila/files directory, the dashboard can be hosted by the following command:
```console
$ voila --no-browser --VoilaConfiguration.file_whitelist="['.*.(nc|.csv|.png)']" --Voila.ip=0.0.0.0 --port=3600 iot_data_dashboard.ipynb
```
Similar to the receiver, --Voila.ip=0.0.0.0 will host the webpage on all interfaces, and after running this command on the machine the dashboard can be accessed at ```http://<public_ip>:3600```.

### Closing the Dashboard

Similar to the receiver, get the PID of the voila process: 
```console
ps aux | grep voila
```
then run:
```console
kill <PID>
```

## TODO:

Below is a list of goals and possible optimizations for the project

- Host the receiver.oy in production mode. It is currently hosted in the development environment, which opens security vulnerabilities.

- Create a seperate process for generating and updating the .csv and .nc files. Having to generate the files on the load of the page makings accessing the page much slower. 
- Create a process to check for sensor drift and other possible errors. If a sensor begins giving faulty values, completely turns off, or begins drifting, there is currently no alert system. A system which checks the quality or status of the file uploads and then sends an email when a sensor appears to be faulty would be helpful.
- Add metadata to the data pipeline. At the moment, unit names, measurement measure data, or any kind of additional data is not stored anywhere on the stations, the receiver, the database, or the dashboard. It is possible to include it in the config files on the stations and on the ```stations_info``` config files.
- Host the MongoDB publicly instead of locally. This would require username and password authentication. It would make the database accessible to programs that do not run on the primary machine. The main concern that other databases, managed and created by other teams, are also being hosted on the same MongoDB instance. Approval would be needed from those teams.
- Host the dashboard with HTTPS

