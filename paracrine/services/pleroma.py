from pathlib import Path

from ..deps import Modules
from ..helpers.config import build_config, core_config, get_config_file, local_config
from ..helpers.debian import apt_install
from ..helpers.fs import (
    download_and_unpack,
    link,
    make_directory,
    run_command,
    run_with_marker,
    set_file_contents,
    set_file_contents_from_template,
)
from ..helpers.systemd import link_service, systemd_set
from ..helpers.users import adduser
from ..runners import certs
from . import postgresql

# FIXME: Do soapbox from https://gitlab.com/soapbox-pub/soapbox/-/jobs/3371276281/artifacts/download
# Unzipped with "unzip soapbox.zip -d instance" and then moved instance/static to /var/lib/pleroma
# https://docs.soapbox.pub/frontend/installing/#install-soapbox


def dependencies() -> Modules:
    LOCAL = build_config(local_config())
    return [
        postgresql,
        (
            certs,
            {"hostname": LOCAL["PLEROMA_HOST"], "email": LOCAL["PLEROMA_EMAIL"]},
        ),
    ]


def run():
    LOCAL = build_config(core_config())
    adduser("pleroma", home_dir="/opt/pleroma")
    make_directory("/opt/pleroma", owner="pleroma")
    # Taken from https://git.pleroma.social/pleroma/pleroma/-/pipelines?page=1&scope=branches&ref=stable using amd64:archive
    res = download_and_unpack(
        "https://git.pleroma.social/pleroma/pleroma/-/jobs/234433/artifacts/download?file_type=archive",
        "8ef0bea62671d39e60f9e08d13109a4c332c552a1f855184063353987d46c84a",
        "pleroma-2.5.2.zip",
        "/opt/pleroma-2.5.2",
    )
    release_changed = res["changed"]

    if release_changed:
        run_command("cp -R /opt/pleroma-2.5.2/release/* /opt/pleroma")
        run_command("chown -R pleroma /opt/pleroma")

    make_directory("/var/lib/pleroma/uploads", owner="pleroma")
    make_directory("/var/lib/pleroma/static", owner="pleroma")
    set_file_contents_from_template("/var/lib/pleroma/static/robots.txt", "robots.txt")
    make_directory("/etc/pleroma", owner="pleroma")
    config_changes = set_file_contents_from_template(
        "/etc/pleroma/config.exs", "config.exs.j2", ignore_changes=False, **LOCAL
    )
    db_changes = set_file_contents_from_template(
        "/opt/pleroma/setup_db.psql", "setup_db.psql.j2", ignore_changes=False, **LOCAL
    )

    run_with_marker(
        "/opt/pleroma/setup_db.marker",
        'su postgres -s $SHELL -lc "psql -f /opt/pleroma/setup_db.psql"',
        deps=["/opt/pleroma/setup_db.psql"],
        force_build=release_changed and db_changes,
        run_if_command_changed=False,
    )
    run_with_marker(
        "/opt/pleroma/migrate.marker",
        'su pleroma -s $SHELL -lc "./bin/pleroma_ctl migrate"',
        directory="/opt/pleroma",
        force_build=release_changed,
    )

    link_service("/opt/pleroma/installation/pleroma.service")
    systemd_set(
        "pleroma", enabled=True, running=True, restart=release_changed or config_changes
    )

    cert_dir = Path("/opt/letsencrypt")
    nginx_changes = make_directory(str(cert_dir))
    nginx_changes = (
        set_file_contents(
            cert_dir.joinpath("fullchain.pem"),
            get_config_file(f"configs/other-fullchain-{LOCAL['PLEROMA_HOST']}"),
        )
        or nginx_changes
    )
    nginx_changes = (
        set_file_contents(
            cert_dir.joinpath("privkey.pem"),
            get_config_file(f"configs/other-privkey-{LOCAL['PLEROMA_HOST']}"),
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

    nginx_changes = (
        set_file_contents_from_template(
            "/etc/nginx/sites-available/pleroma.conf",
            "pleroma.nginx.j2",
            PLEROMA_HOST=LOCAL["PLEROMA_HOST"],
            DUMMY_CERTS=certs.get_dummy_certs(),
        )
        or nginx_changes
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
