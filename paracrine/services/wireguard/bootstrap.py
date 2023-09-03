import json
import os
import sys
from distutils.version import LooseVersion

from ...helpers.config import (
    get_config,
    host,
    in_docker,
    network_config,
    other_config_file,
)
from ...helpers.debian import apt_install
from ...helpers.fs import make_directory, run_command, set_file_contents
from .common import private_key_file, public_key_file, public_key_path, wg_config


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


def run():
    apt_install(["kmod", "wireguard"])
    modules = sorted([line.split(" ")[0] for line in run_command("lsmod").splitlines()])
    if "wireguard" not in modules and not in_docker():
        print("modules", modules)
        apt_install(["linux-image-amd64"])
        versions = get_all_kernel_versions()
        version_keys = [
            x.replace("linux-image-", "")
            for x in versions.keys()
            if x
            not in [
                "linux-image-amd64",
                "linux-image-cloud-amd64",
                "linux-image-rt-amd64",
            ]
        ]
        print("kernel version keys", version_keys)
        ordered = sorted(
            version_keys,
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

    return {
        "wg_publickey": open(public_key_file).read().strip(),
        "host": host()["name"],
    }


def parse_return(infos):
    assert len(infos) == 1, infos
    info = infos[0]
    set_file_contents(public_key_path(info["host"]), info["wg_publickey"])

    wg_ips = []

    for server in get_config()["servers"]:
        networks = network_config(server["name"])
        wireguard_networks = [
            network for network in networks if network["ifname"] == "wg0"
        ]
        if len(wireguard_networks) == 1:
            wg_ips.append(wireguard_networks[0]["addr_info"][0]["local"])
    set_file_contents(other_config_file("wireguard-ips"), json.dumps(wg_ips, indent=2))
