import json
import logging
from pathlib import Path
from typing import TypedDict, cast

from looseversion import LooseVersion

from paracrine.helpers.config import config_path, host
from paracrine.helpers.fs import run_command

from .common import get_all_kernel_versions

options: dict[str, object] = {}


class KernelUpgrade(TypedDict):
    hostname: str
    current_version: str
    upgrade_version: str | None


def run() -> KernelUpgrade:
    current_version = LooseVersion(run_command("uname -r", dry_run_safe=True).strip())

    def ku(upgrade_version: str | None) -> KernelUpgrade:
        hostname = host()["name"]
        return KernelUpgrade(
            hostname=hostname,
            current_version=current_version.vstring,
            upgrade_version=upgrade_version,
        )

    minimum_version_raw = cast(str | None, options.get("minimum_version"))
    if minimum_version_raw is None:
        return ku(None)
    minimum_version = LooseVersion(minimum_version_raw)
    if minimum_version <= current_version:
        return ku(None)
    candidate_version = None
    all_versions = get_all_kernel_versions()
    for value in all_versions.values():
        version = value["version"]
        if version >= minimum_version and (
            candidate_version is None or candidate_version > version
        ):
            candidate_version = version
    if candidate_version is None:
        raise Exception(
            "No candidate versions for kernel upgrade. Wanted {}, got {}".format(
                minimum_version_raw, ", ".join(sorted(all_versions.keys()))
            )
        )
    return ku(candidate_version.vstring)


class UpgradeInfo(TypedDict):
    hostname: str | None
    version: str | None


KERNEL_UPGRADE_KEY = "kernel-upgrade"


def parse_return(
    infos: list[KernelUpgrade],
) -> None:
    upgrade_info_path = Path(config_path()).joinpath(KERNEL_UPGRADE_KEY)
    upgrade_info: UpgradeInfo
    try:
        with upgrade_info_path.open() as fp:
            upgrade_info = json.load(fp)
    except FileNotFoundError:
        upgrade_info = {"hostname": None, "version": None}
    if upgrade_info["hostname"] is not None:
        for info in infos:
            if info["hostname"] == upgrade_info["hostname"]:
                if info["upgrade_version"] is None:
                    logging.info(
                        "%s finished upgrading kernel to %s"
                        % (info["hostname"], upgrade_info["version"])
                    )
                    upgrade_info["hostname"] = None
                    upgrade_info["version"] = None
                else:
                    logging.info(
                        "%s is still upgrading to %s"
                        % (info["hostname"], upgrade_info["version"])
                    )

    for info in infos:
        if info["upgrade_version"] is not None:
            if (
                upgrade_info["hostname"] is not None
                and upgrade_info["hostname"] != info["hostname"]
            ):
                logging.info(
                    "%s is upgrading, but %s also wants to upgrade, so ignoring the latter"
                    % (upgrade_info["hostname"], info["hostname"])
                )
                continue
            upgrade_info["hostname"] = info["hostname"]
            upgrade_info["version"] = info["upgrade_version"]

    with upgrade_info_path.open("w") as fp:
        json.dump(upgrade_info, fp)
