import json
import pathlib

from ..helpers.config import config_path, get_config_file
from ..helpers.fs import run_command, set_file_contents


def local():
    aws_path = pathlib.Path(config_path()).joinpath("other-aws")
    if not aws_path.exists():
        set_file_contents(
            aws_path,
            json.dumps(
                {
                    "access_key": run_command(
                        "aws configure get aws_access_key_id"
                    ).strip(),
                    "secret_key": run_command(
                        "aws configure get aws_secret_access_key"
                    ).strip(),
                },
                indent=2,
            ),
        )


def get_env_with_creds():
    aws_conf = json.loads(get_config_file("configs/other-aws"))
    return f"env AWS_ACCESS_KEY_ID={aws_conf['access_key']} AWS_SECRET_ACCESS_KEY={aws_conf['secret_key']}"
