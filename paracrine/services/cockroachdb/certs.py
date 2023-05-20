from pathlib import Path
from typing import Dict, List

from ...helpers.config import config_path
from ...helpers.fs import (
    build_with_command,
    download_and_unpack,
    make_directory,
    set_file_contents,
)
from ...helpers.network import wireguard_ips
from ...runners.core import use_this_host
from .common import CERTS_DIR, binary_path, cockroach_hash, cockroach_url

options = {}


def run():
    if not use_this_host("cockroach-certs"):
        return
    unpacked = download_and_unpack(
        cockroach_url,
        cockroach_hash,
    )
    cockroach = Path(unpacked["dir_name"]).joinpath(binary_path)
    make_directory(CERTS_DIR)
    ca_key_path = CERTS_DIR.joinpath("ca.key")
    build_with_command(
        ca_key_path,
        f"{cockroach} cert create-ca --certs-dir={CERTS_DIR} --ca-key={ca_key_path} --overwrite --allow-ca-key-reuse",
    )
    root_key_path = CERTS_DIR.joinpath("client.root.key")
    build_with_command(
        root_key_path,
        f"{cockroach} cert create-client root --certs-dir={CERTS_DIR} --ca-key={ca_key_path} --overwrite",
        deps=[ca_key_path],
    )

    node_keys = {}
    for ip in wireguard_ips().values():
        crt_path = CERTS_DIR.joinpath(f"{ip}.crt")
        key_path = crt_path.with_suffix(".key")
        build_with_command(
            crt_path,
            f"{cockroach} cert create-node localhost {ip} --certs-dir={CERTS_DIR} --ca-key={ca_key_path} --overwrite && mv {CERTS_DIR.joinpath('node.crt')} {crt_path} && mv {CERTS_DIR.joinpath('node.key')} {key_path}",
            deps=[ca_key_path],
        )
        node_keys[ip] = {"crt": crt_path.open().read(), "key": key_path.open().read()}

    return {
        "root_key": root_key_path.open().read(),
        "root_crt": root_key_path.with_suffix(".crt").open().read(),
        "node_keys": node_keys,
    }


def parse_return(infos: List[Dict]):
    assert len(infos) == 1, infos
    info = infos[0]
    certs_dir = Path(config_path()).joinpath("cockroach-certs")
    make_directory(certs_dir)
    set_file_contents(certs_dir.joinpath("client.root.key"), info["root_key"])
    set_file_contents(certs_dir.joinpath("client.root.crt"), info["root_crt"])

    for ip, values in info["node_keys"].items():
        set_file_contents(certs_dir.joinpath(f"{ip}.key"), values["key"])
        set_file_contents(certs_dir.joinpath(f"{ip}.crt"), values["crt"])
