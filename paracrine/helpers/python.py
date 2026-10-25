import pathlib
import shutil

from paracrine import is_dry_run

from .fs import download_and_unpack, run_command

_expected_python: pathlib.Path | None = None


def get_expected_python() -> pathlib.Path:
    global _expected_python
    if _expected_python is None:
        _expected_python = pathlib.Path(
            run_command("which python3", dry_run_safe=True).strip()
        )
        while _expected_python.is_symlink():
            _expected_python = _expected_python.readlink()
            if not _expected_python.is_absolute():
                raise Exception(_expected_python)

    return _expected_python


def setup_venv(venv: pathlib.Path, with_uv: bool = False) -> bool:
    venv_bin = venv.joinpath("bin")
    venv_python = venv_bin.joinpath("python3").absolute()
    changes = False
    if venv_python.exists():
        expected_python = get_expected_python()
        full_python_path = venv_python
        while full_python_path.is_symlink():
            full_python_path = full_python_path.readlink()
            if not full_python_path.is_absolute():
                full_python_path = venv_bin.joinpath(full_python_path)
        if full_python_path != expected_python:
            changes = True
            if is_dry_run():
                print(
                    f"Would have deleted venv ({venv}) with old Python {full_python_path}, expected {expected_python}"
                )
            else:
                print(
                    f"Deleting venv ({venv}) with old Python {full_python_path}, expected {expected_python}"
                )
                shutil.rmtree(venv)

    if with_uv:
        res = download_and_unpack(
            "https://releases.astral.sh/github/uv/releases/download/0.13.5/uv-i686-unknown-linux-musl.tar.gz",
            "ef427365b5e84790d3f807bd0dfda0d8ee89e78f47e0cfdf86378a5bd9b13894",
        )
        uv_bin = pathlib.Path(res["dir_name"]).joinpath(
            "uv-i686-unknown-linux-musl", "uv"
        )
        if not venv_python.exists():
            run_command(f"{uv_bin} venv {venv}")
    else:
        venv_pip = venv_bin.joinpath("pip")
        if not venv_pip.exists():
            run_command(f"python3 -m venv {venv}")
            changes = True

        if not venv_bin.joinpath("wheel").exists():
            run_command(f"{venv_pip} install wheel")
            changes = True

    return changes
