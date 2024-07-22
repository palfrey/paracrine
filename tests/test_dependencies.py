from paracrine.deps import Modules, maketransmit
from paracrine.helpers.config import set_data
from paracrine.runner import generate_dependencies
from paracrine.services import cockroachdb, wireguard


def test_deps_ordering():
    modules: Modules = [wireguard, cockroachdb]
    set_data({"templates": "", "inventory": {"servers": []}})
    modules = generate_dependencies(modules)

    assert maketransmit(modules) == [
        "paracrine.runners.core",
        ("paracrine.services.cockroachdb.certs", {"versions": {}}),
        "paracrine.services.wireguard.bootstrap",
        "paracrine.services.wireguard.core",
        "paracrine.services.wireguard",
        ("paracrine.services.cockroachdb.node", {"versions": {}}),
        ("paracrine.services.cockroachdb.init", {"versions": {}}),
        "paracrine.services.cockroachdb",
    ]


def test_cockroach_versions():
    modules: Modules = [cockroachdb]
    set_data({"templates": "", "inventory": {"servers": [{"name": "foo"}]}})
    modules = generate_dependencies(modules)

    assert maketransmit(modules) == [
        "paracrine.runners.core",
        ("paracrine.services.cockroachdb.certs", {"versions": {"foo": "23.1.1"}}),
        "paracrine.services.wireguard.bootstrap",
        "paracrine.services.wireguard.core",
        "paracrine.services.wireguard",
        ("paracrine.services.cockroachdb.node", {"versions": {"foo": "23.1.1"}}),
        ("paracrine.services.cockroachdb.init", {"versions": {"foo": "23.1.1"}}),
        "paracrine.services.cockroachdb",
    ]
