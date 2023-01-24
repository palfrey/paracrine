from datetime import timedelta
from pathlib import Path
from typing import Any, Dict

from mitogen.parent import Router

from .aws import set_aws_creds
from .config import core_config, other_config_file, set_data
from .core import main, use_this_host
from .fs import (
    make_directory,
    run_command,
    run_with_marker,
    set_file_contents_from_template,
)
from .python import setup_venv


# Are we in a test config where we should just not get the cert
def get_dummy_certs():
    config = core_config()
    return config.get("dummy_certs", False)


def certbot_for_host(hostname: str, email: str) -> None:
    certbot = Path("/opt/certbot")
    live_path = certbot.joinpath("config", "live", hostname)

    dummy_certs = get_dummy_certs()

    if use_this_host("certbot"):
        set_aws_creds()
        venv = certbot.joinpath("venv")
        venv_bin = venv.joinpath("bin")
        pip = venv_bin.joinpath("pip")
        certbot_bin = venv_bin.joinpath("certbot")

        fullchain_path = live_path.joinpath("fullchain.pem")
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
                        --no-eff-email --domains {hostname} --dns-route53"
                )
        else:
            if not dummy_certs:
                run_with_marker(
                    "/opt/certbot/renew_marker",
                    f"{certbot_bin} renew \
                        --config-dir={certbot.joinpath('config')} \
                        --work-dir={certbot.joinpath('workdir')} \
                        --logs-dir={certbot.joinpath('logs')} \
                        --dns-route53",
                    max_age=timedelta(days=1),
                )

        return {
            "fullchain": fullchain_path.open().read(),
            "privkey": live_path.joinpath("privkey.pem").open().read(),
            "ssl-options": venv.joinpath(
                "lib/python3.9/site-packages/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"  # noqa: E501
            )
            .open()
            .read(),
        }
    else:
        return {}


def do(data: Dict[str, Any], hostname: str, email: str) -> Dict:
    set_data(data)
    return certbot_for_host(hostname, email)


def core(router: Router, hostname: str, email: str) -> None:
    for info in main(router, do, hostname, email):
        for key in info:
            open(other_config_file(key), "w").write(info[key])
