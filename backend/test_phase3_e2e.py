"""
End-to-end integration test for Phase 3 backtest endpoints.

Tests:
  POST /api/v1/backtest/walk-forward
  POST /api/v1/backtest/monte-carlo
  POST /api/v1/backtest/batch
  GET  /api/v1/backtest/batch/{job_id}
  GET  /api/v1/backtest/walk-forward/{job_id}

All must return valid JSON with correct structure.
Uses FastAPI TestClient from fastapi.testclient.
"""

import sys
import os

# Ensure the backend package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Override DATABASE_URL before any imports
os.environ["DATABASE_URL"] = "postgresql+asyncpg://trading_user:Trading%402025@localhost:5432/trading_db"

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assert_valid_json(response, status_code=200):
    """Assert response is JSON and returns expected status."""
    assert response.status_code == status_code, (
        f"Expected {status_code}, got {response.status_code}: {response.text}"
    )
    assert response.headers.get("content-type", "").startswith("application/json"), (
        f"Expected JSON content-type, got: {response.headers.get('content-type')}"
    )
    return response.json()


# ---------------------------------------------------------------------------
# POST /api/v1/backtest/walk-forward
# ---------------------------------------------------------------------------

print("\n=== TEST: POST /api/v1/backtest/walk-forward ===")

wf_payload = {
    "strategy": "ma_cross",
    "strategy_params": {"fast_ma": 10, "slow_ma": 30},
    "pairs": ["BTC/USDT"],
    "timeframes": ["1h"],
    "start_date": "2024-01-01",
    "end_date": "2024-03-01",
    "exchange": "binance",
    "initial_capital": 10000.0,
    "leverage": 1.0,
    "train_window_days": 14,
    "test_window_days": 7,
    "skip_days": 0,
    "direction": "both",
    "maker_fee": 0.0002,
    "taker_fee": 0.0004,
    "slippage_bps": 5.0,
}

wf_response = client.post("/api/v1/backtest/walk-forward", json=wf_payload)
wf_data = assert_valid_json(wf_response)

print(f"Response: {wf_data}")

# Validate WalkForwardResponse structure
assert "job_id" in wf_data, f"Missing 'job_id' in response: {wf_data}"
assert "status" in wf_data, f"Missing 'status' in response: {wf_data}"
assert "n_windows" in wf_data, f"Missing 'n_windows' in response: {wf_data}"
assert isinstance(wf_data["job_id"], str), f"job_id should be str, got {type(wf_data['job_id'])}"
assert isinstance(wf_data["status"], str), f"status should be str, got {type(wf_data['status'])}"
assert isinstance(wf_data["n_windows"], int), f"n_windows should be int, got {type(wf_data['n_windows'])}"
print(f"  ✅ job_id={wf_data['job_id']}, status={wf_data['status']}, n_windows={wf_data['n_windows']}")

wf_job_id = wf_data["job_id"]


# ---------------------------------------------------------------------------
# GET /api/v1/backtest/walk-forward/{job_id}
# ---------------------------------------------------------------------------

print(f"\n=== TEST: GET /api/v1/backtest/walk-forward/{wf_job_id} ===")

wf_get_response = client.get(f"/api/v1/backtest/walk-forward/{wf_job_id}")
wf_get_data = assert_valid_json(wf_get_response)

print(f"Response: {wf_get_data}")

assert "job_id" in wf_get_data, f"Missing 'job_id' in response: {wf_get_data}"
assert "status" in wf_get_data, f"Missing 'status' in response: {wf_get_data}"
assert "n_windows" in wf_get_data, f"Missing 'n_windows' in response: {wf_get_data}"
assert wf_get_data["job_id"] == wf_job_id, (
    f"Expected job_id={wf_job_id}, got {wf_get_data['job_id']}"
)
print(f"  ✅ job_id={wf_get_data['job_id']}, status={wf_get_data['status']}")


# ---------------------------------------------------------------------------
# POST /api/v1/backtest/monte-carlo
# ---------------------------------------------------------------------------

print("\n=== TEST: POST /api/v1/backtest/monte-carlo ===")

mc_payload = {
    "strategy": "ma_cross",
    "strategy_params": {"fast_ma": 10, "slow_ma": 30},
    "pairs": ["BTC/USDT"],
    "timeframes": ["1h"],
    "start_date": "2024-01-01",
    "end_date": "2024-03-01",
    "exchange": "binance",
    "initial_capital": 10000.0,
    "leverage": 1.0,
    "n_runs": 50,
    "random_seed": 42,
    "direction": "both",
    "maker_fee": 0.0002,
    "taker_fee": 0.0004,
    "slippage_bps": 5.0,
}

mc_response = client.post("/api/v1/backtest/monte-carlo", json=mc_payload)
mc_data = assert_valid_json(mc_response)

print(f"Response: {mc_data}")

