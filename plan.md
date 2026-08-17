# SESI 2026-08-16 (#16) — **FASE H-7 & H-8 DITUTUP**: satu daftar surat jalan lintas sumber · empat pintu lama tak lagi kosong

> **Permintaan pemilik:** (1) *"Surat Jalan Gudang: satukan surat jalan vendor, buyer, dan gudang
> jadi satu daftar cetak yang rapi"*; (2) *"Menu Alias Mati: arahkan empat pintu lama Kirim CMT ke
> Portal Produksi supaya tidak ada layar kosong"*.

## 1) ANGKA SEBELUM PERBAIKAN

| Yang diukur | Sebelum |
|---|---|
| layar "Surat Jalan" (Portal Gudang) | HANYA membaca `wh_delivery_notes` = **2 dokumen, keduanya DEMO** |
| surat jalan yang benar-benar dipakai | `vendor_shipments` **4** (kirim material CMT) + `buyer_shipment_items` **8 pengiriman** (dispatch buyer) |
| akibatnya | satu pertanyaan ("surat jalan apa saja yang keluar?") butuh **3 layar di 2 portal**, dan layar yang namanya paling mirip pertanyaan itu isinya paling sedikit |
| 4 alias menu | `cmt-progress`, `do-management`, `prod-cmt-packing`, `maklon-packing` → `wms-cmt-dispatches` (koleksi `wh_cmt_dispatches` = **0 dokumen**) |

## 2) H-7 — SATU DAFTAR, TIGA SUMBER (READ-ONLY)

- `GET /api/wms/delivery-notes/sources?source=&q=&date_from=&date_to=` menormalkan tiga koleksi jadi
  satu daftar (14 baris: 2 gudang + 4 vendor + 8 buyer). **Dispatch buyer dipecah per `dispatch_seq`**
  karena itulah dokumen yang benar-benar dibawa kurir — menggabungnya per PO akan menyembunyikan
  pengiriman ke-2 dan ke-3.
- Tiap baris mencetak **PDF RESMI dokumen aslinya** (`/{id}/pdf` untuk gudang,
  `type=vendor-shipment` untuk vendor, `type=buyer-shipment-dispatch` untuk buyer + `type=buyer-shipment`
  sebagai PDF kumulatif). **Tidak ada nomor baru dan tidak ada generator PDF kedua** — surat jalan tetap
  milik sumbernya. `wh_delivery_notes` TIDAK dipensiunkan (satu-satunya tempat SJ internal/manual dibuat).
- `GET /api/wms/delivery-notes/sources/recap-pdf` mencetak **rekap** (landscape) memakai
  `_pdf_data_table`: 0 tumpang tindih, tabel **100% lebar konten**, mendukung `?token=` untuk unduhan.
- **Cacat lama yang ikut ketemu & diperbaiki:** `_pdf_data_table` memakai `leading` 9,5 pt untuk font
  7,5 pt, padahal kotak glyph ±10,3 pt ⇒ **setiap sel yang teksnya melipat menghasilkan tumpang tindih
  ±0,8 pt** di SEMUA dokumen. Dinaikkan ke 10,8 pt; gate INV-F17 tetap HIJAU sesudahnya.
- Layar: tab pertama **"Semua Sumber"** (badge jumlah) + chip filter sumber berisi angka, rentang
  tanggal, pencarian, CSV, tombol **Cetak Rekap**, dan per baris **PDF · PDF kumulatif · Buka sumber**.
  Tab lama (SJ Gudang/Draft/Issued/Received) + alur buat/issue/receive tetap utuh.

## 3) H-8 — EMPAT PINTU LAMA DIARAHKAN KE PEKERJAAN YANG BENAR

| Alias | Dulu | Sekarang | Alasan |
|---|---|---|---|
| `do-management` | `wms-cmt-dispatches` (0 dok) | `prod-shipments-vendor` | surat jalan/kirim material CMT nyata di `vendor_shipments` |
| `prod-cmt-packing` | `wms-cmt-dispatches` | `da-cmt-receive` | "packing CMT" = **menerima** hasil jadi + QC + posting FG (`cmt_receipts`) |
| `maklon-packing` | `wms-cmt-dispatches` | `da-cmt-receive` | idem |
| `cmt-progress` | `wms-cmt-dispatches` | `cmt-monitor` | progres CMT dipantau di Monitoring CMT, bukan di layar pengiriman |

> Catatan jujur: owner menyebut "arahkan ke `prod-shipments-vendor`" untuk keempatnya. Dua alias
> packing DIARAHKAN KE `da-cmt-receive` karena pekerjaannya memang penerimaan FG — mengirim orang yang
> mengklik "Packing CMT" ke layar kirim material akan salah pekerjaan. Tinggal bilang kalau mau diubah.

## 4) BUKTI

- Gate baru **INV-F23** `scripts/verify_fase_h7_h8_surat_jalan.py` → **HIJAU 8 invarian**
  (kelengkapan 2+4+8=14 · PDF tiap sumber 200 · filter · dispatch per pengiriman · rekap 0 tumpang
  tindih 100% lebar · agregasi read-only · alias tak berujung kosong), terpasang di `scripts/gate.sh`.
- Agen uji: **backend 6/6 grup, layar 7/7 grup, 0 bug**.
- Gate lain tetap hijau: INV-F17 (PDF rapi), INV-F19, INV-F22 (roll), INV-NAV-01, INV-CONTRACT-01.

## 5) SISA FASE H

**H-6b** — Cutting menerbitkan dokumen Material Issue (`cutting_issue`) supaya seluruh arus keluar
gudang muncul di satu daftar "Pengeluaran Material". Itulah satu-satunya sisa Fase H.

---

# SESI 2026-08-16 (#15) — **FASE H-5 & H-6 DITUTUP**: gulungan kain LAHIR saat diterima, MATI saat dipotong

> **Titik berhenti sesi lalu (terukur, bukan dugaan):** `routes/warehouse.py` sudah memanggil
> `fabric_rolls.is_roll_material()`, `fabric_rolls.validate_roll_lines()` dan
> `fabric_roll_engine.create_rolls_from_receipt()` **tanpa satu pun modul itu di-import**, dan
> `rolls_created` **belum pernah diinisialisasi** — `python3 -m pyflakes` melaporkan **4 undefined
> name**. Backend TETAP BISA START (nama global dicari saat runtime), jadi kerusakannya tersembunyi
> sampai ada orang menekan *Confirm Received* pada penerimaan kain: NameError → HTTP 500.
> **Pilihan pemilik sesi ini:** kerjakan H-5 **dan** H-6; restore backup 2026-08-15; nomor roll
> **otomatis** `RL-{YYYY}{MM}-{SEQ:4}` (tidak boleh diketik); **wajib ada** daftar "Penerimaan tanpa
> roll" + tombol terbitkan gulungan retroaktif; kunci AI dilewati (bukan fokus fase ini).

## 1) KENAPA FASE INI PENTING — angka sebelum perbaikan

| Yang diukur | Sebelum | Akibatnya bagi orang gudang |
|---|---|---|
| `wh_fabric_rolls` | 4 dokumen, semuanya `DEMO-RL-000x` | tidak ada gulungan sungguhan yang bisa ditunjuk |
| cara mengisi gulungan | HANYA manual, `roll_no` **wajib diketik** | dua gulungan fisik bisa bernomor sama |
| penerimaan kain (GR) | menambah stok lewat `stock_service.add`, **tidak menyentuh roll** | 420 kg kain di sistem, NOL gulungan |
| pemilihan roll di Cutting | **opsional** ("Roll Fisik (opsional)") | stok turun, roll tetap penuh; "gulungan mana yang dipakai order ini?" tak terjawab |

Dua angka untuk satu penerimaan adalah masalahnya: **orang mencari kain memakai gulungan**,
sementara **laporan memakai stok**. Kalau keduanya tidak menjelaskan penerimaan yang sama,
gudang berdebat dengan dirinya sendiri.

## 2) YANG DIKERJAKAN

### H-5 — gulungan LAHIR dari penerimaan (nomor otomatis)
- `routes/warehouse.py`: import `core.fabric_roll_engine`, `rolls_created`/`rolls_pending`
  diinisialisasi, dan **rincian roll SEMUA baris divalidasi SEBELUM satu pun stok ditulis**
  (tidak ada GR setengah jadi: stok naik tapi gulungan gagal terbit).
- `create_receiving` kini **menyimpan** `item.rolls` — sebelumnya rincian yang diisi layar
  dibuang senyap oleh backend.
- Dokumen GR menyimpan `rolls_created`, `rolls_pending`, `rolls_summary`, dan per baris
  `roll_ids` + `roll_numbers` (jejak dua arah GR ⇄ gulungan).
- `routes/wms_fabric_rolls.py`: `roll_no` **tidak lagi diketik** — diterbitkan
  `fabric_roll_engine.issue_roll_no()` lewat SSOT penomoran (mode `auto` MENOLAK nomor ketikan
  sambil menyebut nomor yang akan dipakai — penolakan diam-diam membuat pemakai menyimpulkan
  sistemnya rusak). Endpoint baru: `GET /number-policy`, `GET /missing-from-receipts`,
  `POST /issue-from-receipt` (idempoten; penerbitan kedua **409**).

