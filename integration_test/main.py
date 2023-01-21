import sys
from paracrine.aws import setup_aws
from mitogen.parent import Router
import paracrine.certs
import paracrine.main
import pleroma


def bootstrap_func(router: Router):
    setup_aws()
    paracrine.certs.core(router, "foo", "bar@foo.com")


def core_func():
    pleroma.do()


if __name__ == "__main__":
    paracrine.main.everything(sys.argv[1], bootstrap_func, core_func)
