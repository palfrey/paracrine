import re
from typing import Any, Dict

from ... import dry_run_safe_read
from ...helpers.config import build_config, core_config
from ...helpers.debian import apt_install
from ...helpers.fs import (
    insert_or_replace,
    render_template,
    set_file_contents,
    set_file_contents_from_template,
)
from ...helpers.network import wireguard_ip
from ...helpers.systemd import systemd_set
from .. import wireguard
from . import check_master
from .common import get_master_ip

options: Dict[str, Any] = {}


def dependencies():
    return [wireguard, check_master]


def run():
    apt_install(["redis-sentinel", "redis-server", "redis-tools"])
    LOCAL = build_config(core_config())
    local_ip = wireguard_ip()
    master_ip = get_master_ip()
    server_changes = set_file_contents_from_template(
        "/etc/redis/redis.conf",
        "redis.conf.j2",
        WIREGUARD_IP=local_ip,
        IS_MASTER=local_ip == master_ip,
        MASTER_IP=master_ip,
        REDIS_PASSWORD=LOCAL["REDIS_PASSWORD"],
    )
    sentinel_changes = False
    # We need to have all the lines we've added, but sentinel messes with things and might add others
    rendered = render_template(
        "redis-sentinel.conf.j2",
        WIREGUARD_IP=local_ip,
        MASTER_IP=master_ip,
        QUORUM_REQUIRED=options.get("quorum", "2"),
        REDIS_PASSWORD=LOCAL["REDIS_PASSWORD"],
    )
    current = dry_run_safe_read("/etc/redis/sentinel.conf", "Example sentinel.conf")
    if "Example sentinel.conf" in current:
        # original Debian one, replace
        sentinel_changes = set_file_contents("/etc/redis/sentinel.conf", rendered)
    else:
        for line in rendered.split("\n"):
            if line.strip() == "":
                continue
            if line.startswith("bind"):
                patt = re.compile("bind.+")
            elif line.startswith("user default on"):
                continue
            elif line.find("mymaster") != -1:
                patt = re.compile(line[: line.find("mymaster")] + "mymaster.+")
            else:
                patt = re.compile(" ".join(line.split(" ")[:-1]) + ".+")
            sentinel_changes = (
                insert_or_replace("/etc/redis/sentinel.conf", patt, line)
                or sentinel_changes
            )
    systemd_set("redis-server", enabled=True, running=True, restart=server_changes)
    systemd_set("redis-sentinel", enabled=True, running=True, restart=sentinel_changes)
