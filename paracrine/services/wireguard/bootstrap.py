import os
import sys
from distutils.version import LooseVersion
from pathlib import Path
from typing import Dict, List

from typing_extensions import TypedDict

from paracrine import dry_run_safe_read, is_dry_run

from ...helpers.config import host, in_docker
from ...helpers.debian import apt_install
from ...helpers.fs import (
    MissingCommandException,
    make_directory,
    run_command,
    set_file_contents,
)
from .common import private_key_file, public_key_file, public_key_path, wg_config


def get_all_kernel_versions():
    raw = run_command(
        r"dpkg-query --showformat=$\{Package\},$\{Status\},$\{Version\}\\t --show linux-image-*",
    )
    versions: Dict[str, str] = {}
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


class ReturnDict(TypedDict):
    wg_publickey: str
    host: str


def run() -> ReturnDict:
    apt_install(["kmod", "wireguard"])
    try:
        modules = sorted(
            [
                line.split(" ")[0]
                for line in run_command("lsmod", dry_run_safe=True).splitlines()
            ]
        )
    except MissingCommandException:
        if is_dry_run():
            modules = []
        else:
            raise
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
        if len(ordered) > 0:
            highest = ordered[0]
            current = run_command("uname -r").strip()
            if current != highest:
                print(ordered)
                print("'%s' != '%s'" % (current, highest))
                apt_install(["systemd-sysv"])
                if not in_docker():
                    run_command("reboot")
                    sys.exit(0)
        elif not is_dry_run():
            raise Exception("No kernel package versions found!")

        if not in_docker():
            apt_install(["linux-headers-amd64"])
            try:
                modules = sorted(
                    [
                        line.split(" ")[0]
                        for line in run_command("lsmod", dry_run_safe=True).splitlines()
                    ]
                )
            except MissingCommandException:
                if is_dry_run():
                    modules = []
                else:
                    raise
            if "wireguard" not in modules:
                print("modules", modules)
                run_command("modprobe wireguard")

    make_directory(wg_config)
    if not os.path.exists(private_key_file):
        run_command("wg genkey > %s" % private_key_file)
    if not os.path.exists(public_key_file):
        run_command("cat %s | wg pubkey > %s" % (private_key_file, public_key_file))

    return {
        "wg_publickey": dry_run_safe_read(Path(public_key_file), "dummy wg publickey"),
        "host": host()["name"],
    }


def parse_return(infos: List[ReturnDict]) -> None:
    assert len(infos) == 1, infos
    info = infos[0]
    set_file_contents(public_key_path(info["host"]), info["wg_publickey"])
