# INVARIANTS.md — SSOT Invarian CV. Dewi Aditya ERP

> Diadaptasi dari metodologi Rahaza-Travel. Setiap invarian punya verifier otomatis di
> `/app/scripts/`. Jalankan `bash scripts/gate.sh`. Perbarui file ini saat menemukan
> invarian baru. **"Selesai" hanya sah bila gate HIJAU (lihat `GATE_RECEIPT.md`).**

## Cara baca
- **FAIL** = pelanggaran keras (blok klaim selesai).
- **WARN** = anomali/semantic-smell (didokumentasikan, non-blok).
- **SKIP** = tak dapat diuji sekarang (backend/auth mati) — **bukan** PASS.

---

## A. Finance / General Ledger — `verify_data_integrity.py`
| ID | Invarian | Koleksi | Sifat |
|---|---|---|---|
| INV-GL-1 | Tiap jurnal seimbang: `total_debit == total_credit == Σ lines.debit/credit` | `rahaza_journal_entries` | FAIL |
| INV-GL-2 | Trial-balance global: Σ debit posted == Σ credit posted | idem | FAIL |
| INV-GL-3 | `line.account_code` ada di CoA aktif | `rahaza_coa_accounts` | FAIL |
| INV-JL-1 | `rahaza_journal_lines.je_id` menunjuk entry yang ada (no orphan) | `rahaza_journal_lines` | WARN |

## B. Accounts Receivable / Payable
| ID | Invarian | Sifat |
|---|---|---|
| INV-AR-1 | AR `balance ∈ [0, total]` (tak minus, tak lebihi total) | FAIL |
| INV-REF-1b | `ar_payments` menunjuk `ar_invoices` yang ada | WARN |
| INV-AP-1 | AP `amount >= 0` | FAIL |

## C. Maklon (RC-7 basis pajak — KALIBRASI PENTING)
| ID | Invarian | Sifat |
|---|---|---|
| INV-MKL-1 | `amount_paid` (tax-incl) <= total invoice tax-inclusive | FAIL |
| INV-MKL-2 | Smell: `amount_paid` (tax-incl) vs `total_value` (pra-pajak) tercampur dalam 1 dok | WARN |

> Catatan: `amount_paid` di `dewi_maklon_pos` SUDAH termasuk PPN 11% (= total `dewi_maklon_invoices`),
> sedangkan `total_value` PRA-pajak. Jangan bandingkan mentah (menghasilkan "overpay" palsu).

## D. Inventory / WMS
| ID | Invarian | Sifat |
|---|---|---|
| INV-STK-1 | Stok tak negatif (`material_stock.qty`, `materials.current_stock`) | FAIL |
| INV-REF-1a | `material_stock.material_id` ada di `materials` | WARN |

## E. Penomoran dokumen (RC-5)
| ID | Invarian | Sifat |
|---|---|---|
| INV-CNT-1 | Nomor dok unik: `je_number, wo_number, ap_number, invoice_number, po_number` | FAIL |
| CC1 | N create paralel → semua 200 nomor UNIK / clean-4xx, **tak ada 5xx** | FAIL |

## F. HR / Cuti
| ID | Invarian | Sifat |
|---|---|---|
| INV-LEAVE-1 | `used ∈ [0, allocated+adjustments]` (tak minus, tak over-consume) | FAIL |

## G. Produksi
| ID | Invarian | Sifat |
|---|---|---|
| INV-WO-1 | `completed_qty ∈ [0, target]` | FAIL |

## H. Numeric bounds
| ID | Invarian | Sifat |
|---|---|---|
| INV-NUM-1 | Uang/qty tak negatif di koleksi finansial kunci | FAIL |

## I. State-machine — `verify_state_machine.py`
| ID | Invarian | Sifat |
|---|---|---|
| SM1 | Post jurnal non-draft ditolak (400) | FAIL |
| SM2 | Void jurnal voided ditolak (400) — idempotent, no double reversal | FAIL |
| SM3 | Delete jurnal non-draft ditolak (400) | FAIL |
| SM4 | Jurnal tak-seimbang ditolak (400) | FAIL |

## J. Adversarial — `verify_adversarial_5xx.py`
| ID | Invarian | Sifat |
|---|---|---|
| INV-5XX-01 | Input hostile (non-numerik, tipe salah, string raksasa, dst) → 4xx, **bukan 5xx** | FAIL |

