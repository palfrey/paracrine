import json
from typing import Dict, List, cast

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


def parse_return(infos: List[Dict[str, object]]) -> None:
    local_master = infos[0]["master_ip"]
    if local_master is None:
        return
    existing_masters = set(get_existing_masters(True))
    existing_masters.add(cast(str, local_master))
    master_path = other_config_file(MASTER_FILE)
    set_file_contents(master_path, json.dumps(list(existing_masters), indent=2))
