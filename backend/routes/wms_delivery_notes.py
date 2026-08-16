"""
WMS — Surat Jalan / Delivery Note (P0-WH-2)
CV. Dewi Aditya — Dokumen pengiriman legal

Tipe:
  SJ-CMT      : kirim kain + aksesoris ke CMT (link ke WO)
  SJ-MAKLON   : kirim barang jadi ke klien maklon
  SJ-SUPPLIER : retur kain/material ke supplier
  SJ-INTERNAL : transfer antar gedung/lokasi internal
  SJ-ONLINE   : pengiriman online shop (batch resi)

Collection: wh_delivery_notes
  id, sj_number (SJ/2026/05/0001), sj_type, status (draft|issued|received|cancelled),
  recipient_name, recipient_address, recipient_phone,
  shipper_name, vehicle_no, notes,
  issued_at, received_at, cancelled_at,
  lines: [{line_no, description, qty, unit, remarks}]
  created_at, created_by, updated_at, updated_by

Endpoints (prefix /api/wms/delivery-notes):
  GET    /                    list + filter
  POST   /                    create draft SJ
  GET    /{sj_id}             detail
  PUT    /{sj_id}             update draft
  DELETE /{sj_id}             delete draft
  POST   /{sj_id}/issue       issue (dari draft → issued, generate PDF)
  POST   /{sj_id}/receive     mark as received (buyer scan/acknowledge)
  POST   /{sj_id}/cancel      cancel
  GET    /{sj_id}/pdf         download PDF
"""
# ruff: noqa: F401
import uuid
import io
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from database import get_db
from utils.counters import gen_prefixed_number
from auth import require_auth, serialize_doc, verify_token_str
from utils.pdf_common import get_company_profile, get_doc_settings, resolve_signature_name
import logging

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wms/delivery-notes", tags=["wms-delivery-notes"])

SJ_TYPES = ["SJ-CMT", "SJ-MAKLON", "SJ-SUPPLIER", "SJ-INTERNAL", "SJ-ONLINE"]
SJ_STATUSES = ["draft", "issued", "received", "cancelled"]


def _now(): return datetime.now(timezone.utc)
def _id(): return str(uuid.uuid4())


class SJLine(BaseModel):
    description: str = Field(..., min_length=1)
    qty: float = Field(..., gt=0)
    unit: str = "pcs"
    remarks: str = ""
    roll_no: str = ""  # optional link to fabric roll
    material_code: str = ""


class SJIn(BaseModel):
    sj_type: str
    recipient_name: str = Field(..., min_length=1)
    recipient_address: str = ""
    recipient_phone: str = ""
    shipper_name: str = ""
    vehicle_no: str = ""
    notes: str = ""
    reference_type: str = ""   # wo, maklon_order, po
    reference_id: str = ""
    reference_no: str = ""
    lines: List[SJLine] = []


class IssueIn(BaseModel):
    shipper_name: str = ""
    vehicle_no: str = ""
    notes: str = ""


class ReceiveIn(BaseModel):
    received_by: str = ""
    notes: str = ""


class CancelIn(BaseModel):
    reason: str = ""


async def _next_sj_number(db, sj_type: str) -> str:
    prefix = f"{sj_type}/{_now().strftime('%Y/%m')}/"
    # RC-5 fix: atomic race-safe numbering (was count_documents()+1 -> dup/E11000)
    return await gen_prefixed_number(db, "wh_delivery_notes", "sj_number", prefix, 4,
                                     ctx={"TIPE": sj_type})


