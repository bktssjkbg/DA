"""rahaza_inventory — Material Issues CRUD + draft-from-wo + approval workflow."""
# ruff: noqa: E741
from fastapi import Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity  # noqa: F401
from typing import Optional
from routes.rahaza_inventory_shared import (
    router, log, _uid, _now, _require_admin,  # noqa: F401
    _require_mi_editor,
    _gen_mi_number, _enrich_mi, _norm_mi_items, _require_mi_approver,
    _log_movement,
)
from routes.rahaza_posting import post_inventory_issue


@router.get("/material-issues")
async def list_mis(request: Request, work_order_id: Optional[str] = None,
                   status: Optional[str] = None, building_id: Optional[str] = None,
                   limit: int = 200, skip: int = 0):
    await require_auth(request)
    db = get_db()
    q = {}
    if work_order_id:
        q["work_order_id"] = work_order_id
    if status:
        q["status"] = status
    if building_id:
        pending_ids = await db.wh_pending_movements.distinct(
            "source_id",
            {"type": "outbound_rm", "source_type": "rahaza_material_issue", "building_id": building_id}
        )
        q["id"] = {"$in": pending_ids or ["__none__"]}
    rows = await db.rahaza_material_issues.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(500)
    for mi in rows:
        await _enrich_mi(db, mi)
        mi["item_count"] = len(mi.get("items") or [])
        mi["total_required"] = round(sum(float(i.get("qty_required") or 0) for i in (mi.get("items") or [])), 4)
    return serialize_doc(rows)


@router.get("/material-issues/{mid}")
async def get_mi(mid: str, request: Request):
    await require_auth(request)
    db = get_db()
    mi = await db.rahaza_material_issues.find_one({"id": mid}, {"_id": 0})
    if not mi:
        raise HTTPException(404, "MI tidak ditemukan.")
    await _enrich_mi(db, mi)
    return serialize_doc(mi)


# FASE 4 (E10 GDG-2): endpoint draft-from-wo DIHAPUS — diganti draft-from-job
# (auto-generate MI saat job dibuat, lihat production_internal_adapter.py).

@router.post("/material-issues")
async def create_mi_manual(request: Request):
    user = await _require_mi_editor(request)
    db = get_db()
    body = await request.json()
    _raw_items = body.get("items") or []
    _mids = [i.get("material_id") for i in _raw_items if i.get("material_id")]
    _mats = {}
    if any(i.get("qty_uom") for i in _raw_items) and _mids:
        async for _m in db.rahaza_materials.find({"id": {"$in": _mids}}, {"_id": 0}):
            _mats[_m["id"]] = _m
    try:
        items = _norm_mi_items(_raw_items, _mats)
    except Exception as e:  # UomError → 400, bukan 500
        raise HTTPException(400, f"Satuan tidak valid: {e}")
    if not items:
        raise HTTPException(400, "Minimal 1 item material.")
    doc = {
        "id": _uid(),
        "mi_number": await _gen_mi_number(db),
        "work_order_id": body.get("work_order_id") or None,
        "wo_number_snapshot": body.get("wo_number_snapshot") or "",
        "model_id": body.get("model_id") or None,
        "size_id":  body.get("size_id") or None,
        "qty_wo_pcs": int(body.get("qty_wo_pcs") or 0),
        "items": items, "status": "draft",
        "notes": body.get("notes") or "",
        "created_by": user["id"], "created_by_name": user.get("name", ""),
        "created_at": _now(), "updated_at": _now(),
    }
    await db.rahaza_material_issues.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.mi", doc["mi_number"])
    await _enrich_mi(db, doc)
    return serialize_doc(doc)


@router.put("/material-issues/{mid}")
async def update_mi(mid: str, request: Request):
    await _require_mi_editor(request)
    db = get_db()
    mi = await db.rahaza_material_issues.find_one({"id": mid}, {"_id": 0})
    if not mi:
        raise HTTPException(404, "MI tidak ditemukan.")
    if mi.get("status") != "draft":
        raise HTTPException(400, "Hanya MI Draft yang bisa diedit.")
    body = await request.json()
    upd = {"updated_at": _now()}
    if "items" in body:
        # 2026-08-05 (BUG): dulu `_norm_mi_items` dipanggil TANPA peta master
        # material, sehingga `qty_uom` pada PUT diabaikan diam-diam (qty dianggap
        # satuan dasar). Sekarang sama dengan jalur POST.
        _raw_items = body.get("items") or []
        _mids = [i.get("material_id") for i in _raw_items if i.get("material_id")]
        _mats = {}
        if any(i.get("qty_uom") for i in _raw_items) and _mids:
            async for _m in db.rahaza_materials.find({"id": {"$in": _mids}}, {"_id": 0}):
                _mats[_m["id"]] = _m
        try:
            items = _norm_mi_items(_raw_items, _mats)
        except Exception as e:  # UomError → 400, bukan 500
            raise HTTPException(400, f"Satuan tidak valid: {e}")
        if not items:
            raise HTTPException(400, "Minimal 1 item material.")
        upd["items"] = items
    if "notes" in body:
        upd["notes"] = body["notes"]
    await db.rahaza_material_issues.update_one({"id": mid}, {"$set": upd})
    out = await db.rahaza_material_issues.find_one({"id": mid}, {"_id": 0})
    await _enrich_mi(db, out)
    return serialize_doc(out)


