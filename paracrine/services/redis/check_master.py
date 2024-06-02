import json
from typing import Dict, List

from ...helpers.config import other_config_file
from ...helpers.fs import set_file_contents
from .. import wireguard
from . import wipe_old_master
from .common import MASTER_FILE, get_existing_masters, get_master_ip

options = {}


def dependencies():
    return [wireguard, wipe_old_master]


def run():
    master_ip = get_master_ip()
    return {"master_ip": master_ip}


def parse_return(infos: List[Dict]) -> None:
    existing_masters = get_existing_masters(True)
    existing_masters.append(infos[0]["master_ip"])
    master_path = other_config_file(MASTER_FILE)
    set_file_contents(master_path, json.dumps(existing_masters, indent=2))
