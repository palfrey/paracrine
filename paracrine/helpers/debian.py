import os
import re
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional, Union

from debian.debian_support import version_compare

from paracrine import dry_run_safe_read

from .fs import (
    build_with_command,
    download,
    run_command,
    run_with_marker,
    set_file_contents,
)

host_arch: Optional[str] = None

_version_pattern = re.compile(r"Version: (\S+)")


def apt_update():
    run_with_marker(
        "/opt/apt-update",
        "apt-get update --allow-releaseinfo-change",
        deps=glob("/etc/apt/sources.list.d/*")
        + glob("/etc/apt/trusted.gpg.d/*")
        + ["/etc/apt/sources.list"],
    )


def add_trusted_key(url: str, name: str, hash: str, armored: bool = True):
    if armored:
        apt_install(["gpg"])
        download(
            url,
            f"/etc/apt/trusted.gpg.d/{name}.gpg.asc",
            hash,
        )
        build_with_command(
            f"/etc/apt/trusted.gpg.d/{name}.gpg",
            f"cat /etc/apt/trusted.gpg.d/{name}.gpg.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/{name}.gpg",
            [f"/etc/apt/trusted.gpg.d/{name}.gpg.asc"],
        )
    else:
        download(
            url,
            f"/etc/apt/trusted.gpg.d/{name}.gpg",
            hash,
        )
    return f"/etc/apt/trusted.gpg.d/{name}.gpg"


def apt_is_installed(package: str, wanted_version: Optional[str] = None) -> bool:
    paths = [
        f"/var/lib/dpkg/info/{package}.list",
        f"/var/lib/dpkg/info/{package}:{host_arch}.list",
    ]
    for path in paths:
        if not os.path.exists(path):
            continue
        if wanted_version is None:  # existance is enough
            return True
        status = run_command(f"dpkg-query --status {package}", dry_run_safe=True)
        version_pattern_match = _version_pattern.search(status)
        if version_pattern_match is None:
            raise Exception(
                f"Failure to match version pattern in '{status}' for {package}"
            )
        version = version_pattern_match.group(1)
        if version_compare(version, wanted_version) >= 0:
            return True

    return False


# List is just "any version", Dict is a "name => min version" requirement
def apt_install(
    packages: Union[List[str], Dict[str, Optional[str]]],
    always_install: bool = False,
    target_release: Optional[str] = None,
) -> bool:
    global host_arch
    dpkg_dev_req: Dict[str, Optional[str]] = {"dpkg-dev": "1.19"}
    if host_arch is None and packages != dpkg_dev_req:
        apt_install(dpkg_dev_req)
        host_arch_path = Path("/opt/host-arch")
        build_with_command(
            host_arch_path, f"dpkg-architecture -q DEB_HOST_ARCH > {host_arch_path}"
        )
        host_arch = dry_run_safe_read(host_arch_path, "amd64")
    if isinstance(packages, List):
        packages = dict([(p, None) for p in packages])
    if always_install:
        to_install = packages
    else:
        to_install = {}
        for package in packages.keys():
            wanted_version = packages[package]
            if not apt_is_installed(package, wanted_version):
                to_install[package] = wanted_version

        if to_install == {}:
            return False

    apt_update()
    # Confdef is to fix https://unix.stackexchange.com/a/416816/73838
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    cmd = (
        'apt-get satisfy "%s" --no-install-recommends --yes -o DPkg::Options::=--force-confdef'
        % ", ".join(
            [
                name if version is None else f"{name} (>= {version})"
                for (name, version) in to_install.items()
            ]
        )
    )
    if target_release is not None:
        cmd += f" --target-release {target_release}"
    run_command(cmd)
    return True


def debian_repo(name: str, contents: Optional[str] = None):
    fname = "/etc/apt/sources.list.d/%s.list" % name
    if contents is None:
        contents = "deb http://deb.debian.org/debian %s main" % name

    changed = set_file_contents(fname, contents)
    if changed:
        apt_update()
    return changed


def set_alternative(alt_name: str, option: str):
    current_alt_path = os.path.realpath(f"/etc/alternatives/{alt_name}")
    if current_alt_path != option:
        print(
            f"current alt path for {alt_name} is {current_alt_path} not {option}, so fixing"
        )
        run_command(f"update-alternatives --set {alt_name} {option}")
        return True
    else:
        return False
