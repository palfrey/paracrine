from ...helpers.fs import make_directory, run_with_marker
from ...helpers.network import wireguard_ip

options = {}


def dependencies():
    from . import init

    return [(init, options)]


def make_user(username: str, password: str):
    from .common import CERTS_DIR, HOME_DIR, cockroach_binary

    user_dir = HOME_DIR.joinpath("users")
    make_directory(user_dir)
    SQL_PORT = options.get("SQL_PORT", 26258)
    run_with_marker(
        user_dir.joinpath(username),
        f"{cockroach_binary} sql --certs-dir={CERTS_DIR} --host={wireguard_ip()}:{SQL_PORT} --execute \"CREATE USER {username} WITH PASSWORD '{password}';\"",
    )


def make_db(name: str, owner: str):
    from .common import CERTS_DIR, HOME_DIR, cockroach_binary

    data_dir = HOME_DIR.joinpath("databases")
    make_directory(data_dir)
    SQL_PORT = options.get("SQL_PORT", 26258)
    run_with_marker(
        data_dir.joinpath(name),
        f'{cockroach_binary} sql --certs-dir={CERTS_DIR} --host={wireguard_ip()}:{SQL_PORT} --execute="CREATE DATABASE {name} OWNER {owner};"',
    )
