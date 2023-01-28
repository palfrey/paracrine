import json
import os
import socket
from pathlib import Path
from typing import Dict

from .config import config, host, network_config_file, other_config_file
from .debian import apt_install
from .fs import run_command
from .users import users


def is_wireguard():
    return os.path.exists("/etc/wireguard")


def hash_fn(key: str, count: int) -> int:
    return sum(bytearray(key.encode("utf-8"))) % count


# Use this host for a given service
# Intended for "run on one machine" things
def use_this_host(name: str) -> bool:
    hosts = [h["name"] for h in config()["servers"]]
    index = hash_fn(name, len(hosts))
    return host()["name"] == hosts[index]


def bootstrap_run():
    apt_install(["iproute2"])

    data = {
        "hostname": socket.gethostname(),
        "network_devices": run_command("ip -j address"),
        "users": users(force_load=True),
        "groups": run_command("getent group"),
        "server_name": host()["name"],
    }
    ip_file = Path("/opt/ip_address")
    if ip_file.exists():
        data["external_ip"] = json.load(ip_file.open())
    else:
        if in_vagrant() or in_docker():
            networks = json.loads(data["network_devices"])
            ext_if = [net for net in networks if net["ifname"] == "eth0"]
            if len(ext_if) > 0 and len(ext_if[0]["addr_info"]) > 0:
                data["external_ip"] = json.dumps(
                    {"ip": ext_if[0]["addr_info"][0]["local"]}
                )
            else:
                data["external_ip"] = "<unknown>"
        else:
            apt_install(["curl", "ca-certificates"])
            data["external_ip"] = run_command("curl https://api.ipify.org?format=json")
        json.dump(data["external_ip"], ip_file.open("w"))

    return data


def bootstrap_parse_return(info: Dict) -> None:
    networks = json.loads(info["network_devices"])
    name = info["server_name"]
    json.dump(networks, open(network_config_file(name), "w"), indent=2)

    other = {
        "external_ip": json.loads(info["external_ip"])["ip"],
        "users": info["users"],
        "groups": info["groups"],
        "hostname": info["hostname"],
    }
    json.dump(other, open(other_config_file(name), "w"), indent=2)


def in_vagrant():
    return "vagrant" in users()


def in_docker():
    return os.path.exists("/.dockerenv")
