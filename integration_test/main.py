import sys

from paracrine.runner import run
from paracrine.services import cockroachdb, kernel, pleroma

if __name__ == "__main__":
    run(
        sys.argv[1:],
        [
            (kernel, {"minimum_version": "6.1.0"}),
            pleroma,
            (cockroachdb, {"HTTP_PORT": 9080}),
        ],
    )