### H-6 — gulungan MATI di Cutting (wajib ditunjuk, FIFO)
- `routes/cutting.py`: `_plan_roll_consumption()` menghitung rencana pemakaian **sebelum** stok
  dipotong; progres tanpa gulungan → **400** yang menyebutkan gulungan bersisa; gulungan kurang →
  **400** dengan angkanya; pengurangan roll manual (blok lama) **diganti** satu pintu
  `fabric_roll_engine.allocate()` + `consume_rolls()`.
- `create_order` menolak kain yang belum punya gulungan **dengan jalan keluarnya** (isi Rincian
  Roll saat Penerimaan, atau terbitkan retroaktif di Roll Kain) dan memvalidasi `roll_ids` benar
  milik kain itu.
- `GET /api/cutting/rolls` kini objek `{items, total, roll_required, total_remaining, uom}`.
- Progres menyimpan `roll_consumption`/`roll_numbers` → jejak audit "gulungan mana dipakai berapa".

### Layar (bundel statis sudah di-rebuild)
- **Penerimaan Barang**: editor **Rincian Gulungan** per baris kain (tombol *Bagi rata*, indikator
  hijau/merah beserta selisihnya, nomor roll "otomatis"), bisa diisi saat membuat GR **atau** saat
  konfirmasi; setelah dikonfirmasi muncul daftar nomor gulungan yang terbit; banner kuning bila ada
  kain yang masuk stok tanpa gulungan.
- **Roll Kain**: input nomor roll **dihapus** (kotak "otomatis" + pola), tab baru
  **"Penerimaan tanpa roll"** (badge jumlah) + tombol **Terbitkan Roll**; detail gulungan
  menampilkan asalnya (`Penerimaan GR-…`).
- **Order Cutting**: pemilih gulungan **WAJIB**, tombol *Catat* mati sebelum gulungan dipilih,
  pratinjau alokasi FIFO ("pakai 40,00 → sisa 0,00" + baris "Rencana: …"), kolom
  **"Gulungan dipakai"** di riwayat progres.

## 3) BUKTI

- `python3 test_core_h5_h6.py` → **61 LULUS · 0 GAGAL** (dijalankan 2×, re-runnable).
- Gate baru **INV-F22** `scripts/verify_fase_h5_h6_roll.py` → **VERDICT HIJAU, 15 invarian**
  (self-cleaning), sudah terpasang di `scripts/gate.sh`.
- Agen uji: backend 52/52 endpoint, 0 bug; layar: semua modul kunci berfungsi.
- Gate lama tetap hijau: `verify_data_integrity` (PASS 24), `verify_concurrency` (FAIL 0),
  INV-F21 penomoran (HIJAU 8), INV-F19 gudang (HIJAU 16), HEALTH-01, INV-NAV-01,
  INV-CONTRACT-01, INV-DEADCODE-01.
- Uji layar (Playwright): selisih rincian → *"Kurang 40,000 kg — total gulungan 60,00 vs diterima
  100,00"*; cocok → *"Cocok — 2 gulungan = 100,00 kg"*; Confirm Received → *"2 gulungan diterbitkan
  otomatis: RL-202608-0131, RL-202608-0132"*; backfill → *"2 gulungan diterbitkan … RL-202608-0133,
  RL-202608-0134"* dan badge 3 → 2; Cutting → tombol Catat mati, lalu *"Gulungan dipakai:
  RL-202608-0003 −10,00 (sisa 30,00)"*.

## 4) CATATAN OPERASIONAL

- Data pembuktian (material `POC-*`/`TEST-H5*`/`TEST-H6*`, GR, gulungan, order cutting) SENGAJA
  ditinggal supaya bisa diperiksa di layar. Sapu kapan pun dengan
  `python3 scripts/cleanup_uji_h5_h6.py` (laporan) → `--apply` (hapus). Counter nomor sengaja tidak
  dikembalikan: nomor gulungan yang pernah dipakai tidak boleh dipakai ulang.
- Frontend = **bundel statis** ⇒ setiap perubahan layar wajib `yarn build` + `supervisorctl restart frontend`.
- Sisa Fase H: **H-7** (Surat Jalan Gudang satu daftar cetak) dan **H-8** (alias `cmt-progress`,
  `do-management`, `prod-cmt-packing`, `maklon-packing` masih mengarah ke `wms-cmt-dispatches`
  yang koleksinya kosong).

---

# SESI 2026-08-15 (#13) — **FASE E · F1/F2 · H-1 DITUTUP**: satu rumus sisa kirim · dokumen tidak tumpang tindih · kirim material memotong stok

> **Keluhan pemilik yang dikerjakan:** (1) chip penerimaan tertulis 90 tapi tabel jadi 80;
> (2) UI mengizinkan 100 lalu Simpan ditolak "maksimal 50"; (3) reject yang sudah diperbaiki
> tidak pernah bisa dikirim; (4) perlu daftar kekurangan kirim; (5) surat jalan PDF tumpang
> tindih & tabelnya kecil padahal margin lega, subtotal per PO diminta dihapus;
> (6) kirim material ke CMT harus otomatis mengurangi stok tanpa ketik-ketik.
> **Pilihan pemilik:** selesaikan Portal Maklon & Produksi dulu, Gudang belakangan; stok
> kurang ⇒ pengiriman DITOLAK, bukan diteruskan minus; menu Scan Gudang & Kirim CMT boleh
> dihapus (dikerjakan di fase Gudang).

## 1) TEMUAN YANG MENENTUKAN SEMUANYA — dibaca dari kode, bukan ditebak

`cmt_receipt_lines.qty_actual` BERARTI qty **LOLOS QC**; reject TIDAK termasuk.
Buktinya `dewi_cmt_packing.py`: `arrived = qty_actual + reject_qty`.

⇒ Layar lama menghitung `qty_actual − reject_qty` sehingga memotong reject **DUA KALI**.
Itulah sebab "chip 90 kok jadi 80". **Backend justru benar; layarnya yang salah.**
Ditambah layar tidak mengurangi qty yang sudah dikirim, jadi form mem-prefill angka yang
PASTI ditolak — pemakai baru tahu setelah klik Simpan.

Sebelum perbaikan ada **TIGA** rumus berbeda untuk satu pertanyaan ("boleh kirim berapa?"):
layar, pagar backend, dan pagar stok FG. Sekarang satu: `core/dispatch_capacity.py`

    sisa bisa kirim = lolos QC + hasil permak − sudah dikirim

`sudah dikirim` dihitung per po_item MELINTASI SEMUA surat jalan buyer — satu-satunya
definisi yang cocok dengan kolom yang benar-benar dilihat pemakai.

## 2) LINGKARAN REJECT → PERBAIKI → KIRIM AKHIRNYA TERTUTUP

`apply_rework_outcome()` dulu hanya menaikkan stok FG + buku kuantitas job dan **tidak
pernah** menyentuh `cmt_receipt_lines`, sementara pagar kirim membaca baris penerimaan
⇒ barang hasil permak MUSTAHIL dikirim, selamanya.

Sekarang permak `permak_sendiri` yang berhasil menambah **field BARU**
`cmt_receipt_lines.qty_reworked_ok`. Sengaja field baru, bukan menaikkan `qty_actual` /
menurunkan `reject_qty`: angka itu adalah HASIL INSPEKSI saat barang datang. Mengubahnya
retroaktif akan menggeser laporan variance, AP vendor (dibayar per qty lolos), dan gate
INV-14 secara diam-diam. `retur_ke_cmt` DIKECUALIKAN — barangnya masuk lagi lewat
penerimaan CMT baru, jadi menambahkannya di sini akan menghitung dua kali.

## 3) CACAT BARU YANG DITEMUKAN SAMBIL JALAN (P0) — SURAT JALAN YATIM

Terlihat di screenshot pemilik sebagai baris **"0 / 0 pcs" status Pending**, tetapi tidak
beliau laporkan. Sebabnya: `POST /api/buyer-shipments` menulis header surat jalan
(`insert_one(master_shipment)`) **SEBELUM** menjalankan pagar qty. Setiap Simpan yang
DITOLAK karena itu meninggalkan surat jalan tanpa item — dan nomornya ikut terpakai.
Pemakai lalu menyangka pengirimannya "sudah pernah dilakukan".

Perbaikan: seluruh pagar dipindah ke ATAS sebelum dokumen ditulis (aman — pagar hanya butuh
`items`/`source_receipt_ids`/`receiver_type`, tidak butuh `shipment_id`).
Migrasi `backend/migrations/2026_08_15_hapus_surat_jalan_buyer_yatim.py` (dry-run default)
membersihkan 2 dokumen yang sudah terbentuk. Nomor yang terpakai TIDAK didaur ulang —
nomor dokumen tidak boleh dipakai ulang (jejak audit). Dijaga invarian **E-5**.

