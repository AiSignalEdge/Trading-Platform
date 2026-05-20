"use client";

import { useEffect, useState, useCallback } from "react";
import { useLivePrices } from "@/hooks/useMarketData";

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "BNB/USDT"];

export default function HomePage() {
  const { prices } = useLivePrices();

  // Build display list — use live price if available, otherwise skip
  const displayPrices = SYMBOLS.map((pair) => {
    const normalized = pair.replace("/", "");
    const tick = prices[normalized];
    return {
      symbol: pair.replace("/USDT", ""),
      price: tick ? tick.price : null,
      change: null,
      up: null,
    };
  });

  return (
    <>
      {/* Market Ticker */}
      <div className="bg-sidebar border-b border-border">
        <div className="flex gap-6 px-6 py-2 overflow-x-auto">
          {displayPrices.map((m) => (
            <div key={m.symbol} className="flex items-center gap-2 shrink-0">
              <span className="text-xs font-bold text-text-secondary uppercase">
                {m.symbol}
              </span>
              <span
                className={`text-sm font-mono font-semibold ${
                  m.price !== null ? "text-text-primary" : "text-text-muted"
                }`}
              >
                {m.price !== null
                  ? `$${m.price.toLocaleString("en-US", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}`
                  : "—"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-text-primary">Dashboard</h1>
              <p className="text-sm text-text-muted mt-1">
                Hermes Trading System — real-time monitoring
              </p>
            </div>
            <div className="flex gap-3">
              <button className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:opacity-90">
                + New Strategy
              </button>
              <button className="px-4 py-2 bg-surface border border-border rounded-lg text-sm text-text-secondary hover:bg-hover">
                Run Backtest
              </button>
            </div>
          </div>

          {/* Portfolio Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { label: "Total Equity", value: "$12,847.23", sub: "+8.4% all-time", up: true },
              { label: "Today's P&L", value: "+$284.50", sub: "+2.26%", up: true },
              { label: "Open Positions", value: "3", sub: "ETH, SOL, AVAX", up: null },
              { label: "Win Rate", value: "67.4%", sub: "Last 30 trades", up: true },
            ].map((card) => (
              <div
                key={card.label}
                className="bg-surface border border-border rounded-xl p-5"
              >
                <p className="text-xs font-medium text-text-muted uppercase tracking-wide">
                  {card.label}
                </p>
                <p
                  className={`text-2xl font-bold font-mono mt-2 ${
                    card.up === true
                      ? "text-accent"
                      : card.up === false
                      ? "text-red-500"
                      : "text-text-primary"
                  }`}
                >
                  {card.value}
                </p>
                <p className="text-xs text-text-muted mt-1">{card.sub}</p>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Equity Curve */}
            <div className="bg-surface border border-border rounded-xl p-5 lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-text-primary">
                  Equity Curve
                </h2>
                <div className="flex gap-2">
                  {["1D", "1W", "1M", "ALL"].map((t) => (
                    <button
                      key={t}
                      className={`px-3 py-1 rounded text-xs font-medium ${
                        t === "1M"
                          ? "bg-accent text-white"
                          : "text-text-muted hover:bg-hover"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <div className="h-48 flex items-center justify-center text-text-muted text-sm">
                Equity chart placeholder
              </div>
            </div>

            {/* Market Distribution */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text-primary mb-4">
                Allocation
              </h2>
              <div className="space-y-3">
                {[
                  { name: "BTC", pct: 45, color: "bg-orange-500" },
                  { name: "ETH", pct: 30, color: "bg-blue-500" },
                  { name: "SOL", pct: 15, color: "bg-purple-500" },
                  { name: "AVAX", pct: 10, color: "bg-red-500" },
                ].map((item) => (
                  <div key={item.name}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-text-secondary">{item.name}</span>
                      <span className="text-text-muted">{item.pct}%</span>
                    </div>
                    <div className="h-2 bg-background rounded-full overflow-hidden">
                      <div
                        className={`h-full ${item.color} rounded-full`}
                        style={{ width: `${item.pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Active Strategies */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Active Strategies
              </h2>
              <span className="text-xs text-text-muted">3 running</span>
            </div>
            <div className="space-y-3">
              {[
                {
                  name: "BTC Trend Follower",
                  strat: "EMA Cross + RSI",
                  pnl: "+$1,240.50",
                  up: true,
                },
                {
                  name: "ETH Mean Reversion",
                  strat: "Bollinger Band",
                  pnl: "-$84.20",
                  up: false,
                },
                {
                  name: "SOL Momentum",
                  strat: "MACD + Volume",
                  pnl: "+$310.00",
                  up: true,
                },
              ].map((s, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 rounded-lg bg-background"
                >
                  <div>
                    <p className="text-sm font-medium text-text-primary">
                      {s.name}
                    </p>
                    <p className="text-xs text-text-muted">{s.strat}</p>
                  </div>
                  <div className="text-right">
                    <p
                      className={`text-sm font-mono font-semibold ${
                        s.up ? "text-accent" : "text-red-500"
                      }`}
                    >
                      {s.pnl}
                    </p>
                    <p className="text-xs text-text-muted">Today</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}