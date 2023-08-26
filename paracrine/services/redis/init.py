from ...helpers.config import build_config, core_config
from ...helpers.fs import run_command
from ...helpers.network import wireguard_ip, wireguard_ips
from . import check_master, node
from .common import get_master_ip

options = {}


def dependencies():
    return [(node, options), check_master]


def run():
    master_ip = get_master_ip()
    local_ip = wireguard_ip()

    LOCAL = build_config(core_config())

    output = run_command(
        f"redis-cli -a {LOCAL['REDIS_PASSWORD']} -h {local_ip} info replication"
    )
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
        f"redis-cli -a {LOCAL['REDIS_PASSWORD']} -h {local_ip} -p 26379 info sentinel"
    )
    count = len(wireguard_ips())
    assert (
        f"master0:name=mymaster,status=ok,address={master_ip}:6379,slaves={count-1},sentinels={count}"
        in output
    ), output
