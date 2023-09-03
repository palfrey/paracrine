from ...helpers.config import config, get_config_file, host, in_docker
from ...helpers.fs import set_file_contents_from_template
from ...helpers.network import external_ip, wireguard_ip
from ...helpers.systemd import systemd_set
from . import bootstrap
from .common import private_key_file, public_key_path


def dependencies():
    return [bootstrap]


def setup(name="wg0", ip="192.168.2.1", netmask=24, peers=[]):
    peers = {}
    for h in config()["servers"]:
        if h["name"] == host()["name"]:
            continue
        public_key = get_config_file(public_key_path(h["name"]))
        peers[h["name"]] = {
            "public_key": public_key,
            "endpoint": "%s:51820" % external_ip(h),
            "peer_addr": h["wireguard_ip"],
        }

    conf_change = set_file_contents_from_template(
        f"/etc/wireguard/{name}.conf",
        "wg.conf.j2",
        PRIVATE_KEY=open(private_key_file).read().strip(),
        PEERS=peers,
        IP=ip,
        NETMASK=netmask,
    )

    if not in_docker():
        systemd_set(f"wg-quick@{name}", enabled=True, restart=conf_change)


def run():
    setup(ip=wireguard_ip())
