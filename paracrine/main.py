import logging
import sys
from typing import Any, Dict

from paracrine.core import main

from .config import set_data
from . import bootstrap

from mitogen.parent import Router


def do(data: Dict[str, Any]) -> None:
    set_data(data)

    blogs.do()
    pleroma.do()


def core(router: Router) -> None:
    for info in main(router, do):
        pass

def everything(config: str):
    logging.basicConfig()
    logging.root.setLevel(logging.INFO)

    set_config(config)
    config = get_config()

    run(bootstrap.core)
    run(core)


if __name__ == "__main__":
    everything(sys.argv[1])