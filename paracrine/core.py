import os
from typing import Any, Callable, Dict

import mitogen.utils
from mitogen.core import StreamError
from mitogen.parent import Router

from .config import config, create_data, get_config, host, path_to_config_file


def is_wireguard():
    return os.path.exists("/etc/wireguard")


def decode(info):
    for k in list(info.keys()):
        if type(k) == bytes:
            info[k.decode()] = info[k].decode()
            del info[k]


def run(func: Callable, *args: Any, **kwargs: Any) -> Any:
    return mitogen.utils.run_with_router(func, *args, **kwargs)


def main(router: Router, func: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    config = get_config()
    calls = []
    wg = is_wireguard()
    for server in config["servers"]:
        assert isinstance(server, Dict)
        hostname = server["wireguard_ip"] if wg else server["ssh_hostname"]
        port = 22 if wg else server.get("ssh_port", 22)
        key_path = path_to_config_file(server["ssh_key"])
        if not os.path.exists(key_path):
            raise Exception(f"Can't find ssh key {key_path}")
        try:
            connect = router.ssh(
                hostname=hostname,
                port=port,
                username=server["ssh_user"],
                identity_file=key_path,
                check_host_keys="accept",
                python_path="python3",
            )
        except StreamError:
            print(
                "Exception while trying to login to %s@%s:%s"
                % (server["ssh_user"], hostname, port)
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
