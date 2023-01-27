import json
import socket
from pathlib import Path

from mitogen.parent import Router

from .config import network_config_file, other_config_file, set_data
from .core import main
from .debian import apt_install
from .fs import run_command
from .users import in_vagrant, users


def do(data):
    set_data(data)
    apt_install(["iproute2"])

    data = {
        "hostname": socket.gethostname(),
        "network_devices": run_command("ip -j address"),
        "users": users(force_load=True),
        "groups": run_command("getent group"),
        "server_name": data["host"]["name"],
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
            apt_install(["curl", "ca-certificates"])
            data["external_ip"] = run_command("curl https://api.ipify.org?format=json")
        json.dump(data["external_ip"], ip_file.open("w"))

    return data


def core(router: Router) -> None:
    for info in main(router, do):
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
