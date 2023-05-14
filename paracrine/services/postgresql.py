from paracrine.debian import add_trusted_key, apt_install, debian_repo
from paracrine.systemd import systemd_set


def core_run():
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
