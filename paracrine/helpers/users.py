from typing import Dict, List, Optional

from paracrine import Pathy

from .config import other_self_config
from .fs import run_command


def users(force_load: bool = False) -> List[str]:
    if not force_load:
        try:
            return other_self_config()["users"]
        except KeyError:
            pass

    raw_users = run_command("getent passwd | cut -d: -f1", dry_run_safe=True)
    return sorted(raw_users.strip().split("\n"))


def adduser(name: str, home_dir: Optional[Pathy] = None) -> bool:
    if name not in users():
        extra = ""
        if home_dir is not None:
            extra += f"--home-dir {home_dir} --create-home"
        run_command(f"useradd {name} {extra}")
        return True
    else:
        return False


def groups() -> Dict[str, List[str]]:
    raw_groups: str = other_self_config()["groups"]

    ret: Dict[str, List[str]] = {}
    for line in raw_groups.split("\n"):
        if line == "":
            continue
        bits = line.split(":")
        if len(bits) < 3:
            raise Exception((line, bits))
        ret[bits[0]] = bits[3].split(",")

    return ret


def add_user_to_group(user: str, group: str) -> bool:
    existing_groups = groups()
    existing_group = existing_groups[group]
    if user not in existing_group:
        run_command("usermod -aG %s %s" % (group, user))
        return True
    else:
        return False


def in_vagrant():
    return "vagrant" in users()
