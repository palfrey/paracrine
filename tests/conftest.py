from typing import BinaryIO

import pytest
import yaml

from paracrine.helpers.config import (
    _clear_config,  # pyright: ignore[reportPrivateUsage]
)


def set_config_data(config_file: BinaryIO, data: object) -> None:
    config_file.write(yaml.dump(data).encode("utf-8"))
    config_file.flush()


@pytest.fixture(autouse=True)
def clear_config() -> None:
    _clear_config()
