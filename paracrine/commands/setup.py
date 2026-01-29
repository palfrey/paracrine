from .login import ssh

if __name__ == "__main__":
    ssh(
        """apt-get update &&
        apt-get install -y curl sudo &&
        (curl --proto '=https' --tlsv1.2 -LsSf https://github.com/astral-sh/uv/releases/download/0.9.18/uv-installer.sh | sh) &&
        ~/.local/bin/uv python install 3.13 &&
        rm -f /usr/local/bin/python3 &&
        ln -s ~/.local/bin/python3.13 /usr/local/bin/python3""",
        as_root=True,
    )
