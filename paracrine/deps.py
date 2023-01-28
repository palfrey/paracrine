import importlib
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

Modules = List[Union[ModuleType, Tuple[ModuleType, Dict]]]
TransmitModules = List[Union[str, Tuple[str, Dict]]]


def runfunc(
    modules: Modules, name: str, arguments: Dict[str, Any] = {}
) -> Dict[str, Any]:
    ret = {}

    def run(module: ModuleType, options: Dict):
        func: Optional[Callable] = getattr(module, name, None)
        if func is not None:
            setattr(module, "options", options)
            if module.__name__ in arguments:
                ret[module.__name__] = func(arguments[module.__name__])
            else:
                ret[module.__name__] = func()

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
