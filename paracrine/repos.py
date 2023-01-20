from paracrine.commands import apt_update, set_file_contents


def debian_repo(name, contents=None):
    fname = "/etc/apt/sources.list.d/%s.list" % name
    if contents is None:
        contents = "deb http://deb.debian.org/debian %s main" % name

    changed = set_file_contents(fname, contents)
    if changed:
        apt_update()
