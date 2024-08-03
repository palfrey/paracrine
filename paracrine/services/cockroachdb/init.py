from typing import Dict, cast

from ...helpers.fs import run_with_marker
from ...runners.core import use_this_host
from . import certs, node
from .common import (
    CERTS_DIR,
    HOME_DIR,
    cockroach_binary,
    local_node_ip,
    version_for_host,
)

options: Dict[str, object] = {}


def dependencies():
    return [(node, options), (certs, {"versions": options["versions"]})]


def run():
    version = version_for_host(cast(Dict[str, str], options["versions"]))
    if not use_this_host("cockroach-init"):
        return
    COCKROACH_PORT = options.get("COCKROACH_PORT", 26257)
    run_with_marker(
        HOME_DIR.joinpath("init_done"),
        f"{cockroach_binary(version)} init --certs-dir={CERTS_DIR} --host={local_node_ip()}:{COCKROACH_PORT}",
        run_if_command_changed=False,
    )
