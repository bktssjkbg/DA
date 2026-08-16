"""
Bank Reconciliation Module
Prefix: /api/finance/bank-recon

Koleksi:
  bank_recon_sessions   — Sesi rekonsiliasi per periode & akun bank
  bank_recon_txns       — Transaksi bank statement per sesi

Flow:
  1. Buat sesi (pilih periode & akun bank)
  2. Import transaksi bank (manual entry atau bulk JSON)
  3. Lihat GL entries untuk periode yang sama
  4. Match/unmatch transaksi bank ↔ GL entry
  5. Approve rekonsiliasi jika unmatched = 0
"""
from fastapi import APIRouter, Request, HTTPException, Query, UploadFile, File
from database import get_db
from auth import require_auth, serialize_doc
from datetime import datetime, timezone, date, timedelta
from typing import Optional
import re
import uuid
import logging
import csv
import io

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/finance/bank-recon", tags=["bank-reconciliation"])

PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc).isoformat()
def _validate_period(period: str):
    if not period or not PERIOD_RE.match(period):
        raise HTTPException(400, "period harus format YYYY-MM (mis. 2026-05)")


# ═══════════════════════════════════════════════════════════════════
# SESSIONS
# ═══════════════════════════════════════════════════════════════════

@router.get("/sessions")
async def list_sessions(
    request: Request,
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
):
    await require_auth(request)
    db = get_db()
    q = {}
    if status:
        q["status"] = status
    total = await db.bank_recon_sessions.count_documents(q)
    rows = await db.bank_recon_sessions.find(q, {"_id": 0}).sort("period", -1).skip(skip).limit(limit).to_list(500)
    return {
        "total": total, "skip": skip, "limit": limit,
        "has_more": (skip + limit) < total,
        "items": serialize_doc(rows),
    }


