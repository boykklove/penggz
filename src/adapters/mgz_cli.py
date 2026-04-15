from __future__ import annotations

import json
import subprocess
from pathlib import Path


class MGZCliError(RuntimeError):
    pass


def _run_cmd(cmd: list[str], timeout_sec: int = 30) -> dict:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise MGZCliError(f"command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")

    stdout = proc.stdout.strip()
    if not stdout:
        raise MGZCliError(f"empty output from command: {' '.join(cmd)}")

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise MGZCliError(f"invalid JSON from command: {' '.join(cmd)}") from exc


def extract_summary_from_rec(rec_path: Path) -> dict:
    # Try common CLI forms used by mgz/aoc-mgz wrappers.
    candidates = [
        ["mgz", "summary", str(rec_path), "--json"],
        ["mgz", "--json", str(rec_path)],
        ["python", "-m", "mgz", "summary", str(rec_path), "--json"],
    ]

    errors = []
    for cmd in candidates:
        try:
            result = _run_cmd(cmd)
            if isinstance(result, dict):
                return result
            errors.append(f"non-object JSON from: {' '.join(cmd)}")
        except (MGZCliError, FileNotFoundError) as exc:
            errors.append(str(exc))

    raise MGZCliError(
        "Failed to parse replay via mgz CLI. "
        "Install `mgz`/`aoc-mgz`, or run with --summary-json. "
        f"Tried {len(candidates)} command variants.\n"
        + "\n".join(errors)
    )
