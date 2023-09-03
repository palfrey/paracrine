from ..helpers.debian import apt_install
from ..helpers.systemd import systemd_set


def run():
    apt_install(["ntp"])
    systemd_set("ntp", enabled=True, running=True)
