from ...helpers.debian import apt_install
from ...helpers.fs import set_file_contents_from_template
from ...helpers.network import wireguard_ip
from ...helpers.systemd import systemd_set
from .. import wireguard


def dependencies():
    return [wireguard]


def run():
    apt_install(["redis"])
    changes = set_file_contents_from_template(
        "/etc/redis/redis.conf", "redis.conf.j2", WIREGUARD_IP=wireguard_ip()
    )
    systemd_set("redis-server", enabled=True, running=True, restart=changes)
