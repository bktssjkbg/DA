"""
PT Rahaza — Phase F2 Accounting Core
Posting Profiles — mapping event_type → CoA account codes.

Collection: rahaza_posting_profiles
  id, event_type (unique), active (bool),
  mapping { <role>: <account_code> },  e.g. {'debit_ar': '1-1301', 'credit_revenue': '4-1100'}
  description, updated_at, updated_by

Seed defaults (garment manufacturing, PSAK):
  ar_invoice        : Dr AR (1-1301), Cr Revenue (4-1100), Cr Tax Output (2-1400)
  ar_payment        : Dr Cash (fallback 1-110), Cr AR (1-1301)
  ap_invoice        : Dr Expense (fallback 6-2200) or Inventory RM (1-1401), Cr AP (2-1100), Dr Tax Input (1-1501)
  ap_payment        : Dr AP (2-1100), Cr Cash (fallback 1-110)
  expense           : Dr Expense (fallback 6-2200), Cr Cash (fallback 1-110)
  payroll_finalize  : Dr Salary Expense (6-2100), Cr Hutang Gaji (2-1200)
  inventory_receive : Dr Inventory RM (1-1401), Cr AP (2-1100) [clearing]
  inventory_issue   : Dr WIP (1-330), Cr Inventory RM (1-1401)
  inventory_adjust  : Dr/Cr Inventory (1-1401) vs Expense (6-2400)
  cogs_shipment     : Dr COGS Material (5-1000), Dr COGS Labor (5-2000), Dr COGS Overhead (5-3000), Cr FG Inventory (1-1404)
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/rahaza/posting-profiles", tags=["rahaza-posting-profiles"])


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


async def _require_fin(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin", "owner", "accounting", "finance", "manager"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "finance.manage" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission finance.")


# ───────────────────────── SEED TEMPLATE ──────────────────────────────────────
# Each event_type maps role -> CoA code.
# `role` is a free-form key used by posting helpers when building JE lines.
DEFAULT_PROFILES = [
    {
        "event_type": "ar_invoice",
        "description": "AR Invoice sent → Dr AR / Cr Revenue (+Tax Output) (+Sales Discount)",
        "mapping": {
            "debit_ar": "1-1301",
            "credit_revenue": "4-1100",
            "credit_tax_output": "2-1400",
            "debit_sales_discount": "6-1100",  # Phase 9C: Sales Discount
        },
    },
    {
        "event_type": "ar_payment",
        "description": "Pembayaran AR → Dr Cash / Cr AR",
        "mapping": {
            "debit_cash_default": "1-110",
            "credit_ar": "1-1301",
        },
    },
    {
        "event_type": "ap_invoice",
        "description": "AP Invoice sent → Dr Expense/Inventory / Cr AP (+Tax Input)",
        "mapping": {
            "debit_expense_default": "6-2200",
            "debit_inventory_rm": "1-1401",
            "debit_tax_input": "1-1501",
            "credit_ap": "2-1100",
        },
    },
    {
        "event_type": "ap_payment",
        "description": "Pembayaran AP → Dr AP / Cr Cash",
        "mapping": {
            "debit_ap": "2-1100",
            "credit_cash_default": "1-110",
        },
    },
    {
        "event_type": "expense",
        "description": "Expense operasional → Dr Expense / Cr Cash",
        "mapping": {
            "debit_expense_default": "6-2200",
            "credit_cash_default": "1-110",
        },
    },
    {
        "event_type": "payroll_finalize",
        "description": "Payroll finalize → Dr Gaji Expense / Cr Hutang Gaji",
        "mapping": {
            "debit_salary_expense": "6-2100",
            "credit_salary_payable": "2-1200",
            "credit_tax_pph21": "2-1301",
            "credit_bpjs_payable": "2-1500",
        },
    },
    {
        "event_type": "payroll_payment",
        "description": "Pembayaran gaji → Dr Hutang Gaji / Cr Bank",
        "mapping": {
            "debit_salary_payable":  "2-1200",
            "credit_bank_default":   "1-1201",
        },
    },
    {
        "event_type": "inventory_receive",
        "description": "Material receive → Dr Inventory RM / Cr AP (clearing)",
        "mapping": {
            "debit_inventory_rm": "1-1401",
            "credit_ap_clearing": "2-1100",
        },
    },
    {
        "event_type": "inventory_issue",
        "description": "Material issue ke WO → Dr WIP / Cr Inventory RM",
        "mapping": {
            "debit_wip": "1-330",
            "credit_inventory_rm": "1-1401",
        },
    },
    {
        "event_type": "inventory_adjust",
        "description": "Material adjust → Dr/Cr Inventory vs Adjustment Expense",
        "mapping": {
            "inventory_rm": "1-1401",
            "adjustment_expense": "6-2400",
        },
    },
    {
        "event_type": "cogs_shipment",
        "description": "Shipment dispatched → Dr COGS / Cr FG Inventory (berdasarkan HPP snapshot)",
        "mapping": {
            "debit_cogs_material": "5-1000",
            "debit_cogs_labor": "5-2000",
            # FASE 4 fix laten: 5-3000 adalah akun HEADER (non-postable) di CoA aktif →
            # ganti 5-250 "Biaya Overhead Pabrik (BOP)" (postable, identik DA_POSTING_PROFILES).
            "debit_cogs_overhead": "5-250",
            "credit_fg_inventory": "1-1404",
        },
    },
    # ── Maklon Finance Profiles (Phase Production-Maklon Overhaul) ──────────────
    {
        "event_type": "maklon_ar_invoice",
        "description": "Maklon AR Invoice → Dr AR Piutang / Cr Pendapatan Jasa Maklon",
        "mapping": {
            "debit_ar": "1-1301",
            "credit_revenue_maklon": "4-1100",  # Pendapatan Jasa Maklon (sama dgn revenue biasa, bisa diganti ke akun khusus)
            "credit_tax_output": "2-1400",
        },
    },
    {
        "event_type": "cmt_ap_invoice",
        "description": "CMT Vendor AP Invoice → Dr Biaya Vendor CMT / Cr AP Vendor",
        "mapping": {
            # FASE IA-C: DULU '6-2200' yang di CoA aktif = "Listrik & Air Kantor" (salah akun).
            # Sekarang dipisah per domain — lihat dewi_maklon_finance._cmt_expense_account().
            "debit_cmt_expense_internal": "5-231",  # Biaya Vendor CMT – Jahit (COGS produksi DA)
            "debit_cmt_expense_maklon": "7-120",    # Biaya Vendor CMT – Maklon (biaya proyek klien)
            "credit_ap": "2-1100",
            "debit_penalty_income": "4-920",  # Pendapatan penalti (jika ada)
        },
    },
    {
        "event_type": "maklon_advance_payment",
        "description": "DP Maklon dari klien → Dr Bank / Cr Uang Muka Diterima – Maklon",
        "mapping": {
            "debit_cash_default": "1-131",   # Bank BCA – DA Official (postable)
            "credit_advance_customer": "2-140",  # Uang Muka Diterima – Maklon (Termin) (postable)
        },
    },
    # ── Phase 6A — WIP → Finished Goods (WO Completion) ─────────────────────
    {
        "event_type": "wip_to_fg_on_wo_complete",
        "description": "WO selesai: pindah nilai WIP ke Barang Jadi → Dr FG / Cr WIP",
        "mapping": {
            "debit_fg_inventory": "1-1404",   # Persediaan Barang Jadi
            "credit_wip":         "1-330",   # WIP
        },
    },
    # ── Phase 6B — Kas Kecil / Petty Cash ────────────────────────────────────
    {
        "event_type": "petty_cash_expense",
        "description": "Pengeluaran kas kecil → Dr Biaya / Cr Kas Kecil",
        "mapping": {
            "debit_expense_default": "6-2400",  # ATK & Supplies (default, overridden by GL Mapping category)
            "credit_petty_cash":     "1-110",  # Kas Kecil
        },
    },
    {
        "event_type": "petty_cash_replenish",
        "description": "Pengisian ulang kas kecil dari bank → Dr Kas Kecil / Cr Bank",
        "mapping": {
            "debit_petty_cash":   "1-110",  # Kas Kecil
            "credit_bank_default": "1-1201",  # Bank BCA (default)
        },
    },
    # ── Phase 6C — Bank Transfer Antar Rekening ───────────────────────────────
    {
        "event_type": "bank_transfer",
        "description": "Transfer antar rekening bank → Dr Bank Tujuan / Cr Bank Sumber",
        "mapping": {
            "debit_bank_target":  "1-1202",  # Bank Mandiri (default tujuan)
            "credit_bank_source": "1-1201",  # Bank BCA (default sumber)
        },
    },
    # ── Phase 7B — Credit Note (Returns Reversal) ─────────────────────────────
    {
        "event_type": "credit_note",
        "description": "Credit note untuk retur → Dr Revenue / Cr AR (reversing entry)",
        "mapping": {
            "debit_revenue":  "4-1100",  # Revenue (di-debit untuk reversal)
            "credit_ar":      "1-1301",  # AR (di-kredit untuk mengurangi piutang)
        },
    },
    # ── Phase 7C — Production Variance Auto-Posting ───────────────────────────
    {
        "event_type": "variance_overproduction",
        "description": "Overproduction variance → Dr FG Inventory / Cr Variance Income",
        "mapping": {
            "debit_inventory_fg":     "1-1404",  # Persediaan Barang Jadi
            "credit_variance_income": "4-920",  # Pendapatan Lain-lain (Variance Income)
        },
    },
    {
        "event_type": "variance_underproduction",
        "description": "Underproduction variance → Dr Variance Loss / Cr WIP",
        "mapping": {
            "debit_variance_loss": "6-4100",  # Biaya Lain-lain (Variance Loss)
            "credit_wip":          "1-330",  # WIP
        },
    },
    # ── Phase 8A — Asset Capitalization ───────────────────────────────────────
    {
        "event_type": "asset_acquisition",
        "description": "Asset acquisition from GRN → Dr Fixed Asset / Cr AP Clearing",
        "mapping": {
            "debit_fixed_asset":  "1-2500",  # Inventaris Kantor (Fixed Asset default)
            "credit_ap_clearing": "2-1100",  # Hutang Usaha (AP Clearing)
        },
    },
    # ── Phase 8B — Monthly Depreciation ───────────────────────────────────────
    {
        "event_type": "depreciation",
        "description": "Monthly depreciation → Dr Depreciation Expense / Cr Accumulated Depreciation",
        "mapping": {
            "debit_depr_expense":  "6-2700",  # Penyusutan Bangunan & Inventaris
            "credit_accum_depr":   "1-2501",  # Akum. Penyusutan Inventaris
        },
    },
    # ── Phase 8C — Accruals & Provisions ──────────────────────────────────────
    {
        "event_type": "accrual",
        "description": "Period-end accrual → Dr Expense / Cr Accrued Expenses",
        "mapping": {
            "debit_expense":   "6-2400",  # Generic Expense (ATK & Supplies default)
            "credit_accrued":  "2-1600",  # Accrued Expenses Payable
        },
    },
    {
        "event_type": "accrual_reversal",
        "description": "Accrual reversal (next period) → Dr Accrued Expenses / Cr Expense",
        "mapping": {
            "debit_accrued":   "2-1600",  # Accrued Expenses Payable
            "credit_expense":  "6-2400",  # Generic Expense
        },
    },
    # ── Phase 9A — Bad Debt Write-off ──────────────────────────────────────────
    {
        "event_type": "bad_debt_writeoff",
        "description": "Bad debt write-off → Dr Bad Debt Expense / Cr AR",
        "mapping": {
            "debit_bad_debt_expense": "6-4400",  # Beban Kerugian Piutang (Bad Debt Expense)
            "credit_ar":              "1-1301",  # Piutang Usaha — Dagang
        },
    },
    # ── Phase 9B — Bank Reconciliation Adjustments ─────────────────────────────
    {
        "event_type": "bank_recon_charge",
        "description": "Bank charges adjustment → Dr Bank Charges / Cr Bank",
        "mapping": {
            "debit_bank_charges": "6-4100",  # Biaya Bank & Admin Bank (updated)
            "credit_bank":        "1-1201",  # Bank BCA
        },
    },
    {
        "event_type": "bank_recon_interest",
        "description": "Bank interest income → Dr Bank / Cr Interest Income",
        "mapping": {
            "debit_bank":             "1-1201",  # Bank BCA
            "credit_interest_income": "4-910",  # Pendapatan Bunga Bank (new account)
        },
    },
    {
        "event_type": "bank_recon_service_fee",
        "description": "Bank service fee → Dr Service Fee / Cr Bank",
        "mapping": {
            "debit_service_fee": "6-4101",  # Biaya Layanan Bank (new account)
            "credit_bank":       "1-1201",  # Bank BCA
        },
    },
    # ── Phase 10A — Asset Disposal ────────────────────────────────────────────
    {
        "event_type": "asset_disposal",
        "description": "Asset disposal (3-way: Dr Accum Depr + Dr Cash + Dr/Cr Gain/Loss, Cr Asset)",
        "mapping": {
            "credit_fixed_asset":       "1-1501",  # Fixed Asset (original cost)
            "debit_accum_depr":         "1-1502",  # Accumulated Depreciation
            "debit_cash":               "1-110",  # Cash (proceeds)
            "debit_loss_on_disposal":   "6-4200",  # Loss on Disposal
            "credit_gain_on_disposal":  "4-2200",  # Gain on Disposal
        },
    },
    # ── Phase 11A & 11B — Employee Loan Management ────────────────────────────
    {
        "event_type": "employee_loan_disbursement",
        "description": "Employee loan disbursement → Dr Employee Loan Receivable / Cr Cash",
        "mapping": {
            "debit_employee_loan_receivable": "1-1320",  # Piutang Pinjaman Karyawan
            "credit_cash":                    "1-110",  # Cash
        },
    },
    {
        "event_type": "employee_loan_repayment_payroll",
        "description": "Employee loan repayment via payroll → Dr Salary Payable / Cr Employee Loan Receivable",
        "mapping": {
            "debit_salary_payable":             "2-1200",  # Salary Payable
            "credit_employee_loan_receivable":  "1-1320",  # Piutang Pinjaman Karyawan
        },
    },
    # ── Phase 11C — Scrap/Waste Material ───────────────────────────────────────
    {
        "event_type": "inventory_scrap",
        "description": "Material scrap/waste → Dr Scrap Expense / Cr Inventory RM",
        "mapping": {
            "debit_scrap_expense":   "6-4300",  # Biaya Scrap & Material Rusak
            "credit_inventory_rm":   "1-1401",  # Inventory Raw Material
        },
    },
]


# ───────────────────────── ENDPOINTS ──────────────────────────────────────────
@router.get("")
async def list_profiles(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_posting_profiles.find({}, {"_id": 0}).sort("event_type", 1).to_list(500)
    return serialize_doc(rows)


@router.get("/{event_type}")
async def get_profile(event_type: str, request: Request):
    await require_auth(request)
    db = get_db()
    doc = await db.rahaza_posting_profiles.find_one({"event_type": event_type}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Posting profile '{event_type}' tidak ditemukan.")
    return serialize_doc(doc)


@router.put("/{event_type}")
async def update_profile(event_type: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    doc = await db.rahaza_posting_profiles.find_one({"event_type": event_type})
    if not doc:
        raise HTTPException(404, f"Posting profile '{event_type}' tidak ditemukan. Jalankan seed dulu.")
    upd = {"updated_at": _now(), "updated_by": user["id"], "updated_by_name": user.get("name", "")}
    if "mapping" in body and isinstance(body["mapping"], dict):
        # validate each account_code exists + leaf + active (warning but not blocker if missing)
        mapping = body["mapping"]
        clean = {}
        # Batch fetch all referenced CoA accounts in one query
        codes = [str(c).strip() for c in mapping.values() if c]
        coa_map = {}
        if codes:
            async for d in db.rahaza_coa_accounts.find({"code": {"$in": codes}}, {"_id": 0}):
                coa_map[d["code"]] = d
        for role, code in mapping.items():
            if not code:
                continue
            code = str(code).strip()
            acc = coa_map.get(code)
            if not acc:
                raise HTTPException(400, f"Role '{role}': akun '{code}' tidak ditemukan di CoA.")
            if acc.get("is_group"):
                raise HTTPException(400, f"Role '{role}': akun '{code}' adalah header (non-postable). Pilih akun leaf.")
            if not acc.get("active"):
                raise HTTPException(400, f"Role '{role}': akun '{code}' tidak aktif.")
            clean[role] = code
        upd["mapping"] = clean
    if "description" in body:
        upd["description"] = (body.get("description") or "").strip()
    if "active" in body:
        upd["active"] = bool(body["active"])
    await db.rahaza_posting_profiles.update_one({"event_type": event_type}, {"$set": upd})
    out = await db.rahaza_posting_profiles.find_one({"event_type": event_type}, {"_id": 0})
    await log_activity(user["id"], user.get("name", ""), "update_posting_profile", "posting_profile", event_type)
    return serialize_doc(out)


async def seed_posting_profiles(db, user=None):
    """Seed default posting profiles idempotent (skip if exists).
    Reusable by both the startup auto-seed (server.py) and the /seed route."""
    uid = (user or {}).get("id", "system")
    uname = (user or {}).get("name", "system")
    inserted = 0
    skipped = 0
    # Batch fetch existing posting profiles
    event_types = [p["event_type"] for p in DEFAULT_PROFILES]
    existing_profiles_set = set()
    if event_types:
        async for d in db.rahaza_posting_profiles.find(
            {"event_type": {"$in": event_types}}, {"_id": 0, "event_type": 1}
        ):
            existing_profiles_set.add(d["event_type"])
    for p in DEFAULT_PROFILES:
        if p["event_type"] in existing_profiles_set:
            skipped += 1
            continue
        doc = {
            "id": _uid(),
            "event_type": p["event_type"],
            "description": p["description"],
            "mapping": p["mapping"],
            "active": True,
            "created_at": _now(),
            "updated_at": _now(),
            "created_by": uid,
            "created_by_name": uname,
        }
        await db.rahaza_posting_profiles.insert_one(doc)
        inserted += 1
    return {"inserted": inserted, "skipped": skipped, "total_template": len(DEFAULT_PROFILES)}


@router.post("/seed")
async def seed_defaults(request: Request):
    """Seed default posting profiles idempotent (skip if exists)."""
    user = await _require_fin(request)
    db = get_db()
    result = await seed_posting_profiles(db, user)
    await log_activity(user["id"], user.get("name", ""), "seed_posting_profiles", "posting_profile",
                       f"inserted={result['inserted']} skipped={result['skipped']}")
    return {"ok": True, **result}


async def ensure_seed(db):
    """Internal helper: auto-seed if collection is empty. Called by posting helpers."""
    cnt = await db.rahaza_posting_profiles.count_documents({})
    if cnt > 0:
        return
    for p in DEFAULT_PROFILES:
        doc = {
            "id": _uid(),
            "event_type": p["event_type"],
            "description": p["description"],
            "mapping": p["mapping"],
            "active": True,
            "created_at": _now(),
            "updated_at": _now(),
            "created_by": "system",
            "created_by_name": "system",
        }
        await db.rahaza_posting_profiles.insert_one(doc)


async def get_mapping(db, event_type: str) -> dict:
    await ensure_seed(db)
    doc = await db.rahaza_posting_profiles.find_one({"event_type": event_type, "active": True}, {"_id": 0})
    if not doc:
        return {}
    return doc.get("mapping") or {}


# ─── DA Posting Profiles (CV. Dewi Aditya — remapped to 3-digit CoA) ──────────
DA_POSTING_PROFILES = [
    {"event_type":"ar_invoice","description":"AR Invoice Maklon → Dr Piutang / Cr Pendapatan / Cr PPN",
     "mapping":{"debit_ar":"1-210","credit_revenue":"4-210","credit_tax_output":"2-130","debit_discount":"4-140"}},
    {"event_type":"ar_invoice_os","description":"AR Invoice Online Shop → Dr Piutang Platform / Cr Pendapatan Channel",
     "mapping":{"debit_ar":"1-220","credit_revenue":"4-121","debit_platform_fee":"4-141"}},
    {"event_type":"ar_payment","description":"AR Payment → Dr Bank / Cr Piutang",
     "mapping":{"debit_cash_default":"1-131","credit_ar":"1-210"}},
    {"event_type":"credit_note","description":"Credit Note → Dr Retur Penjualan / Cr Piutang",
     "mapping":{"debit_revenue":"4-230","credit_ar":"1-210"}},
    {"event_type":"ap_invoice","description":"AP Invoice → Dr Persediaan / Dr PPN / Cr Hutang Usaha",
     "mapping":{"debit_expense_default":"9-290","debit_inventory_rm":"1-310","debit_tax_input":"1-440","credit_ap":"2-110"}},
    {"event_type":"ap_payment","description":"AP Payment → Dr Hutang / Cr Bank",
     "mapping":{"debit_ap":"2-110","credit_cash_default":"1-131"}},
    {"event_type":"expense","description":"Expense → Dr Beban / Cr Kas/Bank",
     "mapping":{"debit_expense_default":"9-290","credit_cash_default":"1-131"}},
    {"event_type":"payroll_finalize","description":"Payroll Finalize → Dr Beban Gaji / Cr Hutang Gaji / Cr PPh21 / Cr BPJS",
     "mapping":{"debit_salary_expense":"9-120","credit_salary_payable":"2-120","credit_tax_pph21":"2-131","credit_bpjs_payable":"2-122"}},
    {"event_type":"payroll_payment","description":"Payroll Payment → Dr Hutang Gaji / Cr Bank",
     "mapping":{"debit_salary_payable":"2-120","credit_bank_default":"1-131"}},
    {"event_type":"bpjs_payment","description":"BPJS Kesehatan → Dr Hutang BPJS / Cr Bank",
     "mapping":{"debit_bpjs_payable":"2-122","credit_bank_default":"1-131"}},
    {"event_type":"bpjs_ketenagakerjaan_payment","description":"BPJS Ketenagakerjaan → Dr Hutang BPJS TK / Cr Bank",
     "mapping":{"debit_bpjs_tk_payable":"2-123","credit_bank_default":"1-131"}},
    {"event_type":"pph21_payment","description":"PPh21 → Dr Hutang PPh21 / Cr Bank",
     "mapping":{"debit_pph21_payable":"2-131","credit_bank_default":"1-131"}},
    {"event_type":"inventory_receive","description":"GRN → Dr Persediaan BB / Cr Hutang Usaha",
     "mapping":{"debit_inventory_rm":"1-310","credit_ap_clearing":"2-110"}},
    {"event_type":"inventory_issue","description":"Material Issue → Dr WIP / Cr Persediaan BB",
     "mapping":{"debit_wip":"1-330","credit_inventory_rm":"1-310"}},
    {"event_type":"inventory_adjust","description":"Inventory Adjust → Dr/Cr Persediaan / Beban",
     "mapping":{"debit_inventory_rm":"1-310","credit_adjustment_loss":"9-290"}},
    {"event_type":"inventory_scrap","description":"Scrap Material → Dr Beban Scrap / Cr Persediaan",
     "mapping":{"debit_scrap_expense":"9-290","credit_inventory_rm":"1-310"}},
    {"event_type":"cogs_shipment","description":"COGS Shipment → Dr HPP (Mat/TK/OH) / Cr Barang Jadi",
     "mapping":{"debit_cogs_material":"5-210","debit_cogs_labor":"5-230","debit_cogs_overhead":"5-250","credit_fg_inventory":"1-340"}},
    {"event_type":"wip_to_fg_on_wo_complete","description":"WO Complete → Dr Barang Jadi / Cr WIP",
     "mapping":{"debit_fg_inventory":"1-340","credit_wip":"1-330"}},
    {"event_type":"depreciation","description":"Depresiasi → Dr Beban Penyusutan / Cr Akum Depresiasi",
     "mapping":{"debit_depr_expense":"8-310","credit_accum_depr":"1-521"}},
    {"event_type":"accrual","description":"Akrual → Dr Beban / Cr Hutang Akrual",
     "mapping":{"debit_expense":"9-290","credit_accrued":"2-160"}},
    {"event_type":"accrual_reversal","description":"Reversal Akrual → Dr Hutang Akrual / Cr Beban",
     "mapping":{"debit_accrued":"2-160","credit_expense":"9-290"}},
    {"event_type":"bad_debt_writeoff","description":"Hapus Buku Piutang → Dr Cadangan Piutang / Cr Piutang",
     "mapping":{"debit_allowance":"1-211","credit_ar":"1-210"}},
    {"event_type":"bank_transfer","description":"Transfer Bank → Dr Bank Tujuan / Cr Bank Sumber",
     "mapping":{"debit_bank_target":"1-131","credit_bank_source":"1-131"}},
    {"event_type":"bank_recon_charge","description":"Bank Recon Biaya Adm → Dr Biaya Adm Bank / Cr Bank",
     "mapping":{"debit_bank_charges":"9-310","credit_bank":"1-131"}},
    {"event_type":"bank_recon_interest","description":"Bank Recon Bunga → Dr Bank / Cr Pendapatan Bunga",
     "mapping":{"debit_bank":"1-131","credit_interest_income":"4-910"}},
    {"event_type":"bank_recon_service_fee","description":"Bank Recon Service Fee → Dr Biaya / Cr Bank",
     "mapping":{"debit_service_fee":"9-310","credit_bank":"1-131"}},
    {"event_type":"petty_cash_expense","description":"Kas Kecil Keluar → Dr Beban / Cr Kas Kecil",
     "mapping":{"debit_expense_default":"9-290","credit_petty_cash":"1-110"}},
    {"event_type":"petty_cash_replenish","description":"Isi Ulang Kas Kecil → Dr Kas Kecil / Cr Bank",
     "mapping":{"debit_petty_cash":"1-110","credit_bank_default":"1-131"}},
    {"event_type":"asset_acquisition","description":"Aset Baru → Dr Aset Tetap / Cr Hutang (default: Peralatan Produksi)",
     "mapping":{"debit_fixed_asset":"1-540","credit_ap_clearing":"2-150"}},
    {"event_type":"asset_disposal","description":"Pelepasan Aset → Bersihkan nilai buku",
     "mapping":{"credit_fixed_asset":"1-540","debit_accum_depr":"1-541","debit_cash":"1-131",
                "debit_loss_on_disposal":"9-420","credit_gain_on_disposal":"4-920"}},
    {"event_type":"employee_loan_disbursement","description":"Kasbon Cair → Dr Kasbon Karyawan / Cr Bank",
     "mapping":{"debit_loan_receivable":"1-120","credit_cash":"1-131"}},
    {"event_type":"employee_loan_repayment_payroll","description":"Potongan Kasbon dari Gaji → Dr Hutang Gaji / Cr Kasbon",
     "mapping":{"debit_salary_payable":"2-120","credit_loan_receivable":"1-120"}},
    {"event_type":"employee_loan_repayment_manual","description":"Pelunasan Kasbon Manual → Dr Bank / Cr Kasbon",
     "mapping":{"debit_bank":"1-131","credit_loan_receivable":"1-120"}},
    {"event_type":"maklon_ar_invoice","description":"Maklon AR Invoice → Dr Piutang / Cr Pendapatan Maklon",
     "mapping":{"debit_ar":"1-210","credit_revenue_maklon":"4-210","credit_tax_output":"2-130"}},
    {"event_type":"maklon_advance_payment","description":"DP Maklon Masuk → Dr Bank / Cr Uang Muka Diterima",
     "mapping":{"debit_cash_default":"1-131","credit_advance_customer":"2-140"}},
    {"event_type":"cmt_ap_invoice","description":"CMT AP Invoice → Dr Biaya Vendor CMT (internal COGS / maklon) / Cr Hutang Vendor CMT",
     "mapping":{"debit_cmt_expense_internal":"5-231","debit_cmt_expense_maklon":"7-120",
                "credit_ap":"2-112","debit_tax_input":"1-440"}},
    {"event_type":"variance_overproduction","description":"Variance Over → Dr Barang Jadi / Cr Pendapatan Lain",
     "mapping":{"debit_inventory_fg":"1-340","credit_variance_income":"4-920"}},
    {"event_type":"variance_underproduction","description":"Variance Under → Dr Beban Lain / Cr WIP",
     "mapping":{"debit_variance_loss":"9-420","credit_wip":"1-330"}},
]


@router.post("/seed-da")
async def seed_da_profiles(request: Request):
    """Remap semua posting profile ke CoA CV. Dewi Aditya (3-digit). Update existing + insert new."""
    user = await _require_fin(request)
    db = get_db()
    updated = 0
    inserted = 0
    for p in DA_POSTING_PROFILES:
        existing = await db.rahaza_posting_profiles.find_one({"event_type": p["event_type"]})
        if existing:
            await db.rahaza_posting_profiles.update_one(
                {"event_type": p["event_type"]},
                {"$set": {"mapping": p["mapping"], "description": p["description"],
                          "updated_at": _now(), "updated_by": user["id"],
                          "updated_by_name": user.get("name", "")}}
            )
            updated += 1
        else:
            doc = {"id": _uid(), "event_type": p["event_type"], "description": p["description"],
                   "mapping": p["mapping"], "active": True, "created_at": _now(), "updated_at": _now(),
                   "created_by": user["id"], "created_by_name": user.get("name", "")}
            await db.rahaza_posting_profiles.insert_one(doc)
            inserted += 1
    await log_activity(user["id"], user.get("name",""), "seed_da_posting_profiles", "posting_profile",
                       f"updated={updated} inserted={inserted}")
    return {"ok": True, "updated": updated, "inserted": inserted, "total": len(DA_POSTING_PROFILES)}

