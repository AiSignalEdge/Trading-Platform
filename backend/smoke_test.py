#!/usr/bin/env python3
"""
Full Backend API Smoke Test
Tests all routes on port 8086
"""
import requests
import json
import time
import sys

BASE = "http://127.0.0.1:8086"
API_KEY = "hermes-secret-api-key-2025"  # from .env
results = []

def req(method, path, token=None, json_data=None, params=None, label=None):
    url = f"{BASE}{path}"
    headers = {"X-API-Key": API_KEY}  # Use API key auth
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_data:
        headers["Content-Type"] = "application/json"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, params=params, timeout=15)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=json_data, params=params, timeout=15)
        elif method == "PUT":
            r = requests.put(url, headers=headers, json=json_data, timeout=15)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=15)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        status = r.status_code
        try:
            body = r.json()
        except:
            body = r.text[:200]
        
        note = ""
        if status >= 500:
            note = f"5xx ERROR: {body}"
        elif status == 404:
            note = "404 NOT FOUND"
        elif status == 401:
            note = "401 UNAUTHORIZED"
        elif status == 422:
            note = f"422 VALIDATION ERROR: {body}"
        
        results.append((label or f"{method} {path}", status, note, body))
        
        print(f"[{status}] {method} {path} — {note or 'OK'}")
        return r, body
    except requests.exceptions.Timeout:
        results.append((label or f"{method} {path}", "TIMEOUT", "Request timed out", None))
        print(f"[TIMEOUT] {method} {path}")
        return None, None
    except Exception as e:
        results.append((label or f"{method} {path}", "ERROR", str(e), None))
        print(f"[ERROR] {method} {path}: {e}")
        return None, None

# ─── Step 1: Register and Login ──────────────────────────────────────────────
print("\n=== PHASE 1: Auth ===")
ts = int(time.time())
_, reg = req("POST", "/api/v1/auth/register", json_data={
    "username": f"smoke_{ts}",
    "email": f"smoke_{ts}@test.com",
    "password": "TestPass123!"
})
if reg and "id" in reg:
    print(f"  Registered user ID: {reg.get('id')}")
else:
    print(f"  Registration response: {reg}")

# Login uses OAuth2PasswordRequestForm (form-data, not JSON)
login_resp = requests.post(f"{BASE}/api/v1/auth/login", data={
    "username": f"smoke_{ts}",
    "password": "TestPass123!"
}, headers={"X-API-Key": API_KEY}, timeout=15)
try:
    login = login_resp.json()
except:
    login = None
if login_resp.status_code >= 400:
    results.append(("POST /api/v1/auth/login", login_resp.status_code, f"ERROR: {login}", login))
    print(f"[{login_resp.status_code}] POST /api/v1/auth/login — ERROR: {login}")
else:
    results.append(("POST /api/v1/auth/login", login_resp.status_code, "OK", login))
    print(f"[{login_resp.status_code}] POST /api/v1/auth/login — OK")
token = None
if login and "access_token" in login:
    token = login["access_token"]
    print(f"  Got token: {token[:20]}...")
else:
    print(f"  Login failed: {login}")
    print("FATAL: Cannot proceed without auth token")
    sys.exit(1)

_, me = req("GET", "/api/v1/auth/me", token=token, label="GET /api/v1/auth/me")
print(f"  Me response: {me}")

# ─── Step 2: Strategies ─────────────────────────────────────────────────────
print("\n=== PHASE 2: Strategies ===")
req("GET", "/api/v1/strategies", token=token, label="GET /api/v1/strategies")
req("GET", "/api/v1/strategies/search", token=token, label="GET /api/v1/strategies/search")

# Create a strategy
_, strat = req("POST", "/api/v1/strategies", token=token, json_data={
    "name": f"Smoke Test Strategy {ts}",
    "type": "momentum",
    "description": "Test strategy from smoke test",
    "parameters": {"rsi_period": 14, "signal": "buy"}
})
strat_id = None
if strat and "id" in strat:
    strat_id = strat["id"]
    print(f"  Created strategy ID: {strat_id}")
else:
    print(f"  Strategy create failed: {strat}")

if strat_id:
    req("GET", f"/api/v1/strategies/{strat_id}", token=token, label=f"GET /api/v1/strategies/{strat_id}")
    req("PUT", f"/api/v1/strategies/{strat_id}", token=token, json_data={"description": "Updated"}, label=f"PUT /api/v1/strategies/{strat_id}")
    req("GET", f"/api/v1/strategies/{strat_id}/versions", token=token, label=f"GET /api/v1/strategies/{strat_id}/versions")
    req("POST", f"/api/v1/strategies/{strat_id}/versions", token=token, json_data={"parameters": {"rsi_period": 21}}, label=f"POST /api/v1/strategies/{strat_id}/versions")
    req("POST", f"/api/v1/strategies/{strat_id}/revert/1", token=token, label=f"POST /api/v1/strategies/{strat_id}/revert/1")

