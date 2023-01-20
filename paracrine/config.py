import os
import pathlib
from typing import Any, Dict

import jinja2


jinja_env = None
data = None


def host():
    return data["host"]


def config():
    return data["config"]


def configs(fname):
    try:
        return data["configs"][fname]
    except KeyError:
        print(sorted(data["configs"].keys()))
        raise


def set_data(new_data: Dict[str, Any]) -> None:
    loader = jinja2.DictLoader(new_data["templates"])
    global jinja_env, data
    jinja_env = jinja2.Environment(
        loader=loader, undefined=jinja2.StrictUndefined, keep_trailing_newline=True
    )
    data = new_data


def add_folder_to_config(configs, folder, shortname=None, filter=None):
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
        configs[key] = open(full).read()


inventory = None
inventory_directory = None


def set_config(inventory_path):
    import yaml

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


def path_to_config_file(name):
    if name.startswith("/"):
        return name
    return f"{config_path()}/{name}"


def data_path():
    if inventory is None:
        return None
    return os.path.join(inventory_directory, inventory["data_path"])


def environment():
    if inventory is None:
        return data["environment"]
    return inventory["environment"]


def create_data(server=None):
    config = get_config()
    templates = {}
    for root, dirs, files in os.walk("templates"):
        for f in files:
            templates[f] = open(os.path.join(root, f)).read()
    configs = {
        "config.yaml": open("config.yaml").read(),
    }
    add_folder_to_config(
        configs,
        config_path(),
        shortname="configs",
        filter=lambda f: f.startswith("wireguard-public")
        or f.startswith("networks-")
        or f.startswith("other-")
        or f.startswith("ssh-"),
    )
    add_folder_to_config(
        configs,
        pathlib.Path(data_path()).joinpath("ssl").as_posix(),
        shortname="ssl",
        filter=lambda f: f.endswith(".pem"),
    )

    return {
        "templates": templates,
        "host": server,
        "config": config,
        "configs": configs,
        "environment": environment(),
        "inventory": get_config(),
    }
