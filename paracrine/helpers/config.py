import json
import os
import pathlib
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, cast

import jinja2
import yaml
from mergedeep import merge
from typing_extensions import NotRequired, TypedDict

from paracrine import is_dry_run


class ServerDict(TypedDict):
    name: str
    count: int
    ssh_hostname: str
    ssh_port: int
    ssh_key: str
    ssh_user: str
    wireguard_ip: NotRequired[str]


class InventoryDict(TypedDict):
    environment: str
    data_path: str
    servers: List[ServerDict]


class ConfigDict(TypedDict):
    environments: Dict[str, object]
    common: NotRequired[Dict[str, object]]


_jinja_env = None
data = None

CONFIG_NAME = "config.yaml"


def jinja_env():
    assert _jinja_env is not None, "Need to run set_data first!"
    return _jinja_env


class Host(TypedDict):
    name: str
    wireguard_ip: NotRequired[str]


def host() -> Host:
    assert data is not None
    return data["host"]


def config() -> InventoryDict:
    assert data is not None
    return data["config"]


def data_files():
    assert data is not None
    return data["data"]


def get_config_keys():
    assert data is not None
    return data["configs"].keys()


def get_config_file(fname: str) -> str:
    if fname not in get_config_keys():
        raise KeyError(f"Can't find {fname}. We have: {sorted(get_config_keys())}")

    assert data is not None
    return data["configs"][fname]


def core_config():
    return yaml.safe_load(get_config_file(CONFIG_NAME))


def set_data(new_data: Mapping[str, Any]) -> None:
    loader = jinja2.DictLoader(new_data["templates"])
    global _jinja_env, data
    _jinja_env = jinja2.Environment(
        loader=loader, undefined=jinja2.StrictUndefined, keep_trailing_newline=True
    )
    data = new_data


return_data: Dict[str, object] = {}


def clear_return_data() -> None:
    global return_data
    return_data = {}


def add_return_data(new_data: Dict[str, Any]) -> None:
    global return_data
    merge(return_data, new_data)


def get_return_data() -> Dict[str, object]:
    global return_data
    return return_data


def add_folder_to_config(
    configs: Dict[str, str],
    folder: str,
    shortname: Optional[str] = None,
    filter: Optional[Callable[[str], bool]] = None,
    prefix: str = "",
):
    if not os.path.exists(folder):
        print("Skipping %s from config as doesn't exist" % folder)
        return
    for f in os.listdir(folder):
        if filter is not None:
            if not filter(f):
                continue
        if shortname is not None:
            key = os.path.join(shortname, f)
            full = os.path.join(folder, f)
        else:
            full = key = os.path.join(folder, f)
        if os.path.isfile(full):
            if prefix != "":
                if "/" in key:
                    parts = key.split("/")
                    key = "/".join(parts[:-1]) + "/" + prefix + parts[-1]
                else:
                    key = prefix + key
            configs[key] = open(full).read()
        else:
            if prefix != "":
                prefix += "/"
            add_folder_to_config(
                configs,
                full,
                shortname=shortname,
                filter=filter,
                prefix=prefix + f + "/",
            )


inventory: Optional[InventoryDict] = None
inventory_directory: Optional[str] = None


def set_config(inventory_path: str) -> None:
    global inventory, inventory_directory
    inventory_directory = os.path.dirname(inventory_path)
    inventory = yaml.safe_load(open(inventory_path))


# Only for tests
def _clear_config() -> None:  # pyright: ignore[reportUnusedFunction]
    global inventory, inventory_directory
    inventory = None
    inventory_directory = None


def get_config() -> InventoryDict:
    if inventory is None:
        assert data is not None
        return data["inventory"]
    return inventory


def config_path(shortname: bool = False) -> str:
    if inventory is None or shortname:
        return "configs"
    else:
        dp = data_path()
        assert dp is not None
        return os.path.join(dp, "configs")


def path_to_config_file(name: str) -> pathlib.Path:
    if name.find("~") != -1:
        return pathlib.Path(name).expanduser()
    return pathlib.Path(config_path()).joinpath(name)


def data_path():
    if inventory is None:
        return None
    assert inventory_directory is not None
    return os.path.join(inventory_directory, inventory["data_path"])


def environment():
    if inventory is None:
        assert data is not None
        return data["environment"]
    return inventory["environment"]


def servers() -> List[ServerDict]:
    try:
        return get_config()["servers"]
    except NotADirectoryError:
        return core_config()["servers"]


def walk(path: pathlib.Path) -> Iterator[pathlib.Path]:
    for p in pathlib.Path(path).iterdir():
        if p.is_dir():
            yield from walk(p)
            continue
        yield p.resolve()


def create_data(server: Optional[ServerDict] = None):
    config = get_config()
    templates = {}
    template_paths = [
        pathlib.Path("templates"),
        pathlib.Path(__file__).parent.parent.joinpath("templates"),
    ]
    for template_path in template_paths:
        if not template_path.exists():
            continue
        for path in walk(template_path):
            templates[path.name] = path.open("r").read()

    data = {}
    data_paths = [
        pathlib.Path("data"),
        pathlib.Path(__file__).parent.joinpath("data"),
    ]
    for data_path in data_paths:
        if not data_path.exists():
            continue
        data_path = data_path.absolute()
        for path in walk(data_path):
            try:
                local_path = path.relative_to(data_path).as_posix()
            except ValueError:
                # Symlink outside of local folder
                continue
            data[local_path] = path.open("rb").read()

    configs = {
        CONFIG_NAME: open(CONFIG_NAME).read(),
    }
    add_folder_to_config(
        configs,
        config_path(),
        shortname="configs",
        filter=lambda f: not f.startswith("."),
    )

    return {
        "templates": templates,
        "host": server,
        "config": config,
        "configs": configs,
        "environment": environment(),
        "inventory": get_config(),
        "data": data,
    }


def network_config_file(name: str, shortname: bool = False) -> str:
    return config_path(shortname) + "/networks-{name}".format(name=name)


def network_config(name: str) -> Any:
    try:
        return json.loads(get_config_file(network_config_file(name, shortname=True)))
    except KeyError:
        if not is_dry_run():
            raise
        return {}


def other_config_file(name: str, shortname: bool = False) -> str:
    return config_path(shortname) + "/other-{name}".format(name=name)


def other_config(name: str) -> Any:
    return json.loads(get_config_file(other_config_file(name, shortname=True)))


def other_self_config():
    return other_config(host()["name"])


def build_config(config: ConfigDict) -> Dict[str, object]:
    env = environment()
    LOCAL = cast(Dict[str, object], config["environments"][env])
    common = config.get("common", {})
    ret = cast(Dict[str, object], dict(**common))
    ret.update(LOCAL)
    return ret


def local_config() -> ConfigDict:
    return yaml.safe_load(open(CONFIG_NAME).read())


def local_server():
    local_hostname = host()["name"]
    for server in servers():
        name = server["name"]
        if name == local_hostname:
            return server

    raise Exception(f"Cannot find {local_hostname}")


def in_docker() -> bool:
    return os.path.exists("/.dockerenv")


def in_local() -> bool:
    return os.path.exists(CONFIG_NAME)