## K. Kontrak FE↔BE — `preflight/verify_fe_be_contract.py`  (INV-CONTRACT-01)
| ID | Invarian | Sifat |
|---|---|---|
| CONTRACT-A | Tidak ada duplicate route `(METHOD, path)` (FastAPI pakai definisi TERAKHIR → handler pertama mati diam-diam) | HIGH (blok) |
| CONTRACT-B | Setiap panggilan API FE `${API}/api/...` cocok dgn route backend (OpenAPI SSOT) | WARN (triase) |
| CONTRACT-C | Route backend yang tak dipanggil FE (orphan / hidden) | INFO |

## L. Auth coverage — `guardrails/verify_auth_coverage.py`  (INV-AUTH-01)
| ID | Invarian | Sifat |
|---|---|---|
| AUTH-01 | Tiap endpoint menegakkan auth (langsung/`Depends`/helper `_require_*`/`require_*_auth`/verifikasi token), kecuali `PUBLIC_ALLOWLIST` (login/register/health/webhook/public) | mutation=HIGH, GET=MED |

## M. RBAC / kebocoran akses — `guardrails/verify_rbac_idor.py`  (INV-RBAC-01)  ★RUNTIME ★BLOCKING (gate.sh)
| ID | Invarian | Sifat |
|---|---|---|
| RBAC-UNAUTH | GET parameterless tanpa token → 401/403 (bukan 200) | sensitif=HIGH (BLOK), lain=MED (advisory) |
| RBAC-XROLE | Role rendah (mis. `operator`) menembak endpoint portal lain (jurnal/AR/AP/payroll/COA) → **403**, bukan 200 (eskalasi privilege) | HIGH (BLOK) |

> Ditegakkan di kode via `shared.require_portal(request, *portal_ids)` (SSOT `check_portal_access`)
> dan `require_portal_dep()` sebagai router-level dependency pada router finance/HR
> (rahaza_journals, rahaza_finance, rahaza_coa, rahaza_payroll_runs) + auth pada `/api/financial-recap`.
> SUPER_ROLES otomatis lolos; izin eksplisit (`*`, `<portal>.view/manage`) dihormati.

## N. Anti-pola statik — `guardrails/verify_static_antipatterns.py`  (INV-STATIC-01)
| ID | Invarian | Sifat |
|---|---|---|
| SA-RC5 | Tak ada `count_documents()+1` untuk penomoran; pakai `utils.counters.gen_prefixed_number` (atomic). Koleksi unique-indexed=HIGH (500 E11000), lain=MED (nomor dup) | HIGH/MED |
| SA-5XX | Koersi numerik input klien harus di-guard try/except→400 (bukan 500) | MED |
| SA-TZ / SA-EXC | datetime naive & `except:` telanjang | LOW |

## O. Integritas navigasi — `guardrails/check_nav_map.py`  (INV-NAV-01)  ★STATIC ★BLOCKING (gate.sh)
| ID | Invarian | Sifat |
|---|---|---|
| NAV-SINGLE | Tak ada section beranggota 1 item (langgar MECE/cohesion) | HIGH (BLOK) |
| NAV-EMPTY | Tak ada section 0 item | HIGH (BLOK) |
| NAV-GHOST | Tiap moduleId menu ADA di `MODULE_REGISTRY` (kecuali `isHeader`) | HIGH (BLOK) |
| NAV-DUP | Tak ada moduleId duplikat DALAM satu portal (lintas-portal boleh) | HIGH (BLOK) |
| NAV-DEPTH | Kedalaman IA ≤ 4 (Portal→Section→Group→Item) | MED |
> SSOT struktur IA: `memory/IA_BLUEPRINT.md`. Self-test-proven (inject→MERAH→revert→HIJAU).

## P. Batas numerik schema — `guardrails/verify_numeric_bounds.py`  (INV-NUM-01)  ★STATIC ★ADVISORY| ID | Invarian | Sifat |
|---|---|---|
| NUM-UNBOUND | Field uang/kuantitas di Pydantic model wajib `ge=`/`gt=` (tolak negatif/absurd) | MED (report-only; baseline 134 field → backlog fix) |

