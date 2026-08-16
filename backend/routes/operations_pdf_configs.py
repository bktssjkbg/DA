# ruff: noqa: F401
"""
operations_pdf_configs.py — PDF Export Configuration Management
Endpoints: /api/pdf-export-columns, /api/pdf-export-configs (CRUD)

Refactored: Session #11.19 Phase 3.2.6 (split from operations_export.py 1277 LOC)
"""
import logging
import uuid
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["operations-pdf-configs"])

# PDF Column Definitions for each report type
PDF_COLUMN_DEFINITIONS = {
    'production-po': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'serial', 'label': 'Serial No'},
        {'key': 'product', 'label': 'Product Name'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Color'},
        {'key': 'qty', 'label': 'Quantity', 'required': True},
        {'key': 'price', 'label': 'Selling Price'},
        {'key': 'cmt', 'label': 'CMT Price'},
    ],
    'vendor-shipment': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'po', 'label': 'PO Number'},
        {'key': 'serial', 'label': 'Serial No'},
        {'key': 'product', 'label': 'Product Name'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Color'},
        {'key': 'qty_sent', 'label': 'Qty Sent', 'required': True},
    ],
    'buyer-shipment-dispatch': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'serial', 'label': 'Serial No'},
        {'key': 'product', 'label': 'Product Name'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Color'},
        {'key': 'ordered', 'label': 'Ordered Qty'},
        {'key': 'this_dispatch', 'label': 'This Dispatch'},
        {'key': 'cumul_shipped', 'label': 'Cumulative Shipped'},
        {'key': 'remaining', 'label': 'Remaining'},
    ],
    'production-report': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'date', 'label': 'Date'},
        {'key': 'po', 'label': 'PO Number'},
        {'key': 'serial', 'label': 'Serial No'},
        {'key': 'product', 'label': 'Product Name'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Color'},
        {'key': 'qty', 'label': 'Quantity'},
        {'key': 'price', 'label': 'Price'},
        {'key': 'cmt', 'label': 'CMT'},
        {'key': 'vendor', 'label': 'Vendor'},
        {'key': 'produced', 'label': 'Produced'},
        {'key': 'shipped', 'label': 'Shipped'},
    ],
    'report-production': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'tanggal', 'label': 'Tanggal'},
        {'key': 'no_po', 'label': 'No PO'},
        {'key': 'no_seri', 'label': 'Serial'},
        {'key': 'nama_produk', 'label': 'Produk'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'warna', 'label': 'Warna'},
        {'key': 'output_qty', 'label': 'Qty'},
        {'key': 'harga', 'label': 'Harga'},
        {'key': 'hpp', 'label': 'HPP/CMT'},
        {'key': 'garment', 'label': 'Vendor'},
        {'key': 'po_status', 'label': 'Status'},
    ],
    'report-progress': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'date', 'label': 'Tanggal'},
        {'key': 'job_number', 'label': 'Job'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'serial_number', 'label': 'Serial'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'product_name', 'label': 'Produk'},
        {'key': 'qty_progress', 'label': 'Qty'},
        {'key': 'notes', 'label': 'Catatan'},
        {'key': 'recorded_by', 'label': 'Dicatat oleh'},
    ],
    'report-financial': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'invoice_number', 'label': 'Invoice No'},
        {'key': 'category', 'label': 'Category'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'vendor_or_buyer', 'label': 'Vendor/Buyer'},
        {'key': 'amount', 'label': 'Amount'},
        {'key': 'paid', 'label': 'Paid'},
        {'key': 'remaining', 'label': 'Remaining'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'date', 'label': 'Date'},
    ],
    'report-shipment': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'direction', 'label': 'Direction'},
        {'key': 'shipment_number', 'label': 'Shipment No'},
        {'key': 'shipment_type', 'label': 'Type'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'inspection', 'label': 'Inspection'},
        {'key': 'date', 'label': 'Date'},
        {'key': 'total_qty', 'label': 'Qty'},
        {'key': 'items', 'label': 'Items'},
    ],
    'report-defect': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'date', 'label': 'Tanggal'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'product_name', 'label': 'Produk'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Warna'},
        {'key': 'defect_qty', 'label': 'Qty Defect'},
        {'key': 'defect_type', 'label': 'Tipe'},
        {'key': 'description', 'label': 'Deskripsi'},
        {'key': 'status', 'label': 'Status'},
    ],
    'report-return': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'return_number', 'label': 'Return No'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'customer_name', 'label': 'Customer'},
        {'key': 'return_date', 'label': 'Date'},
        {'key': 'total_qty', 'label': 'Total Qty'},
        {'key': 'item_count', 'label': 'Items'},
        {'key': 'reason', 'label': 'Reason'},
        {'key': 'status', 'label': 'Status'},
    ],
    'report-missing-material': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'request_number', 'label': 'Request No'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'total_qty', 'label': 'Qty'},
        {'key': 'reason', 'label': 'Reason'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'child_shipment', 'label': 'Child Shipment'},
        {'key': 'date', 'label': 'Date'},
    ],
    'report-replacement': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'request_number', 'label': 'Request No'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'total_qty', 'label': 'Qty'},
        {'key': 'reason', 'label': 'Reason'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'child_shipment', 'label': 'Child Shipment'},
        {'key': 'date', 'label': 'Date'},
    ],
    'report-accessory': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'shipment_number', 'label': 'Shipment'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'date', 'label': 'Date'},
        {'key': 'accessory_name', 'label': 'Accessory'},
        {'key': 'accessory_code', 'label': 'Code'},
        {'key': 'qty_sent', 'label': 'Qty'},
        {'key': 'unit', 'label': 'Unit'},
        {'key': 'status', 'label': 'Status'},
    ],
}


