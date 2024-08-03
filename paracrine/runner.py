import argparse
import json
import logging
import os
from typing import Any, Callable, Dict, List, Mapping, TypedDict, Union, cast

from mergedeep import merge
from mitogen.core import Error, Receiver, StreamError
from mitogen.parent import Context, EofError, Router
from mitogen.utils import run_with_router
from retry.api import retry_call

from paracrine import DRY_RUN_ENV

from .deps import (
    Module,
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


def decode(info: Dict[Union[bytes, str], Union[bytes, str]]):
    for k in list(info.keys()):
        if isinstance(k, bytes):
            value = info[k]
            assert isinstance(value, bytes)
            info[k.decode()] = value.decode()
            del info[k]


ssh_cache: Dict[str, Context] = {}


def clear_ssh_cache():
    global ssh_cache
    ssh_cache = {}


class MainReturn(TypedDict):
    infos: List[Any]
    data: Mapping[str, object]


def main(
    router: Router, func: Callable[..., Any], *args: Any, **kwargs: Any
) -> MainReturn:
    config = get_config()
    calls: List[Receiver] = []
    wg = core.is_wireguard()
    data = {}
    for server in config["servers"]:
        assert isinstance(server, Dict)
        hostname = (
            server["wireguard_ip"]
            if wg and "wireguard_ip" in server
            else server["ssh_hostname"]
        )
        port = 22 if wg else server.get("ssh_port", 22)
        cache_key = f"{hostname}-{port}"
        if cache_key not in ssh_cache:
            key_path = path_to_config_file(server["ssh_key"]).resolve()
            if not os.path.exists(key_path):
                raise Exception(f"Can't find ssh key {key_path}")
            username = server["ssh_user"]

            try:
                connect = retry_call(
                    router.ssh,
                    exceptions=EofError,
                    tries=3,
                    fkwargs={
                        "hostname": hostname,
                        "port": port,
                        "username": username,
                        "identity_file": key_path,
                        "check_host_keys": "accept",
                        "python_path": "python3",
                        "ssh_args": ["-o", "SendEnv DUMP_COMMAND"],
                    },
                )
            except StreamError:
                print(
                    "Exception while trying to login to %s@%s:%s"
                    % (username, hostname, port)
                )
                raise

            if username != "root":
                sudo = router.sudo(
                    via=connect, python_path="python3", preserve_env=True
                )
                ssh_cache[cache_key] = sudo
            else:
                ssh_cache[cache_key] = connect
        data = create_data(server=server)
        calls.append(ssh_cache[cache_key].call_async(func, data, *args, **kwargs))

    infos: List[Any] = []
    errors: List[Exception] = []
    for call in calls:
        try:
            info = call.get().unpickle()
            if info is not None:
                assert isinstance(info, Dict)
                decode(cast(Dict[Union[str, bytes], Union[str, bytes]], info))
            infos.append(info)
        except Error as e:
            print("Got error", e)
            errors.append(e)

    if len(errors) > 0:
        raise Exception(errors)

    return {"infos": infos, "data": data}


def do(
    data: Dict[str, Any], transmitmodules: TransmitModules, name: str, dry_run: bool
):
    os.environ[DRY_RUN_ENV] = str(dry_run)
    set_data(data)
    modules = makereal(transmitmodules)
    return runfunc(modules, name)


def internal_runner(
    router: Router,
    modules: Modules,
    local_func: str,
    run_func: str,
    parse_func: str,
    dry_run: bool,
) -> None:
    for module in modules:
        runfunc([module], local_func)
        infos = main(router, do, maketransmit([module]), run_func, dry_run)
        for info in infos["infos"]:
            os.environ[DRY_RUN_ENV] = str(dry_run)
            runfunc([module], parse_func, info, infos["data"])
            for module_name in info:
                for per_node in info[module_name]:
                    if not isinstance(per_node, Dict):
                        continue
                    if "selector" not in per_node:
                        continue
                    config_path = other_config_file("selectors.json")
                    if os.path.exists(config_path):
                        selector_config: Dict[str, object] = json.load(
                            open(config_path)
                        )
                    else:
                        selector_config = {}
                    merge(
                        selector_config, cast(Dict[str, object], per_node["selector"])
                    )
                    selector_config = dict(sorted(selector_config.items()))
                    set_file_contents(
                        config_path, json.dumps(selector_config, indent=2)
                    )


def generate_dependencies(modules: Modules):
    tree: Dict[str, List[Module]] = {}
    mapping: Dict[str, Module] = {}
    checked: List[Module] = []
    needs_dependencies = list(modules) + [core]
    modules = []
    while len(needs_dependencies) > 0:
        check = needs_dependencies.pop()
        checked.append(check)
        key = str(maketransmit_single(check))
        tree[key] = []
        mapping[key] = check
        new_dependencies = cast(
            Dict[str, List[Modules]], runfunc([check], "dependencies")
        )
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


def run(args: List[str], modules: Modules):
    logging.basicConfig()
    logging.root.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(prog="paracrine")
    parser.add_argument("-i", "--inventory-path", dest="inventory_path", required=True)
    parser.add_argument("-a", "--apply", default=False, action="store_true")
    parsed_args = parser.parse_args(args)
    set_config(parsed_args.inventory_path)

    modules = generate_dependencies(modules)

    print("Running:")
    for module in maketransmit(modules):
        print(f"* {module}")
    print("")

    run_with_router(
        internal_runner, modules, "local", "run", "parse_return", not parsed_args.apply
    )
