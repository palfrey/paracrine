from ...helpers.config import in_docker
from ...helpers.fs import run_with_marker
from ...runners.core import use_this_host
from . import certs, node
from .common import CERTS_DIR, HOME_DIR, cockroach_binary, local_node_ip

options = {}


def dependencies():
    return [(node, options), (certs, options)]


def run():
    # FIXME: Can't make node start work in docker
    if in_docker() or not use_this_host("cockroach-init"):
        return
    COCKROACH_PORT = options.get("COCKROACH_PORT", 26257)
    run_with_marker(
        HOME_DIR.joinpath("init_done"),
        f"{cockroach_binary} init --certs-dir={CERTS_DIR} --host={local_node_ip()}:{COCKROACH_PORT}",
    )
