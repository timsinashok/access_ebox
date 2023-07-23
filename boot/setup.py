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
import sys
import requests as rqs
import time
import hashlib

sys.path.append('/home/pi/')
import packages.modules as modules
import station_id as station

##########

NAME = 'access'
URL = 'https://<ip>:<port>/'

##########


def router_setup() -> None:
    '''
    Creates and modifies all configuration files required to turn the pi into a
    wireless access point
    '''

    # reset wpa file
    with open(os.path.join(modules.PATH, 'wpa_supplicant.conf'), 'w') as f:
        f.write('ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n' +
                'update_config=1\ncountry=AE\n\n')

    # enable wireless access post
    os.system('sudo systemctl unmask hostapd')
    os.system('sudo systemctl enable hostapd')

    # define wireless configuration
    # check if already copied dhcpcd
    dhcpcd_orig = os.path.join(modules.PATH, 'dhcpcd.conf.orig')
    dhcpcd_path = os.path.join(modules.PATH, 'dhcpcd.conf')
    if not os.path.exists(dhcpcd_orig):
        os.system(f'sudo cp /etc/dhcpcd.conf {dhcpcd_orig}')

    # copy original dhcpcd
    os.system(f'cp {dhcpcd_orig} {dhcpcd_path}')
    with open(dhcpcd_path, 'a') as f:
        f.write('\ninterface wlan0\n\tstatic ip_address=192.168.4.1/24\n\t' +
                'nohook wpa_supplicant\n')
    os.system(f'sudo mv {dhcpcd_path} /etc/dhcpcd.conf')

    # configure DHCP and DNS
    # check if already copied dnsmasq.conf
    dnsmasq_orig = os.path.join(modules.PATH, 'dnsmasq.conf.orig')
    dnsmasq_path = os.path.join(modules.PATH, 'dnsmasq.conf')
    if not os.path.exists(dnsmasq_orig):
        os.system(f'sudo cp /etc/dnsmasq.conf {dnsmasq_orig}')

    # set up dhsmasq configuration
    with open(f'{dnsmasq_path}', 'w') as f:
        f.write('interface=wlan0\ndhcp-range=192.168.4.2,' +
                '192.168.4.20,255.255.255.0,24h\n\ndomain=wlan\naddress=' +
                '/gw.wlan/192.168.4.1')
    os.system(f'sudo mv {dnsmasq_path} /etc/dnsmasq.conf')

    # ensure wireless operation
    os.system('sudo rfkill unblock wlan')

    # configure hostapd software
    hostapd_path = os.path.join(modules.PATH, 'hostapd.conf')
    with open(hostapd_path, 'w') as f:
        f.write(f'country_code=AE\ninterface=wlan0\nssid={NAME}\nhw_mode=g\n' +
                'channel=7\nmacaddr_acl=0\n#auth_algs=1\n' +
                'ignore_broadcast_ssid=0\nwpa=0\n#wpa=2\n' +
                '#wpa_passphrase=password\n#wpa_key_mgmt=WPA-PSK\n' +
                '#wpa_pairwise=TKIP\n#rsn_pairwise=CCMP\n')

    modules.run(f'sudo mv {hostapd_path} /etc/hostapd/hostapd.conf')

    # enable dnsmasq in case disabled previously
    os.system('sudo systemctl enable dnsmasq')

    modules.log('Pi configured as wireless access point')

    # reboot system
    os.system('sudo systemctl reboot')


def start_flask() -> None:
    '''
    Starts flask app which hosts page for users to fill form with wifi
        information
    Precondition: pi is set up as wireless access point
    '''
    time.sleep(5)

    os.system('sudo systemctl restart flask_app')
    modules.log('Running Flask server')


