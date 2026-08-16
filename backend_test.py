#!/usr/bin/env python3
"""Backend API testing for returns visibility feature"""
import requests
import sys

BASE_URL = "https://maklon-dispatch-fix.preview.emergentagent.com"
ADMIN_CREDS = {"email": "admin@garment.com", "password": "Admin@123"}

# Expected data for July 2026 at TIKTOK-OUTFIT store
EXPECTED_GROSS = 59783811
EXPECTED_RETURNED = 2222282
EXPECTED_NET = 57561529
EXPECTED_RETURNED_ORDERS = 6

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log(msg, status="INFO"):
    color = Colors.GREEN if status == "PASS" else Colors.RED if status == "FAIL" else Colors.YELLOW
    print(f"{color}{status}{Colors.RESET} {msg}")

def login():
    """Login and get token"""
    try:
        r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS, timeout=30)
        r.raise_for_status()
        token = r.json()["token"]
        log("Login successful", "PASS")
        return token
    except Exception as e:
        log(f"Login failed: {e}", "FAIL")
        sys.exit(1)

def test_cycle_summary(token, account_id):
    """Test GET /api/marketing/cycle/summary for July 2026"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(
            f"{BASE_URL}/api/marketing/cycle/summary",
            headers=headers,
            params={"account_id": account_id, "period": "2026-07"},
            timeout=60
        )
        
        if r.status_code != 200:
            log(f"cycle/summary HTTP {r.status_code}", "FAIL")
            return False
        
        data = r.json()
        actual = data.get("actual", {})
        returns = data.get("returns", {})
        
        # Check gross revenue
        revenue = actual.get("revenue")
        revenue_gross = actual.get("revenue_gross")
        if revenue != EXPECTED_GROSS or revenue_gross != EXPECTED_GROSS:
            log(f"cycle/summary: revenue mismatch. Expected {EXPECTED_GROSS}, got revenue={revenue}, revenue_gross={revenue_gross}", "FAIL")
            return False
        
        # Check returned amount
        returned_amount = actual.get("returned_amount")
        if returned_amount != EXPECTED_RETURNED:
            log(f"cycle/summary: returned_amount mismatch. Expected {EXPECTED_RETURNED}, got {returned_amount}", "FAIL")
            return False
        
        # Check net revenue
        revenue_net = actual.get("revenue_net_returns")
        if revenue_net != EXPECTED_NET:
            log(f"cycle/summary: revenue_net_returns mismatch. Expected {EXPECTED_NET}, got {revenue_net}", "FAIL")
            return False
        
        # Check returned orders
        returned_orders = actual.get("returned_orders")
        if returned_orders != EXPECTED_RETURNED_ORDERS:
            log(f"cycle/summary: returned_orders mismatch. Expected {EXPECTED_RETURNED_ORDERS}, got {returned_orders}", "FAIL")
            return False
        
        # Check returns block
        if not returns:
            log("cycle/summary: returns block missing", "FAIL")
            return False
        
        coverage = returns.get("coverage", {})
        if not coverage.get("complete"):
            log(f"cycle/summary: coverage not complete - {coverage}", "WARN")
        
        # Check revenue_pct is calculated from gross (not net)
        achievement = data.get("achievement", {})
        target = data.get("target", {})
        if target.get("revenue"):
            expected_pct = round((revenue / target["revenue"]) * 100, 1)
            actual_pct = achievement.get("revenue_pct")
            if abs(expected_pct - actual_pct) > 0.1:
                log(f"cycle/summary: revenue_pct should be from gross. Expected ~{expected_pct}%, got {actual_pct}%", "FAIL")
                return False
        
        log(f"cycle/summary: ✓ gross={revenue}, returned={returned_amount}, net={revenue_net}, orders={returned_orders}", "PASS")
        return True
        
    except Exception as e:
        log(f"cycle/summary error: {e}", "FAIL")
        return False

def test_cycle_overview(token):
    """Test GET /api/marketing/cycle/overview for July 2026"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(
            f"{BASE_URL}/api/marketing/cycle/overview",
            headers=headers,
            params={"period": "2026-07"},
            timeout=90
        )
        
        if r.status_code != 200:
            log(f"cycle/overview HTTP {r.status_code}", "FAIL")
            return False
        
        data = r.json()
        totals = data.get("totals", {})
        
        # Check totals have returns fields
        if "returned_amount" not in totals:
            log("cycle/overview: totals missing returned_amount", "FAIL")
            return False
        
        if "revenue_net_returns" not in totals:
            log("cycle/overview: totals missing revenue_net_returns", "FAIL")
            return False
        
        if "returned_orders" not in totals:
            log("cycle/overview: totals missing returned_orders", "FAIL")
            return False
        
        if "returns_pct" not in totals:
            log("cycle/overview: totals missing returns_pct", "FAIL")
            return False
        
        if "returns_coverage_complete" not in totals:
            log("cycle/overview: totals missing returns_coverage_complete", "FAIL")
            return False
        
        # Check calculation
        revenue = totals.get("revenue", 0)
        returned = totals.get("returned_amount", 0)
        net = totals.get("revenue_net_returns", 0)
        
        if net != revenue - returned:
            log(f"cycle/overview: net calculation wrong. revenue={revenue}, returned={returned}, net={net}", "FAIL")
            return False
        
        log(f"cycle/overview: ✓ totals have all returns fields, net={net}", "PASS")
        return True
        
    except Exception as e:
        log(f"cycle/overview error: {e}", "FAIL")
        return False

