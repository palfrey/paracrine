import json
import socket
from pathlib import Path

from mitogen.parent import Router

from .config import network_config_file, other_config_file, set_data
from .core import in_vagrant, main
from .fs import run_command


def do(data):
    set_data(data)

    data = {
        "hostname": socket.gethostname(),
        "network_devices": run_command("ip -j address"),
        "users": run_command("getent passwd | cut -d: -f1"),
        "groups": run_command("getent group"),
    }
    ip_file = Path("/opt/ip_address")
    if ip_file.exists():
        data["external_ip"] = json.load(ip_file.open())
    else:
        if in_vagrant():
            networks = json.loads(data["network_devices"])
            ext_if = [net for net in networks if net["ifname"] == "eth0"]
            if len(ext_if) > 0 and len(ext_if[0]["addr_info"]) > 0:
                data["external_ip"] = json.dumps(
                    {"ip": ext_if[0]["addr_info"][0]["local"]}
                )
            else:
                data["external_ip"] = "<unknown>"
        else:
            data["external_ip"] = run_command(
                "curl --silent https://api.ipify.org?format=json"
            )
        json.dump(data["external_ip"], ip_file.open("w"))

    return data


def core(router: Router) -> None:
    for info in main(router, do):
        networks = json.loads(info["network_devices"])
        json.dump(networks, open(network_config_file(info["hostname"]), "w"), indent=2)

        other = {
            "external_ip": json.loads(info["external_ip"])["ip"],
            "users": sorted(info["users"].strip().split("\n")),
            "groups": info["groups"],
        }
        json.dump(other, open(other_config_file(info["hostname"]), "w"), indent=2)