## 4) DOKUMEN PDF — SEBABNYA TERUKUR, BUKAN SELERA

| Cacat | Sebab yang diukur | Perbaikan |
|---|---|---|
| Teks tumpang tindih | baris `SUBTOTAL {po}` ditulis ke kolom 'Color' selebar **44 pt** memakai `Table()` MENTAH berisi STRING (bukan `Paragraph`) ⇒ tidak ada word-wrap ⇒ meluber menimpa kolom angka | pakai `_pdf_data_table()` (Paragraph + lebar proporsional) |
| Tabel kecil, margin lega | lebar kolom hardcode berjumlah **569 pt**, lebar konten A4 landscape margin 12 mm = **773,8 pt** ⇒ terisi 73% | lebar proporsional dari `content_width(page)` |
| Melimpah keluar halaman | helper memakai `avail = 786` untuk landscape — **12 pt lebih lebar** dari halaman | `CONTENT_W_LANDSCAPE = 773,8` · `CONTENT_W_PORTRAIT = 527,2` |
| Label TOTAL bisa salah kolom | `total_row[-5] = 'TOTAL'` (indeks negatif) bergeser begitu ada kolom disembunyikan lewat konfigurasi PDF | baris TOTAL dibangun per KEY kolom |
| Tanda tangan menumpuk di kiri | `colWidths` hardcode 500 pt | mengikuti lebar konten halaman |

Subtotal per PO **DIHAPUS** dari dokumen kumulatif (keputusan pemilik) — rincian per
pengiriman sudah punya surat jalannya sendiri. Kolom **No. PO tetap ada** sehingga asal
setiap baris tidak hilang.

**Diukur dari PDF sungguhan:** tumpang tindih **0** pada 3 dokumen · tabel mengisi **100%**
lebar konten (garis tabel x 34,0 → 807,9 pt) · **0** teks keluar margin.

## 5) KIRIM MATERIAL KE CMT AKHIRNYA MEMOTONG STOK (H-1)

Yang diukur sebelum perbaikan: `POST /api/vendor-shipments` hanya menulis
`vendor_shipments` + `vendor_shipment_items`, dan baris itemnya adalah **PO ITEM GARMEN**
(`sku`/`size`/`qty_sent`) — **bukan material**. NOL mutasi `rahaza_material_stock`,
NOL dokumen pengeluaran, NOL jurnal ⇒ kain & aksesoris keluar gudang **tanpa jejak**.

Sekarang (PO **INTERNAL**): kebutuhan dihitung dari BOM aktif per (model, size) × qty
dikirim dengan konversi satuan SSOT `core.bom_uom`; Material Issue **terbit otomatis**
berstatus `issued`; lokasi dipilih sistem (stok terbanyak) sehingga **tidak ada field yang
perlu diketik**; stok berkurang; jurnal terposting; `vendor_shipments.material_issue_id`
menyimpan tautan dua arah.

**Tidak ada mekanisme potong stok baru.** Inti `approve_mi` DIEKSTRAK ke
`core/material_issue_engine.issue_material_issue()` supaya "mengeluarkan material dari
gudang" punya SATU definisi — pelajaran langsung dari Fase E: dua definisi untuk satu
pertanyaan = angka bercabang tanpa peringatan.

**Batasan penting, bukan tebakan:** hanya untuk `business_type != 'maklon'`. Pada MAKLON
material milik **KLIEN** — `create_mi_draft_from_job()` sudah menolak job maklon dengan
alasan yang sama. Memotong stok DA untuk maklon justru akan MENGHILANGKAN kain milik DA
yang tidak pernah dikirim. Dijaga invarian **H1-6**.

Stok kurang ⇒ surat jalan **DITOLAK** dengan angka per material, dan surat jalan yang baru
dibuat **DIROLLBACK**: 0 dokumen tertinggal, 0 stok terpotong sebagian.

Ditambah `POST /api/vendor-shipments/material-preview` + panel di form: pemakai melihat
material yang akan keluar (Keluar / Stok Tersedia / Nilai) **sebelum** Simpan, dengan
penanda merah bila kurang. Untuk maklon panel menjelaskan bahwa stok DA tidak dipotong.

## 6) BUKTI

* `bash scripts/gate.sh` → **VERDICT HIJAU**, 40 gate (baru: **INV-F16 · INV-F17 · INV-F18**)
* `verify_fase_e_kapasitas_kirim.py` **11/11** — skenario 100 = 90 lolos + 10 reject dibangun
  lewat ENDPOINT ASLI, lalu 10 pcs hasil permak benar-benar terkirim (total 100)
* `verify_fase_f_pdf_rapi.py` **5/5** — diukur dari bbox teks pada PDF sungguhan
* `verify_fase_h1_kirim_material_potong_stok.py` **6/6** — YRN-DA-CTN −2,5 kg &
  ACC-DA-LBL −10 pcs (tepat BOM × 10 pcs), jurnal Rp 55.000
* **Dibuktikan MERAH lewat sabotase:** mematikan penulisan `qty_reworked_ok` ⇒ 5 invarian
  merah dan pesannya mereproduksi keluhan pemilik ("sisa 0 pcs"); mematikan penerbitan MI
  ⇒ "stok turun 0 (harus 2.5)"
* `testing_agent_v3` iterasi 66: backend **100% (4/4)**, 17/17 invarian skrip, **0 bug**
* Uji LAYAR: modal dispatch menampilkan Lolos QC **90** · Hasil Permak 0 · Sudah Dikirim 0 ·
  Sisa Bisa Kirim **90**, Qty Kirim ter-prefill **90** (dulu 100 yang pasti ditolak), chip
  berbunyi "lolos QC 90 pcs (reject 10)"; tab **Kekurangan Kirim** tampil dengan 4 KPI+tabel

### CATATAN JUJUR
Panel pratinjau material pada form *Kirim Material CMT* terverifikasi di tingkat endpoint
(curl), lint, kompilasi esbuild, dan keberadaan `data-testid` di bundel hasil build —
**belum** dikemudikan penuh lewat browser karena dropdown kustom pada modul itu tidak punya
`role`/`data-testid` sehingga sulit diotomasi. Perilaku backend-nya sendiri sudah dijaga
penuh oleh gate INV-F18.

## 7) BERKAS BARU SESI INI

```
backend/core/dispatch_capacity.py
backend/core/material_issue_engine.py
backend/migrations/2026_08_15_hapus_surat_jalan_buyer_yatim.py
scripts/verify_fase_e_kapasitas_kirim.py
scripts/verify_fase_f_pdf_rapi.py
scripts/verify_fase_h1_kirim_material_potong_stok.py
```

## 8) URUTAN BERIKUTNYA (usulan)

1. **F3/F4** — rapikan 5 PDF tersering (SPP · Invoice · Slip Gaji · Picklist · SJ Vendor) +
   gate yang menolak `Table()` mentah di modul PDF.
2. **E-lanjutan** — tombol "Kirim Sisa" di tab Kekurangan Kirim yang membuka form dispatch
   terisi otomatis.
3. **H-2** — tombol BUAT di layar "Pengeluaran Material" (layar itu masih tanpa jalur create;
   pembuat MI dari UI lama memakai endpoint maklon `deprecated`).
4. **H-3** — menu baru "Buat Barcode" (endpoint label bahan & FG sudah ada, **0** pemanggil UI).
5. **H-4/H-9** — hapus "Scan Gudang" & "Kirim CMT" dari Portal Gudang (sudah diizinkan),
   tempelkan scan ke Inbound/Outbound, rapikan section.
6. **H-5/H-6/H-7** · **G** (penomoran auto/manual) · **D** (Dashboard Marketing ke sidebar).

---

# SESI 2026-08-14 (#12) — **F13 DITUTUP** + tiga temuan pemilik: form wajib pakai MASTER · kartu punya latar

> **Permintaan user:** *"lanjutkan development dari repo ini
> https://github.com/hajsisifufjsj/DA — sebelumnya development terhenti di
> `Now registering gate INV-F13 (one edit at a time, then syntax check)`"*
> lalu ditambah dua temuan: *"lauching product … masih belum tersambung dengan
> product yang ada di katalog masih custom field input … jangan sampai ada cacat
> logic seperti ini di form lainya pastikan kembali, silahkan verifikasi dulu
> untuk semua form lainya"* dan *"beberapa page di portal marketing cardsnya
> masih belum terdesign dengan baik seperti lupa di kasih background cardsnya,
> lalu ada beberapa yang masih abu abu itu perbaiki."*
> **Pilihan user:** urutan A → B → C; Fase B dibatasi 4–6 layar UANG/STOK paling mahal.

## 0) TITIK BERHENTI — DIUKUR, BUKAN DITEBAK