## U. Satuan material (multi-UOM) — `guardrails/verify_uom_integrity.py`  (INV-UOM-01)  ★RUNTIME ★BLOCKING
| ID | Invarian | Sifat |
|---|---|---|
| INV-UOM-1 | `rahaza_materials.unit_cost` **selalu** harga per **satuan dasar**. Satuan lain hanya alat bantu entri; hasil konversinya yang disimpan. `cost_uom` tidak boleh persist ≠ satuan dasar. | FAIL |
| INV-UOM-2 | Semua qty di `rahaza_material_stock`, `rahaza_stock_ledger`, `rahaza_material_movements` **selalu** dalam satuan dasar | FAIL |
| INV-UOM-3 | `uoms` valid: tepat 1 satuan dasar berfaktor 1, kode unik, tiap faktor > 0, maks 3 satuan (dasar + 2 tingkat kemasan), induk ada di daftar | FAIL |
| INV-UOM-4 | `unit` (lama) == `base_uom` (baru); cermin `pack_unit`/`pack_size` konsisten dengan `uoms` | FAIL |
| INV-UOM-5 | Mengedit daftar `uoms` **tidak boleh** mengubah angka stok yang sudah ada. Perubahan satuan dasar hanya lewat aksi "Ubah Satuan Dasar" ber-audit | FAIL |
| INV-UOM-6 | `factor` selalu relatif ke **satuan dasar**, bukan ke induknya | FAIL |

> **Kenapa INV-UOM-1 mengikat:** 5 modul hilir — `dewi_rnd_hpp`, `rahaza_hpp`,
> `rahaza_material_requirements`, `production_internal_adapter`, `rahaza_posting` —
> memakai rumus `amount = qty × unit_cost` dan mengasumsikan keduanya satuan dasar.
> Mengubah makna `unit_cost` merusak HPP RnD, HPP produksi, MRP, dan posting GL sekaligus.
>
> SSOT konversi: `backend/core/uom.py` ⇄ `frontend/src/lib/uom.js` (wajib sinkron).
> Rancangan: `docs/RANCANGAN_MULTI_UOM.md` · Audit: `docs/AUDIT_KONVERSI_SATUAN.md`
> Peta dampak: `docs/MAP_UOM_IMPACT.md` (132 file BE, 64 FE, 52 titik tulis stok).
> Self-test-proven: 5 kelas pelanggaran sintetis terbukti MERAH lalu HIJAU setelah revert.

## Q. Cross-entity referensial — `guardrails/verify_cross_entity.py`  (INV-CROSS-01)  ★RUNTIME ★ADVISORY
| ID | Invarian | Sifat |
|---|---|---|
| CROSS-ORPHAN | Child FK (journal_line→entry/COA, AR→customer, WO→order, issue→WO, maklon PO→client) tak yatim | HIGH (report-only; skip aman bila field-name beda) |

## R. Kualitas kerja / effort statik — `guardrails/verify_effort_quality.py`  (INV-QUALITY-01)  ★STATIC ★ADVISORY
| ID | Invarian | Sifat |
|---|---|---|
| QUAL-NOTIMPL | Tak ada `NotImplementedError` di router | HIGH |
| QUAL-SWALLOW | Tak ada `except…: pass` (telan error senyap) | MED |
| QUAL-SECRET/FEURL/MONGO | Tak ada rahasia/URL backend/mongo:// hardcoded | HIGH |
> Melengkapi `meta/effort_gate.py` (git-diff). Lihat `ANTI_UNDERDELIVERY_PROTOCOL.md`.

## S. Meta guardrail-registry — `guardrails/verify_guardrail_registry.py`  (INV-META-01)  ★STATIC
| ID | Invarian | Sifat |
|---|---|---|
| META-UNWIRED | Tiap guardrail `verify_*/check_*` WAJIB dirujuk `gate.sh` (cegah perlindungan mati diam-diam / "HIJAU-PALSU") | HIGH (report-only) |

## T. Health — `health_check.py`  (HEALTH-01)  ★RUNTIME ★BLOCKING
| ID | Invarian | Sifat |
|---|---|---|
| HEALTH-DOWN/AUTH/5XX | `/api/health` 2xx, login admin OK, endpoint inti tak 5xx | CRIT/HIGH (BLOK) |

## META. Efektivitas gate & kualitas AI
| ID | Invarian | Sifat |
|---|---|---|
| MUT-01 (`meta/mutation_test.py`) | Setiap korupsi invarian yang disuntik HARUS `KILLED` gate integrity (SURVIVED=blind spot) | FAIL |
| EFFORT-01 (`meta/effort_gate.py`) | Klaim "selesai" wajib punya bukti: receipt HIJAU+baru, tanpa TODO/mock/stub, mutation SURVIVED=0 | lensa BLOK |

---

## MAKLON-CMT-SSOT — Keputusan SSOT Operasional CMT (Maklon CMT Operasional Plan, Fase 0)
> Kontrak keras untuk pekerjaan operasional CMT baru (KEJAR, Dashboard Owner, Potongan Masuk, Rekap Aksesoris, Kapasitas).
> Tujuan: cegah duplikat/percabangan/split-brain. **Semua fitur baru WAJIB membaca rantai SSOT ini, bukan koleksi paralel.**

