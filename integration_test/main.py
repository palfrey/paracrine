import sys

from mitogen.parent import Router

import paracrine.certs
import paracrine.services.pleroma as pleroma
from paracrine.aws import setup_aws
from paracrine.runner import everything


def bootstrap_func(router: Router):
    setup_aws()
    paracrine.certs.core(router, "pleroma.example.com", "bar@foo.com")


if __name__ == "__main__":
    everything(sys.argv[1], [pleroma])
