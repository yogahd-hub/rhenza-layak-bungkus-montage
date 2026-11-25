#!/usr/bin/env python3
"""Susun montage: bagi part, kartu penanda, concat, gabung SRT + offset, index.csv.

Input  : <in-dir>/**/meta/NNN.json, clips/NNN.mp4, srt/NNN.srt  (hasil job process)
Output : <out-dir>/montage_partNN.mp4, montage_partNN_540p.mp4, montage_partNN.srt,
         multiple_srt_layak_bungkus.txt, index.csv

Pemakaian:
  python scripts/assemble.py --in-dir artifacts --out-dir final \
      --title-card true --max-part-minutes 10
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TS_RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def log(msg):
    print(f"[assemble {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fmt_ts(sec: float) -> str:
    ms = max(0, int(round(sec * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_hms(sec: float) -> str:
    return fmt_ts(sec).replace(",", ".")


def probe_dur(path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)], text=True)
    return float(out.strip())


def parse_srt(path: Path):
    """-> list of (start, end, text)"""
    if not path.exists():
        return []
    cues = []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())
    for b in blocks:
        lines = [l for l in b.strip().splitlines()]
        for i, l in enumerate(lines):
            m = TS_RE.search(l)
            if m:
                g = list(map(int, m.groups()))
                st = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
                en = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
                text = "\n".join(lines[i + 1:]).strip()
                if text:
                    cues.append((st, en, text))
                break
    return cues


def run(cmd):
    log("$ " + " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def make_contact_sheets(clips, dest: Path, per_sheet=12, cols=3):
    """Lembar kontak: tiap klip = 3 potongan layar + label nomor & nama file."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log("Pillow tidak ada -> lembar kontak dilewati")
        return
    tw, th, lab = 270, 480, 40
    cw, ch = tw * 3 + 20, th + lab + 20
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    dest.mkdir(parents=True, exist_ok=True)
    for si in range(0, len(clips), per_sheet):
        group = clips[si:si + per_sheet]
        rows = (len(group) + cols - 1) // cols
        sheet = Image.new("RGB", (cw * cols, ch * rows), "white")
        d = ImageDraw.Draw(sheet)
        for gi, m in enumerate(group):
            x0, y0 = (gi % cols) * cw + 10, (gi // cols) * ch + 10
            label = f"#{m['final_no']} {m['name']}"[:60]
            d.text((x0, y0 + 8), label, fill="black", font=font)
            thumbs_dir = Path(m["clip_path"]).parent.parent / "thumbs"
            src_no = Path(m["clip_path"]).stem
            for k in range(3):
                tp = thumbs_dir / f"{src_no}_{k + 1}.jpg"
                if tp.exists():
                    im = Image.open(tp).convert("RGB").resize((tw, th))
                    sheet.paste(im, (x0 + k * tw, y0 + lab))
        out = dest / f"kontak_{si // per_sheet + 1:02d}.jpg"
        sheet.save(out, quality=80)
        log(f"lembar kontak {out.name}: klip #{group[0]['final_no']}-#{group[-1]['final_no']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--title-card", default="true")
    ap.add_argument("--card-seconds", type=float, default=0.5)
    ap.add_argument("--max-part-minutes", type=float, default=10)
    ap.add_argument("--no-proxy", action="store_true")
    ap.add_argument("--keep-clips", action="store_true",
                    help="jangan hapus klip normalisasi setelah dipakai (default: hapus untuk hemat disk)")
    args = ap.parse_args()

    title_card = str(args.title_card).lower() in ("1", "true", "yes", "ya")
    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_work"
    work.mkdir(exist_ok=True)

    # ---- kumpulkan klip ----------------------------------------------------
    metas = []
    for mp in sorted(in_dir.rglob("meta/*.json")):
        m = json.loads(mp.read_text(encoding="utf-8"))
        base = mp.parent.parent
        nnn = mp.stem
        m["clip_path"] = base / "clips" / f"{nnn}.mp4"
        m["srt_path"] = base / "srt" / f"{nnn}.srt"
        if not m["clip_path"].exists():
            sys.exit(f"klip hilang: {m['clip_path']}")
        metas.append(m)
    if not metas:
        sys.exit("Tidak ada klip di " + str(in_dir))
    metas.sort(key=lambda m: m["no"])

    # dedupe kedua (berdasarkan md5 file yang benar-benar diunduh) -> penting untuk mode gdown
    seen, clips = {}, []
    for m in metas:
        key = m.get("md5_local") or m.get("md5") or m["id"]
        if key in seen:
            log(f"duplikat dibuang: {m['name']} (id={m['id']}) == {seen[key]['name']}")
            continue
        seen[key] = m
        clips.append(m)
    for i, m in enumerate(clips, 1):
        m["final_no"] = i
    log(f"{len(clips)} klip unik")

    # ---- durasi & kartu ----------------------------------------------------
    for m in clips:
        m["dur"] = probe_dur(m["clip_path"])
        if title_card:
            card = work / f"card_{m['final_no']:03d}.mp4"
            run([HERE / "normalize.sh", "card", card, m["final_no"], m["name"], args.card_seconds])
            m["card_path"] = card
            m["card_dur"] = probe_dur(card)
        else:
            m["card_path"], m["card_dur"] = None, 0.0

    # ---- bagi part (klip tidak pernah dipotong) ----------------------------
    max_sec = args.max_part_minutes * 60
    parts, cur, cur_len = [], [], 0.0
    for m in clips:
        seg = m["card_dur"] + m["dur"]
        if cur and cur_len + seg > max_sec:
            parts.append(cur)
            cur, cur_len = [], 0.0
        cur.append(m)
        cur_len += seg
    if cur:
        parts.append(cur)
    log(f"{len(parts)} part (maks {args.max_part_minutes} menit per part)")

    # ---- concat + SRT ------------------------------------------------------
    combined = []
    cue_no = 0
    index_rows = []
    for pi, part in enumerate(parts, 1):
        pname = f"montage_part{pi:02d}"
        lst = work / f"{pname}.txt"
        t = 0.0
        part_cues = []
        with lst.open("w", encoding="utf-8") as fh:
            for m in part:
                if m["card_path"]:
                    fh.write(f"file '{Path(m['card_path']).resolve()}'\n")
                    t += m["card_dur"]
                fh.write(f"file '{Path(m['clip_path']).resolve()}'\n")
                m["part"] = pi
                m["start"] = t
                m["end"] = t + m["dur"]
                t += m["dur"]

        mp4 = out_dir / f"{pname}.mp4"
        log(f"=== {pname}: {len(part)} klip, perkiraan durasi {fmt_hms(t)} ===")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", lst, "-c", "copy", "-movflags", "+faststart", mp4])
        real = probe_dur(mp4)
        drift = real - t
        log(f"{pname}.mp4 selesai: durasi {fmt_hms(real)} (selisih {drift * 1000:+.0f} ms), "
            f"ukuran {mp4.stat().st_size / 1e6:.0f} MB")
        if abs(drift) > 1.0:
            print(f"::warning::{pname}: durasi hasil concat beda {drift:.2f}s dari perkiraan", flush=True)

        if not args.no_proxy:
            proxy = out_dir / f"{pname}_540p.mp4"
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats_period", "30", "-stats",
                 "-y", "-i", mp4, "-vf", "scale=540:960", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "28", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", proxy])
            log(f"proxy {proxy.name}: {proxy.stat().st_size / 1e6:.0f} MB")

        combined.append(f"=== PART {pi:02d} ===")
        n_local = 0
        for m in part:
            cues = parse_srt(Path(m["srt_path"]))
            vcues = []
            for st, en, text in cues:
                st = min(st, m["dur"])
                en = min(max(en, st), m["dur"])
                a, b = m["start"] + st, m["start"] + en
                cue_no += 1
                n_local += 1
                vcues.append(f"{cue_no}\n{fmt_ts(a)} --> {fmt_ts(b)}\n{text}")
                part_cues.append(f"{n_local}\n{fmt_ts(a)} --> {fmt_ts(b)}\n{text}")
            header = f"Video {m['final_no']} — {m['name']}"
            combined.append(header + ("\n" + "\n\n".join(vcues) if vcues else ""))
            index_rows.append({
                "no": m["final_no"],
                "part": f"{pi:02d}",
                "file_asli": m["name"],
                "drive_file_id": m["id"],
                "durasi_detik": f"{m['dur']:.3f}",
                "start_di_part": fmt_hms(m["start"]),
                "end_di_part": fmt_hms(m["end"]),
                "orientasi": m.get("orientasi", ""),
            })
        (out_dir / f"{pname}.srt").write_text("\n\n".join(part_cues) + "\n", encoding="utf-8")

        if not args.keep_clips:
            for m in part:
                Path(m["clip_path"]).unlink(missing_ok=True)

    # file gabungan: header tiap video, cue bersambung, satu baris kosong antar blok
    # tiap blok "Video N — nama" langsung diikuti cue-nya; antar blok satu baris kosong
    txt = "\n\n".join(combined)
    (out_dir / "multiple_srt_layak_bungkus.txt").write_text(txt.strip() + "\n", encoding="utf-8")

    with (out_dir / "index.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["no", "part", "file_asli", "drive_file_id", "durasi_detik",
                                           "start_di_part", "end_di_part", "orientasi"])
        w.writeheader()
        w.writerows(index_rows)

    make_contact_sheets(clips, out_dir / "kontak")

    shutil.rmtree(work, ignore_errors=True)
    log(f"selesai: {len(parts)} part, {len(clips)} klip, {cue_no} cue")


if __name__ == "__main__":
    main()
