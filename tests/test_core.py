import json
import os
import tempfile

import pytest

from paracrine.runners.core import parse_return


def test_no_infos_parse_return() -> None:
    parse_return([])


def test_parse_return(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as raw_temp_directory:
        monkeypatch.chdir(raw_temp_directory)
        monkeypatch.setenv("PARACRINE_DRY_RUN", "false")
        parse_return(
            [
                {
                    "network_devices": json.dumps({}),
                    "server_name": "foo",
                    "users": [],
                    "groups": [],
                    "hostname": "foo",
                    "external_ip": json.dumps({"ip": "1.2.3.4"}),
                }
            ]
        )
        files = os.listdir(raw_temp_directory)
        assert files == ["configs"]
        config_files = os.listdir(os.path.join(raw_temp_directory, "configs"))
        assert config_files == ["other-foo", "networks-foo"]
