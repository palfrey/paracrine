from typing import Dict

from paracrine import is_dry_run
from paracrine.deps import Modules

from ...helpers.config import build_config, core_config
from ...helpers.fs import MissingCommandException, run_command
from ...helpers.network import wireguard_ip, wireguard_ips
from . import check_master, node
from .common import get_master_ip

options: Dict[str, object] = {}


def dependencies() -> Modules:
    return [(node, options), check_master]


def run():
    master_ip = get_master_ip()
    local_ip = wireguard_ip()

    LOCAL = build_config(core_config())

    try:
        output = run_command(
            f"redis-cli -a {LOCAL['REDIS_PASSWORD']} -h {local_ip} info replication",
            dry_run_safe=True,
        )
    except MissingCommandException:
        if is_dry_run():
            return
        else:
            raise
    if "role:slave" in output:
        assert f"master_host:{master_ip}" in output, output
        assert "master_link_status:up" in output, output
    else:
        assert "role:master" in output, output
        for ip in wireguard_ips().values():
            if ip == master_ip:
                continue
            assert f"ip={ip},port=6379,state=online" in output, output

    output = run_command(
        f"redis-cli -a {LOCAL['REDIS_PASSWORD']} -h {local_ip} -p 26379 info sentinel",
        dry_run_safe=True,
    )
    count = len(wireguard_ips())
    expected = f"master0:name=mymaster,status=ok,address={master_ip}:6379,slaves={count-1},sentinels={count}"
    assert expected in output, (expected, output)
