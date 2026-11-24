#!/usr/bin/env python3
"""Transkrip per klip dengan faster-whisper -> satu .srt per klip.

Timestamp di SRT per klip relatif terhadap awal klip (0 = frame pertama klip
hasil normalisasi). Job assemble yang menggeser timestamp ke timeline montage.

Pemakaian:
  python scripts/transcribe.py --model small --language id --out-dir srt clips/001.mp4 clips/002.mp4 ...
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def fmt_ts(sec: float) -> str:
    ms = max(0, int(round(sec * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def duration(path: str) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path], text=True)
    return float(out.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", "small"))
    ap.add_argument("--language", default="id")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("clips", nargs="+")
    args = ap.parse_args()

    from faster_whisper import WhisperModel

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print(f"[whisper] memuat model '{args.model}' (cpu, int8)", flush=True)
    model = WhisperModel(args.model, device="cpu", compute_type="int8",
                         cpu_threads=os.cpu_count() or 4)
    print(f"[whisper] model siap dalam {time.time() - t0:.1f}s", flush=True)

    for clip in args.clips:
        t1 = time.time()
        dur = duration(clip)
        segments, info = model.transcribe(
            clip,
            language=args.language,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
        )
        lines, n = [], 0
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            start = max(0.0, min(seg.start, dur))
            end = max(start, min(seg.end, dur))
            if end - start < 0.05:
                continue
            n += 1
            lines.append(f"{n}\n{fmt_ts(start)} --> {fmt_ts(end)}\n{text}\n")
        out = out_dir / (Path(clip).stem + ".srt")
        out.write_text("\n".join(lines), encoding="utf-8")
        el = time.time() - t1
        print(f"[whisper] {Path(clip).name}: {n} cue, durasi {dur:.1f}s, "
              f"waktu {el:.1f}s ({dur / el if el else 0:.1f}x realtime)", flush=True)

    print(f"[whisper] selesai, total {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