| Yang mungkin diduga | Kenyataan sesudah bring-up |
|---|---|
| "F13 belum dikerjakan" | **SALAH.** Keempat layar (`FinanceKasbon`, `EmployeeExpenseApproval`, `WMSFabricRolls`, `WMSDeliveryNotes`) sudah punya tabel ≥8 kolom + pengalih + urut + halaman + unduh; `test_core_f13` **39/39** pada jalan PERTAMA |
| "gate.sh tinggal ditambah entri" | **SALAH.** `insert_text` terakhir sesi lalu menyisipkan `fi` LIAR di baris 380 ⇒ `bash -n scripts/gate.sh` = *syntax error near unexpected token `else`* ⇒ **gate.sh tidak bisa dijalankan sama sekali** |
| — | **YANG BENAR-BENAR HILANG:** perbaikan `gate.sh`, entri gate `INV-F13`, dan dokumen sesi #12 |

Bring-up: `/app` datang sebagai template kosong ⇒ klon + `rsync` (env platform dipertahankan)
+ `bootstrap.sh` (92 detik, 6 akun HTTP 200). Frontend tetap **bundel statis**
(`scripts/rebuild_frontend.sh` sesudah setiap ubah `src`) — kuota 1 core / 2 GiB.

## 1) FASE A — F13 DITUTUP