# ─── Step 3: Pairs ───────────────────────────────────────────────────────────
print("\n=== PHASE 3: Pairs ===")
req("GET", "/api/v1/pairs", token=token, label="GET /api/v1/pairs")
req("GET", "/api/v1/pairs/1", token=token, label="GET /api/v1/pairs/1")
req("GET", "/api/v1/pairs/symbol/binance/BTCUSDT", token=token, label="GET /api/v1/pairs/symbol/binance/BTCUSDT")
req("GET", "/api/v1/pairs/search/similar", token=token, params={"symbol": "BTC"}, label="GET /api/v1/pairs/search/similar")

# ─── Step 4: Dashboard ───────────────────────────────────────────────────────
print("\n=== PHASE 4: Dashboard ===")
req("GET", "/api/v1/dashboard/summary", token=token, label="GET /api/v1/dashboard/summary")
req("GET", "/api/v1/dashboard/equity-curve", token=token, label="GET /api/v1/dashboard/equity-curve")
req("GET", "/api/v1/dashboard/active-strategies", token=token, label="GET /api/v1/dashboard/active-strategies")

# ─── Step 5: Risk ────────────────────────────────────────────────────────────
print("\n=== PHASE 5: Risk ===")
req("GET", "/api/v1/risk/summary", token=token, label="GET /api/v1/risk/summary")
req("GET", "/api/v1/risk/analysis/1", token=token, label="GET /api/v1/risk/analysis/1")
req("GET", "/api/v1/risk/metrics/1", token=token, label="GET /api/v1/risk/metrics/1")
req("GET", "/api/v1/risk/limits/1", token=token, label="GET /api/v1/risk/limits/1")
req("POST", "/api/v1/risk/limits/1", token=token, json_data={"max_position_size": 0.1}, label="POST /api/v1/risk/limits/1")
req("GET", "/api/v1/risk/var/1", token=token, label="GET /api/v1/risk/var/1")
req("GET", "/api/v1/risk/stress-test/1", token=token, label="GET /api/v1/risk/stress-test/1")

# ─── Step 6: Scheduler ───────────────────────────────────────────────────────
print("\n=== PHASE 6: Scheduler ===")
req("GET", "/api/v1/scheduler/jobs", token=token, label="GET /api/v1/scheduler/jobs")
req("GET", "/api/v1/scheduler/jobs/history", token=token, label="GET /api/v1/scheduler/jobs/history")

# Create a job
_, job = req("POST", "/api/v1/scheduler/jobs", token=token, json_data={
    "name": f"Smoke Test Job {ts}",
    "job_type": "backtest",
    "cron": "0 0 * * *",
    "config": {"strategy_id": strat_id} if strat_id else {}
})
job_id = None
if job and "id" in job:
    job_id = job["id"]
    print(f"  Created job ID: {job_id}")
else:
    print(f"  Job create response: {job}")

if job_id:
    req("GET", f"/api/v1/scheduler/jobs/{job_id}", token=token, label=f"GET /api/v1/scheduler/jobs/{job_id}")
    req("PUT", f"/api/v1/scheduler/jobs/{job_id}", token=token, json_data={"name": "Updated Job"}, label=f"PUT /api/v1/scheduler/jobs/{job_id}")
    req("POST", f"/api/v1/scheduler/jobs/{job_id}/run", token=token, label=f"POST /api/v1/scheduler/jobs/{job_id}/run")
    req("DELETE", f"/api/v1/scheduler/jobs/{job_id}", token=token, label=f"DELETE /api/v1/scheduler/jobs/{job_id}")

# ─── Step 7: Backtest ────────────────────────────────────────────────────────
print("\n=== PHASE 7: Backtest ===")
req("GET", "/api/v1/backtest", token=token, label="GET /api/v1/backtest")
req("GET", "/api/v1/backtest/history", token=token, label="GET /api/v1/backtest/history")
req("GET", "/api/v1/backtest/1", token=token, label="GET /api/v1/backtest/1")
req("GET", "/api/v1/backtest/1/results", token=token, label="GET /api/v1/backtest/1/results")
req("GET", "/api/v1/backtest/1/equity-curve", token=token, label="GET /api/v1/backtest/1/equity-curve")
req("GET", "/api/v1/backtest/1/trades", token=token, label="GET /api/v1/backtest/1/trades")

# ─── Step 8: Signals ─────────────────────────────────────────────────────────
print("\n=== PHASE 8: Signals ===")
req("GET", "/api/v1/signals", token=token, label="GET /api/v1/signals")
req("POST", "/api/v1/signals/generate", token=token, json_data={"strategy_id": strat_id} if strat_id else {}, label="POST /api/v1/signals/generate")
req("GET", "/api/v1/signals/history", token=token, label="GET /api/v1/signals/history")

# ─── Step 9: Portfolio ───────────────────────────────────────────────────────
print("\n=== PHASE 9: Portfolio ===")
req("GET", "/api/v1/portfolio", token=token, label="GET /api/v1/portfolio")
req("GET", "/api/v1/portfolio/positions", token=token, label="GET /api/v1/portfolio/positions")
req("GET", "/api/v1/portfolio/performance", token=token, label="GET /api/v1/portfolio/performance")
req("GET", "/api/v1/portfolio/balances", token=token, label="GET /api/v1/portfolio/balances")

