import logging
from pathlib import Path
from typing import Dict, Union

from ...helpers.config import host, in_docker, servers
from ...helpers.network import wireguard_ip


def cockroach_url(cockroach_version: str) -> str:
    return f"https://binaries.cockroachdb.com/cockroach-v{cockroach_version}.linux-amd64.tgz"


def binary_path(cockroach_version: str) -> str:
    return f"cockroach-v{cockroach_version}.linux-amd64/cockroach"


def cockroach_binary(cockroach_version: str) -> str:
    return f"/opt/cockroach-v{cockroach_version}.linux-amd64/{binary_path(cockroach_version)}"


cockroach_versions = {
    "23.1.1": {
        "hash": "8197562ce59d1ac4f53f67c9d277827d382db13c5e650980942bcb5e5104bb4e"
    }
}

HOME_DIR = Path("/var/lib/cockroach")
CERTS_DIR = HOME_DIR.joinpath("certs")
USER = "cockroach"


def local_node_ip() -> str:
    if in_docker():
        return "127.0.0.1"
    else:
        return wireguard_ip()


def node_count() -> int:
    return len(servers())


def calculate_version(versions: Union[None, str, Dict[str, int]]) -> Dict[str, str]:
    if versions is None:
        versions = sorted(list(cockroach_versions.keys()))[0]

    if isinstance(versions, str):
        versions = {versions: node_count()}

    logging.info(f"Cockroach versions is {versions}")

    server_list = sorted(servers(), key=lambda s: s["name"])
    version_map: Dict[str, str] = {}

    index = 0
    for version, count in sorted(versions.items()):
        for c in range(count):
            version_map[server_list[index + c]["name"]] = version
        index += count

    assert index == len(server_list)

    logging.info(f"Cockroach version map is {version_map}")
    return version_map


def version_for_host(versions: Dict[str, str]) -> str:
    return versions[host()["name"]]
