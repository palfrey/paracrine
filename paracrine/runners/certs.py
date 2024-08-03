import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Union, cast

from paracrine import dry_run_safe_read

from ..deps import Modules
from ..helpers import cron
from ..helpers.config import build_config, core_config, local_config, other_config_file
from ..helpers.debian import apt_install
from ..helpers.fs import (
    make_directory,
    run_command,
    run_with_marker,
    set_file_contents,
    set_file_contents_from_template,
)
from ..helpers.python import setup_venv
from . import aws
from .core import use_this_host

options: Dict[str, Any] = {}


# Are we in a test config where we should just not get the cert
def get_dummy_certs() -> bool:
    try:
        config = local_config()
    except FileNotFoundError:
        config = core_config()
    dummy_certs = config.get("dummy_certs")
    if dummy_certs is not None:
        return dummy_certs

    env = build_config(config)
    return cast(bool, env.get("DUMMY_CERTS", False))


def certbot_for_host(hostname: Union[str, List[str]], email: str) -> Dict[str, object]:
    if isinstance(hostname, str):
        hostnames = [hostname]
    else:
        hostnames = hostname
    certbot = Path("/opt/certbot")
    cert_name = "_".join(hostnames)
    live_path = certbot.joinpath("config", "live", cert_name)

    dummy_certs = get_dummy_certs()

    if use_this_host("certbot"):
        venv = certbot.joinpath("venv")
        venv_bin = venv.joinpath("bin")
        pip = venv_bin.joinpath("pip")
        certbot_bin = venv_bin.joinpath("certbot")

        fullchain_path = live_path.joinpath("fullchain.pem")
        envs = aws.get_env_with_creds()
        renew_command = f"{envs} {certbot_bin} renew \
                        --cert-name={cert_name} \
                        --config-dir={certbot.joinpath('config')} \
                        --work-dir={certbot.joinpath('workdir')} \
                        --logs-dir={certbot.joinpath('logs')} \
                        --dns-route53 \
                        --no-random-sleep-on-renew"
        while renew_command.find("  ") != -1:
            renew_command = renew_command.replace("  ", " ")
        make_directory(live_path)
        make_directory(certbot)
        setup_venv(venv)
        set_file_contents_from_template(
            "/opt/certbot/requirements.txt", "certbot_requirements.txt"
        )
        run_with_marker(
            "/opt/certbot/deps_installed",
            f"{pip} install -r /opt/certbot/requirements.txt",
            deps=["/opt/certbot/requirements.txt"],
        )
        config_path = certbot.joinpath(f"config/renewal/{cert_name}.conf")

        if not config_path.exists():
            if dummy_certs:
                set_file_contents(fullchain_path, "")
                set_file_contents(live_path.joinpath("privkey.pem"), "")
            else:
                run_command(
                    f"{envs} {certbot_bin} certonly \
                        --config-dir={certbot.joinpath('config')} \
                        --work-dir={certbot.joinpath('workdir')} \
                        --logs-dir={certbot.joinpath('logs')} \
                        --cert-name={cert_name} \
                        -m {email} --agree-tos --non-interactive \
                        --no-eff-email --domains {','.join(hostnames)} --dns-route53"
                )
        else:
            if not dummy_certs:
                run_with_marker(
                    f"/opt/certbot/renew_marker_{cert_name}",
                    renew_command,
                    max_age=timedelta(days=1),
                )

        apt_install(["moreutils"])
        cron.create_cron(
            f"certs-renew-{hostnames[0]}",
            "0 3 * * *",
            "root",
            f"chronic {renew_command}",
        )

        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        return {
            f"fullchain-{hostnames[0]}": dry_run_safe_read(
                fullchain_path, "dummy fullchain"
            ),
            f"privkey-{hostnames[0]}": dry_run_safe_read(
                live_path.joinpath("privkey.pem"), "dummy privkey"
            ),
            "ssl-options": dry_run_safe_read(
                venv.joinpath(
                    f"lib/python{python_version}/site-packages/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"  # noqa: E501
                ),
                "fake ssl options",
            ),
        }
    else:
        return {}


def dependencies() -> Modules:
    return [aws, cron]


def run() -> Dict[str, object]:
    return certbot_for_host(options["hostname"], options["email"])


def parse_return(
    infos: List[Dict[str, str]],
) -> None:
    for info in infos:
        for key in info:
            if key == "selector":
                continue
            open(other_config_file(key), "w").write(info[key])
