from typing import Dict

from .config import ServerDict, host, network_config, other_config, servers


def networks_by_interface(h):
    return dict([(intf["ifname"], intf) for intf in network_config(h["name"])])


def get_ipv4(network):
    addrs = network["addr_info"]
    for addr in addrs:
        if addr["family"] == "inet" and addr["local"] != "":
            return addr["local"]
    return None


def external_ip(h: ServerDict) -> str:
    return other_config(h["name"])["external_ip"]


def external_ips() -> dict[str, object]:
    return dict([(h["name"], external_ip(h)) for h in servers()])


def wireguard_ips() -> Dict[str, str]:
    return dict(
        [(h["name"], h["wireguard_ip"]) for h in servers() if "wireguard_ip" in h]
    )


def wireguard_ip():
    return host()["wireguard_ip"]


def ips_for_network(net):
    return [
        x for x in [get_ipv4(intf) for (name, intf) in net.items()] if x is not None
    ]


def ips(h):
    network = networks_by_interface(h)
    return ips_for_network(network)
