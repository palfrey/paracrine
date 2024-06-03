import importlib
from types import ModuleType
from typing import Any, Callable, Dict, Optional, Sequence, Tuple, Union

from mergedeep import merge

from .helpers.config import clear_return_data, get_return_data, set_data

Module = Union[ModuleType, Tuple[ModuleType, Dict[object, object]]]
Modules = Sequence[Module]
"""Type of modules handed to `paracrine.runner.run`"""

TransmitModule = Union[str, Tuple[str, Dict[object, object]]]
TransmitModules = Sequence[TransmitModule]


def runfunc(
    modules: Modules,
    name: str,
    arguments: Dict[str, Any] = {},
    data: Dict[str, object] = {},
) -> Dict[str, Any]:
    ret = {}

    def run(module: ModuleType, options: Dict[object, object]):
        func: Optional[Callable] = getattr(module, name, None)
        if func is not None:
            setattr(module, "options", options)
            clear_return_data()
            if data != {}:
                set_data(data)
            try:
                if module.__name__ not in ret:
                    ret[module.__name__] = []
                if module.__name__ in arguments:
                    info = func(arguments[module.__name__])
                else:
                    info = func()
                if isinstance(info, Dict):
                    info = merge({}, info, get_return_data())
                elif info is None:
                    info = get_return_data()
                ret[module.__name__].append(info)
            except Exception:
                print(f"Error while running {name} for {module.__name__}")
                raise

    for module in modules:
        if isinstance(module, ModuleType):
            run(module, {})
        else:
            run(module[0], module[1])
    return ret


def maketransmit_single(module: Module) -> TransmitModule:
    if isinstance(module, ModuleType):
        return module.__name__
    else:
        return (module[0].__name__, module[1])


def maketransmit(modules: Modules) -> TransmitModules:
    return [maketransmit_single(module) for module in modules]


def makereal(modules: TransmitModules) -> Modules:
    ret = []
    for module in modules:
        if isinstance(module, str):
            ret.append(importlib.import_module(module))
        else:
            ret.append((importlib.import_module(module[0]), module[1]))

    return ret
