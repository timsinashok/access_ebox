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

import sys
import os

sys.path.append('/home/pi/')
import packages.modules as modules

##########


def p_install(pkg: str) -> None:
    '''
    install python package via pip
    Assumes package name is correct
    @param pkg Package name to install
    '''
    os.system(f'pip3 install {pkg}')


def install(sft: str) -> None:
    '''
    install package via apt-get
    Assumes package name is correct
    @param sft software to install
    '''
    os.system(f'sudo apt-get install -y {sft}')


##########


def main() -> int:
    # install all python dependencies
    pip_installs = ['Flask', 'pyserial', 'pigpio', 'pynmea', 'pynmea2',
                    'adafruit-circuitpython-bme280',
                    'adafruit-circuitpython-ms8607',
                    'adafruit-circuitpython-scd30',
                    'adafruit-extended-bus']

    for package in pip_installs:
        p_install(package)

    # install apt-get dependencies
    dependencies = ['hostapd', 'dnsmasq', 'pigpiod']
    for package in dependencies:
        install(package)

    modules.log('All dependencies installed')

    # set up dependencies
    os.system('sudo DEBIAN_FRONTEND=noninteractive apt install -y ' +
              'netfilter-persistent iptables-persistent')

    # set up services
    os.system('sudo systemctl enable pigpiod')
    os.system('sudo systemctl start pigpiod')

    # move services
    os.system(f'sudo cp {os.path.join(modules.PATH, "services/*")} ' +
              '/lib/systemd/system/')
    # enable services
    os.system('sudo systemctl daemon-reload')

    modules.log('All services loaded')

    # create state.txt file
    with open(os.path.join(modules.PATH, 'state.txt'), 'w') as f:
        f.write('1')

    modules.log('State file created')

    return 0


if __name__ == '__main__':
    main()
