import json
import logging
import os
from typing import Any, Callable, Dict

from mergedeep import merge
from mitogen.core import Error, StreamError
from mitogen.parent import Context, Router
from mitogen.utils import run_with_router

from .deps import (
    Modules,
    TransmitModules,
    makereal,
    maketransmit,
    maketransmit_single,
    runfunc,
)
from .helpers.config import (
    create_data,
    get_config,
    other_config_file,
    path_to_config_file,
    set_config,
    set_data,
)
from .helpers.fs import set_file_contents
from .runners import core


def decode(info):
    for k in list(info.keys()):
        if type(k) == bytes:
            info[k.decode()] = info[k].decode()
            del info[k]


ssh_cache: Dict[str, Context] = {}


def main(router: Router, func: Callable[..., None], *args: Any, **kwargs: Any) -> Dict:
    config = get_config()
    calls = []
    wg = core.is_wireguard()
    data = None
    for server in config["servers"]:
        assert isinstance(server, Dict)
        hostname = server["wireguard_ip"] if wg else server["ssh_hostname"]
        port = 22 if wg else server.get("ssh_port", 22)
        cache_key = f"{hostname}-{port}"
        if cache_key not in ssh_cache:
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
            ssh_cache[cache_key] = sudo
        data = create_data(server=server)
        calls.append(ssh_cache[cache_key].call_async(func, data, *args, **kwargs))

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
    for module in modules:
        runfunc([module], local_func)
        infos = main(router, do, maketransmit([module]), run_func)
        for info in infos["infos"]:
            runfunc([module], parse_func, info, infos["data"])
            for module_name in info:
                for per_node in info[module_name]:
                    if not isinstance(per_node, Dict):
                        continue
                    if "selector" not in per_node:
                        continue
                    config_path = other_config_file("selectors.json")
                    if os.path.exists(config_path):
                        selector_config = json.load(open(config_path))
                    else:
                        selector_config = {}
                    merge(selector_config, per_node["selector"])
                    selector_config = dict(sorted(selector_config.items()))
                    set_file_contents(
                        config_path, json.dumps(selector_config, indent=2)
                    )


def generate_dependencies(modules: Modules):
    tree = {}
    mapping = {}
    checked = []
    needs_dependencies = list(modules) + [core]
    modules = []
    while len(needs_dependencies) > 0:
        check = needs_dependencies.pop()
        checked.append(check)
        key = str(maketransmit_single(check))
        tree[key] = []
        mapping[key] = check
        new_dependencies = runfunc([check], "dependencies")
        for item in new_dependencies.values():
            for new_dependency in item[0]:
                tree[key].append(new_dependency)
                if new_dependency in needs_dependencies or new_dependency in checked:
                    continue
                needs_dependencies.append(new_dependency)

    count = 0
    while len(checked) > 0:
        count += 1
        if count == 100:
            raise Exception((modules, checked))
        for key, value in tree.items():
            mapped = mapping[key]
            if mapped in modules:
                continue
            for dep in value:
                if dep not in modules:
                    break
            else:
                modules.append(mapped)
                checked.remove(mapped)

    return modules


def run(inventory_path: str, modules: Modules):
    logging.basicConfig()
    logging.root.setLevel(logging.INFO)
    set_config(inventory_path)

    modules = generate_dependencies(modules)

    print("Running:")
    for module in maketransmit(modules):
        print(f"* {module}")
    print("")

    run_with_router(internal_runner, modules, "local", "run", "parse_return")
