import subprocess
import sys
from typing import Optional

from ..helpers.config import ServerDict, get_config, path_to_config_file, set_config


def ssh_server(server: ServerDict, run: str = "", as_root: bool = False):
    if run != "" and as_root and server["ssh_user"] != "root":
        run = f"sudo {run}"
    command = f"ssh {server['ssh_user']}@{server['ssh_hostname']} \
        -i {path_to_config_file(server['ssh_key'])} \
        -p {server['ssh_port']} \
        -o StrictHostKeyChecking=no \
        {run}"
    while command.find("  ") != -1:
        command = command.replace("  ", " ")
    print(command)
    subprocess.check_call(command.split(" "))


def ssh(run: str = "", index: Optional[int] = None, as_root: bool = False):
    set_config(sys.argv[1])

    if index is not None:
        server = get_config()["servers"][index]
        ssh_server(server, run, as_root)
    else:
        for server in get_config()["servers"]:
            ssh_server(server, run, as_root)


if __name__ == "__main__":
    index = int(sys.argv[2])
    ssh(index=index)
