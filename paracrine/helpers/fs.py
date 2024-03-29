import contextlib
import grp
import hashlib
import logging
import os
import pwd
import re
import stat
import subprocess
from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from typing import List, Optional, Union

from .config import data_files, jinja_env


def hash_data(data: bytes) -> str:
    m = hashlib.sha256()
    m.update(data)
    return m.hexdigest()


def set_file_contents(
    fname: str,
    contents: Union[str, bytes],
    ignore_changes: bool = False,
    owner: Optional[str] = None,
    group: Optional[str] = None,
) -> bool:
    needs_update = False

    if type(contents) == bytes:
        try:
            contents = contents.decode("utf-8")
        except UnicodeDecodeError:
            pass

    if not os.path.exists(fname):
        needs_update = True
        logging.info("File %s was missing" % fname)
    elif not ignore_changes:
        if type(contents) == str:
            data = open(fname, "rb").read().decode("utf-8").splitlines(True)
            diff = list(unified_diff(data, contents.splitlines(True)))
            if len(diff) > 0:
                diff = "".join(diff)
                logging.info("File %s was different. Diff is: \n%s" % (fname, diff))
                needs_update = True
        else:
            data = open(fname, "rb").read()
            if hash_data(data) != hash_data(contents):
                logging.info("File %s was different" % fname)
                needs_update = True

    if needs_update:
        if type(contents) == str:
            open(fname, "w").write(contents)
        else:
            open(fname, "wb").write(contents)

    needs_update = set_owner(fname, owner, group) or needs_update

    return needs_update


def render_template(template, **kwargs):
    return jinja_env().get_template(template).render(**kwargs)


def set_file_contents_from_template(fname, template, ignore_changes=False, **kwargs):
    return set_file_contents(
        fname,
        render_template(template, **kwargs),
        ignore_changes=ignore_changes,
    )


def set_file_contents_from_data(fname: str, data_path: str):
    return set_file_contents(fname, data_files()[data_path])


@contextlib.contextmanager
def cd(path: os.PathLike):
    CWD = os.getcwd()

    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(CWD)


def set_mode(path, mode):
    if type(mode) == str:
        raw_mode = int(mode, 8)
    else:
        raw_mode = mode
    existing = stat.S_IMODE(os.stat(path).st_mode)
    if existing != raw_mode:
        logging.info("chmod %s %s" % (path, mode))
        os.chmod(path, raw_mode)
        return True
    else:
        return False


def set_owner(path, owner: Optional[str] = None, group: Optional[str] = None):
    st = os.stat(path)
    if owner is not None:
        owner_id = pwd.getpwnam(owner).pw_uid
    else:
        owner_id = st.st_uid
    if group is not None:
        group_id = grp.getgrnam(group).gr_gid
    else:
        group_id = st.st_gid

    if st.st_uid != owner_id or st.st_gid != group_id:
        os.chown(path, owner_id, group_id)
        return True
    else:
        return False


def make_directory(path, mode=None, owner=None, group=None):
    ret = False
    if not os.path.exists(path):
        logging.info("Make directory %s" % path)
        os.makedirs(path)
        ret = True
    if mode is not None:
        ret = set_mode(path, mode) or ret
    if owner is not None or group is not None:
        set_owner(path, owner, group)
    return ret


def replace_line(fname, search, replace):
    existing = open(fname).read()
    if search in existing:
        set_file_contents(fname, existing.replace(search, replace))


def insert_line(fname, line):
    existing = open(fname).read()
    if line not in existing:
        return set_file_contents(fname, existing + "\n" + line)
    else:
        return False


def insert_or_replace(fname: str, matcher: Union[re.Pattern, str], line: str) -> bool:
    existing = open(fname).read()
    if isinstance(matcher, re.Pattern):
        results = matcher.search(existing)
        if results is not None:
            return set_file_contents(
                fname, existing[: results.start()] + line + existing[results.end() :]
            )
    elif matcher in existing:
        return set_file_contents(fname, existing.replace(matcher, line))
    return set_file_contents(fname, existing + "\n" + line)


def sha_file(fname):
    from .debian import apt_install

    apt_install(["coreutils"])
    existing_sha = run_command("sha256sum %s" % fname).strip()
    return existing_sha.split(" ")[0]


def has_sha(fname, sha):
    if os.path.exists(fname):
        existing_sha = sha_file(fname)
        if existing_sha == sha:
            return True

    return False


def download(url, fname, sha, mode=None):
    exists = has_sha(fname, sha)
    if not exists:
        from .debian import apt_install

        apt_install(["curl", "ca-certificates"])
        run_command("curl -Lo %s %s" % (fname, url))
        existing_sha = sha_file(fname)
        assert existing_sha == sha, (existing_sha, sha)

    if mode is not None:
        set_mode(fname, mode)

    return not exists


