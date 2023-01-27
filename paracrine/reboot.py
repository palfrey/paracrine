from mitogen.parent import Router

from .config import set_config
from .core import main, run
from .fs import run_command


def do(data):
    run_command("reboot")


def core(router: Router) -> None:
    for _ in main(router, do):
        pass


if __name__ == "__main__":
    import sys

    set_config(sys.argv[1])
    run(core)
