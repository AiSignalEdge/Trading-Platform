"use client";

import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/authFetch";
import {
  Shield,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Activity,
  PieChart,
  Settings,
  Zap,
  Clock,
} from "lucide-react";

// Types
interface Position {
  id: string;
  pair: string;
  side: "long" | "short";
  size: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnl: number;
  pnlPct: number;
  stopLoss: number;
  takeProfit: number;
  distanceToSL: number;
}

interface Exposure {
  symbol: string;
  long: number;
  short: number;
  total: number;
  pctOfPortfolio: number;
}

interface RiskMetrics {
  totalEquity: number;
  cash: number;
  marginUsed: number;
  var95: number;
  maxDrawdown: number;
  portfolioBeta: number;
  correlationBTC: number;
  correlationETH: number;
}

interface CircuitBreaker {
  drawdownLimit: number;
  currentDrawdown: number;
  drawdownPct: number;
  daysSinceLargeLoss: number;
  autoPauseActive: boolean;
  status: "normal" | "warning" | "critical" | "paused";
}

interface AlertThresholds {
  maxDrawdownPct: number;
  maxSingleLossPct: number;
  maxDailyLossPct: number;
  currentDrawdown: number;
  currentSingleLoss: number;
  currentDailyLoss: number;
}

// Mock data
const MOCK_POSITIONS: Position[] = [
  {
    id: "1",
    pair: "BTC/USD",
    side: "long",
    size: 0.5,
    entryPrice: 67200,
    currentPrice: 68500,
    unrealizedPnl: 650,
    pnlPct: 1.93,
    stopLoss: 65000,
    takeProfit: 72000,
    distanceToSL: 5.11,
  },
  {
    id: "2",
    pair: "ETH/USD",
    side: "long",
    size: 3.2,
    entryPrice: 3420,
    currentPrice: 3380,
    unrealizedPnl: -128,
    pnlPct: -1.17,
    stopLoss: 3300,
    takeProfit: 3800,
    distanceToSL: 2.37,
  },
  {
    id: "3",
    pair: "SOL/USD",
    side: "short",
    size: 25,
    entryPrice: 178,
    currentPrice: 182,
    unrealizedPnl: -100,
    pnlPct: -2.25,
    stopLoss: 190,
    takeProfit: 160,
    distanceToSL: 4.4,
  },
  {
    id: "4",
    pair: "AVAX/USD",
    side: "long",
    size: 45,
    entryPrice: 38.5,
    currentPrice: 39.2,
    unrealizedPnl: 31.5,
    pnlPct: 1.82,
    stopLoss: 36,
    takeProfit: 45,
    distanceToSL: 8.16,
  },
  {
    id: "5",
    pair: "LINK/USD",
    side: "short",
    size: 80,
    entryPrice: 14.8,
    currentPrice: 14.5,
    unrealizedPnl: 24,
    pnlPct: 2.03,
    stopLoss: 15.5,
    takeProfit: 12.5,
    distanceToSL: 6.9,
  },
];

const MOCK_EXPOSURE: Exposure[] = [
  { symbol: "BTC", long: 34250, short: 0, total: 34250, pctOfPortfolio: 45.2 },
  { symbol: "ETH", long: 10900, short: 0, total: 10900, pctOfPortfolio: 14.4 },
  { symbol: "SOL", long: 0, short: 4550, total: 4550, pctOfPortfolio: 6.0 },
  { symbol: "AVAX", long: 1764, short: 0, total: 1764, pctOfPortfolio: 2.3 },
  { symbol: "LINK", long: 0, short: 1160, total: 1160, pctOfPortfolio: 1.5 },
  { symbol: "USDC", long: 23400, short: 0, total: 23400, pctOfPortfolio: 30.9 },
];

const MOCK_RISK_METRICS: RiskMetrics = {
  totalEquity: 75824,
  cash: 23400,
  marginUsed: 52424,
  var95: 2840,
  maxDrawdown: 8.2,
  portfolioBeta: 1.15,
  correlationBTC: 0.72,
  correlationETH: 0.68,
};

