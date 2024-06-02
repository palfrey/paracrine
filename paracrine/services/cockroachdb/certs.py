from pathlib import Path
from typing import Dict, List, Optional

from paracrine import dry_run_safe_read

from ...helpers.config import config_path
from ...helpers.fs import (
    build_with_command,
    download_and_unpack,
    make_directory,
    set_file_contents,
)
from ...helpers.network import wireguard_ips
from ...runners.core import use_this_host
from .common import binary_path, cockroach_hash, cockroach_url, local_node_ip

options = {}


def run():
    if not use_this_host("cockroach-certs"):
        return None
    unpacked = download_and_unpack(
        cockroach_url,
        cockroach_hash,
    )
    cockroach = Path(unpacked["dir_name"]).joinpath(binary_path)
    certs_dir = Path("/opt/cockroach/certs")
    make_directory(certs_dir)
    ca_key_path = certs_dir.joinpath("ca.key")
    build_with_command(
        ca_key_path,
        f"{cockroach} cert create-ca --certs-dir={certs_dir} --ca-key={ca_key_path} --overwrite --allow-ca-key-reuse",
    )
    root_key_path = certs_dir.joinpath("client.root.key")
    build_with_command(
        root_key_path,
        f"{cockroach} cert create-client root --certs-dir={certs_dir} --ca-key={ca_key_path} --overwrite",
        deps=[ca_key_path],
    )

    node_keys = {}
    ip_keys = set(wireguard_ips().values())
    ip_keys.add(local_node_ip())
    for ip in ip_keys:
        crt_path = certs_dir.joinpath(f"{ip}.crt")
        key_path = crt_path.with_suffix(".key")
        build_with_command(
            crt_path,
            f"{cockroach} cert create-node localhost {ip} --certs-dir={certs_dir} --ca-key={ca_key_path} --overwrite && mv {certs_dir.joinpath('node.crt')} {crt_path} && mv {certs_dir.joinpath('node.key')} {key_path}",
            deps=[ca_key_path],
        )
        node_keys[ip] = {
            "crt": dry_run_safe_read(crt_path, "fake crt"),
            "key": dry_run_safe_read(key_path, "fake key"),
        }

    return {
        "ca_crt": dry_run_safe_read(ca_key_path.with_suffix(".crt"), "fake crt"),
        "root_key": dry_run_safe_read(root_key_path, "fake root key"),
        "root_crt": dry_run_safe_read(
            root_key_path.with_suffix(".crt"), "fake root crt"
        ),
        "node_keys": node_keys,
    }


def parse_return(infos: List[Optional[Dict]]):
    assert len(infos) == 1, infos
    info = infos[0]
    if info is None or "ca_crt" not in info:
        return
    certs_dir = Path(config_path()).joinpath("cockroach-certs")
    make_directory(certs_dir)
    set_file_contents(certs_dir.joinpath("ca.crt"), info["ca_crt"])
    set_file_contents(certs_dir.joinpath("client.root.key"), info["root_key"])
    set_file_contents(certs_dir.joinpath("client.root.crt"), info["root_crt"])

    for ip, values in info["node_keys"].items():
        set_file_contents(certs_dir.joinpath(f"{ip}.key"), values["key"])
        set_file_contents(certs_dir.joinpath(f"{ip}.crt"), values["crt"])
