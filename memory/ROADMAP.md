# ROADMAP — CV. Dewi Aditya ERP

## Portal Gudang — sisa Fase H (setelah H-1 · H-2 · H-3 · H-4/H-9 SELESAI 2026-08-16,
## dan H-5 · H-6 SELESAI 2026-08-16 sesi #15)
- ✅ **H-5 (SELESAI 2026-08-16 #15)** Penerimaan kain menerbitkan **gulungan otomatis**
  (`RL-{YYYY}{MM}-{SEQ:4}`, nomor tidak boleh diketik), rincian roll divalidasi SEBELUM stok
  ditulis, dan penerimaan lama yang belum punya gulungan muncul di tab **"Penerimaan tanpa roll"**
  dengan tombol terbitkan retroaktif (idempoten). Gate: **INV-F22**.
- ✅ **H-6 (SELESAI 2026-08-16 #15)** Portal Cutting **WAJIB** menunjuk gulungan untuk kain yang
  dilacak per gulungan; pemakaian dibagi **FIFO** lewat satu pintu `core/fabric_roll_engine`
  (sisa roll + movement `issue` selalu ikut), dan kain yang belum punya gulungan ditolak dengan
  jalan keluarnya disebut. Gate: **INV-F22**.
  *(Catatan lingkup: dokumen **Material Issue** untuk arus keluar kain di Cutting — usul lama
  `ref_type='cutting_issue'` — BELUM dikerjakan; stok & gulungan sudah benar, yang belum ada
  hanyalah dokumen MI supaya arus keluar kain ikut muncul di satu daftar "Pengeluaran Material".)*
- **H-7 (P2)** Surat Jalan Gudang masih terpisah per sumber — satukan jadi satu daftar cetak.
- **H-8 (P2)** Alias lama `cmt-progress` · `do-management` · `prod-cmt-packing` · `maklon-packing`
  masih mengarah ke modul `wms-cmt-dispatches` yang koleksinya kosong; arahkan ke
  `prod-shipments-vendor`.
- **H-6b (P2, sisa dari H-6)** Cutting menerbitkan dokumen **Material Issue** (`cutting_issue`)
  supaya seluruh arus keluar gudang tampil di satu daftar.
- **F3/F4 (P1)** Rapikan 5 PDF tersering (SPP · Invoice · Slip Gaji · Picklist · SJ Vendor) ke pola
  `_pdf_data_table` (auto-wrap + penuh lebar halaman) seperti Surat Jalan Buyer di Fase F1/F2.
- **G (P1)** Penomoran dokumen **Auto/Manual per jenis dokumen** yang bisa diatur System Admin
  (SPP · CMT-RCV · SJ-RWK · Invoice · Kasbon).
- **D (P0)** Dashboard Marketing: komponennya ada tapi **tidak pernah didaftarkan di sidebar**
  mana pun, dan angkanya belum dari data hidup.

## P0 (menunggu owner)
- **Kunci Anthropic**: isi `ANTHROPIC_API_KEY` di `backend/.env`. Sampai diisi, SEMUA fitur AI
  (Asisten ERP untuk pertanyaan kompleks, Prediksi Kas, Ringkasan Harian, Analitik SDM, Estimasi
  Produksi/Maklon) gagal dengan anggun tapi tidak berfungsi.
- **Isi kemasan 478 item** lewat Ekspor/Impor Excel — lihat `docs/PANDUAN_UOM_EXCEL.md`.
- **Rebase 91 item bersatuan kemasan** (74 rol · 14 pak · 3 lusin) —
  `scripts/uom_rebase_worklist.py --export` lalu isi 2 kolom.

## P1 (next)
- **Basis pengetahuan Asisten** belum mencakup Portal Vendor, Klien, dan LiveHost
  (12 dari 15 portal sudah ada di `backend/data/portal_kb/`).
- Rekonsiliasi lokasi stok aksesoris `int-demo-loc-1` → zona kanonik `ZN-AKS`
  (`scripts/migrate_stock_locations_to_wh.py`).
- Verifikasi email SUNGGUHAN (SMTP dummy `aiosmtpd` atau kredensial nyata) untuk membuktikan
  lampiran Excel+PDF rapor valuasi benar terkirim.
- Perluas Jest/RTL ke `AccessoryValuationAutomation` + `StokOpnameTab`.
- Deeper UAT of remaining advanced Finance modules via UI flows (frontend) — backend logic already
  validated 39/39. Candidates: Executive Report Hub, AI Cash Flow (needs EMERGENT_LLM_KEY), Bad Debt
  Write-off, Purchase Discount (AP), Settlement Queue.
- Seed demo data for Budget, GL-Mapping, Master Categories, Periods so modules show populated states.

## P2 (nice-to-have)
- Standardise trailing-slash policy (e.g. `/api/announcements` 307 redirect) app-wide.
- Document required query params (e.g. `/finance/reports/general-ledger` needs `account_code`).
- Batch operations (bulk approve/pay), email notifications for approvals, Excel export on all reports.

## Backlog / tech-debt
- Remove `*_backup.py` route files if confirmed unused (e.g. `dewi_accessories_full_backup.py`).
- Reduce remaining non-gating ruff findings (F401 unused imports) incrementally.

## Done sesi 2026-08-05 (lihat CHANGELOG entri teratas)
- ✅ **Pemilih satuan di layar untuk 6 titik masuk stok** — Penerimaan (scan-in), Opname aksesoris,
  Cutting (progres), Pengeluaran Material, Put-away, Opname gudang, plus Aksesoris masuk/keluar.
  Satu endpoint opsi satuan (`GET /api/rahaza/materials/uom-options`), satu komponen UI
  (`uom/UomPicker.jsx`), dan cakupan konversi diseragamkan lewat `core/bom_uom.factor_to_base`.
  Uji: `tests/flow_uom_entry_points_ui_test.py` 38/38.
- ✅ **Penomoran dokumen tahap 2** — 11 penghasil nomor manual dipusatkan ke
  `utils.counters.gen_prefixed_number`; katalog layar 34 → 45 jenis; peta manual 18 → 7 (sisanya bukan
  nomor dokumen). Uji: `tests/flow_doc_numbering_phase2_test.py` 19/19 (termasuk 25 nomor bersamaan → unik).
- ✅ **Dashboard Maklon** memakai `GET /api/prod/dashboard?business_type=maklon` — tab "Alur Produksi"
  + pintu menu `maklon-alur-produksi`, label akhir "Dispatch ke Buyer".
- ✅ **Sisa uji R&D UoM** — jalur simpan Sample Costing terbukti (`backend/tests/flow_rnd_uom_test.py` 38/38).

## Done (see CHANGELOG.md)
- **FASE 11 (2026-07-25)**: BUG-R11-A ditutup tuntas (46 endpoint · sweep 7.184 req → 0 error 500) ·
  BUG-4 `datetime` SUBCLASS `date` (3 file) · BUG-5 kode akun modul Aset tidak ada di CoA ·
  alias legacy `yarn_*` dihentikan penulisannya · 4 alat uji diperbaiki · gate.sh 9/9 HIJAU.
  Detail: `docs/PLAN_FASE11.md`.
- Finance flow/integration hardening + lint cleanup (2026-06-07).
- Light-mode portals, Announcement Board, business-process docs, first Finance test (2026-06-02).
