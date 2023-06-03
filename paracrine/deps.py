import importlib
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from mergedeep import merge

from .helpers.config import clear_return_data, get_return_data, set_data

Modules = List[Union[ModuleType, Tuple[ModuleType, Dict]]]
"""Type of modules handed to `paracrine.runner.run`"""

TransmitModules = List[Union[str, Tuple[str, Dict]]]


def runfunc(
    modules: Modules, name: str, arguments: Dict[str, Any] = {}, data: Dict = {}
) -> Dict[str, Any]:
    ret = {}

    def run(module: ModuleType, options: Dict):
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


def maketransmit(modules: Modules) -> TransmitModules:
    ret = []
    for module in modules:
        if isinstance(module, ModuleType):
            ret.append(module.__name__)
        else:
            ret.append((module[0].__name__, module[1]))

    return ret


def makereal(modules: TransmitModules) -> Modules:
    ret = []
    for module in modules:
        if isinstance(module, str):
            ret.append(importlib.import_module(module))
        else:
            ret.append((importlib.import_module(module[0]), module[1]))

    return ret
