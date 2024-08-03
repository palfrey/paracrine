import json
import logging
import os
import re
from typing import Dict, List, Optional

from ...helpers.config import build_config, core_config, other_config, other_config_file
from ...helpers.debian import apt_is_installed
from ...helpers.fs import run_command
from ...helpers.network import wireguard_ip
from ...runners.core import wireguard_ip_for_machine_for

MASTER_FILE = "masters.json"


def get_existing_masters(local: bool) -> List[str]:
    if local:
        master_file = other_config_file(MASTER_FILE)
        if os.path.exists(master_file):
            return json.load(open(master_file))
        else:
            return []
    else:
        try:
            return other_config("masters.json")
        except KeyError:
            return []


def get_master_ip() -> Optional[str]:
    existing_masters = get_existing_masters(False)
    if len(existing_masters) > 0:
        if all([master == existing_masters[0] for master in existing_masters]):
            # everyone agrees, awesome
            return existing_masters[0]
        rated: Dict[str, int] = {}
        for master in existing_masters:
            if master not in rated:
                rated[master] = 1
            else:
                rated[master] += 1
        highest = sorted(rated.values(), reverse=True)[0]
        best_masters = [k for k in rated.keys() if rated[k] == highest]
        if len(best_masters) != 1:
            raise Exception(
                f"Can't choose, because {len(best_masters)} with {highest} entries in {best_masters}. See also {existing_masters}"
            )

        return best_masters[0]

    if not apt_is_installed("redis-tools"):
        return None

    local_ip = wireguard_ip()
    LOCAL = build_config(core_config())
    try:
        output = run_command(
            f"redis-cli -a {LOCAL['REDIS_PASSWORD']} -h {local_ip} info replication",
            dry_run_safe=True,
        )
    except AssertionError:
        # redis isn't up
        return None
    if "role:master" in output and ",port=6379,state=online" in output:
        master_ip = local_ip
    else:
        master_host_match = re.search("master_host:(.+)", output)
        if master_host_match is not None:
            master_ip = master_host_match.groups()[0].strip()
        else:
            master_ip = wireguard_ip_for_machine_for("redis-master")

    logging.info(f"Redis master for {local_ip} is {master_ip}")
    return master_ip
