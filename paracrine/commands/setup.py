import pathlib

from .login import ssh

if __name__ == "__main__":
    python_wrapper = (
        pathlib.Path(__file__).parent.joinpath("python_wrapper.sh").open().read()
    )
    ssh(
        f"""apt-get update &&
        apt-get install -y curl sudo gettext-base &&
        (curl --proto '=https' --tlsv1.2 -LsSf https://github.com/astral-sh/uv/releases/download/0.9.18/uv-installer.sh | sh) &&
        ~/.local/bin/uv python install 3.13 &&
        rm -f /usr/local/bin/python3 &&
        echo '{python_wrapper}' | FULL_PYTHON_PATH=$(realpath ~/.local/bin/python3.13) envsubst > /usr/local/bin/python3 && chmod +x /usr/local/bin/python3""",
        as_root=True,
    )
