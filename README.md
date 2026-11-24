# Montage + SRT otomatis — "18. Layak Bungkus"

Repo ini menjalankan **GitHub Actions** (komputer gratis milik GitHub di cloud) untuk:

1. mengunduh semua video dari folder Google Drive,
2. menyeragamkan tiap klip ke **1080×1920 (9:16), 30 fps**,
3. menyisipkan **kartu penanda 0,5 detik** (nomor + nama file asli) sebelum tiap klip,
4. menggabungkan semuanya menjadi **montage** yang dipecah per ±10 menit (`montage_part01.mp4`, `montage_part02.mp4`, …) + versi **proxy 540p**,
5. membuat **transkrip bahasa Indonesia** (faster-whisper) yang timestamp-nya sudah cocok dengan timeline montage,
6. mengunggah hasil ke folder Drive output dan menyimpan SRT + `index.csv` di folder [`output/`](output/) repo ini.

Anda tidak perlu menginstal apa pun di laptop, kecuali `rclone` sekali saja untuk membuat "kunci" akses Drive (Langkah 3).

---

## Daftar isi

- [Alur kerja singkat](#alur-kerja-singkat)
- [Setup awal (sekali saja)](#setup-awal-sekali-saja)
  - [Langkah 1 — Siapkan folder Drive output](#langkah-1--siapkan-folder-drive-output)
  - [Langkah 2 — Isi variable `DRIVE_FOLDER_ID` dan `DRIVE_OUTPUT_FOLDER_ID`](#langkah-2--isi-variable-drive_folder_id-dan-drive_output_folder_id)
  - [Langkah 3 — Buat secret `RCLONE_CONFIG`](#langkah-3--buat-secret-rclone_config)
  - [Langkah 4 — Izinkan workflow menulis ke repo](#langkah-4--izinkan-workflow-menulis-ke-repo)
- [Menjalankan workflow](#menjalankan-workflow)
- [Hasil yang didapat](#hasil-yang-didapat)
- [Format SRT](#format-srt)
- [Mengedit manual di CapCut / OpenCut](#mengedit-manual-di-capcut--opencut)
- [Batasan GitHub & perkiraan waktu](#batasan-github--perkiraan-waktu)
- [Kalau ada masalah](#kalau-ada-masalah)
- [Untuk yang penasaran: isi repo](#untuk-yang-penasaran-isi-repo)

---

## Alur kerja singkat

```
Job 1 "list"     → baca isi folder Drive, buang file non-video (.jpeg), buang duplikat (md5),
                   urutkan nama file (natural sort), bagi jadi batch @12 file
Job 2 "process"  → (maks 4 batch jalan bersamaan) download → normalisasi ffmpeg → transkrip whisper
Job 3 "assemble" → kartu penanda → bagi part ≤10 menit (klip tidak pernah terpotong) → concat
                   → proxy 540p → gabung SRT dengan offset → index.csv → upload Drive + commit ke repo
```

---

## Setup awal (sekali saja)

Semua pengaturan ada di halaman repo: **Settings → Secrets and variables → Actions**.
Di halaman itu ada dua tab: **Secrets** (rahasia, isinya tidak bisa dilihat lagi) dan **Variables** (biasa).

### Langkah 1 — Siapkan folder Drive output

1. Buka Google Drive, buat folder baru, misalnya `Hasil Montage Layak Bungkus`.
2. Buka folder itu. Lihat alamat di browser, contohnya
   `https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp`
   Bagian setelah `folders/` (`1AbCdEfGhIjKlMnOp`) adalah **ID folder**. Catat.

ID folder sumber (video mentah) sudah diketahui: `1Y2Xa2ijF78Y0ivmrheqW_FnOxS0mBpH_`.

### Langkah 2 — Isi variable `DRIVE_FOLDER_ID` dan `DRIVE_OUTPUT_FOLDER_ID`

1. Di repo ini, klik **Settings** (tab paling kanan di atas).
2. Menu kiri: **Secrets and variables → Actions**.
3. Klik tab **Variables**, lalu **New repository variable**.
4. Buat dua variable:

| Name | Value |
|---|---|
| `DRIVE_FOLDER_ID` | `1Y2Xa2ijF78Y0ivmrheqW_FnOxS0mBpH_` |
| `DRIVE_OUTPUT_FOLDER_ID` | ID folder output dari Langkah 1 |

### Langkah 3 — Buat secret `RCLONE_CONFIG`

Workflow memakai **rclone** untuk membaca/menulis Google Drive. rclone butuh file konfigurasi berisi "kunci" akses. Isi file itu disimpan sebagai secret `RCLONE_CONFIG`. Nama remote **harus** `gdrive`.

Pilih **salah satu** opsi:

#### Opsi B (DIREKOMENDASIKAN) — Login Google lewat `rclone config` di laptop

Cara ini paling mudah dan bisa membaca **dan** mengunggah hasil ke Drive Anda.

1. **Instal rclone** di laptop:
   - Windows: unduh dari <https://rclone.org/downloads/>, ekstrak, buka folder hasil ekstrak, klik kanan → *Open in Terminal*.
   - macOS: di Terminal jalankan `brew install rclone` (atau unduh dari link di atas).
   - Linux: `sudo -v ; curl https://rclone.org/install.sh | sudo bash`
2. Jalankan:
   ```bash
   rclone config
   ```
   Jawab pertanyaannya seperti ini (ketik lalu Enter):

   | Pertanyaan | Jawaban |
   |---|---|
   | `n) New remote` | `n` |
   | `name>` | `gdrive` |
   | `Storage>` | `drive` (Google Drive) |
   | `client_id>` / `client_secret>` | kosongkan saja (Enter) |
   | `scope>` | `1` (akses penuh, perlu untuk upload hasil) |
   | `service_account_file>` | kosongkan (Enter) |
   | `Edit advanced config?` | `n` |
   | `Use web browser to automatically authenticate?` | `y` → browser terbuka, login ke akun Google pemilik/punya akses ke folder, klik **Allow** |
   | `Configure this as a Shared Drive?` | `n` |
   | `Keep this "gdrive" remote?` | `y` |
   | (menu utama) | `q` untuk keluar |

3. **Uji** bahwa folder sumber terbaca:
   ```bash
   rclone lsf gdrive: --drive-root-folder-id 1Y2Xa2ijF78Y0ivmrheqW_FnOxS0mBpH_
   ```
   Harus muncul daftar `IMG_....MOV`.
4. Cari lokasi file konfigurasi:
   ```bash
   rclone config file
   ```
   Buka file itu dengan Notepad/TextEdit. Isinya kira-kira:
   ```ini
   [gdrive]
   type = drive
   scope = drive
   token = {"access_token":"ya29....","token_type":"Bearer","refresh_token":"1//0g....","expiry":"2026-..."}
   team_drive =
   ```
5. **Salin seluruh bagian `[gdrive]`** (dari baris `[gdrive]` sampai baris terakhirnya).
6. Di GitHub: **Settings → Secrets and variables → Actions → tab Secrets → New repository secret**
   - Name: `RCLONE_CONFIG`
   - Secret: tempel teks tadi → **Add secret**.

> ⚠️ Isi `token` adalah kunci akses ke Google Drive Anda. Jangan dibagikan ke siapa pun selain sebagai secret GitHub.
> Jika suatu saat workflow gagal dengan pesan `invalid_grant` / token kedaluwarsa, ulangi langkah 2–6 (biasanya terjadi kalau password Google diganti atau akses dicabut).

#### Opsi A — Service account (untuk yang terbiasa dengan Google Cloud)

1. Buka <https://console.cloud.google.com/> → buat project → **APIs & Services → Enable APIs** → aktifkan **Google Drive API**.
2. **IAM & Admin → Service Accounts → Create service account** → selesai → buka service account → tab **Keys → Add key → JSON** → file `.json` terunduh.
3. Catat email service account (mis. `montage@proyek-anda.iam.gserviceaccount.com`).
4. Di Google Drive, **Share** folder sumber ke email itu (cukup *Viewer*), dan folder output (sebagai *Editor*).
5. Ubah isi file JSON menjadi satu baris (di <https://jsonformatter.org/json-minify> atau dengan `jq -c . file.json`).
6. Isi secret `RCLONE_CONFIG` dengan:
   ```ini
   [gdrive]
   type = drive
   scope = drive
   service_account_credentials = {"type":"service_account","project_id":"...", ... }
   ```

> ⚠️ **Penting:** service account **tidak punya kuota penyimpanan**. Membaca folder sumber akan berhasil, tetapi **upload hasil ke folder "My Drive" biasa akan gagal** (`storageQuotaExceeded`). Upload hanya berhasil jika folder output berada di **Shared Drive** (Google Workspace). Kalau Anda tidak punya Shared Drive, pakai Opsi B.

#### Opsi C (cadangan) — Folder publik "Anyone with the link" + `gdown`

Kalau folder sumber di-share **"Anyone with the link"**, workflow bisa mengunduh tanpa rclone dengan memilih `SOURCE = gdown` saat menjalankan.

Keterbatasan:
- `gdown` hanya bisa membaca **maksimal 50 file** per folder (folder ini ±75 file → tidak semua terbaca). Cocok untuk uji coba, bukan untuk proses penuh.
- Dedupe dilakukan setelah download (md5 file), jadi duplikat tetap ikut diunduh dulu.
- Tanpa `RCLONE_CONFIG`, hasil video **tidak** di-upload ke Drive; sebagai gantinya video disimpan sebagai artifact `montage-video` (hanya 3 hari).

### Langkah 4 — Izinkan workflow menulis ke repo

Workflow meng-commit `output/multiple_srt_layak_bungkus.txt` dan `output/index.csv`. Biasanya sudah diizinkan oleh file workflow. Jika langkah commit gagal dengan error `403`/`Permission denied`:

**Settings → Actions → General → Workflow permissions → pilih "Read and write permissions" → Save.**

---

## Menjalankan workflow

1. Klik tab **Actions** di atas repo.
   (Jika muncul tombol hijau *"I understand my workflows, go ahead and enable them"*, klik dulu.)
2. Di daftar kiri, klik **"Montage + SRT (Layak Bungkus)"**.
3. Di kanan, klik tombol **Run workflow** ▾. Akan muncul formulir:

| Input | Arti | Default |
|---|---|---|
| `WHISPER_MODEL` | Model transkrip. `small` = seimbang. `medium` lebih akurat tapi ±3× lebih lama. `tiny`/`base` lebih cepat tapi kurang akurat. | `small` |
| `PAD_MODE` | Klip landscape tidak di-crop. `blur` = latar belakang blur dari video itu sendiri; `black` = garis hitam. | `blur` |
| `TITLE_CARD` | `true` = sisipkan kartu hitam 0,5 detik bertuliskan `#nomor` + nama file sebelum tiap klip. | `true` |
| `MAX_PART_MINUTES` | Batas durasi per part. Klip tidak pernah dipotong, jadi part bisa sedikit lebih pendek. | `10` |
| `TEST_LIMIT` | `3` = hanya proses 3 file pertama (uji coba). `0` = semua file. | `0` |
| `SOURCE` | `rclone` (pakai secret) atau `gdown` (folder publik, maks 50 file). | `rclone` |
| `AUTO_EDITOR` | `true` = buat juga `montage_partNN_tanpa_jeda.mp4` yang jeda heningnya dibuang (auto-editor). SRT **tidak** cocok dengan versi ini. | `false` |

4. **Pertama kali, isi `TEST_LIMIT` = `3`** lalu klik **Run workflow** (tombol hijau). Tunggu ±10–20 menit.
5. Klik run yang sedang berjalan untuk melihat progres. Ada 3 kotak: **1. Daftar file Drive → 2. Proses batch → 3. Susun montage + SRT**. Klik salah satu untuk melihat log ffmpeg/whisper.
6. Kalau semua centang hijau ✅, cek hasilnya (lihat bagian berikut). Kalau sudah oke, jalankan lagi dengan `TEST_LIMIT = 0` untuk memproses semua video.

---

## Hasil yang didapat

**Di folder Drive output**, subfolder `montage_run<nomor>_<tanggal>` (akhiran `_TEST` jika memakai TEST_LIMIT):

| File | Isi |
|---|---|
| `montage_part01.mp4`, `montage_part02.mp4`, … | Montage 1080×1920, maks ±10 menit per part |
| `montage_part01_540p.mp4`, … | Proxy 540×960 untuk preview cepat di HP |
| `montage_part01.srt`, … | Subtitle per part (SRT standar, bisa langsung diimpor ke CapCut/Premiere/VLC) |
| `multiple_srt_layak_bungkus.txt` | Semua transkrip dalam satu file, format "Video N — nama file" |
| `index.csv` | Daftar klip: nomor, part, nama file asli, ID Drive, durasi, posisi di part, orientasi |

**Di repo** (folder [`output/`](output/)): `multiple_srt_layak_bungkus.txt` dan `index.csv` (video tidak di-commit karena besar).

**Di halaman run Actions** (bagian *Artifacts* di bawah): `srt-dan-index` berisi semua SRT + CSV (tersimpan 30 hari).

### `index.csv`

| Kolom | Arti |
|---|---|
| `no` | Nomor klip (sama dengan nomor di kartu penanda dan di `Video N`) |
| `part` | Part montage tempat klip berada (`01`, `02`, …) |
| `file_asli` | Nama file di Drive |
| `drive_file_id` | ID file Drive. Buka `https://drive.google.com/file/d/<ID>/view` untuk melihat file aslinya |
| `durasi_detik` | Durasi klip (tanpa kartu penanda) |
| `start_di_part` / `end_di_part` | Posisi klip di dalam file part (`jam:menit:detik.milidetik`), sesudah kartu penanda |
| `orientasi` | `portrait`, `landscape`, atau `square` (setelah rotasi otomatis) |

---

## Format SRT

`multiple_srt_layak_bungkus.txt` mengikuti format yang sudah Anda pakai, ditambah penanda part:

```
=== PART 01 ===

Video 1 — IMG_3152.MOV
1
00:00:00,866 --> 00:00:02,466
teks...

2
00:00:02,500 --> 00:00:04,100
teks...

Video 2 — IMG_3153.MOV
37
...

=== PART 02 ===

Video 14 — IMG_3170.MOV
412
00:00:00,610 --> ...
```

- Nomor cue **bersambung** dari awal sampai akhir semua part.
- Timestamp mengikuti **timeline file part masing-masing** (setiap part mulai dari `00:00:00`), sudah termasuk durasi kartu penanda. Jadi cue pertama tiap video minimal di detik 0,5 kalau `TITLE_CARD=true`.
- File `montage_partNN.srt` berisi cue yang sama untuk part itu, tetapi dalam **format SRT standar** (tanpa baris `Video N — …`, nomor mulai dari 1) supaya bisa diimpor ke aplikasi edit tanpa error.

---

## Mengedit manual di CapCut / OpenCut

Otomasi di repo ini memakai **ffmpeg**, bukan OpenCut. OpenCut adalah editor berbasis browser tanpa mode headless/CLI, jadi tidak bisa dijalankan otomatis di GitHub Actions.

Setelah montage jadi, Anda bisa mengedit manual:

- **CapCut**: impor `montage_partNN.mp4`, lalu *Text → Captions → Import captions/Local captions* → pilih `montage_partNN.srt`.
- **OpenCut** (<https://opencut.app>): buka di browser, impor `montage_partNN.mp4` (atau proxy 540p supaya lebih ringan).
- Gunakan kartu penanda `#nomor` + `index.csv` untuk menemukan file asli di Drive.

---

## Batasan GitHub & perkiraan waktu

| Batas | Dampak & cara repo ini menanganinya |
|---|---|
| Disk runner ±14 GB (±30 GB setelah dibersihkan) | Video diproses per batch (12 file); file sumber dihapus setelah dinormalisasi; klip dihapus setelah di-concat. |
| Maks 6 jam per job | Tiap batch jalan di job sendiri (timeout 5 jam); assemble timeout 3 jam. |
| Ukuran/kuota artifact | Klip per batch disimpan sebagai artifact sementara (retensi 1 hari) dan **dihapus otomatis** setelah montage selesai. |
| Menit Actions (repo private, akun gratis: 2.000 menit/bulan) | Perkiraan satu proses penuh (±75 klip, ±7 GB, model `small`): ±4–8 jam total waktu runner (dibagi ke beberapa job paralel, jadi selesainya ±1,5–3 jam). Uji `TEST_LIMIT=3` hanya ±15–30 menit. Model `medium` bisa 2–3× lebih lama. |

Sisa kuota bisa dilihat di **github.com → foto profil → Settings → Billing and plans**.

---

## Kalau ada masalah

| Pesan / gejala | Penyebab & solusi |
|---|---|
| `Repository variable DRIVE_FOLDER_ID belum diisi` | Ulangi [Langkah 2](#langkah-2--isi-variable-drive_folder_id-dan-drive_output_folder_id). |
| `Secret RCLONE_CONFIG kosong` / `Remote 'gdrive' tidak ada` | Ulangi [Langkah 3](#langkah-3--buat-secret-rclone_config); pastikan baris pertamanya persis `[gdrive]`. |
| `invalid_grant`, `token expired` | Token Google kedaluwarsa/dicabut. Ulangi Opsi B langkah 2–6 dan perbarui secret. |
| `rclone menemukan 0 file` | Akun Google/service account belum punya akses ke folder, atau ID folder salah. |
| `storageQuotaExceeded` saat upload | Anda memakai service account (Opsi A) ke folder My Drive biasa. Pakai Opsi B. |
| `The quota has been exceeded` saat download | Kuota unduh Google Drive per file habis (file sering diunduh). Tunggu 24 jam lalu jalankan lagi. |
| Langkah commit gagal 403 | Lihat [Langkah 4](#langkah-4--izinkan-workflow-menulis-ke-repo). |
| Salah satu batch merah | Batch lain tetap jalan (`fail-fast: false`), tetapi assemble tidak dijalankan. Klik batch merah → lihat log → jalankan ulang dengan **Re-run failed jobs**. |
| Teks transkrip kurang akurat | Coba `WHISPER_MODEL = medium`. |

---

## Untuk yang penasaran: isi repo

```
.github/workflows/montage.yml   # definisi workflow (3 job)
scripts/list_drive.py           # rclone lsjson → filter video → dedupe md5 → natural sort → batch
scripts/process_batch.sh        # 1 batch: download → normalisasi → transkrip
scripts/normalize.sh            # ffmpeg: normalisasi klip (auto-rotate, pad/blur, HDR→SDR) + kartu penanda
scripts/transcribe.py           # faster-whisper (language=id, vad_filter, int8 CPU) → SRT per klip
scripts/assemble.py             # bagi part, concat -c copy, proxy 540p, SRT + offset, index.csv
requirements.txt                # faster-whisper
output/                         # hasil SRT gabungan + index.csv (di-commit otomatis)
```

Detail teknis:
- Normalisasi: `scale` + `pad` (atau background blur) ke 1080×1920, `fps=30`, H.264 `-preset veryfast -crf 23`, AAC 48 kHz stereo. Rotasi dari metadata iPhone diterapkan otomatis. Video iPhone HDR (HLG/Dolby Vision) di-tonemap ke SDR supaya warna tidak pucat. Klip tanpa audio diberi audio hening.
- Semua klip & kartu memakai parameter encode yang identik, sehingga concat memakai `-f concat -c copy` (cepat, tanpa encode ulang).
- Transkrip dibuat per klip (timestamp relatif klip), lalu digeser sesuai posisi klip di part.
- Menjalankan lokal (butuh ffmpeg, jq, rclone, Python):
  ```bash
  pip install -r requirements.txt
  python scripts/list_drive.py --lsjson lsjson.json --out manifest.json --test-limit 3
  scripts/process_batch.sh manifest.json 1 work
  python scripts/assemble.py --in-dir work --out-dir final
  ```