| ID | Invarian / Keputusan | Sifat |
|---|---|---|
| MCS-01 | Rantai SSOT Maklon = `production_pos`/`po_items` → `vendor_shipments`/`vendor_shipment_items`(+`vendor_material_inspections`) → `production_jobs`/`production_job_items`/`production_progress` → `cmt_receipts`/`cmt_receipt_lines` → `dewi_cmt_permak` → `buyer_shipments`/`buyer_shipment_items`. Komponen-kurang aksesoris = `dewi_cmt_component_requests`. | FAIL bila fitur maklon baru menulis truth di luar rantai ini |
| MCS-02 | Master CMT partner SSOT = `vendor_partners` (owner `vendor_portal.py`, nav `vendor-admin`). `dewi_cmt_partners`/`dewi_cmt_jobs`/`dewi_cmt_progress` = **LEGACY/ARSIP** (hanya `_archive/*` + `dewi_demo_seed`), jangan tulis dari kode baru. | WARN (deprecate) |
| MCS-03 | Progress/qty PO dihitung HANYA dari rantai SSOT (mis. `production_job_items.produced_qty`, `cmt_receipt_lines`, `dewi_cmt_permak`, `buyer_shipment_items`). `vendor_jobs`/`vendor_progress_reports` (portal CMT eksternal) **BUKAN sumber angka PO** (opsi B2-A) — hindari double-count. | FAIL bila KPI PO baca `vendor_jobs` |
| MCS-04 | Untuk PORTAL MAKLON, dispatch DA→CMT = `vendor_shipments`+`cmt_receipts`. `wh_cmt_dispatches` (wms_cmt_dispatches.py) = domain WMS/Produksi-internal, **tidak** dipakai KPI maklon (konsolidasi = Fase 5). | WARN |
| MCS-05 | Semua metrik operasional (kejar/dashboard/rekap/kapasitas) = **READ-ONLY agregasi** di atas SSOT + config (`dewi_system_config`: `maklon_cmt_buffer_days`, `maklon_cmt_late_grace_days`, `maklon_permak_return_grace_days`). **0 koleksi kebenaran baru.** | FAIL bila muncul koleksi truth baru |
| MCS-06 | Target CMT = `delivery_deadline − maklon_cmt_buffer_days` (computed, tidak disimpan). Deadline Mitra/Buyer = `production_pos.delivery_deadline`. Deadline internal = `production_pos.deadline`. | FAIL bila ada field target_cmt tersimpan ganda |
| MCS-07 | **Nomor seri (SN) SSOT tunggal = `po_items.serial_number`** (input saat BUAT ORDER, mewaris otomatis ke `production_job_items`/`vendor_shipment_items`/`buyer_shipment_items`). Cek-seri (`/api/dewi/cmt-intake/*`) = READ-ONLY deteksi dobel; **DILARANG** membuat field/koleksi seri baru. | FAIL bila ada field seri baru selain warisan `serial_number` |
| MCS-08 | Kapasitas CMT = field additif `vendor_partners.capacity_pcs`/`capacity_note` (owner `vendor_portal.py`). Rekap aksesoris & kapasitas (`/api/dewi/cmt-belanja/*`) = READ-ONLY (`po_accessories` + BOM×qty; beban via `services.cmt_kejar`). | FAIL bila kapasitas/rekap disimpan sebagai truth baru |
| MCS-09 | **Fase 5 = pemisahan PERMANEN ditegaskan.** `vendor_shipments`(maklon/pcs) & `wh_cmt_dispatches`(WMS/meter) tetap TERPISAH; `/api/dewi/cmt-recon/dispatch` hanya READ-ONLY monitor + deteksi overlap. Bridge `vendor_progress_reports → production_progress` (B2-B) **SENGAJA TIDAK dibuat** (opsi B2-A). | FAIL bila ada penggabungan/bridge yang double-count |

## Gap yang BELUM ter-invarian (TODO — lihat GAP_ANALYSIS §8)
- ~~Cross-entity double-allocation (referensial yatim)~~ → **kini tercakup** oleh INV-CROSS-01 (`verify_cross_entity.py`, advisory). Ekstensi double-allocation stok FG/operator/mesin masih backlog.
- Reservation-lock statik.
- Lintas-periode payroll (no double-count).
- ~~RBAC-guard statik~~ → **kini tercakup RUNTIME & BLOCKING** oleh INV-RBAC-01 (`verify_rbac_idor.py`, terpasang di `gate.sh`). **BUG-RBAC-1 SUDAH DITUTUP** — read-guard ditegakkan di kode via `require_portal`/`require_portal_dep` (lihat ENGINEERING_GUARDRAILS §12).
