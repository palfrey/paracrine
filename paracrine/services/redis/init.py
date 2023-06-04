from ...helpers.config import build_config, core_config
from ...helpers.fs import run_command
from ...helpers.network import wireguard_ips
from ...runners.core import wireguard_ip_for_machine_for
from . import node

options = {}


def dependencies():
    return [(node, options)]


def run():
    LOCAL = build_config(core_config())
    output = run_command(f"redis-cli -a {LOCAL['REDIS_PASSWORD']} info replication")
    master_ip = wireguard_ip_for_machine_for("redis-master")

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
        f"redis-cli -a {LOCAL['REDIS_PASSWORD']} -p 26379 info sentinel"
    )
    count = len(wireguard_ips())
    assert (
        f"master0:name=mymaster,status=ok,address={master_ip}:6379,slaves={count-1},sentinels={count}"
        in output
    ), output
