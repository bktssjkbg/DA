"""marketing_settlements — **F9: PENCAIRAN (SETTLEMENT) MARKETPLACE** (input MANUAL).

═══════════════════════════════════════════════════════════════════════════════
KENAPA INPUT MANUAL, BUKAN IMPOR BERKAS — DAN KENAPA ITU JUSTRU LEBIH AMAN
═══════════════════════════════════════════════════════════════════════════════
Rencana asli F9 adalah mengimpor berkas laporan pencairan Shopee/TikTok. Aturan
proyek ini (blokir data **BD-2**) melarangnya sampai ada contoh berkas ASLI:

    "1 contoh laporan Pencairan/Settlement TikTok dan Shopee — F9 tidak boleh
     dimulai; pemetaan kolom uang TIDAK BOLEH DITEBAK."

Larangan itu masuk akal. Modul ini menghitung `net_payout`, komisi platform,
potongan iklan, dan refund — lalu **membuat jurnal akuntansi**. Kalau kolom
ditebak (mis. "Total" dianggap omzet padahal artinya omzet setelah potongan),
angkanya akan terlihat rapi tetapi SALAH, dan salahnya masuk buku besar tanpa
satu pun galat.

Keputusan pemilik (2026-08-14): **"settlement pencairan sementara dibuatkan
manual input dulu"**. Itu menghapus blokirnya sepenuhnya, bukan menghindarinya:
kalau staf mengisi field yang NAMANYA JELAS satu per satu, tidak ada kolom yang
perlu ditebak siapa pun. Saat berkas asli tersedia nanti, impor bisa ditambahkan
di atas struktur yang sudah terbukti ini.

═══════════════════════════════════════════════════════════════════════════════
TIGA ATURAN YANG MEMBUAT ANGKA DI SINI BISA DIPERCAYA
═══════════════════════════════════════════════════════════════════════════════
1. **`net_payout` TIDAK PERNAH DIHITUNG SERVER — ia DIISI STAF dari mutasi bank
   / laporan platform.** Server justru menghitung *nilai yang seharusnya* lalu
   menampilkan **SELISIH**-nya. Ini kebalikan dari kebiasaan umum, dan
   sengaja: kalau server yang menghitung net, maka setiap potongan yang belum
   kita kenal akan HILANG diam-diam (angkanya tetap "cocok" karena kita sendiri
   yang membuatnya cocok). Dengan cara ini, potongan tak dikenal muncul sebagai
   selisih — dan selisih adalah satu-satunya petunjuk bahwa ada biaya yang
   belum kita catat.

2. **Selisih ≠ 0 ⇒ TIDAK BOLEH jadi jurnal.** Jurnal dari angka yang belum
   seimbang mustahil seimbang (Σ debit ≠ Σ kredit). Staf harus MENAMAI dulu
   selisihnya di `other_deductions` atau `adjustments` (dengan catatan). Jadi
   penolakan ini bukan birokrasi: ia memaksa biaya tak dikenal punya NAMA.

3. **Jurnalnya DRAFT.** Angka datang dari pihak luar; Keuangan yang memutuskan
   ia masuk buku besar (`POST /api/rahaza/journals/{je_id}/post`, endpoint yang
   sudah ada). Idempoten lewat `source_module` + `source_ref` ⇒ menekan tombol
   dua kali tidak melahirkan dua jurnal.

Kolom mengikuti spesifikasi F9.1 (`RENCANA_EKSEKUSI_MASTER` §F9), dan dedupe
`(platform, account_id, settlement_id)` mencegah satu pencairan tercatat dua kali.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from auth import require_auth
from core import marketing_account_scope as _scope
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/marketing/settlements", tags=["marketing-settlements"])

COLL = "marketing_settlements"
SOURCE_MODULE = "marketplace_settlement"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ser(d: dict) -> dict:
    out = {}
    for k, v in (d or {}).items():
        if k == "_id":
            continue
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out


# ── Peta akun (COA) — DITULIS DI SATU TEMPAT ────────────────────────────────
# Kalau setiap endpoint memilih akunnya sendiri, suatu hari salah satunya
# memakai akun berbeda dan laporan L/R berubah tanpa ada yang mengubah aturan.
COA = {
    "cash":        "1-1201",  # Bank BCA — uang yang benar-benar masuk
    "revenue":     "4-1100",  # Penjualan Garment (bruto)
    "returns":     "4-1200",  # Retur Penjualan (kontra-pendapatan)
    "discount":    "4-1300",  # Diskon Penjualan (kontra-pendapatan)
    "platform_fee": "4-141",  # Potongan Platform (Fee Shopee/TikTok)
    "ads":         "6-1100",  # Biaya Iklan & Promosi
    "other":       "7-4000",  # Pendapatan/Beban Lain-Lain
}

# Field uang + arahnya terhadap `net_payout`. Satu daftar ini dipakai oleh
# perhitungan selisih DAN pembuat jurnal, jadi keduanya mustahil berbeda.
MONEY_FIELDS = {
    "gross_sales":          +1,
    "refunds":              -1,
    "seller_discount":      -1,
    "shipping_subsidy":     +1,
    "platform_commission":  -1,
    "platform_service_fee": -1,
    "affiliate_commission": -1,
    "ads_deduction":        -1,
    "other_deductions":     -1,
    "adjustments":          +1,   # boleh negatif (koreksi platform)
}


class SettlementIn(BaseModel):
    account_id: str
    platform: str
    settlement_id: str = Field(min_length=1)
    settlement_date: str                 # YYYY-MM-DD — tanggal uang masuk
    period_from: Optional[str] = None
    period_to: Optional[str] = None

    gross_sales: float = Field(default=0, ge=0)
    refunds: float = Field(default=0, ge=0)
    seller_discount: float = Field(default=0, ge=0)
    shipping_subsidy: float = Field(default=0, ge=0)
    platform_commission: float = Field(default=0, ge=0)
    platform_service_fee: float = Field(default=0, ge=0)
    affiliate_commission: float = Field(default=0, ge=0)
    ads_deduction: float = Field(default=0, ge=0)
    other_deductions: float = Field(default=0, ge=0)
    # `adjustments` SENGAJA tanpa `ge=0`: koreksi platform bisa mengurangi.
    adjustments: float = 0
    # Diisi staf dari mutasi bank / laporan platform — BUKAN dihitung server.
    net_payout: float = Field(default=0, ge=0)
    notes: Optional[str] = ""
    other_deductions_note: Optional[str] = ""


def _expected_net(doc: dict) -> float:
    return round(sum(sign * float(doc.get(f) or 0)
                     for f, sign in MONEY_FIELDS.items()), 2)


def _with_math(doc: dict) -> dict:
    """Tambahkan hasil pemeriksaan aritmetika — SELALU, bukan hanya saat gagal."""
    expected = _expected_net(doc)
    actual = round(float(doc.get("net_payout") or 0), 2)
    diff = round(actual - expected, 2)
    doc["expected_net_payout"] = expected
    doc["net_payout_diff"] = diff
    doc["math_verified"] = abs(diff) < 0.01
    total_ded = round(
        sum(float(doc.get(f) or 0) for f, s in MONEY_FIELDS.items() if s < 0), 2)
    doc["total_deductions"] = total_ded
    gross = float(doc.get("gross_sales") or 0)
    # Berapa persen omzet bruto yang dipotong platform — angka yang paling sering
    # ditanyakan pemilik dan paling jarang bisa dijawab.
    doc["deduction_pct"] = round(total_ded / gross * 100, 2) if gross else 0.0
    return doc


@router.get("/coa-map")
async def coa_map(request: Request):
    """Peta akun yang dipakai jurnal — DITAMPILKAN di layar, bukan disembunyikan.

    Kalau peta akun hanya ada di kode, orang yang membaca laporan tidak bisa
    memeriksa apakah potongan platform masuk ke akun yang benar.
    """
    await require_auth(request)
    db = get_db()
    out = []
    for role, code in COA.items():
        acc = await db.rahaza_coa_accounts.find_one(
            {"code": code}, {"_id": 0, "code": 1, "name": 1, "type": 1, "active": 1})
        out.append({"role": role, "code": code,
                    "name": (acc or {}).get("name"),
                    "type": (acc or {}).get("type"),
                    "found": bool(acc and acc.get("active"))})
    return {"ok": True, "coa": out,
            "missing": [o["code"] for o in out if not o["found"]]}


@router.get("")
async def list_settlements(
    request: Request,
    account_id: str = Query(default=""),
    platform: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, le=200),
    # Pelajaran Fase B: pengurutan dikerjakan SERVER supaya "pencairan terbesar"
    # berlaku untuk SELURUH data, bukan halaman yang kebetulan terbuka.
    sort_by: str = Query(default="settlement_date"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    user = await require_auth(request)
    db = get_db()

    q: dict = {}
    vis = await _scope.visible_account_ids(db, user)
    if vis is not None:
        q["account_id"] = {"$in": vis}
    if account_id:
        q["account_id"] = account_id
    if platform:
        q["platform"] = platform
    if date_from:
        q.setdefault("settlement_date", {})["$gte"] = date_from
    if date_to:
        q.setdefault("settlement_date", {})["$lte"] = date_to
    if search:
        q["settlement_id"] = {"$regex": search, "$options": "i"}

    SORTABLE = {"settlement_date", "settlement_id", "platform", "gross_sales",
                "net_payout", "total_deductions", "deduction_pct", "created_at"}
    key = sort_by if sort_by in SORTABLE else "settlement_date"
    direction = -1 if sort_dir == "desc" else 1

    total = await db[COLL].count_documents(q)
    rows = await db[COLL].find(q, {"_id": 0}).sort(key, direction) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)

    # Ringkasan dihitung atas SELURUH data yang cocok (bukan halaman) — kalau
    # dihitung dari halaman, "total pencairan" akan berubah saat orang pindah
    # halaman dan tidak ada yang tahu angka mana yang benar.
    agg = await db[COLL].aggregate([
        {"$match": q},
        {"$group": {"_id": None,
                    "gross": {"$sum": "$gross_sales"},
                    "net": {"$sum": "$net_payout"},
                    "ded": {"$sum": "$total_deductions"}}},
    ]).to_list(1)
    s = agg[0] if agg else {}
    unverified = await db[COLL].count_documents({**q, "math_verified": False})

    return {
        "ok": True,
        "data": [_ser(r) for r in rows],
        "summary": {
            "gross_sales": round(float(s.get("gross") or 0), 2),
            "net_payout": round(float(s.get("net") or 0), 2),
            "total_deductions": round(float(s.get("ded") or 0), 2),
            "deduction_pct": round(float(s.get("ded") or 0) / float(s["gross"]) * 100, 2)
            if s.get("gross") else 0.0,
            "unverified_count": unverified,
        },
        "pagination": {"total": total, "page": page, "page_size": page_size,
                       "total_pages": max(1, (total + page_size - 1) // page_size)},
    }


@router.post("")
async def create_settlement(body: SettlementIn, request: Request):
    user = await require_auth(request)
    db = get_db()
    account = await _scope.require_account(db, body.account_id)

    # Kunci duplikat = (toko, nomor pencairan). SENGAJA TANPA `platform`:
    # `_scope.stamp_account()` menimpa `platform` dengan platform milik toko,
    # sehingga nilai yang DICARI (kiriman browser) bisa berbeda dari yang
    # TERSIMPAN — dan pencarian duplikatnya jadi tidak pernah cocok. Terbukti:
    # nomor pencairan yang sama bisa masuk dua kali (HTTP 200 dua-duanya).
    # Platform juga redundan di sini: satu toko hanya ada di satu platform.
    dup = await db[COLL].find_one({
        "account_id": body.account_id, "settlement_id": body.settlement_id,
    }, {"_id": 0, "id": 1, "settlement_date": 1})
    if dup:
        raise HTTPException(
            409, f"Pencairan '{body.settlement_id}' untuk toko ini sudah pernah "
                 f"dicatat (tanggal {dup.get('settlement_date')}). Satu pencairan "
                 f"yang tercatat dua kali akan menggandakan pendapatan.")

    doc = body.dict()
    doc.update({
        "id": str(uuid.uuid4()),
        "je_id": None, "je_number": None, "je_status": None,
        "created_by": (getattr(request.state, "user", {}) or {}).get("email", "unknown"),
        "created_at": _now(), "updated_at": _now(),
    })
    _scope.stamp_account(doc, account)
    _with_math(doc)
    await db[COLL].insert_one(doc)
    return {"ok": True, "data": _ser(doc)}


@router.put("/{sid}")
async def update_settlement(sid: str, body: SettlementIn, request: Request):
    await require_auth(request)
    db = get_db()
    cur = await db[COLL].find_one({"id": sid}, {"_id": 0})
    if not cur:
        raise HTTPException(404, "Pencairan tidak ditemukan.")
    # Sudah ada jurnal ⇒ angkanya sudah dipakai akuntansi. Mengubahnya diam-diam
    # akan membuat jurnal dan sumbernya bercerita hal berbeda.
    if cur.get("je_id"):
        raise HTTPException(
            400, f"Pencairan ini sudah punya jurnal ({cur.get('je_number')}). "
                 f"Batalkan/void jurnalnya dulu di Portal Finance sebelum "
                 f"mengubah angkanya — kalau tidak, jurnal dan sumbernya akan "
                 f"menyebut angka yang berbeda.")
    upd = body.dict()
    upd["updated_at"] = _now()
    merged = {**cur, **upd}
    _with_math(merged)
    upd.update({k: merged[k] for k in
                ("expected_net_payout", "net_payout_diff", "math_verified",
                 "total_deductions", "deduction_pct")})
    await db[COLL].update_one({"id": sid}, {"$set": upd})
    return {"ok": True, "data": _ser({**cur, **upd})}


@router.delete("/{sid}")
async def delete_settlement(sid: str, request: Request):
    await require_auth(request)
    db = get_db()
    cur = await db[COLL].find_one({"id": sid}, {"_id": 0})
    if not cur:
        raise HTTPException(404, "Pencairan tidak ditemukan.")
    if cur.get("je_id"):
        raise HTTPException(
            400, f"Tidak bisa dihapus: sudah terbit jurnal {cur.get('je_number')}. "
                 f"Void jurnalnya dulu di Portal Finance.")
    await db[COLL].delete_one({"id": sid})
    return {"ok": True}


@router.post("/{sid}/journal")
async def create_draft_journal(sid: str, request: Request):
    """Buat jurnal **DRAFT** dari satu pencairan. Idempoten."""
    user = await require_auth(request)
    db = get_db()
    doc = await db[COLL].find_one({"id": sid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Pencairan tidak ditemukan.")
    _with_math(doc)

    # ── Aturan 2: selisih harus BERNAMA dulu ──────────────────────────────────
    if not doc["math_verified"]:
        # Angka diformat SENDIRI-SENDIRI. Versi pertama memformat seluruh
        # kalimat dengan `.replace(",", ".")` dan itu ikut mengubah koma
        # kalimatnya ("…punya NAMA, bukan hilang" → "NAMA. bukan hilang").
        # Pesan yang rusak tata bahasanya membuat orang menduga sistemnya rusak.
        def _rp(v: float) -> str:
            return f"Rp {v:,.0f}".replace(",", ".")

        raise HTTPException(
            400,
            f"Angka belum seimbang: net payout yang diisi "
            f"{_rp(doc['net_payout'])} sedangkan hasil hitung dari rinciannya "
            f"{_rp(doc['expected_net_payout'])} (selisih "
            f"{_rp(doc['net_payout_diff'])}). Jurnal dari angka yang belum "
            f"seimbang MUSTAHIL seimbang. Catat dulu selisihnya sebagai "
            f"'Potongan lain' atau 'Penyesuaian' beserta keterangannya — supaya "
            f"biaya yang belum dikenal punya NAMA, bukan hilang.")

    from routes.rahaza_posting import _create_posted_je, _find_existing_je

    existing = await _find_existing_je(db, SOURCE_MODULE, doc["settlement_id"])
    if existing:
        await db[COLL].update_one({"id": sid}, {"$set": {
            "je_id": existing["id"], "je_number": existing["je_number"],
            "je_status": existing["status"], "updated_at": _now()}})
        return {"ok": True, "already": True, "je_number": existing["je_number"],
                "je_status": existing["status"],
                "message": f"Pencairan ini sudah punya jurnal "
                           f"{existing['je_number']} ({existing['status']}) — "
                           f"tidak dibuat dua kali."}

    g = lambda f: round(float(doc.get(f) or 0), 2)  # noqa: E731
    fee_total = g("platform_commission") + g("platform_service_fee") \
        + g("affiliate_commission")
    adj = g("adjustments")

    lines = [
        # Uang yang benar-benar masuk rekening
        {"account_code": COA["cash"], "debit": g("net_payout"), "credit": 0,
         "description": f"Pencairan {doc['platform']} {doc['settlement_id']}"},
        # Pendapatan BRUTO — bukan angka bersih. Kalau yang dicatat angka bersih,
        # potongan platform tidak pernah terlihat sebagai biaya.
        {"account_code": COA["revenue"], "debit": 0, "credit": g("gross_sales"),
         "description": "Penjualan bruto marketplace"},
        {"account_code": COA["returns"], "debit": g("refunds"), "credit": 0,
         "description": "Refund / retur"},
        {"account_code": COA["discount"], "debit": g("seller_discount"), "credit": 0,
         "description": "Diskon penjual"},
        {"account_code": COA["other"], "debit": 0, "credit": g("shipping_subsidy"),
         "description": "Subsidi ongkir platform"},
        {"account_code": COA["platform_fee"], "debit": fee_total, "credit": 0,
         "description": "Komisi + fee layanan + komisi afiliasi"},
        {"account_code": COA["ads"], "debit": g("ads_deduction"), "credit": 0,
         "description": "Biaya iklan dipotong dari pencairan"},
        {"account_code": COA["other"], "debit": g("other_deductions"), "credit": 0,
         "description": (doc.get("other_deductions_note") or "Potongan lain")},
        # Penyesuaian bisa dua arah — ditulis di sisi yang benar, bukan dipaksa.
        {"account_code": COA["other"],
         "debit": (-adj if adj < 0 else 0), "credit": (adj if adj > 0 else 0),
         "description": "Penyesuaian platform"},
    ]

    res = await _create_posted_je(
        db,
        je_date=date.fromisoformat(str(doc["settlement_date"])[:10]),
        memo=f"Pencairan {doc['platform']} — {doc.get('account_name') or ''} "
             f"({doc['settlement_id']})",
        source_module=SOURCE_MODULE,
        source_ref=doc["settlement_id"],
        lines_raw=lines,
        user=user,
        status="draft",
    )
    if not res.get("ok"):
        raise HTTPException(400, res.get("error") or "Gagal membuat jurnal.")

    await db[COLL].update_one({"id": sid}, {"$set": {
        "je_id": res["je_id"], "je_number": res["je_number"],
        "je_status": "draft", "updated_at": _now()}})
    return {"ok": True, "je_id": res["je_id"], "je_number": res["je_number"],
            "je_status": "draft",
            "message": f"Jurnal DRAFT {res['je_number']} dibuat. Keuangan "
                       f"menyetujuinya di Portal Finance → Jurnal."}


@router.get("/reconcile")
async def reconcile(
    request: Request,
    account_id: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
):
    """Jawab pertanyaan "angka mana yang benar": omzet marketing vs pencairan.

    Dua angka ini SELALU berbeda, dan itu normal (pencairan tertinggal beberapa
    hari, dan sudah dipotong). Yang tidak normal adalah kalau bedanya tidak bisa
    dijelaskan. Karena itu selisihnya ditampilkan APA ADANYA beserta total
    potongan — tanpa ada yang "dirapikan" supaya kelihatan cocok.
    """
    user = await require_auth(request)
    db = get_db()

    sq: dict = {}
    vis = await _scope.visible_account_ids(db, user)
    if vis is not None:
        sq["account_id"] = {"$in": vis}
    if account_id:
        sq["account_id"] = account_id
    if date_from:
        sq.setdefault("settlement_date", {})["$gte"] = date_from
    if date_to:
        sq.setdefault("settlement_date", {})["$lte"] = date_to

    sagg = await db[COLL].aggregate([
        {"$match": sq},
        {"$group": {"_id": None, "n": {"$sum": 1},
                    "gross": {"$sum": "$gross_sales"},
                    "net": {"$sum": "$net_payout"},
                    "ded": {"$sum": "$total_deductions"},
                    "refunds": {"$sum": "$refunds"}}},
    ]).to_list(1)
    s = sagg[0] if sagg else {}

    # Omzet marketing dari SSOT pesanan (bukan koleksi turunan).
    #
    # HATI-HATI (jebakan yang sempat membuat rekonsiliasi ini BOHONG): versi
    # pertama memakai `total_amount` dan menyaring `order_date` sebagai STRING.
    # Field `total_amount` TIDAK ADA di `marketing_orders`, dan `order_date`
    # bertipe `datetime` — hasilnya "559 pesanan, omzet Rp 0". Angka nol yang
    # muncul di sebelah 559 pesanan bukan sekadar salah: ia membuat seluruh
    # selisih rekonsiliasi terlihat seperti kesalahan platform.
    #
    # `marketing_orders` punya TIGA angka omzet dengan arti berbeda, jadi
    # ketiganya dilaporkan APA ADANYA beserta labelnya — memilih satu diam-diam
    # berarti memutuskan definisi omzet atas nama pembaca laporan.
    oq: dict = {}
    if vis is not None:
        oq["account_id"] = {"$in": vis}
    if account_id:
        oq["account_id"] = account_id
    _dt = {}
    if date_from:
        _dt["$gte"] = datetime.fromisoformat(f"{date_from}T00:00:00+00:00")
    if date_to:
        _dt["$lte"] = datetime.fromisoformat(f"{date_to}T23:59:59+00:00")
    if _dt:
        oq["order_date"] = _dt
    oagg = await db.marketing_orders.aggregate([
        {"$match": oq},
        {"$group": {"_id": None, "n": {"$sum": 1},
                    "order_amount": {"$sum": "$order_amount"},
                    "revenue_gross": {"$sum": "$revenue_gross"},
                    "revenue_product": {"$sum": "$revenue_product"}}},
    ]).to_list(1)
    o = oagg[0] if oagg else {}

    gross = round(float(s.get("gross") or 0), 2)
    omzet_gross = round(float(o.get("revenue_gross") or 0), 2)
    omzet_product = round(float(o.get("revenue_product") or 0), 2)
    order_amount = round(float(o.get("order_amount") or 0), 2)
    unverified = await db[COLL].count_documents({**sq, "math_verified": False})

    return {
        "ok": True,
        "settlement": {
            "count": int(s.get("n") or 0),
            "gross_sales": gross,
            "net_payout": round(float(s.get("net") or 0), 2),
            "total_deductions": round(float(s.get("ded") or 0), 2),
            "refunds": round(float(s.get("refunds") or 0), 2),
            "deduction_pct": round(float(s.get("ded") or 0) / gross * 100, 2)
            if gross else 0.0,
            "unverified_count": unverified,
        },
        "marketing": {
            "order_count": int(o.get("n") or 0),
            # Ketiganya dilaporkan; labelnya ikut supaya tidak dibaca sebagai
            # angka yang seharusnya sama.
            "revenue_gross": omzet_gross,
            "revenue_product": omzet_product,
            "order_amount": order_amount,
            "labels": {
                "revenue_gross": "sebelum diskon penjual & potongan platform",
                "revenue_product": "sesudah diskon penjual, sebelum potongan platform",
                "order_amount": "nilai yang dibayar pembeli",
            },
        },
        "gap": {
            # Pembanding yang paling setara: bruto platform vs bruto marketing.
            "gross_vs_revenue_gross": round(gross - omzet_gross, 2),
            "net_vs_revenue_product": round(
                float(s.get("net") or 0) - omzet_product, 2),
            "why": ("Selisih WAJAR terjadi karena: (1) pencairan tertinggal "
                    "beberapa hari dari tanggal pesanan, (2) pesanan yang "
                    "dibatalkan/retur tidak ikut dicairkan, dan (3) satu "
                    "pencairan bisa memuat beberapa periode. Yang perlu "
                    "ditelusuri adalah selisih yang TIDAK bisa dijelaskan oleh "
                    "ketiga hal itu. Angka omzet ditampilkan dalam tiga definisi "
                    "karena ketiganya memang berbeda arti — bukan supaya salah "
                    "satunya dipilih agar 'cocok'."),
        },
    }
