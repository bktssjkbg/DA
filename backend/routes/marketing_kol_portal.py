"""marketing_kol — Creator Portal endpoints (Auth, Catalog, Requests, Performance, KPI)."""
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.params import Query
from database import get_db
from auth import verify_password, serialize_doc
from routes.marketing_kol_shared import (
    router, _uid, _now, _create_creator_token, _client_ip,
    _check_creator_lockout, _record_failed_attempt, _clear_attempts,
    require_creator_auth, CreatorLoginIn, ItemRequestCreate, CreatorPortalSessionCreate,
)
from core import stock_service


@router.post('/creator-portal/auth/login')
async def creator_login(payload: CreatorLoginIn, request: Request):
    """Creator portal login — returns JWT with audience='creator-portal'.
    Brute-force protected: 5 failed attempts per IP+email → 15 min lockout.
    """
    db = get_db()
    email = payload.email.lower().strip()
    identifier = f"{_client_ip(request)}:{email}"
    await _check_creator_lockout(db, identifier)
    creator = await db.marketing_kol_creators.find_one({'login_email': email}, {'_id': 0})
    if not creator:
        remaining = await _record_failed_attempt(db, identifier)
        raise HTTPException(
            401,
            f'Email atau password salah. Sisa {remaining} percobaan.'
            if remaining > 0
            else 'Akun terkunci sementara karena terlalu banyak percobaan login.'
        )
    if not verify_password(payload.password, creator.get('login_password_hash', '')):
        remaining = await _record_failed_attempt(db, identifier)
        raise HTTPException(
            401,
            f'Email atau password salah. Sisa {remaining} percobaan.'
            if remaining > 0
            else 'Akun terkunci sementara karena terlalu banyak percobaan login.'
        )
    if creator.get('status') != 'active':
        raise HTTPException(403, 'Akun creator tidak aktif. Hubungi admin.')
    await _clear_attempts(db, identifier)
    await db.marketing_kol_creators.update_one({'id': creator['id']}, {'$set': {'last_login_at': _now()}})
    token = _create_creator_token(creator)
    return {
        'token': token,
        'creator_id': creator['id'],
        'creator_name': creator['name'],
        'creator_code': creator['creator_code'],
        'assigned_account_ids': creator.get('assigned_account_ids', []),
    }


@router.get('/creator-portal/auth/profile')
async def creator_get_profile(request: Request):
    creator = await require_creator_auth(request)
    db = get_db()
    assigned = await db.marketing_platform_accounts.find(
        {'id': {'$in': creator.get('assigned_account_ids', [])}}, {'_id': 0}
    ).to_list(500)
    return serialize_doc({**creator, 'assigned_accounts': assigned})


@router.get('/creator-portal/catalog')
async def creator_get_catalog(request: Request, account_id: Optional[str] = Query(None)):
    creator = await require_creator_auth(request)
    db = get_db()
    allowed_account_ids = creator.get('assigned_account_ids', [])
    query = {'is_active': True}
    if account_id:
        if account_id not in allowed_account_ids:
            raise HTTPException(403, 'Creator tidak memiliki akses ke akun ini')
        query['account_id'] = account_id
    elif allowed_account_ids:
        query['account_id'] = {'$in': allowed_account_ids}
    else:
        return []
    catalog = await db.marketing_creator_catalog.find(query, {'_id': 0}).sort('product_name', 1).to_list(500)
    # BUG-INV-12 fix: agregasi stok kanonik lintas semua baris/skema.
    fg_ids = [it.get('fg_product_id') for it in catalog if it.get('fg_product_id')]
    stock_map = await stock_service.onhand_map(fg_ids, db=db) if fg_ids else {}
    for item in catalog:
        fg_id = item.get('fg_product_id')
        item['stock_qty'] = stock_map.get(fg_id, 0) if fg_id else 0
    return serialize_doc(catalog)


