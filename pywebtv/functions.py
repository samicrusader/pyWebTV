# -*- coding: UTF-8 -*-

import json
import magic
import os
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