def link(target, source):
    if os.path.lexists(target) and (
        not os.path.exists(target) or not os.path.samefile(source, target)
    ):
        logging.info("Unlink %s" % target)
        os.remove(target)
    if not os.path.lexists(target):
        logging.info("Link %s to %s" % (target, source))
        os.symlink(source, target)
        return True
    else:
        return False


def download_executable(url, hash, name=None, path=None):
    if name is None:
        name = url.split("/")[-1]
    if path is None:
        path = "/usr/local/bin/%s" % name
    download(
        url,
        path,
        hash,
        mode="755",
    )


def download_and_unpack(url, hash, name=None, dir_name=None, compressed_root="/opt"):
    if name is None:
        name = url.split("/")[-1]
    compressed_path: str = "%s/%s" % (compressed_root, name)
    if dir_name is None:
        dir_name = "/opt/%s" % name.replace(".tar.gz", "").replace(".tgz", "").replace(
            ".tar.xz", ""
        )
    changed = download(
        url,
        compressed_path,
        hash,
    )

    make_directory(dir_name)
    marker_name = Path(compressed_path + ".unpacked")
    if not marker_name.exists():
        from .debian import apt_install

        if compressed_path.endswith("tar.gz") or compressed_path.endswith(".tgz"):
            apt_install(["tar"])
            run_command("tar --directory=%s -zxvf %s" % (dir_name, compressed_path))
        elif compressed_path.endswith("tar.xz"):
            apt_install(["tar", "xz-utils"])
            run_command("tar --directory=%s -Jxvf %s" % (dir_name, compressed_path))
        elif compressed_path.endswith("zip"):
            apt_install(["unzip"])
            run_command("unzip %s -d %s" % (compressed_path, dir_name))
        else:
            raise Exception(compressed_path)

        marker_name.open("w").write("")

        changed = True

    return {"changed": changed, "dir_name": dir_name}


def last_modified(fname):
    try:
        return os.stat(fname).st_mtime
    except FileNotFoundError:
        return float(0)


def delete(fname: str, quiet: bool = False) -> bool:
    if os.path.exists(fname):
        if not quiet:
            logging.info("Deleting %s", fname)
        os.remove(fname)
        return True
    else:
        return False


def build_with_command(fname, command, deps=[], force_build=False, directory=None):
    display = command.strip()
    while display.find("  ") != -1:
        display = display.replace("  ", " ")
    changed = set_file_contents("%s.command" % fname, display) or force_build
    target_modified = last_modified(fname)
    for dep in deps:
        if last_modified(dep) > target_modified:
            logging.info("%s is younger than %s" % (dep, fname))
            changed = True
            break
    if not os.path.exists(fname) or changed:
        logging.info("Building %s" % fname)
        if command.find("|") != -1:
            out = ""
            commands = command.split("|")
            for command in commands:
                try:
                    out = run_command(command, input=out, directory=directory)
                except subprocess.CalledProcessError:
                    print("Ran '%s' with input '%s'" % (command, out))
                    raise
        else:
            run_command(command, directory=directory)
        return True
    else:
        return False


def run_with_marker(
    fname,
    command,
    deps=[],
    max_age=None,
    force_build=False,
    directory=None,
    run_if_command_changed=True,
    input: Optional[str] = None,
):
    changed = not os.path.exists(fname) or force_build
    target_modified = last_modified(fname)
    if max_age is not None:
        age = datetime.now() - datetime.fromtimestamp(target_modified)
        if age > max_age:
            changed = True
    for dep in deps:
        dep_modified = last_modified(dep)
        if dep_modified > target_modified:
            logging.info("%s is younger than %s" % (dep, fname))
            changed = True
            break

    if run_if_command_changed and not changed:
        old_command = open(fname).read()
        changed = old_command != command

    if changed:
        run_command(command, directory=directory, input=input)
        open(fname, "w").write(command)

    return changed


def run_command(
    cmd: str,
    directory: Optional[str] = None,
    input: Optional[str] = None,
    allowed_exit_codes: List[int] = [0],
) -> str:
    display = cmd.strip()
    while display.find("  ") != -1:
        display = display.replace("  ", " ")
    try:
        if directory is not None:
            logging.info("Run in %s: %s" % (directory, display))
            with cd(directory):
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    stdin=subprocess.PIPE,
                )
        else:
            logging.info("Run: %s" % display)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                stdin=subprocess.PIPE,
            )

        if input is not None:
            input = input.encode("utf-8")
        (stdout, stderr) = process.communicate(input=input)
        assert process.returncode in allowed_exit_codes, (
            process.returncode,
            stdout,
            stderr,
        )
        return stdout.decode("utf-8")
    except subprocess.CalledProcessError as e:
        print(e.output)
        raise
