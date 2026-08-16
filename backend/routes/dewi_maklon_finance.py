"""
CV. Dewi Aditya — Finance Integration untuk Maklon
Phase Production-Maklon Overhaul — Phase 4

Menutup gap kritis: Maklon Billing harus masuk Finance GL.

Fungsi:
  post_maklon_ar_invoice(db, po, user)    → Dr AR / Cr Pendapatan Jasa Maklon
  post_cmt_ap_invoice(db, payment, user)  → Dr Biaya CMT / Cr AP Vendor
  post_maklon_ar_payment(db, invoice, movement, user) → Dr Bank / Cr AR

Endpoints:
  POST /api/dewi/maklon/pos/{po_id}/post-ar      → Manual trigger post AR
  POST /api/dewi/maklon/pos/{po_id}/advance-payment → Input DP klien
  POST /api/dewi/cmt/payments/{payment_id}/post-ap   → Post CMT AP ke GL
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, date
from database import get_db
from auth import require_auth, serialize_doc, log_activity
from routes.rahaza_posting import _create_posted_je, _find_existing_je
from routes.rahaza_posting_profiles import get_mapping
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api/dewi/maklon/finance', tags=['Dewi-Maklon-Finance'])


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────────────
# POSTING HELPERS (shared functions)
# ──────────────────────────────────────────────────────────────────────────────

async def post_maklon_ar_invoice(db, po: dict, user: dict) -> dict:
    """
    Post AR Invoice untuk Maklon PO ke Finance GL.
    Dr Piutang Usaha (AR) / Cr Pendapatan Jasa Maklon
    Idempotent: cek existing JE dulu.
    """
    po_id = po.get('id')
    ar_invoice_id = po.get('ar_invoice_id')
    if not ar_invoice_id:
        return {'ok': False, 'error': 'PO belum punya AR Invoice. Confirm dulu.'}

    source_ref = f'maklon_ar:{ar_invoice_id}'
    existing = await _find_existing_je(db, 'maklon_ar_invoice', source_ref)
    if existing:
        return {'ok': True, 'je_id': existing['id'], 'je_number': existing.get('je_number'), 'already_posted': True}

    mapping = await get_mapping(db, 'maklon_ar_invoice')
    if not mapping:
        # Fallback ke ar_invoice mapping jika maklon_ar_invoice belum ada
        mapping = await get_mapping(db, 'ar_invoice')
    if not mapping:
        return {'ok': False, 'error': 'Posting profile maklon_ar_invoice tidak ditemukan'}

    total = po.get('total_value', 0)
    tax_pct = 0.0  # bisa dikonfigurasi nanti
    tax_amount = round(total * tax_pct / 100, 2)
    revenue_amount = round(total - tax_amount, 2)

    lines = [
        {
            'account_code': mapping.get('debit_ar', '1-1301'),
            'debit': total,
            'credit': 0,
            'description': f'AR Jasa Maklon — {po.get("po_number","")} — {po.get("client_name","")}',
        },
        {
            'account_code': mapping.get('credit_revenue_maklon', mapping.get('credit_revenue', '4-1100')),
            'debit': 0,
            'credit': revenue_amount,
            'description': f'Pendapatan Jasa Maklon — {po.get("po_number","")}',
        },
    ]
    if tax_amount > 0:
        lines.append({
            'account_code': mapping.get('credit_tax_output', '2-1400'),
            'debit': 0,
            'credit': tax_amount,
            'description': f'PPN Keluaran — {po.get("po_number","")}',
        })

    je_date = date.fromisoformat(po.get('po_date') or date.today().isoformat())
    result = await _create_posted_je(
        db,
        je_date=je_date,
        memo=f'AR Jasa Maklon — {po.get("po_number","")} — {po.get("client_name","")}',
        source_module='maklon_ar_invoice',
        source_ref=source_ref,
        lines_raw=lines,
        user=user,
    )
    # Save result to AR Invoice
    if result.get('ok'):
        await db.rahaza_ar_invoices.update_one(
            {'id': ar_invoice_id},
            {'$set': {
                'gl_posted_at': _now(),
                'gl_je_id': result['je_id'],
                'gl_je_number': result['je_number'],
                'status': 'issued',
                'post_error': None,
            }}
        )
        await db.dewi_maklon_pos.update_one(
            {'id': po_id},
            {'$set': {
                'gl_posted_at': _now(),
                'gl_je_id': result['je_id'],
                'gl_je_number': result.get('je_number'),
                'post_error': None,
            }}
        )
    else:
        await db.dewi_maklon_pos.update_one(
            {'id': po_id},
            {'$set': {'post_error': result.get('error'), 'post_error_at': _now()}}
        )
    return result


async def _cmt_expense_account(db, cmt_payment: dict, mapping: dict) -> tuple:
    """(account_code, domain) akun BIAYA untuk tagihan jasa jahit CMT.

    FASE IA-C (2026-07-26) — BUG AKUNTANSI NYATA: profil bawaan `cmt_ap_invoice`
    memakai `debit_cmt_expense = '6-2200'` dengan komentar "# Biaya Jasa CMT",
    padahal di CoA yang benar-benar ter-seed **6-2200 = "Listrik & Air Kantor"**.
    Akibatnya SETIAP tagihan jasa jahit yang diposting (termasuk lewat pintu Invoice
    Produksi yang baru) menambah beban Listrik & Air — HPP produksi kurang saji dan
    laporan biaya operasional membengkak tanpa sebab.

    Perbaikan sekaligus memenuhi arahan owner #7 (data internal & maklon terpisah):
      · PO internal → `5-231 Biaya Vendor CMT – Jahit` (COGS produksi DA sendiri)
      · PO maklon   → `7-120 Biaya Vendor CMT – Maklon` (biaya proyek maklon)
    Keduanya bisa ditimpa lewat Master Akuntansi (kunci `debit_cmt_expense_internal`
    / `debit_cmt_expense_maklon`), dan tetap jatuh ke `debit_cmt_expense` lama bila
    profil kustom pengguna hanya punya kunci itu.
    """
    domain = 'maklon'
    po_id = cmt_payment.get('po_id')
    if po_id:
        po = await db.production_pos.find_one({'id': po_id}, {'_id': 0, 'business_type': 1})
        if (po or {}).get('business_type') == 'internal':
            domain = 'internal'
    elif cmt_payment.get('job_ids'):
        domain = 'internal'   # CMT-flow: DA menjahitkan produk DA sendiri
    key = 'debit_cmt_expense_internal' if domain == 'internal' else 'debit_cmt_expense_maklon'
    default = '5-231' if domain == 'internal' else '7-120'
    code = mapping.get(key) or mapping.get('debit_cmt_expense') or \
        mapping.get('debit_expense_default') or default
    # profil lama yang masih menunjuk akun keliru → pakai akun yang benar
    if code == '6-2200':
        code = default
    return code, domain


async def post_cmt_ap_invoice(db, cmt_payment: dict, user: dict) -> dict:
    """
    Post AP Invoice untuk CMT Payment ke Finance GL.
    Dr Biaya Vendor CMT (COGS internal / biaya maklon) / Cr Hutang Usaha (AP Vendor)
    """
    payment_id = cmt_payment.get('id')
    source_ref = f'cmt_ap:{payment_id}'
    existing = await _find_existing_je(db, 'cmt_ap_invoice', source_ref)
    if existing:
        return {'ok': True, 'je_id': existing['id'], 'je_number': existing.get('je_number'), 'already_posted': True}

    mapping = await get_mapping(db, 'cmt_ap_invoice')
    if not mapping:
        # Fallback
        mapping = await get_mapping(db, 'ap_invoice')
    if not mapping:
        return {'ok': False, 'error': 'Posting profile cmt_ap_invoice tidak ditemukan'}

    total = float(cmt_payment.get('subtotal', 0))
    if total <= 0:
        return {'ok': False, 'error': 'Total CMT payment = 0, tidak bisa di-post'}

    # Phase 5: per-vendor AP subledger. Resolve akun AP milik vendor CMT ini;
    # fallback ke akun kontrol (mapping credit_ap / 2-1100) bila fitur mati/gagal.
    ap_code = mapping.get('credit_ap', '2-1100')
    try:
        from routes.coa_auto import resolve_ap_account_for_cmt
        resolved = await resolve_ap_account_for_cmt(
            db, cmt_payment.get('cmt_partner_id'), cmt_payment.get('cmt_name'), user
        )
        if resolved:
            ap_code = resolved
    except Exception as _e:
        logger.warning(f'[cmt_ap] resolve subledger gagal, pakai kontrol: {_e}')

    expense_code, expense_domain = await _cmt_expense_account(db, cmt_payment, mapping)

    lines = [
        {
            'account_code': expense_code,
            'debit': total,
            'credit': 0,
            'description': f'Biaya Jasa CMT {expense_domain} — {cmt_payment.get("cmt_name","")} — '
                           f'{cmt_payment.get("payment_code") or cmt_payment.get("payment_number","")}',
        },
        {
            'account_code': ap_code,
            'debit': 0,
            'credit': total,
            'description': f'AP CMT Vendor — {cmt_payment.get("cmt_name","")}',
        },
    ]

    # Penalty reduction
    penalty = float(cmt_payment.get('total_penalty', 0))
    if penalty > 0:
        lines[1]['credit'] = round(total - penalty, 2)
        lines.append({
            'account_code': mapping.get('debit_penalty_income', '4-920'),
            'debit': 0,
            'credit': penalty,
            'description': f'Penalti keterlambatan CMT — {cmt_payment.get("cmt_name","")}',
        })

    je_date = date.fromisoformat(cmt_payment.get('payment_date') or date.today().isoformat())
    result = await _create_posted_je(
        db,
        je_date=je_date,
        memo=f'Biaya CMT — {cmt_payment.get("cmt_name","")} — '
             f'{cmt_payment.get("payment_code") or cmt_payment.get("payment_number","")}',
        source_module='cmt_ap_invoice',
        source_ref=source_ref,
        lines_raw=lines,
        user=user,
    )
    if result.get('ok'):
        await db.dewi_cmt_payments.update_one(
            {'id': payment_id},
            {'$set': {
                'gl_posted_at': _now(),
                'gl_je_id': result['je_id'],
                'gl_je_number': result.get('je_number'),
                'post_error': None,
            }}
        )
    else:
        await db.dewi_cmt_payments.update_one(
            {'id': payment_id},
            {'$set': {'post_error': result.get('error'), 'post_error_at': _now()}}
        )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

@router.post('/pos/{po_id}/post-ar')
async def post_ar_for_po(po_id: str, user: dict = Depends(require_auth)):
    """Trigger manual post AR Invoice ke Finance GL untuk Maklon PO."""
    db = get_db()
    po = await db.dewi_maklon_pos.find_one({'id': po_id})
    if not po:
        raise HTTPException(404, 'PO tidak ditemukan')
    if po.get('status') == 'draft':
        raise HTTPException(400, 'PO harus di-confirm dulu sebelum post ke Finance')

    result = await post_maklon_ar_invoice(db, po, user)
    if not result.get('ok'):
        raise HTTPException(400, result.get('error', 'Posting gagal'))
    return {
        'status': 'posted',
        'je_id': result.get('je_id'),
        'je_number': result.get('je_number'),
        'already_posted': result.get('already_posted', False),
    }


class AdvancePaymentIn(BaseModel):
    amount: float = Field(..., gt=0)
    payment_date: Optional[str] = None
    notes: Optional[str] = None
    bank_account: Optional[str] = None


@router.post('/pos/{po_id}/advance-payment')
async def record_advance_payment(po_id: str, payload: AdvancePaymentIn, user: dict = Depends(require_auth)):
    """Input DP/Uang Muka dari klien maklon."""
    db = get_db()
    po = await db.dewi_maklon_pos.find_one({'id': po_id})
    if not po:
        raise HTTPException(404, 'PO tidak ditemukan')

    payment_date = payload.payment_date or date.today().isoformat()

    # Finance GL: Dr Bank / Cr Uang Muka Diterima – Maklon.
    # Resolve accounts from the dedicated 'maklon_advance_payment' posting profile,
    # but VALIDATE each is a postable leaf (not a group/header). Fall back to the
    # known-postable defaults (1-131 bank / 2-140 uang muka diterima) if the mapped
    # account is missing or a non-postable header — this self-heals against stale
    # seeded profiles (e.g. an old mapping that pointed to 2-1300 'Hutang Pajak').
    mapping = await get_mapping(db, 'maklon_advance_payment') or {}

    async def _postable(code, default):
        if code:
            acc = await db.rahaza_coa_accounts.find_one({'code': code}, {'is_group': 1})
            if acc and not acc.get('is_group'):
                return code
        return default

    debit_acc = await _postable(mapping.get('debit_cash_default'), '1-131')
    credit_acc = await _postable(mapping.get('credit_advance_customer'), '2-140')

    dp_id = _uid()
    lines = [
        {
            'account_code': debit_acc,
            'debit': payload.amount,
            'credit': 0,
            'description': f'DP Maklon — {po.get("po_number","")} — {po.get("client_name","")}',
        },
        {
            'account_code': credit_acc,  # Uang Muka Diterima – Maklon (postable)
            'debit': 0,
            'credit': payload.amount,
            'description': f'Uang Muka Klien Maklon — {po.get("po_number","")}',
        },
    ]
    je_date = date.fromisoformat(payment_date)
    je_result = await _create_posted_je(
        db,
        je_date=je_date,
        memo=f'DP Maklon — {po.get("po_number","")} — {po.get("client_name","")}',
        source_module='maklon_advance_payment',
        source_ref=f'dp:{po_id}:{dp_id}',
        lines_raw=lines,
        user=user,
    )

    # Update PO advance payment
    await db.dewi_maklon_pos.update_one(
        {'id': po_id},
        {'$inc': {'advance_payment': payload.amount}, '$set': {'updated_at': _now()}}
    )

    # Save DP record
    dp_doc = {
        'id': _uid(),
        'po_id': po_id,
        'po_number': po['po_number'],
        'client_id': po['client_id'],
        'client_name': po['client_name'],
        'amount': payload.amount,
        'payment_date': payment_date,
        'notes': payload.notes or '',
        'bank_account': payload.bank_account or '',
        'gl_je_id': je_result.get('je_id'),
        'gl_je_number': je_result.get('je_number'),
        'post_error': je_result.get('error') if not je_result.get('ok') else None,
        'created_at': _now(),
        'created_by': user.get('id'),
    }
    await db.dewi_maklon_advance_payments.insert_one(dp_doc)
    await log_activity(user.get('id', ''), user.get('name', ''), 'advance_payment', 'dewi_maklon_advance_payments',
                       f'DP Maklon {po.get("po_number")} — Rp {payload.amount:,.0f}')
    return serialize_doc(dp_doc)


@router.post('/cmt-payments/{payment_id}/post-ap')
async def post_ap_for_cmt_payment(payment_id: str, user: dict = Depends(require_auth)):
    """Post AP Invoice untuk pembayaran CMT Vendor ke Finance GL."""
    db = get_db()
    payment = await db.dewi_cmt_payments.find_one({'id': payment_id})
    if not payment:
        raise HTTPException(404, 'CMT Payment tidak ditemukan')

    result = await post_cmt_ap_invoice(db, payment, user)
    if not result.get('ok'):
        raise HTTPException(400, result.get('error', 'Posting gagal'))
    return {
        'status': 'posted',
        'je_id': result.get('je_id'),
        'je_number': result.get('je_number'),
        'already_posted': result.get('already_posted', False),
    }
