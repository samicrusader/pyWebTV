# -*- coding: UTF-8 -*-

import json

def load_json(file:str):
    """
    Returns a dictionary from a .json file that's specified with file.
    This is just a cleaner way to read that stuff within the code.
    """
    return json.load(open(file, 'r'))