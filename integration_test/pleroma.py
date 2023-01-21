from pathlib import Path
from paracrine.debian import apt_install, debian_repo
from paracrine.config import core_config, environment, get_config_file
from paracrine.fs import (
    build_with_command,
    download,
    download_and_unpack,
    link,
    make_directory,
    run_command,
    set_file_contents,
    set_file_contents_from_template,
)
from paracrine.systemd import systemctl_daemon_reload, systemd_set
from paracrine.users import adduser

# FIXME: Do soapbox from https://gitlab.com/soapbox-pub/soapbox/-/jobs/3371276281/artifacts/download
# Unzipped with "unzip soapbox.zip -d instance" and then moved instance/static to /var/lib/pleroma


def do():
    config = core_config()
    env = environment()
    LOCAL = config["environments"][env]

    adduser("pleroma", home_dir="/opt/pleroma")
    make_directory("/opt/pleroma", owner="pleroma")
    # Taken from https://git.pleroma.social/pleroma/pleroma/-/pipelines?page=1&scope=branches&ref=stable
    res = download_and_unpack(
        "https://git.pleroma.social/pleroma/pleroma/-/jobs/220705/artifacts/download?file_type=archive",
        "8b4e2ab17362c7b0ed3ca685e19d578ad842ac00cde2db7d8c54dfd5a4e05891",
        "pleroma-2.4.4.zip",
        "/opt/pleroma-2.4.4",
    )
    release_changed = res["changed"]

    if release_changed:
        run_command("cp -R /opt/pleroma-2.4.4/release/* /opt/pleroma")
        run_command("chown -R pleroma /opt/pleroma")

    make_directory("/var/lib/pleroma/uploads", owner="pleroma")
    make_directory("/var/lib/pleroma/static", owner="pleroma")
    set_file_contents_from_template("/var/lib/pleroma/static/robots.txt", "robots.txt")
    make_directory("/etc/pleroma", owner="pleroma")
    config_changes = set_file_contents_from_template(
        "/etc/pleroma/config.exs", "config.exs.j2", PLEROMA_HOST=LOCAL["PLEROMA_HOST"]
    )
    db_changes = set_file_contents_from_template(
        "/opt/pleroma/setup_db.psql", "setup_db.psql"
    )

    download(
        "https://www.postgresql.org/media/keys/ACCC4CF8.asc",
        "/etc/apt/trusted.gpg.d/postgresql.gpg.asc",
        "0144068502a1eddd2a0280ede10ef607d1ec592ce819940991203941564e8e76",
    )
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

    if release_changed and db_changes:
        run_command('su postgres -s $SHELL -lc "psql -f /opt/pleroma/setup_db.psql"')

    if release_changed:
        run_command(
            'su pleroma -s $SHELL -lc "./bin/pleroma_ctl migrate"',
            directory="/opt/pleroma",
        )

    link_change = link(
        "/etc/systemd/system/pleroma.service",
        "/opt/pleroma/installation/pleroma.service",
    )
    if link_change:
        systemctl_daemon_reload()
    systemd_set(
        "pleroma", enabled=True, running=True, restart=release_changed or config_changes
    )

    cert_dir = Path("/opt/letsencrypt")
    nginx_changes = make_directory(str(cert_dir))
    nginx_changes = (
        set_file_contents(
            cert_dir.joinpath("fullchain.pem"),
            get_config_file("configs/other-fullchain"),
        )
        or nginx_changes
    )
    nginx_changes = (
        set_file_contents(
            cert_dir.joinpath("privkey.pem"), get_config_file("configs/other-privkey")
        )
        or nginx_changes
    )
    nginx_changes = (
        set_file_contents(
            cert_dir.joinpath("options-ssl-nginx.conf"),
            get_config_file("configs/other-ssl-options"),
        )
        or nginx_changes
    )

    apt_install(["nginx"])

    nginx_changes = set_file_contents_from_template(
        "/etc/nginx/sites-available/pleroma.conf",
        "pleroma.nginx.j2",
        PLEROMA_HOST=LOCAL["PLEROMA_HOST"],
    )
    nginx_changes = (
        link(
            "/etc/nginx/sites-enabled/pleroma.conf",
            "/etc/nginx/sites-available/pleroma.conf",
        )
        or nginx_changes
    )

    if nginx_changes:
        systemd_set("nginx", reloaded=True)
