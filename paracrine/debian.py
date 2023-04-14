import os
import re
from typing import Dict, List, Optional, Union

from debian.debian_support import version_compare

from .fs import run_command, set_file_contents

host_arch: Optional[str] = None

_version_pattern = re.compile(r"Version: (\S+)")


# List is just "any version", Dict is a "name => min version" requirement
def apt_install(
    packages: Union[List[str], Dict[str, Optional[str]]],
    always_install: bool = False,
    target_release: Optional[str] = None,
) -> None:
    global host_arch
    if host_arch is None and packages != ["dpkg-dev"]:
        apt_install(["dpkg-dev"])
        host_arch = run_command("dpkg-architecture -q DEB_HOST_ARCH").strip()
    if isinstance(packages, List):
        packages = dict([(p, None) for p in packages])
    if always_install:
        to_install = list(packages.keys())
    else:
        to_install = []
        for package in packages.keys():
            paths = [
                f"/var/lib/dpkg/info/{package}.list",
                f"/var/lib/dpkg/info/{package}:{host_arch}.list",
            ]
            for path in paths:
                if not os.path.exists(path):
                    continue
                wanted_version = packages[package]
                if wanted_version is None:  # existance is enough
                    break
                status = run_command(f"dpkg-query --status {package}")
                version = _version_pattern.search(status).group(1)
                if version_compare(version, wanted_version) >= 0:
                    break
            else:
                to_install.append(package)

        if to_install == []:
            return
    # Confdef is to fix https://unix.stackexchange.com/a/416816/73838
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    cmd = (
        "apt-get install %s --no-install-recommends --yes -o DPkg::Options::=--force-confdef"
        % " ".join(to_install)
    )
    if target_release is not None:
        cmd += f" --target-release {target_release}"
    run_command(cmd)


def apt_update():
    run_command("apt-get update --allow-releaseinfo-change")


def debian_repo(name, contents=None):
    fname = "/etc/apt/sources.list.d/%s.list" % name
    if contents is None:
        contents = "deb http://deb.debian.org/debian %s main" % name

    changed = set_file_contents(fname, contents)
    if changed:
        apt_update()


def set_alternative(alt_name: str, option: str):
    current_alt_path = os.path.realpath(f"/etc/alternatives/{alt_name}")
    if current_alt_path != option:
        print(
            f"current alt path for {alt_name} is {current_alt_path} not {option}, so fixing"
        )
        run_command(f"update-alternatives --set {alt_name} {option}")
