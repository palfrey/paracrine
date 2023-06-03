from ...helpers.debian import apt_install
from ...helpers.fs import set_file_contents_from_template
from ...helpers.network import wireguard_ip
from ...helpers.systemd import systemd_set
from ...runners.core import wireguard_ip_for_machine_for
from .. import wireguard


def dependencies():
    return [wireguard]


def run():
    apt_install(["redis-sentinel", "redis-server"])
    master_ip = wireguard_ip_for_machine_for("redis-master")
    local_ip = wireguard_ip()
    server_changes = set_file_contents_from_template(
        "/etc/redis/redis.conf",
        "redis.conf.j2",
        WIREGUARD_IP=local_ip,
        IS_MASTER=local_ip == master_ip,
        MASTER_IP=master_ip,
    )
    sentinel_changes = set_file_contents_from_template(
        "/etc/redis/sentinel.conf",
        "redis-sentinel.conf.j2",
        WIREGUARD_IP=local_ip,
        MASTER_IP=master_ip,
        ignore_changes=True,
    )
    systemd_set("redis-server", enabled=True, running=True, restart=server_changes)
    systemd_set("redis-sentinel", enabled=True, running=True, restart=sentinel_changes)
