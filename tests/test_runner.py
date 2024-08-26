import tempfile
from typing import BinaryIO, cast
from unittest.mock import MagicMock, call, patch

from callee import InstanceOf, List, String
from mitogen.parent import Router

from paracrine.deps import Module
from paracrine.helpers import cron
from paracrine.runner import run, server_name_filter, server_role_picker
from paracrine.runners import aws, certs, core
from paracrine.services import ntp, postgresql

from .conftest import set_config_data


def get_run_sets(mock_internal_runner: MagicMock):
    sets: list[tuple[list[str], list[Module]]] = []
    for call_arg in mock_internal_runner.call_args_list:
        assert call_arg == call(
            InstanceOf(Router),
            List(of=String()),
            List(),
            "local",
            "run",
            "parse_return",
            True,
        )
        sets.append((call_arg.args[1], call_arg.args[2]))

    return sets


def test_runner_one_dep():
    with patch("paracrine.runner.internal_runner") as mock_internal_runner:
        with tempfile.NamedTemporaryFile() as config_file:
            set_config_data(
                cast(BinaryIO, config_file),
                {
                    "data_path": ".",
                    "servers": [{"name": "foo"}],
                },
            )
            run(["-i", config_file.name], [ntp])

        assert get_run_sets(mock_internal_runner) == [(["foo"], [core, ntp])]


def test_runner_dep_with_extras():
    with patch("paracrine.runner.internal_runner") as mock_internal_runner:
        with tempfile.NamedTemporaryFile() as config_file:
            set_config_data(
                cast(BinaryIO, config_file),
                {
                    "data_path": ".",
                    "servers": [{"name": "foo"}],
                },
            )
            run(["-i", config_file.name], [certs])

        assert get_run_sets(mock_internal_runner) == [
            (["foo"], [core, cron, aws, certs])
        ]


def test_runner_dep_with_multiple():
    with patch("paracrine.runner.internal_runner") as mock_internal_runner:
        with tempfile.NamedTemporaryFile() as config_file:
            set_config_data(
                cast(BinaryIO, config_file),
                {
                    "data_path": ".",
                    "servers": [{"name": "foo"}, {"name": "bar"}],
                },
            )
            run(
                ["-i", config_file.name],
                {
                    server_name_filter("foo"): [ntp],
                    server_name_filter("bar"): [postgresql],
                },
            )

        assert get_run_sets(mock_internal_runner) == [
            (["bar", "foo"], [core]),
            (["foo"], [ntp]),
            (["bar"], [postgresql]),
        ]


def test_runner_one_dep_with_config():
    with patch("paracrine.runner.internal_runner") as mock_internal_runner:
        with tempfile.NamedTemporaryFile() as config_file:
            set_config_data(
                cast(BinaryIO, config_file),
                {
                    "data_path": ".",
                    "servers": [{"name": "foo"}],
                },
            )
            run(["-i", config_file.name], [(ntp, {"foo": "bar"})])

        assert get_run_sets(mock_internal_runner) == [
            (["foo"], [core, (ntp, {"foo": "bar"})])
        ]


def test_runner_server_role_picker():
    with patch("paracrine.runner.internal_runner") as mock_internal_runner:
        with tempfile.NamedTemporaryFile() as config_file:
            set_config_data(
                cast(BinaryIO, config_file),
                {
                    "data_path": ".",
                    "servers": [{"name": "foo"}],
                },
            )
            run(
                ["-i", config_file.name],
                {
                    server_role_picker("timeserver"): [ntp],
                },
            )

        assert get_run_sets(mock_internal_runner) == [(["foo"], [core, ntp])]
