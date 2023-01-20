from os import system

from .config import get_config, path_to_config_file, set_config

if __name__ == "__main__":
    import sys

    set_config(sys.argv[1])
    server = int(sys.argv[2])

    server = get_config()["servers"][server]
    command = f"ssh {server['ssh_user']}@{server['ssh_hostname']} \
        -i {path_to_config_file(server['ssh_key'])} \
        -p {server['ssh_port']}"
    print(command)
    system(command)
