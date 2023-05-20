from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Union

from ..deps import Modules
from ..helpers import cron
from ..helpers.config import core_config, other_config_file
from ..helpers.debian import apt_install
from ..helpers.fs import (
    make_directory,
    run_command,
    run_with_marker,
    set_file_contents_from_template,
)
from ..helpers.python import setup_venv
from . import aws
from .core import use_this_host

options = {}


# Are we in a test config where we should just not get the cert
def get_dummy_certs():
    config = core_config()
    return config.get("dummy_certs", False)


def certbot_for_host(hostname: Union[str, List[str]], email: str) -> Dict:
    if type(hostname) == str:
        hostnames = [hostname]
    else:
        hostnames = hostname
    certbot = Path("/opt/certbot")
    live_path = certbot.joinpath("config", "live", hostnames[0])

    dummy_certs = get_dummy_certs()

    if use_this_host("certbot"):
        aws.set_aws_creds()
        venv = certbot.joinpath("venv")
        venv_bin = venv.joinpath("bin")
        pip = venv_bin.joinpath("pip")
        certbot_bin = venv_bin.joinpath("certbot")

        fullchain_path = live_path.joinpath("fullchain.pem")
        renew_command = f"{certbot_bin} renew \
                        --config-dir={certbot.joinpath('config')} \
                        --work-dir={certbot.joinpath('workdir')} \
                        --logs-dir={certbot.joinpath('logs')} \
                        --dns-route53"
        while renew_command.find("  ") != -1:
            renew_command = renew_command.replace("  ", " ")
        if not fullchain_path.exists():
            make_directory(live_path)
            make_directory(certbot)
            setup_venv(venv)
            set_file_contents_from_template(
                "/opt/certbot/requirements.txt", "certbot_requirements.txt"
            )
            run_with_marker(
                "/opt/certbot/deps_installed",
                f"{pip} install -r /opt/certbot/requirements.txt",
            )

            if dummy_certs:
                fullchain_path.open("w").write("")
                live_path.joinpath("privkey.pem").open("w").write("")
            else:
                run_command(
                    f"{certbot_bin} certonly \
                        --config-dir={certbot.joinpath('config')} \
                        --work-dir={certbot.joinpath('workdir')} \
                        --logs-dir={certbot.joinpath('logs')} \
                        -m {email} --agree-tos --non-interactive \
                        --no-eff-email --domains {','.join(hostnames)} --dns-route53"
                )
        else:
            if not dummy_certs:
                run_with_marker(
                    "/opt/certbot/renew_marker",
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

        return {
            f"fullchain-{hostnames[0]}": fullchain_path.open().read(),
            f"privkey-{hostnames[0]}": live_path.joinpath("privkey.pem").open().read(),
            "ssl-options": venv.joinpath(
                "lib/python3.9/site-packages/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"  # noqa: E501
            )
            .open()
            .read(),
        }
    else:
        return {}


def dependencies() -> Modules:
    return [aws, cron]


def run() -> Dict:
    return certbot_for_host(options["hostname"], options["email"])


def parse_return(
    infos: List[Dict],
) -> None:
    for info in infos:
        for key in info:
            open(other_config_file(key), "w").write(info[key])
