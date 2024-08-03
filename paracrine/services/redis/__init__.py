from typing import Dict

from paracrine.deps import Modules

options: Dict[str, object] = {}


def dependencies() -> Modules:
    from . import init

    return [(init, options)]