| # | Isi | Bukti |
|---|---|---|
| A1 | `fi` liar dibuang; **satu edit, lalu `bash -n`** (aturan sesi #11) | `bash -n` lolos · 466 baris · ekor berkas utuh |
| A2 | gate **INV-F13** didaftarkan di bagian **STATIK** — sengaja BUKAN di blok `AUTH_READY`: penjaganya membaca BERKAS layar, bukan HTTP; kalau ditaruh di blok backend ia akan di-`skip` tiap backend mati, padahal justru saat itulah regresi layar paling mungkin lolos | `scripts/gate.sh` |
| A3 | `test_core_f13_layar_uang_bisa_dibawa.py` **39/39 HIJAU** | keluaran uji |
| A4 | **Dibuktikan MERAH lewat sabotase** (`rows={csvRows}` → daftar mentah) ⇒ `C-2·kasbon` gagal (38/39) ⇒ dipulihkan | keluaran uji |

## 2) TEMUAN PEMILIK #1 — "LAUNCHING PRODUCT MASIH CUSTOM FIELD"

### Yang diukur (bukan dugaan)
`marketing_product_launches`: **8 dari 8** dokumen tanpa `model_id`. Nama/bahan/model
teks bebas ("Gamis Busui Friendly DA-2026 Series 1", "Katun Linen Premium"), padahal
`rahaza_models` berisi produk DA sungguhan beserta varian FG, HPP, dan harga resmi.

**Kenapa ini bukan soal kenyamanan mengetik — tiga akibat berantai:**
1. **Master stok kotor.** `_auto_create_fg_from_launch()` MEMBUAT barang jadi dari teks:
   `code = style_code OR model OR product_name.replace(" ","-").upper()[:30]` ⇒ FG
   `GAMIS-BUSUI-FRIENDLY-DA-2026-S` tanpa `model_id`, tanpa varian, `hpp = 0`, kategori
   literal `"launch"`. Satu produk jadi **dua** barang di master stok ⇒ "stok produk ini
   berapa?" punya **dua jawaban** — dan tidak ada satu pun galat, hanya sebaris log info.
2. **Harga tak bisa direkonsiliasi** — rencana (ketikan) vs katalog (`harga_jual`) vs
   master (`retail_price`); tidak ada yang tahu ketiganya berhubungan.
3. **Ejaan = identitas** — "Katun Linen Premium" ≠ "katun linen premium" bagi mesin.

### Yang dikerjakan
* **`MasterProductSelect`** (`components/erp/pickers/`) — SATU pemilih ber-pencarian yang
  membaca `GET /api/marketing/catalogs/master-products`, endpoint **yang sama** dengan layar
  Katalog dari Master ⇒ dua layar mustahil menampilkan daftar produk berbeda.
* **`_resolve_master_model()`** — satu-satunya penulis field turunan master. Mengikuti
  pelajaran `received_at`/`closed_at`: **kiriman browser DIABAIKAN**. Dibuktikan runtime:
  POST membawa `product_name: "NAMA PALSU KIRIMAN BROWSER"` ⇒ yang tersimpan
  `"Celana Jogger Tapered Fit"`. PUT juga tidak bisa menimpanya (`MASTER_DERIVED_FIELDS`).
* **`model_id` WAJIB** pada pembuatan; produk tak dikenal / non-aktif ditolak **400 dengan
  alasan + jalan keluar**, bukan "gagal menyimpan".
* **Barang jadi kembar tidak bisa lahir lagi** — `_auto_create_fg_from_launch()` sekarang
  MENAUTKAN ke varian FG master yang sudah ada; tidak ada `insert_one` ke `rahaza_materials`.
  Dibuktikan: `launched` ⇒ jumlah FG **330 → 330**.
* **Warisan DIAKUI, bukan ditebak** — server menghitung `master_link.unlinked_total`, layar
  menampilkan banner amber + penanda "belum tertaut" per baris, form Edit mengatakan
  keadaannya. Migrasi `relink_product_launches_to_master.py` membuang **contoh** yang
  melanggar aturan (data contoh yang salah MENGAJARKAN pola salah) tetapi **menolak menebak**
  padanan untuk dokumen NYATA — menebak = menautkan ke produk salah tanpa bisa dibedakan.
* **Seeder** menyemai dari master; kalau master kosong, **0 contoh** (layar kosong + petunjuk
  lebih jujur daripada 8 rencana untuk produk yang tidak ada).

## 3) TEMUAN PEMILIK #2 — "VERIFIKASI SEMUA FORM LAIN"

`scripts/_audit_form_master_refs.py` memindai **582 layar** untuk 10 konsep ber-master.

**Jalan pertama: 13 temuan di 9 layar. Sesudah ditriase, 4 di antaranya TUDUHAN SALAH** —
dan itu penting: penjaga yang salah tuduh berhenti dipercaya, dan penjaga yang tidak
dipercaya sama dengan tidak ada penjaga (pelajaran sesi #10). Yang dikecualikan **beserta
alasannya**:

| Layar | Kenapa BUKAN cacat |
|---|---|
| `EmployeeExpenseGLMappingModule.category` | kategori **BIAYA** (Transportasi/Konsumsi) — dan form ini justru yang mendefinisikannya |
| `HRKPIModule.category` | kategori penilaian **KPI** ("Tanggung Jawab") |
| `CreateAssetDialog.model` | model **ASET IT** ("XPS 13 9310") — master aset tidak menyimpan daftar model laptop |
| `MaklonBuyerCatalogModule.product_name` | form ini **ADALAH** master katalog buyer; produk yang sedang dibuat belum ada di master mana pun |

**Yang benar-benar cacat & diperbaiki:**
| Layar | Perbaikan |
|---|---|
| `ProductLaunchModule` | 3 kotak ketik → `MasterProductSelect`; bahan & kode model jadi read-only dari master |
| `AIContentGeneratorModule` | produk dari master; kategori/material read-only; warna dari varian master. **Teks ini TAYANG ke pembeli** — bahan karangan di caption adalah klaim produk yang salah. Backend meresolusi ulang dari `model_id` dan menyimpannya di riwayat |
| `CMTComponentRequestModule` | produk dari master lewat `_resolve_product_from_master()` (opsional, karena permintaan bisa lahir dari inspeksi sebelum produk ditentukan — tetapi kalau diisi, WAJIB ada di master) |
| `MaklonAIQuoteModule` | `BuyerCatalogSelect` **dua mode**: artikel dari katalog, atau "artikel baru" yang DITANDAI `is_new_article`. Melarang teks bebas di sini justru berbahaya: staf akan memilih artikel yang MIRIP supaya form mau lanjut ⇒ penawaran menempel pada artikel yang salah |

**Dua jebakan audit yang sempat membuatnya BOHONG (dan sudah dijaga):**
* `product_name: e.target.value` ikut cocok dengan pola "diisi dari objek lain" ⇒ audit
  melaporkan **0 temuan padahal semua kotak ketik masih utuh**. Objek event kini dikecualikan.
* Aturan "ada pemilih di berkas ⇒ temuan gugur" terlalu longgar — satu berkas bisa punya
  pemilih **dan** kotak ketik sekaligus, dan justru itu bentuk yang paling mudah lolos.

## 4) TEMUAN PEMILIK #3 — "CARDS LUPA BACKGROUND, ADA YANG ABU-ABU"

Ketiganya punya satu sifat: **tidak pernah menjadi galat**, jadi build & lint tetap HIJAU
sementara layarnya rusak.

| Cacat | Jumlah | Sebab | Perbaikan |
|---|---:|---|---|
| **Kelas Tailwind RUSAK** `bg-foreground/[0.06]0` | **23** di 9 berkas | find/replace massal gagal: `bg-white/60` → ganti `white/6` jadi `foreground/[0.06]` → `…[0.06]0`. Angka nyasar sesudah `]` ⇒ Tailwind **tidak menghasilkan CSS apa pun** ⇒ elemen benar-benar tanpa latar | dipetakan ke padanan sadar-tema per KONTEKS (`bg-background/60`, `border-border`, `border-foreground/30`). Perkecualian disengaja: `UniversalScanPortal` memakai panel `bg-zinc-900` yang selalu gelap ⇒ `border-white/10` memang jawaban yang benar |
| **Abu-abu di atas abu-abu** `text-muted-foreground/50|60|70` pada `bg-muted` | **56** | `muted-foreground` sudah warna redup; modifikator opasitas hanya mencampurnya ke latar. Rasio kontras **1.9–2.6** (lantai 3.0) di tema terang MAUPUN gelap | modifikator dibuang ⇒ rasio ± 4.3 terang / 4.9 gelap |
| **Cadangan token MUSTAHIL** `localStorage.getItem('auth_token')` | **30** | `auth_token` **tidak pernah ditulis** (`setItem('auth_token')` = **0** kejadian); kunci yang benar `erp_token`. Begitu prop `token` kosong ⇒ `Bearer null` dan layar berkata "gagal memuat" tanpa sebab | semua → `erp_token`. Cadangan yang mustahil bekerja LEBIH BURUK daripada tidak ada cadangan: ia membuat orang berhenti mencurigai token |

**Bonus (ditemukan lewat lint saat memeriksa yang di atas):** `PickingListModal` memakai
`accountFilter` milik komponen **INDUK** ⇒ `ReferenceError` = layar putih begitu modal
dibuka. JavaScript baru mengeluh saat baris itu dijalankan, jadi build tidak pernah merah.
Sekarang dikirim sebagai prop — sekaligus membuat daftar picking mengikuti toko yang dipilih,
bukan diam-diam semua toko.

Audit yang mengukurnya (`scripts/_audit_ui_card_contrast.py`) **MENGHITUNG rasio kontras
WCAG**, bukan memakai ambang opasitas kasar. Versi pertama memakai "opasitas < 100 = cacat"
dan menuduh `text-foreground/80` yang rasionya **8.6** — sangat terbaca.

## 5) BUKTI

* `python3 test_core_f13_layar_uang_bisa_dibawa.py` → **39/39** · sabotase ⇒ 38/39 MERAH
* `python3 test_core_f14_form_pakai_master.py` → **34/34** · sabotase (kotak ketik nama
  produk dikembalikan) ⇒ 33/34 MERAH, dan **audit ikut menangkapnya**
* `python3 test_core_f15_kartu_terbaca.py` → **13/13** · sabotase (kelas rusak dikembalikan)
  ⇒ 12/13 MERAH
* `bash scripts/gate.sh` → **HIJAU** (3 gate baru: INV-F13 · INV-F14 · INV-F15)
* **Uji LAYAR** (Playwright, bundel statis): form Launching tidak lagi punya kotak ketik
  nama/bahan/model; pemilih master berisi 5 produk; memilih `CLN-0001` mengisi kategori
  *Celana*, HPP *Rp 76.000*, harga resmi *Rp 175.000*, 2 varian, dan Harga Asli otomatis
  *175000* — **0 page error · 0 console error**
* Runtime: POST tanpa `model_id` ⇒ **422** · `model_id` palsu ⇒ **400 dengan alasan** ·
  nama palsu kiriman browser ⇒ **diabaikan** · `launched` ⇒ FG **330 → 330** (0 produk kembar)

## 7) FASE B — **5 LAYAR UANG/STOK BERIKUTNYA DITUTUP** + cacat kelas dinamis

### Yang dipilih (dengan satu pertanyaan: kalau salah, berapa mahalnya?)

| Layar | Kelas | Kenapa mahal kalau salah |
|---|---|---|
| `HRKasbonModule` | UANG | antrian persetujuan kasbon — yang disetujui menjadi POTONGAN GAJI |
| `KasbonStaffModule` | UANG | riwayat kasbon karyawan sendiri; bukti yang sering diminta HR/Finance |
| `ReceivingModule` | STOK | **pintu masuk seluruh stok**; kolom *qty ditolak* adalah dasar klaim ke supplier |
| `ProcurementRequestModule` | UANG | permintaan pengadaan = komitmen belanja |
| `AccessoriesDashboard` | STOK+UANG | nilai stok aksesoris (Rp 9,66 juta) + item yang **belum dinilai** ⇒ ikut laporan keuangan |

**Tidak dipilih (dan alasannya dicatat):** `PutAwayModule` berbentuk **wizard 3 langkah**,
bukan layar daftar. Memasang tabel di situ akan merusak alurnya — pola tidak boleh
dipaksakan hanya supaya angka "layar KARTU-SAJA" turun.

### Keputusan yang tidak kosmetik
* **Pengurutan Pengadaan dipindah ke SERVER** (`sort_by`/`sort_dir` + daftar putih kolom).
  Kalau layar mengurutkan sendiri, ia hanya bisa mengurutkan halaman yang sedang dibuka:
  pertanyaan yang membuat kolom itu ada — *"PR mana yang nilainya PALING BESAR?"* — akan
  dijawab dengan urutan 15 baris pertama, dan **jawabannya terlihat meyakinkan padahal
  salah**. Itu lebih berbahaya daripada tidak ada pengurutan.
* **Item aksesoris yang belum dinilai DIAKUI di layar** (banner + penanda `BELUM`): selama
  angkanya > 0, total nilai stok pasti LEBIH RENDAH dari kenyataan — dan angka itu masuk
  laporan keuangan.
* **`PaginationLite` dipakai juga untuk paginasi SERVER** di Pengadaan, sehingga label
  "Menampilkan a–b dari N" menyebut jumlah SEBENARNYA, bukan jumlah baris yang kebetulan
  sedang dirender.

### CACAT BARU YANG DITEMUKAN SAAT MENGERJAKANNYA — kelas Tailwind DIRAKIT saat berjalan

    className={`bg-${color}-500/5 border border-${color}-500/20 …`}

Tailwind menghasilkan CSS dengan **membaca teks berkas sumber**; ia tidak menjalankan
JavaScript. Kelas itu **tidak pernah dibuat**. Yang membuatnya nyaris mustahil dilihat:
kadang kelasnya KEBETULAN ada karena berkas LAIN memakainya secara harfiah.

**Diukur langsung pada bundel hasil build (`main.*.css`) sebelum perbaikan:**
`bg-violet-500/5` **ADA** · `bg-teal-500/5`, `border-teal-500/20`, `border-teal-500/25`
**TIDAK ADA** ⇒ pada komponen KPI yang **sama**, kartu "violet" tampil benar sementara
kartu **"Perlu Diserahkan" (teal)** tampil **polos tanpa latar dan tanpa garis**. Itu
persis keluhan pemilik, dan sebabnya bukan selera.

Ditutup lewat `lib/tone.js` (nama warna boleh dinamis, **kelasnya harfiah**) untuk
**21 kejadian di 7 berkas**. Sesudah rebuild, `bg-teal-50`/`border-teal-200`/`bg-teal-100`
ada di CSS.

**Bonus (ditemukan lewat lint):** `TabBtn` di Pengadaan didefinisikan **di dalam** komponen
induk ⇒ React melihat TIPE komponen baru setiap render dan membongkar-pasang subtree-nya:
fokus keyboard hilang & state ter-reset saat pemakai sedang mengetik di penyaring. Gejalanya
terasa seperti "kadang aplikasinya nge-lag", jadi hampir tidak pernah dilaporkan sebagai bug.

### Bukti Fase B
* `test_core_f13_layar_uang_bisa_dibawa.py` diperluas 4 → **9 layar** ⇒ **84/84 HIJAU**
* Ambang KARTU-SAJA **diketatkan 74 → 69** (kalau dibiarkan longgar, layar baru tanpa tabel
  & unduhan lolos diam-diam dan "kemajuan" hanya berarti tidak memburuk)
* `test_core_f15_kartu_terbaca.py` **15/15** (penjaga kelas dinamis ditambahkan)
* `bash scripts/gate.sh` → **VERDICT HIJAU**
* `testing_agent_v3` iterasi 64: backend **4/4** · frontend **100%** · tampilan **100%** ·
  regresi **100%** · **0 bug**
* Uji LAYAR: kartu KPI teal kini berlatar; tabel stok aksesoris menampilkan **2 item belum
  dinilai** dengan banner yang menjelaskan akibatnya

## 6) URUTAN KERJA BERIKUTNYA

| Fase | Isi | Status |
|---|---|---|
| **B** | Konsolidasi **5 layar UANG/STOK** non-marketing (HRKasbon · KasbonStaff · Receiving · ProcurementRequest · AccessoriesDashboard) | ✅ **SELESAI** — KARTU-SAJA 74 → **69** |
| **C** | **F9 Pencairan/Settlement** — dibangun sebagai **INPUT MANUAL** (keputusan pemilik). Blokir BD-2 dihapus: tidak ada kolom yang ditebak. Jurnal **DRAFT**, selisih wajib DINAMAI sebelum bisa dijurnal | ✅ **SELESAI** |
| **D** | Sisa konsolidasi layar (69 kartu-saja · 133 tabel tanpa pengalih) · impor berkas pencairan saat contoh asli tersedia | ⏳ BERIKUTNYA |
| **D** | Dashboard Marketing hilang dari menu sidebar | 📝 BACKLOG |
| **E** | Portal Maklon — Dispatch ke Buyer: SSOT kapasitas kirim · hasil permak bisa dikirim · tab Kekurangan Kirim · surat jalan yatim ditutup | ✅ **SELESAI** (gate INV-F16, 11 invarian) |
| **F1+F2** | PDF surat jalan buyer: 0 tumpang tindih · tabel penuh lebar · subtotal per PO dibuang | ✅ **SELESAI** (gate INV-F17, 5 invarian) · F3/F4 masih backlog |
| **G** | Penomoran dokumen otomatis/manual + konfigurasi format | 📝 BACKLOG |
| **H-1** | Kirim Material CMT → Material Issue otomatis + stok berkurang + jurnal (produksi INTERNAL) | ✅ **SELESAI** (gate INV-F18, 6 invarian) |
| **H-2…H-9** | Sisa Portal Gudang (tombol BUAT MI · menu Buat Barcode · hapus Scan Gudang & Kirim CMT · Roll Kain ke Inbound · Surat Jalan lintas sumber) | 📝 BACKLOG |
| — | 3 toko DEMO tidak muncul di pemilih toko (penyaring `status=active`, dokumen DEMO tanpa field itu). Tidak mengganggu, layak dirapikan | 📝 |
| — | Master produk belum punya field **bahan**; `composition` terisi **0/331** FG ⇒ layar jujur menulis "Belum dicatat di Master Produk". Melengkapinya = pekerjaan Master Produk, bukan tambal di form | 📝 |

---

# BACKLOG TAMBAHAN (ditampung — ANALISIS dulu, **tidak mulai implementasi**)

> Konteks umum:
> * Screenshot user berasal dari environment PRODUCTION (contoh `sj-test-01` & `CMT-RCV-00041..44` tidak ada di DB preview `test_database`).
> * Frontend adalah **STATIC BUNDLE** (`static_server.js`) ⇒ setiap ubah React wajib `bash scripts/rebuild_frontend.sh`.
> * Pada sesi backlog ini: **tidak ada satu baris kode pun diubah** (sesuai permintaan user: analisis dulu).

## FASE D (BACKLOG, DITAMPUNG) — Dashboard Marketing hilang dari menu

**Status:** BACKLOG (ditunda atas permintaan user)

### Temuan verifikasi kode
- Komponen `frontend/src/components/erp/marketing/MarketingOverviewDashboard.jsx` (399 LOC) ADA dan berfungsi.
- `moduleRegistry.js:410` lazy-import OK; `moduleRegistry.js:1075` hanya memetakan id `marketing-overview` sebagai "deeplink backward compat".
- `portal-shell/portalNav.js` portal `toko` (title 'Marketing') punya 4 seksi (PENJUALAN MULTI-CHANNEL / KONTEN KAMPANYE & KREATOR / ANALITIK LIVE & AI / AFTER-SALES & PENGATURAN) — **tidak ada** item id `marketing-overview`.
  - **Akar masalah:** dashboard tidak pernah didaftarkan di sidebar.
- Satu-satunya jalan masuk: `MarketingReportsHub.jsx:145` merender `<MarketingOverviewDashboard/>` sebagai tab di dalam menu "Laporan Marketing" (id `marketing-reports`).
- **Data usang:** dashboard hanya memanggil 6 endpoint ringkasan:
  - `orders/summary`, `complaints/summary`, `health/summary`, `discounts/summary`, `product-launches/summary`, `content-calendar/summary`
  - Modul lebih baru belum dipakai: Sales/Omzet, Settlement F9 (`marketing_settlements`), Live Selling (`live-sessions/summary`), Ads/ROAS (`ads/summary`), Platform KPI (`platform-kpi/summary`), Target (`targets/monthly-summary`), Returns, Reviews, Samples, Fulfillment.

### Rencana kerja (bila di-approve)
- D1: daftarkan item `marketing-overview` label **"Ringkasan"** (icon `LayoutDashboard`) di paling atas seksi pertama portal `toko`; jadikan default landing.
- D2: endpoint agregat baru `GET /api/marketing/dashboard/overview?period=` (hormati RBAC scope toko) supaya **1 request** bukan 10.
- D3: rombak KPI + panel (Omzet, Order, Pencairan, AOV, Live, ROAS, Kirim, After-sales, Konten/Launch, Alert) + skeleton/empty/error state.
- D4: keputusan hapus/pertahankan tab lama di `MarketingReportsHub`.
- D5: rebuild frontend + gate + testing_agent.

## FASE E (BACKLOG) — Portal Maklon: Dispatch ke Buyer

**Status:** BACKLOG — **ANALISIS SELESAI**, IMPLEMENTASI **BELUM BOLEH MULAI**

### Laporan bug user (dari screenshot)
- Di modal **Buat Buyer Shipment**:
  - Chip receipt menulis `actual 90 pcs` namun baris tabel **"Maks (dari CMT)"** menjadi **80**.
  - `test-po-1` memperbolehkan input 100 di UI, namun saat Simpan ditolak: **"Maksimal kirim: 50 pcs"** (karena sudah pernah dispatch 50).
  - `test-po-2` seharusnya 100 (10 reject sudah diperbaiki) namun tetap 90/80.
- Tidak ada **dispatch list** untuk mengirim kekurangan (sisa outstanding) dengan alur 1 klik.
- UX membingungkan: UI mengizinkan input qty yang pasti ditolak oleh backend.

### Akar masalah terverifikasi — 3 definisi kapasitas kirim yang berbeda (bukan 1 SSOT)
1) **Frontend** `BuyerShipmentModule.jsx:176-194 buildConsItems()`
   - `cap = Σ(qty_actual − reject_qty)` (netto) **tanpa** mengurangi qty yang sudah didispatch.
   - `qty_shipped` di-*prefill* = cap penuh → user diarahkan ke angka yang **pasti ditolak**.
   - Sumber "90 jadi 80": chip receipt menampilkan `total_actual` (bruto 90) sedangkan baris tabel memakai netto (90−10 reject = 80) ⇒ **dua angka beda** untuk hal yang sama di satu layar.

2) **Backend** `buyer_shipment.py:85-187 _validate_source_receipts_cap()`
   - `max = Σ(qty_actual) − Σ(sudah didispatch efektif)`
   - **Tidak** mengurangi `reject_qty`.
   - Untuk kasus `test-po-1`: 100 actual − 50 sudah didispatch = 50.

