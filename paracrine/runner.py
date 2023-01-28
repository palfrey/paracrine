import logging
import os
from typing import Any, Callable, Dict

from mitogen.core import Error, StreamError
from mitogen.parent import Router
from mitogen.utils import run_with_router

from . import core
from .config import create_data, get_config, path_to_config_file, set_config, set_data
from .deps import Modules, TransmitModules, makereal, maketransmit, runfunc


def decode(info):
    for k in list(info.keys()):
        if type(k) == bytes:
            info[k.decode()] = info[k].decode()
            del info[k]


def main(router: Router, func: Callable[..., None], *args: Any, **kwargs: Any) -> Dict:
    config = get_config()
    calls = []
    wg = core.is_wireguard()
    data = None
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
        data = create_data(server=server)
        calls.append(sudo.call_async(func, data, *args, **kwargs))

    infos = []
    errors = []
    for call in calls:
        try:
            info = call.get().unpickle()
            if info is not None:
                decode(info)
            infos.append(info)
        except Error as e:
            print("Got error", e)
            errors.append(e)

    if len(errors) > 0:
        raise Exception(errors)

    return {"infos": infos, "data": data}


def do(data, transmitmodules: TransmitModules, name: str):
    set_data(data)
    modules = makereal(transmitmodules)
    return runfunc(modules, name)


def internal_runner(
    router: Router, modules: Modules, local_func: str, run_func: str, parse_func: str
) -> None:
    runfunc(modules, local_func)
    infos = main(router, do, maketransmit(modules), run_func)
    for info in infos["infos"]:
        runfunc(modules, parse_func, info, infos["data"])


def run(inventory_path: str, modules: Modules):
    logging.basicConfig()
    logging.root.setLevel(logging.INFO)
    set_config(inventory_path)

    modules.insert(0, core)
    needs_dependencies = list(modules)
    while len(needs_dependencies) > 0:
        new_dependencies = runfunc(needs_dependencies, "dependencies")
        needs_dependencies = []
        for item in new_dependencies.values():
            for new_dependency in item:
                if new_dependency in modules:
                    continue
                modules.insert(0, new_dependency)
                needs_dependencies.append(new_dependency)

    print("Running:")
    for module in maketransmit(modules):
        print(f"* {module}")
    print("")

    run_with_router(
        internal_runner,
        modules,
        "bootstrap_local",
        "bootstrap_run",
        "bootstrap_parse_return",
    )
    run_with_router(
        internal_runner, modules, "core_local", "core_run", "core_parse_return"
    )
