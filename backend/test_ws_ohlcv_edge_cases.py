"""
WebSocket /ws/ohlcv Edge Case Tests
- Various timeframes (1m/5m/1h/1d)
- Bad symbol format
- Rapid connect/disconnect
- Malformed JSON
- Large message (10KB JSON payload)
"""
import asyncio
import json
import time
import websockets
from datetime import datetime

WS_URL = "ws://127.0.0.1:8080/ws/ohlcv"

async def test_timeframes():
    """Test various timeframe subscriptions."""
    print("\n=== Test: Various Timeframes ===")
    timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
    results = []
    for tf in timeframes:
        try:
            async with websockets.connect(WS_URL) as ws:
                await ws.send(json.dumps({
                    "action": "subscribe",
                    "symbol": "BTCUSDT",
                    "timeframe": tf
                }))
                response = await asyncio.wait_for(ws.recv(), timeout=3)
                resp_data = json.loads(response)
                status = "PASS" if resp_data.get("timeframe") == tf else "FAIL"
                print(f"  {tf}: {status} -> {response}")
                results.append((tf, status))
                await ws.close()
        except Exception as e:
            print(f"  {tf}: ERROR -> {e}")
            results.append((tf, "ERROR"))
        await asyncio.sleep(0.2)
    return results

async def test_bad_symbol_formats():
    """Test bad symbol formats."""
    print("\n=== Test: Bad Symbol Formats ===")
    bad_symbols = [
        "BTC/USDT",      # slash instead of no separator
        "BTC-USDT",      # dash separator
        "btcusdt",       # lowercase
        "BTC",           # missing quote symbol
        "",              # empty string
        "A",             # single char
        "A/B/C",         # too many parts
        "12",            # numbers only
        "BTC/USDT!!!",   # special chars
        None,            # null
    ]
    results = []
    for sym in bad_symbols:
        try:
            async with websockets.connect(WS_URL) as ws:
                payload = {"action": "subscribe", "symbol": sym, "timeframe": "1m"} if sym is not None else {"action": "subscribe", "timeframe": "1m"}
                await ws.send(json.dumps(payload))
                response = await asyncio.wait_for(ws.recv(), timeout=3)
                resp_data = json.loads(response)
                # Server should either accept or reject gracefully
                print(f"  symbol={sym}: ACCEPTED (server handled it)")
                results.append((sym, "ACCEPTED"))
                await ws.close()
        except websockets.exceptions.ConnectionClosed as e:
            print(f"  symbol={sym}: CLOSED -> {e}")
            results.append((sym, "CLOSED"))
        except Exception as e:
            print(f"  symbol={sym}: ERROR -> {type(e).__name__}: {e}")
            results.append((sym, "ERROR"))
        await asyncio.sleep(0.2)
    return results

async def test_rapid_connect_disconnect():
    """Test rapid connect/disconnect cycles."""
    print("\n=== Test: Rapid Connect/Disconnect ===")
    count = 0
    errors = 0
    start = time.time()
    for i in range(20):
        try:
            async with websockets.connect(WS_URL) as ws:
                await ws.send(json.dumps({"action": "subscribe", "symbol": "BTCUSDT", "timeframe": "1m"}))
                await asyncio.wait_for(ws.recv(), timeout=2)
                count += 1
        except Exception as e:
            errors += 1
            print(f"  Cycle {i+1}: ERROR -> {e}")
        await asyncio.sleep(0.05)  # 50ms between cycles
    elapsed = time.time() - start
    print(f"  Completed {count} connections, {errors} errors in {elapsed:.2f}s")
    return count, errors, elapsed

async def test_malformed_json():
    """Test malformed JSON payloads."""
    print("\n=== Test: Malformed JSON ===")
    malformed_payloads = [
        '{"action": "subscribe", "symbol": "BTCUSDT',  # unclosed object
        '{"action": subscribe, "symbol": "BTCUSDT"}',   # bare value
        'not json at all',
        '{"action": "subscribe", symbol: "BTCUSDT"}',   # missing quotes on key
        '{"action": "subscribe", "symbol": }',          # empty value
        '',                                             # empty string
        '{broken}',
        'null',
        '{"action": "subscribe", "timeframe": "1m", "symbol": "BTCUSDT"}',  # valid JSON
    ]
    results = []
    for payload in malformed_payloads:
        try:
            async with websockets.connect(WS_URL) as ws:
                await ws.send(payload)
                # Some malformed JSON may cause immediate disconnect
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2)
                    resp_data = json.loads(response)
                    print(f"  payload={repr(payload)[:50]}: RESPONSE -> {response}")
                    results.append((payload[:30], "RESPONSE"))
                except asyncio.TimeoutError:
                    print(f"  payload={repr(payload)[:50]}: TIMEOUT (no response)")
                    results.append((payload[:30], "TIMEOUT"))
                except websockets.exceptions.ConnectionClosed:
                    print(f"  payload={repr(payload)[:50]}: CLOSED (server rejected)")
                    results.append((payload[:30], "CLOSED"))
                except Exception as e:
                    print(f"  payload={repr(payload)[:50]}: ERROR -> {e}")
                    results.append((payload[:30], "ERROR"))
                await ws.close()
        except websockets.exceptions.ConnectionClosed:
            print(f"  payload={repr(payload)[:50]}: CONNECTION CLOSED immediately")
            results.append((payload[:30], "CONN_CLOSED"))
        except Exception as e:
            print(f"  payload={repr(payload)[:50]}: CONNECT ERROR -> {e}")
            results.append((payload[:30], "CONNECT_ERR"))
        await asyncio.sleep(0.2)
    return results

