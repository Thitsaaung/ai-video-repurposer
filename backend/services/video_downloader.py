"""Download videos from a URL using yt-dlp (best quality up to 1080p)."""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from pathlib import Path

import yt_dlp

from app.core.config import get_settings, resolve_youtube_cookiefile

logger = logging.getLogger(__name__)

# backend/downloads — independent of the caller's working directory
DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"

# Best video + best audio, capped at 1080p; fall back to best combined ≤1080p
FORMAT_SELECTOR = "bv*[height<=1080]+ba/b[height<=1080]"

# Sprint #6A — yt-dlp-native resilience (finite retries; no outer job loops).
# retry_sleep_functions matches CLI: --retry-sleep linear=1::2
# and --retry-sleep fragment:exp=1:20 (see yt-dlp YoutubeDL docs).
_DOWNLOAD_SOCKET_TIMEOUT = 30
_DOWNLOAD_RETRIES = 10
_DOWNLOAD_FRAGMENT_RETRIES = 10

# Stable Chrome desktop UA — cookies are typically exported from a browser;
# pairing them with yt-dlp's default UA looks more automated on cloud IPs.
_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Light pacing only — enough to reduce bursty extract/request patterns on
# Railway without making single-video downloads feel slow.
_SLEEP_INTERVAL_REQUESTS_S = 1.0
_SLEEP_INTERVAL_S = 1.0

# Cookie-compatible YouTube Innertube clients (yt-dlp 2026.x authenticated defaults).
# Do not use android/ios here — those clients do not support account cookies.
_YOUTUBE_PLAYER_CLIENTS = ("tv_downgraded", "web_safari", "web")


def _http_retry_sleep(attempt: int) -> float:
    """Linear backoff: 1, 3, 5, … seconds (CLI linear=1::2)."""
    return 1.0 + 2.0 * float(attempt)


def _fragment_retry_sleep(attempt: int) -> float:
    """Exponential backoff capped at 20s (CLI fragment:exp=1:20)."""
    return min(1.0 * (2.0 ** float(attempt)), 20.0)


def _detect_js_runtimes() -> dict[str, dict]:
    """
    Enable yt-dlp JS runtimes that are present on PATH.

    yt-dlp defaults to deno only; Railway typically installs Node via
    ``RAILPACK_PACKAGES=node``, which must be enabled explicitly.
    """
    runtimes: dict[str, dict] = {}
    # Prefer deno when present (yt-dlp default), always enable node when present.
    if shutil.which("deno"):
        runtimes["deno"] = {}
    if shutil.which("node"):
        runtimes["node"] = {}
    return runtimes


class _YtDlpAuthDiagLogger:
    """
    Temporary yt-dlp logger — captures auth/client debug lines only.

    Never logs cookie values or secrets. Remove after debugging.
    """

    _INTEREST_SUBSTR = (
        "account cookie",
        "youtube account",
        "no longer valid",
        "player api json",
        "client config",
        "player client",
        "sign in to confirm",
        "login_required",
        "login required",
        "cookies are",
    )

    _SECRET_MARKERS = (
        "\t",
        "SID=",
        "HSID=",
        "SSID=",
        "APISID=",
        "SAPISID=",
        "__Secure-",
        "LOGIN_INFO",
        "cookie: ",
        "Cookie: ",
    )

    def __init__(self) -> None:
        self.account_cookies_found = False
        self.account_cookies_invalid = False
        self.observed_clients: list[str] = []

    def _looks_secret(self, message: str) -> bool:
        if any(marker in message for marker in self._SECRET_MARKERS):
            return True
        # Netscape cookie lines / huge dumps
        if "cookie" in message.lower() and len(message) > 400:
            return True
        return False

    def _interesting(self, message: str) -> bool:
        low = message.lower()
        return any(token in low for token in self._INTEREST_SUBSTR)

    def _track(self, message: str) -> None:
        low = message.lower()
        if "found youtube account cookies" in low:
            self.account_cookies_found = True
        if "no longer valid" in low and "cookie" in low:
            self.account_cookies_invalid = True

        for pattern in (
            r"Downloading (.+?) player API JSON",
            r"Downloading (.+?) client config",
        ):
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if not match:
                continue
            client = match.group(1).strip().replace(" ", "_")
            if client and client not in self.observed_clients:
                self.observed_clients.append(client)

    def _emit(self, message: object) -> None:
        text = str(message)
        if self._looks_secret(text):
            logger.info("DIAG yt-dlp: [message redacted — possible secret content]")
            return
        self._track(text)
        if self._interesting(text):
            logger.info("DIAG yt-dlp: %s", text)

    def debug(self, msg: object) -> None:
        self._emit(msg)

    def info(self, msg: object) -> None:
        self._emit(msg)

    def warning(self, msg: object) -> None:
        self._emit(msg)

    def error(self, msg: object) -> None:
        self._emit(msg)

    def summary_log(self, *, configured_clients: tuple[str, ...]) -> None:
        logger.info(
            "DIAG yt-dlp auth summary: account_cookies_found=%s "
            "account_cookies_invalid=%s configured_player_client=%s "
            "observed_clients=%s",
            self.account_cookies_found,
            self.account_cookies_invalid,
            ",".join(configured_clients),
            ",".join(self.observed_clients) if self.observed_clients else "none",
        )


