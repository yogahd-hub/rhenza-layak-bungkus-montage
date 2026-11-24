#!/usr/bin/env bash
# Normalisasi klip & pembuatan kartu penanda dengan ffmpeg.
#
#   scripts/normalize.sh clip <input> <output.mp4> [black|blur]
#       -> 1080x1920 (9:16), 30 fps, H.264 veryfast crf23, AAC 48 kHz stereo.
#          Orientasi otomatis dari metadata rotate, landscape TIDAK di-crop (pad hitam / blur).
#          Juga menulis <output>.orient berisi portrait|landscape|square.
#
#   scripts/normalize.sh card <output.mp4> <nomor> <nama_file_asli> [durasi=0.5]
#       -> kartu hitam bertuliskan nomor klip + nama file asli (parameter encode identik
#          dengan klip, sehingga semua file bisa di-concat dengan `-c copy`).
set -euo pipefail

W=1080; H=1920; FPS=30
FONT_BOLD="${FONT_BOLD:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}"
FONT_REG="${FONT_REG:-/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf}"

# Parameter encode yang WAJIB sama di semua file agar concat -c copy aman.
VENC=(-c:v libx264 -preset veryfast -crf 23 -profile:v high -level:v 4.1
      -pix_fmt yuv420p -r "$FPS" -g 60 -keyint_min 30 -sc_threshold 0
      -video_track_timescale 30000)
AENC=(-c:a aac -b:a 160k -ar 48000 -ac 2)
FFLOG=(-hide_banner -loglevel error -stats_period 10 -stats -y)

log() { printf '[normalize %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

probe() { # probe <file> <entries> <stream-selector>
  ffprobe -v error -select_streams "$3" -show_entries "$2" -of default=nw=1:nk=1 "$1" | head -n1
}

mode="${1:-}"; shift || true

case "$mode" in
clip)
  in="$1"; out="$2"; pad_mode="${3:-blur}"
  [[ -f "$in" ]] || { echo "input tidak ada: $in" >&2; exit 1; }

  w=$(probe "$in" stream=width v:0); h=$(probe "$in" stream=height v:0)
  rot=$(ffprobe -v error -select_streams v:0 -show_entries stream_side_data=rotation \
          -of default=nw=1:nk=1 "$in" | head -n1); rot=${rot:-0}; rot=${rot%.*}
  trc=$(probe "$in" stream=color_transfer v:0)
  vdur=$(probe "$in" stream=duration v:0)
  [[ "$vdur" =~ ^[0-9.]+$ ]] || vdur=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$in")
  has_audio=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$in" | head -n1)

  # dimensi setelah rotasi
  if (( (${rot#-} / 90) % 2 == 1 )); then dw=$h; dh=$w; else dw=$w; dh=$h; fi
  if   (( dh > dw )); then orient=portrait
  elif (( dw > dh )); then orient=landscape
  else orient=square; fi
  echo "$orient" > "$out.orient"

  # sudah 9:16 persis (±1%)? -> tidak perlu background blur
  same_ar=$(awk -v a="$dw" -v b="$dh" 'BEGIN{r=(a/b)/(9/16); print (r>0.99 && r<1.01)?1:0}')

  # iPhone HDR (HLG/PQ) -> tonemap ke SDR bt709 supaya warna tidak pucat
  tm=""
  if [[ "$trc" == "arib-std-b67" || "$trc" == "smpte2084" ]]; then
    tm="zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
  fi

  tail_f="setsar=1,fps=${FPS},format=yuv420p"
  if [[ "$pad_mode" == "black" || "$same_ar" == "1" ]]; then
    vf="[0:v]${tm}scale=${W}:${H}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=black,${tail_f}[v]"
  else
    vf="[0:v]${tm}split=2[bg][fg];[bg]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:2,scale=${W}:${H},eq=brightness=-0.06[bgb];[fg]scale=${W}:${H}:force_original_aspect_ratio=decrease:force_divisible_by=2[fgs];[bgb][fgs]overlay=(W-w)/2:(H-h)/2,${tail_f}[v]"
  fi

  if [[ -n "$has_audio" ]]; then
    # apad: audio dipanjangkan dengan hening bila lebih pendek; output dipotong tepat di durasi video (-t)
    inputs=(-i "$in"); af="[0:a:0]aresample=48000,aformat=channel_layouts=stereo,apad[a]"
  else
    inputs=(-i "$in" -f lavfi -i "anullsrc=r=48000:cl=stereo"); af="[1:a]anull[a]"
  fi

  log "clip  : $(basename "$in")  ${w}x${h} rot=${rot} -> ${orient}, trc=${trc:-?}, audio=$([[ -n "$has_audio" ]] && echo ya || echo tidak), pad=${pad_mode}${tm:+, HDR->SDR}"
  t0=$(date +%s)
  run() {
    ffmpeg "${FFLOG[@]}" "${inputs[@]}" -filter_complex "$1;$af" \
      -map "[v]" -map "[a]" -t "$vdur" "${VENC[@]}" "${AENC[@]}" \
      -map_metadata -1 -movflags +faststart "$out"
  }
  if ! run "$vf"; then
    if [[ -n "$tm" ]]; then
      log "tonemap gagal, ulangi tanpa tonemap"
      vf="${vf/$tm/}"; run "$vf"
    else
      exit 1
    fi
  fi
  dur=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$out")
  log "ok    : $(basename "$out")  durasi=${dur}s  ukuran=$(du -h "$out" | cut -f1)  waktu=$(( $(date +%s) - t0 ))s"
  ;;

card)
  out="$1"; no="$2"; name="$3"; dur="${4:-0.5}"
  tmp=$(mktemp -d)
  printf '#%s' "$no" > "$tmp/no.txt"
  printf '%s' "$name" > "$tmp/name.txt"
  vf="drawtext=fontfile=${FONT_BOLD}:textfile=${tmp}/no.txt:fontcolor=white:fontsize=160:x=(w-text_w)/2:y=(h/2)-text_h-20,"
  vf+="drawtext=fontfile=${FONT_REG}:textfile=${tmp}/name.txt:fontcolor=white@0.9:fontsize=64:x=(w-text_w)/2:y=(h/2)+40,"
  vf+="setsar=1,format=yuv420p"
  ffmpeg "${FFLOG[@]}" -f lavfi -i "color=c=black:s=${W}x${H}:r=${FPS}:d=${dur}" \
    -f lavfi -i "anullsrc=r=48000:cl=stereo" -t "$dur" \
    -vf "$vf" "${VENC[@]}" "${AENC[@]}" -shortest -map_metadata -1 -movflags +faststart -nostats "$out"
  rm -rf "$tmp"
  [[ -s "$out" ]] || { echo "gagal membuat kartu $out" >&2; exit 1; }
  log "card  : #${no} ${name} -> $(basename "$out")"
  ;;

*)
  echo "pemakaian: $0 clip <in> <out> [black|blur] | card <out> <no> <nama> [durasi]" >&2
  exit 2
  ;;
esac
