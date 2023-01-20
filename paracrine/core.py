import os
from typing import Any, Callable
import mitogen
from mitogen.core import StreamError
from mitogen.parent import Router

from .users import users

from .config import config, create_data, get_config, host, path_to_config_file


def in_vagrant():
    return "vagrant" in users()


def is_wireguard():
    return os.path.exists("/etc/wireguard")


def decode(info):
    for k in list(info.keys()):
        if type(k) == bytes:
            info[k.decode()] = info[k].decode()
            del info[k]


def run(func: Callable, *args: Any, **kwargs: Any) -> Any:
    mitogen.utils.log_to_file()
    return mitogen.utils.run_with_router(func)


def main(router: Router, func: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    config = get_config()
    calls = []
    wg = is_wireguard()
    for server in config["servers"]:
        try:
            connect = router.ssh(
                hostname=server["wireguard_ip"] if wg else server["ssh_hostname"],
                port=22 if wg else server["ssh_port"],
                username=server["ssh_user"],
                identity_file=path_to_config_file(server["ssh_key"]),
                check_host_keys="accept",
                python_path="python3",
            )
        except StreamError:
            print(
                "Exception while trying to login to %s@%s:%s"
                % (server["ssh_user"], server["ssh_hostname"], server["ssh_port"])
            )
            raise

        sudo = router.sudo(via=connect, python_path="python3")
        calls.append(sudo.call_async(func, create_data(server=server), *args, **kwargs))

    infos = []
    errors = []
    for call in calls:
        try:
            info = call.get().unpickle()
            if info is not None:
                decode(info)
            infos.append(info)
        except mitogen.core.Error as e:
            print("Got error", e)
            errors.append(e)

    if len(errors) > 0:
        raise Exception(errors)

    return infos


def hash_fn(key: str, count: int) -> int:
    return sum(bytearray(key.encode("utf-8"))) % count


# Use this host for a given service
# Intended for "run on one machine" things
def use_this_host(name: str) -> bool:
    hosts = [h["name"] for h in config()["servers"]]
    index = hash_fn(name, len(hosts))
    return host()["name"] == hosts[index]