@router.get("")
async def list_sj(
    request: Request,
    sj_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    await require_auth(request)
    db = get_db()
    q = {}
    if sj_type:
        q["sj_type"] = sj_type
    if status:
        q["status"] = status
    if search:
        q["$or"] = [
            {"sj_number": {"$regex": search, "$options": "i"}},
            {"recipient_name": {"$regex": search, "$options": "i"}},
            {"reference_no": {"$regex": search, "$options": "i"}},
        ]
    total = await db.wh_delivery_notes.count_documents(q)
    skip = (page - 1) * limit
    items = await db.wh_delivery_notes.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {
        "items": [serialize_doc(i) for i in items],
        "pagination": {
            "page": page, "limit": limit, "total": total,
            "total_pages": max(1, (total + limit - 1) // limit),
            "has_next": (skip + limit) < total,
            "has_prev": page > 1,
        }
    }


@router.post("")
async def create_sj(data: SJIn, request: Request):
    user = await require_auth(request)
    db = get_db()
    if data.sj_type not in SJ_TYPES:
        raise HTTPException(400, f"sj_type harus salah satu dari {SJ_TYPES}")
    sj_id = _id()
    now = _now()
    sj_number = await _next_sj_number(db, data.sj_type)
    lines = [{"line_no": i + 1, **line.dict()} for i, line in enumerate(data.lines)]
    doc = {
        "id": sj_id,
        "sj_number": sj_number,
        "sj_type": data.sj_type,
        "status": "draft",
        "recipient_name": data.recipient_name,
        "recipient_address": data.recipient_address,
        "recipient_phone": data.recipient_phone,
        "shipper_name": data.shipper_name,
        "vehicle_no": data.vehicle_no,
        "notes": data.notes,
        "reference_type": data.reference_type,
        "reference_id": data.reference_id,
        "reference_no": data.reference_no,
        "lines": lines,
        "issued_at": None, "received_at": None, "cancelled_at": None,
        "created_at": now,
        "created_by": user.get("name", user["id"]),
        "updated_at": now,
        "updated_by": user.get("name", user["id"]),
    }
    await db.wh_delivery_notes.insert_one(doc)
    out = await db.wh_delivery_notes.find_one({"id": sj_id}, {"_id": 0})
    return {"ok": True, "sj": serialize_doc(out)}


@router.get("/{sj_id}")
async def get_sj(sj_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    sj = await db.wh_delivery_notes.find_one({"$or": [{"id": sj_id}, {"sj_number": sj_id}]}, {"_id": 0})
    if not sj:
        raise HTTPException(404, "Surat Jalan tidak ditemukan")
    return serialize_doc(sj)


@router.put("/{sj_id}")
async def update_sj(sj_id: str, data: dict, request: Request):
    user = await require_auth(request)
    db = get_db()
    sj = await db.wh_delivery_notes.find_one({"id": sj_id})
    if not sj:
        raise HTTPException(404, "Surat Jalan tidak ditemukan")
    if sj["status"] != "draft":
        raise HTTPException(400, "Hanya draft Surat Jalan yang dapat diupdate")
    allowed = {"recipient_name", "recipient_address", "recipient_phone", "shipper_name",
               "vehicle_no", "notes", "lines", "reference_type", "reference_id", "reference_no"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if "lines" in updates:
        updates["lines"] = [{"line_no": i + 1, **ln} for i, ln in enumerate(updates["lines"])]
    updates["updated_at"] = _now()
    updates["updated_by"] = user.get("name", user["id"])
    await db.wh_delivery_notes.update_one({"id": sj_id}, {"$set": updates})
    out = await db.wh_delivery_notes.find_one({"id": sj_id}, {"_id": 0})
    return {"ok": True, "sj": serialize_doc(out)}


@router.post("/{sj_id}/issue")
async def issue_sj(sj_id: str, data: IssueIn, request: Request):
    user = await require_auth(request)
    db = get_db()
    sj = await db.wh_delivery_notes.find_one({"id": sj_id})
    if not sj:
        raise HTTPException(404, "Surat Jalan tidak ditemukan")
    if sj["status"] != "draft":
        raise HTTPException(400, "Hanya draft yang dapat di-issue")
    if not sj.get("lines"):
        raise HTTPException(400, "Surat Jalan harus memiliki minimal 1 item")
    updates = {
        "status": "issued",
        "issued_at": _now(),
        "updated_at": _now(),
        "updated_by": user.get("name", user["id"]),
    }
    if data.shipper_name:
        updates["shipper_name"] = data.shipper_name
    if data.vehicle_no:
        updates["vehicle_no"] = data.vehicle_no
    if data.notes:
        updates["notes"] = (sj.get("notes", "") + " " + data.notes).strip()
    await db.wh_delivery_notes.update_one({"id": sj_id}, {"$set": updates})

    # WS-E: SJ-INTERNAL → buat PENDING OUTBOUND_RM (best-effort resolve material_code).
    # Stok BELUM turun; gudang wajib Scan-Out di WMS. Baris yang tak ter-resolve → dokumen saja.
    pendings = []
    if sj.get("sj_type") == "SJ-INTERNAL":
        try:
            from routes.wms_receiving import helper_create_pending_outbound_rm
            for ln in sj.get("lines", []):
                code = (ln.get("material_code") or "").strip()
                if not code:
                    continue
                mat = await db.rahaza_materials.find_one({"code": code}, {"_id": 0})
                if not mat:
                    continue  # tak ter-resolve → tak sentuh stok
                pending = await helper_create_pending_outbound_rm(
                    db,
                    material_id=mat.get("id"),
                    material_code=code,
                    material_name=mat.get("name", ln.get("description", "")),
                    qty=float(ln.get("qty", 0) or 0),
                    unit=ln.get("unit", "pcs"),
                    source_type="delivery_note",
                    source_id=sj_id,
                    source_ref=sj.get("sj_number", ""),
                    notes=f"SJ Internal {sj.get('sj_number','')} — Scan-Out diperlukan",
                    created_by=user.get("email", user.get("name", "system")),
                )
                pendings.append({"pending_id": pending.get("id"), "ref_number": pending.get("ref_number"),
                                 "material_name": mat.get("name", ""), "qty": ln.get("qty", 0)})
            if pendings:
                await db.wh_delivery_notes.update_one(
                    {"id": sj_id},
                    {"$set": {"wms_pending_refs": [p["ref_number"] for p in pendings]}}
                )
        except Exception as e:
            log.warning(f"Gagal buat pending outbound_rm SJ-INTERNAL {sj_id}: {e}")

    out = await db.wh_delivery_notes.find_one({"id": sj_id}, {"_id": 0})
    return {"ok": True, "sj": serialize_doc(out), "wms_pending": pendings,
            "scan_out_required": bool(pendings)}


@router.post("/{sj_id}/receive")
async def receive_sj(sj_id: str, data: ReceiveIn, request: Request):
    user = await require_auth(request)
    db = get_db()
    sj = await db.wh_delivery_notes.find_one({"id": sj_id})
    if not sj:
        raise HTTPException(404, "Surat Jalan tidak ditemukan")
    if sj["status"] != "issued":
        raise HTTPException(400, "Hanya Surat Jalan issued yang dapat dikonfirmasi diterima")
    await db.wh_delivery_notes.update_one({"id": sj_id}, {"$set": {
        "status": "received",
        "received_at": _now(),
        "received_by": data.received_by or user.get("name", user["id"]),
        "updated_at": _now(),
        "updated_by": user.get("name", user["id"]),
    }})
    out = await db.wh_delivery_notes.find_one({"id": sj_id}, {"_id": 0})
    return {"ok": True, "sj": serialize_doc(out)}


@router.post("/{sj_id}/cancel")
async def cancel_sj(sj_id: str, data: CancelIn, request: Request):
    user = await require_auth(request)
    db = get_db()
    sj = await db.wh_delivery_notes.find_one({"id": sj_id})
    if not sj:
        raise HTTPException(404, "Surat Jalan tidak ditemukan")
    if sj["status"] == "received":
        raise HTTPException(400, "Surat Jalan yang sudah diterima tidak dapat dibatalkan")
    await db.wh_delivery_notes.update_one({"id": sj_id}, {"$set": {
        "status": "cancelled",
        "cancelled_at": _now(),
        "cancel_reason": data.reason,
        "updated_at": _now(),
        "updated_by": user.get("name", user["id"]),
    }})
    return {"ok": True}


@router.delete("/{sj_id}")
async def delete_sj(sj_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    sj = await db.wh_delivery_notes.find_one({"id": sj_id})
    if not sj:
        raise HTTPException(404, "Surat Jalan tidak ditemukan")
    if sj["status"] not in ("draft", "cancelled"):
        raise HTTPException(400, "Hanya draft/cancelled yang dapat dihapus")
    await db.wh_delivery_notes.delete_one({"id": sj_id})
    return {"ok": True}


@router.get("/{sj_id}/pdf")
async def sj_pdf(
    sj_id: str,
    request: Request,
    token: Optional[str] = None,
):
    if token:
        user = verify_token_str(token)
        if not user:
            raise HTTPException(401, "Invalid token")
    else:
        user = await require_auth(request)
    db = get_db()
    sj = await db.wh_delivery_notes.find_one(
        {"$or": [{"id": sj_id}, {"sj_number": sj_id}]}, {"_id": 0})
    if not sj:
        raise HTTPException(404, "Surat Jalan tidak ditemukan")
    if not REPORTLAB_OK:
        raise HTTPException(500, "ReportLab tidak tersedia")

    profile = await get_company_profile(db)
    doc_settings = await get_doc_settings(db, "delivery-note")

    buf = io.BytesIO()
    W, H = A4
    c = canvas.Canvas(buf, pagesize=A4)

    def draw_line(y_):
        c.setStrokeColor(colors.HexColor("#dee2e6"))
        c.line(15 * mm, y_, W - 15 * mm, y_)

    # ── Header ──
    c.setFont("Helvetica-Bold", 14)
    c.drawString(15 * mm, H - 20 * mm, "SURAT JALAN")
    c.setFont("Helvetica", 9)
    c.drawString(15 * mm, H - 27 * mm, profile.get("company_name") or "CV. DEWI ADITYA")
    _addr = profile.get("address") or "Jl. Industri Garmen No. 1, Indonesia"
    c.drawString(15 * mm, H - 32 * mm, _addr[:70])

    # SJ Number & type
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(W - 15 * mm, H - 20 * mm, sj.get("sj_number", ""))
    c.setFont("Helvetica", 8)
    sj_type_labels = {
        "SJ-CMT": "Pengiriman ke CMT",
        "SJ-MAKLON": "Pengiriman ke Klien Maklon",
        "SJ-SUPPLIER": "Retur ke Supplier",
        "SJ-INTERNAL": "Transfer Internal",
        "SJ-ONLINE": "Pengiriman Online Shop",
    }
    c.drawRightString(W - 15 * mm, H - 27 * mm, sj_type_labels.get(sj.get("sj_type", ""), sj.get("sj_type", "")))
    issued_at = sj.get("issued_at") or sj.get("created_at")
    if hasattr(issued_at, "strftime"):
        c.drawRightString(W - 15 * mm, H - 32 * mm, issued_at.strftime("%d/%m/%Y"))
    elif isinstance(issued_at, str):
        c.drawRightString(W - 15 * mm, H - 32 * mm, issued_at[:10])

    draw_line(H - 36 * mm)

    # Recipient
    y = H - 43 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(15 * mm, y, "KEPADA:")
    c.setFont("Helvetica", 8)
    c.drawString(35 * mm, y, sj.get("recipient_name", ""))
    y -= 5 * mm
    if sj.get("recipient_address"):
        c.drawString(35 * mm, y, sj["recipient_address"][:80])
        y -= 5 * mm
    if sj.get("recipient_phone"):
        c.drawString(35 * mm, y, f"Telp: {sj['recipient_phone']}")
        y -= 5 * mm
    if sj.get("reference_no"):
        c.setFont("Helvetica-Bold", 8)
        c.drawString(15 * mm, y, "REF:")
        c.setFont("Helvetica", 8)
        c.drawString(35 * mm, y, f"{sj.get('reference_type', '').upper()} {sj['reference_no']}")
        y -= 5 * mm

    draw_line(y - 2 * mm)
    y -= 8 * mm

    # Table header
    c.setFont("Helvetica-Bold", 8)
    col_x = [15 * mm, 20 * mm, 130 * mm, 155 * mm, 170 * mm]
    c.drawString(col_x[0], y, "No")
    c.drawString(col_x[1], y, "Deskripsi Barang")
    c.drawString(col_x[2], y, "Qty")
    c.drawString(col_x[3], y, "Satuan")
    c.drawString(col_x[4], y, "Keterangan")
    y -= 4 * mm
    draw_line(y)
    y -= 5 * mm

    # Lines
    c.setFont("Helvetica", 8)
    for line in sj.get("lines", []):
        if y < 50 * mm:
            c.showPage()
            y = H - 20 * mm
            c.setFont("Helvetica", 8)
        c.drawString(col_x[0], y, str(line.get("line_no", "")))
        desc = str(line.get("description", ""))[:60]
        c.drawString(col_x[1], y, desc)
        c.drawRightString(col_x[2] + 15 * mm, y, f"{float(line.get('qty', 0)):,.2f}")
        c.drawString(col_x[3], y, str(line.get("unit", "")))
        c.drawString(col_x[4], y, str(line.get("remarks", ""))[:25])
        y -= 6 * mm

    draw_line(y)
    y -= 10 * mm

    # Notes
    if sj.get("notes"):
        c.setFont("Helvetica-Oblique", 7)
        c.drawString(15 * mm, y, f"Catatan: {sj['notes'][:100]}")
        y -= 8 * mm

    # Signatures (configurable — P1d)
    if doc_settings.get("show_signatures", True):
        sig_context = {
            "issued_by": sj.get("shipper_name") or sj.get("issued_by_name", ""),
            "recipient_name": sj.get("recipient_name", ""),
            "driver_name": sj.get("driver_name") or sj.get("shipper_name", ""),
            "sj_number": sj.get("sj_number", ""),
        }
        sig_defs = doc_settings.get("signatures") or [
            {"label": "Pengirim", "name_source": "field", "field_key": "issued_by"},
            {"label": "Penerima", "name_source": "blank", "field_key": "recipient_name"},
            {"label": "Mengetahui", "name_source": "blank"},
        ]
        sig_defs = sig_defs[:3]  # maks 3 kolom di halaman
        n = len(sig_defs)
        xs = [15 * mm, W / 2 - 20 * mm, W - 15 * mm][:n] if n <= 3 else []
        aligns = ["L", "L", "R"][:n]
        y = max(30 * mm, y - 10 * mm)
        c.setFont("Helvetica", 8)
        for i, sd in enumerate(sig_defs):
            label = sd.get("label", "")
            if aligns[i] == "R":
                c.drawRightString(xs[i], y, label)
            else:
                c.drawString(xs[i], y, label)
        y -= 18 * mm
        c.setFont("Helvetica", 8)
        for i, sd in enumerate(sig_defs):
            nm = resolve_signature_name(sd, sig_context)
            line = f"({nm})" if nm else "(.......................)"
            if aligns[i] == "R":
                c.drawRightString(xs[i], y, line)
            else:
                c.drawString(xs[i], y, line)
        # role label kecil di bawah nama
        c.setFont("Helvetica", 6)
        for i, sd in enumerate(sig_defs):
            role = sd.get("role_label", "")
            if role:
                if aligns[i] == "R":
                    c.drawRightString(xs[i], y - 4 * mm, role)
                else:
                    c.drawString(xs[i], y - 4 * mm, role)
        c.setFont("Helvetica", 7)
        c.drawString(15 * mm, y - 9 * mm, f"Kendaraan: {sj.get('vehicle_no', '-')}")

    c.save()
    buf.seek(0)
    filename = f"surat-jalan-{sj.get('sj_number', sj_id).replace('/', '-')}.pdf"
    preview = request.query_params.get("preview") in ("1", "true", "yes")
    disposition = "inline" if preview else "attachment"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