const MOCK_CIRCUIT_BREAKER: CircuitBreaker = {
  drawdownLimit: 15,
  currentDrawdown: 6.4,
  drawdownPct: 42.7,
  daysSinceLargeLoss: 12,
  autoPauseActive: false,
  status: "normal",
};

const MOCK_ALERT_THRESHOLDS: AlertThresholds = {
  maxDrawdownPct: 15,
  maxSingleLossPct: 5,
  maxDailyLossPct: 8,
  currentDrawdown: 6.4,
  currentSingleLoss: 2.25,
  currentDailyLoss: 3.1,
};

// API Functions
interface ApiPosition {
  symbol: string;
  side?: string;
  size?: number;
  quantity?: number;
  entry_price?: number;
  entryPrice?: number;
  current_price?: number;
  currentPrice?: number;
  unrealized_pnl?: number;
  unrealizedPnl?: number;
  pnl_pct?: number;
  pnlPct?: number;
  stop_loss?: number;
  stopLoss?: number;
  take_profit?: number;
  takeProfit?: number;
  distance_to_sl?: number;
  distanceToSL?: number;
}

interface ApiPortfolioResponse {
  id?: string;
  name?: string;
  positions?: ApiPosition[];
  metrics?: RiskMetrics;
  items?: Array<{ id: string; name: string; [key: string]: unknown }>;
  total?: number;
}

async function fetchPortfolio(): Promise<{ positions: Position[]; metrics: RiskMetrics }> {
  // Fetch portfolio list first to get portfolio IDs
  const listRes = await authFetch("/api/v1/portfolio");
  if (!listRes.ok) throw new Error("Failed to fetch portfolio list");
  const listData: ApiPortfolioResponse = await listRes.json();
  
  // If we have portfolios, fetch the first one's positions
  if (listData.items && listData.items.length > 0) {
    const portfolioId = listData.items[0].id;
    const posRes = await authFetch(`/api/v1/portfolio/${portfolioId}/positions`);
    if (posRes.ok) {
      const posData = await posRes.json();
      const positions: Position[] = (posData.positions || []).map((p: ApiPosition, i: number) => ({
        id: String(i + 1),
        pair: p.symbol || "BTC/USD",
        side: (p.side as "long" | "short") || "long",
        size: p.size || p.quantity || 0,
        entryPrice: p.entry_price || p.entryPrice || 0,
        currentPrice: p.current_price || p.currentPrice || 0,
        unrealizedPnl: p.unrealized_pnl || p.unrealizedPnl || 0,
        pnlPct: p.pnl_pct || p.pnlPct || 0,
        stopLoss: p.stop_loss || p.stopLoss || 0,
        takeProfit: p.take_profit || p.takeProfit || 0,
        distanceToSL: p.distance_to_sl || p.distanceToSL || 0,
      }));
      return { positions, metrics: listData.items[0] as unknown as RiskMetrics };
    }
  }
  return { positions: [], metrics: {
    totalEquity: 0,
    cash: 0,
    marginUsed: 0,
    var95: 0,
    maxDrawdown: 0,
    portfolioBeta: 0,
    correlationBTC: 0,
    correlationETH: 0,
  }};
}