def test_creator_scorecard(token):
    """Test GET /api/marketing/targets/creator/scorecard for July 2026"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(
            f"{BASE_URL}/api/marketing/targets/creator/scorecard",
            headers=headers,
            params={"year": 2026, "month": 7},
            timeout=90
        )
        
        if r.status_code != 200:
            log(f"creator/scorecard HTTP {r.status_code}", "FAIL")
            return False
        
        data = r.json()
        totals = data.get("totals", {})
        
        # Check totals have returns fields
        required_fields = ["order_revenue_returned", "orders_returned", "order_revenue_net_returns"]
        for field in required_fields:
            if field not in totals:
                log(f"creator/scorecard: totals missing {field}", "FAIL")
                return False
        
        # Check rows have returns fields
        rows = data.get("rows", [])
        if rows:
            first_row = rows[0]
            actual = first_row.get("actual", {})
            for field in required_fields:
                if field not in actual:
                    log(f"creator/scorecard: row actual missing {field}", "FAIL")
                    return False
        
        log(f"creator/scorecard: ✓ totals and rows have returns fields", "PASS")
        return True
        
    except Exception as e:
        log(f"creator/scorecard error: {e}", "FAIL")
        return False

def test_creator_detail(token):
    """Test GET /api/marketing/targets/creator/{id}/detail"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        # First get scorecard to find a creator
        r = requests.get(
            f"{BASE_URL}/api/marketing/targets/creator/scorecard",
            headers=headers,
            params={"year": 2026, "month": 7},
            timeout=90
        )
        
        if r.status_code != 200:
            log("creator/detail: can't get scorecard to find creator", "WARN")
            return True  # Skip if no data
        
        data = r.json()
        rows = data.get("rows", [])
        if not rows:
            log("creator/detail: no creators to test", "WARN")
            return True
        
        creator_id = rows[0]["creator_id"]
        
        # Get detail
        r = requests.get(
            f"{BASE_URL}/api/marketing/targets/creator/{creator_id}/detail",
            headers=headers,
            params={"year": 2026, "month": 7},
            timeout=90
        )
        
        if r.status_code != 200:
            log(f"creator/detail HTTP {r.status_code}", "FAIL")
            return False
        
        data = r.json()
        totals = data.get("totals", {})
        
        # Check totals have returns fields
        if "orders_returned_counted" not in totals:
            log("creator/detail: totals missing orders_returned_counted", "FAIL")
            return False
        
        if "orders_returned_counted_revenue" not in totals:
            log("creator/detail: totals missing orders_returned_counted_revenue", "FAIL")
            return False
        
        if "order_revenue_net_returns" not in totals:
            log("creator/detail: totals missing order_revenue_net_returns", "FAIL")
            return False
        
        # Check calculation
        order_revenue = totals.get("order_revenue", 0)
        returned_revenue = totals.get("orders_returned_counted_revenue", 0)
        net = totals.get("order_revenue_net_returns", 0)
        
        expected_net = max(order_revenue - returned_revenue, 0)
        if abs(net - expected_net) > 0.01:
            log(f"creator/detail: net calculation wrong. order_revenue={order_revenue}, returned={returned_revenue}, net={net}, expected={expected_net}", "FAIL")
            return False
        
        log(f"creator/detail: ✓ totals have returns fields and calculation correct", "PASS")
        return True
        
    except Exception as e:
        log(f"creator/detail error: {e}", "FAIL")
        return False

