import logging
from typing import Callable, Optional

from . import bootstrap
from .config import set_config
from .core import run


def everything(
    inventory_path: str, bootstrap_func: Optional[Callable], core_func: Callable
):
    logging.basicConfig()
    logging.root.setLevel(logging.INFO)

    set_config(inventory_path)
    run(bootstrap.core)
    if bootstrap_func is not None:
        run(bootstrap_func)
    run(core_func)
