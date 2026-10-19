"""Run a local open.mp (or SA-MP) server headlessly and report what happened.

Used for smoke tests ("does the gamemode boot without runtime errors?") and
for YSI y_testing suites (`#define RUN_TESTS` + `@test() Name() { ASSERT(...); }`).
The server is started on a free UDP port with announce/query disabled so it
never appears on the public server list, and is stopped when the script exits,
when y_testing prints its summary, when `stop_on` matches, or at the timeout.
"""
from __future__ import annotations

import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from .crashlog import analyze_log

YTEST_SUMMARY = re.compile(r"\*\*\* Tests?: (\d+), Checks?: (\d+), Fails?: (\d+|\?\?\?)")


def _free_udp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _find_server(server_dir: Path) -> tuple[Path | None, str]:
    for name, kind in (("omp-server.exe", "open.mp"), ("omp-server", "open.mp"),
                       ("samp-server.exe", "sa-mp"), ("samp03svr", "sa-mp")):
        p = server_dir / name
        if p.is_file():
            return p, kind
    return None, ""


def server_run(server_dir: str, script: str | None = None, amx_path: str | None = None, timeout_s: int = 30,
               stop_on: str | None = None, config: dict | None = None, max_output_lines: int = 400) -> dict:
    sd = Path(server_dir).expanduser().resolve()
    binary, kind = _find_server(sd)
    if not binary:
        return {"ok": False, "error": f"No omp-server or samp-server binary in {sd}."}
    timeout_s = max(5, min(int(timeout_s or 30), 600))

    copied = None
    if amx_path:
        src = Path(amx_path).expanduser().resolve()
        if not src.is_file():
            return {"ok": False, "error": f"AMX not found: {src}"}
        gm = sd / "gamemodes"
        gm.mkdir(exist_ok=True)
        if src.parent != gm:
            copied = gm / "_pawnforge_test.amx"
            shutil.copy2(src, copied)
            script = copied.stem
        else:
            script = src.stem

    args = [str(binary)]
    if kind == "open.mp":
        port = _free_udp_port()
        if script:
            args.append(script)
        overrides = {"network.port": port, "announce": "false", "enable_query": "false", "rcon.enable": "false"}
        overrides.update(config or {})
        for k, v in overrides.items():
            args += ["-c", f"{k}={v}"]
    else:
        if script or config:
            return {"ok": False, "error": "The SA-MP server has no command-line script/config overrides. Point "
                                          "server.cfg at the test gamemode, or test on open.mp (recommended)."}
        port = None

    stop_re = re.compile(stop_on) if stop_on else None
    env = dict(os.environ)
    env.setdefault("LD_LIBRARY_PATH", str(sd))
    t0 = time.time()
    try:
        proc = subprocess.Popen(args, cwd=sd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
    except OSError as exc:
        hint = ""
        if os.name != "nt":
            hint = (" The Linux server is 32-bit: install the i386 runtime (Debian/Ubuntu: "
                    "sudo apt install libc6-i386 lib32stdc++6 lib32atomic1).")
        if copied:
            copied.unlink(missing_ok=True)
        return {"ok": False, "error": f"Could not start {binary.name}: {exc}.{hint}"}

    q: "queue.Queue[str | None]" = queue.Queue()

    def pump():
        for line in proc.stdout:  # type: ignore[union-attr]
            q.put(line.rstrip("\n"))
        q.put(None)

    threading.Thread(target=pump, daemon=True).start()
    lines: list[str] = []
    reason = "timeout"
    summary = None
    deadline = t0 + timeout_s
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            line = q.get(timeout=min(0.5, remaining))
        except queue.Empty:
            if proc.poll() is not None and q.empty():
                reason = "exited"
                break
            continue
        if line is None:
            reason = "exited"
            break
        lines.append(line)
        m = YTEST_SUMMARY.search(line)
        if m:
            summary = {"tests": int(m.group(1)), "checks": int(m.group(2)),
                       "fails": None if m.group(3) == "???" else int(m.group(3))}
            reason = "tests_finished"
            # y_testing prints the failing test list and timing right after the summary.
            grace = time.time() + 1.5
            while time.time() < grace:
                try:
                    more = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                if more is None:
                    break
                lines.append(more)
                if "*** Time:" in more:
                    break
            break
        if stop_re and stop_re.search(line):
            reason = "stop_on_matched"
            break
        if re.search(r"(?i)segmentation fault|server crashed", line):
            reason = "crashed"

    if proc.poll() is None:
        try:
            proc.stdin.write("exit\n")  # type: ignore[union-attr]
            proc.stdin.flush()  # type: ignore[union-attr]
        except Exception:
            pass
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    # Drain anything printed during shutdown.
    while True:
        try:
            line = q.get_nowait()
        except queue.Empty:
            break
        if line is None:
            break
        lines.append(line)
    if copied:
        copied.unlink(missing_ok=True)
    for stream in (proc.stdin, proc.stdout):
        try:
            if stream:
                stream.close()
        except Exception:
            pass

    text = "\n".join(lines)
    analysis = analyze_log(text=text, source_root=str(sd))
    if summary is not None:
        clean = [re.sub(r"^(?:\s*\[[^\]]{1,40}\]\s*)+", "", l) for l in lines]
        summary["assert_failures"] = [l.strip() for l in clean if l.strip().startswith("FAIL:")][:50]
        after = False
        failed = []
        for l in clean:
            if YTEST_SUMMARY.search(l):
                after = True
                continue
            mm = re.match(r"^\s*-\s+(\S+)\s+\((\d+)\)", l)
            if after and mm:
                failed.append({"test": mm.group(1), "failed_checks": int(mm.group(2))})
        summary["failed_tests"] = failed
    script_errors = [l for l in lines if re.search(r"(?i)(could not|failed to|unable to) (load|find|open).*(script|amx|plugin|component)|"
                                                   r"script .* not found|invalid amx|file or function is not found", l)]
    result = {
        "ok": True,
        "server": kind,
        "command": " ".join(args),
        "port": port,
        "stop_reason": reason,
        "exit_code": proc.returncode,
        "elapsed_s": round(time.time() - t0, 2),
        "y_testing": summary,
        "passed": (summary is not None and summary["fails"] == 0) if summary else
                  (reason in ("exited", "stop_on_matched", "timeout") and not analysis["incidents"]
                   and not script_errors and reason != "crashed"),
        "script_errors": script_errors[:30],
        "runtime": {k: analysis[k] for k in ("incidents", "missing_natives", "plugin_failures")},
        "output_tail": lines[-max_output_lines:],
    }
    result["runtime_errors_detectable"] = any("crashdetect" in l.lower() for l in lines)
    if not result["runtime_errors_detectable"]:
        result["note"] =("CrashDetect is not loaded: runtime errors (out-of-bounds, divide by zero) may be "
                          "silently swallowed. Add it to pawn.legacy_plugins and compile with -d3 for backtraces.")
    return result
