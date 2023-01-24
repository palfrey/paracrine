import subprocess
import sys

from .config import get_config, path_to_config_file, set_config


def ssh_server(server, run=""):
    command = f"ssh {server['ssh_user']}@{server['ssh_hostname']} \
        -i {path_to_config_file(server['ssh_key'])} \
        -p {server['ssh_port']} \
        -o StrictHostKeyChecking=no \
        {run}"
    while command.find("  ") != -1:
        command = command.replace("  ", " ")
    print(command)
    subprocess.check_call(command.split(" "))


def ssh(run="", index=None):
    set_config(sys.argv[1])

    if index is not None:
        server = get_config()["servers"][index]
        ssh_server(server, run)
    else:
        for server in get_config()["servers"]:
            ssh_server(server, run)


if __name__ == "__main__":
    index = int(sys.argv[2])
    ssh(index=index)
