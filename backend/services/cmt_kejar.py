"""
services/cmt_kejar.py — READ-ONLY agregasi "KEJAR CMT" + Dashboard Owner CMT.

Semua dihitung dari rantai SSOT (INVARIANTS MCS-01/03/04/05/06):
  production_pos/po_items · vendor_shipments/vendor_shipment_items · cmt_receipts/cmt_receipt_lines
  · dewi_cmt_permak · dewi_cmt_component_requests
TIDAK menulis koleksi apa pun. TIDAK membaca vendor_jobs/wh_cmt_dispatches (hindari split-brain).

Konsep:
- Target CMT (M4) = delivery_deadline − buffer_days (config maklon_cmt_buffer_days). Fallback: deadline internal.
- Bucket keterlambatan (S3): aman | on_track | mendekati | jatuh_tempo | telat(H+late_grace) | tanpa_deadline.
- Sisa di CMT (M5) = Σqty_sent(vendor_shipment_items) − Σqty_returned(cmt_receipt_lines approved).
- Kali setor (M5) = jumlah cmt_receipts Approved untuk PO.
- Ongkos jahit terhitung (M2) = Σ(cmt_price_snapshot × qty_accepted).
"""
from datetime import datetime, timezone, date
from typing import Dict, List, Any, Optional
import logging

from core.cmt_receipt_status import (ST_DONE as _RC_DONE,
                                    canon_status_filter as _rc_filter)

_log = logging.getLogger(__name__)

COMPONENT_OPEN_STATUSES = ("pending", "cutting", "ready")  # belum diterima


def _int(v) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return 0


def _to_date(v) -> Optional[date]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


async def get_buffer_config(db) -> Dict[str, int]:
    async def _c(key, default):
        try:
            d = await db.dewi_system_config.find_one({"key": key}, {"_id": 0, "value": 1})
            return int(d["value"]) if d and d.get("value") is not None else default
        except Exception:
            # F13 — buffer & tenggang inilah yang menentukan bucket "telat" di
            # papan KEJAR CMT. Diam-diam memakai default berarti seluruh papan
            # bisa memakai aturan yang bukan pilihan owner tanpa satu pun tanda.
            _log.warning("[cmt-kejar] config '%s' tidak terbaca — memakai default %s",
                         key, default, exc_info=True)
            return default
    return {
        "buffer_days": await _c("maklon_cmt_buffer_days", 3),
        "late_grace_days": await _c("maklon_cmt_late_grace_days", 5),
    }


async def _approved_receipt_ids(db, po_id: str) -> List[str]:
    docs = await db.cmt_receipts.find(
        {"po_id": po_id, "status": _rc_filter(_RC_DONE)}, {"_id": 0, "id": 1}
    ).to_list(None)
    return [d["id"] for d in docs if d.get("id")]


def _bucket(outstanding_cmt: int, target: Optional[date], today: date, late_grace: int) -> Dict[str, Any]:
    if outstanding_cmt <= 0:
        return {"bucket": "aman", "overdue_days": 0, "days_to_target": None}
    if target is None:
        return {"bucket": "tanpa_deadline", "overdue_days": None, "days_to_target": None}
    overdue = (today - target).days
    to_target = (target - today).days
    if overdue > late_grace:
        b = "telat"
    elif overdue >= 0:
        b = "jatuh_tempo"
    elif to_target <= 3:
        b = "mendekati"
    else:
        b = "on_track"
    return {"bucket": b, "overdue_days": overdue, "days_to_target": to_target}


async def compute_po_kejar(db, po: Dict[str, Any], cfg: Dict[str, int], today: date = None) -> Dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    po_id = po["id"]
    items = await db.po_items.find({"po_id": po_id}, {"_id": 0}).to_list(None)
    item_ids = [i["id"] for i in items]
    price_by_item = {i["id"]: float(i.get("cmt_price_snapshot", 0) or 0) for i in items}
    qty_ordered = sum(_int(i.get("qty")) for i in items)

    # Sent to CMT (potongan dikirim) — vendor_shipment_items.qty_sent
    sent_cmt = 0
    dispatch_dates: List[date] = []
    if item_ids:
        vsi = await db.vendor_shipment_items.find(
            {"po_item_id": {"$in": item_ids}}, {"_id": 0, "qty_sent": 1, "shipment_id": 1}
        ).to_list(None)
        sent_cmt = sum(_int(v.get("qty_sent")) for v in vsi)
        ship_ids = list({v.get("shipment_id") for v in vsi if v.get("shipment_id")})
        if ship_ids:
            ships = await db.vendor_shipments.find(
                {"id": {"$in": ship_ids}}, {"_id": 0, "shipment_date": 1}
            ).to_list(None)
            for s in ships:
                d = _to_date(s.get("shipment_date"))
                if d:
                    dispatch_dates.append(d)

    # Returned + accepted from Approved receipts
    returned = accepted = 0
    accepted_by_item: Dict[str, int] = {}
    approved_ids = await _approved_receipt_ids(db, po_id)
    kali_setor = len(approved_ids)
    if approved_ids and item_ids:
        lines = await db.cmt_receipt_lines.find(
            {"receipt_id": {"$in": approved_ids}, "po_item_id": {"$in": item_ids}},
            {"_id": 0, "po_item_id": 1, "qty_shipped_by_cmt": 1, "qty_actual": 1},
        ).to_list(None)
        for ln in lines:
            returned += _int(ln.get("qty_shipped_by_cmt"))
            a = _int(ln.get("qty_actual"))
            accepted += a
            accepted_by_item[ln["po_item_id"]] = accepted_by_item.get(ln["po_item_id"], 0) + a

    outstanding_cmt = max(0, sent_cmt - returned)
    ongkos_jahit = round(sum(price_by_item.get(iid, 0) * q for iid, q in accepted_by_item.items()), 2)

    delivery_deadline = _to_date(po.get("delivery_deadline"))   # Deadline Mitra/Buyer
    internal_deadline = _to_date(po.get("deadline"))
    base_deadline = delivery_deadline or internal_deadline
    target_cmt = None
    if base_deadline:
        from datetime import timedelta
        target_cmt = base_deadline - timedelta(days=cfg["buffer_days"])

    b = _bucket(outstanding_cmt, target_cmt, today, cfg["late_grace_days"])
    earliest_dispatch = min(dispatch_dates) if dispatch_dates else None
    days_at_cmt = (today - earliest_dispatch).days if (earliest_dispatch and outstanding_cmt > 0) else None

    return {
        "po_id": po_id,
        "po_number": po.get("po_number", ""),
        "customer_name": po.get("customer_name", ""),
        "status": po.get("status", ""),
        "qty_ordered": qty_ordered,
        "qty_sent_cmt": sent_cmt,
        "qty_returned": returned,
        "qty_accepted": accepted,
        "qty_outstanding_cmt": outstanding_cmt,   # sisa di CMT
        "kali_setor": kali_setor,
        "ongkos_jahit_terhitung": ongkos_jahit,
        "delivery_deadline": delivery_deadline.isoformat() if delivery_deadline else None,
        "internal_deadline": internal_deadline.isoformat() if internal_deadline else None,
        "target_cmt_date": target_cmt.isoformat() if target_cmt else None,
        "earliest_dispatch_date": earliest_dispatch.isoformat() if earliest_dispatch else None,
        "days_at_cmt": days_at_cmt,
        **b,
    }


