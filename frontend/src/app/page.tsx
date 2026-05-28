"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useLivePrices } from "@/hooks/useMarketData";
import { authFetch } from "@/lib/authFetch";
import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "BNB/USDT"];

// ─── API Types ────────────────────────────────────────────────────────────────

interface DashboardSummary {
  total_equity: number;
  total_equity_pct_change: number;
  today_pnl: number;
  today_pnl_pct: number;
  open_positions: number;
  open_positions_list: string[];
  win_rate: number;
  win_rate_label: string;
  mode: string;
}

interface EquityCurvePoint {
  timestamp: string;
  equity: number;
}

interface EquityCurveResponse {
  timeframe: string;
  points: EquityCurvePoint[];
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
}

interface LiveSummary {
  mode: string;
  cash_balance: number;
  total_position_value: number;
  total_equity: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  open_positions: number;
  positions: LivePosition[];
}

interface LivePosition {
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
}

interface ActiveStrategy {
  id: string;
  name: string;
  strategy_type: string;
  pair: string;
  today_pnl: number;
  today_pnl_pct: number;
  status: string;
}

interface ActiveStrategiesResponse {
  count: number;
  strategies: ActiveStrategy[];
}

// ─── Fetch Helpers ────────────────────────────────────────────────────────────

async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const res = await authFetch("/api/v1/dashboard/summary");
  if (!res.ok) throw new Error("Failed to fetch dashboard summary");
  return res.json();
}

async function fetchEquityCurve(timeframe: string, aggregate = false): Promise<EquityCurveResponse> {
  const agg = aggregate ? "&aggregate=true" : "";
  const res = await authFetch(`/api/v1/dashboard/equity-curve?timeframe=${timeframe}${agg}`);
  if (!res.ok) throw new Error("Failed to fetch equity curve");
  return res.json();
}

