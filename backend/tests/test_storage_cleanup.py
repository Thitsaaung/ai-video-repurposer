"""Unit tests for storage cleanup and retention policy."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.enums import JobStatus
from app.services.storage_cleanup import (
    CleanupConfig,
    collect_protected_paths,
    run_cleanup,
)


def _touch(path: Path, *, mtime: datetime, content: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    ts = mtime.timestamp()
    os.utime(path, (ts, ts))
    return path


class TestStorageCleanup(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.downloads = self.root / "downloads"
        self.transcripts = self.root / "transcripts"
        self.clips = self.root / "output_clips"
        for d in (self.downloads, self.transcripts, self.clips):
            d.mkdir(parents=True, exist_ok=True)
        self.now = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)
        self.config = CleanupConfig(
            backend_root=self.root,
            downloads_dir=self.downloads,
            transcripts_dir=self.transcripts,
            output_clips_dir=self.clips,
            downloads_retention=timedelta(hours=24),
            transcripts_retention=timedelta(hours=24),
            clips_retention=timedelta(hours=48),
            temp_retention=timedelta(hours=1),
            failed_job_retention=timedelta(hours=12),
            completed_job_retention=timedelta(hours=48),
            now=self.now,
            dry_run=False,
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_deletes_expired_download_and_keeps_fresh(self) -> None:
        old = _touch(
            self.downloads / "old.mp4",
            mtime=self.now - timedelta(hours=48),
            content=b"old",
        )
        fresh = _touch(
            self.downloads / "fresh.mp4",
            mtime=self.now - timedelta(hours=1),
            content=b"new",
        )

        report = run_cleanup(self.config, jobs=[], delete_job=lambda _id: False)

        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())
        self.assertEqual(report.categories.get("downloads_orphan"), 1)
        self.assertGreater(report.bytes_freed, 0)

    def test_never_deletes_paths_for_active_jobs(self) -> None:
        protected_video = _touch(
            self.downloads / "active.mp4",
            mtime=self.now - timedelta(hours=72),
            content=b"active",
        )
        orphan = _touch(
            self.downloads / "orphan.mp4",
            mtime=self.now - timedelta(hours=72),
            content=b"orphan",
        )
        jobs = [
            {
                "job_id": "j-active",
                "status": JobStatus.PROCESSING.value,
                "created_at": self.now.isoformat(),
                "updated_at": self.now.isoformat(),
                "video_path": str(protected_video),
                "output_clip_paths": [],
            }
        ]

        report = run_cleanup(self.config, jobs=jobs, delete_job=lambda _id: False)

        self.assertTrue(protected_video.exists())
        self.assertFalse(orphan.exists())
        self.assertTrue(
            any("active.mp4" in p for p in report.skipped_protected),
        )

    def test_skips_temp_cleanup_when_active_job(self) -> None:
        temp_srt = _touch(
            self.root / "temp.srt",
            mtime=self.now - timedelta(hours=5),
            content=b"1\n",
        )
        jobs = [
            {
                "job_id": "j1",
                "status": JobStatus.QUEUED.value,
                "created_at": self.now.isoformat(),
                "updated_at": self.now.isoformat(),
            }
        ]

        report = run_cleanup(self.config, jobs=jobs, delete_job=lambda _id: False)

        self.assertTrue(temp_srt.exists())
        self.assertTrue(report.skipped_active_temps)

    def test_deletes_expired_temp_when_idle(self) -> None:
        temp_srt = _touch(
            self.root / "temp.srt",
            mtime=self.now - timedelta(hours=5),
            content=b"1\n",
        )
        temp_audio = _touch(
            self.root / "temp_audio.mp3",
            mtime=self.now - timedelta(hours=5),
            content=b"audio",
        )
        cookies = _touch(
            self.root / "cookies.txt",
            mtime=self.now - timedelta(hours=100),
            content=b"secret",
        )

        report = run_cleanup(self.config, jobs=[], delete_job=lambda _id: False)

        self.assertFalse(temp_srt.exists())
        self.assertFalse(temp_audio.exists())
        self.assertTrue(cookies.exists())
        self.assertEqual(report.categories.get("temp"), 2)

    def test_expired_output_clips_deleted(self) -> None:
        old_clip = _touch(
            self.clips / "clip_1_Old.mp4",
            mtime=self.now - timedelta(hours=72),
            content=b"clip",
        )
        recent = _touch(
            self.clips / "clip_2_New.mp4",
            mtime=self.now - timedelta(hours=2),
            content=b"clip2",
        )

        run_cleanup(self.config, jobs=[], delete_job=lambda _id: False)

        self.assertFalse(old_clip.exists())
        self.assertTrue(recent.exists())

    def test_protects_completed_job_clips_by_basename(self) -> None:
        clip = _touch(
            self.clips / "clip_1_Keep.mp4",
            mtime=self.now - timedelta(hours=72),
            content=b"keep",
        )
        jobs = [
            {
                "job_id": "j-done",
                "status": JobStatus.COMPLETED.value,
                "created_at": (self.now - timedelta(hours=1)).isoformat(),
                "updated_at": (self.now - timedelta(hours=1)).isoformat(),
                "output_clip_paths": [f"/media/clips/{clip.name}"],
            }
        ]

        run_cleanup(self.config, jobs=jobs, delete_job=lambda _id: False)
        self.assertTrue(clip.exists())

    def test_purges_expired_failed_jobs_not_active(self) -> None:
        deleted: list[str] = []

        def delete_job(job_id: str) -> bool:
            deleted.append(job_id)
            return True

        jobs = [
            {
                "job_id": "fail-old",
                "status": JobStatus.FAILED.value,
                "created_at": (self.now - timedelta(hours=24)).isoformat(),
                "updated_at": (self.now - timedelta(hours=24)).isoformat(),
            },
            {
                "job_id": "fail-new",
                "status": JobStatus.FAILED.value,
                "created_at": (self.now - timedelta(hours=1)).isoformat(),
                "updated_at": (self.now - timedelta(hours=1)).isoformat(),
            },
            {
                "job_id": "still-running",
                "status": JobStatus.PROCESSING.value,
                "created_at": (self.now - timedelta(hours=100)).isoformat(),
                "updated_at": (self.now - timedelta(hours=100)).isoformat(),
            },
        ]

        report = run_cleanup(self.config, jobs=jobs, delete_job=delete_job)

        self.assertEqual(deleted, ["fail-old"])
        self.assertEqual(report.deleted_jobs, ["fail-old"])
        self.assertNotIn("still-running", deleted)

    def test_refuses_path_outside_allowed_root(self) -> None:
        outside = Path(tempfile.gettempdir()) / "tclipper_cleanup_outside.bin"
        _touch(outside, mtime=self.now - timedelta(hours=100), content=b"nope")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))

        # Pretend an orphan listing somehow included outside — cleanup_directory
        # only iterates allowed dirs; verify _safe_unlink via protected collect.
        from app.services.storage_cleanup import CleanupReport, _safe_unlink

        report = CleanupReport()
        ok = _safe_unlink(
            outside,
            allowed_root=self.downloads,
            config=self.config,
            report=report,
            category="downloads",
        )
        self.assertFalse(ok)
        self.assertTrue(outside.exists())
        self.assertTrue(any("outside_root" in e for e in report.errors))

    def test_dry_run_does_not_delete(self) -> None:
        old = _touch(
            self.downloads / "dry.mp4",
            mtime=self.now - timedelta(hours=48),
            content=b"dry",
        )
        self.config.dry_run = True
        report = run_cleanup(self.config, jobs=[], delete_job=lambda _id: False)
        self.assertTrue(old.exists())
        self.assertEqual(len(report.deleted_files), 1)

    def test_graceful_when_directory_missing(self) -> None:
        self.config.downloads_dir = self.root / "missing_downloads"
        report = run_cleanup(self.config, jobs=[], delete_job=lambda _id: False)
        self.assertEqual(report.errors, [])

    def test_collect_protected_paths(self) -> None:
        video = self.downloads / "v.mp4"
        video.write_bytes(b"v")
        jobs = [
            {
                "video_path": str(video),
                "curated_json_path": str(self.transcripts / "curated_x.json"),
                "output_clip_paths": ["/media/clips/clip_9_Title.mp4"],
            }
        ]
        protected = collect_protected_paths(jobs)
        self.assertIn(video.resolve(), protected)
        self.assertIn(Path("clip_9_Title.mp4"), protected)


class TestJobStoreDeleteGuards(unittest.TestCase):
    def test_delete_job_refuses_active(self) -> None:
        from app.services import job_store

        job = job_store.create_job("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        job_id = job["job_id"]
        job_store.update_job_status(job_id, JobStatus.PROCESSING)
        self.assertFalse(job_store.delete_job(job_id))
        self.assertIsNotNone(job_store.get_job(job_id))

        job_store.update_job_status(job_id, JobStatus.FAILED, error="x")
        self.assertTrue(job_store.delete_job(job_id))
        self.assertIsNone(job_store.get_job(job_id))


if __name__ == "__main__":
    unittest.main()
