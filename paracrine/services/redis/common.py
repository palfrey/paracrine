import re

from ...helpers.config import build_config, core_config
from ...helpers.fs import run_command
from ...helpers.network import wireguard_ip
from ...runners.core import wireguard_ip_for_machine_for


def get_master_ip():
    LOCAL = build_config(core_config())
    local_ip = wireguard_ip()
    output = run_command(f"redis-cli -a {LOCAL['REDIS_PASSWORD']} info replication")
    if "role:master" in output and ",port=6379,state=online" in output:
        master_ip = local_ip
    elif "master_host:" in output:
        master_ip = re.search("master_host:(.+)", output).groups()[0].strip()
    else:
        master_ip = wireguard_ip_for_machine_for("redis-master")

    return master_ip
