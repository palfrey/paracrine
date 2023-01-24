#!/usr/bin/python3.9 -u

# FIXME: This is an immensely hacky script, mostly out of
# me not being able to either get https://github.com/gdraheim/docker-systemctl-replacement
# or the actual systemd to reliably work inside Docker
#
# It's one saving grace is that it's just about good enough to do the paracrine integration tests
# but should be replaced with something better at some point.

import configparser
import json
import subprocess
import time
from pathlib import Path
from sys import argv, exit
from typing import List

systemd_roots = [Path("/etc/systemd/system"), Path("/lib/systemd/system/")]


def get_enabled_services():
    services = []
    for systemd_root in systemd_roots:
        for path in systemd_root.iterdir():
            if path.suffix != ".service":
                continue
            services.append(path.stem)
    return services


_running_service_path = Path("/running_service.json")


def get_running_services() -> List[str]:
    try:
        return json.load(_running_service_path.open())
    except FileNotFoundError:
        return []


def add_running_service(service: str) -> None:
    existing = get_running_services()
    existing.append(service)
    with _running_service_path.open("w") as rs:
        json.dump(existing, rs)


if __name__ == "__main__":
    if len(argv) == 1:
        systemd_root = Path("/etc/systemd/system/multi-user.target.wants")
        for path in systemd_root.iterdir():
            name = path.stem
            print(f"Starting {name}")
            subprocess.check_call([f"/etc/init.d/{name}", "start"])
            add_running_service(name)

        print("sleeping")
        while True:
            time.sleep(1)

    args = argv[1:]
    if args[0] == "--quiet":
        args = args[1:]

    if args[0] == "show":
        service = args[1]
        if service in get_enabled_services():
            print("UnitFileState=enabled")
        else:
            print("UnitFileState=disabled")
        if service in get_running_services():
            print("SubState=running")
        else:
            print("SubState=dead")
    elif args[0] == "start":
        service = args[1]
        if service in get_running_services():
            exit(0)
        service_path = Path(f"/etc/init.d/{service}")
        if service_path.exists():
            args = ["nohup", service_path, "start"]
            print(args)
            subprocess.check_call(args)
        else:
            for systemd_root in systemd_roots:
                service_path = systemd_root.joinpath(f"{service}.service")
                if service_path.exists():
                    print(service_path)
                    config = configparser.ConfigParser()
                    config.read(service_path)
                    assert "Service" in config, config.keys()
                    assert "ExecStart" in config["Service"], config["Service"].keys()
                    cmd = config["Service"]["ExecStart"]
                    args = ["nohup"] + cmd.split(" ")
                    print(args)
                    subprocess.Popen(args, start_new_session=True)
        add_running_service(service)
    elif args[0] == "enable":
        service = args[1]
        args = ["update-rc.d", service, "enable", "2"]
        print(args)
        subprocess.check_call(args)
    elif args[0] == "daemon-reload":
        pass  # FIXME, do stuff
    elif args[0] == "reload":
        service = args[1]
        service_path = Path(f"/etc/init.d/{service}")
        if service_path.exists():
            subprocess.check_call([service_path, "reload"])
        else:
            raise Exception(service)
    else:
        raise Exception(argv)