3) **Backend** `_fg_precheck_for_dispatch()` memakai stok FG gudang (definisi ke-3) sebagai precheck.

### Akar masalah "10 reject sudah diperbaiki tapi tetap 90" (sinkron permak → dispatch)
- `dewi_cmt_permak.py` saat `selesai_berhasil` memanggil `core/production_qty_ledger.apply_rework_outcome()`:
  - menambah stok FG (release karantina) + menaikkan `production_job_items.qty_accepted/qty_repaired`
  - **tidak** mengubah `cmt_receipt_lines.reject_qty` / `qty_actual`
- Karena validasi dispatch membaca `cmt_receipt_lines`, hasil permak yang sudah jadi bagus **tidak pernah menambah kapasitas kirim**. Lingkaran 100→10 reject→diperbaiki→100 tidak tertutup untuk jalur dispatch.

### Rencana kerja (bila di-approve)
- E1 (P0): satukan SSOT kapasitas kirim.
  - Endpoint baru `GET /api/buyer-dispatch-capacity?buyer=&receipt_ids=` mengembalikan per `po_item_id`:
    `ordered`, `diterima_cmt_netto`, `reject_open`, `hasil_permak_ok`, `sudah_dikirim`, `sisa_bisa_kirim`, `stok_fg`.
  - Frontend & validator backend wajib membaca angka yang sama (hilangkan 3 definisi).
- E2 (P0): buat hasil permak ikut menambah kapasitas dispatch.
  - Opsi aman: field baru di SSOT penerimaan (mis. `cmt_receipt_lines.qty_reworked_ok`) sehingga angka historis `qty_actual/reject_qty` tidak dimutasi.
- E3 (P0 UX): perbaiki UI dispatch:
  - ganti kolom menjadi: `Order | Diterima CMT | Sudah Dikirim | Sisa Bisa Kirim`.
  - input di-*clamp* `max=sisa`; *prefill* = `sisa` (bukan cap penuh).
  - baris `sisa=0` disabled + badge "Lunas".
  - chip receipt tampilkan angka **netto siap kirim** (bukan bruto `actual`).
- E4 (P1): modul/layar baru **"Kekurangan Kirim (Dispatch List)"**:
  - daftar outstanding per buyer→PO→item (ordered, shipped, remaining, ready-stock)
  - tombol "Kirim Sisa" membuka form terisi otomatis
  - pola tabel F10 (sort/pagination/export CSV).

## FASE F (BACKLOG) — Perbaikan total format PDF

