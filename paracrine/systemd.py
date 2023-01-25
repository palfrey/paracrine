import logging
import subprocess
from pathlib import Path

from .fs import link, run_command


def journal(name):
    res = run_command("journalctl -u %s" % name)
    print(res)


def systemd_set(name, enabled=None, running=None, restart=None, reloaded=None):
    raw = run_command("systemctl show %s --no-page" % name)
    status = dict([line.split("=", 1) for line in raw.splitlines()])
    if status.get("UnitFileState") == "masked":
        logging.info("Unmasking %s" % name)
        run_command("systemctl unmask %s" % name)
    if enabled is not None:
        if enabled:
            if status["UnitFileState"] != "enabled":
                logging.info("%s is currently %s" % (name, status["UnitFileState"]))
                run_command("systemctl enable %s" % name)
        else:
            if status["UnitFileState"] != "disabled":
                logging.info("%s is currently %s" % (name, status["UnitFileState"]))
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

    if reloaded is not None:
        run_command("systemctl reload %s" % name)


def systemctl_daemon_reload():
    run_command("systemctl daemon-reload")


def link_service(fullpath: str):
    path = Path(fullpath)
    link_change = link(
        f"/etc/systemd/system/{path.name}",
        path,
    )
    if link_change:
        systemctl_daemon_reload()
