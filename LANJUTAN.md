# Lanjutan Project: Montage Layak Bungkus

Catatan status untuk melanjutkan project ini (di percakapan / project lain).

## Ringkasan project
- Repo GitHub (private): https://github.com/yogahd-hub/rhenza-layak-bungkus-montage (branch `main`)
- Fungsi: GitHub Actions mengambil semua video dari folder Google Drive, menyatukannya jadi montage 9:16 (part maks 10 menit), membuat subtitle Bahasa Indonesia (faster-whisper), lalu meng-upload hasil ke folder Drive output.
- Hasil:
  - `montage_partNN.mp4` + versi kecil `montage_partNN_540p.mp4`
  - `montage_partNN.srt` (subtitle per part)
  - `multiple_srt_layak_bungkus.txt` (semua subtitle digabung, dengan judul per video)
  - `index.csv` (daftar klip: nomor, part, nama file asli, durasi, posisi di part)
  - Di Drive: subfolder `montage_run<N>_<tanggal>` (akhiran `_TEST` kalau uji coba)
  - TXT + CSV juga di-commit ke folder `output/` di repo

## File penting di repo
| File | Fungsi |
|---|---|
| `.github/workflows/montage.yml` | Alur kerja: 1. daftar file → 2. proses per batch (12 file) → 3. susun montage |
| `scripts/list_drive.py` | Daftar file Drive, buang duplikat, urutkan, bagi batch |
| `scripts/process_batch.sh` | Download, normalisasi, transkrip satu batch |
| `scripts/normalize.sh` | ffmpeg: ubah klip ke 1080x1920 30fps + buat kartu penanda |
| `scripts/transcribe.py` | Transkrip dengan faster-whisper |
| `scripts/assemble.py` | Gabung part, kartu penanda, SRT, index.csv |
| `README.md` | Panduan lengkap untuk pemula |

## Pengaturan GitHub (Settings → Secrets and variables → Actions)
| Jenis | Nama | Status |
|---|---|---|
| Variable | `DRIVE_FOLDER_ID` = `1Y2Xa2ijF78Y0ivmrheqW_FnOxS0mBpH_` (folder sumber) | ✅ sudah |
| Variable | `DRIVE_OUTPUT_FOLDER_ID` = `1T04vb6gWp_fmwkoQcLeWylKG7ci8gk_N` (folder hasil) | ✅ sudah |
| Secret (Repository secret) | `RCLONE_CONFIG` = seluruh isi file rclone.conf, mulai `[gdrive]` | ❌ terbaca kosong |

> Jangan pernah tempel isi rclone.conf / token ke chat. Isinya hanya untuk kolom secret di GitHub.

## Status terakhir
- Uji coba pertama (TEST_LIMIT=3) **gagal** di langkah "1. Daftar file Drive":
  `Secret RCLONE_CONFIG kosong. Isi dulu, atau jalankan dengan SOURCE=gdown.`
- Penyebab yang mungkin:
  1. Secret tersimpan di **Environment secrets**, bukan **Repository secrets**.
  2. Nama secret tidak persis `RCLONE_CONFIG`.
  3. Login rclone sebelumnya belum berhasil (sempat error 400 saat login Google), jadi file rclone.conf belum berisi token.
- Peringatan kuning "Node.js 20 is deprecated" boleh diabaikan.

## Langkah berikutnya
1. **Perbaiki secret**
   - Di Windows PowerShell (folder rclone): `.\rclone config file` → buka file yang ditunjuk dengan Notepad.
   - Pastikan isinya ada bagian `[gdrive]` dengan `type = drive` dan baris `token = {...}`.
   - GitHub → Settings → Secrets and variables → Actions → tab **Secrets** → **New repository secret** → Name `RCLONE_CONFIG` → tempel seluruh isi file → Add secret.
2. **Jalankan uji coba**: Actions → "Montage + SRT (Layak Bungkus)" → Run workflow → `TEST_LIMIT` = `3` → Run.
3. Kalau hijau: cek folder Drive output (`montage_run..._TEST`), tonton part01 dan cek SRT.
4. **Jalankan penuh**: Run workflow dengan `TEST_LIMIT` = `0` (±75 video).

## Kalau login rclone error 400
Kode login bawaan rclone kemungkinan diblokir Google. Buat kode login sendiri (gratis, ±10 menit):
1. Buka console.cloud.google.com → buat project baru.
2. APIs & Services → Library → aktifkan **Google Drive API**.
3. OAuth consent screen → External → isi nama app → tambahkan akun Google sendiri sebagai **Test user**.
4. Credentials → Create credentials → **OAuth client ID** → tipe **Desktop app** → catat client_id dan client_secret.
5. Jalankan `.\rclone config` → hapus remote `gdrive` lama → buat lagi bernama `gdrive`, tipe `drive`, isi client_id dan client_secret tadi, scope `1` (full access), login di browser.
6. Lanjut ke langkah 1 di "Langkah berikutnya".

## Alternatif tanpa rclone
Jika folder sumber dibuat publik ("Anyone with the link"), jalankan dengan `SOURCE` = `gdown` (maks 50 file per folder). Tanpa `RCLONE_CONFIG`, hasil video tidak di-upload ke Drive, tapi disimpan sebagai artifact `montage-video` di halaman run (3 hari).

## Pilihan saat Run workflow
| Pilihan | Default | Arti |
|---|---|---|
| WHISPER_MODEL | small | `medium` lebih akurat tapi jauh lebih lama |
| PAD_MODE | blur | Latar video landscape: blur atau hitam |
| TITLE_CARD | true | Kartu 0,5 detik (nomor + nama file) sebelum tiap klip |
| MAX_PART_MINUTES | 10 | Durasi maksimal per part |
| TEST_LIMIT | 0 | Isi angka untuk uji coba N file pertama |
| SOURCE | rclone | `gdown` untuk folder publik |
| AUTO_EDITOR | false | Versi tambahan tanpa jeda hening (tidak cocok dengan SRT) |

## Catatan untuk asisten berikutnya
- Pengguna awam coding: jawab singkat, Bahasa Indonesia sederhana, langkah per langkah.
- Hemat kuota percakapan.
