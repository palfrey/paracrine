import json
import os
import pathlib

from .fs import run_command
from .config import config_path, configs


def setup_aws():
    aws_path = pathlib.Path(config_path()).joinpath("other-aws")
    if not aws_path.exists():
        json.dump(
            {
                "access_key": run_command(
                    "aws configure get aws_access_key_id"
                ).strip(),
                "secret_key": run_command(
                    "aws configure get aws_secret_access_key"
                ).strip(),
            },
            aws_path.open("w"),
            indent=2,
        )


def set_aws_creds():
    aws_conf = json.loads(configs("configs/other-aws"))
    os.environ["AWS_ACCESS_KEY_ID"] = aws_conf["access_key"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = aws_conf["secret_key"]
