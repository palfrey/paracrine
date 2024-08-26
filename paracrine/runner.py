import argparse
import json
import logging
import os
from typing import Any, Callable, Dict, List, Mapping, TypedDict, Union, cast

from mergedeep import merge
from mitogen.core import Error, Receiver, StreamError
from mitogen.parent import Context, EofError, Router
from mitogen.ssh import HostKeyError
from mitogen.utils import run_with_router
from retry.api import retry_call

from paracrine import DRY_RUN_ENV

from .deps import (
    Module,
    Modules,
    TransmitModule,
    TransmitModules,
    freeze_module,
    makereal,
    maketransmit,
    maketransmit_single,
    runfunc,
    unfreeze_module,
)
from .helpers.config import (
    ServerDict,
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
    router: Router,
    servers: Union[list[str], None],
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> MainReturn:
    config = get_config()
    calls: List[Receiver] = []
    wg = core.is_wireguard()
    data = {}
    for server in config["servers"]:
        if servers is not None and server["name"] not in servers:
            continue
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
            except HostKeyError:
                print(
                    f"HostKeyError while trying to login to to {username}@{hostname}:{port}. Try running the following manually: ssh {username}@{hostname} -p {port} -i {key_path}"
                )
                raise
            except StreamError:
                print(
                    f"Exception while trying to login to {username}@{hostname}:{port}"
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
    servers: list[str],
    modules: Modules,
    local_func: str,
    run_func: str,
    parse_func: str,
    dry_run: bool,
) -> None:
    for module in modules:
        runfunc([module], local_func)
        infos = main(router, servers, do, maketransmit([module]), run_func, dry_run)
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
        check = freeze_module(needs_dependencies.pop())
        checked.append(check)
        key = str(maketransmit_single(check))
        tree[key] = []
        mapping[key] = check
        new_dependencies = cast(
            Dict[str, List[Modules]], runfunc([check], "dependencies")
        )
        for item in new_dependencies.values():
            for new_dependency in item[0]:
                new_dependency = freeze_module(new_dependency)
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


SERVER_FILTER = Callable[[ServerDict], bool]

ALL_SERVERS: SERVER_FILTER = lambda _: True


def server_name_filter(name: str) -> SERVER_FILTER:
    return lambda server: server["name"] == name


def server_not_name_filter(name: str) -> SERVER_FILTER:
    return lambda server: server["name"] != name


def server_role_picker(name: str) -> SERVER_FILTER:
    def inner(server: ServerDict) -> bool:
        picked_server = core._index_fn(name)  # pyright: ignore[reportPrivateUsage]
        return picked_server == server

    return inner


def run(
    args: List[str],
    modules: Union[Modules, dict[Callable[[ServerDict], bool], Modules]],
):
    logging.basicConfig()
    logging.root.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(prog="paracrine")
    parser.add_argument("-i", "--inventory-path", dest="inventory_path", required=True)
    parser.add_argument("-a", "--apply", default=False, action="store_true")
    parsed_args = parser.parse_args(args)
    set_config(parsed_args.inventory_path)

    all_servers = get_config()["servers"]

    if isinstance(modules, dict):
        module_mapping = dict(
            [(k, generate_dependencies(v)) for (k, v) in modules.items()]
        )
        all_modules: Modules = []
        for modules in module_mapping.values():
            for module in modules:
                if module not in all_modules:
                    all_modules.append(module)
    else:
        all_modules = generate_dependencies(modules)
        module_mapping = {ALL_SERVERS: all_modules}

    module_descriptions = dict(
        [(module, maketransmit_single(module)) for module in all_modules]
    )

    all_server_names = set([server["name"] for server in all_servers])
    server_modules: dict[str, list[TransmitModule]] = dict(
        [(name, []) for name in all_server_names]
    )

    for server_filter, specific_modules in module_mapping.items():
        for server in all_servers:
            if not server_filter(server):
                continue
            server_modules[server["name"]].extend(
                [module_descriptions[module] for module in specific_modules]
            )

    modules_for_server: dict[TransmitModule, list[str]] = {}

    for server_name, specific_modules in server_modules.items():
        for module in specific_modules:
            if module not in modules_for_server:
                modules_for_server[module] = [server_name]
            else:
                modules_for_server[module].append(server_name)

    print("Running:")
    for module, module_name in module_descriptions.items():
        print(f"* {unfreeze_module(module_name)}", end="")
        servers = set(modules_for_server.get(module_name, []))
        if servers == all_server_names:
            print("")
        else:
            print(f" {list(servers)}")

    print("")

    def do_runs(router: Router) -> None:
        to_run_modules: list[Module] = []
        to_run_servers = []

        for module in all_modules:
            module_description = module_descriptions[module]
            if module_description not in modules_for_server:
                continue

            wanted_servers = sorted(set(modules_for_server[module_description]))
            if to_run_servers != [] and to_run_servers != wanted_servers:
                internal_runner(
                    router,
                    to_run_servers,
                    to_run_modules,
                    "local",
                    "run",
                    "parse_return",
                    not parsed_args.apply,
                )
                to_run_modules = []

            to_run_servers = wanted_servers
            to_run_modules.append(unfreeze_module(module))

        internal_runner(
            router,
            to_run_servers,
            to_run_modules,
            "local",
            "run",
            "parse_return",
            not parsed_args.apply,
        )

    run_with_router(do_runs)
