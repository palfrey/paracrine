from paracrine.deps import maketransmit
from paracrine.runner import generate_dependencies
from paracrine.services import cockroachdb, wireguard


def test_deps_ordering():
    modules = [wireguard, cockroachdb]
    modules = generate_dependencies(modules)

    assert maketransmit(modules) == [
        "paracrine.runners.core",
        "paracrine.services.cockroachdb.certs",
        "paracrine.services.wireguard.bootstrap",
        "paracrine.services.wireguard.core",
        "paracrine.services.wireguard",
        ("paracrine.services.cockroachdb.node", {}),
        ("paracrine.services.cockroachdb.init", {}),
        "paracrine.services.cockroachdb",
    ]
