import contextlib
import grp
import hashlib
import logging
import os
import pwd
import re
import select
import stat
import subprocess
from datetime import datetime, timedelta
from difflib import unified_diff
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union, cast

from typing_extensions import TypedDict

from paracrine import Pathy, is_dry_run

from .config import data_files, jinja_env


def hash_data(data: bytes) -> str:
    m = hashlib.sha256()
    m.update(data)
    return m.hexdigest()


def set_file_contents(
    fname: Pathy,
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
        if isinstance(contents, str):
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

    if needs_update and not is_dry_run():
        if isinstance(contents, str):
            open(fname, "w").write(contents)
        else:
            open(fname, "wb").write(contents)

    needs_update = set_owner(fname, owner, group) or needs_update

    return needs_update


def render_template(template: str, **kwargs: object) -> str:
    return jinja_env().get_template(template).render(**kwargs)


def set_file_contents_from_template(
    fname: Pathy, template: str, ignore_changes: bool = False, **kwargs: object
) -> bool:
    return set_file_contents(
        fname,
        render_template(template, **kwargs),
        ignore_changes=ignore_changes,
    )


def set_file_contents_from_data(fname: Pathy, data_path: str):
    return set_file_contents(fname, data_files()[data_path])


@contextlib.contextmanager
def cd(path: Pathy):
    CWD = os.getcwd()

    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(CWD)


def set_mode(path: Pathy, mode: Union[str, int]) -> bool:
    if isinstance(mode, str):
        raw_mode = int(mode, 8)
    else:
        raw_mode = mode

    dry_run = is_dry_run()

    try:
        existing = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        if dry_run:
            logging.info(f"Missing {path}, but would have set mode to {mode}")
            return True
        else:
            raise
    if existing != raw_mode:
        logging.info("chmod %s %s" % (path, mode))
        if not dry_run:
            os.chmod(path, raw_mode)
        return True
    else:
        return False


def set_owner(
    path: Pathy, owner: Optional[str] = None, group: Optional[str] = None
) -> bool:
    if owner is None and group is None:
        return False
    try:
        st = os.stat(path)
    except FileNotFoundError:
        if is_dry_run():
            logging.info(
                f"Can't find {path}, but would have set owner {owner} and group {group}"
            )
            return True
        else:
            raise
    if owner is not None:
        owner_id = pwd.getpwnam(owner).pw_uid
    else:
        owner_id = st.st_uid
    if group is not None:
        group_id = grp.getgrnam(group).gr_gid
    else:
        group_id = st.st_gid

    if st.st_uid != owner_id or st.st_gid != group_id:
        if not is_dry_run():
            os.chown(path, owner_id, group_id)
        return True
    else:
        return False


def make_directory(
    path: Pathy,
    mode: Union[str, int, None] = None,
    owner: Optional[str] = None,
    group: Optional[str] = None,
) -> bool:
    ret = False
    if not os.path.exists(path):
        logging.info("Make directory %s" % path)
        if not is_dry_run():
            os.makedirs(path)
        ret = True
    if mode is not None:
        ret = set_mode(path, mode) or ret
    if owner is not None or group is not None:
        set_owner(path, owner, group)
    return ret


def replace_line(fname: Pathy, search: str, replace: str) -> bool:
    existing = open(fname).read()
    if search in existing:
        return set_file_contents(fname, existing.replace(search, replace))
    else:
        return False


def insert_line(fname: Pathy, line: str) -> bool:
    existing = open(fname).read()
    if line not in existing:
        return set_file_contents(fname, existing + "\n" + line)
    else:
        return False


def insert_or_replace(
    fname: str, matcher: Union[re.Pattern[str], str], line: str
) -> bool:
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


def sha_file(fname: Pathy) -> str:
    from .debian import apt_install

    apt_install(["coreutils"])
    existing_sha = run_command("sha256sum %s" % fname, dry_run_safe=True).strip()
    return existing_sha.split(" ")[0]


def has_sha(fname: Pathy, sha: str) -> bool:
    if os.path.exists(fname):
        existing_sha = sha_file(fname)
        if existing_sha == sha:
            return True

    return False


def download(
    url: str, fname: Pathy, sha: str, mode: Union[int, str, None] = None
) -> bool:
    exists = has_sha(fname, sha)
    if not exists:
        from .debian import apt_install

        apt_install(["curl", "ca-certificates"])
        run_command("curl -Lo %s %s" % (fname, url))
        if not is_dry_run():
            existing_sha = sha_file(fname)
            assert existing_sha == sha, (existing_sha, sha)

    if mode is not None:
        set_mode(fname, mode)

    return not exists


def link(target: Pathy, source: Pathy) -> bool:
    if os.path.lexists(target) and (
        not os.path.exists(target) or not os.path.samefile(source, target)
    ):
        logging.info("Unlink %s" % target)
        if not is_dry_run():
            os.remove(target)
    if not os.path.lexists(target):
        logging.info("Link %s to %s" % (target, source))
        if not is_dry_run():
            os.symlink(source, target)
        return True
    else:
        return False


def download_executable(
    url: str, hash: str, name: Optional[str] = None, path: Optional[Pathy] = None
) -> bool:
    if name is None:
        name = url.split("/")[-1]
    if path is None:
        path = "/usr/local/bin/%s" % name
    return download(
        url,
        path,
        hash,
        mode="755",
    )


class Unpacked(TypedDict):
    changed: bool
    dir_name: Pathy


def download_and_unpack(
    url: str,
    hash: str,
    name: Optional[str] = None,
    dir_name: Optional[Pathy] = None,
    compressed_root: str = "/opt",
) -> Unpacked:
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
            run_command("unzip -q %s -d %s" % (compressed_path, dir_name))
        else:
            raise Exception(compressed_path)

        set_file_contents(marker_name, "")

        changed = True

    return {"changed": changed, "dir_name": dir_name}


def last_modified(fname: Pathy) -> float:
    try:
        return os.stat(fname).st_mtime
    except FileNotFoundError:
        return float(0)


def delete(fname: Pathy, quiet: bool = False) -> bool:
    if os.path.exists(fname):
        if not quiet:
            logging.info("Deleting %s", fname)
        if not is_dry_run():
            os.remove(fname)
        return True
    else:
        return False


def build_with_command(
    fname: Pathy,
    command: str,
    deps: List[Pathy] = [],
    force_build: bool = False,
    directory: Optional[Pathy] = None,
    binary: bool = False,
    run_if_command_changed: bool = True,
) -> bool:
    display = command.strip()
    while display.find("  ") != -1:
        display = display.replace("  ", " ")
    changed = (
        set_file_contents(
            "%s.command" % fname, display, ignore_changes=not run_if_command_changed
        )
        or force_build
    )
    target_modified = last_modified(fname)
    for dep in deps:
        if last_modified(dep) > target_modified:
            logging.info("%s is younger than %s" % (dep, fname))
            changed = True
            break
    existing_target = os.path.exists(fname)
    if not existing_target or changed:
        logging.info("Building %s" % fname)
        if command.find("|") != -1:
            out = b"" if binary else ""
            commands = command.split("|")
            for command in commands:
                print(f"running with {len(out)} bytes of input")
                try:
                    if binary:
                        out = run_command_raw(
                            command, input=cast(bytes, out), directory=directory
                        )
                    else:
                        out = run_command(
                            command, input=cast(str, out), directory=directory
                        )
                except subprocess.CalledProcessError:
                    print("Ran '%s' with input '%s'" % (command, out))
                    if not existing_target:
                        delete(fname)
                    raise
                except Exception:
                    if not existing_target:
                        delete(fname)
                    raise
        else:
            try:
                run_command(command, directory=directory)
            except Exception:
                if not existing_target:
                    delete(fname)
                raise
        return True
    else:
        return False


def run_with_marker(
    fname: Pathy,
    command: str,
    deps: Sequence[Pathy] = [],
    max_age: Optional[timedelta] = None,
    force_build: bool = False,
    directory: Optional[Pathy] = None,
    run_if_command_changed: bool = True,
    input: Optional[str] = None,
) -> bool:
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
        if not is_dry_run():
            open(fname, "w").write(command)

    return changed


class MissingCommandException(Exception):
    pass


def non_breaking_communicate(proc: subprocess.Popen[bytes]) -> Tuple[bytes, bytes]:
    assert proc.stdout is not None
    assert proc.stderr is not None
    working = select.select([proc.stdout, proc.stderr], [], [], 10)[0]
    if len(working) > 0:
        if working[0] == proc.stdout:
            return (proc.stdout.read(), b"")
        else:
            return (b"", proc.stderr.read())
    else:
        return (b"", b"")


def run_command_raw(
    cmd: str,
    directory: Optional[Pathy] = None,
    input: Optional[bytes] = None,
    allowed_exit_codes: List[int] = [0],
    dry_run_safe: bool = False,
) -> bytes:
    run_for_real = dry_run_safe or not is_dry_run()
    display = cmd.strip()
    while display.find("  ") != -1:
        display = display.replace("  ", " ")
    try:
        process = None
        if directory is not None:
            if run_for_real:
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
                logging.info("Would have run in %s: %s" % (directory, display))
        else:
            if run_for_real:
                logging.info("Run: %s" % display)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    stdin=subprocess.PIPE,
                )
            else:
                logging.info("Would have run: %s" % display)

        if run_for_real:
            assert process is not None
            assert process.stdout is not None
            os.set_blocking(process.stdout.fileno(), False)
            assert process.stderr is not None
            os.set_blocking(process.stderr.fileno(), False)
            stdout = b""
            stderr = b""
            DUMP_COMMAND = os.environ.get("DUMP_COMMAND", "false").lower() == "true"
            assert process.stdin is not None
            if input is not None:
                process.stdin.write(input)
            process.stdin.close()
            while True:

                def get_output() -> bool:
                    nonlocal stdout, stderr
                    (new_stdout, new_stderr) = non_breaking_communicate(process)
                    stdout += new_stdout
                    if DUMP_COMMAND and new_stdout != b"":
                        print(new_stdout.decode("utf-8"), end=None)
                    stderr += new_stderr
                    if DUMP_COMMAND and new_stderr != b"":
                        print(new_stderr.decode("utf-8"), end=None)
                    return new_stdout != b"" or new_stderr != b""

                get_output()
                maybe_returncode = process.poll()
                if maybe_returncode is None:
                    continue
                while get_output():
                    pass
                if maybe_returncode not in allowed_exit_codes:
                    if b": not found" in stderr or process.returncode == 127:
                        # missing command
                        raise MissingCommandException
                    assert process.returncode in allowed_exit_codes, (
                        process.returncode,
                        stdout,
                        stderr,
                    )
                break
            return stdout
        else:
            return b""
    except subprocess.CalledProcessError as e:
        print(e.output)
        raise


def run_command(
    cmd: str,
    directory: Optional[Pathy] = None,
    input: Union[str, bytes, None] = None,
    allowed_exit_codes: List[int] = [0],
    dry_run_safe: bool = False,
) -> str:
    if input is None or isinstance(input, bytes):
        real_input = input
    else:
        real_input = input.encode("utf-8")
    return run_command_raw(
        cmd, directory, real_input, allowed_exit_codes, dry_run_safe
    ).decode("utf-8")
