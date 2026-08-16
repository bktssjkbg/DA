# 🧾 GATE RECEIPT — CV. Dewi Aditya ERP

> Dihasilkan `scripts/gate.sh`. JANGAN edit manual.
> "Selesai" hanya sah bila receipt HIJAU untuk cakupan yang TIDAK di-skip.

- **Waktu:** 2026-08-16 19:49:43  ·  **Durasi:** 76s  ·  **Mode:** cepat
- **Backend:** RUNNING · **Auth:** READY

| Gate | Hasil |
|------|-------|
| UANG/DATA — invarian GL, stok, AR/AP (verify_data_integrity) | PASS |
| UANG — baseline valuasi aksesoris (SSOT acc_baseline) | PASS |
| UANG — state machine jurnal (draft→posted→voided) | PASS |
| UANG — nomor dokumen tak boleh kembar saat balapan (RC-5) | PASS |
| UANG — batas nilai AR/AP/maklon (round6) | PASS |
| KEAMANAN — akses lintas-role & tanpa token (RBAC/IDOR) | PASS |
| KETAHANAN — input jahat harus 4xx, bukan 500 | PASS |
| BISA DIPAKAI — endpoint kritis terjangkau | PASS |
| ALUR — produksi/maklon/CMT: reject, rework, stok FG, SJ gabungan | PASS |
| DATA/UANG — R&D: ukuran tech pack, SKU SSOT, HPP hybrid (INV-RND) | PASS |
| DATA — SSOT warna: palet master bebas warna sampah (INV-COLOR) | PASS |
| DATA/UANG — R&D: padankan ukuran + harga master basi (INV-RND2) | PASS |
| KEAMANAN/UANG — Portal CMT Override: kewenangan, scoping, jejak (INV-CMTOV) | PASS |
| UANG/PRODUK — Rekap Harian + Mingguan CMT: batas WIB, definisi terisi, SSOT export (INV-REKAP) | PASS |
| UANG/DATA — Master Produk: kode kembar, kategori, HPP, berat, SKU (INV-PRODUK) | PASS |
| UANG — Katalog: satu rumus stok jual, anti-overselling, tautan order (INV-KATALOG) | PASS |
| DATA/UANG — Marketing: lingkup toko + impor tanpa AI (INV-MKTSCOPE) | PASS |
| UANG/ARAH — Marketing: siklus target·anggaran·omzet + kunci periode (INV-MKTCYCLE) | PASS |
| DATA/UANG — Marketing: impor KPI Seller Center + assign toko + scorecard (INV-KPIIMPOR) | PASS |
| DATA/UANG — Marketing: status pengiriman (Ekspor B/C) + pemulihan impor (INV-MKTFULFILL) | PASS |
| DATA/KEWENANGAN — Marketing: assign toko · ingat pemetaan · scorecard kreator (INV-MKTOPS) | PASS |
| UANG/ARAH — Marketing: omzet bruto vs setelah retur (INV-RETUR) | PASS |
| KEAMANAN/DATA — Marketing: lingkup toko per pemakai + jejak perubahan (INV-F6RBAC) | PASS |
| BISA DIPAKAI — Marketing: layar daftar (tabel · cari · unduh) + field tak disembunyikan (INV-F10) | PASS |
| DATA/UANG — Marketing: pratinjau impor per baris = kenyataan (INV-F11) | PASS |
| DATA/UANG — Marketing: berkas ekspor tidak boleh masuk toko yang salah (INV-F12) | PASS |
| UANG/STOK — Dispatch ke buyer: satu rumus sisa kirim + hasil permak bisa dikirim (INV-F16) | PASS |
| DOKUMEN — PDF rapi: 0 tumpang tindih + tabel penuh lebar halaman (INV-F17) | PASS |
| STOK/UANG — Kirim material ke CMT menerbitkan MI + memotong stok + jurnal (INV-F18) | PASS |
| PRODUK/STOK — Gudang: tombol buat MI, Buat Barcode, menu mati dilepas (INV-F19) | PASS |
| LAYAR/UANG — Dashboard Marketing: ada pintunya + angka resmi dari SSOT siklus (INV-F20) | PASS |
| DATA — Nomor dokumen: mode Otomatis/Manual ditegakkan, nomor bebas ditolak (INV-F21) | PASS |
| FITUR MATI — handler tergabung / kode setelah return | PASS |
| FITUR MATI — panggilan FE ke endpoint yang tak ada | PASS |
| NAVIGASI — menu hantu / duplikat / kedalaman | PASS |
| LAYAR — UANG/STOK di luar Marketing bisa dipakai & dibawa (INV-F13) | PASS |
| DATA/UANG — Form wajib memakai Master, bukan ketikan (INV-F14) | PASS |
| LAYAR — Kartu punya latar, tulisan terbaca, token tidak berbohong (INV-F15) | PASS |
| SERAH-TERIMA — mesin lint platform hidup (import validation + oxlint) | PASS |

## ✅ VERDICT: HIJAU — boleh lanjut / klaim selesai (untuk cakupan non-skip).

_SKIP bukan PASS. Jalankan ulang saat backend + auth hidup._
