"use client";

import { useEffect, useState, useCallback } from "react";

export interface TickerData {
  symbol: string;
  exchange: string;
  price: number;
  bid: number;
  ask: number;
  volume: number;
  timestamp: string;
}

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "BNB/USDT"];

/** useLivePrices — polls /api/v1/data/tickers every 5 seconds. */
export function useLivePrices() {
  const [prices, setPrices] = useState<Record<string, TickerData>>({});
  const [error, setError] = useState<string | null>(null);

  const fetchPrices = useCallback(async () => {
    try {
      const symbolsParam = SYMBOLS.join(",");
      const res = await fetch(
        `/api/v1/data/tickers?exchange=binance&symbols=${encodeURIComponent(symbolsParam)}`,
        { signal: AbortSignal.timeout(4000) }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TickerData[] = await res.json();
      const map: Record<string, TickerData> = {};
      for (const tick of data) map[tick.symbol] = tick;
      setPrices(map);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    fetchPrices();
    const id = setInterval(fetchPrices, 5000);
    return () => clearInterval(id);
  }, [fetchPrices]);

  return { prices, error };
}