def _format_exception_chain(exc: BaseException) -> str:
    """Flatten __cause__ / __context__ for log lines (diagnostics only)."""
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    depth = 0
    while current is not None and id(current) not in seen and depth < 8:
        seen.add(id(current))
        parts.append(
            f"{type(current).__module__}.{type(current).__name__}: {current!s}"
        )
        nxt = current.__cause__ or (
            current.__context__ if not current.__suppress_context__ else None
        )
        current = nxt
        depth += 1
    return " | caused by: ".join(parts) if parts else repr(exc)


def _log_download_failure(
    *,
    url: str,
    elapsed_s: float,
    exc: BaseException,
    kind: str,
) -> None:
    """
    Log full download failure diagnostics for operators.

    Does not alter the exception or any client-facing message.
    """
    exc_type = f"{type(exc).__module__}.{type(exc).__name__}"
    cause = exc.__cause__
    context = exc.__context__ if not getattr(exc, "__suppress_context__", False) else None
    logger.error(
        "Download %s failed url=%s elapsed_s=%.3f "
        "exc_type=%s exc_message=%r exc_repr=%r exc_args=%r "
        "cause_type=%s cause_message=%r "
        "context_type=%s context_message=%r "
        "exception_chain=%s",
        kind,
        url,
        elapsed_s,
        exc_type,
        str(exc),
        repr(exc),
        getattr(exc, "args", ()),
        f"{type(cause).__module__}.{type(cause).__name__}" if cause else None,
        str(cause) if cause else None,
        f"{type(context).__module__}.{type(context).__name__}" if context else None,
        str(context) if context else None,
        _format_exception_chain(exc),
        exc_info=exc,
    )


def _youtube_cookies_base64_configured() -> bool:
    """True when YOUTUBE_COOKIES_BASE64 is set (value never logged)."""
    settings = get_settings()
    if settings.youtube_cookies_base64:
        return True
    for key, value in os.environ.items():
        if key.upper() == "YOUTUBE_COOKIES_BASE64":
            return bool(isinstance(value, str) and value.strip())
    return False


