from pathlib import Path

from ..helpers.debian import add_trusted_key, apt_install, debian_repo
from ..helpers.fs import make_directory, run_with_marker
from ..helpers.systemd import systemd_set


def run():
    add_trusted_key(
        "https://www.postgresql.org/media/keys/ACCC4CF8.asc",
        "postgresql",
        "0144068502a1eddd2a0280ede10ef607d1ec592ce819940991203941564e8e76",
    )
    debian_repo(
        "postgresql_org_repository",
        "deb http://apt.postgresql.org/pub/repos/apt bullseye-pgdg main",
    )
    apt_install(["postgresql-14"], target_release="bullseye-pgdg")
    systemd_set("postgresql@14-main", enabled=True, running=True)


db_dir = Path("/opt/postgresql")


def make_user(username: str, password: str):
    user_dir = db_dir.joinpath("users")
    make_directory(user_dir)
    run_with_marker(
        user_dir.joinpath(username),
        f"sudo -u postgres psql --command=\"CREATE USER {username} WITH ENCRYPTED PASSWORD '{password}';\"",
        run_if_command_changed=False,
    )


def make_db(name: str, owner: str):
    data_dir = db_dir.joinpath("databases")
    make_directory(data_dir)
    run_with_marker(
        data_dir.joinpath(name),
        f'sudo -u postgres psql --command="CREATE DATABASE {name} OWNER {owner};"',
        run_if_command_changed=False,
    )