@router.post("/sessions")
async def create_session(request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    period = body.get("period", "")  # YYYY-MM
    bank_name = (body.get("bank_name") or "").strip()
    account_no = (body.get("account_no") or "").strip()
    account_name = (body.get("account_name") or "").strip()
    opening_balance = float(body.get("opening_balance", 0))
    closing_balance = float(body.get("closing_balance", 0))

    if not period or not PERIOD_RE.match(period):
        raise HTTPException(400, "period harus format YYYY-MM (mis. 2026-05)")
    if not bank_name:
        raise HTTPException(400, "bank_name wajib diisi")

    # Check if session for same period+account already exists
    existing = await db.bank_recon_sessions.find_one({"period": period, "account_no": account_no})
    if existing:
        raise HTTPException(409, f"Sesi rekonsiliasi untuk periode {period} dan akun {account_no} sudah ada.")

    doc = {
        "id": _uid(),
        "period": period,
        "bank_name": bank_name,
        "account_no": account_no,
        "account_name": account_name,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "status": "draft",
        "total_bank_txns": 0,
        "matched_count": 0,
        "unmatched_count": 0,
        "difference": 0.0,
        "notes": body.get("notes", ""),
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
        "created_at": _now(),
        "updated_at": _now(),
        "approved_at": None,
        "approved_by": None,
    }
    await db.bank_recon_sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")

    # Get GL entries for this period (from journal entries)
    period = s.get("period", "")
    if period:
        from_dt = f"{period}-01"
        year, mon = map(int, period.split("-"))
        last_day = (date(year, mon, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        to_dt = last_day.isoformat()
        gl_entries = await db.rahaza_journal_entries.find(
            {
                "date": {"$gte": from_dt, "$lte": to_dt},
                "account_type": {"$in": ["kas", "bank", "cash", "bank_account"]},
            },
            {"_id": 0}
        ).sort("date", 1).to_list(200)
        s["gl_entries"] = serialize_doc(gl_entries)
    else:
        s["gl_entries"] = []

    return serialize_doc(s)


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if s.get("status") == "approved":
        raise HTTPException(400, "Sesi sudah disetujui, tidak bisa diubah.")
    body = await request.json()
    allowed = ["bank_name", "account_no", "account_name", "opening_balance", "closing_balance", "notes"]
    upd = {k: v for k, v in body.items() if k in allowed}
    upd["updated_at"] = _now()
    await db.bank_recon_sessions.update_one({"id": session_id}, {"$set": upd})
    out = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    return serialize_doc(out)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if s.get("status") == "approved":
        raise HTTPException(400, "Sesi approved tidak dapat dihapus.")
    await db.bank_recon_sessions.delete_one({"id": session_id})
    await db.bank_recon_txns.delete_many({"session_id": session_id})
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# BANK TRANSACTIONS (per session)
# ═══════════════════════════════════════════════════════════════════

@router.get("/sessions/{session_id}/transactions")
async def list_transactions(
    session_id: str,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    matched: Optional[bool] = None,
):
    await require_auth(request)
    db = get_db()
    q = {"session_id": session_id}
    if matched is not None:
        q["is_matched"] = matched
    total = await db.bank_recon_txns.count_documents(q)
    rows = await db.bank_recon_txns.find(q, {"_id": 0}).sort("txn_date", 1).skip(skip).limit(limit).to_list(500)
    return {"total": total, "skip": skip, "limit": limit, "has_more": (skip + limit) < total, "items": rows}


@router.post("/sessions/{session_id}/transactions")
async def add_transaction(session_id: str, request: Request):
    """Add a single bank transaction to the session."""
    await require_auth(request)
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if s.get("status") == "approved":
        raise HTTPException(400, "Sesi sudah disetujui.")
    body = await request.json()
    txn_date = body.get("txn_date")
    amount = float(body.get("amount", 0))
    txn_type = body.get("type", "debit")  # debit / credit
    if not txn_date:
        raise HTTPException(400, "txn_date wajib diisi")
    doc = {
        "id": _uid(),
        "session_id": session_id,
        "txn_date": txn_date,
        "description": (body.get("description") or "").strip(),
        "reference": (body.get("reference") or "").strip(),
        "amount": abs(amount),
        "type": txn_type,
        "is_matched": False,
        "match_id": None,
        "match_ref": None,
        "created_at": _now(),
    }
    await db.bank_recon_txns.insert_one(doc)
    doc.pop("_id", None)
    await _recalculate_session(db, session_id)
    return doc


@router.post("/sessions/{session_id}/import-bulk")
async def import_bulk_transactions(session_id: str, request: Request):
    """
    Import multiple bank transactions at once.
    Body: { "transactions": [ {txn_date, description, reference, amount, type}, ... ] }
    """
    await require_auth(request)
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if s.get("status") == "approved":
        raise HTTPException(400, "Sesi sudah disetujui.")
    body = await request.json()
    txns = body.get("transactions", [])
    if not txns or not isinstance(txns, list):
        raise HTTPException(400, "transactions harus berupa list.")
    docs = []
    for t in txns[:500]:  # Max 500 per import
        docs.append({
            "id": _uid(),
            "session_id": session_id,
            "txn_date": t.get("txn_date", ""),
            "description": (t.get("description") or "").strip(),
            "reference": (t.get("reference") or "").strip(),
            "amount": abs(float(t.get("amount", 0))),
            "type": t.get("type", "debit"),
            "is_matched": False,
            "match_id": None,
            "match_ref": None,
            "created_at": _now(),
        })
    if docs:
        await db.bank_recon_txns.insert_many(docs)
        for d in docs:
            d.pop("_id", None)
    await _recalculate_session(db, session_id)
    return {"imported": len(docs), "message": f"{len(docs)} transaksi berhasil diimpor."}


@router.delete("/sessions/{session_id}/transactions/{txn_id}")
async def delete_transaction(session_id: str, txn_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    res = await db.bank_recon_txns.delete_one({"id": txn_id, "session_id": session_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Transaksi tidak ditemukan.")
    await _recalculate_session(db, session_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# MATCHING
# ═══════════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/match")
async def match_transaction(session_id: str, request: Request):
    """
    Match a bank transaction to a GL journal entry.
    Body: { "txn_id": "...", "gl_entry_id": "...", "gl_ref": "..." }
    """
    await require_auth(request)
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if s.get("status") == "approved":
        raise HTTPException(400, "Sesi sudah disetujui.")
    body = await request.json()
    txn_id = body.get("txn_id")
    gl_entry_id = body.get("gl_entry_id", "")
    gl_ref = body.get("gl_ref", "")

    txn = await db.bank_recon_txns.find_one({"id": txn_id, "session_id": session_id})
    if not txn:
        raise HTTPException(404, "Transaksi tidak ditemukan.")

    await db.bank_recon_txns.update_one(
        {"id": txn_id},
        {"$set": {"is_matched": True, "match_id": gl_entry_id, "match_ref": gl_ref, "matched_at": _now()}}
    )
    await _recalculate_session(db, session_id)
    return {"ok": True, "txn_id": txn_id, "matched_to": gl_entry_id}


@router.post("/sessions/{session_id}/unmatch")
async def unmatch_transaction(session_id: str, request: Request):
    """Remove match from a bank transaction."""
    await require_auth(request)
    db = get_db()
    body = await request.json()
    txn_id = body.get("txn_id")
    await db.bank_recon_txns.update_one(
        {"id": txn_id, "session_id": session_id},
        {"$set": {"is_matched": False, "match_id": None, "match_ref": None, "matched_at": None}}
    )
    await _recalculate_session(db, session_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# GL ENTRIES LOOKUP
# ═══════════════════════════════════════════════════════════════════

@router.get("/gl-entries")
async def get_gl_entries(request: Request, period: str = Query(...)):
    """Get GL journal entries for the given period (YYYY-MM)."""
    await require_auth(request)
    _validate_period(period)
    db = get_db()
    from_dt = f"{period}-01"
    year, mon = map(int, period.split("-"))
    last_day = (date(year, mon, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    to_dt = last_day.isoformat()

    # Try to get from journal entries - look for bank/cash account entries
    entries = await db.rahaza_journal_entries.find(
        {"date": {"$gte": from_dt, "$lte": to_dt}},
        {"_id": 0}
    ).sort("date", 1).to_list(500)
    return {"period": period, "total": len(entries), "items": serialize_doc(entries)}


# ═══════════════════════════════════════════════════════════════════
# CSV FILE IMPORT
# ═══════════════════════════════════════════════════════════════════

def _parse_idr(val: str) -> float:
    """Parse Indonesian number format: 1.500.000,50 → 1500000.5"""
    val = val.strip().replace(' ', '')
    # Remove currency symbols / spaces
    for sym in ['Rp', 'IDR', 'rp']:
        val = val.replace(sym, '').strip()
    # Handle negative wrapped in parentheses (accounting format)
    negative = val.startswith('-') or (val.startswith('(') and val.endswith(')'))
    val = val.lstrip('-(').rstrip(')')
    # ID format uses . as thousands sep and , as decimal sep
    # Detect format: if it ends with ,XX (2 digits) treat comma as decimal
    if re.search(r',\d{1,2}$', val):
        val = val.replace('.', '').replace(',', '.')
    else:
        val = val.replace('.', '').replace(',', '')
    try:
        result = float(val)
    except ValueError:
        result = 0.0
    return -result if negative else result

def _parse_date(val: str) -> str:
    """Try multiple date formats → YYYY-MM-DD."""
    val = val.strip()
    fmts = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
        "%d/%m/%y", "%d-%m-%y", "%m/%d/%Y",
        "%d %b %Y", "%d %B %Y", "%Y/%m/%d",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Try ISO-like partial dates
    m = re.match(r"(\d{1,2})[\-/](\d{1,2})[\-/](\d{2,4})", val)
    if m:
        d, mo, y = m.groups()
        y = int(y)
        d = int(d)
        mo = int(mo)
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d).isoformat()
        except Exception:
            logging.getLogger(__name__).debug("suppressed exception", exc_info=True)
    return val  # return as-is if unparseable


@router.post("/sessions/{session_id}/import-csv")
async def import_csv_file(session_id: str, request: Request, file: UploadFile = File(...)):
    """
    Upload a bank statement CSV file.
    Auto-detects columns:
      - Date  (txn_date)
      - Description / Keterangan
      - Debit / Credit amounts  OR  single Amount + sign
      - Reference / Ref
    Returns {imported, skipped, message}
    """
    await require_auth(request)
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if s.get("status") == "approved":
        raise HTTPException(400, "Sesi sudah disetujui.")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # strip BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(400, "File CSV kosong.")

    # ─── Column detection ────────────────────────────────────────
    header_row = [h.strip().lower() for h in rows[0]]
    data_start = 1  # assume first row is header

    DATE_KEYS   = ["tanggal", "date", "tgl", "transaction date", "posting date"]
    DESC_KEYS   = ["keterangan", "description", "deskripsi", "uraian", "narasi",
                   "trans description", "transaction description", "remark"]
    DEBIT_KEYS  = ["debit", "pengeluaran", "keluar", "db"]
    CREDIT_KEYS = ["credit", "kredit", "pemasukan", "masuk", "cr"]
    AMT_KEYS    = ["nominal", "amount", "jumlah", "nilai", "mutasi"]
    REF_KEYS    = ["referensi", "reference", "ref", "no ref", "no. ref", "no.ref",
                   "cheque no", "no cheque"]

    def _find_col(keys):
        for k in keys:
            for i, h in enumerate(header_row):
                if k in h:
                    return i
        return None

    col_date   = _find_col(DATE_KEYS)
    col_desc   = _find_col(DESC_KEYS)
    col_debit  = _find_col(DEBIT_KEYS)
    col_credit = _find_col(CREDIT_KEYS)
    col_amt    = _find_col(AMT_KEYS)
    col_ref    = _find_col(REF_KEYS)

    # If no header recognized, try to detect positionally (date, desc, amount)
    if col_date is None:
        # Assume first row is data (no header)
        data_start = 0
        col_date, col_desc, col_amt = 0, 1, 2

    docs = []
    skipped = 0
    for row in rows[data_start:]:
        if not row or all(not c.strip() for c in row):
            continue
        def _get(idx):
            if idx is None or idx >= len(row):
                return ""
            return row[idx].strip()

        raw_date = _get(col_date)
        if not raw_date:
            skipped += 1
            continue

        txn_date = _parse_date(raw_date)
        description = _get(col_desc)
        reference   = _get(col_ref)

        # Determine amount & type
        if col_debit is not None and col_credit is not None:
            d_val = _parse_idr(_get(col_debit))
            c_val = _parse_idr(_get(col_credit))
            if d_val and not c_val:
                amount = abs(d_val)
                txn_type = "debit"
            elif c_val and not d_val:
                amount = abs(c_val)
                txn_type = "credit"
            elif d_val:
                amount = abs(d_val)
                txn_type = "debit"
            else:
                skipped += 1
                continue
        elif col_amt is not None:
            raw_amt = _parse_idr(_get(col_amt))
            if raw_amt < 0:
                amount = abs(raw_amt)
                txn_type = "credit"
            else:
                amount = raw_amt
                txn_type = "debit"
        else:
            skipped += 1
            continue

        if amount == 0:
            skipped += 1
            continue

        docs.append({
            "id": _uid(),
            "session_id": session_id,
            "txn_date": txn_date,
            "description": description,
            "reference": reference,
            "amount": amount,
            "type": txn_type,
            "is_matched": False,
            "match_id": None,
            "match_ref": None,
            "created_at": _now(),
        })
        if len(docs) >= 500:
            break

    if docs:
        await db.bank_recon_txns.insert_many(docs)
        for d in docs:
            d.pop("_id", None)
    await _recalculate_session(db, session_id)
    return {
        "imported": len(docs),
        "skipped": skipped,
        "message": f"{len(docs)} transaksi berhasil diimpor{f', {skipped} baris dilewati' if skipped else ''}.",
    }


# ═══════════════════════════════════════════════════════════════════
# AUTO-MATCH HEURISTIC
# ═══════════════════════════════════════════════════════════════════

def _word_overlap_score(a: str, b: str) -> float:
    """Return fraction of words in `a` that appear in `b` (0-1)."""
    if not a or not b:
        return 0.0
    a_words = set(re.sub(r'[^a-z0-9]', ' ', a.lower()).split())
    b_words = set(re.sub(r'[^a-z0-9]', ' ', b.lower()).split())
    stop = {'the', 'a', 'an', 'dan', 'ke', 'di', 'dari', 'untuk', 'dengan', 'ke', 'pada'}
    a_words -= stop
    b_words -= stop
    if not a_words:
        return 0.0
    common = a_words & b_words
    return len(common) / len(a_words)


@router.post("/sessions/{session_id}/auto-match")
async def auto_match_transactions(session_id: str, request: Request):
    """
    Automatically match unmatched bank transactions to unmatched GL entries
    using a scoring heuristic:
      50 pts — exact amount match
      20 pts — same date, 15 within 1 day, 10 within 3 days, 5 within 7 days
      30 pts — description/reference word overlap (scaled)
    Threshold: ≥ 60 pts to auto-match.
    Returns {matched, attempted, message}
    """
    await require_auth(request)
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if s.get("status") == "approved":
        raise HTTPException(400, "Sesi sudah disetujui.")

    # Load unmatched bank transactions
    txns = await db.bank_recon_txns.find(
        {"session_id": session_id, "is_matched": False}, {"_id": 0}
    ).to_list(500)

    # Load unmatched GL entries for the same period
    period = s.get("period", "")
    if period:
        year, month = period.split("-")
        gl_start = f"{year}-{month}-01"
        import calendar as _cal
        last_day = _cal.monthrange(int(year), int(month))[1]
        gl_end = f"{year}-{month}-{last_day:02d}"
        gl_q = {"date": {"$gte": gl_start, "$lte": gl_end}, "is_matched": {"$ne": True}}
    else:
        gl_q = {"is_matched": {"$ne": True}}

    # RC-26: SSOT GL = rahaza_journal_entries (gl_entries = phantom — 0 insert di seluruh
    # kode → auto-match tak pernah jalan). Hanya JE berstatus 'posted' yang dicocokkan.
    gl_q["status"] = "posted"
    gl_entries = await db.rahaza_journal_entries.find(gl_q, {"_id": 0}).to_list(500)

    if not txns or not gl_entries:
        return {"matched": 0, "attempted": len(txns), "message": "Tidak ada data untuk dicocokkan."}

    matched_count = 0
    used_gl_ids = set()

    for txn in txns:
        best_score = 0
        best_gl = None

        txn_amount = float(txn.get("amount", 0))
        txn_date_str = txn.get("txn_date", "")
        try:
            txn_date = date.fromisoformat(txn_date_str) if txn_date_str else None
        except Exception:
            txn_date = None
        txn_desc = f"{txn.get('description', '')} {txn.get('reference', '')}".strip()

        for gl in gl_entries:
            if gl.get("id") in used_gl_ids:
                continue

            score = 0
            # RC-26: peta field JE — nominal = total_debit (JE seimbang), fallback lama
            gl_amount = float(gl.get("total_debit") or gl.get("amount") or gl.get("debit") or gl.get("credit") or 0)

            # 1. Amount match (50 pts)
            if abs(txn_amount - gl_amount) < 0.01:
                score += 50

            # 2. Date proximity (max 20 pts)
            gl_date_str = gl.get("date", gl.get("txn_date", ""))
            if gl_date_str and txn_date:
                try:
                    gl_date = date.fromisoformat(gl_date_str[:10])
                    diff = abs((txn_date - gl_date).days)
                    if diff == 0:
                        score += 20
                    elif diff <= 1:
                        score += 15
                    elif diff <= 3:
                        score += 10
                    elif diff <= 7:
                        score += 5
                except Exception:
                    logging.getLogger(__name__).debug("suppressed exception", exc_info=True)

            # 3. Description / reference overlap (max 30 pts) — RC-26: JE pakai memo/je_number
            gl_desc = f"{gl.get('memo', gl.get('description', ''))} {gl.get('je_number', gl.get('reference', ''))}".strip()
            overlap = _word_overlap_score(txn_desc, gl_desc)
            score += int(overlap * 30)

            if score > best_score:
                best_score = score
                best_gl = gl

        # Auto-match if score ≥ 60 and amount was matched
        if best_gl and best_score >= 60:
            gl_id = best_gl.get("id", "")
            gl_ref = best_gl.get("je_number", best_gl.get("memo", ""))
            await db.bank_recon_txns.update_one(
                {"id": txn["id"]},
                {"$set": {"is_matched": True, "match_id": gl_id, "match_ref": gl_ref,
                           "match_score": best_score, "auto_matched": True}}
            )
            # RC-26: flag match ditulis ADDITIVE ke JE (is_matched/matched_txn_id) —
            # tidak mengubah field akuntansi apa pun; dipakai gl_q utk eksklusi run berikutnya.
            await db.rahaza_journal_entries.update_one(
                {"id": gl_id},
                {"$set": {"is_matched": True, "matched_txn_id": txn["id"]}}
            )
            used_gl_ids.add(gl_id)
            matched_count += 1

    await _recalculate_session(db, session_id)
    return {
        "matched": matched_count,
        "attempted": len(txns),
        "message": f"Auto-match selesai: {matched_count} dari {len(txns)} transaksi berhasil dicocokkan.",
    }


# ═══════════════════════════════════════════════════════════════════
# APPROVE
# ═══════════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/approve")
async def approve_session(session_id: str, request: Request):
    from routes.shared import require_perm
    user = await require_perm(
        request, 'finance.approve', 'finance.manage',
        legacy_roles=('accounting', 'manager_keuangan', 'staff_keuangan',
                      'owner', 'admin', 'superadmin'),
        message='Akses ditolak: Anda tidak berhak menyetujui rekonsiliasi bank.')
    db = get_db()
    s = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if s.get("status") == "approved":
        raise HTTPException(400, "Sesi sudah disetujui.")
    if s.get("unmatched_count", 0) > 0:
        raise HTTPException(400, f"Masih ada {s['unmatched_count']} transaksi yang belum dicocokkan. Selesaikan dulu sebelum approve.")
    await db.bank_recon_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "status": "approved",
            "approved_at": _now(),
            "approved_by": user["id"],
            "approved_by_name": user.get("name", ""),
        }}
    )
    out = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    return serialize_doc(out)


# ═══════════════════════════════════════════════════════════════════
# SUMMARY DASHBOARD
# ═══════════════════════════════════════════════════════════════════

@router.get("/summary")
async def get_summary(request: Request):
    await require_auth(request)
    db = get_db()
    total = await db.bank_recon_sessions.count_documents({})
    draft = await db.bank_recon_sessions.count_documents({"status": "draft"})
    in_progress = await db.bank_recon_sessions.count_documents({"status": "in_progress"})
    approved = await db.bank_recon_sessions.count_documents({"status": "approved"})
    # Total unmatched across all active sessions
    pipeline = [
        {"$match": {"status": {"$nin": ["approved"]}}},
        {"$group": {"_id": None, "total_unmatched": {"$sum": "$unmatched_count"}}},
    ]
    agg = await db.bank_recon_sessions.aggregate(pipeline).to_list(1)
    total_unmatched = agg[0]["total_unmatched"] if agg else 0
    # Recent sessions
    recent = await db.bank_recon_sessions.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(500)
    return {
        "total_sessions": total,
        "draft": draft,
        "in_progress": in_progress,
        "approved": approved,
        "total_unmatched": total_unmatched,
        "recent": serialize_doc(recent),
    }


# ═══════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════

async def _recalculate_session(db, session_id: str):
    """Recount matched/unmatched and update session totals.
    Workflow status (draft/in_progress/approved) is preserved — only the
    explicit /approve endpoint promotes a session to 'approved'."""
    total_txns = await db.bank_recon_txns.count_documents({"session_id": session_id})
    matched = await db.bank_recon_txns.count_documents({"session_id": session_id, "is_matched": True})
    unmatched = total_txns - matched
    # Calculate total amounts
    pipeline = [
        {"$match": {"session_id": session_id}},
        {"$group": {
            "_id": "$type",
            "total": {"$sum": "$amount"}
        }}
    ]
    amounts = await db.bank_recon_txns.aggregate(pipeline).to_list(500)
    debit_total = next((a["total"] for a in amounts if a["_id"] == "debit"), 0)
    credit_total = next((a["total"] for a in amounts if a["_id"] == "credit"), 0)
    difference = debit_total - credit_total

    # Compute next workflow status (never auto-approve — that requires explicit user action)
    session = await db.bank_recon_sessions.find_one({"id": session_id}, {"_id": 0})
    current_status = (session or {}).get("status", "draft")
    if current_status == "approved":
        next_status = "approved"
    elif total_txns > 0:
        next_status = "in_progress"
    else:
        next_status = "draft"

    await db.bank_recon_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "total_bank_txns": total_txns,
            "matched_count": matched,
            "unmatched_count": unmatched,
            "debit_total": debit_total,
            "credit_total": credit_total,
            "difference": difference,
            "is_balanced": (total_txns > 0 and unmatched == 0),
            "status": next_status,
            "updated_at": _now(),
        }}
    )