# ─── Step 10: Execution ──────────────────────────────────────────────────────
print("\n=== PHASE 10: Execution ===")
req("GET", "/api/v1/execution/orders", token=token, label="GET /api/v1/execution/orders")
req("GET", "/api/v1/execution/orders/1", token=token, label="GET /api/v1/execution/orders/1")
req("GET", "/api/v1/execution/trades", token=token, label="GET /api/v1/execution/trades")

# ─── Step 11: Webhooks ──────────────────────────────────────────────────────
print("\n=== PHASE 11: Webhooks ===")
req("GET", "/api/v1/webhooks", token=token, label="GET /api/v1/webhooks")
req("POST", "/api/v1/webhooks", token=token, json_data={
    "url": f"https://test_{ts}.com/hook",
    "events": ["trade.executed"]
}, label="POST /api/v1/webhooks")
req("POST", "/api/v1/webhooks/test", token=token, json_data={"url": f"https://test_{ts}.com/hook"}, label="POST /api/v1/webhooks/test")

# ─── Step 12: Data Quality ───────────────────────────────────────────────────
print("\n=== PHASE 12: Data Quality ===")
req("GET", "/api/v1/data-quality/candles", token=token, label="GET /api/v1/data-quality/candles")
req("GET", "/api/v1/data-quality/candles/BTCUSDT/1h/gaps", token=token, label="GET /api/v1/data-quality/candles/BTCUSDT/1h/gaps")
req("GET", "/api/v1/data-quality/summary", token=token, label="GET /api/v1/data-quality/summary")

# ─── Step 13: Export ─────────────────────────────────────────────────────────
print("\n=== PHASE 13: Export ===")
req("GET", "/api/v1/export", token=token, label="GET /api/v1/export")
req("GET", "/api/v1/export/strategies", token=token, label="GET /api/v1/export/strategies")
req("GET", "/api/v1/export/strategies/1", token=token, label="GET /api/v1/export/strategies/1")
req("GET", "/api/v1/export/backtests/1", token=token, label="GET /api/v1/export/backtests/1")
req("GET", "/api/v1/export/portfolios/1", token=token, label="GET /api/v1/export/portfolios/1")
req("GET", "/api/v1/export/signals/1", token=token, label="GET /api/v1/export/signals/1")
req("GET", "/api/v1/export/batch", token=token, label="GET /api/v1/export/batch")

# ─── Step 14: Data ───────────────────────────────────────────────────────────
print("\n=== PHASE 14: Data ===")
req("GET", "/api/v1/data/candles", token=token, params={"pair": "BTCUSDT", "timeframe": "1h", "limit": 10}, label="GET /api/v1/data/candles")
req("GET", "/api/v1/data/ohlcv", token=token, params={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 10}, label="GET /api/v1/data/ohlcv")
req("GET", "/api/v1/data/tickers", token=token, label="GET /api/v1/data/tickers")
req("GET", "/api/v1/data/orderbooks", token=token, params={"symbol": "BTCUSDT"}, label="GET /api/v1/data/orderbooks")

# ─── Step 15: AI/Describe ───────────────────────────────────────────────────
print("\n=== PHASE 15: AI/Describe ===")
req("POST", "/api/v1/ai/describe", token=token, json_data={"query": "What is RSI?"}, label="POST /api/v1/ai/describe")
if strat_id:
    req("POST", f"/api/v1/ai/describe/{strat_id}", token=token, label=f"POST /api/v1/ai/describe/{strat_id}")

# ─── Step 16: Notifications ──────────────────────────────────────────────────
print("\n=== PHASE 16: Notifications ===")
req("GET", "/api/v1/notifications", token=token, label="GET /api/v1/notifications")
req("POST", "/api/v1/notifications", token=token, json_data={"title": "Test", "message": "Smoke test"}, label="POST /api/v1/notifications")

# ─── Summary ─────────────────────────────────────────────────────────────────
print("\n\n" + "="*80)
print("SMOKE TEST RESULTS SUMMARY")
print("="*80)

failures = []
for endpoint, status, note, body in results:
    if status == "TIMEOUT" or status == "ERROR":
        failures.append((endpoint, status, note))
    elif isinstance(status, int) and status >= 400:
        failures.append((endpoint, status, note))

if failures:
    print(f"\n❌ {len(failures)} FAILURES:\n")
    for endpoint, status, note in failures:
        print(f"  {endpoint}")
        print(f"    Status: {status}")
        print(f"    Note: {note}")
        print()
else:
    print("\n✅ All endpoints returned non-4xx/5xx responses")

print("\n--- FULL RESULTS TABLE ---")
print(f"{'Endpoint':<55} {'Status':<10} {'Notes'}")
print("-"*100)
for endpoint, status, note, body in results:
    print(f"{endpoint:<55} {str(status):<10} {note}")