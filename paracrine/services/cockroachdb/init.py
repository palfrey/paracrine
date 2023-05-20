from ...helpers.fs import run_with_marker
from ...helpers.network import wireguard_ip
from ...runners.core import use_this_host
from . import certs, node
from .common import CERTS_DIR, HOME_DIR, cockroach_binary

options = {}


def dependencies():
    return [node, certs]


def run():
    if not use_this_host("cockroach-init"):
        return
    COCKROACH_PORT = options.get("COCKROACH_PORT", 26257)
    run_with_marker(
        HOME_DIR.joinpath("init_done"),
        f"{cockroach_binary} init --certs-dir={CERTS_DIR} --host={wireguard_ip()}:{COCKROACH_PORT}",
    )