@router.post("/material-issues/{mid}/submit")
async def submit_mi(mid: str, request: Request):
    user = await _require_mi_editor(request)
    db = get_db()
    mi = await db.rahaza_material_issues.find_one({"id": mid}, {"_id": 0})
    if not mi:
        raise HTTPException(404, "MI tidak ditemukan.")
    if mi.get("status") not in ("draft", "rejected"):
        raise HTTPException(400, f"Hanya MI Draft/Rejected yang bisa diajukan. Status: {mi.get('status')}")
    missing = [it for it in (mi.get("items") or []) if not it.get("location_id")]
    if missing:
        raise HTTPException(400, f"{len(missing)} item belum punya lokasi. Set lokasi dulu sebelum submit.")
    await db.rahaza_material_issues.update_one(
        {"id": mid},
        {"$set": {"status": "pending_approval", "submitted_at": _now(), "submitted_by": user["id"], "updated_at": _now()}}
    )
    await log_activity(user["id"], user.get("name", ""), "submit", "rahaza.mi", mi["mi_number"])
    out = await db.rahaza_material_issues.find_one({"id": mid}, {"_id": 0})
    await _enrich_mi(db, out)
    return serialize_doc(out)


@router.post("/material-issues/{mid}/approve")
async def approve_mi(mid: str, request: Request):
    user = await _require_mi_approver(request)
    db = get_db()
    mi = await db.rahaza_material_issues.find_one({"id": mid}, {"_id": 0})
    if not mi:
        raise HTTPException(404, "MI tidak ditemukan.")
    if mi.get("status") != "pending_approval":
        raise HTTPException(400, f"Hanya MI Pending Approval yang bisa di-approve. Status: {mi.get('status')}")
    await db.rahaza_material_issues.update_one(
        {"id": mid},
        {"$set": {"approved_at": _now(), "approved_by": user["id"], "approved_by_name": user.get("name", ""), "updated_at": _now()}}
    )
    try:
        body = await request.json()
    except Exception:
        body = {}
    # ── FASE H-1 (2026-08-15) — INTI PENGELUARAN DIPINDAH KE SATU MESIN ───────
    # Isi fungsi ini (validasi stok per lokasi → `stock_service.issue()` atomik →
    # catat movement → posting jurnal) DIEKSTRAK ke `core.material_issue_engine`
    # supaya "mengeluarkan material dari gudang" punya SATU definisi. Alasannya
    # bukan kerapian: "Kirim Material CMT" kini menerbitkan MI otomatis, dan
    # kalau ia menyalin logikanya sendiri kita akan punya DUA cara memotong stok
    # yang bisa berbeda diam-diam — cacat yang persis sama seperti tiga rumus
    # kapasitas kirim di Fase E.
    from core import material_issue_engine as mie
    try:
        out = await mie.issue_material_issue(
            db, mi, user, loc_overrides=body.get("location_overrides") or {})
    except mie.MaterialShortage as e:
        raise HTTPException(400, {"message": "Stok tidak cukup untuk issue.",
                                  "shortages": e.shortages})
    except mie.BomMissing as e:
        raise HTTPException(400, str(e))
    await log_activity(user["id"], user.get("name", ""), "approve+issue", "rahaza.mi", mi["mi_number"])
    return serialize_doc(out)


@router.post("/material-issues/{mid}/reject")
async def reject_mi(mid: str, request: Request):
    user = await _require_mi_approver(request)
    db = get_db()
    body = await request.json()
    reason = body.get("reason") or "Tidak ada alasan"
    mi = await db.rahaza_material_issues.find_one({"id": mid}, {"_id": 0})
    if not mi:
        raise HTTPException(404, "MI tidak ditemukan.")
    if mi.get("status") != "pending_approval":
        raise HTTPException(400, f"Hanya MI Pending Approval yang bisa di-reject. Status: {mi.get('status')}")
    await db.rahaza_material_issues.update_one(
        {"id": mid},
        {"$set": {"status": "rejected", "rejected_at": _now(), "rejected_by": user["id"],
                 "rejected_by_name": user.get("name", ""), "rejected_reason": reason, "updated_at": _now()}}
    )
    await log_activity(user["id"], user.get("name", ""), f"reject:{reason}", "rahaza.mi", mi["mi_number"])
    out = await db.rahaza_material_issues.find_one({"id": mid}, {"_id": 0})
    await _enrich_mi(db, out)
    return serialize_doc(out)
