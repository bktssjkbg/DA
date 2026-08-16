"""
Content Calendar Module — Backend Routes
Phase 3 Week 8: Jadwal konten multi-platform dengan AI hook generation
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
# F6 (sesi #10) — endpoint DAFTAR/RINGKAS wajib menyaring sendiri (middleware
# hanya menolak permintaan yang MENYEBUT toko, ia tidak tahu isi jawaban).
from core import marketing_account_scope as _scope
from database import get_db
from auth import require_auth
from routes.shared import require_portal
from ai_llm import LlmChat, UserMessage
import json
import calendar

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/marketing/content-calendar", tags=["marketing-content-calendar"])

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

CONTENT_TYPES = [
    "foto_produk", "video_produk", "reels_tiktok", "live_streaming",
    "story", "promo_flash_sale", "konten_edukasi", "behind_scenes",
    "testimonial", "unboxing", "kolaborasi_kol"
]

CONTENT_TYPE_LABELS = {
    "foto_produk":       "Foto Produk",
    "video_produk":      "Video Produk",
    "reels_tiktok":      "Reels / TikTok",
    "live_streaming":    "Live Streaming",
    "story":             "Story",
    "promo_flash_sale":  "Promo Flash Sale",
    "konten_edukasi":    "Konten Edukasi",
    "behind_scenes":     "Behind the Scenes",
    "testimonial":       "Testimonial",
    "unboxing":          "Unboxing",
    "kolaborasi_kol":    "Kolaborasi KOL",
}

CONTENT_STATUSES = ["draft", "scheduled", "posted", "cancelled"]
PLATFORMS = ["shopee", "tiktok", "tokopedia", "instagram", "facebook"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)

def serialize(obj):
    if isinstance(obj, list):
        return [serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items() if k != "_id"}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    return obj

def _get_user(request: Request) -> dict:
    return getattr(request.state, "user", {}) or {}


# ── Seed ─────────────────────────────────────────────────────────────────────
async def seed_content_calendar_if_empty():
    db = get_db()
    if await db.marketing_content_calendar.count_documents({}) > 0:
        return

    import random
    # F14 — model `ContentEntryIn` SUDAH punya `account_id`, tapi seed demo ini
    # menulis nama toko sebagai teks saja ⇒ 30/30 baris demo tak berlingkup toko.
    from core import marketing_account_scope as _scope
    accounts = await _scope.seed_account_pool(db)
    content_types = CONTENT_TYPES
    hooks = [
        "Gamis busui friendly yang bikin nyaman seharian!",
        "Koleksi terbaru Daluna – tampil syari & modern",
        "Flash sale 3 hari, diskon hingga 50%!",
        "Tutorial styling kerudung segiempat dalam 60 detik",
        "Unboxing paket gamis ukuran M-XXXL – semua ada!",
        "Customer review bintang 5 – yuk intip!",
        "Behind the scenes proses jahit kualitas premium",
        "Tips memilih bahan gamis yang adem untuk iklim tropis",
        "Live sore ini jam 3 – ada doorprize!",
        "Bundle hemat 2 pcs gamis + kerudung",
    ]
    ctas = ["Klik di bio!", "Order sekarang!", "DM admin!", "Klik link di bio!", "Swipe up!"]
    post_times = ["07:00", "09:00", "11:00", "12:00", "15:00", "17:00", "19:00", "20:00", "21:00"]
    statuses = ["posted", "posted", "posted", "scheduled", "scheduled", "draft"]

    entries = []
    base = _now().replace(day=1)
    for i in range(30):
        day_offset = random.randint(-5, 25)
        post_date = (base + timedelta(days=day_offset)).date()
        acc = random.choice(accounts)
        ct  = random.choice(content_types)
        entries.append({
            "id":           str(uuid.uuid4()),
            "account_id":   acc["id"],
            "account_name": acc.get("account_name", ""),
            "platform":     acc.get("platform", "shopee"),
            "date":         post_date.isoformat(),
            "content_type": ct,
            "content_type_label": CONTENT_TYPE_LABELS.get(ct, ct),
            "title":        random.choice(hooks),
            "description":  "Konten ini bertujuan meningkatkan engagement dan penjualan produk busana muslim DA/Daluna.",
            "cta":          random.choice(ctas),
            "post_time":    random.choice(post_times),
            "reference_link": "",
            "status":       random.choice(statuses),
            "_seed_origin": True,
            "created_by":   "system",
            "created_at":   _now(),
            "updated_at":   _now(),
        })

    if entries:
        await db.marketing_content_calendar.insert_many(entries)
    logger.info(f"[content_calendar] seeded {len(entries)} entries")


# ── Models ───────────────────────────────────────────────────────────────────
class ContentEntryIn(BaseModel):
    account_id: Optional[str] = None  # UUID dari marketing_platform_accounts
    account_name: str
    platform: str
    date: str          # YYYY-MM-DD
    content_type: str
    title: str
    description: Optional[str] = ""
    cta: Optional[str] = ""
    post_time: Optional[str] = ""  # HH:MM
    reference_link: Optional[str] = ""
    status: Optional[str] = "draft"
    # ── F7 (2026-08-13) — pemilik konten, bukti terbit, dan KPI ───────────────
    creator_id: Optional[str] = None        # pemilik konten (marketing_kol_creators)
    catalog_item_id: Optional[str] = None   # produk yang dipromosikan
    sku: Optional[str] = ""
    brief: Optional[str] = ""
    hook: Optional[str] = ""
    published_url: Optional[str] = ""       # WAJIB bila status='posted'
    published_at: Optional[str] = ""
    platform_post_id: Optional[str] = ""
    kpi: Optional[dict] = None

class ContentEntryUpdate(BaseModel):
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    platform: Optional[str] = None
    date: Optional[str] = None
    content_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    cta: Optional[str] = None
    post_time: Optional[str] = None
    reference_link: Optional[str] = None
    status: Optional[str] = None
    creator_id: Optional[str] = None
    catalog_item_id: Optional[str] = None
    sku: Optional[str] = None
    brief: Optional[str] = None
    hook: Optional[str] = None
    published_url: Optional[str] = None
    published_at: Optional[str] = None
    platform_post_id: Optional[str] = None
    kpi: Optional[dict] = None


class ContentKpiIn(BaseModel):
    """KPI satu konten. Diisi manual (atau nanti dari impor `content_performance`)."""
    views: float = 0
    likes: float = 0
    comments: float = 0
    shares: float = 0
    saves: float = 0
    watch_time_avg_sec: float = 0
    ctr: float = 0
    orders: float = 0
    gmv: float = 0
    published_url: Optional[str] = None
    source: Optional[str] = "manual"


KPI_KEYS = ("views", "likes", "comments", "shares", "saves",
            "watch_time_avg_sec", "ctr", "orders", "gmv")
_URL_RE = __import__("re").compile(r"^https?://[^\s]+$", 2)


def _kpi_derived(kpi: dict) -> dict:
    """Angka turunan KPI konten — dihitung, tidak pernah diketik."""
    views = float(kpi.get("views") or 0)
    eng = sum(float(kpi.get(k) or 0) for k in ("likes", "comments", "shares"))
    orders = float(kpi.get("orders") or 0)
    gmv = float(kpi.get("gmv") or 0)
    return {
        "engagement": round(eng, 2),
        "engagement_rate": round(eng / views * 100, 2) if views > 0 else 0.0,
        "save_rate": round(float(kpi.get("saves") or 0) / views * 100, 2) if views > 0 else 0.0,
        "cvr": round(orders / views * 100, 4) if views > 0 else 0.0,
        "gmv_per_view": round(gmv / views, 2) if views > 0 else 0.0,
        "aov": round(gmv / orders, 2) if orders > 0 else 0.0,
    }


async def _validate_content_links(db, doc: dict, *, status: str) -> None:
    """Pagar F7: bukti terbit & pemilik konten tidak boleh dikarang.

    `status='posted'` TANPA `published_url` adalah cara paling mudah membuat laporan
    konten berisi baris "sudah terbit" yang tidak bisa dibuka siapa pun — dan KPI-nya
    tidak akan pernah bisa dicek ulang.
    """
    from fastapi import HTTPException as _HE
    url = (doc.get("published_url") or "").strip()
    if status == "posted":
        if not url:
            raise _HE(400, "Konten berstatus 'posted' wajib membawa link terbit "
                           "(published_url) sebagai bukti tayang.")
        if not _URL_RE.match(url):
            raise _HE(400, f"Link terbit harus berupa URL http/https — diterima: '{url[:60]}'")
    elif url and not _URL_RE.match(url):
        raise _HE(400, f"Link terbit harus berupa URL http/https — diterima: '{url[:60]}'")
    cid = doc.get("creator_id")
    if cid:
        cr = await db.marketing_kol_creators.find_one({"id": cid}, {"_id": 0, "id": 1})
        if not cr:
            raise _HE(400, f"Kreator '{cid}' tidak ada di master KOL/Kreator.")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/types")
async def get_content_types(request: Request):
    await require_portal(request, "toko")  # RBAC read-guard (BUG-AUTH-1)
    return {"success": True, "types": [{"value": k, "label": v} for k, v in CONTENT_TYPE_LABELS.items()]}

@router.get("/platforms")
async def get_platforms(request: Request):
    await require_portal(request, "toko")  # RBAC read-guard (BUG-AUTH-1)
    labels = {"shopee": "Shopee", "tiktok": "TikTok", "tokopedia": "Tokopedia",
               "instagram": "Instagram", "facebook": "Facebook"}
    return {"success": True, "platforms": [{"value": p, "label": labels.get(p, p)} for p in PLATFORMS]}


@router.get("/summary")
async def get_summary(request: Request,
                      account_id: str = Query(default="")):
    user = await require_auth(request)
    await seed_content_calendar_if_empty()
    db = get_db()
    _sq = await _scope.scope_filter(
        db, user, {"account_id": account_id} if account_id else {})

    total     = await db.marketing_content_calendar.count_documents(dict(_sq))
    draft     = await db.marketing_content_calendar.count_documents({**_sq, "status": "draft"})
    scheduled = await db.marketing_content_calendar.count_documents({**_sq, "status": "scheduled"})
    posted    = await db.marketing_content_calendar.count_documents({**_sq, "status": "posted"})
    cancelled = await db.marketing_content_calendar.count_documents({**_sq, "status": "cancelled"})

    # This month
    now = _now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    now.strftime("%Y-%m")
    this_month = await db.marketing_content_calendar.count_documents(
        {**_sq, "date": {"$gte": month_start.strftime("%Y-%m-01"),
                         "$lte": now.strftime("%Y-%m-%d")}}
    )

    # By platform
    pipeline = [{"$group": {"_id": "$platform", "count": {"$sum": 1}}}]
    by_platform_raw = await db.marketing_content_calendar.aggregate(pipeline).to_list(100)
    by_platform = {r["_id"]: r["count"] for r in by_platform_raw if r["_id"]}

    return {
        "success": True,
        "data": {
            "total":      total,
            "draft":      draft,
            "scheduled":  scheduled,
            "posted":     posted,
            "cancelled":  cancelled,
            "this_month": this_month,
            "by_platform": by_platform,
        }
    }


@router.get("/monthly")
async def get_monthly(
    request: Request,
    year:    int = Query(default=None, ge=1970, le=2999),
    month:   int = Query(default=None, ge=1, le=12),
    account: str = Query(default=""),
    platform: str = Query(default="")
):
    user = await require_auth(request)
    await seed_content_calendar_if_empty()
    db = get_db()

    now = _now()
    y = year  or now.year
    m = month or now.month

    # Build date range for the month
    start_d = f"{y:04d}-{m:02d}-01"
    last_day = calendar.monthrange(y, m)[1]
    end_d   = f"{y:04d}-{m:02d}-{last_day:02d}"

    q = await _scope.scope_filter(db, user, {"date": {"$gte": start_d, "$lte": end_d}})
    if account:
        q["account_name"] = {"$regex": account, "$options": "i"}
    if platform:
        q["platform"]    = platform

    entries = await db.marketing_content_calendar.find(q, {"_id": 0}).sort("date", 1).to_list(500)
    return {"success": True, "data": serialize(entries), "year": y, "month": m}


@router.get("")
async def list_entries(
    request: Request,
    page:     int = Query(default=1, ge=1),
    page_size:int = Query(default=20, le=100),
    account_id: str = Query(default="", description="F14 — filter per toko (SSOT)"),
    status:   str = Query(default=""),
    platform: str = Query(default=""),
    account:  str = Query(default="", description="kompatibilitas: cocok nama"),
    content_type: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to:   str = Query(default=""),
):
    user = await require_auth(request)
    await seed_content_calendar_if_empty()
    db = get_db()

    q = await _scope.scope_filter(
        db, user, {"account_id": account_id} if account_id else {})
    if status:
        q["status"]       = status
    if platform:
        q["platform"]     = platform
    if content_type:
        q["content_type"] = content_type
    if account:
        q["account_name"] = {"$regex": account, "$options": "i"}
    if date_from:
        q.setdefault("date", {})["$gte"] = date_from
    if date_to:
        q.setdefault("date", {})["$lte"] = date_to

    total  = await db.marketing_content_calendar.count_documents(q)
    skip   = (page - 1) * page_size
    items  = await db.marketing_content_calendar.find(q, {"_id": 0})\
                     .sort("date", 1).skip(skip).limit(page_size).to_list(page_size)
    return {
        "success": True,
        "data": serialize(items),
        "pagination": {"total": total, "page": page, "page_size": page_size,
                       "total_pages": (total + page_size - 1) // page_size}
    }


@router.post("")
async def create_entry(body: ContentEntryIn, request: Request):
    await require_auth(request)
    user = _get_user(request)
    db   = get_db()

    entry = {
        "id":           str(uuid.uuid4()),
        "account_id":   body.account_id,  # FK to marketing_platform_accounts (UUID)
        "account_name": body.account_name,
        "platform":     body.platform,
        "date":         body.date,
        "content_type": body.content_type,
        "content_type_label": CONTENT_TYPE_LABELS.get(body.content_type, body.content_type),
        "title":        body.title,
        "description":  body.description or "",
        "cta":          body.cta or "",
        "post_time":    body.post_time or "",
        "reference_link": body.reference_link or "",
        "status":       body.status if body.status in CONTENT_STATUSES else "draft",
        # F7 — pemilik konten, produk, bukti terbit, KPI
        "creator_id":       body.creator_id,
        "catalog_item_id":  body.catalog_item_id,
        "sku":              body.sku or "",
        "brief":            body.brief or "",
        "hook":             body.hook or "",
        "published_url":    (body.published_url or "").strip(),
        "published_at":     body.published_at or "",
        "platform_post_id": body.platform_post_id or "",
        "kpi":              {k: float((body.kpi or {}).get(k) or 0) for k in KPI_KEYS},
        "kpi_updated_at":   None,
        "kpi_source":       "",
        "created_by":   user.get("email", "unknown"),
        "created_at":   _now(),
        "updated_at":   _now(),
    }
    await _validate_content_links(db, entry, status=entry["status"])
    if entry.get("creator_id"):
        entry["kpi_derived"] = _kpi_derived(entry["kpi"])
    await db.marketing_content_calendar.insert_one(entry)
    return {"success": True, "data": serialize(entry)}


@router.put("/{entry_id}")
async def update_entry(entry_id: str, body: ContentEntryUpdate, request: Request):
    await require_auth(request)
    db = get_db()

    existing = await db.marketing_content_calendar.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Entry not found")

    upd = {k: v for k, v in body.dict().items() if v is not None}
    if "content_type" in upd:
        upd["content_type_label"] = CONTENT_TYPE_LABELS.get(upd["content_type"], upd["content_type"])
    upd["updated_at"] = _now()
    _merged = {**existing, **upd}
    await _validate_content_links(db, _merged, status=str(_merged.get("status") or "draft"))
    await db.marketing_content_calendar.update_one({"id": entry_id}, {"$set": upd})
    updated = {**existing, **upd}
    return {"success": True, "data": serialize(updated)}


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    res = await db.marketing_content_calendar.delete_one({"id": entry_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Entry not found")
    return {"success": True, "message": "Deleted"}


@router.post("/{entry_id}/status")
async def update_status(entry_id: str, request: Request):
    await require_auth(request)
    body = await request.json()
    new_status = body.get("status", "")
    if new_status not in CONTENT_STATUSES:
        raise HTTPException(400, f"Invalid status: {new_status}")
    db = get_db()
    existing = await db.marketing_content_calendar.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Entry not found")
    await db.marketing_content_calendar.update_one(
        {"id": entry_id}, {"$set": {"status": new_status, "updated_at": _now()}}
    )
    return {"success": True, "status": new_status}


@router.post("/{entry_id}/ai-hook")
async def generate_ai_hook(entry_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    entry = await db.marketing_content_calendar.find_one({"id": entry_id}, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Entry not found")

    if not EMERGENT_LLM_KEY:
        raise HTTPException(503, "AI not configured")

    ct_label = CONTENT_TYPE_LABELS.get(entry.get("content_type", ""), entry.get("content_type", ""))
    platform = entry.get("platform", "")
    account  = entry.get("account_name", "")

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"content-hook-{entry_id[:8]}",
        system_message="Kamu adalah copywriter ahli untuk marketplace Indonesia (Shopee, TikTok Shop, Tokopedia). Buat caption/hook yang menarik, singkat, relevan untuk audiens Indonesia. Respond ONLY with valid JSON."
    ).with_model("openai", "gpt-4o-mini")

    prompt = (
        f"Buat 3 variasi hook/judul konten untuk:\n"
        f"Platform: {platform} | Akun: {account} | Jenis: {ct_label}\n"
        f"Konten saat ini: '{entry.get('title', '')}\n\n"
        f"Return JSON persis: {{\"hooks\": [\"hook1\", \"hook2\", \"hook3\"], "
        f"\"best_hook\": \"pilihan terbaik\", \"cta_suggestion\": \"CTA rekomendasi\", "
        f"\"description_suggestion\": \"deskripsi 1-2 kalimat\"}}"
    )

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())

        best_hook = result.get("best_hook", entry.get("title", ""))
        await db.marketing_content_calendar.update_one(
            {"id": entry_id},
            {"$set": {
                "title": best_hook,
                "cta":   result.get("cta_suggestion", entry.get("cta", "")),
                "description": result.get("description_suggestion", entry.get("description", "")),
                "updated_at": _now()
            }}
        )
        return {"success": True, "result": result, "applied_hook": best_hook}
    except Exception as e:
        raise HTTPException(500, f"AI hook generation failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# F7.3 — KPI KONTEN & LAPORAN PERFORMA KREATOR
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/{entry_id}/kpi")
async def set_content_kpi(entry_id: str, body: ContentKpiIn, request: Request):
    """Isi/perbarui KPI satu konten.

    KPI hanya boleh diisi untuk konten yang **sudah terbit** dan punya link — kalau
    tidak, laporan performa akan memuat angka yang tidak bisa dicek ulang ke mana pun.
    """
    user = await require_auth(request)
    db = get_db()
    entry = await db.marketing_content_calendar.find_one({"id": entry_id}, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Konten tidak ditemukan")
    url = (body.published_url or entry.get("published_url") or "").strip()
    if not url:
        raise HTTPException(400, "KPI hanya bisa diisi untuk konten yang sudah terbit — "
                                 "isi link terbitnya dulu (tombol Edit).")
    if not _URL_RE.match(url):
        raise HTTPException(400, f"Link terbit harus URL http/https — diterima: '{url[:60]}'")
    kpi = {k: float(getattr(body, k) or 0) for k in KPI_KEYS}
    now = _now()
    upd = {
        "kpi": kpi, "kpi_derived": _kpi_derived(kpi),
        "kpi_updated_at": now, "kpi_source": body.source or "manual",
        "published_url": url, "updated_at": now,
        "updated_by": user.get("email", "system"),
    }
    if str(entry.get("status")) != "posted":
        # Konten yang KPI-nya sudah ada jelas sudah terbit; status "draft" pada baris
        # yang punya angka nyata adalah kontradiksi yang membuat rekap salah hitung.
        upd["status"] = "posted"
        upd["published_at"] = entry.get("published_at") or now.date().isoformat()
    await db.marketing_content_calendar.update_one({"id": entry_id}, {"$set": upd})
    return {"success": True, "data": serialize({**entry, **upd})}


@router.get("/performance")
async def content_performance(request: Request,
                              account_id: Optional[str] = Query(None),
                              creator_id: Optional[str] = Query(None),
                              date_from: Optional[str] = Query(None),
                              date_to: Optional[str] = Query(None),
                              group_by: str = Query("creator",
                                                    description="creator|content_type|account")):
    """Performa konten dikelompokkan — dipakai rapat mingguan & laporan kreator.

    **Omzet yang didorong kreator** dibaca dari DUA sumber yang sengaja dipisah:
      * `gmv` KPI konten (angka dari platform, per konten);
      * `marketing_orders.creator_id` (pesanan nyata hasil impor, F1).
    Keduanya ditampilkan berdampingan, TIDAK dijumlah — menjumlahkannya akan
    menghitung satu penjualan dua kali, dan tidak ada yang bisa membuktikan mana
    yang benar bila keduanya berbeda.
    """
    user = await require_auth(request)
    db = get_db()
    from core import marketing_account_scope as _scope
    q: dict = {}
    if account_id:
        await _scope.assert_account_visible(db, user, account_id)
        q["account_id"] = account_id
    else:
        visible = await _scope.visible_account_ids(db, user)
        if visible is not None:
            q["account_id"] = {"$in": visible}
    if creator_id:
        q["creator_id"] = creator_id
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
    rows = await db.marketing_content_calendar.find(q, {"_id": 0}).to_list(5000)

    key_field = {"creator": "creator_id", "content_type": "content_type",
                 "account": "account_id"}.get(group_by, "creator_id")
    creators = {c["id"]: c for c in await db.marketing_kol_creators.find(
        {}, {"_id": 0, "id": 1, "name": 1, "creator_code": 1}).to_list(500)}
    accounts = {a["id"]: a for a in await db.marketing_platform_accounts.find(
        {}, {"_id": 0, "id": 1, "account_name": 1}).to_list(300)}

    buckets: dict = {}
    for r in rows:
        gk = r.get(key_field) or ("(tanpa kreator)" if key_field == "creator_id" else "(kosong)")
        b = buckets.setdefault(gk, {"key": gk, "contents": 0, "posted": 0, "with_kpi": 0,
                                    "views": 0.0, "likes": 0.0, "comments": 0.0,
                                    "shares": 0.0, "saves": 0.0, "orders": 0.0,
                                    "gmv_kpi": 0.0, "ctr_sum": 0.0, "ctr_n": 0})
        k = r.get("kpi") or {}
        b["contents"] += 1
        if str(r.get("status")) == "posted":
            b["posted"] += 1
        if r.get("kpi_updated_at"):
            b["with_kpi"] += 1
        for f, dst in (("views", "views"), ("likes", "likes"), ("comments", "comments"),
                       ("shares", "shares"), ("saves", "saves"), ("orders", "orders"),
                       ("gmv", "gmv_kpi")):
            b[dst] += float(k.get(f) or 0)
        if float(k.get("ctr") or 0) > 0:
            b["ctr_sum"] += float(k["ctr"])
            b["ctr_n"] += 1

    # omzet nyata per kreator dari pesanan (F1) — hanya untuk group_by=creator
    order_rev: dict = {}
    if key_field == "creator_id":
        oq: dict = {"creator_id": {"$nin": [None, ""]}}
        if q.get("account_id"):
            oq["account_id"] = q["account_id"]
        if date_from or date_to:
            oq["$and"] = []
            if date_from:
                oq["$and"].append({"$or": [{"order_date": {"$gte": date_from}},
                                           {"order_date": {"$gte": _dt(date_from)}}]})
            if date_to:
                oq["$and"].append({"$or": [{"order_date": {"$lte": date_to + "\uffff"}},
                                           {"order_date": {"$lte": _dt(date_to, end=True)}}]})
        from core import marketing_daily_rollup as _rollup
        for o in await db.marketing_orders.find(
                oq, {"_id": 0, "creator_id": 1, "status": 1, "revenue_product": 1,
                     "order_amount": 1, "items": 1, "total_payment": 1}).to_list(30000):
            if (o.get("status") or "") == "cancelled":
                continue
            cid = o.get("creator_id")
            d = order_rev.setdefault(cid, {"orders": 0, "revenue": 0.0})
            d["orders"] += 1
            d["revenue"] += _rollup.order_revenue_product(o)

    out = []
    for b in buckets.values():
        eng = b["likes"] + b["comments"] + b["shares"]
        label = b["key"]
        if key_field == "creator_id":
            label = (creators.get(b["key"], {}).get("name") or b["key"])
        elif key_field == "account_id":
            label = (accounts.get(b["key"], {}).get("account_name") or b["key"])
        elif key_field == "content_type":
            label = CONTENT_TYPE_LABELS.get(b["key"], b["key"])
        ov = order_rev.get(b["key"], {})
        out.append({
            **b, "label": label,
            "creator_code": creators.get(b["key"], {}).get("creator_code", ""),
            "engagement": round(eng, 2),
            "engagement_rate": round(eng / b["views"] * 100, 2) if b["views"] > 0 else 0.0,
            "ctr_avg": round(b["ctr_sum"] / b["ctr_n"], 2) if b["ctr_n"] else 0.0,
            "gmv_per_content": round(b["gmv_kpi"] / b["contents"], 2) if b["contents"] else 0.0,
            "views_per_content": round(b["views"] / b["contents"], 2) if b["contents"] else 0.0,
            "order_revenue": round(ov.get("revenue", 0.0), 2),
            "order_count": ov.get("orders", 0),
            "kpi_coverage_pct": round(b["with_kpi"] / b["contents"] * 100, 2) if b["contents"] else 0.0,
        })
    out.sort(key=lambda r: (-r["gmv_kpi"], -r["views"], r["label"]))
    totals = {
        "contents": sum(r["contents"] for r in out),
        "posted": sum(r["posted"] for r in out),
        "with_kpi": sum(r["with_kpi"] for r in out),
        "views": round(sum(r["views"] for r in out), 2),
        "engagement": round(sum(r["engagement"] for r in out), 2),
        "orders": round(sum(r["orders"] for r in out), 2),
        "gmv_kpi": round(sum(r["gmv_kpi"] for r in out), 2),
        "order_revenue": round(sum(r["order_revenue"] for r in out), 2),
    }
    totals["kpi_coverage_pct"] = (round(totals["with_kpi"] / totals["contents"] * 100, 2)
                                  if totals["contents"] else 0.0)
    return serialize({
        "success": True, "group_by": group_by, "rows": out, "totals": totals,
        "data_notes": [
            "GMV dari KPI konten (angka platform) dan omzet dari pesanan "
            "(`marketing_orders.creator_id`) ditampilkan BERDAMPINGAN dan tidak "
            "dijumlah — menjumlahkannya berarti menghitung satu penjualan dua kali.",
            f"Cakupan KPI {totals['kpi_coverage_pct']}%: hanya konten yang KPI-nya "
            "sudah diisi yang ikut menghitung views/engagement/GMV.",
            "Konten berstatus 'posted' wajib punya link terbit — angka tanpa link "
            "tidak bisa dicek ulang.",
        ],
    })


def _dt(date_str: str, end: bool = False):
    from datetime import datetime as _d, timezone as _tz
    d = _d.strptime(date_str, "%Y-%m-%d").replace(tzinfo=_tz.utc)
    return d.replace(hour=23, minute=59, second=59) if end else d
