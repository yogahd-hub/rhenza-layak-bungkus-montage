#!/usr/bin/env python3
"""Daftar video di folder Drive -> filter -> dedupe (md5) -> natural sort -> batch.

Pemakaian:
  # mode rclone (default): baca output `rclone lsjson --hash`
  python scripts/list_drive.py --lsjson listing.json --out manifest.json \
      --batch-size 12 --test-limit 0

  # mode gdown (fallback, folder "Anyone with the link")
  python scripts/list_drive.py --gdown-folder <FOLDER_ID> --out manifest.json

Output:
  manifest.json  -> {"source": "...", "files": [ {no, name, path, id, size, md5, batch}, ... ]}
  stdout         -> baris `matrix=<json>` dan `count=<n>` untuk $GITHUB_OUTPUT
"""
import argparse
import json
import re
import sys

VIDEO_EXT = (".mov", ".mp4", ".m4v", ".mkv", ".avi", ".3gp", ".mts", ".webm")


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def is_video(name: str, mime: str = "") -> bool:
    if mime and mime.startswith("video/"):
        return True
    return name.lower().endswith(VIDEO_EXT)


def from_lsjson(path: str):
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    files, skipped = [], []
    for it in items:
        if it.get("IsDir"):
            continue
        name = it.get("Name") or it.get("Path")
        if not is_video(name, it.get("MimeType", "")):
            skipped.append(name)
            continue
        files.append(
            {
                "name": name,
                "path": it.get("Path", name),
                "id": it.get("ID", ""),
                "size": int(it.get("Size", 0) or 0),
                "md5": ((it.get("Hashes") or {}).get("md5") or "").lower(),
            }
        )
    return files, skipped


def from_gdown(folder_id: str):
    import gdown  # noqa: import lokal supaya mode rclone tidak butuh gdown

    entries = gdown.download_folder(
        id=folder_id, skip_download=True, quiet=True, remaining_ok=True
    )
    files, skipped = [], []
    for e in entries or []:
        name = e.path.split("/")[-1]
        if not is_video(name):
            skipped.append(name)
            continue
        # gdown tidak memberi ukuran/md5 -> dedupe dilakukan lagi di job assemble (md5 file)
        files.append({"name": name, "path": e.path, "id": e.id, "size": 0, "md5": ""})
    if len(entries or []) >= 50:
        print(
            "::warning::gdown hanya bisa membaca maksimal 50 file per folder. "
            "Pakai mode rclone untuk folder besar.",
            file=sys.stderr,
        )
    return files, skipped


def dedupe(files):
    seen, keep, dropped = {}, [], []
    for f in files:
        key = f["md5"] or (f"{f['name']}|{f['size']}" if f["size"] else f["id"])
        if key in seen:
            dropped.append((f, seen[key]))
            continue
        seen[key] = f
        keep.append(f)
    return keep, dropped


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lsjson")
    g.add_argument("--gdown-folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--test-limit", type=int, default=0)
    args = ap.parse_args()

    if args.lsjson:
        files, skipped = from_lsjson(args.lsjson)
        source = "rclone"
    else:
        files, skipped = from_gdown(args.gdown_folder)
        source = "gdown"

    for s in skipped:
        print(f"[skip] bukan video: {s}", file=sys.stderr)

    # sort dulu (natural, by path lalu id) supaya duplikat yang dipertahankan selalu yang pertama
    files.sort(key=lambda f: (natural_key(f["path"]), f["id"]))
    files, dropped = dedupe(files)
    for d, orig in dropped:
        print(
            f"[dedupe] buang {d['name']} (id={d['id']}) == {orig['name']} (id={orig['id']})",
            file=sys.stderr,
        )

    if args.test_limit and args.test_limit > 0:
        files = files[: args.test_limit]
        print(f"[test] TEST_LIMIT={args.test_limit} -> hanya {len(files)} file", file=sys.stderr)

    if not files:
        print("::error::Tidak ada file video ditemukan di folder Drive.", file=sys.stderr)
        sys.exit(1)

    bs = max(1, args.batch_size)
    for i, f in enumerate(files):
        f["no"] = i + 1
        f["batch"] = i // bs + 1

    n_batches = files[-1]["batch"]
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"source": source, "files": files}, fh, indent=2, ensure_ascii=False)

    print(f"[list] {len(files)} video unik, {len(dropped)} duplikat dibuang, "
          f"{len(skipped)} non-video di-skip, {n_batches} batch", file=sys.stderr)
    for f in files:
        print(f"  #{f['no']:03d} batch{f['batch']:02d} {f['path']} "
              f"({f['size'] / 1e6:.1f} MB)", file=sys.stderr)

    print("matrix=" + json.dumps({"batch": list(range(1, n_batches + 1))}))
    print(f"count={len(files)}")


if __name__ == "__main__":
    main()
