import sys

from paracrine.runner import run
from paracrine.services import cockroachdb, pleroma

if __name__ == "__main__":
    run(
        sys.argv[1],
        [
            pleroma,
            (cockroachdb, {"HTTP_PORT": 9080}),
        ],
    )