@router.post('/creator-portal/requests')
async def creator_request_item(data: ItemRequestCreate, request: Request):
    creator = await require_creator_auth(request)
    db = get_db()
    allowed = creator.get('assigned_account_ids', [])
    if data.account_id not in allowed:
        raise HTTPException(403, 'Creator tidak memiliki akses ke akun ini')
    catalog_item = await db.marketing_creator_catalog.find_one({'id': data.catalog_item_id, 'is_active': True}, {'_id': 0})
    if not catalog_item:
        raise HTTPException(404, 'Produk tidak ditemukan di katalog')
    fg_id = catalog_item.get('fg_product_id')
    stock_qty = 0
    if fg_id:
        # BUG-INV-12 fix: agregasi stok kanonik lintas semua baris/skema.
        stock_qty = await stock_service.get_onhand(fg_id, db=db)
    req = {
        'id': _uid(), 'creator_id': creator['id'], 'creator_name': creator['name'],
        'creator_code': creator['creator_code'], 'account_id': data.account_id,
        'catalog_item_id': data.catalog_item_id, 'product_name': catalog_item['product_name'],
        'sku': catalog_item['sku'], 'fg_product_id': fg_id,
        'quantity_requested': data.quantity_requested, 'stock_at_request': stock_qty,
        'purpose': data.purpose or '', 'notes': data.notes or '',
        'status': 'pending', 'reviewed_at': None, 'reviewed_by': None, 'rejection_reason': None,
        'created_at': _now(),
    }
    await db.marketing_creator_item_requests.insert_one(req)
    return serialize_doc({'message': 'Permintaan berhasil dikirim', 'request': req})


@router.get('/creator-portal/my-requests')
async def creator_my_requests(request: Request):
    creator = await require_creator_auth(request)
    db = get_db()
    requests = await db.marketing_creator_item_requests.find(
        {'creator_id': creator['id']}, {'_id': 0}
    ).sort('created_at', -1).to_list(500)
    return serialize_doc(requests)


@router.post('/creator-portal/sessions')
async def creator_create_session(data: CreatorPortalSessionCreate, request: Request):
    """Creator self-report sebuah sesi live. creator_id dari token.
    Otomatis ter-agregasi ke Sales Marketing (revenue_type='live')."""
    creator = await require_creator_auth(request)
    db = get_db()

    # Validasi account & pastikan ter-assign ke creator ini
    account = await db.marketing_platform_accounts.find_one({'id': data.account_id}, {'_id': 0})
    if not account:
        raise HTTPException(404, 'Account tidak ditemukan')
    assigned = creator.get('assigned_account_ids', []) or []
    if assigned and data.account_id not in assigned:
        raise HTTPException(403, 'Account ini tidak ditugaskan untuk Anda')

    session = {
        'id': _uid(), 'creator_id': creator['id'], 'creator_name': creator['name'],
        'creator_code': creator.get('creator_code'), 'account_id': data.account_id,
        'account_name': account['account_name'], 'platform': data.platform,
        'date': data.date, 'session_name': data.session_name or f"Live {data.date}",
        'duration_minutes': data.duration_minutes, 'viewers': data.viewers,
        'peak_viewers': data.peak_viewers, 'revenue': data.revenue, 'orders': data.orders,
        'items_promoted': data.items_promoted or [], 'notes': data.notes or '',
        'source': 'creator_self_report',
        'created_at': _now(), 'created_by': creator.get('login_email') or creator['name'],
    }
    await db.marketing_creator_sessions.insert_one(session)

    # Sinkronkan ke Sales Marketing agar tidak "slip".
    try:
        from routes.marketing_live_sales_sync import sync_live_sales_to_marketing
        await sync_live_sales_to_marketing(db, data.account_id, data.date)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("sync_live_sales gagal (creator session)", exc_info=True)

    return serialize_doc({'message': 'Sesi berhasil dicatat', 'session': session})


@router.get('/creator-portal/my-sessions')
async def creator_my_sessions(request: Request, month: Optional[str] = Query(None)):
    """Daftar sesi self-report milik creator (default bulan berjalan)."""
    creator = await require_creator_auth(request)
    db = get_db()
    q = {'creator_id': creator['id']}
    if month:
        q['date'] = {'$regex': f'^{month}'}
    sessions = await db.marketing_creator_sessions.find(q, {'_id': 0}).sort('date', -1).to_list(500)
    return serialize_doc(sessions)


