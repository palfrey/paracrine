import json

from paracrine.helpers.config import get_config_file, host
from paracrine.helpers.debian import apt_install

from .common import get_all_kernel_versions
from .needs_upgrade import KERNEL_UPGRADE_KEY, UpgradeInfo

options: dict[str, object] = {}


def dependencies():
    from . import needs_upgrade

    return [(needs_upgrade, options)]


def run():
    upgrade_info_raw = get_config_file(f"configs/{KERNEL_UPGRADE_KEY}")
    upgrade_info: UpgradeInfo = json.loads(upgrade_info_raw)
    if upgrade_info["hostname"] != host()["name"]:  # which includes the None case
        return
    all_versions = get_all_kernel_versions()
    for key, value in all_versions.items():
        if key == upgrade_info["version"]:
            apt_install([value["package"]])
            break
    else:
        raise Exception(all_versions)
