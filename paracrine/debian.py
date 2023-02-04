import os
from typing import List, Optional

from .fs import run_command, set_file_contents

host_arch: Optional[str] = None


def apt_install(packages: List[str], always_install: bool = False) -> None:
    global host_arch
    if host_arch is None:
        host_arch = run_command("dpkg-architecture -q DEB_HOST_ARCH").strip()
    if not always_install:
        packages = [
            package
            for package in packages
            if not os.path.exists(f"/var/lib/dpkg/info/{package}.list")
            and not os.path.exists(f"/var/lib/dpkg/info/{package}:{host_arch}.list")
        ]
        if packages == []:
            return
    # Confdef is to fix https://unix.stackexchange.com/a/416816/73838
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    run_command(
        "apt-get install %s --no-install-recommends --yes -o DPkg::Options::=--force-confdef"
        % " ".join(packages)
    )


def apt_update():
    run_command("apt-get update --allow-releaseinfo-change")


def debian_repo(name, contents=None):
    fname = "/etc/apt/sources.list.d/%s.list" % name
    if contents is None:
        contents = "deb http://deb.debian.org/debian %s main" % name

    changed = set_file_contents(fname, contents)
    if changed:
        apt_update()