async function fetchExposure(): Promise<Exposure[]> {
  // Fetch from portfolio positions endpoint - calculate exposure from positions
  const listRes = await authFetch("/api/v1/portfolio");
  if (!listRes.ok) throw new Error("Failed to fetch exposure");
  const listData: ApiPortfolioResponse = await listRes.json();
  
  if (listData.items && listData.items.length > 0) {
    const portfolioId = listData.items[0].id;
    const posRes = await authFetch(`/api/v1/portfolio/${portfolioId}/positions`);
    if (posRes.ok) {
      const posData = await posRes.json();
      const exposures: Exposure[] = [];
      const symbolMap = new Map<string, Exposure>();
      
      for (const p of posData.positions || []) {
        const symbol = p.symbol?.replace(/[/USD]/g, "") || "BTC";
        const existing = symbolMap.get(symbol);
        const size = p.size || p.quantity || 0;
        const price = p.current_price || p.currentPrice || 0;
        const value = size * price;
        
        if (existing) {
          if (p.side === "long" || !p.side) {
            existing.long += value;
          }
          if (p.side === "short") {
            existing.short += value;
          }
          existing.total = existing.long + existing.short;
        } else {
          symbolMap.set(symbol, {
            symbol,
            long: p.side === "long" || !p.side ? value : 0,
            short: p.side === "short" ? value : 0,
            total: value,
            pctOfPortfolio: 0,
          });
        }
      }
      
      const totalValue = Array.from(symbolMap.values()).reduce((sum, e) => sum + e.total, 0);
      for (const exp of symbolMap.values()) {
        exp.pctOfPortfolio = totalValue > 0 ? (exp.total / totalValue) * 100 : 0;
        exposures.push(exp);
      }
      return exposures;
    }
  }
  return [];
}

async function fetchRiskMetrics(): Promise<RiskMetrics> {
  // Risk metrics endpoint requires portfolio_id path param - fetch from portfolio list
  const listRes = await authFetch("/api/v1/portfolio");
  if (!listRes.ok) throw new Error("Failed to fetch risk metrics");
  const listData: ApiPortfolioResponse = await listRes.json();
  
  if (listData.items && listData.items.length > 0) {
    const portfolioId = listData.items[0].id;
    const res = await authFetch(`/api/v1/risk/metrics/${portfolioId}`);
    if (res.ok) {
      const data = await res.json();
      return {
        totalEquity: data.total_equity || data.totalEquity || 0,
        cash: data.cash || 0,
        marginUsed: data.margin_used || data.marginUsed || 0,
        var95: data.var_95 || data.var95 || 0,
        maxDrawdown: data.max_drawdown || data.maxDrawdown || 0,
        portfolioBeta: data.portfolio_beta || data.portfolioBeta || 1.0,
        correlationBTC: data.correlation_btc || data.correlationBTC || 0,
        correlationETH: data.correlation_eth || data.correlationETH || 0,
      };
    }
  }
  // Return empty metrics if API calls fail
  return {
    totalEquity: 0,
    cash: 0,
    marginUsed: 0,
    var95: 0,
    maxDrawdown: 0,
    portfolioBeta: 1.0,
    correlationBTC: 0,
    correlationETH: 0,
  };
}

// Components
function MetricCard({
  label,
  value,
  sub,
  trend,
  icon: Icon,
}: {
  label: string;
  value: string;
  sub?: string;
  trend?: "up" | "down" | "neutral";
  icon: React.ElementType;
}) {
  const colorClass =
    trend === "up" ? "text-emerald-400" : trend === "down" ? "text-red-400" : "text-slate-300";
  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-slate-500" />
        <span className="text-slate-400 text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div className={`text-xl font-bold ${colorClass}`}>{value}</div>
      {sub && <div className="text-slate-500 text-xs mt-1">{sub}</div>}
    </div>
  );
}

function ExposureBar({ long, short }: { long: number; short: number }) {
  const total = long + short;
  const longPct = total > 0 ? (long / total) * 100 : 50;
  return (
    <div className="flex h-3 rounded-full overflow-hidden bg-[#1e1e2e]">
      <div className="bg-emerald-500/60" style={{ width: `${longPct}%` }} />
      <div className="bg-red-500/60" style={{ width: `${100 - longPct}%` }} />
    </div>
  );
}

