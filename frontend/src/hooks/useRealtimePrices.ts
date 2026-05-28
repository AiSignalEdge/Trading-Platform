"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface PriceTick {
  symbol: string;
  exchange: string;
  price: number;
  bid: number;
  ask: number;
  volume: number;
  timestamp: string;
}

const WS_URL =
  typeof window !== "undefined"
    ? `ws://${window.location.hostname}:8086/ws/prices`
    : null;

const POLL_INTERVAL = 5000; // fallback polling interval ms

/**
 * useRealtimePrices — connects to the backend WebSocket for live price ticks.
 * Falls back to HTTP polling if WebSocket is unavailable.
 */
export function useRealtimePrices(symbols: string[]) {
  const [prices, setPrices] = useState<Record<string, PriceTick>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [connected, setConnected] = useState(false);

  const fetchPrices = useCallback(async () => {
    try {
      // GET /api/v1/data/tickers?exchange=binance&symbols=BTC/USDT,ETH/USDT,SOL/USDT
      const params = new URLSearchParams({ exchange: "binance", symbols: symbols.join(",") });
      const res = await fetch(`/api/v1/data/tickers?${params}`, {
        headers: { "X-API-Key": "hermes-secret-api-key-2025" },
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) return;
      const data = await res.json();
      setPrices((prev) => {
        const next = { ...prev };
        for (const tick of Array.isArray(data) ? data : [data]) {
          next[`${tick.exchange}:${tick.symbol}`] = tick;
        }
        return next;
      });
    } catch {
      // ignore poll failures
    }
  }, []);

  const connectWs = useCallback(() => {
    if (!WS_URL) return;
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        ws.send(JSON.stringify({ action: "subscribe", symbols }));
      };

      ws.onmessage = (event) => {
        try {
          const tick = JSON.parse(event.data) as PriceTick;
          setPrices((prev) => ({
            ...prev,
            [`${tick.exchange}:${tick.symbol}`]: tick,
          }));
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // reconnect after 3s
        setTimeout(connectWs, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // WebSocket not available — fall through to polling
    }
  }, [symbols]);

  useEffect(() => {
    connectWs();

    // Fallback polling every POLL_INTERVAL
    fetchPrices();
    pollRef.current = setInterval(fetchPrices, POLL_INTERVAL);

    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [connectWs, fetchPrices]);

  return { prices, connected };
}