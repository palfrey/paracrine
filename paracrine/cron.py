from typing import Optional

from .fs import set_file_contents_from_template

mailto: Optional[str] = None
mailfrom: Optional[str] = None


def set_mailto(email: str) -> None:
    global mailto
    mailto = email


def set_mailfrom(email: str) -> None:
    global mailfrom
    mailfrom = email


def create_cron(name: str, schedule: str, user: str, command: str):
    global mailto, mailfrom
    envs = {}
    if mailto is not None:
        envs["MAILTO"] = mailto
    if mailto is not None:
        envs["MAILFROM"] = mailfrom
    set_file_contents_from_template(
        f"/etc/cron.d/{name}",
        "cron.j2",
        SCHEDULE=schedule,
        USER=user,
        COMMAND=command,
        ENVS=envs,
    )