function PositionTable({ positions }: { positions: Position[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#1e1e2e]">
            <th className="text-left px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              Pair
            </th>
            <th className="text-left px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              Side
            </th>
            <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              Size
            </th>
            <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              Entry
            </th>
            <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              Current
            </th>
            <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              Unrealized PnL
            </th>
            <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              SL Distance
            </th>
            <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              Stop Loss
            </th>
            <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">
              Take Profit
            </th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => (
            <tr
              key={pos.id}
              className="border-b border-[#1e1e2e]/50 hover:bg-[#1a1a2e]/50 transition-colors"
            >
              <td className="px-4 py-3">
                <span className="text-white font-medium">{pos.pair}</span>
              </td>
              <td className="px-4 py-3">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    pos.side === "long"
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "bg-red-500/10 text-red-400"
                  }`}
                >
                  {pos.side.toUpperCase()}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-300 text-sm text-right">{pos.size}</td>
              <td className="px-4 py-3 text-slate-300 text-sm text-right">
                ${pos.entryPrice.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-slate-300 text-sm text-right">
                ${pos.currentPrice.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right">
                <div
                  className={`flex items-center justify-end gap-1 text-sm ${
                    pos.unrealizedPnl >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {pos.unrealizedPnl >= 0 ? (
                    <TrendingUp size={12} />
                  ) : (
                    <TrendingDown size={12} />
                  )}
                  <span>
                    {pos.unrealizedPnl >= 0 ? "+" : ""}
                    {pos.unrealizedPnl.toFixed(2)}
                  </span>
                  <span className="text-xs opacity-70">({pos.pnlPct >= 0 ? "+" : ""}{pos.pnlPct.toFixed(2)}%)</span>
                </div>
              </td>
              <td className="px-4 py-3 text-right">
                <span
                  className={`text-sm ${
                    pos.distanceToSL < 3
                      ? "text-red-400"
                      : pos.distanceToSL < 5
                      ? "text-yellow-400"
                      : "text-slate-300"
                  }`}
                >
                  {pos.distanceToSL.toFixed(1)}%
                </span>
              </td>
              <td className="px-4 py-3 text-slate-400 text-sm text-right">
                ${pos.stopLoss.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-slate-400 text-sm text-right">
                ${pos.takeProfit.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExposureChart({ exposures }: { exposures: Exposure[] }) {
  const colors = ["#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#6366f1"];
  const maxPct = Math.max(...exposures.map((e) => e.pctOfPortfolio));

  return (
    <div className="space-y-3">
      {exposures.map((exp, i) => (
        <div key={exp.symbol} className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium">{exp.symbol}</span>
            <span className="text-slate-400">
              {exp.long > 0 ? `L: ${exp.long.toLocaleString()}` : ""}
              {exp.long > 0 && exp.short > 0 ? " | " : ""}
              {exp.short > 0 ? `S: ${exp.short.toLocaleString()}` : ""}
              <span className="ml-2 text-slate-500">({exp.pctOfPortfolio.toFixed(1)}%)</span>
            </span>
          </div>
          <div className="h-2 bg-[#1e1e2e] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(exp.pctOfPortfolio / maxPct) * 100}%`,
                backgroundColor: colors[i % colors.length],
                opacity: 0.7,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function CircuitBreakerPanel({ breaker }: { breaker: CircuitBreaker }) {
  const statusConfig = {
    normal: { color: "bg-emerald-500/10 border-emerald-500/20", text: "text-emerald-400", label: "NORMAL" },
    warning: { color: "bg-yellow-500/10 border-yellow-500/20", text: "text-yellow-400", label: "WARNING" },
    critical: { color: "bg-red-500/10 border-red-500/20", text: "text-red-400", label: "CRITICAL" },
    paused: { color: "bg-purple-500/10 border-purple-500/20", text: "text-purple-400", label: "PAUSED" },
  };

  const config = statusConfig[breaker.status];
  const drawdownProgress = Math.min((breaker.currentDrawdown / breaker.drawdownLimit) * 100, 100);

  return (
    <div className={`p-4 rounded-lg border ${config.color}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Shield size={16} className={config.text} />
          <span className="text-sm font-medium text-white">Circuit Breaker</span>
        </div>
        <span className={`px-2 py-0.5 rounded text-xs font-bold ${config.text} ${config.color}`}>
          {config.label}
        </span>
      </div>

      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-slate-400">Drawdown vs Limit</span>
            <span className={config.text}>
              {breaker.currentDrawdown.toFixed(1)}% / {breaker.drawdownLimit}%
            </span>
          </div>
          <div className="h-3 bg-[#1e1e2e] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                breaker.status === "critical"
                  ? "bg-red-500"
                  : breaker.status === "warning"
                  ? "bg-yellow-500"
                  : "bg-emerald-500"
              }`}
              style={{ width: `${drawdownProgress}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-slate-500" />
            <span className="text-xs text-slate-400">Days since large loss:</span>
            <span className="text-sm font-medium text-white">{breaker.daysSinceLargeLoss}</span>
          </div>
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-slate-500" />
            <span className="text-xs text-slate-400">Auto-pause:</span>
            <span className={`text-sm font-medium ${breaker.autoPauseActive ? "text-purple-400" : "text-slate-400"}`}>
              {breaker.autoPauseActive ? "ACTIVE" : "Inactive"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function AlertThresholdsPanel({ alertThresholds: thresholds }: { alertThresholds: AlertThresholds }) {
  const items = [
    {
      label: "Max Drawdown",
      current: thresholds.currentDrawdown,
      max: thresholds.maxDrawdownPct,
      color: "emerald",
    },
    {
      label: "Max Single Trade Loss",
      current: thresholds.currentSingleLoss,
      max: thresholds.maxSingleLossPct,
      color: "yellow",
    },
    {
      label: "Max Daily Loss",
      current: thresholds.currentDailyLoss,
      max: thresholds.maxDailyLossPct,
      color: "red",
    },
  ];

  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle size={14} className="text-slate-400" />
        <span className="text-sm font-medium text-white">Alert Thresholds</span>
      </div>

      <div className="space-y-3">
        {items.map((item) => {
          const pct = (item.current / item.max) * 100;
          const isBreached = item.current >= item.max;
          const colorClass =
            item.color === "emerald"
              ? "bg-emerald-500"
              : item.color === "yellow"
              ? "bg-yellow-500"
              : "bg-red-500";

          return (
            <div key={item.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">{item.label}</span>
                <span className={isBreached ? "text-red-400 font-medium" : "text-slate-300"}>
                  {item.current.toFixed(1)}% / {item.max}%
                </span>
              </div>
              <div className="h-1.5 bg-[#1e1e2e] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${colorClass} ${isBreached ? "animate-pulse" : ""}`}
                  style={{ width: `${Math.min(pct, 100)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Main Component
// TanStack Query hooks for real data
export default function RiskPage() {
  const { data: portfolioData } = useQuery({
    queryKey: ["risk-portfolio"],
    queryFn: fetchPortfolio,
    refetchInterval: 10000,
  });

  const { data: exposureData } = useQuery({
    queryKey: ["risk-exposure"],
    queryFn: fetchExposure,
    refetchInterval: 10000,
  });

  const { data: metricsData } = useQuery({
    queryKey: ["risk-metrics"],
    queryFn: fetchRiskMetrics,
    refetchInterval: 10000,
  });

  // Use real data when available, fall back to mock data
  const positions = portfolioData?.positions?.length ? portfolioData.positions : MOCK_POSITIONS;
  const exposures = exposureData?.length ? exposureData : MOCK_EXPOSURE;
  const metrics = metricsData && metricsData.totalEquity > 0 ? metricsData : MOCK_RISK_METRICS;
  const circuitBreaker = MOCK_CIRCUIT_BREAKER;
  const alertThresholds = MOCK_ALERT_THRESHOLDS;

  const totalLong = exposures.reduce((sum, e) => sum + e.long, 0);
  const totalShort = exposures.reduce((sum, e) => sum + e.short, 0);
  const totalExposure = totalLong + totalShort;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Shield size={24} className="text-blue-400" />
            Risk Monitor
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time exposure tracking and risk management
          </p>
        </div>
        <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e1e2e] border border-[#1e1e2e] text-slate-400 hover:text-white hover:border-slate-500 transition-all text-sm">
          <Settings size={14} />
          Configure
        </button>
      </div>

      {/* Portfolio Overview */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Total Equity"
          value={`$${metrics.totalEquity.toLocaleString()}`}
          sub={`Cash: $${metrics.cash.toLocaleString()}`}
          icon={Activity}
        />
        <MetricCard
          label="Margin Used"
          value={`$${metrics.marginUsed.toLocaleString()}`}
          sub={`${((metrics.marginUsed / metrics.totalEquity) * 100).toFixed(1)}% of equity`}
          icon={PieChart}
        />
        <MetricCard
          label="VaR (95%)"
          value={`$${metrics.var95.toLocaleString()}`}
          sub="1-day Value at Risk"
          trend="down"
          icon={AlertTriangle}
        />
        <MetricCard
          label="Max Drawdown"
          value={`${metrics.maxDrawdown.toFixed(1)}%`}
          sub="Current drawdown"
          trend={metrics.maxDrawdown > 5 ? "down" : "neutral"}
          icon={TrendingDown}
        />
      </div>

      {/* Exposure Overview */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-white flex items-center gap-2">
              <PieChart size={14} className="text-slate-400" />
              Portfolio Exposure
            </h2>
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-emerald-500/60" />
                <span className="text-slate-400">Long {totalLong.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-red-500/60" />
                <span className="text-slate-400">Short {totalShort.toLocaleString()}</span>
              </div>
            </div>
          </div>
          <ExposureBar long={totalLong} short={totalShort} />
          <div className="mt-4">
            <ExposureChart exposures={exposures} />
          </div>
        </div>

        <div className="space-y-4">
          <CircuitBreakerPanel breaker={circuitBreaker} />
          <AlertThresholdsPanel alertThresholds={alertThresholds} />
        </div>
      </div>

      {/* Risk Metrics */}
      <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
        <h2 className="text-sm font-medium text-white flex items-center gap-2 mb-4">
          <Activity size={14} className="text-slate-400" />
          Risk Metrics
        </h2>
        <div className="grid grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-white">
              {metrics.portfolioBeta.toFixed(2)}
            </div>
            <div className="text-xs text-slate-400 mt-1">Portfolio Beta (BTC)</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">
              {metrics.correlationBTC.toFixed(2)}
            </div>
            <div className="text-xs text-slate-400 mt-1">BTC Correlation</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">
              {metrics.correlationETH.toFixed(2)}
            </div>
            <div className="text-xs text-slate-400 mt-1">ETH Correlation</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">
              {((totalExposure / metrics.totalEquity) * 100).toFixed(1)}%
            </div>
            <div className="text-xs text-slate-400 mt-1">Total Exposure</div>
          </div>
        </div>
      </div>

      {/* Position Table */}
      <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[#1e1e2e]">
          <h2 className="text-sm font-medium text-white flex items-center gap-2">
            <Activity size={14} className="text-slate-400" />
            Active Positions
          </h2>
        </div>
        <PositionTable positions={positions} />
        {positions.length === 0 && (
          <div className="py-12 text-center text-slate-500">
            <Activity size={32} className="mx-auto mb-3 opacity-50" />
            <p>No active positions</p>
          </div>
        )}
      </div>

      {/* Sector Exposure */}
      <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
        <h2 className="text-sm font-medium text-white flex items-center gap-2 mb-4">
          <PieChart size={14} className="text-slate-400" />
          Asset Class Exposure
        </h2>
        <div className="grid grid-cols-3 gap-8">
          <div>
            <div className="text-xs text-slate-400 mb-2">Crypto</div>
            <div className="text-xl font-bold text-white">68.4%</div>
            <div className="text-xs text-slate-500 mt-1">${(metrics.totalEquity * 0.684).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 mb-2">Stables</div>
            <div className="text-xl font-bold text-white">30.9%</div>
            <div className="text-xs text-slate-500 mt-1">${(metrics.totalEquity * 0.309).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 mb-2">FX</div>
            <div className="text-xl font-bold text-slate-400">0.7%</div>
            <div className="text-xs text-slate-500 mt-1">${(metrics.totalEquity * 0.007).toLocaleString()}</div>
          </div>
        </div>
      </div>
    </div>
  );
}