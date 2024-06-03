import logging
import subprocess
from glob import glob
from pathlib import Path
from typing import Optional

from .fs import link, run_command, run_with_marker


def journal(name: str) -> None:
    res = run_command("journalctl -u %s" % name)
    print(res)


def systemd_set(
    name: str,
    enabled: Optional[bool] = None,
    running: Optional[bool] = None,
    restart: Optional[bool] = None,
    reloaded: Optional[bool] = None,
) -> None:
    systemctl_daemon_reload()
    raw = run_command("systemctl show %s --no-page" % name, dry_run_safe=True)
    status = dict([line.split("=", 1) for line in raw.splitlines()])
    unitFileState = status.get("UnitFileState")
    if unitFileState == "masked":
        logging.info("Unmasking %s" % name)
        run_command("systemctl unmask %s" % name)
    if enabled is not None:
        if enabled:
            if unitFileState not in ["enabled", "enabled-runtime"]:
                logging.info("%s is currently %s" % (name, unitFileState))
                run_command("systemctl enable %s" % name)
        else:
            if unitFileState is not None and unitFileState != "disabled":
                logging.info("%s is currently %s" % (name, unitFileState))
                run_command("systemctl disable %s" % name)
    started = False
    if running is not None:
        if running:
            if status["SubState"] not in ["running", "auto-restart", "start"]:
                logging.info("running: %s %s" % (name, status["SubState"]))
                try:
                    run_command("systemctl start %s" % name)
                except subprocess.CalledProcessError:
                    journal(name)
                    raise
                started = True
        else:
            if status["SubState"] not in ["dead"]:
                logging.info("running: %s %s" % (name, status["SubState"]))
                try:
                    run_command("systemctl stop %s" % name)
                except subprocess.CalledProcessError:
                    journal(name)
                    raise
    if restart is True and not started:
        try:
            run_command("systemctl restart %s" % name)
        except subprocess.CalledProcessError:
            journal(name)
            raise

    if reloaded is True:
        run_command("systemctl reload %s" % name)


def systemctl_daemon_reload():
    run_with_marker(
        "/opt/daemon-reload",
        "systemctl daemon-reload",
        deps=glob("/etc/systemd/system/*.service")
        + glob("/etc/systemd/user/*.service"),
    )


def link_service(fullpath: str) -> bool:
    path = Path(fullpath)
    link_change = link(
        f"/etc/systemd/system/{path.name}",
        path,
    )
    if link_change:
        systemctl_daemon_reload()
    return link_change
