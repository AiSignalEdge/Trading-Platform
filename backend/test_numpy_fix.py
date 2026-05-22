"""
Test script to verify numpy serialization fix in walk-forward and monte-carlo endpoints.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_walk_forward():
    """Test walk-forward endpoint returns 200 with valid JSON."""
    print("Testing POST /api/v1/backtest/walk-forward ...")
    response = client.post(
        "/api/v1/backtest/walk-forward",
        json={
            "pairs": ["BTC/USDT"],
            "timeframes": ["4h"],
            "strategy": "ma_cross",
            "start_date": "2025-01-01",
            "end_date": "2025-03-01",
        },
    )
    print(f"  Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    print(f"  Response keys: {list(data.keys())}")
    print(f"  job_id: {data.get('job_id')}")
    print(f"  status: {data.get('status')}")
    print(f"  n_windows: {data.get('n_windows')}")
    print(f"  avg_train_return: {data.get('avg_train_return')}")
    print(f"  overfit_score: {data.get('overfit_score')}")
    # Verify all values are native Python types (not numpy)
    assert isinstance(data.get('n_windows'), int), f"n_windows should be int, got {type(data.get('n_windows'))}"
    assert isinstance(data.get('avg_train_return'), (float, type(None))), f"avg_train_return should be float, got {type(data.get('avg_train_return'))}"
    if data.get('windows'):
        w = data['windows'][0]
        assert isinstance(w.get('train_return'), (float, type(None))), f"train_return should be float, got {type(w.get('train_return'))}"
        assert isinstance(w.get('trades'), int), f"trades should be int, got {type(w.get('trades'))}"
    print("  ✓ PASSED\n")
    return data


def test_monte_carlo():
    """Test monte-carlo endpoint returns 200 with valid JSON."""
    print("Testing POST /api/v1/backtest/monte-carlo ...")
    response = client.post(
        "/api/v1/backtest/monte-carlo",
        json={
            "pairs": ["BTC/USDT"],
            "timeframes": ["4h"],
            "strategy": "ma_cross",
            "start_date": "2025-01-01",
            "end_date": "2025-03-01",
            "n_runs": 50,
        },
    )
    print(f"  Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    print(f"  Response keys: {list(data.keys())}")
    print(f"  job_id: {data.get('job_id')}")
    print(f"  status: {data.get('status')}")
    print(f"  n_runs: {data.get('n_runs')}")
    print(f"  median_return: {data.get('median_return')}")
    print(f"  percentile_5_return: {data.get('percentile_5_return')}")
    print(f"  percentile_95_return: {data.get('percentile_95_return')}")
    # Verify all values are native Python types (not numpy)
    assert isinstance(data.get('n_runs'), int), f"n_runs should be int, got {type(data.get('n_runs'))}"
    assert isinstance(data.get('median_return'), (float, type(None))), f"median_return should be float, got {type(data.get('median_return'))}"
    assert isinstance(data.get('percentile_5_return'), (float, type(None))), f"percentile_5_return should be float, got {type(data.get('percentile_5_return'))}"
    assert isinstance(data.get('percentile_95_return'), (float, type(None))), f"percentile_95_return should be float, got {type(data.get('percentile_95_return'))}"
    if data.get('all_returns'):
        for r in data['all_returns']:
            assert isinstance(r, float), f"all_returns elements should be float, got {type(r)}"
    print("  ✓ PASSED\n")
    return data


if __name__ == "__main__":
    print("=" * 60)
    print("Testing numpy serialization fix for backtest endpoints")
    print("=" * 60)
    
    try:
        wf_result = test_walk_forward()
        mc_result = test_monte_carlo()
        print("=" * 60)
        print("All tests PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)