# Validate MonteCarloResponse structure
assert "job_id" in mc_data, f"Missing 'job_id' in response: {mc_data}"
assert "status" in mc_data, f"Missing 'status' in response: {mc_data}"
assert "n_runs" in mc_data, f"Missing 'n_runs' in response: {mc_data}"
assert isinstance(mc_data["job_id"], str), f"job_id should be str, got {type(mc_data['job_id'])}"
assert isinstance(mc_data["status"], str), f"status should be str, got {type(mc_data['status'])}"
assert isinstance(mc_data["n_runs"], int), f"n_runs should be int, got {type(mc_data['n_runs'])}"
print(f"  ✅ job_id={mc_data['job_id']}, status={mc_data['status']}, n_runs={mc_data['n_runs']}")


# ---------------------------------------------------------------------------
# POST /api/v1/backtest/batch
# ---------------------------------------------------------------------------

print("\n=== TEST: POST /api/v1/backtest/batch ===")

batch_payload = {
    "name": "Test Batch",
    "configs": [
        {
            "name": "Batch Config 1",
            "strategies": [],
            "pairs": ["BTC/USDT"],
            "timeframes": ["1h"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-01",
            "exchange": "binance",
            "initial_capital": 10000.0,
            "leverage": 1.0,
            "max_positions": 5,
            "direction": "both",
            "fees": {"maker": 0.0002, "taker": 0.0004},
        },
        {
            "name": "Batch Config 2",
            "strategies": [],
            "pairs": ["ETH/USDT"],
            "timeframes": ["4h"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-01",
            "exchange": "binance",
            "initial_capital": 10000.0,
            "leverage": 1.0,
            "max_positions": 5,
            "direction": "both",
            "fees": {"maker": 0.0002, "taker": 0.0004},
        },
    ],
}

batch_response = client.post("/api/v1/backtest/batch", json=batch_payload)
batch_data = assert_valid_json(batch_response)

print(f"Response: {batch_data}")

# Validate BatchRunResponse structure
assert "job_id" in batch_data, f"Missing 'job_id' in response: {batch_data}"
assert "count" in batch_data, f"Missing 'count' in response: {batch_data}"
assert "status" in batch_data, f"Missing 'status' in response: {batch_data}"
assert isinstance(batch_data["job_id"], str), f"job_id should be str, got {type(batch_data['job_id'])}"
assert isinstance(batch_data["count"], int), f"count should be int, got {type(batch_data['count'])}"
assert isinstance(batch_data["status"], str), f"status should be str, got {type(batch_data['status'])}"
assert batch_data["count"] == 2, f"Expected count=2, got {batch_data['count']}"
print(f"  ✅ job_id={batch_data['job_id']}, count={batch_data['count']}, status={batch_data['status']}")

batch_job_id = batch_data["job_id"]


# ---------------------------------------------------------------------------
# GET /api/v1/backtest/batch/{job_id}
# ---------------------------------------------------------------------------

print(f"\n=== TEST: GET /api/v1/backtest/batch/{batch_job_id} ===")

batch_get_response = client.get(f"/api/v1/backtest/batch/{batch_job_id}")
batch_get_data = assert_valid_json(batch_get_response)

print(f"Response: {batch_get_data}")

# Validate BatchProgressResponse structure
assert "job_id" in batch_get_data, f"Missing 'job_id' in response: {batch_get_data}"
assert "status" in batch_get_data, f"Missing 'status' in response: {batch_get_data}"
assert "total" in batch_get_data, f"Missing 'total' in response: {batch_get_data}"
assert "completed" in batch_get_data, f"Missing 'completed' in response: {batch_get_data}"
assert "failed" in batch_get_data, f"Missing 'failed' in response: {batch_get_data}"
assert "progress_pct" in batch_get_data, f"Missing 'progress_pct' in response: {batch_get_data}"
assert isinstance(batch_get_data["job_id"], str), f"job_id should be str, got {type(batch_get_data['job_id'])}"
assert isinstance(batch_get_data["total"], int), f"total should be int, got {type(batch_get_data['total'])}"
assert isinstance(batch_get_data["completed"], int), f"completed should be int, got {type(batch_get_data['completed'])}"
assert isinstance(batch_get_data["failed"], int), f"failed should be int, got {type(batch_get_data['failed'])}"
assert isinstance(batch_get_data["progress_pct"], (int, float)), (
    f"progress_pct should be numeric, got {type(batch_get_data['progress_pct'])}"
)
assert batch_get_data["job_id"] == batch_job_id, (
    f"Expected job_id={batch_job_id}, got {batch_get_data['job_id']}"
)
print(f"  ✅ job_id={batch_get_data['job_id']}, status={batch_get_data['status']}, "
      f"total={batch_get_data['total']}, completed={batch_get_data['completed']}, "
      f"failed={batch_get_data['failed']}, progress_pct={batch_get_data['progress_pct']}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("✅ ALL PHASE 3 ENDPOINT TESTS PASSED")
print("=" * 60)
print("  POST /api/v1/backtest/walk-forward   → valid JSON ✓")
print("  POST /api/v1/backtest/monte-carlo     → valid JSON ✓")
print("  POST /api/v1/backtest/batch           → valid JSON ✓")
print("  GET  /api/v1/backtest/batch/{job_id}  → valid JSON ✓")
print("  GET  /api/v1/backtest/walk-forward/{job_id} → valid JSON ✓")
print("=" * 60)