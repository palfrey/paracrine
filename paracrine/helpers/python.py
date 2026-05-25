import pathlib
import shutil

from paracrine import is_dry_run

from .fs import run_command


def setup_venv(venv: pathlib.Path) -> None:
    venv_bin = venv.joinpath("bin")
    venv_python = venv_bin.joinpath("python3")
    expected_python = pathlib.Path(
        run_command("which python3", dry_run_safe=True).strip()
    )
    if venv_python.exists():
        full_python_path = venv_python.readlink()
        if full_python_path != expected_python:
            if is_dry_run():
                print(
                    f"Would have deleted venv ({venv}) with old Python {full_python_path}, expected {expected_python}"
                )
            else:
                print(
                    f"Deleting venv ({venv}) with old Python {full_python_path}, expected {expected_python}"
                )
                shutil.rmtree(venv)

    venv_pip = venv_bin.joinpath("pip")
    if not venv_pip.exists():
        run_command(f"python3 -m venv {venv}")

    if not venv_bin.joinpath("wheel").exists():
        run_command(f"{venv_pip} install wheel")
