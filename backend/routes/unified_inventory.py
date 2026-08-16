"""
CV. Dewi Aditya — Unified Inventory Viewer (Phase 2 Enhancement)

Endpoint terpadu untuk melihat dan mengelola seluruh stok internal:
  • Raw Material (Bahan Baku)
  • WIP Internal (Work In Progress)
  • FG Internal (Finished Goods)
  • Maklon WIP / FG (milik klien Maklon)

Sumber data: collection `rahaza_material_stock`
  Field utama: material_id, material_name, material_code, inventory_category, ownership,
               quantity, available_quantity, reserved_quantity, location, unit, reorder_point

Endpoints (prefix /api/wms):
  - GET  /stock/unified                    → filter by category/ownership/search
  - GET  /stock/unified/summary            → ringkasan statistik
  - POST /stock/unified/adjust             → manual adjustment (opname)
  - GET  /stock/unified/adjustments        → riwayat adjustment

Adjustments dicatat ke koleksi: rahaza_material_movements (movement_type=ADJUST)
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import logging

from database import get_db
from auth import require_auth, serialize_doc, log_activity
from pymongo import ReturnDocument

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wms", tags=["unified-inventory"])


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


CATEGORIES = ["raw_material", "wip_internal", "fg_internal", "maklon_wip", "maklon_fg"]
OWNERSHIPS = ["cv_da", "maklon", "maklon_client"]


# ── Pydantic Models ────────────────────────────────────────────────────────────

class StockAdjustIn(BaseModel):
    material_id: str = Field(..., description="ID material/SKU pada rahaza_material_stock")
    adjustment_type: str = Field(..., description="opname_increase | opname_decrease | correction | damage")
    qty_delta: float = Field(..., description="Selisih (boleh negatif). Misal opname temukan kelebihan 5 → 5; jika kurang 3 → -3")
    reason: str = Field(..., min_length=3, description="Alasan/keterangan adjustment")
    reference_no: Optional[str] = Field(default=None, description="Nomor berita acara / referensi dokumen")


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _require_admin(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin", "owner", "warehouse_manager", "inventory_admin"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "inventory.manage" in perms or "warehouse.manage" in perms:
        return user
    raise HTTPException(403, "Butuh permission inventory / warehouse untuk adjustment.")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/stock/unified")
async def list_unified_stock(
    request: Request,
    inventory_category: Optional[str] = None,
    ownership: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    user: dict = Depends(require_auth),
):
    """
    List semua stok dari rahaza_material_stock dengan filter terpadu + pagination.
    Query: page (1-based), limit (default 50, max 500)
    Response: { items, total, page, limit, total_pages, has_next, has_prev, filters_applied }
    """
    db = get_db()
    page = max(1, int(page))
    limit = max(1, min(500, int(limit)))
    skip = (page - 1) * limit

    query: dict = {}

    if inventory_category and inventory_category != "all":
        query["inventory_category"] = inventory_category
    if ownership and ownership != "all":
        if ownership == "maklon":
            query["ownership"] = {"$in": ["maklon", "maklon_client"]}
        else:
            query["ownership"] = ownership
    if search:
        query["$or"] = [
            {"material_id": {"$regex": search, "$options": "i"}},
            {"material_name": {"$regex": search, "$options": "i"}},
            {"material_code": {"$regex": search, "$options": "i"}},
        ]

    # Total count untuk pagination
    total = await db.rahaza_material_stock.count_documents(query)
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    cursor = (
        db.rahaza_material_stock
        .find(query, {"_id": 0})
        .sort("material_name", 1)
        .skip(skip)
        .limit(limit)
    )
    items: List[dict] = []
    async for row in cursor:
        row.setdefault("quantity", row.get("qty", 0))
        row.setdefault("available_quantity", row.get("quantity", row.get("qty", 0)))
        row.setdefault("reserved_quantity", 0)
        row.setdefault("ownership", "cv_da")
        row.setdefault("inventory_category", "raw_material")
        items.append(serialize_doc(row))

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "filters_applied": {
            "inventory_category": inventory_category,
            "ownership": ownership,
            "search": search,
        },
    }


@router.get("/stock/unified/summary")
async def unified_stock_summary(user: dict = Depends(require_auth)):
    """
    Ringkasan total stok per category & ownership.
    """
    db = get_db()
    pipe_cat = [
        {"$group": {
            "_id": "$inventory_category",
            "total_qty": {"$sum": {"$ifNull": ["$quantity", {"$ifNull": ["$qty", 0]}]}},
            "total_available": {"$sum": {"$ifNull": ["$available_quantity", 0]}},
            "total_reserved": {"$sum": {"$ifNull": ["$reserved_quantity", 0]}},
            "row_count": {"$sum": 1},
        }},
    ]
    by_category = await db.rahaza_material_stock.aggregate(pipe_cat).to_list(50)

    pipe_own = [
        {"$group": {
            "_id": "$ownership",
            "total_qty": {"$sum": {"$ifNull": ["$quantity", {"$ifNull": ["$qty", 0]}]}},
            "row_count": {"$sum": 1},
        }},
    ]
    by_ownership = await db.rahaza_material_stock.aggregate(pipe_own).to_list(50)

    # Low stock: available_quantity < reorder_point (atau <10 default)
    low_stock = await db.rahaza_material_stock.count_documents({
        "$expr": {"$lt": ["$available_quantity", {"$ifNull": ["$reorder_point", 10]}]}
    })

    return {
        "by_category": [
            {"category": (r["_id"] or "uncategorized"), **{k: v for k, v in r.items() if k != "_id"}}
            for r in by_category
        ],
        "by_ownership": [
            {"ownership": (r["_id"] or "unknown"), **{k: v for k, v in r.items() if k != "_id"}}
            for r in by_ownership
        ],
        "low_stock_count": low_stock,
    }


@router.post("/stock/unified/adjust")
async def adjust_stock(payload: StockAdjustIn, request: Request):
    """
    Manual adjustment (stock opname / koreksi).
    Mengupdate quantity & available_quantity pada rahaza_material_stock + log ke rahaza_material_movements.
    """
    user = await _require_admin(request)
    db = get_db()

    stock = await db.rahaza_material_stock.find_one({"material_id": payload.material_id})
    if not stock:
        raise HTTPException(404, f"Stock untuk material {payload.material_id} tidak ditemukan")

    qty_before = float(stock.get("quantity", stock.get("qty", 0)))
    available_before = float(stock.get("available_quantity", qty_before))

    # Enforce sign based on adjustment_type at backend for safety
    raw = float(payload.qty_delta)
    if payload.adjustment_type in ("opname_decrease", "damage"):
        signed_delta = -abs(raw)
    elif payload.adjustment_type == "opname_increase":
        signed_delta = abs(raw)
    else:  # correction — gunakan sign apa adanya
        signed_delta = raw

    # ── R10 concurrency hardening (TOCTOU-safe): guard non-negativity INSIDE the
    # filter ($expr) and apply the delta atomically via an aggregation pipeline.
    # Prevents lost-update / negative stock under parallel adjustments (CC6).
    _q = {"$ifNull": ["$quantity", {"$ifNull": ["$qty", 0]}]}
    _a = {"$ifNull": ["$available_quantity", {"$ifNull": ["$quantity", {"$ifNull": ["$qty", 0]}]}]}
    updated = await db.rahaza_material_stock.find_one_and_update(
        {
            "id": stock["id"],
            "$expr": {"$and": [
                {"$gte": [{"$add": [_q, signed_delta]}, 0]},
                {"$gte": [{"$add": [_a, signed_delta]}, 0]},
            ]},
        },
        [{"$set": {
            "quantity": {"$add": [_q, signed_delta]},
            "qty": {"$add": [_q, signed_delta]},
            "available_quantity": {"$add": [_a, signed_delta]},
            "updated_at": _now(),
        }}],
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(400, "Adjustment tidak valid: qty/available akan menjadi negatif (kemungkinan race concurrent adjust).")

    # Derive from the authoritative post-update doc for an accurate movement log.
    new_qty = float(updated.get("quantity", updated.get("qty", 0)))
    qty_before = new_qty - signed_delta

    # Log movement
    movement = {
        "id": _uid(),
        "material_id": payload.material_id,
        "movement_type": "ADJUST",
        "quantity": signed_delta,
        "qty_before": qty_before,
        "qty_after": new_qty,
        "adjustment_type": payload.adjustment_type,
        "reason": payload.reason,
        "reference_no": payload.reference_no,
        "source_module": "unified-inventory",
        "performed_by": user.get("email") or user.get("id"),
        "performed_by_name": user.get("name"),
        "created_at": _now(),
        "notes": f"{payload.adjustment_type}: {payload.reason}" + (f" (ref: {payload.reference_no})" if payload.reference_no else ""),
    }
    await db.rahaza_material_movements.insert_one(movement)

    try:
        await log_activity(
            user_id=user.get("id") or user.get("email"),
            user_name=user.get("name") or user.get("email", "system"),
            action="stock_adjust",
            module="unified-inventory",
            details=f"material={payload.material_id} delta={payload.qty_delta} reason={payload.reason}"
        )
    except Exception as e:
        logger.warning(f"log_activity failed: {e}")

    return {
        "status": "ok",
        "material_id": payload.material_id,
        "qty_before": qty_before,
        "qty_after": new_qty,
        "delta": signed_delta,
        "movement_id": movement["id"],
    }


@router.get("/stock/unified/adjustments")
async def list_adjustments(
    material_id: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(require_auth),
):
    """Riwayat semua adjustment manual (opname / koreksi)."""
    db = get_db()
    q: dict = {"movement_type": "ADJUST"}
    if material_id:
        q["material_id"] = material_id

    cursor = db.rahaza_material_movements.find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    items = [serialize_doc(row) async for row in cursor]
    return {"items": items, "total": len(items)}
