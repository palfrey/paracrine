import tempfile
from pathlib import Path
from typing import BinaryIO, cast
from unittest.mock import patch

import pytest
from mitogen.ssh import HostKeyError

from paracrine.runner import run
from paracrine.services import ntp

from .conftest import set_config_data


def test_empty_servers():
    with tempfile.NamedTemporaryFile() as config_file:
        set_config_data(cast(BinaryIO, config_file), {"servers": []})
        run(["-i", config_file.name], [])


def test_bad_ssh_path():
    with tempfile.NamedTemporaryFile() as config_file:
        set_config_data(
            cast(BinaryIO, config_file),
            {
                "data_path": ".",
                "servers": [
                    {
                        "ssh_hostname": "",
                        "ssh_key": "TBD",
                        "ssh_user": "",
                        "name": "foo",
                    }
                ],
            },
        )
        with pytest.raises(Exception, match="Can't find ssh key /tmp/configs/TBD"):
            run(["-i", config_file.name], [ntp])


def test_host_key_error(capsys: pytest.CaptureFixture[str]):
    with patch("mitogen.parent.Router.ssh", side_effect=HostKeyError):
        with tempfile.TemporaryDirectory() as raw_temp_directory:
            temp_directory = Path(raw_temp_directory)
            config_file_path = temp_directory.joinpath("config.yaml")
            with config_file_path.open("wb") as config_file:
                set_config_data(
                    cast(BinaryIO, config_file),
                    {
                        "data_path": ".",
                        "servers": [
                            {
                                "name": "test",
                                "ssh_hostname": "foo",
                                "ssh_key": "key_path",
                                "ssh_user": "test_user",
                            }
                        ],
                    },
                )
            configs_folder = temp_directory.joinpath("configs")
            configs_folder.mkdir()
            key_path = configs_folder.joinpath("key_path")
            key_path.open("w").write("test")
            with pytest.raises(HostKeyError):
                run(["-i", config_file_path.as_posix()], [ntp])

            res = capsys.readouterr()
            assert (
                f"Try running the following manually: ssh test_user@foo -p 22 -i {key_path.as_posix()}"
                in res.out
            ), res.out
