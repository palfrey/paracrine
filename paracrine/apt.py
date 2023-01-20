import os
from typing import List

from .fs import run_command


def apt_install(packages: List[str], always_install: bool = False) -> None:
    if not always_install:
        packages = [
            package
            for package in packages
            if not os.path.exists(f"/var/lib/dpkg/info/{package}.list")
        ]
        if packages == []:
            return
    # Confdef is to fix https://unix.stackexchange.com/a/416816/73838
    run_command(
        "apt-get install %s --no-install-recommends --yes -o DPkg::Options::=--force-confdef"
        % " ".join(packages)
    )


def apt_update():
    run_command("apt-get update --allow-releaseinfo-change")
