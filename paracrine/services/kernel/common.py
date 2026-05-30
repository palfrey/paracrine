import json
from typing import TypedDict

from looseversion import LooseVersion

from paracrine.helpers.debian import apt_update, install_apt_query
from paracrine.helpers.fs import run_command


class VersionInfo(TypedDict):
    version: LooseVersion
    installed: bool
    package: str


def get_all_kernel_versions():
    apt_update()
    apt_query = install_apt_query()
    raw = run_command(
        "{} linux-image-*".format(apt_query["path"]),
        dry_run_safe=True,
    )
    versions: dict[str, VersionInfo] = {}
    for line in raw.split("\n"):
        if line.strip() == "":
            continue
        info = json.loads(line)
        if (
            "-unsigned" in info["name"]
            or "-dbg" in info["name"]
            or "-rt" in info["name"]
            or "-cloud" in info["name"]
        ):
            continue
        version = info["name"][len("linux-image-") :]
        if not version[0].isdigit():
            continue
        version = version[: version.find("-")]
        versions[version] = {
            "version": LooseVersion(version),
            "installed": info["installed_version"] is not None,
            "package": info["name"],
        }
    return versions
