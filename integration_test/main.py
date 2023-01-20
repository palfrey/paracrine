import sys
from paracrine.main import everything
from mitogen.parent import Router
from paracrine.certs import do as certs_do
from . import pleroma

def bootstrap_func(router: Router):
    certs_do(router, "foo", "bar@foo.com")

def core_func():
    pleroma.do()

if __name__ == "__main__":
    everything(sys.argv[1], bootstrap_func, core_func)