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


cockroach_url = "https://binaries.cockroachdb.com/cockroach-v22.2.9.linux-amd64.tgz"
cockroach_hash = "7ed169bf5f1f27bd49ab4e04a00068f7b44cff8a0672778b0f67d87ece3de07b"
binary_path = "cockroach-v22.2.9.linux-amd64/cockroach"
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
        f"{cockroach} cert create-ca --certs-dir={certs_dir} --ca-key={store_path}/ca.key",
    )
    build_with_command(
        certs_dir.joinpath("client.root.key"),
        f"{cockroach} cert create-client root --certs-dir={certs_dir} --ca-key={store_path}/ca.key",
    )

    for ip in wireguard_ips().values():
        crt_path = certs_dir.joinpath(f"{ip}.crt")
        build_with_command(
            crt_path,
            f"{cockroach} cert create-node localhost {ip} --certs-dir={certs_dir} --ca-key={store_path}/ca.key && mv {certs_dir.joinpath('node.crt')} {crt_path} && mv {certs_dir.joinpath('node.key')} {crt_path.with_suffix('.key')}",
        )


def core_run():
    unpacked = download_and_unpack(
        cockroach_url,
        cockroach_hash,
    )
    cockroach_path = Path(unpacked["dir_name"]).joinpath(binary_path)
    adduser(USER, HOME_DIR)
    make_directory(CERTS_DIR)
    for fname in get_config_keys():
        if "cockroach-certs" not in fname:
            continue
        new_fname = CERTS_DIR.joinpath(
            fname.replace("configs/cockroach-certs/", "")
        ).as_posix()
        if wireguard_ip() in fname:
            new_fname = new_fname.replace(wireguard_ip(), "node")
        set_file_contents(new_fname, get_config_file(fname), owner="cockroach")
        set_mode(new_fname, "700")

    COCKROACH_PORT = options.get("COCKROACH_PORT", 26257)
    SQL_PORT = options.get("SQL_PORT", 26258)
    changes = set_file_contents_from_template(
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
    if changes:
        systemctl_daemon_reload()
    systemd_set("cockroach", enabled=True, running=True, restart=changes)

    if use_this_host("cockroach"):
        run_with_marker(
            HOME_DIR.joinpath("init_done"),
            f"/opt/cockroach-v22.2.9.linux-amd64/cockroach-v22.2.9.linux-amd64/cockroach init --certs-dir={CERTS_DIR} --host={wireguard_ip()}:26257",
        )
