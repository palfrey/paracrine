from .config import other_self_config
from .fs import run_command


def users(force_load=False):
    if not force_load:
        try:
            return other_self_config()["users"]
        except KeyError:
            pass

    raw_users = run_command("getent passwd | cut -d: -f1")
    return sorted(raw_users.strip().split("\n"))


def adduser(name, home_dir=None):
    if name not in users():
        extra = ""
        if home_dir is not None:
            extra += f"--home-dir {home_dir} --create-home"
        run_command(f"useradd {name} {extra}")
        return True
    else:
        return False


def groups():
    raw_groups = other_self_config()["groups"]

    ret = {}
    for line in raw_groups.split("\n"):
        if line == "":
            continue
        bits = line.split(":")
        if len(bits) < 3:
            raise Exception((line, bits))
        ret[bits[0]] = bits[3].split(",")

    return ret


def add_user_to_group(user, group):
    existing_groups = groups()
    existing_group = existing_groups[group]
    if user not in existing_group:
        run_command("usermod -aG %s %s" % (group, user))
        return True
    else:
        return False
