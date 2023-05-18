from pathlib import Path

from paracrine.config import config_path, data_path, get_config_file, get_config_keys
from paracrine.core import use_this_host
from paracrine.fs import (
    build_with_command,
    download_and_unpack,
    make_directory,
    run_with_marker,
    set_file_contents,
    set_file_contents_from_template,
    set_mode,
)
from paracrine.network import wireguard_ip, wireguard_ips
from paracrine.services import ntp, wireguard
from paracrine.systemd import systemctl_daemon_reload, systemd_set
from paracrine.users import adduser

options = {}


def dependencies():
    return [ntp, wireguard]


cockroach_version = "23.1.1"
cockroach_url = (
    f"https://binaries.cockroachdb.com/cockroach-v{cockroach_version}.linux-amd64.tgz"
)
cockroach_hash = "8197562ce59d1ac4f53f67c9d277827d382db13c5e650980942bcb5e5104bb4e"
binary_path = f"cockroach-v{cockroach_version}.linux-amd64/cockroach"
# FIXME
cockroach_binary = f"/opt/cockroach-v{cockroach_version}.linux-amd64/{binary_path}"
HOME_DIR = Path("/var/lib/cockroach")
CERTS_DIR = HOME_DIR.joinpath("certs")
USER = "cockroach"


def bootstrap_local():
    store_path = Path(data_path()).joinpath("cockroach")
    make_directory(store_path)
    download_and_unpack(
        cockroach_url,
        cockroach_hash,
        dir_name=store_path,
        compressed_root=data_path(),
    )
    cockroach = store_path.joinpath(binary_path)
    certs_dir = Path(config_path()).joinpath("cockroach-certs")
    make_directory(certs_dir)
    build_with_command(
        store_path.joinpath("ca.key"),
        f"{cockroach} cert create-ca --certs-dir={certs_dir} --ca-key={store_path}/ca.key --overwrite --allow-ca-key-reuse",
    )
    build_with_command(
        certs_dir.joinpath("client.root.key"),
        f"{cockroach} cert create-client root --certs-dir={certs_dir} --ca-key={store_path}/ca.key --overwrite",
        deps=[f"{store_path}/ca.key"],
    )

    for ip in wireguard_ips().values():
        crt_path = certs_dir.joinpath(f"{ip}.crt")
        build_with_command(
            crt_path,
            f"{cockroach} cert create-node localhost {ip} --certs-dir={certs_dir} --ca-key={store_path}/ca.key --overwrite && mv {certs_dir.joinpath('node.crt')} {crt_path} && mv {certs_dir.joinpath('node.key')} {crt_path.with_suffix('.key')}",
            deps=[f"{store_path}/ca.key"],
        )


def core_run():
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
        if wireguard_ip() in fname:
            new_fname = new_fname.replace(wireguard_ip(), "node")
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
        WIREGUARD_IP=wireguard_ip(),
        HTTP_PORT=options.get("HTTP_PORT", 8080),
        COCKROACH_PORT=COCKROACH_PORT,
        SQL_PORT=SQL_PORT,
        HOST_LIST=",".join(
            [f"{ip}:{COCKROACH_PORT}" for ip in wireguard_ips().values()]
        ),
    )
    if service_file_changes:
        systemctl_daemon_reload()
    systemd_set(
        "cockroach",
        enabled=True,
        running=True,
        restart=file_changes or service_file_changes,
    )

    if use_this_host("cockroach"):
        run_with_marker(
            HOME_DIR.joinpath("init_done"),
            f"{cockroach_binary} init --certs-dir={CERTS_DIR} --host={wireguard_ip()}:{COCKROACH_PORT}",
        )


def make_user(username: str, password: str):
    user_dir = HOME_DIR.joinpath("users")
    make_directory(user_dir)
    SQL_PORT = options.get("SQL_PORT", 26258)
    run_with_marker(
        user_dir.joinpath(username),
        f"{cockroach_binary} sql --certs-dir={CERTS_DIR} --host={wireguard_ip()}:{SQL_PORT} --execute \"CREATE USER {username} WITH PASSWORD '{password}';\"",
    )


def make_db(name: str, owner: str):
    data_dir = HOME_DIR.joinpath("databases")
    make_directory(data_dir)
    SQL_PORT = options.get("SQL_PORT", 26258)
    run_with_marker(
        data_dir.joinpath(name),
        f'{cockroach_binary} sql --certs-dir={CERTS_DIR} --host={wireguard_ip()}:{SQL_PORT} --execute="CREATE DATABASE {name} OWNER {owner};"',
    )
