import tempfile
from typing import BinaryIO

import pytest
import yaml

from paracrine.runner import run


def set_config_data(config_file: BinaryIO, data: object) -> None:
    config_file.write(yaml.dump(data).encode("utf-8"))
    config_file.flush()


def test_empty_servers():
    with tempfile.NamedTemporaryFile() as config_file:
        set_config_data(config_file, {"servers": []})
        run(config_file.name, [])


def test_bad_ssh_path():
    with tempfile.NamedTemporaryFile() as config_file:
        set_config_data(
            config_file,
            {
                "data_path": ".",
                "servers": [{"ssh_hostname": "", "ssh_key": "TBD", "ssh_user": ""}],
            },
        )
        with pytest.raises(Exception, match="Can't find ssh key /tmp/configs/TBD"):
            run(config_file.name, [])
