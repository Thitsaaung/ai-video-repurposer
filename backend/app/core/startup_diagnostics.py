"""Temporary Railway startup diagnostics — safe to delete after investigation.

Does not alter download, pipeline, or job business logic.
"""

from __future__ import annotations

import glob
import logging
import subprocess
import sys
from pathlib import Path

from app.core.config import resolve_youtube_cookiefile

logger = logging.getLogger(__name__)

# Short, publicly known YouTube sample (list-formats only; no full download).
_DIAG_VIDEO_URL = "https://youtu.be/jNQXAC9IVRw"


def _emit(label: str, text: str) -> None:
    """Print and log diagnostic output (Railway captures both)."""
    for line in (text or "").splitlines() or [""]:
        print(f"[DIAG startup {label}] {line}", flush=True)
    logger.info("DIAG startup %s:\n%s", label, text or "(empty)")


def _run_captured(argv: list[str], *, timeout_s: float = 60.0) -> None:
    cmd_display = " ".join(argv)
    print(f"[DIAG startup] $ {cmd_display}", flush=True)
    logger.info("DIAG startup running: %s", cmd_display)
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        msg = f"command not found: {argv[0]!r} ({exc})"
        _emit("error", msg)
        return
    except subprocess.TimeoutExpired as exc:
        _emit("timeout", f"timed out after {timeout_s}s: {cmd_display}")
        if exc.stdout:
            _emit("stdout", exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", "replace"))
        if exc.stderr:
            _emit("stderr", exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", "replace"))
        return
    except Exception as exc:
        _emit("error", f"{type(exc).__name__}: {exc}")
        logger.exception("DIAG startup command failed: %s", cmd_display)
        return

    _emit("returncode", str(completed.returncode))
    _emit("stdout", completed.stdout or "")
    _emit("stderr", completed.stderr or "")


def _resolve_diag_cookiefile() -> str | None:
    """
    Prefer resolve_youtube_cookiefile(), then /tmp/yt_cookies_*.txt glob.

    Never logs cookie contents.
    """
    resolved = resolve_youtube_cookiefile()
    if resolved and Path(resolved).is_file():
        logger.info("DIAG startup cookiefile from resolve: %s", resolved)
        return resolved

    matches = sorted(glob.glob("/tmp/yt_cookies_*.txt"))
    logger.info(
        "DIAG startup cookie glob /tmp/yt_cookies_*.txt matches=%s",
        matches,
    )
    for path in matches:
        if Path(path).is_file():
            return path
    return None


def run_startup_diagnostics() -> None:
    """Run temporary toolchain + cookie list-formats probes. Never raises."""
    print("[DIAG startup] begin temporary diagnostics", flush=True)
    logger.info("DIAG startup: begin temporary diagnostics")

    try:
        _run_captured(["yt-dlp", "--version"], timeout_s=30.0)
        _run_captured(["ffmpeg", "-version"], timeout_s=30.0)
        _run_captured(
            [
                sys.executable,
                "-c",
                "import yt_dlp; print(yt_dlp.version.__version__)",
            ],
            timeout_s=30.0,
        )

        cookiefile = _resolve_diag_cookiefile()
        if not cookiefile:
            msg = (
                "No cookie file for yt-dlp -F probe "
                "(resolve_youtube_cookiefile returned None and "
                "/tmp/yt_cookies_*.txt matched nothing). Skipping format list."
            )
            _emit("cookies", msg)
            return

        size = Path(cookiefile).stat().st_size
        _emit(
            "cookies",
            f"using cookiefile={cookiefile} size_bytes={size} "
            f"(contents not logged)",
        )
        # Equivalent to: yt-dlp --cookies /tmp/yt_cookies_*.txt -F <url>
        # (glob expanded to a concrete path for subprocess; no shell).
        _run_captured(
            [
                "yt-dlp",
                "--cookies",
                cookiefile,
                "-F",
                _DIAG_VIDEO_URL,
            ],
            timeout_s=120.0,
        )
    except Exception:
        logger.exception("DIAG startup: unexpected failure (ignored)")
        print("[DIAG startup] unexpected failure (ignored)", flush=True)
    finally:
        print("[DIAG startup] end temporary diagnostics", flush=True)
        logger.info("DIAG startup: end temporary diagnostics")