@router.get('/creator-portal/my-accounts')
async def creator_my_accounts(request: Request):
    """Akun yang ditugaskan untuk creator (untuk dropdown input sesi)."""
    creator = await require_creator_auth(request)
    db = get_db()
    ids = creator.get('assigned_account_ids', []) or []
    if not ids:
        return []
    accs = await db.marketing_platform_accounts.find(
        {'id': {'$in': ids}},
        {'_id': 0, 'id': 1, 'account_name': 1, 'account_code': 1, 'platform': 1}
    ).to_list(200)
    return serialize_doc(accs)



@router.get('/creator-portal/my-performance')
async def creator_my_performance(
    request: Request, month: Optional[str] = Query(None, description="YYYY-MM"),
):
    creator = await require_creator_auth(request)
    db = get_db()
    if not month:
        month = _now().strftime('%Y-%m')
    date_from = f'{month}-01'
    year, mon = int(month.split('-')[0]), int(month.split('-')[1])
    next_month = datetime(year, mon, 1, tzinfo=timezone.utc) + timedelta(days=32)
    date_to = (next_month.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
    sessions = await db.marketing_creator_sessions.find(
        {'creator_id': creator['id'], 'date': {'$gte': date_from, '$lte': date_to}}, {'_id': 0}
    ).sort('date', -1).to_list(500)
    kpi = creator.get('kpi_targets', {})
    total_revenue = sum(s.get('revenue', 0) for s in sessions)
    total_sessions = len(sessions)
    total_viewers = sum(s.get('viewers', 0) for s in sessions)
    return serialize_doc({
        'month': month, 'sessions': sessions,
        'summary': {
            'total_sessions': total_sessions,
            'total_revenue': round(total_revenue),
            'total_viewers': total_viewers,
            'total_orders': sum(s.get('orders', 0) for s in sessions),
        },
        'kpi_targets': kpi,
        'kpi_progress': {
            'revenue_pct': round(total_revenue / kpi['monthly_revenue'] * 100, 1) if kpi.get('monthly_revenue') else None,
            'sessions_pct': round(total_sessions / kpi['monthly_sessions'] * 100, 1) if kpi.get('monthly_sessions') else None,
            'viewers_pct': round(total_viewers / kpi['monthly_viewers'] * 100, 1) if kpi.get('monthly_viewers') else None,
        },
    })


@router.get('/creator-portal/my-kpi')
async def creator_my_kpi(request: Request):
    creator = await require_creator_auth(request)
    db = get_db()
    month = _now().strftime('%Y-%m')
    date_from = f'{month}-01'
    year, mon = int(month.split('-')[0]), int(month.split('-')[1])
    next_month = datetime(year, mon, 1, tzinfo=timezone.utc) + timedelta(days=32)
    date_to = (next_month.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
    sessions = await db.marketing_creator_sessions.find(
        {'creator_id': creator['id'], 'date': {'$gte': date_from, '$lte': date_to}}, {'_id': 0}
    ).to_list(500)
    kpi = creator.get('kpi_targets', {})
    total_revenue = sum(s.get('revenue', 0) for s in sessions)
    total_sessions = len(sessions)
    total_viewers = sum(s.get('viewers', 0) for s in sessions)
    return serialize_doc({
        'month': month, 'creator_name': creator['name'],
        'kpi_targets': kpi,
        'actuals': {
            'monthly_revenue': round(total_revenue),
            'monthly_sessions': total_sessions,
            'monthly_viewers': total_viewers,
        },
        'progress': {
            'revenue_pct': round(total_revenue / kpi['monthly_revenue'] * 100, 1) if kpi.get('monthly_revenue') else None,
            'sessions_pct': round(total_sessions / kpi['monthly_sessions'] * 100, 1) if kpi.get('monthly_sessions') else None,
            'viewers_pct': round(total_viewers / kpi['monthly_viewers'] * 100, 1) if kpi.get('monthly_viewers') else None,
        },
    })
