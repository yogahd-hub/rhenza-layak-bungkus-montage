# Prompt untuk Chat Claude: Analisis Video Layak Bungkus

## Sebelum dipakai
1. Workflow GitHub sudah selesai hijau (minimal uji coba TEST_LIMIT=3).
2. Di claude.ai, aktifkan connector **Google Drive** (ikon + / Connectors → Google Drive).
3. Salin seluruh teks di dalam kotak di bawah, tempel ke chat Claude baru.

---

```
Saya punya kumpulan video interview untuk konten "Layak Bungkus". Bantu saya memahami isinya.
Saya awam soal teknis: jawab singkat, Bahasa Indonesia sederhana.

Pakai connector Google Drive untuk membuka folder hasil dengan ID:
1T04vb6gWp_fmwkoQcLeWylKG7ci8gk_N

Di dalamnya ada subfolder bernama montage_run<nomor>_<tanggal> (pakai yang paling baru).
Isi subfolder itu:
- kontak/kontak_01.jpg, kontak_02.jpg, ... = lembar kontak. Tiap klip punya label
  "#nomor nama_file" dan 3 potongan layar (awal, tengah, akhir).
- multiple_srt_layak_bungkus.txt = transkrip semua video, dengan judul "Video N — nama_file".
- index.csv = daftar klip: nomor, part, nama file asli, durasi, posisi di montage.
- montage_partNN.mp4 = video gabungan (tidak perlu dibuka, Claude tidak bisa memutar video).

Tugas:
1. Lihat SEMUA gambar lembar kontak dan baca transkripnya.
2. Kelompokkan klip berdasarkan ORANG (narasumber). Beri nama sementara, misal
   "Perempuan A (baju merah, rambut panjang)". Sebutkan nomor klip tiap orang.
3. Untuk tiap orang, kelompokkan lagi berdasarkan TEMPAT / SETTING (misal: dapur, warung,
   luar ruangan) dan KONTEKS / TOPIK pembicaraan dari transkrip.
4. Buat tabel: No klip | Nama file | Orang | Tempat | Topik singkat | Durasi.
5. Tandai klip yang ragu-ragu (wajah tidak jelas, kemungkinan orang lain) dengan "⚠ cek manual".
6. Terakhir, beri ringkasan 3–5 kalimat: ada berapa orang, berapa setting, dan
   saran klip mana yang paling layak dipakai untuk konten.

Kalau ada file yang tidak bisa dibuka, sebutkan namanya saja dan lanjutkan dengan yang ada.
Jangan menebak isi yang tidak terlihat; tulis "tidak jelas" bila ragu.
```

---

## Catatan
- Claude tidak bisa menonton video. Ia hanya melihat gambar lembar kontak dan membaca transkrip,
  jadi hasilnya perkiraan. Cek ulang klip bertanda ⚠.
- Kalau connector Drive tidak bisa membuka gambar: unduh file `kontak_*.jpg` dari Drive
  (atau dari artifact `srt-dan-index` di halaman run GitHub), lalu upload manual ke chat
  bersama prompt di atas.