async def test_large_json_payload():
    """Test that server handles large JSON payload (10KB+) without crashing."""
    print("\n=== Test: Large JSON Payload (10KB+) ===")
    # Create a large JSON payload with many fields
    large_data = {
        "action": "subscribe",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "metadata": {
            "client_id": "test_client_12345",
            "session_id": "session_abcdefghijklmnopqrstuvwxyz",
            "request_id": 1234567890,
            "timestamp": datetime.now().isoformat(),
        },
        "options": {},
        "fields": [],
    }
    # Add many fields to exceed 10KB
    for i in range(300):
        large_data["fields"].append({
            f"field_{i}": f"value_{i}" * 10,
            f"data_{i}": "x" * 50,
        })
    
    json_str = json.dumps(large_data)
    size_kb = len(json_str) / 1024
    print(f"  Payload size: {size_kb:.1f} KB")
    
    try:
        async with websockets.connect(WS_URL) as ws:
            await ws.send(json_str)
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                resp_data = json.loads(response)
                print(f"  Large payload: PASS -> Received response")
                await ws.close()
                return "PASS", size_kb
            except asyncio.TimeoutError:
                print(f"  Large payload: TIMEOUT (no response within 5s)")
                await ws.close()
                return "TIMEOUT", size_kb
            except websockets.exceptions.ConnectionClosed as e:
                print(f"  Large payload: CLOSED -> {e}")
                return "CLOSED", size_kb
    except Exception as e:
        print(f"  Large payload: ERROR -> {e}")
        return f"ERROR: {e}", size_kb

async def test_empty_message():
    """Test empty/minimal messages."""
    print("\n=== Test: Empty/Minimal Messages ===")
    empty_messages = [
        '{}',
        '{"action": ""}',
        '{"action": "subscribe"}',
        '{"action": "subscribe", "symbol": ""}',
        '{"timeframe": ""}',
    ]
    results = []
    for msg in empty_messages:
        try:
            async with websockets.connect(WS_URL) as ws:
                await ws.send(msg)
                await asyncio.wait_for(ws.recv(), timeout=2)
                print(f"  msg={repr(msg)}: OK")
                results.append((msg, "OK"))
                await ws.close()
        except Exception as e:
            print(f"  msg={repr(msg)}: {type(e).__name__}")
            results.append((msg, str(e)))
        await asyncio.sleep(0.2)
    return results

async def main():
    print("=" * 60)
    print("WebSocket /ws/ohlcv Edge Case Test Suite")
    print("=" * 60)
    
    # Run all tests
    tf_results = await test_timeframes()
    bad_sym_results = await test_bad_symbol_formats()
    rapid_count, rapid_errors, rapid_time = await test_rapid_connect_disconnect()
    malformed_results = await test_malformed_json()
    large_result, large_size = await test_large_json_payload()
    empty_results = await test_empty_message()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Timeframes: {sum(1 for _, s in tf_results if s == 'PASS')}/{len(tf_results)} passed")
    print(f"Bad Symbols: {sum(1 for _, s in bad_sym_results if s == 'ACCEPTED')}/{len(bad_sym_results)} accepted gracefully")
    print(f"Rapid Connect/Disconnect: {rapid_count} succeeded, {rapid_errors} errors in {rapid_time:.2f}s")
    print(f"Malformed JSON: {sum(1 for _, s in malformed_results if s == 'RESPONSE' or s == 'TIMEOUT')}/{len(malformed_results)} handled")
    print(f"Large Payload ({large_size:.1f}KB): {large_result}")
    print(f"Empty Messages: {sum(1 for _, s in empty_results if s == 'OK')}/{len(empty_results)} handled")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