**Status:** BACKLOG — **ANALISIS SELESAI**

### Bug tervalidasi pada surat jalan buyer kumulatif
Lokasi: `operations_pdf.py` (`pdf_type='buyer-shipment'`, sekitar 1050–1086)
- **Tumpang tindih:** baris subtotal menulis `SUBTOTAL {po_no}` ke kolom indeks 6 ('Color') yg sempit, dan memakai `Table()` mentah (bukan `Paragraph`) ⇒ tidak ada word-wrap ⇒ teks meluber dan menimpa kolom angka.
- **Tabel kecil:** `cw` hardcode total 569pt, sementara lebar konten A4 landscape dengan margin 12mm ≈ 774pt ⇒ tabel hanya 73% lebar halaman.
- Dispatch PDF juga hardcode (`int(680/len(headers))`) — 680 bukan lebar konten.
- Helper yang benar sudah ada: `_pdf_data_table()` (Paragraph wrap + lebar proporsional), tetapi masih banyak tabel memakai `Table()` mentah.
- Bug halus helper: `avail=786` untuk landscape, padahal A4 landscape margin 12mm ≈ 774pt; portrait 515 juga tidak tepat.

### Permintaan user
- Format dokumen PDF harus profesional: tidak tumpang tindih, memanfaatkan lebar halaman.
- Untuk dokumen **kumulatif**, tidak perlu grouping/subtotal per PO; cukup total (karena sudah ada surat jalan per dispatch).
- Cakupan jangka panjang: semua dokumen PDF yang dapat diunduh harus dibersihkan dari layout hardcode.

### Rencana kerja (bila di-approve)
- F1 (P0): perbaiki PDF `buyer-shipment` (kumulatif) & `buyer-shipment-dispatch`:
  - pakai `_pdf_data_table()` dengan weights
  - hilangkan subtotal per PO pada kumulatif
  - tabel full width + angka rata kanan
- F2 (P0): betulkan ukuran `avail` di helper:
  - landscape 786 → 774
  - portrait 515 → 527 (sesuai A4 595pt minus margin 2×12mm)
- F3 (P1): migrasi bertahap semua `Table()` mentah → `_pdf_data_table()` mulai dokumen paling sering dicetak (SPP, invoice, payslip, picklist, surat jalan vendor, inspeksi).
- F4 (P1): gate test baru `INV-F16`:
  - menolak `Table(` mentah pada modul PDF tertentu
  - mengecek Σ colWidths ≈ lebar konten

## FASE G (BACKLOG) — Penomoran dokumen otomatis/manual

**Status:** BACKLOG — **ANALISIS SELESAI**, implementasi parsial sudah ada.

### Yang sudah ada
- `backend/utils/doc_numbering.py`:
  - token `{PREFIX}{YYYY}{YY}{MM}{DD}{SEQ}{SEQn}{PO}{BUYER}`
  - `seq_reset` yearly/monthly/never
  - counter atomik anti-duplikat + `preview_number()`
- `backend/routes/document_number_configs.py`:
  - GET list, GET/PUT per doc_type, POST preview
  - config ada `enabled`
- Frontend: `DocNumberingModule.jsx` + menu `sys-doc-numbering` (System Admin)

### Yang kurang
- Default config baru mencakup 2 doc_type: `buyer_shipment_da`, `buyer_shipment_buyer`.
- Dokumen lain masih hardcode prefix via `gen_prefixed_number` (contoh `CMT-RCV-`, `SJ-RWK-`, dll).
- Belum ada mode eksplisit **AUTO vs MANUAL**.
  - Saat ini implisit: kalau field nomor kosong → auto.
  - Akibat: user bisa mengetik nomor bebas (mis. `sj-test-01`) yang melanggar format.

### Rencana kerja (bila di-approve)
- G1: perluas config:
  - tambah `mode: 'auto'|'manual'|'auto_editable'`
  - tambah `validate_regex`
  - backend menolak nomor manual saat mode=auto
- G2: registry semua doc_type (SPP, surat jalan vendor, rework, CMT receipt, material request, PR, invoice, kasbon, retur produksi, dll) dalam satu tempat.
- G3: UI:
  - tampilkan semua doc_type + preview live + toggle mode
  - form dokumen: nomor read-only + hint preview saat mode auto
- G4: gate `INV-F17`:
  - menolak penggunaan `gen_prefixed_number` baru untuk doc_type yang sudah terdaftar

## FASE H (BACKLOG) — Portal Gudang: Inbound/Outbound tidak jelas + banyak menu mati

**Status:** BACKLOG — **ANALISIS SELESAI**, IMPLEMENTASI **BELUM DIMULAI**

### Bukti angka (hitung dokumen langsung, DB preview `test_database`)

| Lapisan `wh_*` (WMS) | Jumlah | Lapisan `rahaza_*`/operasional | Jumlah |
|---|---:|---|---:|
| `wh_pending_movements` | 0 | `rahaza_material_stock` | 22 |
| `wh_cmt_dispatches` | 0 | `rahaza_stock_ledger` | 153 |
| `wh_stock` | 0 | `rahaza_materials` | 343 |
| `wh_positions` | 0 | `rahaza_material_issues` | 2 |
| `wh_movements` | 0 | `vendor_shipments` | 2 (+3 item) |
| `wh_stock_movements` | 0 | `buyer_shipments` | 2 |
| `wh_delivery_notes` | 2 | `cmt_receipts` | 0 |
| `wh_fabric_rolls` | 4 | `cutting_orders` | 0 |

**Kesimpulan akar:** ada **dua gudang** di dalam kode — lapisan `wh_*` (WMS, mayoritas kosong)
dan lapisan `rahaza_*` (yang benar-benar dipakai). Portal Gudang mencampur keduanya tanpa
penanda → inbound/outbound terasa tidak jelas dan banyak menu menjadi layar kosong.

### H1 (P0) — Pengeluaran Material usang: pintu masuknya mati
- `RahazaMaterialIssueModule.jsx` (menu "Pengeluaran Material", 488 LOC) **tidak punya CREATE flow**. Hanya list/detail/confirm/submit/approve/reject/cancel/delete.
- `POST /api/rahaza/material-issues/draft-from-job` (auto dari BOM job) ada (`production_internal_adapter.py:335`) tetapi **0 pemanggil di frontend**.
- Satu-satunya pembuatan MI dari UI adalah jalur maklon lama `MaklonMaterialIssuePanel.jsx` → `POST /api/dewi/maklon/orders/{id}/material-issues` yang di backend sudah ditandai **deprecated=True**.
- Mesinnya sehat: `approve` MI (`rahaza_inventory_issues.py:148-243`) validasi stok per lokasi, `core.stock_service.issue()` atomik, log movement, dan `post_inventory_issue()` ke GL.

➡️ **Yang rusak bukan mesin, tapi pintu masuknya.**

### H2 (P0, paling mahal) — "Kirim Material CMT" tidak mengurangi stok apa pun
- Endpoint `POST /api/vendor-shipments` (`vendor_shipment.py:158-278`) hanya menulis `vendor_shipments` + `vendor_shipment_items`.
- Item yang dikirim adalah **PO ITEM garment** (`sku`, `size`, `color`, `qty_sent`) — bukan material.
- Tidak ada mutasi `rahaza_material_stock`, tidak ada `stock_service`, tidak ada MI, tidak ada jurnal, tidak ada update roll.

➡️ **Kain/aksesoris keluar gudang ke CMT tanpa jejak; stok tidak pernah turun.**

**Permintaan owner:** saat "Kirim Material CMT" dieksekusi, Material Issue dibuat **otomatis dari BOM** (kain + aksesoris + komponen lain), stok langsung berkurang, tanpa ketik ulang.

**Rencana (bila di-approve):** reuse `create_mi_draft_from_job()` + jalur approve/issue yang sudah benar; MI dibuat `issued` (atau auto-approve) saat shipment dikirim; `vendor_shipments` menyimpan `material_issue_id` untuk trace dua arah.

### H3 (P1) — Portal Cutting sudah benar; yang kurang adalah dokumen MI untuk keterlihatan outbound
- Cutting **sudah** punya mutasi stok yang benar:
  - `stock_service.issue(input_material_id, loc, input_used)` → stok kain berkurang
  - `stock_service.add(out_mat_id, loc, output_qty)` → stok potongan bertambah
  - roll fisik `wh_fabric_rolls.remaining_kg/remaining_m` dikurangi + movement dicatat
- Master potongan dibuat otomatis di `rahaza_materials` (idempoten, `is_cut_panel:True`, `unit:'pcs'`, ada `source_material_id` → ketelusuran).
- `cutting_orders` = 0 dokumen → belum ada bukti runtime.

**Yang kurang:** cutting memutasi ledger tanpa dokumen Material Issue resmi ⇒ outbound kain tidak muncul di daftar "Pengeluaran Material".

➡️ Perbaikan: terbitkan MI otomatis `ref_type='cutting_issue'` supaya satu daftar memuat semua arus keluar.

