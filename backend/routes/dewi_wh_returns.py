"""
Return & Refund — Portal Gudang (Blueprint §3.7)

Dua tipe return:
  Tipe 1 — paket kembali dari ekspedisi  (expedition_return)
  Tipe 2 — customer request refund       (customer_refund)

Workflow:
  Pending → Received (unboxing) → Inspected (cek kondisi & penyebab) → Resolved

Collections: wh_returns

Endpoints:
  GET    /api/wh/returns              — list (filter: type, status, search)
  GET    /api/wh/returns/summary      — stats dashboard
  POST   /api/wh/returns              — buat record return baru
  GET    /api/wh/returns/{id}         — detail
  PUT    /api/wh/returns/{id}         — update info dasar
  POST   /api/wh/returns/{id}/receive — terima fisik (unboxing notes, foto notes)
  POST   /api/wh/returns/{id}/inspect — hasil inspeksi (kondisi, penyebab, rekomendasi)
  POST   /api/wh/returns/{id}/resolve — resolusi akhir (restock/reshipment/appeal/dispose)
  DELETE /api/wh/returns/{id}         — hapus (hanya Pending)
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import uuid
import re
from datetime import datetime, timezone

from database import get_db
from utils.counters import gen_prefixed_number
from auth import require_auth, serialize_doc
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wh", tags=["wh-returns"])

# ── helpers ──────────────────────────────────────────────────────────────────
def _id():  return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc).isoformat()

RETURN_TYPES   = ["expedition_return", "customer_refund"]
CONDITIONS     = ["Baik", "Rusak Ringan", "Rusak Berat", "Tidak Layak Jual"]
CAUSES         = ["Kesalahan Gudang", "Kesalahan Customer", "Kesalahan Ekspedisi", "Lainnya"]
ACTIONS        = ["Restock ke Gudang", "Reshipment", "Appeal Platform", "Dibuang / Dispose", "Donasi"]
STATUS_FLOW    = ["Pending", "Received", "Inspected", "Resolved", "Cancelled"]

CHANNELS = ["Shopee", "Tokopedia", "TikTok Shop", "Lazada", "Instagram", "WhatsApp", "Lainnya"]


async def _next_code(db) -> str:
    # RC-5 fix: atomic race-safe numbering (was count_documents()+1)
    return await gen_prefixed_number(db, "wh_returns", "return_code", "WH-RET-", 5)


# ═══════════════════════════════════════════════════════════════
# LIST & SUMMARY
# ═══════════════════════════════════════════════════════════════

@router.get("/returns/summary")
async def get_summary(request: Request):
    await require_auth(request)
    db = get_db()

    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    by_status = {r["_id"]: r["count"] for r in await db.wh_returns.aggregate(pipeline).to_list(500)}

    by_type = [{"$group": {"_id": "$return_type", "count": {"$sum": 1}}}]
    type_counts = {r["_id"]: r["count"] for r in await db.wh_returns.aggregate(by_type).to_list(500)}

    total = await db.wh_returns.count_documents({})
    pending = by_status.get("Pending", 0)
    received = by_status.get("Received", 0)
    inspected = by_status.get("Inspected", 0)
    resolved = by_status.get("Resolved", 0)

    # Items needing action today: Pending + Received + Inspected
    action_needed = pending + received + inspected

    return {
        "total": total,
        "pending": pending,
        "received": received,
        "inspected": inspected,
        "resolved": resolved,
        "action_needed": action_needed,
        "expedition_returns": type_counts.get("expedition_return", 0),
        "customer_refunds": type_counts.get("customer_refund", 0),
    }


@router.get("/returns")
async def list_returns(request: Request):
    await require_auth(request)
    db = get_db()
    sp = request.query_params
    query = {}
    if sp.get("return_type"):
        query["return_type"] = sp["return_type"]
    if sp.get("status"):
        query["status"] = sp["status"]
    if sp.get("search"):
        rx = re.compile(re.escape(sp["search"]), re.IGNORECASE)
        query["$or"] = [{"return_code": rx}, {"order_number": rx},
                         {"customer_name": rx}, {"resi_number": rx}]
    docs = await db.wh_returns.find(query, {"_id": 0}).sort("created_at", -1).limit(200).to_list(500)
    return serialize_doc(docs)


# ═══════════════════════════════════════════════════════════════
# CREATE & GET
# ═══════════════════════════════════════════════════════════════

@router.post("/returns")
async def create_return(request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()

    rt = body.get("return_type", "expedition_return")
    if rt not in RETURN_TYPES:
        raise HTTPException(400, f"return_type harus salah satu dari: {RETURN_TYPES}")
    if not body.get("order_number") and not body.get("resi_number"):
        raise HTTPException(400, "order_number atau resi_number wajib diisi")

    code = await _next_code(db)
    doc = {
        "id": _id(),
        "return_code": code,
        "return_type": rt,
        # Order info
        "order_number": body.get("order_number", ""),
        "resi_number": body.get("resi_number", ""),
        "channel": body.get("channel", ""),
        "customer_name": body.get("customer_name", ""),
        "customer_contact": body.get("customer_contact", ""),
        "sku_code": body.get("sku_code", ""),
        "product_name": body.get("product_name", ""),
        "qty": int(body.get("qty", 1)),
        "order_value": float(body.get("order_value", 0)),
        "initial_reason": body.get("initial_reason", ""),  # alasan awal customer/ekspedisi
        "notes": body.get("notes", ""),
        # Workflow
        "status": "Pending",
        "timeline": [
            {"status": "Pending", "at": _now(), "by": user["name"],
             "note": "Return dibuat"}
        ],
        # Receive step
        "received_at": "", "received_by": "",
        "unboxing_condition_notes": "",   # catatan kondisi saat unboxing
        "unboxing_photo_notes": "",       # kode foto/link bukti
        "package_condition": "",          # kondisi kemasan luar
        # Inspect step
        "inspected_at": "", "inspected_by": "",
        "item_condition": "",             # Baik / Rusak Ringan / Rusak Berat / Tidak Layak Jual
        "return_cause": "",               # Kesalahan Gudang / Customer / Ekspedisi / Lainnya
        "cause_detail": "",
        "recommended_action": "",
        # Resolve step
        "resolved_at": "", "resolved_by": "",
        "action_taken": "",               # Restock / Reshipment / Appeal / Dispose
        "action_notes": "",
        "reshipment_resi": "",            # jika reshipment
        "appeal_status": "",              # jika appeal: Pending / Success / Fail
        "restock_qty": 0,                 # jika restock
        # Meta
        "created_by": user["name"], "created_at": _now(), "updated_at": _now()
    }
    await db.wh_returns.insert_one(doc)
    return JSONResponse(serialize_doc(doc), status_code=201)


@router.get("/returns/{return_id}")
async def get_return(return_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    doc = await db.wh_returns.find_one({"id": return_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Return tidak ditemukan")
    return serialize_doc(doc)


@router.put("/returns/{return_id}")
async def update_return(return_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    body = await request.json()
    doc = await db.wh_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(404, "Return tidak ditemukan")
    upd = {k: v for k, v in body.items()
           if k not in ("_id", "id", "return_code", "status", "timeline", "created_at", "created_by")}
    upd["updated_at"] = _now()
    await db.wh_returns.update_one({"id": return_id}, {"$set": upd})
    result = await db.wh_returns.find_one({"id": return_id}, {"_id": 0})
    return serialize_doc(result)


@router.delete("/returns/{return_id}")
async def delete_return(return_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    doc = await db.wh_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(404, "Return tidak ditemukan")
    if doc.get("status") != "Pending":
        raise HTTPException(400, "Hanya return berstatus Pending yang bisa dihapus")
    await db.wh_returns.delete_one({"id": return_id})
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# WORKFLOW STEPS
# ═══════════════════════════════════════════════════════════════

@router.post("/returns/{return_id}/receive")
async def receive_return(return_id: str, request: Request):
    """
    Step 1: Tim Packing terima fisik barang.
    Input: unboxing_condition_notes, unboxing_photo_notes, package_condition
    """
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    doc = await db.wh_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(404, "Return tidak ditemukan")
    if doc["status"] != "Pending":
        raise HTTPException(400, f"Status saat ini '{doc['status']}' — harus Pending untuk di-receive")

    timeline_entry = {
        "status": "Received", "at": _now(), "by": user["name"],
        "note": body.get("unboxing_condition_notes", "Barang diterima dari ekspedisi")
    }
    upd = {
        "status": "Received",
        "received_at": _now(), "received_by": user["name"],
        "unboxing_condition_notes": body.get("unboxing_condition_notes", ""),
        "unboxing_photo_notes": body.get("unboxing_photo_notes", ""),
        "package_condition": body.get("package_condition", ""),
        "updated_at": _now()
    }
    await db.wh_returns.update_one({"id": return_id}, {
        "$set": upd, "$push": {"timeline": timeline_entry}
    })
    result = await db.wh_returns.find_one({"id": return_id}, {"_id": 0})
    return serialize_doc(result)


@router.post("/returns/{return_id}/inspect")
async def inspect_return(return_id: str, request: Request):
    """
    Step 2: Inspeksi kondisi item dan tentukan penyebab return.
    Input: item_condition, return_cause, cause_detail, recommended_action
    """
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    doc = await db.wh_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(404, "Return tidak ditemukan")
    if doc["status"] != "Received":
        raise HTTPException(400, f"Status saat ini '{doc['status']}' — harus Received untuk di-inspect")

    condition = body.get("item_condition", "")
    cause = body.get("return_cause", "")
    recommended = body.get("recommended_action", "")

    # Auto-recommend action berdasarkan penyebab
    if not recommended:
        if cause == "Kesalahan Gudang":
            recommended = "Reshipment"
        elif cause == "Kesalahan Customer":
            recommended = "Appeal Platform"
        elif cause == "Kesalahan Ekspedisi":
            recommended = "Reshipment"
        else:
            recommended = "Restock ke Gudang"

    timeline_entry = {
        "status": "Inspected", "at": _now(), "by": user["name"],
        "note": f"Kondisi: {condition} | Penyebab: {cause} | Rekomendasi: {recommended}"
    }
    upd = {
        "status": "Inspected",
        "inspected_at": _now(), "inspected_by": user["name"],
        "item_condition": condition,
        "return_cause": cause,
        "cause_detail": body.get("cause_detail", ""),
        "recommended_action": recommended,
        "updated_at": _now()
    }
    await db.wh_returns.update_one({"id": return_id}, {
        "$set": upd, "$push": {"timeline": timeline_entry}
    })
    result = await db.wh_returns.find_one({"id": return_id}, {"_id": 0})
    return serialize_doc(result)


@router.post("/returns/{return_id}/resolve")
async def resolve_return(return_id: str, request: Request):
    """
    Step 3: Eksekusi tindakan akhir.
    - Restock ke Gudang     → otomatis +1 ke inventory (rahaza_material_stock atau fg inventory)
    - Reshipment            → input resi baru
    - Appeal Platform       → update appeal_status
    - Dibuang / Dispose     → catat alasan
    """
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    doc = await db.wh_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(404, "Return tidak ditemukan")
    if doc["status"] != "Inspected":
        raise HTTPException(400, f"Status saat ini '{doc['status']}' — harus Inspected untuk di-resolve")

    action = body.get("action_taken", doc.get("recommended_action", ""))
    if not action:
        raise HTTPException(400, "action_taken wajib diisi")

    restock_qty = int(body.get("restock_qty", doc.get("qty", 1)) or 0)

    # Jika Restock ke Gudang — tambah ke fg_inventory
    if action == "Restock ke Gudang" and doc.get("sku_code"):
        fg_item = await db.rahaza_fg_inventory.find_one({"sku_code": doc["sku_code"]})
        if fg_item:
            await db.rahaza_fg_inventory.update_one(
                {"sku_code": doc["sku_code"]},
                {"$inc": {"total_qty": restock_qty}, "$set": {"updated_at": _now()}}
            )
            # Log movement
            await db.rahaza_fg_movements.insert_one({
                "id": _id(), "sku_code": doc["sku_code"],
                "movement_type": "IN", "qty": restock_qty,
                "source": "return_restock", "ref_id": return_id,
                "ref_number": doc["return_code"],
                "notes": f"Restock dari return {doc['return_code']}",
                "created_by": user["name"], "created_at": _now()
            })

    timeline_entry = {
        "status": "Resolved", "at": _now(), "by": user["name"],
        "note": f"Aksi: {action} | {body.get('action_notes', '')}"
    }
    upd = {
        "status": "Resolved",
        "resolved_at": _now(), "resolved_by": user["name"],
        "action_taken": action,
        "action_notes": body.get("action_notes", ""),
        "reshipment_resi": body.get("reshipment_resi", ""),
        "appeal_status": body.get("appeal_status", ""),
        "restock_qty": restock_qty,
        "updated_at": _now()
    }
    await db.wh_returns.update_one({"id": return_id}, {
        "$set": upd, "$push": {"timeline": timeline_entry}
    })

    # RC-FLOW-UX-11a (opsi B): callback ke marketing_returns bila retur ini
    # berasal dari retur Toko (link `source_marketing_return_id`). Update
    # `wh_return_status='Resolved'` supaya UI Marketing tahu barang sudah masuk
    # kembali & tombol "Terbitkan Credit Note" bisa jalan aman.
    src_mkt_id = doc.get("source_marketing_return_id")
    if src_mkt_id:
        # 2026-08-07 — DULU `except Exception: pass` dengan komentar
        # "Non-blocking: jangan gagalkan resolve karena callback marketing gagal".
        # Keputusan non-blocking-nya BENAR (barang sudah fisik masuk gudang; membatalkan
        # resolve akan lebih merusak). Yang salah: kegagalannya tak berjejak. Padahal
        # justru sinkronisasi INILAH yang membuka tombol "Terbitkan Credit Note" di
        # Marketing. Kalau gagal diam-diam, retur pelanggan MENGGANTUNG: barang sudah
        # diterima, uang/credit note tidak pernah terbit, dan tidak ada satu pun layar
        # yang menunjukkan kenapa. Sekarang: dicatat ERROR + DITANDAI di dokumen retur
        # gudang supaya bisa ditindak (lihat `mkt_sync_ok`).
        try:
            await db.marketing_returns.update_one(
                {"id": src_mkt_id},
                {"$set": {
                    "wh_return_status": "Resolved",
                    "wh_action_taken": action,
                    "wh_restock_qty": restock_qty,
                    "wh_resolved_at": _now(),
                    "updated_at": _now(),
                }}
            )
            await db.wh_returns.update_one(
                {"id": return_id},
                {"$set": {"mkt_sync_ok": True, "mkt_sync_error": "", "mkt_sync_at": _now()}})
        except Exception as e:  # noqa: BLE001
            logger.error(
                "[retur-gudang] GAGAL menyinkronkan retur %s ke Marketing (%s) — tombol "
                "'Terbitkan Credit Note' TIDAK akan aktif dan retur pelanggan menggantung. "
                "Perlu tindakan manual: %s", return_id, src_mkt_id, e)
            await db.wh_returns.update_one(
                {"id": return_id},
                {"$set": {"mkt_sync_ok": False, "mkt_sync_error": str(e)[:300],
                          "mkt_sync_at": _now()}})

    result = await db.wh_returns.find_one({"id": return_id}, {"_id": 0})
    return serialize_doc(result)


# ── Cancel ─────────────────────────────────────────────────────────────────

@router.post("/returns/{return_id}/cancel")
async def cancel_return(return_id: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    doc = await db.wh_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(404, "Return tidak ditemukan")
    if doc["status"] in ("Resolved", "Cancelled"):
        raise HTTPException(400, "Return sudah selesai atau dibatalkan")
    timeline_entry = {
        "status": "Cancelled", "at": _now(), "by": user["name"],
        "note": body.get("reason", "Dibatalkan")
    }
    await db.wh_returns.update_one({"id": return_id}, {
        "$set": {"status": "Cancelled", "updated_at": _now()},
        "$push": {"timeline": timeline_entry}
    })
    result = await db.wh_returns.find_one({"id": return_id}, {"_id": 0})
    return serialize_doc(result)
