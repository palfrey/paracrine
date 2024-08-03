import subprocess
import sys

from ..helpers.config import get_config, path_to_config_file, set_config


def sftp(index: int):
    set_config(sys.argv[1])

    server = get_config()["servers"][index]
    command = f"sftp \
        -i {path_to_config_file(server['ssh_key'])} \
        -P {server['ssh_port']} \
        -o StrictHostKeyChecking=no \
        {server['ssh_user']}@{server['ssh_hostname']}"
    while command.find("  ") != -1:
        command = command.replace("  ", " ")
    print(command)
    subprocess.check_call(command.split(" "))


if __name__ == "__main__":
    index = int(sys.argv[2])
    sftp(index=index)
