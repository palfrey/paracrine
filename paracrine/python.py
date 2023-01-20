import pathlib

from .fs import run_command, apt_install


def setup_venv(venv: pathlib.Path) -> None:
    venv_bin = venv.joinpath("bin")
    venv_pip = venv_bin.joinpath("pip")

    if not venv_pip.exists():
        apt_install(["python3-venv"])
        run_command(f"python3 -m venv {venv}")

    if not venv_bin.joinpath("wheel").exists():
        run_command(f"{venv_pip} install wheel")
