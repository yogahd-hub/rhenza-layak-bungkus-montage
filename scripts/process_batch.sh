#!/usr/bin/env bash
# Proses satu batch: download -> normalisasi -> (hapus sumber) -> transkrip.
#
#   scripts/process_batch.sh <manifest.json> <batch_no> <work_dir>
#
# Env: SOURCE=rclone|gdown, PAD_MODE=blur|black, WHISPER_MODEL=small
# Hasil di <work_dir>/out/{clips,srt,meta}/NNN.*  (NNN = nomor urut global)
set -euo pipefail

manifest="$1"; batch="$2"; work="$3"
SOURCE="${SOURCE:-rclone}"; PAD_MODE="${PAD_MODE:-blur}"; WHISPER_MODEL="${WHISPER_MODEL:-small}"
here="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$work/src" "$work/out/clips" "$work/out/srt" "$work/out/meta" "$work/out/thumbs"

mapfile -t rows < <(jq -c --argjson b "$batch" '.files[] | select(.batch == $b)' "$manifest")
echo "::group::Batch ${batch}: ${#rows[@]} file"
for r in "${rows[@]}"; do echo "  $(jq -r '"#\(.no) \(.path)"' <<<"$r")"; done
echo "::endgroup::"

clips=()
for r in "${rows[@]}"; do
  no=$(jq -r .no <<<"$r"); id=$(jq -r .id <<<"$r"); name=$(jq -r .name <<<"$r")
  nnn=$(printf '%03d' "$no")
  ext="${name##*.}"
  src="$work/src/${nnn}.${ext}"
  out="$work/out/clips/${nnn}.mp4"

  echo "::group::#${no} ${name}"
  t0=$(date +%s)
  for attempt in 1 2 3; do
    if [[ "$SOURCE" == "gdown" ]]; then
      gdown --quiet "$id" -O "$src" && break
    else
      rclone backend copyid gdrive: "$id" "$src" --drive-acknowledge-abuse --retries 3 && break
    fi
    echo "download gagal (percobaan $attempt), coba lagi..."; sleep $((attempt * 10))
  done
  [[ -s "$src" ]] || { echo "::error::Gagal download #${no} ${name} (id=${id})"; exit 1; }
  echo "[download] ${name}  $(du -h "$src" | cut -f1)  $(( $(date +%s) - t0 ))s"

  md5=$(md5sum "$src" | cut -d' ' -f1)
  "$here/normalize.sh" clip "$src" "$out" "$PAD_MODE"
  orient=$(cat "$out.orient"); rm -f "$out.orient"
  dur=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$out")
  rm -f "$src"   # hemat disk runner

  # 3 potongan layar (15%, 50%, 85%) untuk lembar kontak
  for k in 1 2 3; do
    ss=$(awk -v d="$dur" -v k="$k" 'BEGIN{f=(k==1)?0.15:((k==2)?0.5:0.85); printf "%.2f", d*f}')
    ffmpeg -hide_banner -loglevel error -y -ss "$ss" -i "$out" -frames:v 1 -vf scale=270:480 \
      -q:v 4 "$work/out/thumbs/${nnn}_${k}.jpg" || true
  done

  jq -n --argjson r "$r" --arg md5 "$md5" --arg orient "$orient" --arg dur "$dur" \
    '$r + {md5_local: $md5, orientasi: $orient, durasi: ($dur|tonumber)}' \
    > "$work/out/meta/${nnn}.json"
  clips+=("$out")
  echo "::endgroup::"
done

echo "::group::Transkrip (faster-whisper ${WHISPER_MODEL})"
python "$here/transcribe.py" --model "$WHISPER_MODEL" --language id --out-dir "$work/out/srt" "${clips[@]}"
echo "::endgroup::"

echo "[batch ${batch}] selesai. Ukuran hasil: $(du -sh "$work/out" | cut -f1)"
