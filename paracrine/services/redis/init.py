from ...helpers.fs import run_command, run_with_marker
from ...helpers.network import wireguard_ips
from ...runners.core import use_this_host
from . import node

options = {}


def dependencies():
    return [(node, options)]


def run():
    if not use_this_host("redis-init"):
        return
    ips = list(wireguard_ips().values())
    nodes = " ".join([f"{ip}:7000" for ip in ips])
    run_with_marker(
        "/var/lib/redis/init-done",
        f"redis-cli --cluster create {nodes} --cluster-replicas 1",
        input="yes",
    )

    output = run_command(f"redis-cli --cluster check {ips[0]}:7000")

    for ip in ips:
        assert f"{ip}:7000" in output