@router.get("/pdf-export-columns")
async def get_pdf_export_columns(request: Request):
    """Get available columns for a PDF type."""
    await require_auth(request)
    pdf_type = request.query_params.get('type', '')
    if pdf_type in PDF_COLUMN_DEFINITIONS:
        return {'pdf_type': pdf_type, 'columns': PDF_COLUMN_DEFINITIONS[pdf_type]}
    return {'pdf_type': pdf_type, 'columns': [], 'available_types': list(PDF_COLUMN_DEFINITIONS.keys())}


@router.get("/pdf-export-configs")
async def list_pdf_export_configs(request: Request):
    """List all PDF export configurations."""
    await require_auth(request)
    db = get_db()
    pdf_type = request.query_params.get('type')
    query = {}
    if pdf_type:
        query['pdf_type'] = pdf_type
    configs = await db.pdf_export_configs.find(query, {'_id': 0}).sort('created_at', -1).to_list(500)
    return serialize_doc(configs)


@router.get("/pdf-export-configs/{config_id}")
async def get_pdf_export_config(config_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    cfg = await db.pdf_export_configs.find_one({'id': config_id}, {'_id': 0})
    if not cfg:
        raise HTTPException(404, 'Config not found')
    return serialize_doc(cfg)


@router.post("/pdf-export-configs")
async def create_pdf_export_config(request: Request):
    """Create a new PDF export config."""
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    pdf_type = body.get('pdf_type', '')
    name = body.get('name', '')
    columns = body.get('columns', [])
    is_default = body.get('is_default', False)
    if not pdf_type or not name:
        raise HTTPException(400, 'pdf_type and name required')
    if not columns:
        raise HTTPException(400, 'columns array required')
    # Ensure required columns are included
    if pdf_type in PDF_COLUMN_DEFINITIONS:
        required = [c['key'] for c in PDF_COLUMN_DEFINITIONS[pdf_type] if c.get('required')]
        provided = set(columns)
        if not all(r in provided for r in required):
            raise HTTPException(400, f'Required columns missing: {required}')
    # If setting as default, unset previous defaults
    if is_default:
        await db.pdf_export_configs.update_many({'pdf_type': pdf_type, 'is_default': True},
                                                 {'$set': {'is_default': False}})
    new_cfg = {'id': str(uuid.uuid4()), 'pdf_type': pdf_type, 'name': name, 'columns': columns,
               'is_default': is_default, 'created_by': user.get('name', ''),
               'created_at': datetime.now(timezone.utc), 'updated_at': datetime.now(timezone.utc)}
    await db.pdf_export_configs.insert_one(new_cfg)
    await log_activity(user['id'], user.get('name', ''), 'create', 'pdf_export_config', f"Created config {name}")
    return serialize_doc({k: v for k, v in new_cfg.items() if k != '_id'})


@router.put("/pdf-export-configs/{config_id}")
async def update_pdf_export_config(config_id: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    existing = await db.pdf_export_configs.find_one({'id': config_id})
    if not existing:
        raise HTTPException(404, 'Config not found')
    update = {'updated_at': datetime.now(timezone.utc)}
    if 'name' in body:
        update['name'] = body['name']
    if 'columns' in body:
        columns = body['columns']
        # Validate required columns
        pdf_type = existing.get('pdf_type', '')
        if pdf_type in PDF_COLUMN_DEFINITIONS:
            required = [c['key'] for c in PDF_COLUMN_DEFINITIONS[pdf_type] if c.get('required')]
            provided = set(columns)
            if not all(r in provided for r in required):
                raise HTTPException(400, f'Required columns missing: {required}')
        update['columns'] = columns
    if 'is_default' in body:
        if body['is_default']:
            await db.pdf_export_configs.update_many({'pdf_type': existing['pdf_type'], 'is_default': True},
                                                     {'$set': {'is_default': False}})
        update['is_default'] = body['is_default']
    await db.pdf_export_configs.update_one({'id': config_id}, {'$set': update})
    await log_activity(user['id'], user.get('name', ''), 'update', 'pdf_export_config',
                       f"Updated config {existing.get('name', config_id)}")
    return serialize_doc(await db.pdf_export_configs.find_one({'id': config_id}, {'_id': 0}))


@router.delete("/pdf-export-configs/{config_id}")
async def delete_pdf_export_config(config_id: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    existing = await db.pdf_export_configs.find_one({'id': config_id})
    if not existing:
        raise HTTPException(404, 'Config not found')
    await db.pdf_export_configs.delete_one({'id': config_id})
    await log_activity(user['id'], user.get('name', ''), 'delete', 'pdf_export_config',
                       f"Deleted config {existing.get('name', config_id)}")
    return {'success': True}