async function fetchLiveSummary(): Promise<LiveSummary | null> {
  try {
    const res = await authFetch("/api/v1/dashboard/live-summary");
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchActiveStrategies(): Promise<ActiveStrategiesResponse> {
  const res = await authFetch("/api/v1/dashboard/active-strategies");
  if (!res.ok) throw new Error("Failed to fetch active strategies");
  return res.json();
}

// ─── Chart Component ──────────────────────────────────────────────────────────

function EquityCurveChart({
  points,
  color = "#6366f1",
  label = "Equity",
}: {
  points: EquityCurvePoint[];
  color?: string;
  label?: string;
}) {
  if (!points || points.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-text-muted text-sm">
        No equity data available
      </div>
    );
  }

  const data = points.map((p) => ({
    time: new Date(p.timestamp).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
    equity: p.equity,
  }));

  return (
    <ResponsiveContainer width="100%" height={192}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <XAxis
          dataKey="time"
          tick={{ fill: "#6b7280", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: "#6b7280", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          width={50}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1a1a2e",
            border: "1px solid #2d2d4a",
            borderRadius: "8px",
            color: "#e5e7eb",
            fontSize: "12px",
          }}
          labelStyle={{ color: "#9ca3af" }}
          formatter={(value: number) => [
            `$${value.toLocaleString("en-US", { minimumFractionDigits: 2 })}`,
            label,
          ]}
        />
        <Line
          type="monotone"
          dataKey="equity"
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: color }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ─── Mode Toggle ──────────────────────────────────────────────────────────────

const MODES = [
  { key: "backtest", label: "Backtest" },
  { key: "live", label: "Live / Demo" },
] as const;
type Mode = (typeof MODES)[number]["key"];

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function HomePage() {
  const router = useRouter();
  const { prices } = useLivePrices();
  const [timeframe, setTimeframe] = useState("1M");
  const [mode, setMode] = useState<Mode>("backtest");

  // Fetch dashboard summary
  const { data: summary } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: fetchDashboardSummary,
    staleTime: 30000,
  });

  // Fetch aggregate equity curve for backtest mode
  const { data: equityCurve } = useQuery({
    queryKey: ["equity-curve", timeframe, mode],
    queryFn: () => fetchEquityCurve(timeframe, mode === "backtest"),
    enabled: mode === "backtest",
    staleTime: 60000,
  });

  // Fetch live summary for live mode
  const { data: liveSummary } = useQuery({
    queryKey: ["live-summary"],
    queryFn: fetchLiveSummary,
    enabled: mode === "live",
    staleTime: 10000, // refresh live data more often
  });

  // Fetch active strategies
  const { data: activeStrategies } = useQuery({
    queryKey: ["active-strategies"],
    queryFn: fetchActiveStrategies,
    staleTime: 30000,
  });

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

  const formatCurrency = (value: number) =>
    `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const formatPct = (value: number) =>
    `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;

  // ─── Mode-specific values ────────────────────────────────────────────────
  const isLive = mode === "live";
  const liveData = liveSummary;

  // Equity for chart
  const chartPoints = isLive
    ? liveData
      ? [
          { timestamp: new Date(Date.now() - 86400000).toISOString(), equity: liveData.cash_balance },
          { timestamp: new Date().toISOString(), equity: liveData.total_equity },
        ]
      : []
    : equityCurve?.points ?? [];

  const chartColor = isLive ? "#10b981" : "#6366f1"; // green for live, indigo for backtest

  // Equity summary card
  const equityValue = isLive
    ? liveData?.total_equity ?? 0
    : equityCurve?.final_equity ?? summary?.total_equity ?? 0;

  const equityPct = isLive
    ? 0
    : equityCurve?.total_return_pct ?? summary?.total_equity_pct_change ?? 0;

  const equityLabel = isLive ? "Live Equity" : "Backtest Equity";

  // Open positions
  const openPositions = isLive
    ? liveData?.open_positions ?? 0
    : summary?.open_positions ?? 0;

  const openPositionsList = isLive
    ? liveData?.positions?.map((p) => p.symbol) ?? []
    : summary?.open_positions_list ?? [];

  // P&L
  const todayPnl = isLive
    ? liveData?.total_unrealized_pnl ?? 0
    : summary?.today_pnl ?? 0;

  const todayPnlPct = isLive
    ? 0
    : summary?.today_pnl_pct ?? 0;

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
            <div className="flex items-center gap-3">
              {/* Mode Toggle */}
              <div className="flex bg-surface border border-border rounded-lg p-1 gap-1">
                {MODES.map((m) => (
                  <button
                    key={m.key}
                    onClick={() => setMode(m.key)}
                    className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                      mode === m.key
                        ? m.key === "live"
                          ? "bg-green-600 text-white"
                          : "bg-accent text-white"
                        : "text-text-muted hover:text-text-primary"
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
              <button
                onClick={() => router.push("/strategies")}
                className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:opacity-90"
              >
                + New Strategy
              </button>
              <button
                onClick={() => router.push("/backtest")}
                className="px-4 py-2 bg-surface border border-border rounded-lg text-sm text-text-secondary hover:bg-hover"
              >
                Run Backtest
              </button>
            </div>
          </div>

          {/* Portfolio Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              {
                label: equityLabel,
                value: equityValue > 0 ? formatCurrency(equityValue) : "—",
                sub: !isLive && equityPct !== 0 ? formatPct(equityPct) + " total return" : isLive ? `Mode: ${liveSummary?.mode ?? "paper"}` : "Loading...",
                up: isLive ? null : equityPct >= 0 ? true : false,
              },
              {
                label: isLive ? "Unrealized P&L" : "Today's P&L",
                value: todayPnl !== 0 || isLive ? (todayPnl >= 0 ? "+" : "") + formatCurrency(todayPnl) : "—",
                sub: !isLive && todayPnlPct !== 0 ? formatPct(todayPnlPct) : isLive && liveData ? `${liveData.open_positions} open positions` : "—",
                up: todayPnl >= 0 ? true : todayPnl < 0 ? false : null,
              },
              {
                label: "Open Positions",
                value: String(openPositions),
                sub: openPositionsList.length > 0 ? openPositionsList.join(", ") : "—",
                up: null,
              },
              {
                label: "Win Rate",
                value: summary ? `${summary.win_rate.toFixed(1)}%` : "—",
                sub: summary?.win_rate_label || "—",
                up: summary ? summary.win_rate >= 50 : null,
              },
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
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded ${
                      isLive ? "bg-green-900 text-green-400" : "bg-indigo-900 text-indigo-400"
                    }`}
                  >
                    {isLive ? "LIVE" : "BACKTEST"}
                  </span>
                  <h2 className="text-sm font-semibold text-text-primary">Equity Curve</h2>
                </div>
                <div className="flex gap-2 items-center">
                  {!isLive && (
                    <select
                      value={timeframe}
                      onChange={(e) => setTimeframe(e.target.value)}
                      className="bg-background border border-border text-text-secondary text-xs rounded px-2 py-1"
                    >
                      <option value="1D">1D</option>
                      <option value="1W">1W</option>
                      <option value="1M">1M</option>
                      <option value="ALL">ALL</option>
                    </select>
                  )}
                  {!isLive && (
                    <div className="flex gap-1">
                      {["1D", "1W", "1M", "ALL"].map((t) => (
                        <button
                          key={t}
                          onClick={() => setTimeframe(t)}
                          className={`px-3 py-1 rounded text-xs font-medium ${
                            t === timeframe
                              ? "bg-accent text-white"
                              : "text-text-muted hover:bg-hover"
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="h-48">
                {chartPoints.length > 0 ? (
                  <EquityCurveChart points={chartPoints} color={chartColor} />
                ) : (
                  <div className="h-full flex items-center justify-center text-text-muted text-sm">
                    {isLive ? "No live positions yet" : "Loading equity curve..."}
                  </div>
                )}
              </div>
              {!isLive && equityCurve && (
                <div className="mt-2 flex items-center gap-4 text-xs text-text-muted">
                  <span>
                    Initial: <span className="text-text-secondary">{formatCurrency(equityCurve.initial_capital)}</span>
                  </span>
                  <span>
                    Final: <span className="text-text-secondary">{formatCurrency(equityCurve.final_equity)}</span>
                  </span>
                  <span>
                    Return:{" "}
                    <span
                      className={
                        equityCurve.total_return_pct >= 0 ? "text-accent" : "text-red-500"
                      }
                    >
                      {formatPct(equityCurve.total_return_pct)}
                    </span>
                  </span>
                </div>
              )}
              {isLive && liveData && (
                <div className="mt-2 flex items-center gap-4 text-xs text-text-muted">
                  <span>
                    Cash: <span className="text-text-secondary">{formatCurrency(liveData.cash_balance)}</span>
                  </span>
                  <span>
                    Positions: <span className="text-text-secondary">{formatCurrency(liveData.total_position_value)}</span>
                  </span>
                  <span>
                    Unrealized:{" "}
                    <span className={liveData.total_unrealized_pnl >= 0 ? "text-accent" : "text-red-500"}>
                      {formatCurrency(liveData.total_unrealized_pnl)}
                    </span>
                  </span>
                </div>
              )}
            </div>

            {/* Live Positions or Allocation */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text-primary mb-4">
                {isLive ? "Live Positions" : "Allocation"}
              </h2>
              {isLive && liveData?.positions && liveData.positions.length > 0 ? (
                <div className="space-y-3">
                  {liveData.positions.map((pos, i) => (
                    <div key={i} className="p-3 rounded-lg bg-background">
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-semibold text-text-primary">
                          {pos.symbol}
                        </span>
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded ${
                            pos.side === "buy"
                              ? "bg-green-900 text-green-400"
                              : "bg-red-900 text-red-400"
                          }`}
                        >
                          {pos.side.toUpperCase()}
                        </span>
                      </div>
                      <div className="flex justify-between mt-1 text-xs text-text-muted">
                        <span>Qty: {pos.quantity}</span>
                        <span>Entry: ${pos.entry_price.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between mt-1 text-xs text-text-muted">
                        <span>Current: ${pos.current_price.toFixed(2)}</span>
                        <span
                          className={
                            pos.unrealized_pnl >= 0 ? "text-accent" : "text-red-500"
                          }
                        >
                          P&L: {pos.unrealized_pnl >= 0 ? "+" : ""}{formatCurrency(pos.unrealized_pnl)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : isLive ? (
                <div className="text-center py-8 text-text-muted text-sm">
                  No open positions
                </div>
              ) : (
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
              )}
            </div>
          </div>

          {/* Active Strategies */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Active Strategies
              </h2>
              <span className="text-xs text-text-muted">
                {activeStrategies?.count ?? 0} running
              </span>
            </div>
            <div className="space-y-3">
              {activeStrategies?.strategies?.length
                ? activeStrategies.strategies.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-background"
                    >
                      <div>
                        <p className="text-sm font-medium text-text-primary">
                          {s.name}
                        </p>
                        <p className="text-xs text-text-muted">
                          {s.strategy_type} · {s.pair}
                        </p>
                      </div>
                      <div className="text-right">
                        <p
                          className={`text-sm font-mono font-semibold ${
                            s.today_pnl >= 0 ? "text-accent" : "text-red-500"
                          }`}
                        >
                          {s.today_pnl >= 0 ? "+" : ""}
                          {s.today_pnl.toFixed(2)}
                        </p>
                        <p className="text-xs text-text-muted">
                          {formatPct(s.today_pnl_pct)}
                        </p>
                      </div>
                    </div>
                  ))
                : (
                  <div className="text-center py-6 text-text-muted text-sm">
                    No active strategies
                  </div>
                )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}