def _log_pre_download_cookie_diagnostics(
    *,
    cookie_path: str | None,
    ydl_opts: dict,
) -> None:
    """
    Temporary pre-yt-dlp cookie diagnostics for Railway operators.

    Never logs cookie file contents — only presence, paths, and sizes.
    """
    b64_exists = _youtube_cookies_base64_configured()
    path_obj = Path(cookie_path) if cookie_path else None
    file_exists = bool(path_obj and path_obj.is_file())
    size_bytes: int | None
    if file_exists and path_obj is not None:
        try:
            size_bytes = path_obj.stat().st_size
        except OSError:
            size_bytes = None
    else:
        size_bytes = None

    cookiefile_set = "cookiefile" in ydl_opts and bool(ydl_opts.get("cookiefile"))
    cookiefile_value = ydl_opts.get("cookiefile") if cookiefile_set else None

    # Temp files from base64 use prefix yt_cookies_ (see _write_cookies_from_base64).
    from_base64_temp = bool(
        path_obj is not None and path_obj.name.startswith("yt_cookies_"),
    )

    if not b64_exists:
        decode_succeeded = False
        decode_note = "YOUTUBE_COOKIES_BASE64 not set (decode skipped)"
    elif from_base64_temp and file_exists and size_bytes is not None and size_bytes > 0:
        decode_succeeded = True
        decode_note = "base64 materialized to temp cookie file"
    elif from_base64_temp and cookie_path and not file_exists:
        decode_succeeded = False
        decode_note = "base64 resolve returned a path but file is missing on disk"
    elif cookie_path and file_exists and not from_base64_temp:
        decode_succeeded = False
        decode_note = (
            "YOUTUBE_COOKIES_BASE64 is set but this run used YOUTUBE_COOKIES_FILE "
            "instead (base64 decode not used)"
        )
    else:
        decode_succeeded = False
        decode_note = (
            "YOUTUBE_COOKIES_BASE64 is set but no usable cookie file after resolve "
            "(decode/materialize failed — see earlier DIAG / exception logs)"
        )

    logger.info(
        "DIAG cookie pre-yt-dlp: "
        "YOUTUBE_COOKIES_BASE64_exists=%s "
        "decode_succeeded=%s "
        "decode_note=%s "
        "cookie_path=%s "
        "cookie_file_exists=%s "
        "cookie_file_size_bytes=%s "
        "ydl_opts_cookiefile_set=%s "
        "ydl_opts_cookiefile=%s",
        b64_exists,
        decode_succeeded,
        decode_note,
        cookie_path,
        file_exists,
        size_bytes,
        cookiefile_set,
        cookiefile_value,
    )

    if cookiefile_set:
        return

    # Explain why cookiefile is missing from yt-dlp options (implementation unchanged).
    if not b64_exists and not cookie_path:
        why = (
            "ydl_opts['cookiefile'] not set because no cookie source resolved "
            "(YOUTUBE_COOKIES_BASE64 and YOUTUBE_COOKIES_FILE both unavailable "
            "or empty)."
        )
    elif b64_exists and not cookie_path:
        why = (
            "ydl_opts['cookiefile'] not set because YOUTUBE_COOKIES_BASE64 is "
            "configured but resolve_youtube_cookiefile() returned None "
            "(decode/materialize failed — see earlier DIAG / exception logs)."
        )
    elif cookie_path and not file_exists:
        why = (
            f"ydl_opts['cookiefile'] not set because resolved path does not "
            f"exist on disk: {cookie_path}"
        )
    else:
        why = (
            "ydl_opts['cookiefile'] not set for an unexpected reason — "
            f"cookie_path={cookie_path!r} file_exists={file_exists} "
            f"b64_exists={b64_exists}"
        )
    logger.warning("DIAG cookie pre-yt-dlp: %s", why)


