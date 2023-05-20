from pathlib import Path

from ...helpers.config import get_config_file, get_config_keys, in_docker
from ...helpers.fs import (
    download_and_unpack,
    make_directory,
    set_file_contents,
    set_file_contents_from_template,
    set_mode,
)
from ...helpers.network import wireguard_ips
from ...helpers.systemd import systemctl_daemon_reload, systemd_set
from ...helpers.users import adduser
from .. import wireguard
from . import certs
from .common import (
    CERTS_DIR,
    HOME_DIR,
    USER,
    binary_path,
    cockroach_hash,
    cockroach_url,
    local_node_ip,
)

options = {}


def dependencies():
    return [certs, wireguard]


def run():
    unpacked = download_and_unpack(
        cockroach_url,
        cockroach_hash,
    )
    cockroach_path = Path(unpacked["dir_name"]).joinpath(binary_path)
    adduser(USER, HOME_DIR)
    make_directory(CERTS_DIR)
    file_changes = False
    for fname in get_config_keys():
        if "cockroach-certs" not in fname:
            continue
        new_fname = CERTS_DIR.joinpath(
            fname.replace("configs/cockroach-certs/", "")
        ).as_posix()
        if local_node_ip() in fname:
            new_fname = new_fname.replace(local_node_ip(), "node")
        elif "192.168" in new_fname:  # wireguard
            continue
        file_changes = (
            set_file_contents(new_fname, get_config_file(fname), owner="cockroach")
            or file_changes
        )
        file_changes = set_mode(new_fname, "700") or file_changes

    COCKROACH_PORT = options.get("COCKROACH_PORT", 26257)
    SQL_PORT = options.get("SQL_PORT", 26258)
    service_file_changes = set_file_contents_from_template(
        "/etc/systemd/system/cockroach.service",
        "cockroach.service.j2",
        COCKROACH_PATH=cockroach_path,
        HOME_DIR=HOME_DIR,
        USER=USER,
        CERTS_DIR=CERTS_DIR,
        WIREGUARD_IP=local_node_ip(),
        HTTP_PORT=options.get("HTTP_PORT", 8080),
        COCKROACH_PORT=COCKROACH_PORT,
        SQL_PORT=SQL_PORT,
        HOST_LIST=",".join(
            [f"{ip}:{COCKROACH_PORT}" for ip in wireguard_ips().values()]
        ),
    )
    if service_file_changes:
        systemctl_daemon_reload()

    # FIXME: Can't make this work in Docker
    if not in_docker():
        systemd_set(
            "cockroach",
            enabled=True,
            running=True,
            restart=file_changes or service_file_changes,
        )
