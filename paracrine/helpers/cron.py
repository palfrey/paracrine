import json
import pathlib
from typing import Optional

from .config import config_path, get_config_file
from .fs import set_file_contents, set_file_contents_from_template

mailto: Optional[str] = None
mailfrom: Optional[str] = None


def local():
    global mailto, mailfrom
    cron_path = pathlib.Path(config_path()).joinpath("cron-info")
    set_file_contents(
        cron_path,
        json.dumps(
            {"mailto": mailto, "mailfrom": mailfrom},
            indent=2,
        ),
    )


def set_mailto(email: str) -> None:
    global mailto
    mailto = email


def set_mailfrom(email: str) -> None:
    global mailfrom
    mailfrom = email


def create_cron(name: str, schedule: str, user: str, command: str):
    cron_info = json.loads(get_config_file("configs/cron-info"))
    envs = {}
    if cron_info["mailto"] is not None:
        envs["MAILTO"] = cron_info["mailto"]
    if cron_info["mailfrom"] is not None:
        envs["MAILFROM"] = cron_info["mailfrom"]
    set_file_contents_from_template(
        f"/etc/cron.d/{name}",
        "cron.j2",
        SCHEDULE=schedule,
        USER=user,
        COMMAND=command,
        ENVS=envs,
    )
