from typing import Dict, Optional, cast

from ...helpers.fs import make_directory, run_with_marker
from ...helpers.network import wireguard_ip

options: Dict[str, object] = {}


def dependencies():
    from . import init
    from .common import calculate_version

    options["versions"] = calculate_version(
        cast(Optional[str], options.get("versions"))
    )

    return [(init, options)]


def make_user(version: str, username: str, password: str):
    from .common import CERTS_DIR, HOME_DIR, cockroach_binary

    user_dir = HOME_DIR.joinpath("users")
    make_directory(user_dir)
    SQL_PORT = options.get("SQL_PORT", 26258)
    run_with_marker(
        user_dir.joinpath(username),
        f"{cockroach_binary(version)} sql --certs-dir={CERTS_DIR} --host={wireguard_ip()}:{SQL_PORT} --execute \"CREATE USER {username} WITH PASSWORD '{password}';\"",
        run_if_command_changed=False,
    )


def make_db(version: str, name: str, owner: str):
    from .common import CERTS_DIR, HOME_DIR, cockroach_binary

    data_dir = HOME_DIR.joinpath("databases")
    make_directory(data_dir)
    SQL_PORT = options.get("SQL_PORT", 26258)
    run_with_marker(
        data_dir.joinpath(name),
        f'{cockroach_binary(version)} sql --certs-dir={CERTS_DIR} --host={wireguard_ip()}:{SQL_PORT} --execute="CREATE DATABASE {name} OWNER {owner};"',
        run_if_command_changed=False,
    )
