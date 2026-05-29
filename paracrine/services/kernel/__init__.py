options: dict[str, object] = {}


def dependencies():
    from . import do_upgrade

    return [(do_upgrade, options)]
