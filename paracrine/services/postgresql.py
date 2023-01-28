from paracrine.debian import apt_install, debian_repo
from paracrine.fs import build_with_command, download
from paracrine.systemd import systemd_set


def core_run():
    apt_install(["curl"])
    download(
        "https://www.postgresql.org/media/keys/ACCC4CF8.asc",
        "/etc/apt/trusted.gpg.d/postgresql.gpg.asc",
        "0144068502a1eddd2a0280ede10ef607d1ec592ce819940991203941564e8e76",
    )
    apt_install(["gpg"])
    build_with_command(
        "/etc/apt/trusted.gpg.d/postgresql.gpg",
        "cat /etc/apt/trusted.gpg.d/postgresql.gpg.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/postgresql.gpg",
        ["/etc/apt/trusted.gpg.d/postgresql.gpg.asc"],
    )
    debian_repo(
        "postgresql_org_repository",
        "deb http://apt.postgresql.org/pub/repos/apt bullseye-pgdg main",
    )
    apt_install(["postgresql-14"])
    systemd_set("postgresql", enabled=True, running=True)
