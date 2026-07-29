"""Automatic storage cleanup and retention for pipeline artifacts.

Deletes only files under known backend directories, never touches active
(queued/processing) jobs or paths they reference. Failures are logged and
skipped so cleanup never crashes the API process.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.core.config import Settings, get_settings
from app.core.enums import JobStatus
from app.services import job_store

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = frozenset(
    {JobStatus.QUEUED.value, JobStatus.PROCESSING.value},
)

# Shared pipeline temps at backend root (never delete cookies / source).
_TEMP_NAME_EXACT = frozenset({"temp.srt", "temp_audio.mp3"})
_TEMP_PREFIXES = ("temp_",)
_TEMP_SUFFIXES = (".srt", ".mp3")

_NEVER_DELETE_NAMES = frozenset(
    {
        "cookies.txt",
        "cookies.example.txt",
        "extension_cookies.txt",
        ".env",
        ".env.example",
    }
)

_scheduler_stop = threading.Event()
_scheduler_thread: threading.Thread | None = None
_scheduler_lock = threading.Lock()


@dataclass
class CleanupConfig:
    """Resolved retention policy and directories (injectable for tests)."""

    backend_root: Path
    downloads_dir: Path
    transcripts_dir: Path
    output_clips_dir: Path
    downloads_retention: timedelta
    transcripts_retention: timedelta
    clips_retention: timedelta
    temp_retention: timedelta
    failed_job_retention: timedelta
    completed_job_retention: timedelta
    now: datetime | None = None
    dry_run: bool = False

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        now: datetime | None = None,
        dry_run: bool = False,
    ) -> CleanupConfig:
        root = settings.project_root
        return cls(
            backend_root=root,
            downloads_dir=settings.downloads_dir,
            transcripts_dir=settings.transcripts_dir,
            output_clips_dir=settings.output_clips_dir,
            downloads_retention=timedelta(
                hours=settings.storage_downloads_retention_hours,
            ),
            transcripts_retention=timedelta(
                hours=settings.storage_transcripts_retention_hours,
            ),
            clips_retention=timedelta(hours=settings.storage_clips_retention_hours),
            temp_retention=timedelta(hours=settings.storage_temp_retention_hours),
            failed_job_retention=timedelta(
                hours=settings.storage_failed_job_retention_hours,
            ),
            completed_job_retention=timedelta(
                hours=settings.storage_completed_job_retention_hours,
            ),
            now=now,
            dry_run=dry_run,
        )


@dataclass
class CleanupReport:
    """Summary of one cleanup pass (for logs and tests)."""

    deleted_files: list[str] = field(default_factory=list)
    deleted_jobs: list[str] = field(default_factory=list)
    skipped_protected: list[str] = field(default_factory=list)
    skipped_active_temps: bool = False
    errors: list[str] = field(default_factory=list)
    bytes_freed: int = 0
    categories: dict[str, int] = field(default_factory=dict)

    def bump(self, category: str, count: int = 1) -> None:
        self.categories[category] = self.categories.get(category, 0) + count


def _utc_now(config: CleanupConfig) -> datetime:
    if config.now is not None:
        return config.now if config.now.tzinfo else config.now.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _job_timestamp(job: dict[str, Any]) -> datetime | None:
    return _parse_iso(job.get("updated_at")) or _parse_iso(job.get("created_at"))


def _resolve_safe(path_value: object) -> Path | None:
    if not path_value or not isinstance(path_value, str):
        return None
    try:
        return Path(path_value).expanduser().resolve()
    except OSError:
        return None


def collect_protected_paths(jobs: list[dict[str, Any]]) -> set[Path]:
    """Absolute paths referenced by any in-memory job (all statuses)."""
    protected: set[Path] = set()
    for job in jobs:
        for key in ("video_path", "curated_json_path"):
            resolved = _resolve_safe(job.get(key))
            if resolved is not None:
                protected.add(resolved)
        clips = job.get("output_clip_paths") or []
        if isinstance(clips, list):
            for clip in clips:
                # Public URLs like /media/clips/foo.mp4 → basename only
                if isinstance(clip, str) and ("/" in clip or "\\" in clip):
                    name = Path(clip).name
                    if name:
                        # Protect by basename match later; also try resolve
                        resolved = _resolve_safe(clip)
                        if resolved is not None:
                            protected.add(resolved)
                        protected.add(Path(name))  # marker for basename check
                else:
                    resolved = _resolve_safe(clip)
                    if resolved is not None:
                        protected.add(resolved)
    return protected


def _is_protected(path: Path, protected: set[Path]) -> bool:
    if path in protected:
        return True
    if Path(path.name) in protected:
        return True
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return resolved in protected


def _is_under_dir(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except (ValueError, OSError):
        return False


def _file_mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _is_expired(mtime: datetime, now: datetime, retention: timedelta) -> bool:
    return mtime <= (now - retention)


def _safe_unlink(
    path: Path,
    *,
    allowed_root: Path,
    config: CleanupConfig,
    report: CleanupReport,
    category: str,
) -> bool:
    """Delete ``path`` only if it is a file under ``allowed_root``."""
    name = path.name
    if name in _NEVER_DELETE_NAMES or name.startswith("."):
        report.skipped_protected.append(str(path))
        return False

    try:
        resolved = path.resolve()
    except OSError as exc:
        report.errors.append(f"resolve:{path}:{exc}")
        logger.warning("Cleanup skip (resolve failed) path=%s err=%s", path, exc)
        return False

    if not _is_under_dir(resolved, allowed_root):
        report.errors.append(f"outside_root:{resolved}")
        logger.error(
            "Cleanup refused path outside allowed root path=%s root=%s",
            resolved,
            allowed_root,
        )
        return False

    if not resolved.is_file():
        return False

    try:
        size = resolved.stat().st_size
    except OSError:
        size = 0

    if config.dry_run:
        logger.info(
            "Cleanup dry_run category=%s would_delete=%s bytes=%s",
            category,
            resolved,
            size,
        )
        report.deleted_files.append(str(resolved))
        report.bytes_freed += size
        report.bump(category)
        return True

    try:
        resolved.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        report.errors.append(f"unlink:{resolved}:{exc}")
        logger.warning(
            "Cleanup failed to delete path=%s category=%s err=%s",
            resolved,
            category,
            exc,
        )
        return False

    logger.info(
        "Cleanup deleted category=%s path=%s bytes=%s",
        category,
        resolved,
        size,
    )
    report.deleted_files.append(str(resolved))
    report.bytes_freed += size
    report.bump(category)
    return True


def _is_temp_filename(name: str) -> bool:
    if name in _TEMP_NAME_EXACT:
        return True
    lower = name.lower()
    if not any(lower.endswith(suf) for suf in _TEMP_SUFFIXES):
        return False
    return any(lower.startswith(prefix) for prefix in _TEMP_PREFIXES)


def cleanup_temp_files(
    config: CleanupConfig,
    *,
    any_active_job: bool,
    report: CleanupReport,
) -> None:
    """Remove leftover ``temp.srt`` / ``temp_audio.mp3`` / ``temp_*`` at backend root."""
    if any_active_job:
        report.skipped_active_temps = True
        logger.info(
            "Cleanup skipping temp files — active job present "
            "(shared temp.srt / temp_audio.mp3 may be in use)",
        )
        return

    now = _utc_now(config)
    root = config.backend_root
    if not root.is_dir():
        return

    try:
        entries = list(root.iterdir())
    except OSError as exc:
        report.errors.append(f"list_temps:{exc}")
        logger.warning("Cleanup could not list backend root temps: %s", exc)
        return

    for entry in entries:
        if not entry.is_file() or not _is_temp_filename(entry.name):
            continue
        mtime = _file_mtime(entry)
        if mtime is None or not _is_expired(mtime, now, config.temp_retention):
            continue
        _safe_unlink(
            entry,
            allowed_root=root,
            config=config,
            report=report,
            category="temp",
        )


def cleanup_directory(
    directory: Path,
    *,
    retention: timedelta,
    config: CleanupConfig,
    protected: set[Path],
    report: CleanupReport,
    category: str,
) -> None:
    """Delete expired files under ``directory`` that are not job-protected."""
    if not directory.is_dir():
        return

    now = _utc_now(config)
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        report.errors.append(f"list:{directory}:{exc}")
        logger.warning("Cleanup could not list %s: %s", directory, exc)
        return

    for entry in entries:
        if not entry.is_file():
            continue
        if _is_protected(entry, protected):
            report.skipped_protected.append(str(entry))
            logger.debug(
                "Cleanup skip protected category=%s path=%s",
                category,
                entry,
            )
            continue
        mtime = _file_mtime(entry)
        if mtime is None or not _is_expired(mtime, now, retention):
            continue
        # Age-expired and not referenced → orphan (or simply expired artifact).
        orphan_category = f"{category}_orphan" if category != "temp" else category
        _safe_unlink(
            entry,
            allowed_root=directory,
            config=config,
            report=report,
            category=orphan_category,
        )


def purge_expired_jobs(
    jobs: list[dict[str, Any]],
    config: CleanupConfig,
    *,
    delete_job: Callable[[str], bool],
    report: CleanupReport,
) -> None:
    """Remove expired failed/completed jobs from memory. Never active jobs."""
    now = _utc_now(config)
    for job in jobs:
        job_id = str(job.get("job_id") or "")
        if not job_id:
            continue
        status = job.get("status")
        if status in _ACTIVE_STATUSES:
            continue

        stamp = _job_timestamp(job)
        if stamp is None:
            logger.warning(
                "Cleanup skip job without timestamp job_id=%s",
                job_id,
            )
            continue

        if status == JobStatus.FAILED.value:
            retention = config.failed_job_retention
            category = "failed_job"
        elif status == JobStatus.COMPLETED.value:
            retention = config.completed_job_retention
            category = "completed_job"
        else:
            continue

        if not _is_expired(stamp, now, retention):
            continue

        if config.dry_run:
            logger.info(
                "Cleanup dry_run would_purge_job job_id=%s status=%s",
                job_id,
                status,
            )
            report.deleted_jobs.append(job_id)
            report.bump(category)
            continue

        try:
            removed = delete_job(job_id)
        except Exception as exc:  # noqa: BLE001 — graceful per-job failure
            report.errors.append(f"delete_job:{job_id}:{exc}")
            logger.warning(
                "Cleanup failed to purge job_id=%s err=%s",
                job_id,
                exc,
            )
            continue

        if removed:
            logger.info(
                "Cleanup purged job_id=%s status=%s category=%s",
                job_id,
                status,
                category,
            )
            report.deleted_jobs.append(job_id)
            report.bump(category)
        else:
            logger.warning(
                "Cleanup did not purge job_id=%s (still active or missing)",
                job_id,
            )


def run_cleanup(
    config: CleanupConfig,
    *,
    jobs: list[dict[str, Any]] | None = None,
    delete_job: Callable[[str], bool] | None = None,
) -> CleanupReport:
    """
    Run one full cleanup pass.

    Order: purge expired terminal jobs → refresh protected set → temps →
    downloads → transcripts → output clips.
    """
    report = CleanupReport()
    job_list = list(jobs) if jobs is not None else job_store.list_jobs()
    delete_cb = delete_job or job_store.delete_job

    any_active = any(j.get("status") in _ACTIVE_STATUSES for j in job_list)

    try:
        purge_expired_jobs(
            job_list,
            config,
            delete_job=delete_cb,
            report=report,
        )
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"purge_jobs:{exc}")
        logger.exception("Cleanup job purge failed: %s", exc)

    # Re-read jobs after purge so protected paths stay accurate.
    if jobs is None:
        job_list = job_store.list_jobs()
    else:
        purged = set(report.deleted_jobs)
        job_list = [j for j in job_list if str(j.get("job_id")) not in purged]

    protected = collect_protected_paths(job_list)
    logger.info(
        "Cleanup pass start dry_run=%s active_jobs=%s protected_paths=%s "
        "jobs_in_memory=%s",
        config.dry_run,
        any_active,
        len(protected),
        len(job_list),
    )

    try:
        cleanup_temp_files(config, any_active_job=any_active, report=report)
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"temps:{exc}")
        logger.exception("Cleanup temps failed: %s", exc)

    for directory, retention, category in (
        (config.downloads_dir, config.downloads_retention, "downloads"),
        (config.transcripts_dir, config.transcripts_retention, "transcripts"),
        (config.output_clips_dir, config.clips_retention, "clips"),
    ):
        try:
            cleanup_directory(
                directory,
                retention=retention,
                config=config,
                protected=protected,
                report=report,
                category=category,
            )
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"{category}:{exc}")
            logger.exception("Cleanup %s failed: %s", category, exc)

    logger.info(
        "Cleanup pass done deleted_files=%s deleted_jobs=%s bytes_freed=%s "
        "skipped_protected=%s errors=%s categories=%s",
        len(report.deleted_files),
        len(report.deleted_jobs),
        report.bytes_freed,
        len(report.skipped_protected),
        len(report.errors),
        report.categories,
    )
    return report


def run_cleanup_from_settings(*, dry_run: bool = False) -> CleanupReport | None:
    """Load settings and run cleanup when enabled."""
    settings = get_settings()
    if not settings.storage_cleanup_enabled:
        logger.info("Storage cleanup disabled (STORAGE_CLEANUP_ENABLED=false)")
        return None
    config = CleanupConfig.from_settings(settings, dry_run=dry_run)
    try:
        return run_cleanup(config)
    except Exception:
        logger.exception("Storage cleanup pass crashed (ignored)")
        return None


def _scheduler_loop(interval_seconds: float) -> None:
    logger.info(
        "Storage cleanup scheduler started interval_s=%.0f",
        interval_seconds,
    )
    while not _scheduler_stop.wait(timeout=interval_seconds):
        run_cleanup_from_settings()
    logger.info("Storage cleanup scheduler stopped")


def start_cleanup_scheduler() -> None:
    """Start daemon thread for periodic cleanup (idempotent)."""
    global _scheduler_thread
    settings = get_settings()
    if not settings.storage_cleanup_enabled:
        logger.info("Storage cleanup scheduler not started (disabled)")
        return

    interval = max(60.0, float(settings.storage_cleanup_interval_minutes) * 60.0)
    with _scheduler_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            logger.info("Storage cleanup scheduler already running")
            return
        _scheduler_stop.clear()
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(interval,),
            name="storage-cleanup",
            daemon=True,
        )
        _scheduler_thread.start()


def stop_cleanup_scheduler() -> None:
    """Signal the scheduler to stop (used by tests)."""
    _scheduler_stop.set()


def run_startup_cleanup() -> None:
    """Best-effort cleanup at API startup, then start the periodic scheduler."""
    run_cleanup_from_settings()
    start_cleanup_scheduler()
