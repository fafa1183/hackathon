# Tutorial Pemakaian SIGAP-Banjir (untuk Pemula)

Panduan langkah demi langkah, dari nol sampai jadi laporan. Tidak perlu
pengalaman pemrograman — cukup ikuti urutannya.

## 1. SIGAP-Banjir itu apa?

SIGAP-Banjir membaca **sepasang foto udara** suatu lokasi — satu foto
**sebelum** banjir dan satu foto **sesudah** banjir — lalu secara
otomatis:

1. menemukan rumah, air, dan jalan di foto (memakai AI SAM 3.1),
2. mengukur rumah mana saja yang bersentuhan dengan air banjir baru
   (air lama seperti sungai dan danau dikurangi dulu, jadi tidak ikut
   terhitung sebagai banjir),
3. menulis **laporan situasi (sitrep)**: ringkasan kejadian, jumlah
   rumah terdampak, dan daftar prioritas evakuasi.

Hasilnya dipakai untuk triase awal: petugas bisa melihat area mana
yang perlu didatangi lebih dulu, sebelum survei lapangan dilakukan.

## 2. Bahan yang diperlukan

| Bahan | Keterangan |
|---|---|
| Komputer | Linux, macOS, atau Windows dengan WSL. |
| Internet | AI-nya berjalan di server Meta, jadi harus online. |
| Sepasang foto udara | Foto **sebelum** dan **sesudah** banjir. Syaratnya di bawah. |
| API key Meta Model API | Kunci akses milikmu sendiri (langkah 3.3). Gratis untuk kuota awal; jangan bagikan ke siapa pun. |

**Syarat foto** (ini yang paling menentukan hasil):

- Lokasi **sama** dan bingkai/sudut pengambilan **sama** antara foto
  sebelum dan sesudah.
- Ukuran piksel **sama persis** (misalnya sama-sama 960x400).
- Paling bagus: foto permukiman skala dekat (rumah terlihat jelas).
  Foto wilayah sangat luas dari ketinggian besar sering tidak terbaca
  (lihat bagian 6).

Tidak punya foto latihan? Pakai pasangan foto domain publik dari NOAA
(survei Badai Harvey) yang dipakai contoh di tutorial ini — tautannya
ada di langkah 4.

## 3. Persiapan (cukup sekali)

Buka terminal, lalu jalankan perintah berikut satu per satu.

**3.1 Ambil programnya**

```bash
git clone https://github.com/fafa1183/hackathon.git
cd hackathon
```

**3.2 Pasang kebutuhan program**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3.3 Pasang API key kamu**

API key didapat dari dashboard Meta Model API (menu **API keys**) pada
proyek milikmu. Pasang di terminal seperti ini (key hanya berlaku di
jendela terminal ini):

```bash
export MODEL_API_KEY=key-kamu-di-sini
```

Jangan pernah menaruh key di dalam file program, chat, atau foto
layar — key itu seperti kata sandi.

## 4. Menjalankan dari foto

Contoh memakai foto latihan NOAA (unduh dulu kedua fotonya):

```bash
curl -O https://oceanservice.noaa.gov/news/sep17/west-houston-before.jpg
curl -O https://oceanservice.noaa.gov/news/sep17/west-houston-after.jpg
```

Lalu jalankan satu perintah ini:

```bash
python tools/olah_foto.py \
  --before west-houston-before.jpg \
  --after west-houston-after.jpg \
  --outdir hasil-foto
```

Untuk foto kamu sendiri, ganti saja nama file pada `--before` dan
`--after`. Prosesnya beberapa menit (ada beberapa panggilan ke AI).
Layar akan menampilkan Tahap 1/3, 2/3, 3/3, dan diakhiri tulisan
**SELESAI** beserta ringkasan angkanya.

## 5. Membaca hasil

Di folder `--outdir` (contoh: `hasil-foto`) ada tiga file:

- **`overlay.png`** — foto sesudah banjir dengan kotak di setiap
  rumah yang terdeteksi. Buka seperti membuka foto biasa.
  **Penting:** warna kotak menunjukkan *keyakinan deteksi AI*
  (hijau = yakin, oranye = kurang yakin), **bukan** tingkat prioritas.
  Prioritas dibaca dari laporan, bukan dari warna kotak.
- **`measurements.json`** — angka hasil pengukuran: jumlah rumah,
  luas air baru (piksel), dan daftar rumah prioritas beserta kontak
  airnya.
- **`sitrep.json`** — laporan situasinya. Bagian `ringkasan` adalah
  paragraf ringkas berbahasa Indonesia; bagian prioritas menyebut
  rumah yang perlu didahulukan.

Cara membaca prioritas:

- **Kontak air 10% atau lebih** = rumah *prioritas* (genangan baru
  menyentuh sebagian besar keliling rumah).
- **Kontak air 20% atau lebih** = yang *terberat*, didahulukan.
- Pada contoh West Houston, hasil yang wajar: sekitar 90 rumah
  terdeteksi, belasan prioritas, beberapa terberat, 2 segmen jalan.
  Angka persisnya bisa sedikit berbeda di setiap run — itu normal
  untuk model AI.

File `sitrep.json` ini juga yang dibaca oleh dashboard
(`dashboard/sigap_dashboard.html`) untuk ditampilkan sebagai peta
situasi.

## 6. Kalau hasilnya kosong atau sangat sedikit

Itu bisa terjadi dan bukan berarti programnya rusak. Penyebab yang
sudah kami temui di pengujian:

- Foto terlalu luas/tinggi sehingga rumah terlalu kecil untuk dibaca.
- Air banjir keruh menyatu dengan tanah/sungai di gambar.
- Kerusakan dominan angin (atap rusak) tanpa genangan — SIGAP mengukur
  genangan, bukan kerusakan bangunan.

SIGAP paling andal pada foto permukiman skala dekat, seperti contoh
West Houston dan dataset FloodNet yang dipakai di validasi repo ini.

## 7. Masalah umum

| Gejala | Penyebab & cara mengatasi |
|---|---|
| `MODEL_API_KEY belum terpasang` | Ulangi langkah 3.3 di jendela terminal yang sama. |
| `Ukuran foto tidak sama` | Pasangan fotonya beda ukuran piksel; pakai pasangan yang sebingkai dan seukuran. |
| `ModuleNotFoundError` / modul tidak ditemukan | Venv belum aktif; jalankan `source .venv/bin/activate` dulu (langkah 3.2). |
| Sitrep gagal dibuat, tapi `measurements.json` ada | Angka pengukuranmu aman. Buat laporannya saja: `python tools/run_sitrep.py --measurements hasil-foto/measurements.json --out hasil-foto/sitrep.json` |

## 8. Batasan yang perlu diketahui

- Angka luas dalam **piksel**, bukan meter dan bukan kedalaman air.
  SIGAP tidak tahu kedalaman genangan, jumlah penghuni, atau kondisi
  struktur bangunan.
- Daftar prioritas adalah **triage awal** untuk membantu petugas
  memutuskan urutan pengecekan — bukan pengganti penilaian petugas di
  lapangan.
- Jalan yang terdeteksi dilaporkan sebagai "perlu dicek aksesnya";
  SIGAP tidak menyatakan jalan pasti bisa/tidak bisa dilewati.
