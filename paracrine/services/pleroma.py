from pathlib import Path
from typing import cast

from ..deps import Modules
from ..helpers.config import build_config, core_config, local_config
from ..helpers.debian import apt_install
from ..helpers.fs import (
    are_deps_younger,
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
    # Deps of the Debian elixir package (which is out of date) plus Pleroma
    apt_install(
        [
            "erlang-dev",
            "erlang-base",
            "erlang-crypto",
            "erlang-inets",
            "erlang-parsetools",
            "erlang-public-key",
            "erlang-tools",
            "erlang-syntax-tools",
            "erlang-eldap",
            "erlang-os-mon",
            "erlang-ssh",
            "erlang-xmerl",
            "git",
            "gcc",
            "g++",
            "libc6-dev",
            "linux-libc-dev",
            "cmake",
            "libmagic-dev",
        ]
    )
    res = download_and_unpack(
        "https://github.com/elixir-lang/elixir/releases/download/v1.14.5/elixir-otp-23.zip",
        "d45dc33a0c4e007a4f85719d23d2abcac8a33742fb042a1499c411b847462874",
    )
    elixir_bin_path = Path(res["dir_name"]).joinpath("bin")

    # Taken from https://git.pleroma.social/pleroma/pleroma/-/releases/v2.5.2
    res = download_and_unpack(
        "https://git.pleroma.social/pleroma/pleroma/archive/v2.5.2.zip",
        "ab1d01f1c4014e99c3a33cfe8f2ce7150c1549cc8913d78a9b8f9a530a3e807f",
    )
    new_source = res["changed"]
    pleroma_source_dir = Path(res["dir_name"]).joinpath("pleroma-v2.5.2")

    mix_env = {"MIX_ENV": "prod", "PATH": elixir_bin_path.as_posix()}
    new_prod_secret = set_file_contents(
        pleroma_source_dir.joinpath("config", "prod.secret.exs"), "import Config"
    )
    run_with_marker(
        "/opt/pleroma-mix-hex",
        "mix local.hex --force",
        directory=pleroma_source_dir,
        env=mix_env,
        force_build=new_source,
    )
    run_with_marker(
        "/opt/pleroma-mix-rebar",
        "mix local.rebar --force",
        directory=pleroma_source_dir,
        env=mix_env,
        force_build=new_source,
    )
    run_with_marker(
        "/opt/pleroma-mix-deps",
        "mix deps.get --only prod",
        directory=pleroma_source_dir,
        env=mix_env,
        force_build=new_source,
    )
    run_with_marker(
        "/opt/pleroma-mix-compile",
        "mix compile",
        directory=pleroma_source_dir,
        env=mix_env,
        force_build=new_source,
        deps=["/opt/pleroma-mix-deps"],
    )
    make_directory(pleroma_source_dir.joinpath("release"))
    release_changed = run_with_marker(
        "/opt/pleroma-release",
        "mix release --path release",
        directory=pleroma_source_dir,
        env=mix_env,
        force_build=new_source or new_prod_secret,
        deps=["/opt/pleroma-mix-compile"],
    )

    if release_changed:
        run_command(f"cp -R {pleroma_source_dir}/release/* /opt/pleroma")
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

    hostname = cast(str, LOCAL["PLEROMA_HOST"])
    certs_data = certs.get_certs([hostname])

    apt_install(["nginx"])

    nginx_changes = set_file_contents_from_template(
        "/etc/nginx/sites-available/pleroma.conf",
        "pleroma.nginx.j2",
        PLEROMA_HOST=LOCAL["PLEROMA_HOST"],
        DUMMY_CERTS=certs.get_dummy_certs(),
        FULLCHAIN_CERT=certs_data[f"fullchain-{hostname}"],
        PRIVKEY_CERT=certs_data[f"privkey-{hostname}"],
        SSL_OPTIONS=certs_data["ssl-options"],
    )

    nginx_changes = (
        are_deps_younger(
            "/etc/nginx/sites-available/pleroma.conf",
            [
                certs_data[f"fullchain-{hostname}"],
                certs_data[f"privkey-{hostname}"],
                certs_data["ssl-options"],
            ],
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
