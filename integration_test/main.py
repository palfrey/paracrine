import sys
from typing import Any, Dict

import pleroma
from mitogen.parent import Router

import paracrine.certs
from paracrine.aws import setup_aws
from paracrine.config import set_data
from paracrine.core import main
from paracrine.main import everything

# Can't get simpler because of https://github.com/mitogen-hq/mitogen/issues/894


def bootstrap_func(router: Router):
    setup_aws()
    paracrine.certs.core(router, "foo", "bar@foo.com")


def do(data: Dict[str, Any]) -> None:
    set_data(data)
    pleroma.do()


def core_func(router: Router) -> None:
    for _ in main(router, do):
        pass


if __name__ == "__main__":
    everything(sys.argv[1], bootstrap_func, core_func)
