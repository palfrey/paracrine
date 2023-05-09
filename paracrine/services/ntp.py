from paracrine.debian import apt_install
from paracrine.systemd import systemd_set


def core_run():
    apt_install(["ntp"])
    systemd_set("ntp", enabled=True, running=True)
