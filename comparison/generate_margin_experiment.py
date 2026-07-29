"""
MarginV-only positioning experiment.

Monkeypatches _SUBTITLE_FORCE_STYLE MarginV only.
Does not modify production defaults on disk.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
COMPARISON = ROOT / "comparison"
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.core.config import get_settings  # noqa: E402
from services import video_cutter as vc  # noqa: E402

MARGINS = (58, 68, 78, 88)
FRAME_SS = "25"

# Production baseline knobs except MarginV (set per run).
_BASE = (
    "FontSize=24,"
    "Bold=1,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BorderStyle=1,"
    "Outline=4,"
    "Shadow=1,"
    "Alignment=2,"
    "MarginL=18,"
    "MarginR=18,"
)


def _style(margin_v: int) -> str:
    return f"{_BASE}MarginV={margin_v}"


def _extract_frame(mp4: Path, png: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        FRAME_SS,
        "-i",
        str(mp4),
        "-frames:v",
        "1",
        "-update",
        "1",
        str(png),
    ]
    completed = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if completed.returncode != 0 or not png.is_file():
        raise RuntimeError(f"Frame extract failed for {mp4.name}: {(completed.stderr or '')[-2000:]}")


def main() -> None:
    COMPARISON.mkdir(parents=True, exist_ok=True)

    curated_path = BACKEND / "transcripts" / "curated_hXET-58xrqM.json"
    sanitized_path = BACKEND / "transcripts" / "sanitized_hXET-58xrqM.json"
    downloads = BACKEND / "downloads"
    matches = [
        p
        for p in downloads.iterdir()
        if p.is_file() and "[hXET-58xrqM]" in p.name and p.suffix.lower() == ".mp4"
    ]
    if not matches:
        raise FileNotFoundError("Source video for hXET-58xrqM not found")
    video_path = matches[0]

    payload = json.loads(curated_path.read_text(encoding="utf-8"))
    clip = payload["clips"][0]

    settings = get_settings()
    video_duration = vc._probe_video_duration_seconds(video_path)
    cut_start, cut_end = vc._apply_editorial_padding(
        float(clip["start_time"]),
        float(clip["end_time"]),
        pad_start=float(settings.clip_pad_start_seconds),
        pad_end=float(settings.clip_pad_end_seconds),
        video_duration=video_duration,
    )
    render_clip = {
        **clip,
        "start_time": cut_start,
        "end_time": cut_end,
        "duration": round(cut_end - cut_start, 3),
    }

    print(f"video={video_path}")
    print(f"cut_window={cut_start:.3f}->{cut_end:.3f}")
    print(f"frame_ss={FRAME_SS}")
    print(f"baseline_style_prefix={_BASE!r}")

    relative_srt = "temp.srt"
    temp_srt = vc.PROJECT_ROOT / relative_srt
    vc.generate_srt_for_clip(render_clip, str(sanitized_path), str(temp_srt))

    # Sanity: production file still has MarginV=58
    src = (BACKEND / "services" / "video_cutter.py").read_text(encoding="utf-8")
    if not re.search(r'MarginV=58"', src) and 'MarginV=58' not in src:
        print("WARNING: unexpected MarginV in video_cutter.py")

    try:
        for margin in MARGINS:
            style = _style(margin)
            vc._SUBTITLE_FORCE_STYLE = style
            out_mp4 = COMPARISON / f"margin{margin}.mp4"
            out_png = COMPARISON / f"margin{margin}.png"
            print(f"\n=== MarginV={margin} ===")
            print(f"force_style={style}")
            vc.cut_clip(
                str(video_path),
                cut_start,
                cut_end,
                str(out_mp4),
                relative_srt_path=relative_srt,
            )
            _extract_frame(out_mp4, out_png)
            st = out_mp4.stat()
            print(f"wrote {out_mp4.name} bytes={st.st_size}")
    finally:
        if temp_srt.is_file():
            temp_srt.unlink()
            print("deleted temp.srt")
        # Restore in-process baseline (disk file never changed)
        vc._SUBTITLE_FORCE_STYLE = _style(58)

    print("\nDone.")


if __name__ == "__main__":
    main()
