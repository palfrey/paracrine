from mitogen.parent import Router
from mitogen.utils import run_with_router

from paracrine.helpers.config import set_config
from paracrine.helpers.fs import run_command
from paracrine.runner import main


def do(data: object):
    run_command("reboot")


def core(router: Router) -> None:
    for _ in main(router, None, do):
        pass


if __name__ == "__main__":
    import sys

    set_config(sys.argv[1])
    run_with_router(core)
