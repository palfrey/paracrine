import json
import os
import pathlib
from typing import Any, Dict, Optional

import jinja2
import yaml

_jinja_env = None
data = None

CONFIG_NAME = "config.yaml"


def jinja_env():
    assert _jinja_env is not None, "Need to run set_data first!"
    return _jinja_env


def host():
    return data["host"]


def config():
    return data["config"]


def data_files():
    return data["data"]


def get_config_keys():
    return data["configs"].keys()


def get_config_file(fname):
    if fname not in get_config_keys():
        raise KeyError(f"Can't find {fname}. We have: {sorted(get_config_keys())}")
    return data["configs"][fname]


def core_config():
    return yaml.safe_load(get_config_file(CONFIG_NAME))


def set_data(new_data: Dict[str, Any]) -> None:
    loader = jinja2.DictLoader(new_data["templates"])
    global _jinja_env, data
    _jinja_env = jinja2.Environment(
        loader=loader, undefined=jinja2.StrictUndefined, keep_trailing_newline=True
    )
    data = new_data


def add_folder_to_config(configs, folder, shortname=None, filter=None, prefix=""):
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


inventory = None
inventory_directory = None


def set_config(inventory_path):
    global inventory, inventory_directory
    inventory_directory = os.path.dirname(inventory_path)
    inventory = yaml.safe_load(open(inventory_path))


def get_config():
    if inventory is None:
        assert data is not None
        return data["inventory"]
    return inventory


def config_path(shortname=False):
    if inventory is None or shortname:
        return "configs"
    else:
        return os.path.join(data_path(), "configs")


def path_to_config_file(name: str) -> str:
    if name.find("~") != -1:
        return pathlib.Path(name).expanduser()
    return pathlib.Path(config_path()).joinpath(name)


def data_path():
    if inventory is None:
        return None
    return os.path.join(inventory_directory, inventory["data_path"])


def environment():
    if inventory is None:
        return data["environment"]
    return inventory["environment"]


def servers():
    try:
        return get_config()["servers"]
    except NotADirectoryError:
        return core_config()["servers"]


def walk(path):
    for p in pathlib.Path(path).iterdir():
        if p.is_dir():
            yield from walk(p)
            continue
        yield p.resolve()


def create_data(server: Optional[Dict] = None):
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
        "config.yaml": open("config.yaml").read(),
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


def network_config_file(name, shortname=False):
    return config_path(shortname) + "/networks-{name}".format(name=name)


def network_config(name):
    return json.loads(get_config_file(network_config_file(name, shortname=True)))


def other_config_file(name, shortname=False):
    return config_path(shortname) + "/other-{name}".format(name=name)


def other_config(name):
    return json.loads(get_config_file(other_config_file(name, shortname=True)))


def other_self_config():
    return other_config(host()["name"])


def build_config(config: Dict) -> Dict:
    env = environment()
    LOCAL = config["environments"][env]
    common = config.get("common", {})
    ret = dict(**common)
    ret.update(LOCAL)
    return ret


def local_config() -> Dict:
    return yaml.safe_load(open(CONFIG_NAME).read())


def local_server():
    local_hostname = host()["name"]
    for server in servers():
        name = server["name"]
        if name == local_hostname:
            return server

    raise Exception(f"Cannot find {local_hostname}")


def in_docker():
    return os.path.exists("/.dockerenv")
