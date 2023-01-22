import logging
from typing import Any, Callable, Dict, Optional

from .core import main, run

from .config import set_config, set_data
from . import bootstrap

from mitogen.parent import Router


def do(data: Dict[str, Any], core_func: Callable) -> None:
    set_data(data)
    core_func()


def core(router: Router, core_func: Callable) -> None:
    for _ in main(router, do, core_func):
        pass


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