def revert_router() -> None:
    '''
    Reverts pi from being a wireless access point back to normal functionality
    Precondition: router_setup() must have run first. This method depends on
        files created by router_setup
    '''
    # lets flask app finish running before rebooting pi
    time.sleep(2)

    # remove hostapd.conf
    os.system('sudo rm /etc/hostapd/hostapd.conf')

    # restore dnsmasq.conf
    os.system(f'sudo mv {os.path.join(modules.PATH, "dnsmasq.conf.orig")} ' +
              '/etc/dnsmasq.conf')

    # restore dhcpcd
    os.system(f'sudo mv {os.path.join(modules.PATH, "dhcpcd.conf.orig")} ' +
              '/etc/dhcpcd.conf')

    # disable hostapd and dnsmasq
    os.system('sudo systemctl disable dnsmasq')
    os.system('sudo systemctl disable hostapd')

    # move wpa supplicant
    os.system(f'sudo mv {os.path.join(modules.PATH, "networkconfig.txt")} ' +
              '/etc/wpa_supplicant/wpa_supplicant.conf')

    # reboot
    os.system('sudo systemctl reboot')


def test_connection() -> None:
    '''
    Attempts to communicate with central server to test if pi is connected to
        the internet
    Precondition: pi must NOT be set up as a wireless access network
    '''

    # wait for network to connect and return an ip address
    time.sleep(30)

    while True:
        try:
            if register_box() != '200':
                raise ConnectionError('Failed to register email')
            modules.log('Pi is connected to the internet, starting data ' +
                        'collection')
            # if test network does not time out
            modules.write_state(5)
            break
        except rqs.exceptions.RequestException:
            # connected to the router but timeout connecting to the internet
            modules.log('The Pi could not connect')

            # return to router state and restart
            modules.write_state(2)
            router_setup()
            exit(0)  # router_setup restarts pi, this line will never hit
        except ConnectionError:
            # server did not validate the data received, try send it again
            modules.log('Response error from server')
            time.sleep(20)

    main()  # if the function doesn't restart the pi and manages to escape the
    #         loop then the network should be verified


def register_box() -> str:
    '''
    Sends user email and sensor configuration information to central server
    Can raise an exception in rqs fails to contact server
    @return response from server
    '''

    # collect email from temp file create by flask app
    with open(os.path.join(modules.PATH, "email.txt"), 'r') as f:
        email = f.readline().strip()

    url = os.path.join(URL, 'register/')
    headers = {'pi_id': station.secret, 'email': email}
    cert = os.path.join(modules.HOME, 'cert.pem')

    # collect file detailing what sensors are on this box
    # this file is automatically created during sensor testing
    with open(os.path.join(modules.HOME, 'sensors_config.txt'), 'rb') as f:
        hash_256 = hashlib.sha256(f.read()).hexdigest()

    files = {'sensor_config':
             open(os.path.join(modules.HOME, 'sensors_config.txt'), 'rb')}
    headers['checksum'] = hash_256

    # send
    modules.log('Sending email to register')
    rsp = rqs.post(url, verify=cert, headers=headers, files=files)
    return rsp.text


def main():
    # check state of machine
    state_path = os.path.join(modules.PATH, modules.STATE)
    if not os.path.isfile(state_path):
        state = 1
    else:
        with open(state_path, 'r') as f:
            state = int(f.readline().strip())

    modules.log(f'Current state: {state}')

    if state == 1:  # packages downloaded, Pi now needs to set up as a router
        modules.write_state(2)
        router_setup()
    elif state == 2:  # start up flask app
        # state will not change until form is submitted
        start_flask()
    elif state == 3:  # pi must test connection to wifi
        modules.write_state(4)
        modules.log('Pi will stop serving as a wireless access point')
        revert_router()
    elif state == 4:
        modules.log('Testing wifi connection')
        test_connection()
    # state 3 will keep Pi as wireless access point but test wifi
    # state 4 will revert pi as router
    # state 5 will start the detection and measurement
    elif state == 5:

        modules.log('Starting data collection')
        time.sleep(20)
        os.system('sudo systemctl start diagnostics')
        os.system('python3 ' +
                  f'{os.path.join(modules.HOME, "data_collection.py")}')

    return 0


if __name__ == '__main__':
    main()
