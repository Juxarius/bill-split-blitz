import json
from functools import cache

config_file = "./blitz/config.json"

with open(config_file) as f:
    data = json.load(f)

@cache
def get_config(kw: str=None):
    if not kw: return data
    return data[kw]
