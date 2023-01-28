import logging
import os
from typing import Any, Callable, Dict

import mitogen.utils
from mitogen.core import StreamError
from mitogen.parent import Router

from . import core
from .config import create_data, get_config, path_to_config_file, set_config, set_data
from .deps import Modules, TransmitModules, makereal, maketransmit, runfunc


def run(func: Callable, *args: Any, **kwargs: Any) -> Any:
    return mitogen.utils.run_with_router(func, *args, **kwargs)


def decode(info):
    for k in list(info.keys()):
        if type(k) == bytes:
            info[k.decode()] = info[k].decode()
            del info[k]


def main(router: Router, func: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    config = get_config()
    calls = []
    wg = core.is_wireguard()
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


def do(data, transmitmodules: TransmitModules, name: str):
    set_data(data)
    modules = makereal(transmitmodules)
    for module in modules:
        print("remote", module)
    return runfunc(modules, name)


def internal_runner(
    router: Router, modules: Modules, local_func: str, run_func: str, parse_func: str
) -> None:
    runfunc(modules, local_func)
    for info in main(router, do, maketransmit(modules), run_func):
        runfunc(modules, parse_func, info)


def everything(inventory_path: str, modules: Modules):
    logging.basicConfig()
    logging.root.setLevel(logging.INFO)

    modules.append(core)
    for module in modules:
        print("local", module)

    set_config(inventory_path)
    run(
        internal_runner,
        modules,
        "bootstrap_local",
        "bootstrap_run",
        "bootstrap_parse_return",
    )
    run(internal_runner, modules, "core_local", "core_run", "core_parse_return")
