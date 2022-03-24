# -*- coding: UTF-8 -*-

from .decorators import WTVPResponse
import json
import magic
import os
import pathlib
import socket
import xrequests
from datetime import datetime
from geoip2 import database as geoip2
from tzlocal import get_localzone

def load_json(file: str):
    """
    Returns a dictionary from a .json file that's specified with file.
    This is just a cleaner way to read that stuff within the code.
    """
    return json.load(open(file, 'r'))


def return_file(filepath: str):
    """
    This returns a WTVPResponse class with a file embedded.
    """
    if os.path.exists(filepath) == False:
        raise FileNotFoundError('file not found')
    try:
        # FIXME: Remove Magic, it sucks.
        mimetype = magic.from_file(filepath, mime=True)
    except AttributeError:
        raise Exception('python-magic is not correctly installed.')
        return False
    except:
        mimetype = 'text/plain'
    with open(filepath, 'rb') as fh:
        data = fh.read()
    return WTVPResponse(data=data, content_type=mimetype)


def returnLocalTime(ip: str):
    """
    Returns a dictionary of headers that will set the client's time.
    This will work with a DB in MaxMind DB format. I use GeoIP2 for this example.
    You will want to put that in the directory of this module.

    If an error occurs with the DB, it will default to using the local machine's
    timezone.
    """
    path = pathlib.Path(__file__).parent.resolve()
    path = os.path.join(path, 'GeoIP2-City.mmdb')
    with geoip2.Reader(path) as reader:
        try:
            r = reader.city(ip)
        except:
            tz = get_localzone()
        else:
            tz = r.location.time_zone
    reader.close()
    dt = datetime.now(tz)
    return {'wtv-client-time-zone': dt.strftime('%Z %z'),
            'wtv-client-time-dst-rule': dt.strftime('%Z'),
            'wtv-client-date': dt.strftime("%a %b %d %H:%M:%S %Y")}


def returnIP():
    """
    Return the local machine's public IP address.

    We need the public IP for Internet-based clients to properly connect.
    This should get around NATs.

    You can still change the reported and listening IPs either way.
    This is only called if you don't.
    """
    try:
        req = xrequests.get('https://34.117.59.81/ip',
                            headers={'Host': 'ifconfig.me'},
                            verify=False)  # Normally you don't do this, however
        # we are just returning our IP.
        ip = ''.join(re.findall(r'[0-9\.]', req.text))
    except:
        try:
            returnLocalIP()
        except:
            raise ConnectionRefusedError(
                'Unable to auto-obtain a services IP.')
    else:
        return ip


def returnLocalIP():
    """
    Returns the local machine's LAN IP address.
    This is needed to actually listen to a TCP socket!
    """
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except:
        raise ConnectionRefusedError('Unable to auto-obtain a local IP.')
    else:
        return ip


def return_service(name: str,
                   port: int,
                   host: str = returnIP(),
                   DontEncryptRequests: bool = False,
                   UseHTTP: bool = False,
                   WideOpen: bool = False,
                   UseServiceCookies: bool = False,
                   NoMeter: bool = False,
                   connections: int = -1):
    """
    Returns a wtv-service header from variables. 
    It's a cleaner way to deploy one of these things.
    """
    flags = 0

    if DontEncryptRequests == True:
        flags += 1
    if UseHTTP == True:
        flags += 2
    if WideOpen == True:
        flags += 4
    if UseServiceCookies == True:
        flags += 10
    if NoMeter == True:
        flags += 40

    strflags = str()
    constr = str()
    if not flags == 0:
        strflags = f' flags=0x{format(11, "#08")}'  # '#010x'
    if not connections == -1:
        constr = f' connections={connections}'

    return f'name={name} host={host} port={port}{strflags}{constr}'
