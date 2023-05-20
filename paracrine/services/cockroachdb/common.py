from pathlib import Path

from ...helpers.config import in_docker
from ...helpers.network import wireguard_ip

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


def local_node_ip():
    if in_docker():
        return "127.0.0.1"
    else:
        return wireguard_ip()
