"""T60 — the collector is killed outright (SIGKILL) and its child must still go.

Author tests (not D5), added after the independent review of 2026-11-19: the
shell kills, not terminates, the collector when the plugin is unloaded, so the
signal handler alone left that path open. Also covers a burst of cancel signals.
"""
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

COLLECT = Path(__file__).resolve().parents[1] / "bin" / "ai-usage-collect"

FAKE = """#!/bin/sh
{trap}
echo $$ > "$FAKE_PID"
sleep 120 &
echo $! > "$FAKE_PID.child"
wait
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def _start(tmp_path, trap=""):
    fake = tmp_path / "bin" / "ai-usagebar"
    fake.parent.mkdir()
    fake.write_text(FAKE.format(trap=trap))
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    pidfile = tmp_path / "pid"
    env = dict(os.environ, FAKE_PID=str(pidfile),
               PATH=f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    proc = subprocess.Popen([sys.executable, str(COLLECT), "--source", "ai-usagebar"],
                            env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    child_file = Path(str(pidfile) + ".child")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not (
            pidfile.exists() and child_file.exists()
            and pidfile.read_text().strip() and child_file.read_text().strip()):
        time.sleep(0.02)
    return proc, int(pidfile.read_text()), int(child_file.read_text())


def _wait_gone(pids, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not any(_alive(p) for p in pids):
            return True
        time.sleep(0.05)
    return False


@pytest.mark.parametrize("trap", ["", "trap '' TERM"], ids=["plain", "ignores-term"])
def test_sigkill_on_the_collector_still_stops_the_child_tree(tmp_path, trap):
    proc, child, grandchild = _start(tmp_path, trap)
    try:
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=5)
        assert _wait_gone([child, grandchild], 6), "the child tree outlived a killed collector"
    finally:
        for pid in (child, grandchild):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_a_burst_of_cancel_signals_is_one_teardown(tmp_path):
    proc, child, grandchild = _start(tmp_path, "trap '' TERM")
    try:
        started = time.monotonic()
        for _ in range(60):
            if proc.poll() is not None:
                break
            proc.send_signal(signal.SIGTERM)
            time.sleep(0.03)
        proc.wait(timeout=6)
        # One grace period, not one per signal.
        assert time.monotonic() - started < 5
        assert proc.returncode not in (0, None)
        assert _wait_gone([child, grandchild], 3)
    finally:
        for pid in (child, grandchild):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_no_guardian_is_left_after_a_normal_read(tmp_path):
    fake = tmp_path / "bin" / "ai-usagebar"
    fake.parent.mkdir()
    fake.write_text('#!/bin/sh\necho \'{"schema_version":1,"primary":null,"entries":[]}\'\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    marker = f"--max-secondary=7"
    env = dict(os.environ, PATH=f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    started = time.monotonic()
    r = subprocess.run([sys.executable, str(COLLECT), "--source", "ai-usagebar", marker],
                       env=env, capture_output=True, text=True, timeout=20)
    # The guardian must not hold stdout open: the read returns at once.
    assert r.returncode == 0, r.stderr
    assert time.monotonic() - started < 5
    time.sleep(0.6)
    out = subprocess.run(["pgrep", "-f", f"{COLLECT} --source ai-usagebar {marker}"],
                         capture_output=True, text=True).stdout.split()
    assert out == [], f"guardian still running: {out}"


# --- Guardian lifecycle (second review round of the store PR, 2026-11-20) ----
# The first guardian was forked AFTER the child and polled every 200 ms: a
# hard kill in between left the child unwatched, and a guardian that left early
# stayed a zombie while the collector ran.

def _children(pid: int) -> list[int]:
    try:
        with open(f"/proc/{pid}/task/{pid}/children") as fh:
            return [int(x) for x in fh.read().split()]
    except OSError:
        return []


def _state(pid: int) -> str:
    with open(f"/proc/{pid}/stat") as fh:
        return fh.read().rsplit(")", 1)[1].split()[0]


@pytest.mark.parametrize("round_", range(5))
def test_a_child_that_kills_its_parent_at_once_is_still_stopped(tmp_path, round_):
    """The narrowest window there is: the collector dies as early as the child
    can make it die. The guardian already exists by then."""
    fake = tmp_path / "bin" / "ai-usagebar"
    fake.parent.mkdir()
    fake.write_text('#!/bin/sh\nkill -9 $PPID\ntrap \'\' TERM\n'
                    'echo $$ > "$FAKE_PID"\nsleep 120 &\n'
                    'echo $! > "$FAKE_PID.child"\nwait\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    pidfile = tmp_path / "pid"
    child_file = Path(str(pidfile) + ".child")
    env = dict(os.environ, FAKE_PID=str(pidfile),
               PATH=f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    proc = subprocess.Popen([sys.executable, str(COLLECT), "--source", "ai-usagebar"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pids: list[int] = []
    try:
        assert proc.wait(timeout=10) == -signal.SIGKILL
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            pids = [int(f.read_text()) for f in (pidfile, child_file)
                    if f.exists() and f.read_text().strip()]
            if pids and not any(_alive(p) for p in pids):
                break
            time.sleep(0.05)
        # The child may be stopped before it writes anything; that is a pass.
        assert not any(_alive(p) for p in pids), "the child outlived its killed parent"
    finally:
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_the_guardian_is_alive_not_a_zombie_while_the_collector_runs(tmp_path):
    proc, child, grandchild = _start(tmp_path)
    try:
        time.sleep(0.6)  # longer than the old poll interval
        others = [p for p in _children(proc.pid) if p != child]
        assert len(others) == 1, f"expected one guardian, found {others}"
        assert _state(others[0]) != "Z", "the guardian is a zombie"
        guardian = others[0]
        # Created BEFORE the child, so the child never exists unwatched. Linux
        # hands out pids in increasing order; a wrap-around in between would
        # show as a huge gap, and then the order proves nothing.
        if abs(guardian - child) < 100_000:
            assert guardian < child, "the guardian was started after the child"
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=6)
        assert _wait_gone([child, grandchild, guardian], 3)
    finally:
        for pid in (child, grandchild):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_no_guardian_is_left_when_the_dependency_is_missing(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    marker = "--max-secondary=6"
    r = subprocess.run([sys.executable, str(COLLECT), "--source", "ai-usagebar", marker],
                       env=dict(os.environ, PATH=str(empty)), capture_output=True,
                       text=True, timeout=20)
    assert r.returncode not in (0, None)
    time.sleep(0.3)
    out = subprocess.run(["pgrep", "-f", f"{COLLECT} --source ai-usagebar {marker}"],
                         capture_output=True, text=True).stdout.split()
    assert out == [], f"guardian still running: {out}"
