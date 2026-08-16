"""Katalog jenis dokumen yang nomornya BISA dikonfigurasi owner.

Sumber kebenaran daftar ini = pemetaan `scripts/map_document_numbers.py`
(semua pemanggilan `utils.counters.gen_prefixed_number`). Menambah entri di
sini TIDAK membuat generator baru — hanya memberi label & format bawaan untuk
layar konfigurasi. Kunci = "<koleksi>.<field>".

Token yang tersedia untuk SEMUA jenis:
    {YYYY} {YY} {MM} {DD}  → tanggal pembuatan dokumen
    {SEQ:n}                → nomor urut, n = jumlah digit (WAJIB, harus di akhir)
Token khusus per jenis ada di kolom `tokens`.
"""

DOC_NUMBER_REGISTRY = [
    # ── GUDANG ────────────────────────────────────────────────────────────────
    # FASE H-5 (2026-08-16) — entri BARU 'Roll Kain'. Nomor roll dulu WAJIB
    # DIKETIK (`RollIn.roll_no`), padahal roll adalah barang fisik yang datang
    # belasan sekaligus: nomor ketikan membuat dua gulungan bisa bernomor sama dan
    # tidak ada yang bisa membuktikan gulungan mana yang dipotong. Mode `auto`
    # menjadi bawaan — roll lahir dari penerimaan barang, bukan dari ketikan.
    {"key": "wh_fabric_rolls.roll_no", "label": "Roll Kain", "group": "Gudang",
     "default_format": "RL-{YYYY}{MM}-{SEQ:4}", "tokens": [], "default_mode": "auto",
     "catatan": "Dibuat otomatis saat penerimaan kain (rincian roll per gulungan)."},
    {"key": "wh_delivery_notes.sj_number", "label": "Surat Jalan", "group": "Gudang",
     "default_format": "{TIPE}/{YYYY}/{MM}/{SEQ:4}", "tokens": ["TIPE"],
     "catatan": "TIPE = jenis surat jalan (mis. SJ, SJK)."},
    {"key": "wh_cmt_dispatches.dispatch_no", "label": "Pengiriman ke CMT", "group": "Gudang",
     "default_format": "CMD/{YYYY}/{MM}/{SEQ:4}", "tokens": []},
    {"key": "wh_returns.return_code", "label": "Retur Gudang", "group": "Gudang",
     "default_format": "WH-RET-{SEQ:5}", "tokens": []},
    {"key": "wh_opname_sessions2.session_no", "label": "Sesi Opname (Aksesoris)", "group": "Gudang",
     "default_format": "OPNAME-{SEQ:4}", "tokens": []},
    {"key": "wh_opname3_sessions.session_no", "label": "Sesi Opname (Gudang)", "group": "Gudang",
     "default_format": "OPN-{YYYY}{MM}-{SEQ:4}", "tokens": []},
    {"key": "rahaza_grn_inspections.inspection_no", "label": "Inspeksi Penerimaan", "group": "Gudang",
     "default_format": "INS-{YYYY}{MM}-{SEQ:4}", "tokens": []},
    {"key": "rahaza_material_issues.mi_number", "label": "Pengeluaran Material", "group": "Gudang",
     "default_format": "MI-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},
    {"key": "warehouse_receiving.receipt_number", "label": "Penerimaan Barang (GR)", "group": "Gudang",
     "default_format": "GR-{SEQ:5}", "tokens": [],
     "catatan": "Dibuat otomatis saat PO pembelian diterima di gudang."},
    {"key": "rahaza_fg_issues.issue_number", "label": "Pengeluaran Barang Jadi", "group": "Gudang",
     "default_format": "FGI-{YYYY}{MM}{DD}-{SEQ:4}", "tokens": []},
    {"key": "rahaza_fg_reservations.reservation_no", "label": "Reservasi Barang Jadi", "group": "Gudang",
     "default_format": "RES-{YYYY}{MM}-{SEQ:4}", "tokens": []},
    {"key": "rahaza_shipments.shipment_number", "label": "Pengiriman", "group": "Gudang",
     "default_format": "SHP-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},

    # ── PENGADAAN ─────────────────────────────────────────────────────────────
    {"key": "dewi_procurement_requests.request_number", "label": "Permintaan Pengadaan (PR)", "group": "Pengadaan",
     "default_format": "PR-{YYYY}{MM}-{SEQ:4}", "tokens": []},
    {"key": "rahaza_purchase_orders.po_number", "label": "Purchase Order (PO)", "group": "Pengadaan",
     "default_format": "PO-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},
    {"key": "acc_purchase_requests.pr_number", "label": "Permintaan Beli Aksesoris", "group": "Pengadaan",
     "default_format": "ACC-PR-{SEQ:4}", "tokens": []},

    # ── PRODUKSI & MAKLON ─────────────────────────────────────────────────────
    # FASE G (2026-08-16) — DUA entri di bawah BARU. Nomor PO produksi (sumber
    # nomor SPP) selama ini 100% diketik tangan: `create_po_internal()` menolak
    # permintaan tanpa `po_number` dan menyimpan apa pun yang dikirim. Isinya
    # sekarang bercampur bebas (`PO-INT-DEMO-1`, `PO-MK-DEMO-1`, `PO-MKL-GAB-A`).
    # `default_mode: manual` menjaga perilaku hari ini APA ADANYA — yang berubah
    # hanyalah nomor manual wajib mengikuti polanya, dan owner boleh memindah ke
    # OTOMATIS kapan pun dari layar Penomoran Dokumen.
    # Satu koleksi+field menampung dua jenis dokumen (internal vs maklon) ⇒ kunci
    # kedua memakai override `collection`/`field` seperti pola invoice AR.
    {"key": "production_pos.po_number", "label": "PO Produksi Internal (SPP)", "group": "Produksi",
     "default_format": "PO-INT-{YYYY}{MM}-{SEQ:4}", "tokens": [], "default_mode": "manual",
     "catatan": "Dipakai juga sebagai nomor SPP. Mode manual = nomor diketik tetapi "
                "wajib mengikuti pola ini."},
    {"key": "production_pos.po_number_maklon", "label": "PO Maklon (Produksi)", "group": "Maklon",
     "default_format": "PO-MKL-{YYYY}{MM}-{SEQ:4}", "tokens": [], "default_mode": "manual",
     "collection": "production_pos", "field": "po_number",
     "catatan": "PO maklon yang tersimpan di koleksi PO produksi (SSOT satu penulis)."},
    {"key": "cutting_orders.number", "label": "Order Cutting", "group": "Produksi",
     "default_format": "CUT-{YYYY}{MM}-{SEQ:4}", "tokens": []},
    {"key": "dewi_cmt_permak.permak_number", "label": "Permak / Perbaikan", "group": "Produksi",
     "default_format": "PMK/{YYYY}/{MM}/{SEQ:4}", "tokens": []},
    {"key": "cmt_receipts.receipt_code", "label": "Penerimaan FG dari CMT", "group": "Produksi",
     "default_format": "CMT-RCV-{SEQ:5}", "tokens": []},
    {"key": "production_material_returns.ref_no", "label": "Retur Material Produksi", "group": "Produksi",
     "default_format": "PMR/{YYYY}/{MM}/{SEQ:4}", "tokens": []},
    {"key": "dewi_cmt_component_requests.request_code", "label": "Permintaan Komponen Kurang", "group": "Produksi",
     "default_format": "CMP-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},
    {"key": "dewi_maklon_samples.sample_code", "label": "Sampel Maklon", "group": "Maklon",
     "default_format": "SMP-{YYYY}{MM}-{SEQ:2}", "tokens": []},
    {"key": "dewi_maklon_credit_notes.credit_note_number", "label": "Nota Kredit Maklon", "group": "Maklon",
     "default_format": "CN-MKL-{SEQ:5}", "tokens": []},
    {"key": "dewi_cmt_payments.payment_code", "label": "Pembayaran CMT", "group": "Maklon",
     "default_format": "PAY-CMT-{SEQ:5}", "tokens": []},
    # ── tahap 2 (2026-08-05): 11 penghasil nomor manual dipusatkan ────────────
    {"key": "dewi_maklon_pos.po_number", "label": "PO Maklon", "group": "Maklon",
     "default_format": "MKL-{KLIEN}-{YYYY}-{SEQ:4}", "tokens": ["KLIEN"],
     "catatan": "KLIEN = kode klien maklon (mis. ARN)."},
    {"key": "dewi_maklon_dispatches.dispatch_number", "label": "Pengiriman Maklon ke Klien",
     "group": "Maklon", "default_format": "DISP-{KLIEN}-{YYYY}{MM}{DD}-{SEQ:3}",
     "tokens": ["KLIEN"]},
    {"key": "dewi_maklon_invoices.invoice_number", "label": "Invoice Maklon (manual)",
     "group": "Maklon", "default_format": "{PREFIX}-{YYYY}-{SEQ:4}", "tokens": ["PREFIX"],
     "catatan": "PREFIX mengikuti Pengaturan Sistem 'maklon_invoice_prefix' (bawaan INV-MKL)."},
    {"key": "dewi_maklon.ar_invoice_number", "label": "Invoice Maklon otomatis (AR)",
     "group": "Maklon", "default_format": "INV-MKL-{YYYY}-{SEQ:4}", "tokens": [],
     "collection": "rahaza_ar_invoices", "field": "invoice_number",
     "catatan": "Dibuat otomatis saat PO Maklon dikonfirmasi. Tersimpan di koleksi "
                "invoice piutang, terpisah dari nomor AR Finance."},
    {"key": "vendor_jobs.job_number", "label": "Job Vendor (Portal Vendor)", "group": "Maklon",
     "default_format": "VJ-{SEQ:5}", "tokens": []},

    # ── KEUANGAN ──────────────────────────────────────────────────────────────
    {"key": "rahaza_journal_entries.je_number", "label": "Jurnal Umum (JE)", "group": "Keuangan",
     "default_format": "JE-{YYYY}{MM}{DD}-{SEQ:4}", "tokens": []},
    {"key": "rahaza_ar_invoices.invoice_number", "label": "Invoice Piutang (AR)", "group": "Keuangan",
     "default_format": "AR-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},
    {"key": "rahaza_credit_notes.cn_number", "label": "Nota Kredit", "group": "Keuangan",
     "default_format": "CN-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},
    {"key": "rahaza_bank_transfers.ref_number", "label": "Transfer Bank", "group": "Keuangan",
     "default_format": "BT-{YYYY}{MM}{DD}-{SEQ:4}", "tokens": []},
    {"key": "rahaza_fixed_assets.asset_code", "label": "Aset Tetap", "group": "Keuangan",
     "default_format": "FA-{SEQ:5}", "tokens": []},
    {"key": "rahaza_orders.order_number", "label": "Order Penjualan", "group": "Keuangan",
     "default_format": "ORD-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},
    {"key": "rahaza_ap_invoices.invoice_number", "label": "Invoice Hutang (AP dari GR)",
     "group": "Keuangan", "default_format": "AP-{YY}{MM}-{SEQ:4}", "tokens": []},

    # ── SDM ───────────────────────────────────────────────────────────────────
    {"key": "rahaza_payroll_runs.run_number", "label": "Run Penggajian", "group": "SDM",
     "default_format": "PAY-{YYYY}{MM}-{SEQ:4}", "tokens": []},
    {"key": "dewi_kasbon_requests.request_number", "label": "Pengajuan Kasbon", "group": "SDM",
     "default_format": "KSB-{YYYY}{MM}-{SEQ:5}", "tokens": []},
    {"key": "rahaza_employee_loans.loan_number", "label": "Pinjaman Karyawan", "group": "SDM",
     "default_format": "LOAN-{SEQ:5}", "tokens": []},
    {"key": "dewi_assets.asset_number", "label": "Aset Inventaris", "group": "SDM",
     "default_format": "AST-{YYYY}-{SEQ:4}", "tokens": []},
    {"key": "rahaza_expense_claims.claim_number", "label": "Klaim Biaya Karyawan", "group": "SDM",
     "default_format": "EC-{YYYY}{MM}-{SEQ:4}", "tokens": []},
    {"key": "employee_travel_requests.trip_number", "label": "Permohonan Perjalanan Dinas",
     "group": "SDM", "default_format": "TR-{YYYY}{MM}-{SEQ:4}", "tokens": []},
    {"key": "employee_travel_settlements.settlement_number", "label": "Penyelesaian Perjalanan Dinas",
     "group": "SDM", "default_format": "TS-{YYYY}{MM}-{SEQ:4}", "tokens": []},

    # ── LAIN-LAIN ─────────────────────────────────────────────────────────────
    {"key": "dewi_accessory_requests.request_code", "label": "Permintaan Aksesoris", "group": "Aksesoris",
     "default_format": "AR-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},
    {"key": "dewi_kreator_requests.request_code", "label": "Permintaan Kreator", "group": "Marketing",
     "default_format": "REQ-KR-{YYYY}{MM}{DD}-{SEQ:3}", "tokens": []},

    # ── SKU / KODE MASTER ─────────────────────────────────────────────────────
    {"key": "rahaza_materials.code", "label": "SKU Aksesoris Baru", "group": "SKU / Kode Master",
     "default_format": "ACC-{SEQ:4}", "tokens": []},
    {"key": "rahaza_materials.cut_panel_code", "label": "SKU Potongan (Cutting)", "group": "SKU / Kode Master",
     "default_format": "CUT-{STYLE}-{WARNA}-{SIZE}", "tokens": ["STYLE", "WARNA", "SIZE"],
     "sequenced": False,
     "catatan": "Kode potongan hasil cutting. Tanpa nomor urut — kombinasi style/warna/ukuran sudah unik."},
]

REGISTRY_BY_KEY = {e["key"]: e for e in DOC_NUMBER_REGISTRY}
GROUPS = sorted({e["group"] for e in DOC_NUMBER_REGISTRY})


def target_of(entry: dict) -> tuple:
    """(koleksi, field) NYATA tempat nomor disimpan.

    Umumnya diturunkan dari `key` ("<koleksi>.<field>"), tetapi entri boleh
    menimpanya lewat `collection`/`field` bila satu koleksi menampung dua jenis
    nomor (mis. invoice AR Finance vs invoice maklon otomatis).
    """
    coll, fld = entry["key"].rsplit(".", 1)
    return entry.get("collection") or coll, entry.get("field") or fld
