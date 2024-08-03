import json
import pathlib
import re
from typing import Dict, Optional

from paracrine import is_dry_run

from .config import config_path, get_config_file
from .fs import delete, set_file_contents, set_file_contents_from_template

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


def cron_path(name: str):
    # run-parts doesn't like some names
    run_parts_safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    return f"/etc/cron.d/{run_parts_safe_name}"


def create_cron(name: str, schedule: str, user: str, command: str):
    cron_info: Dict[str, str]
    try:
        cron_info = json.loads(get_config_file("configs/cron-info"))
    except KeyError:
        if not is_dry_run():
            raise
        cron_info = {}
    envs: Dict[str, str] = {}
    if cron_info.get("mailto") is not None:
        envs["MAILTO"] = cron_info["mailto"]
    if cron_info.get("mailfrom") is not None:
        envs["MAILFROM"] = cron_info["mailfrom"]
    set_file_contents_from_template(
        cron_path(name),
        "cron.j2",
        SCHEDULE=schedule,
        USER=user,
        COMMAND=command,
        ENVS=envs,
    )


def delete_cron(name: str):
    delete(cron_path(name))