### H4 (P0) — Barcode: endpoint lengkap, UI-nya nol
Backend sudah punya 4 sistem label terpisah:
- **Bahan**: `GET /api/wms/materials/{id}/label-pdf` + `POST /api/wms/materials/labels/batch-pdf` → **0 pemanggil di frontend**
- **FG**: `GET /api/wms/fg/{id}/label-pdf` + `POST /api/wms/fg/labels/batch-pdf` + `POST /api/wms/fg/label-pdf/custom` → **0 pemanggil di frontend**
- **Rak/posisi**: `/api/wms/positions/{id}/label-pdf`, `/api/wms/racks/{id}/labels-pdf`, `/api/wms/labels/batch-pdf` → dipanggil, tapi `wh_positions` = 0 ⇒ tidak ada yang dicetak
- **Aset**: `/api/assets/{id}/barcode|qrcode|label-pdf` → ada UI, tapi satu-satu per aset

➡️ Barcode bahan & FG praktis tidak bisa diambil dari UI.

**Permintaan owner:** satu menu baru **"Buat Barcode"** untuk semua jenis (aset, bahan, FG, potongan, rak), dua mode:
- (a) otomatis dari produksi (pilih PO/job → artikel + qty mengikuti produksi)
- (b) manual (pilih item dari master data, isi qty)
Plus: pilih template, preview jumlah label, 1 PDF gabungan, riwayat cetak.

### H5 (P1) — Surat Jalan Gudang membaca koleksi yang bukan operasional
- `wms-delivery-notes` memakai `wh_delivery_notes` (2 dokumen) dengan penomoran `SJ/2026/05/0001`.
- Surat jalan operasional hidup di `vendor_shipments` (kirim ke CMT) dan `buyer_shipments` (dispatch buyer), dan keduanya punya PDF di `operations_pdf.py`.
- Ada klaim redirect "SSOT surat jalan = WMS Delivery Notes" tetapi koleksinya bukan yang dipakai operasional.

➡️ Terdapat 3 koleksi SJ paralel; perlu keputusan: jadikan `wh_delivery_notes` sebagai **lapisan daftar cetak lintas sumber** (read-only agregasi) atau pensiunkan dan arahkan ke sumber asli.

### H6 (P0) — "Kirim CMT" di Gudang adalah menu mati + duplikat
- `wms-cmt-dispatches` → `wh_cmt_dispatches` = 0 dokumen.
- Empat pintu legacy diarahkan ke modul kosong ini: `cmt-progress`, `do-management`, `prod-cmt-packing`, `maklon-packing`.
- Pekerjaan nyata sudah ada di `prod-shipments-vendor` (Portal Produksi & Maklon).

➡️ Backlog: hapus pintu Gudang, alihkan semua alias ke `prod-shipments-vendor`.

### H7 (P0) — "Scan Gudang" antreannya tidak pernah diisi
- `wh-scan` = `WMSModule(section:'receiving')` → membaca `GET /api/wms/pending` (`wh_pending_movements`).
- `wh_pending_movements` = 0.
- Endpoint pengisi antrean ada (`/api/wms/pending/create-from-production|create-from-shipment`) tetapi **tidak ada pemanggil di seluruh repo**.

➡️ Layar permanen kosong. Scan seharusnya melekat ke proses inbound/outbound, bukan menu terpisah.

### H8 (P1) — "Roll Kain" salah kamar & tidak terhubung ke inbound
- `wh_fabric_rolls` = 4 dokumen demo, dibuat manual dari tombol "+ Roll Baru".
- Inbound penerimaan tidak membuat roll otomatis → data harus diketik ulang.
- `wh_positions` = 0 sehingga roll tidak pernah benar-benar putaway.
- Roll dipakai sebagai input Cutting.

➡️ Roll Kain harus jadi bagian rantai inbound kain → cutting; pindahkan ke section inbound dan buat penerimaan kain menurunkan roll otomatis (sinkron dengan Fase G penomoran).

### H9 (P1) — Rapikan IA Portal Gudang (akar keluhan "menu berserakan")
Usulan struktur (tanpa membuat menu baru selain "Buat Barcode"):
- INVENTORI & STOK: Dashboard · Master Item · Stok & Akurasi · Alert & Reorder
- INBOUND: Penerimaan Barang (+scan-in) · Roll Kain · Penyimpanan · Karantina QC
- OUTBOUND: Pengeluaran Material (+scan-out + tombol BUAT) · Pick List · Fulfillment · Retur Fisik · Surat Jalan (daftar cetak lintas sumber)
- ALAT & AKSESORIS: Buat Barcode (baru) · Struktur Gudang · Satuan & Konversi · Audit Trail · Inbox Aksesoris
- DIHAPUS/DIREDIRECT: Scan Gudang (menempel ke proses) · Kirim CMT (duplikat Produksi) · Operasi Aksesoris (sudah redirect)

### Rencana kerja Fase H (bila di-approve)
Urutan berdasarkan kerusakan data (P0 dulu):
- H-1 (P0): "Kirim Material CMT" → auto-terbitkan Material Issue dari BOM + potong stok kain/aksesoris + posting GL + simpan `material_issue_id` dua arah.
- H-2 (P0): Pengeluaran Material → tombol BUAT hidup (dari job/BOM & manual dari master), pensiunkan endpoint maklon deprecated.
- H-3 (P0): Menu baru "Buat Barcode" — auto dari produksi + manual dari master, batch PDF, riwayat cetak.
- H-4 (P0): Bersihkan menu mati: hapus "Scan Gudang" & "Kirim CMT" dari Gudang; tempelkan scan-in/scan-out ke inbound/outbound; alihkan alias.
- H-5 (P1): Pindahkan "Roll Kain" ke inbound + penerimaan kain menurunkan roll otomatis.
- H-6 (P1): Cutting menerbitkan Material Issue (`cutting_issue`) agar arus keluar kain muncul di satu daftar.
- H-7 (P1): Surat Jalan Gudang → agregasi lintas sumber (vendor_shipments + buyer_shipments + wh_delivery_notes) atau dipensiunkan.
- H-8 (P1): Gate test baru:
  - `INV-F18` menolak menu menunjuk koleksi kosong / endpoint tanpa pemanggil
  - `INV-F19` memastikan setiap arus keluar gudang punya dokumen MI + baris ledger

### Catatan lintas fase
- Aturan F14 (input wajib dari master) berlaku untuk "Buat Barcode".
- Fase G penomoran dipakai untuk nomor MI, nomor roll, nomor SJ.
- Frontend static bundle ⇒ wajib rebuild setiap perubahan.

## ANTREAN LAMA (tetap backlog)
- Konsolidasi ±69 layar KARTU-SAJA ke pola tabel F10.
- Rekap Pencairan Bulanan (tren fee platform).
- Lengkapi data bahan baku Master Produk (hilangkan "belum dicatat").
- Refactor komponen React yang mendefinisikan sub-komponen di dalam render.

---

# SESI 2026-08-14 (#11) — **F11 + F12 DITUTUP**: pratinjau impor per baris · berkas ekspor tidak boleh masuk toko yang salah

> (Bagian sesi #11 dan sebelumnya dipertahankan UTUH dari plan lama; tidak diubah pada update ini.)

## Status fase (ringkas, diperbarui)
- F0 ✅
- F1 ✅
- F2 ✅
- F3 🟡 (monitoring UI selesai; sisa impor Ekspor B/C masih menunggu BD-1)
- F4 ✅
- F5 ✅
- F6 ✅ **(inti RBAC per toko + jejak sudah terbukti)**
- F7 ✅ **(inti konten+kreator sudah terbukti)**; berikutnya: **impor KPI konten + scorecard**
- F8 🟡 (laporan mingguan selesai; sisa impor/form KPI menunggu BD-3)
- F9 ✅ **SELESAI** (input manual)
- F10 ⏳
- F13 ✅
- F14 ✅
- F15 ✅
- **F16 ✅** (2026-08-15) satu rumus sisa kirim buyer + hasil permak bisa dikirim + surat jalan yatim ditutup
- **F17 ✅** (2026-08-15) dokumen PDF rapi: 0 tumpang tindih, tabel penuh lebar halaman
- **F18 ✅** (2026-08-15) kirim material ke CMT menerbitkan MI + memotong stok + jurnal (produksi internal)
- **F19 ✅** (2026-08-16) Gudang: tombol **Buat MI** (admin gudang + supervisor produksi), menu
  **Buat Barcode** (2 tab, jumlah lembar, otomatis dari PO, riwayat cetak), dua menu mati
  (`wh-scan`, `wms-cmt-dispatches`) dilepas dari sidebar tanpa mematikan deep-link

> Catatan: fase huruf D/E/F/G/H di dokumen ini adalah hasil analisis 2026-08-15.
> **E, F1/F2, H-1 (sesi #13) dan H-2 · H-3 · H-4/H-9 (sesi #14) SUDAH SELESAI.**
> Yang masih BACKLOG: D · F3/F4 · G · H-5 · H-6 · H-7 · H-8 — rinciannya di `memory/ROADMAP.md`.
