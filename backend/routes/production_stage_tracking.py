"""PO Stage Tracking — ekstensi DA (dipertahankan saat adopsi SOMMERVILLE Fase 2).

Dipakai oleh panel aktif `POStageTrackingPanel.jsx` di RahazaOrdersModule.
Sumber asli: routes/_archive/pre_sommerville/production_po.py (GAP #3 + BUG-003).
Mendukung dua koleksi: production_pos DAN rahaza_orders.
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc
from core.helpers import now
from routes.production_rbac import deny_klien

router = APIRouter(prefix="/api", tags=["production-stage-tracking"])


@router.put("/production-pos/{po_id}/stage-qty")
async def update_po_stage_qty(po_id: str, request: Request):
    """
    Input / update qty per tahap produksi untuk internal PO.
    stage: cutting | sewing | qc | packing
    Jika PO punya WO, data aktual diambil dari WIP events (real-time).
    Input manual di sini berlaku sebagai override/suplemen.
    """
    user = await require_auth(request)
    deny_klien(user)
    db = get_db()
    # BUG-003 fix: panel Stage Tracking juga dipakai oleh Order Produksi Rahaza
    # (koleksi rahaza_orders), bukan hanya production_pos. Cari di kedua koleksi.
    po = await db.production_pos.find_one({'id': po_id})
    po_collection = 'production_pos'
    if not po:
        po = await db.rahaza_orders.find_one({'id': po_id})
        po_collection = 'rahaza_orders'
    if not po:
        raise HTTPException(404, 'PO tidak ditemukan')

    body = await request.json()
    stage = body.get('stage')
    valid_stages = ['cutting', 'sewing', 'qc', 'packing']
    if stage not in valid_stages:
        raise HTTPException(400, f"stage harus salah satu dari: {valid_stages}")

    stage_qty = po.get('stage_qty') or {}

    if stage == 'cutting':
        if body.get('qty_in') is not None:
            stage_qty['cutting_input'] = max(0, int(body['qty_in']))
        if body.get('qty_out') is not None:
            stage_qty['cutting_output'] = max(0, int(body['qty_out']))
    elif stage == 'sewing':
        if body.get('qty_out') is not None:
            stage_qty['sewing_output'] = max(0, int(body['qty_out']))
    elif stage == 'qc':
        if body.get('qty_pass') is not None:
            stage_qty['qc_pass'] = max(0, int(body['qty_pass']))
        if body.get('qty_fail') is not None:
            stage_qty['qc_fail'] = max(0, int(body['qty_fail']))
    elif stage == 'packing':
        if body.get('qty_out') is not None:
            stage_qty['packing_output'] = max(0, int(body['qty_out']))

    await db[po_collection].update_one(
        {'id': po_id},
        {'$set': {'stage_qty': stage_qty, 'updated_at': now()}}
    )
    return {'message': f'Stage qty {stage} diperbarui', 'stage_qty': stage_qty}


@router.get("/production-pos/{po_id}/stage-summary")
async def get_po_stage_summary(po_id: str, request: Request):
    """
    Aggregated stage summary untuk PO:
    - Real data dari rahaza_wip_events (linked WOs)
    - Suplemen manual dari po.stage_qty
    Returns cutting/sewing/qc/packing summary.
    """
    user = await require_auth(request)
    deny_klien(user)
    db = get_db()
    # BUG-003 fix: dukung juga Order Produksi Rahaza (koleksi rahaza_orders)
    po = await db.production_pos.find_one({'id': po_id})
    po_source = 'production_pos'
    if not po:
        po = await db.rahaza_orders.find_one({'id': po_id})
        po_source = 'rahaza_orders'
    if not po:
        raise HTTPException(404, 'PO tidak ditemukan')

    # Get all WOs for this PO
    wo_ids_raw = await db.rahaza_work_orders.find(
        {'order_id': po_id, 'source': {'$ne': 'maklon'}},
        {'_id': 0, 'id': 1, 'qty': 1, 'status': 1}
    ).to_list(500)
    wo_ids = [w['id'] for w in wo_ids_raw]
    total_wo_qty = sum(int(w.get('qty', 0)) for w in wo_ids_raw)

    # Aggregate from WIP events
    wip_summary = {'cutting_output': 0, 'sewing_output': 0, 'qc_pass': 0, 'qc_fail': 0, 'packing_output': 0}
    if wo_ids:
        processes = await db.rahaza_processes.find(
            {'active': True}, {'_id': 0, 'id': 1, 'name': 1, 'order_seq': 1, 'process_type': 1}
        ).sort('order_seq', 1).to_list(500)
        proc_ids = [p['id'] for p in processes]

        if proc_ids:
            cutting_proc = processes[0] if processes else None
            last_proc = processes[-1] if processes else None

            pipe_base = [
                {'$match': {'work_order_id': {'$in': wo_ids}, 'event_type': 'output'}},
                {'$group': {'_id': '$process_id', 'total': {'$sum': '$qty'}}}
            ]
            agg = await db.rahaza_wip_events.aggregate(pipe_base).to_list(500)
            by_proc = {r['_id']: r['total'] for r in agg}

            if cutting_proc:
                wip_summary['cutting_output'] = by_proc.get(cutting_proc['id'], 0)
            if last_proc:
                wip_summary['sewing_output'] = by_proc.get(last_proc['id'], 0)

            qc_pipe = [
                {'$match': {'work_order_id': {'$in': wo_ids}, 'event_type': {'$in': ['qc_pass', 'qc_fail']}}},
                {'$group': {'_id': '$event_type', 'total': {'$sum': '$qty'}}}
            ]
            qc_agg = await db.rahaza_wip_events.aggregate(qc_pipe).to_list(500)
            for r in qc_agg:
                if r['_id'] == 'qc_pass':
                    wip_summary['qc_pass'] = r['total']
                elif r['_id'] == 'qc_fail':
                    wip_summary['qc_fail'] = r['total']

    # Manual stage_qty from PO (used as override when WIP data unavailable)
    manual_sq = po.get('stage_qty') or {}

    def _pick(wip_key, manual_key):
        wip_val = wip_summary.get(wip_key, 0)
        manual_val = int(manual_sq.get(manual_key, 0))
        return wip_val if wip_val > 0 else manual_val

    # Items summary for each stage
    if po_source == 'rahaza_orders':
        qty_ordered = sum(int(it.get('qty', 0)) for it in (po.get('items') or []))
    else:
        items = await db.po_items.find({'po_id': po_id}, {'_id': 0}).to_list(500)
        qty_ordered = sum(int(it.get('qty_ordered', 0)) for it in items)

    summary = {
        'po_id': po_id,
        'po_number': po.get('po_number') or po.get('order_number', ''),
        'status': po.get('status', ''),
        'qty_ordered': qty_ordered,
        'total_wo_qty': total_wo_qty,
        'wo_count': len(wo_ids_raw),
        'stage_qty': {
            'cutting_input':   int(manual_sq.get('cutting_input', 0)),
            'cutting_output':  _pick('cutting_output', 'cutting_output'),
            'sewing_output':   _pick('sewing_output', 'sewing_output'),
            'qc_pass':         _pick('qc_pass', 'qc_pass'),
            'qc_fail':         _pick('qc_fail', 'qc_fail'),
            'packing_output':  int(manual_sq.get('packing_output', 0)),
        },
        'wip_data_available': bool(wo_ids),
        'manual_stage_qty': manual_sq,
    }

    # Calculate progress %
    sq = summary['stage_qty']
    if qty_ordered > 0:
        if sq['packing_output'] >= qty_ordered:
            summary['progress_pct'] = 100
        elif sq['qc_pass'] > 0:
            summary['progress_pct'] = min(84, 70 + int((sq['qc_pass'] / qty_ordered) * 14))
        elif sq['sewing_output'] > 0:
            summary['progress_pct'] = min(69, 50 + int((sq['sewing_output'] / qty_ordered) * 19))
        elif sq['cutting_output'] > 0:
            summary['progress_pct'] = min(49, 30 + int((sq['cutting_output'] / qty_ordered) * 19))
        else:
            completed_wos = sum(1 for w in wo_ids_raw if w.get('status') == 'completed')
            summary['progress_pct'] = int((completed_wos / len(wo_ids_raw) * 100)) if wo_ids_raw else 0
    else:
        summary['progress_pct'] = 0

    return serialize_doc(summary)
