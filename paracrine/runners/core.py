import json
import os
import socket
from pathlib import Path
from typing import Dict, List

from paracrine import is_dry_run

from ..helpers.config import (
    ServerDict,
    add_return_data,
    config,
    config_path,
    host,
    in_docker,
    network_config_file,
    other_config,
    other_config_file,
)
from ..helpers.debian import apt_install
from ..helpers.fs import (
    MissingCommandException,
    make_directory,
    run_command,
    set_file_contents,
)
from ..helpers.users import in_vagrant, users


def is_wireguard():
    return os.path.exists("/etc/wireguard")


def hash_fn(key: str, count: int) -> int:
    return sum(bytearray(key.encode("utf-8"))) % count


def _index_fn(name: str) -> ServerDict:
    hosts = config()["servers"]
    try:
        existing_selectors = other_config("selectors.json")
        return [host for host in hosts if host["name"] == existing_selectors[name]][0]
    except KeyError:
        index = hash_fn(name, len(hosts))
        add_return_data({"selector": {name: hosts[index]["name"]}})
        return hosts[index]


# Use this host for a given service
# Intended for "run on one machine" things
def use_this_host(name: str) -> bool:
    use_host = _index_fn(name)
    return host()["name"] == use_host["name"]


def wireguard_ip_for_machine_for(name: str) -> str:
    use_host = _index_fn(name)
    return use_host.get("wireguard_ip", "<unknown>")


def run():
    apt_install(["iproute2"])

    data = {
        "hostname": socket.gethostname(),
        "users": users(force_load=True),
        "groups": run_command("getent group", dry_run_safe=True),
        "server_name": host()["name"],
    }
    try:
        data["network_devices"] = run_command("ip -j address", dry_run_safe=True)
    except MissingCommandException:
        if is_dry_run():
            data["network_devices"] = "{}"
        else:
            raise
    ip_file = Path("/opt/ip_address")
    if ip_file.exists():
        data["external_ip"] = json.load(ip_file.open())
    else:
        if in_vagrant() or in_docker():
            networks = json.loads(data["network_devices"])
            ext_if = [
                net
                for net in networks
                if net["ifname"].startswith("eth") and len(net["addr_info"]) > 0
            ]
            if len(ext_if) > 0:
                data["external_ip"] = json.dumps(
                    {"ip": ext_if[-1]["addr_info"][0]["local"]}
                )
            else:
                data["external_ip"] = "<unknown>"
        else:
            apt_install(["curl", "ca-certificates"])
            data["external_ip"] = run_command(
                "curl https://api.ipify.org?format=json", dry_run_safe=True
            )
        set_file_contents(ip_file, json.dumps(data["external_ip"]))

    return data


def parse_return(infos: List[Dict]) -> None:
    info = infos[0]
    networks = json.loads(info["network_devices"])
    name = info["server_name"]
    make_directory(config_path())
    set_file_contents(network_config_file(name), json.dumps(networks, indent=2))

    other = {
        "users": info["users"],
        "groups": info["groups"],
        "hostname": info["hostname"],
    }
    try:
        other["external_ip"] = json.loads(info["external_ip"])["ip"]
    except json.JSONDecodeError:
        if is_dry_run():
            other["external_ip"] = "<unknown>"
        else:
            raise

    set_file_contents(other_config_file(name), json.dumps(other, indent=2))