def download_video(url: str, output_dir: Path | str | None = None) -> str:
    """
    Download a video from ``url`` and return the local file path.

    Uses yt-dlp to fetch the best video and audio streams (up to 1080p),
    merges them into a single file under ``downloads/``, and returns that path.
    """
    if not url or not str(url).strip():
        raise ValueError("A non-empty video URL is required.")

    dest = Path(output_dir) if output_dir is not None else DOWNLOADS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    js_runtimes = _detect_js_runtimes()
    if js_runtimes:
        logger.info(
            "yt-dlp JS runtime detected: %s",
            ", ".join(sorted(js_runtimes.keys())),
        )
    else:
        logger.info(
            "yt-dlp JS runtime detected: none "
            "(install Node on Railway via RAILPACK_PACKAGES=node)",
        )

    logger.info(
        "yt-dlp youtube player_client=%s",
        ",".join(_YOUTUBE_PLAYER_CLIENTS),
    )

    ydl_opts: dict = {
        "format": FORMAT_SELECTOR,
        "outtmpl": str(dest / "%(title)s [%(id)s].%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        # Temporary: enable yt-dlp debug so account-cookie / client lines surface.
        "verbose": True,
        # Sprint #6A — finite yt-dlp-native resilience (no outer job retries).
        "socket_timeout": _DOWNLOAD_SOCKET_TIMEOUT,
        "retries": _DOWNLOAD_RETRIES,
        "fragment_retries": _DOWNLOAD_FRAGMENT_RETRIES,
        "retry_sleep_functions": {
            "http": _http_retry_sleep,
            "fragment": _fragment_retry_sleep,
        },
        # Minimal browser identity + light request pacing (429 mitigation).
        "http_headers": {
            "User-Agent": _CHROME_USER_AGENT,
        },
        "sleep_interval_requests": _SLEEP_INTERVAL_REQUESTS_S,
        "sleep_interval": _SLEEP_INTERVAL_S,
        # Cookie-compatible clients for cloud + browser-exported cookies.
        "extractor_args": {
            "youtube": {
                "player_client": list(_YOUTUBE_PLAYER_CLIENTS),
            },
        },
    }
    # Temporary auth/client diagnostics (no cookie values). Remove after debugging.
    auth_diag = _YtDlpAuthDiagLogger()
    ydl_opts["logger"] = auth_diag

    if js_runtimes:
        # Enable Node when present — yt-dlp's default is deno-only.
        ydl_opts["js_runtimes"] = js_runtimes

    cookie_path = resolve_youtube_cookiefile()
    if cookie_path:
        cookie_file = Path(cookie_path)
        if cookie_file.is_file():
            logger.info("YouTube cookies loaded")
            logger.info("Cookie file exists")
            logger.info("Using cookiefile: %s", cookie_path)
            ydl_opts["cookiefile"] = cookie_path
        else:
            logger.warning(
                "Resolved cookie path does not exist on disk: %s",
                cookie_path,
            )
            logger.info("No YouTube cookies configured")
    else:
        logger.info("No YouTube cookies configured")

    # Temporary diagnostics immediately before yt-dlp (no cookie contents).
    _log_pre_download_cookie_diagnostics(
        cookie_path=cookie_path,
        ydl_opts=ydl_opts,
    )
    logger.info(
        "DIAG yt-dlp: configured extractor player_client=%s",
        ",".join(_YOUTUBE_PLAYER_CLIENTS),
    )

    started = time.perf_counter()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise RuntimeError(f"yt-dlp returned no info for URL: {url}")

            # Prefer the post-merge filepath when available
            requested = info.get("requested_downloads") or []
            if requested and requested[0].get("filepath"):
                filepath = requested[0]["filepath"]
            else:
                filepath = ydl.prepare_filename(info)
                # After merge, extension may be mp4 even if prepare_filename differs
                if info.get("ext"):
                    filepath = str(Path(filepath).with_suffix(f".{info['ext']}"))

            resolved = str(Path(filepath).resolve())
            logger.info(
                "Downloaded video to %s elapsed_s=%.3f",
                resolved,
                time.perf_counter() - started,
            )
            return resolved

    except yt_dlp.utils.DownloadError as exc:
        _log_download_failure(
            url=url,
            elapsed_s=time.perf_counter() - started,
            exc=exc,
            kind="yt-dlp.DownloadError",
        )
        raise
    except Exception as exc:
        _log_download_failure(
            url=url,
            elapsed_s=time.perf_counter() - started,
            exc=exc,
            kind="unexpected",
        )
        raise
    finally:
        auth_diag.summary_log(configured_clients=_YOUTUBE_PLAYER_CLIENTS)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Short Creative Commons sample — replace with any YouTube URL to test
    sample_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

    print(f"Downloading: {sample_url}")
    path = download_video(sample_url)
    print(f"Saved to: {path}")