def test_weekly_report(token):
    """Test GET /api/marketing/reports/weekly for week containing July 13-19, 2026"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(
            f"{BASE_URL}/api/marketing/reports/weekly",
            headers=headers,
            params={"week_start": "2026-07-13"},  # Monday of week containing Jul 13-19
            timeout=120
        )
        
        if r.status_code != 200:
            log(f"weekly report HTTP {r.status_code}", "FAIL")
            return False
        
        data = r.json()
        gabungan = data.get("gabungan", {})
        
        # Check gabungan has returns fields
        if "nilai_retur" not in gabungan:
            log("weekly report: gabungan missing nilai_retur", "FAIL")
            return False
        
        if "omzet_setelah_retur" not in gabungan:
            log("weekly report: gabungan missing omzet_setelah_retur", "FAIL")
            return False
        
        if "retur" not in gabungan:
            log("weekly report: gabungan missing retur (count)", "FAIL")
            return False
        
        # Check per_toko rows
        per_toko = data.get("per_toko", [])
        if per_toko:
            first_store = per_toko[0]
            if "nilai_retur" not in first_store:
                log("weekly report: per_toko missing nilai_retur", "FAIL")
                return False
            if "omzet_setelah_retur" not in first_store:
                log("weekly report: per_toko missing omzet_setelah_retur", "FAIL")
                return False
            if "retur_persen" not in first_store:
                log("weekly report: per_toko missing retur_persen", "FAIL")
                return False
        
        # Check calculation
        omzet = gabungan.get("omzet", 0)
        nilai_retur = gabungan.get("nilai_retur", 0)
        setelah_retur = gabungan.get("omzet_setelah_retur", 0)
        
        expected_net = max(omzet - nilai_retur, 0)
        if abs(setelah_retur - expected_net) > 0.01:
            log(f"weekly report: calculation wrong. omzet={omzet}, nilai_retur={nilai_retur}, setelah_retur={setelah_retur}, expected={expected_net}", "FAIL")
            return False
        
        log(f"weekly report: ✓ gabungan and per_toko have returns fields", "PASS")
        return True
        
    except Exception as e:
        log(f"weekly report error: {e}", "FAIL")
        return False

def test_weekly_exports(token):
    """Test weekly report Excel and PDF exports"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test Excel export
        r = requests.get(
            f"{BASE_URL}/api/marketing/reports/weekly/export-excel",
            headers=headers,
            params={"week_start": "2026-07-13"},
            timeout=120
        )
        
        if r.status_code != 200:
            log(f"weekly export-excel HTTP {r.status_code}", "FAIL")
            return False
        
        if len(r.content) < 1000:
            log(f"weekly export-excel: file too small ({len(r.content)} bytes)", "FAIL")
            return False
        
        # Test PDF export
        r = requests.get(
            f"{BASE_URL}/api/marketing/reports/weekly/export-pdf",
            headers=headers,
            params={"week_start": "2026-07-13"},
            timeout=120
        )
        
        if r.status_code != 200:
            log(f"weekly export-pdf HTTP {r.status_code}", "FAIL")
            return False
        
        if len(r.content) < 1000:
            log(f"weekly export-pdf: file too small ({len(r.content)} bytes)", "FAIL")
            return False
        
        log("weekly exports: ✓ Excel and PDF exports return HTTP 200", "PASS")
        return True
        
    except Exception as e:
        log(f"weekly exports error: {e}", "FAIL")
        return False

def get_tiktok_outfit_id(token):
    """Get the account_id for TIKTOK-OUTFIT store"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(
            f"{BASE_URL}/api/marketing/accounts",
            headers=headers,
            timeout=30
        )
        
        if r.status_code != 200:
            log(f"Failed to get accounts: HTTP {r.status_code}", "FAIL")
            return None
        
        accounts = r.json()
        if not isinstance(accounts, list):
            accounts = accounts.get("accounts", [])
        
        for acc in accounts:
            if acc.get("account_code") == "TIKTOK-OUTFIT":
                return acc.get("id")
        
        log("TIKTOK-OUTFIT account not found", "FAIL")
        return None
        
    except Exception as e:
        log(f"Error getting TIKTOK-OUTFIT id: {e}", "FAIL")
        return None

def main():
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}Backend API Testing - Returns Visibility Feature{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}\n")
    
    token = login()
    account_id = get_tiktok_outfit_id(token)
    
    if not account_id:
        log("Cannot proceed without TIKTOK-OUTFIT account_id", "FAIL")
        return 1
    
    log(f"Found TIKTOK-OUTFIT account_id: {account_id}", "INFO")
    
    tests = [
        ("cycle/summary", lambda: test_cycle_summary(token, account_id)),
        ("cycle/overview", lambda: test_cycle_overview(token)),
        ("creator/scorecard", lambda: test_creator_scorecard(token)),
        ("creator/detail", lambda: test_creator_detail(token)),
        ("weekly report", lambda: test_weekly_report(token)),
        ("weekly exports", lambda: test_weekly_exports(token)),
    ]
    
    passed = 0
    failed = 0
    
    print(f"\n{Colors.YELLOW}Running API tests...{Colors.RESET}\n")
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            log(f"{name} exception: {e}", "FAIL")
            failed += 1
    
    print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}Results: {passed} passed, {failed} failed{Colors.RESET}")
    
    if failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ All backend API tests passed{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Some backend API tests failed{Colors.RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
