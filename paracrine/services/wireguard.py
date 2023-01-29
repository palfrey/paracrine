import json
import os
import sys
from distutils.version import LooseVersion

from ..config import (
    config,
    config_path,
    get_config,
    get_config_file,
    host,
    network_config,
    other_config_file,
)
from ..core import in_docker
from ..debian import apt_install
from ..fs import make_directory, run_command, set_file_contents_from_template
from ..network import external_ip
from ..systemd import systemd_set

wg_config = "/etc/wireguard"
private_key_file = "{wg_config}/privatekey".format(wg_config=wg_config)
public_key_file = "{wg_config}/publickey".format(wg_config=wg_config)


def public_key_path(name):
    return config_path() + "/wireguard-public-{name}.key".format(name=name)


def get_output(host, command):
    status, stdout, stderr = host.run_shell_command(command=command)
    stdout = "".join(stdout)
    assert status is True, (stdout, stderr)
    return stdout


def get_all_kernel_versions():
    raw = run_command(
        r"dpkg-query --showformat=$\{Package\},$\{Status\},$\{Version\}\\t --show linux-image-*",
    )
    versions = {}
    for line in raw.split("\t"):
        if line.strip() == "":
            continue
        try:
            (name, status, version) = line.split(",")
        except ValueError:
            raise Exception("'%s'" % line)
        if status == "install ok installed":
            versions[name] = version
    return versions


def bootstrap_run():
    apt_install(["kmod"])
    modules = sorted([line.split(" ")[0] for line in run_command("lsmod").splitlines()])
    if "wireguard" not in modules:
        print("modules", modules)
        apt_install(["linux-image-amd64"])
        versions = get_all_kernel_versions()
        ordered = sorted(
            [
                x.replace("linux-image-", "")
                for x in versions.keys()
                if x not in ["linux-image-amd64", "linux-image-cloud-amd64"]
            ],
            key=LooseVersion,
            reverse=True,
        )
        highest = ordered[0]
        current = run_command("uname -r").strip()
        if current != highest:
            print(ordered)
            print("'%s' != '%s'" % (current, highest))
            apt_install(["systemd-sysv"])
            if not in_docker():
                run_command("reboot")
                sys.exit(0)

        apt_install(["wireguard"])
        if not in_docker():
            apt_install(["linux-headers-amd64"])
            modules = sorted(
                [line.split(" ")[0] for line in run_command("lsmod").splitlines()]
            )
            if "wireguard" not in modules:
                print("modules", modules)
                run_command("modprobe wireguard")

    make_directory(wg_config)
    if not os.path.exists(private_key_file):
        run_command("wg genkey > %s" % private_key_file)
    if not os.path.exists(public_key_file):
        run_command("cat %s | wg pubkey > %s" % (private_key_file, public_key_file))

    return {"wg_publickey": open(public_key_file).read().strip()}


def bootstrap_parse_return(info):
    open(public_key_path(host()["name"]), "w").write(info["wg_publickey"])

    wg_ips = []

    for server in get_config()["servers"]:
        networks = network_config(server["name"])
        wireguard_networks = [
            network for network in networks if network["ifname"] == "wg0"
        ]
        if len(wireguard_networks) == 1:
            wg_ips.append(wireguard_networks[0]["addr_info"][0]["local"])
    json.dump(wg_ips, open(other_config_file("wireguard-ips"), "w"), indent=2)


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

    systemd_set(f"wg-quick@{name}", enabled=True, restart=conf_change)


def core_run():
    setup(ip=host()["wireguard_ip"])


__all__ = ["core_run", "bootstrap_run", "bootstrap_parse_return"]
