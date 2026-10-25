from pathlib import Path

from paracrine.helpers.fs import run_with_marker, set_file_contents_from_data
from paracrine.helpers.python import setup_venv


def run():
    self_venv_root = Path("/opt/self-venv")
    self_venv_venv = self_venv_root.joinpath("venv")
    changes = setup_venv(self_venv_venv, with_uv=True)
    changes = (
        set_file_contents_from_data(self_venv_root.joinpath("uv.lock"), "uv.lock")
        or changes
    )
    changes = (
        set_file_contents_from_data(
            self_venv_root.joinpath("pyproject.toml"), "pyproject.toml"
        )
        or changes
    )
    run_with_marker(
        self_venv_root.joinpath("uv.marker"),
        "uv sync",
        directory=self_venv_root,
        force_build=changes,
        env={"UV_PROJECT_ENVIRONMENT": self_venv_venv.as_posix()},
    )
