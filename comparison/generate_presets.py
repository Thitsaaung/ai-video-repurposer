"""
One-off subtitle preset comparison renderer.

Does not modify production defaults permanently.
Monkeypatches services.video_cutter._SUBTITLE_FORCE_STYLE per preset.
"""
from __future__ import annotations

import json
import logging
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

# Shared colours / bold — only listed knobs differ per preset.
_COMMON = (
    "Bold=1,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BorderStyle=1,"
)

PRESETS: dict[str, dict[str, str | int]] = {
    "a": {
        "label": "Minimal",
        "FontSize": 18,
        "Outline": 2,
        "Shadow": 0,
        "MarginV": 64,
        "MarginL": 28,
        "MarginR": 28,
        "Alignment": 2,
    },
    "b": {
        "label": "TikTok",
        "FontSize": 28,
        "Outline": 5,
        "Shadow": 1,
        "MarginV": 72,
        "MarginL": 22,
        "MarginR": 22,
        "Alignment": 2,
    },
    "c": {
        "label": "Balanced (Opus-inspired)",
        "FontSize": 24,
        "Outline": 4,
        "Shadow": 1,
        "MarginV": 68,
        "MarginL": 20,
        "MarginR": 20,
        "Alignment": 2,
    },
    "d": {
        "label": "Accessibility",
        "FontSize": 30,
        "Outline": 5,
        "Shadow": 2,
        "MarginV": 88,
        "MarginL": 32,
        "MarginR": 32,
        "Alignment": 2,
    },
    "e": {
        "label": "T-Clipper Default (experimental)",
        # Current production shipping values in video_cutter.py
        "FontSize": 24,
        "Outline": 4,
        "Shadow": 1,
        "MarginV": 58,
        "MarginL": 18,
        "MarginR": 18,
        "Alignment": 2,
    },
}

FRAME_SS = "25"


def _force_style(p: dict[str, str | int]) -> str:
    return (
        f"FontSize={p['FontSize']},"
        f"{_COMMON}"
        f"Outline={p['Outline']},"
        f"Shadow={p['Shadow']},"
        f"Alignment={p['Alignment']},"
        f"MarginL={p['MarginL']},"
        f"MarginR={p['MarginR']},"
        f"MarginV={p['MarginV']}"
    )


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
    completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0 or not png.is_file():
        raise RuntimeError(f"Frame extract failed for {mp4.name}: {completed.stderr[-2000:]}")


def main() -> None:
    COMPARISON.mkdir(parents=True, exist_ok=True)

    curated_path = BACKEND / "transcripts" / "curated_hXET-58xrqM.json"
    sanitized_path = BACKEND / "transcripts" / "sanitized_hXET-58xrqM.json"
    downloads = BACKEND / "downloads"
    # Avoid Path.glob character-classes: brackets in YouTube ids are literal.
    matches = [
        p
        for p in downloads.iterdir()
        if p.is_file() and "[hXET-58xrqM]" in p.name and p.suffix.lower() == ".mp4"
    ]
    if not matches:
        raise FileNotFoundError("Source video for hXET-58xrqM not found in downloads/")
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

    # Generate SRT once (identical cues for all presets).
    relative_srt = "temp.srt"
    temp_srt = vc.PROJECT_ROOT / relative_srt
    vc.generate_srt_for_clip(render_clip, str(sanitized_path), str(temp_srt))

    results: list[tuple[str, str, str, Path, Path]] = []

    try:
        for key, preset in PRESETS.items():
            style = _force_style(preset)
            vc._SUBTITLE_FORCE_STYLE = style
            out_mp4 = COMPARISON / f"preset_{key}.mp4"
            out_png = COMPARISON / f"preset_{key}.png"
            print(f"\n=== preset_{key} ({preset['label']}) ===")
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
            print(f"wrote {out_mp4.name} bytes={st.st_size} mtime={st.st_mtime}")
            results.append((key, str(preset["label"]), style, out_mp4, out_png))
    finally:
        if temp_srt.is_file():
            temp_srt.unlink()
            print("deleted temp.srt")

    print("\nDone:")
    for key, label, _style, mp4, png in results:
        print(f"  {key}: {label} -> {mp4.name}, {png.name}")


if __name__ == "__main__":
    main()