async def _maklon_pos(db, only_open: bool = True) -> List[Dict[str, Any]]:
    q = {"business_type": "maklon"}
    if only_open:
        q["status"] = {"$nin": ["Closed", "Cancelled", "Selesai", "closed", "cancelled"]}
    return await db.production_pos.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


async def list_kejar(db, bucket: Optional[str] = None, only_open: bool = True) -> Dict[str, Any]:
    cfg = await get_buffer_config(db)
    today = datetime.now(timezone.utc).date()
    pos = await _maklon_pos(db, only_open)
    rows = []
    for po in pos:
        r = await compute_po_kejar(db, po, cfg, today)
        if bucket and r["bucket"] != bucket:
            continue
        rows.append(r)
    order = {"telat": 0, "jatuh_tempo": 1, "mendekati": 2, "on_track": 3, "tanpa_deadline": 4, "aman": 5}
    rows.sort(key=lambda r: (order.get(r["bucket"], 9), -(r["overdue_days"] or -999)))
    return {"config": cfg, "count": len(rows), "rows": rows}


async def owner_dashboard(db) -> Dict[str, Any]:
    """M2 — KPI Dashboard Owner CMT (agregasi seluruh PO maklon aktif)."""
    cfg = await get_buffer_config(db)
    today = datetime.now(timezone.utc).date()
    pos = await _maklon_pos(db, only_open=True)

    agg = {
        "total_po": len(pos),
        "qty_ordered": 0, "qty_sent_cmt": 0, "qty_returned": 0, "qty_accepted": 0,
        "qty_outstanding_cmt": 0, "kali_setor": 0, "ongkos_jahit_terhitung": 0.0,
        "buckets": {"telat": 0, "jatuh_tempo": 0, "mendekati": 0, "on_track": 0, "aman": 0, "tanpa_deadline": 0},
        "telat_pos": [],
    }
    for po in pos:
        r = await compute_po_kejar(db, po, cfg, today)
        agg["qty_ordered"] += r["qty_ordered"]
        agg["qty_sent_cmt"] += r["qty_sent_cmt"]
        agg["qty_returned"] += r["qty_returned"]
        agg["qty_accepted"] += r["qty_accepted"]
        agg["qty_outstanding_cmt"] += r["qty_outstanding_cmt"]
        agg["kali_setor"] += r["kali_setor"]
        agg["ongkos_jahit_terhitung"] += r["ongkos_jahit_terhitung"]
        agg["buckets"][r["bucket"]] = agg["buckets"].get(r["bucket"], 0) + 1
        if r["bucket"] == "telat":
            agg["telat_pos"].append({
                "po_id": r["po_id"], "po_number": r["po_number"], "customer_name": r["customer_name"],
                "overdue_days": r["overdue_days"], "qty_outstanding_cmt": r["qty_outstanding_cmt"],
                "target_cmt_date": r["target_cmt_date"],
            })
    agg["ongkos_jahit_terhitung"] = round(agg["ongkos_jahit_terhitung"], 2)

    # Komponen kurang (aksesoris) belum diterima
    comp = await db.dewi_cmt_component_requests.find(
        {"status": {"$in": list(COMPONENT_OPEN_STATUSES)}}, {"_id": 0}
    ).to_list(None)
    comp_qty = 0
    for c in comp:
        for it in (c.get("items") or []):
            comp_qty += _int(it.get("qty"))
    agg["komponen_kurang_open"] = {"requests": len(comp), "qty": comp_qty}

    # Biaya permak + permak aktif
    permaks = await db.dewi_cmt_permak.find({}, {"_id": 0}).to_list(None)
    biaya_permak = round(sum(float(p.get("total_cost") or 0) for p in permaks), 2)
    permak_open = sum(1 for p in permaks if p.get("status") in ("open", "in_progress"))
    agg["biaya_permak"] = biaya_permak
    agg["permak_open"] = permak_open

    agg["config"] = cfg
    return agg
