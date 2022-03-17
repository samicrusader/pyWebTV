# -*- coding: UTF-8 -*-

from datetime import datetime
from geoip2 import database as geoip2
import json
import magic
import os
import pathlib
from .decorators import WTVPResponse

def load_json(file:str):
    """
    Returns a dictionary from a .json file that's specified with file.
    This is just a cleaner way to read that stuff within the code.
    """
    return json.load(open(file, 'r'))

def return_file(filepath:str):
    """
    This returns a WTVPResponse class with a file embedded.
    """
    if os.path.exists(filepath) == False:
        raise FileNotFoundError('file not found')
    try:
        mimetype = magic.from_file(filepath, mime=True) # FIXME: Remove Magic, it sucks.
    except AttributeError:
        raise Exception('python-magic is not correctly installed.')
        return False
    except:
        mimetype = 'text/plain'
    with open(filepath, 'rb') as fh:
        data = fh.read()
    return WTVPResponse(data=data, content_type=mimetype)

def return_service(name:str, 
                   port:int, 
                   host:str=returnIP(), 
                   DontEncryptRequests:bool=False,
                   UseHTTP:bool=False,
                   WideOpen:bool=False,
                   UseServiceCookies:bool=False,
                   NoMeter:bool=False,
                   connections:int=-1):
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
        strflags = f' flags=0x{format(11, "#08")}' # '#010x'    
    if not connections == -1:
        constr = f' connections={connections}'
    
    return f'name={name} host={host} port={port}{strflags}{constr}'

def returnLocalTime(ip:str):
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