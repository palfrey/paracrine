import sys

import paracrine.services.pleroma as pleroma
from paracrine.runner import run

if __name__ == "__main__":
    run(sys.argv[1], [pleroma])
