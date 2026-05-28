"use client";

import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { createChart, IChartApi, ISeriesApi, LineData, Time } from "lightweight-charts";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { X, TrendingUp, TrendingDown, Minus, BarChart3, GitCompare, Info } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

// ─── Types ───────────────────────────────────────────────────────────────────

interface StrategyResult {
  id: string;
  strategy_id: string;
  strategy_name: string;
  total_return: number;
  annualized_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  win_rate: number;
  profit_factor: number;
  expectancy: number;
  total_trades: number;
  best_month: number;
  worst_month: number;
  volatility: number;
  equity_curve: Array<{ timestamp: string; equity: number }>;
}

interface StrategyOption {
  id: string;
  name: string;
}

// ─── API Helpers ──────────────────────────────────────────────────────────────

interface BacktestResult {
  id: string;
  config_id: string;
  pair: string | null;
  timeframe: string | null;
  strategy_id: string | null;
  status: string;
  progress_pct: number;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  initial_capital: number | null;
  final_equity: number | null;
  total_return: number | null;
  annualized_return: number | null;
  max_drawdown: number | null;
  max_drawdown_pct: number | null;
  max_drawdown_duration_days: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  calmar_ratio: number | null;
  profit_factor: number | null;
  win_rate: number | null;
  expectancy: number | null;
  total_trades: number | null;
  equity_curve: { curve?: number[] } | null;
}

interface StrategyOption {
  id: string;
  name: string;
}

async function fetchBacktestList(): Promise<BacktestResult[]> {
  const res = await authFetch("/api/v1/backtest?limit=50");
  if (!res.ok) throw new Error("Failed to fetch backtests");
  return res.json();
}

async function fetchBacktestEquity(backtestId: string): Promise<{ equity_curve: { curve?: number[] } }> {
  const res = await authFetch(`/api/v1/backtest/${backtestId}/equity`);
  if (!res.ok) throw new Error("Failed to fetch equity curve");
  return res.json();
}

function transformBacktestToStrategyResult(bt: BacktestResult, equityCurve: { equity_curve?: { curve?: number[] } } | null): StrategyResult {
  const equityData = equityCurve?.equity_curve;
  const equityArray = equityData?.curve || [];
  return {
    id: bt.id,
    strategy_id: bt.strategy_id || bt.config_id || bt.id,
    strategy_name: bt.strategy_id || `Backtest ${bt.id.slice(0, 8)}`,
    total_return: bt.total_return != null ? bt.total_return * 100 : 0,
    annualized_return: bt.annualized_return != null ? bt.annualized_return * 100 : 0,
    max_drawdown: bt.max_drawdown_pct != null ? -bt.max_drawdown_pct : 0,
    sharpe_ratio: bt.sharpe_ratio || 0,
    sortino_ratio: bt.sortino_ratio || 0,
    calmar_ratio: bt.calmar_ratio || 0,
    win_rate: bt.win_rate != null ? bt.win_rate * 100 : 0,
    profit_factor: bt.profit_factor || 0,
    expectancy: bt.expectancy || 0,
    total_trades: bt.total_trades || 0,
    best_month: 0,
    worst_month: 0,
    volatility: 0,
    equity_curve: equityArray.map((value, index) => ({
      timestamp: new Date(Date.now() - (equityArray.length - index) * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
      equity: value,
    })),
  };
}

async function fetchStrategyResults(strategyId: string): Promise<StrategyResult> {
  const btId = strategyId.startsWith("bt_") ? strategyId.replace("bt_", "") : strategyId;
  const [btRes, equityRes] = await Promise.all([
    authFetch(`/api/v1/backtest/${btId}`),
    fetchBacktestEquity(btId),
  ]);
  if (!btRes.ok) throw new Error(`Failed to fetch backtest ${strategyId}`);
  const bt: BacktestResult = await btRes.json();
  return transformBacktestToStrategyResult(bt, equityRes);
}

async function fetchBacktestResults(strategyId: string): Promise<StrategyResult[]> {
  // Get backtest by strategy id (config_id)
  const res = await authFetch(`/api/v1/backtest/${strategyId}`);
  if (!res.ok) return [];
  const bt: BacktestResult = await res.json();
  const equityRes = await fetchBacktestEquity(strategyId);
  return [transformBacktestToStrategyResult(bt, equityRes)];
}

// ─── Chart Colors ─────────────────────────────────────────────────────────────

const CHART_COLORS = [
  "#6366f1", // primary
  "#10b981", // accent
  "#f59e0b", // warning
  "#ef4444", // danger
  "#8b5cf6", // purple
];

// ─── Helper Functions ─────────────────────────────────────────────────────────

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

function normalizeEquityCurve(curve: Array<{ timestamp: string; equity: number }>): LineData[] {
  if (!curve || curve.length === 0) return [];
  const base = curve[0].equity;
  return curve.map((point) => ({
    time: point.timestamp as Time,
    value: ((point.equity - base) / base) * 100,
  }));
}

function calculateCorrelation(curve1: LineData[], curve2: LineData[]): number {
  if (curve1.length !== curve2.length || curve1.length < 2) return 0;
  const n = curve1.length;
  const mean1 = curve1.reduce((s, p) => s + p.value, 0) / n;
  const mean2 = curve2.reduce((s, p) => s + p.value, 0) / n;
  let num = 0, den1 = 0, den2 = 0;
  for (let i = 0; i < n; i++) {
    const d1 = curve1[i].value - mean1;
    const d2 = curve2[i].value - mean2;
    num += d1 * d2;
    den1 += d1 * d1;
    den2 += d2 * d2;
  }
  const den = Math.sqrt(den1 * den2);
  return den === 0 ? 0 : num / den;
}

// ─── Components ───────────────────────────────────────────────────────────────

function MetricCell({ value, best, worst }: { value: number; best?: boolean; worst?: boolean }) {
  const isPositive = value >= 0;
  const isNegative = value < 0;

  return (
    <td className="px-4 py-3">
      <div className="flex items-center gap-2">
        <span
          className={`font-mono text-sm ${
            best
              ? "text-accent font-semibold"
              : worst
              ? "text-red-500 font-semibold"
              : "text-text-primary"
          }`}
        >
          {typeof value === "number" && Math.abs(value) < 100
            ? formatPercent(value)
            : formatNumber(value, 2)}
        </span>
        {best && (
          <TrendingUp className="h-3.5 w-3.5 text-accent shrink-0" />
        )}
        {worst && (
          <TrendingDown className="h-3.5 w-3.5 text-red-500 shrink-0" />
        )}
      </div>
    </td>
  );
}

function CorrelationCell({ value }: { value: number }) {
  const intensity = Math.abs(value);
  const isPositive = value >= 0;
  const bgColor = isPositive
    ? `rgba(16, 185, 129, ${intensity * 0.6})`
    : `rgba(239, 68, 68, ${intensity * 0.6})`;
  const textColor = intensity > 0.5 ? "text-white" : "text-text-primary";

  return (
    <td className="px-2 py-2">
      <div
        className="w-full h-8 flex items-center justify-center rounded text-xs font-mono font-semibold"
        style={{ backgroundColor: bgColor, minWidth: "52px" }}
      >
        <span className={textColor}>{value.toFixed(2)}</span>
      </div>
    </td>
  );
}

function MiniBarChart({ values, color }: { values: number[]; color: string }) {
  const max = Math.max(...values.map(Math.abs));
  const min = Math.min(...values.map(Math.abs));
  const range = max - min || 1;

  return (
    <div className="flex items-end gap-0.5 h-12">
      {values.map((v, i) => {
        const height = ((Math.abs(v) - min) / range) * 100 || 10;
        const isPositive = v >= 0;
        return (
          <div
            key={i}
            className="w-3 rounded-sm"
            style={{
              height: `${Math.max(height, 10)}%`,
              backgroundColor: isPositive ? color : "#ef4444",
              opacity: 0.7 + (i / values.length) * 0.3,
            }}
          />
        );
      })}
    </div>
  );
}

// ─── Main Page Component ──────────────────────────────────────────────────────

export default function ComparePage() {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Fetch backtest list from API for strategy options
  const { data: backtestList } = useQuery({
    queryKey: ["backtest-list"],
    queryFn: fetchBacktestList,
    staleTime: 30000,
  });

  // Build strategy options from real backtest data
  const realStrategies: StrategyOption[] = useMemo(() => {
    if (!backtestList) return [];
    const completedBacktests = backtestList.filter((bt) => bt.status === "completed" && bt.equity_curve);
    if (completedBacktests.length === 0) return [];
    return completedBacktests.map((bt) => ({
      id: bt.id,
      name: bt.strategy_id || `Backtest ${bt.id.slice(0, 8)} (${bt.pair || "BTC/USDT"})`,
    }));
  }, [backtestList]);

  // Fetch results for selected strategies
  const selectedResults = useQuery({
    queryKey: ["compare-results", selectedIds],
    queryFn: async () => {
      const results = await Promise.all(selectedIds.map(fetchStrategyResults));
      return results;
    },
    enabled: selectedIds.length > 0,
  });

  // Filtered strategy options
  const availableStrategies = useMemo(() => {
    return realStrategies.filter(
      (s) =>
        !selectedIds.includes(s.id) &&
        s.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [realStrategies, selectedIds, searchQuery]);

  // Add strategy
  const addStrategy = useCallback(
    (id: string) => {
      if (selectedIds.length >= 5) return;
      setSelectedIds((prev) => [...prev, id]);
      setSearchQuery("");
      setDropdownOpen(false);
    },
    [selectedIds]
  );

  // Remove strategy
  const removeStrategy = useCallback((id: string) => {
    setSelectedIds((prev) => prev.filter((s) => s !== id));
  }, []);

  // Normalized equity curves for overlay
  const normalizedCurves = useMemo(() => {
    if (!selectedResults.data) return [];
    return selectedResults.data.map((r) => ({
      id: r.strategy_id,
      name: r.strategy_name,
      normalized: normalizeEquityCurve(r.equity_curve),
    }));
  }, [selectedResults.data]);

  // Correlation matrix
  const correlationMatrix = useMemo(() => {
    if (normalizedCurves.length < 2) return [];
    const matrix: number[][] = [];
    for (let i = 0; i < normalizedCurves.length; i++) {
      matrix[i] = [];
      for (let j = 0; j < normalizedCurves.length; j++) {
        if (i === j) {
          matrix[i][j] = 1;
        } else if (j < i) {
          matrix[i][j] = matrix[j][i];
        } else {
          matrix[i][j] = calculateCorrelation(normalizedCurves[i].normalized, normalizedCurves[j].normalized);
        }
      }
    }
    return matrix;
  }, [normalizedCurves]);

  // Metrics config
  const METRICS = [
    { key: "total_return", label: "Total Return", unit: "percent", higherBetter: true },
    { key: "annualized_return", label: "Annualized Return", unit: "percent", higherBetter: true },
    { key: "max_drawdown", label: "Max Drawdown", unit: "percent", higherBetter: false },
    { key: "sharpe_ratio", label: "Sharpe Ratio", unit: "number", higherBetter: true },
    { key: "sortino_ratio", label: "Sortino Ratio", unit: "number", higherBetter: true },
    { key: "calmar_ratio", label: "Calmar Ratio", unit: "number", higherBetter: true },
    { key: "win_rate", label: "Win Rate", unit: "percent", higherBetter: true },
    { key: "profit_factor", label: "Profit Factor", unit: "number", higherBetter: true },
    { key: "expectancy", label: "Expectancy", unit: "number", higherBetter: true },
    { key: "total_trades", label: "Total Trades", unit: "number", higherBetter: true },
    { key: "best_month", label: "Best Month", unit: "percent", higherBetter: true },
    { key: "worst_month", label: "Worst Month", unit: "percent", higherBetter: false },
    { key: "volatility", label: "Volatility", unit: "percent", higherBetter: false },
  ];

  // Find best/worst per metric
  const getBestWorst = useCallback(
    (metricKey: string, higherBetter: boolean) => {
      if (!selectedResults.data || selectedResults.data.length === 0)
        return { best: null, worst: null };
      const values = selectedResults.data.map((r) => ({
        id: r.strategy_id,
        value: r[metricKey as keyof StrategyResult] as number,
      }));
      if (higherBetter) {
        const bestVal = Math.max(...values.map((v) => v.value));
        const worstVal = Math.min(...values.map((v) => v.value));
        return {
          best: values.find((v) => v.value === bestVal)?.id || null,
          worst: values.find((v) => v.value === worstVal)?.id || null,
        };
      } else {
        const bestVal = Math.min(...values.map((v) => v.value));
        const worstVal = Math.max(...values.map((v) => v.value));
        return {
          best: values.find((v) => v.value === bestVal)?.id || null,
          worst: values.find((v) => v.value === worstVal)?.id || null,
        };
      }
    },
    [selectedResults.data]
  );

  // Equity curve chart
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line">[]>([]);

  useEffect(() => {
    if (!chartContainerRef.current) return;
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = [];
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#64748b",
        fontFamily: "Inter, system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: "#1e1e2e" },
        horzLines: { color: "#1e1e2e" },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: "#6366f1", labelBackgroundColor: "#6366f1" },
        horzLine: { color: "#6366f1", labelBackgroundColor: "#6366f1" },
      },
      rightPriceScale: {
        borderColor: "#1e1e2e",
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: "#1e1e2e",
        timeVisible: true,
      },
      handleScroll: true,
      handleScale: true,
    });

    chartRef.current = chart;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = [];
      }
    };
  }, []);

  // Update chart when curves change
  useEffect(() => {
    if (!chartRef.current || normalizedCurves.length === 0) return;

    // Remove old series
    for (const s of seriesRef.current) {
      chartRef.current.removeSeries(s);
    }
    seriesRef.current = [];

    // Add new series
    for (let i = 0; i < normalizedCurves.length; i++) {
      const curve = normalizedCurves[i];
      if (curve.normalized.length === 0) continue;
      const series = chartRef.current.addLineSeries({
        color: CHART_COLORS[i % CHART_COLORS.length],
        lineWidth: 2,
        visible: true,
        priceLineVisible: false,
        lastValueVisible: true,
        title: curve.name,
      });
      series.setData(curve.normalized);
      seriesRef.current.push(series);
    }

    // Fit content
    chartRef.current.timeScale().fitContent();
  }, [normalizedCurves]);

  // Trade distribution data (mock histogram bins)
  const tradeDistributionData = useMemo(() => {
    if (!selectedResults.data || selectedResults.data.length === 0) return [];
    return selectedResults.data.map((r) => {
      // Generate mock trade PnL distribution
      const trades = [];
      for (let i = 0; i < Math.min(r.total_trades, 50); i++) {
        const pct = (Math.random() - 0.45) * 8; // roughly centered, some negative bias
        trades.push(pct);
      }
      // Bin into 10 buckets from -5% to +5%
      const buckets = Array(10).fill(0);
      const bucketSize = 1;
      for (const t of trades) {
        const idx = Math.floor((t + 5) / bucketSize);
        if (idx >= 0 && idx < 10) buckets[idx]++;
      }
      return {
        id: r.strategy_id,
        name: r.strategy_name,
        buckets,
      };
    });
  }, [selectedResults.data]);

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Strategy Compare</h1>
          <p className="text-sm text-text-muted mt-1">
            Compare up to 5 strategies side-by-side
          </p>
        </div>
        {selectedIds.length > 0 && (
          <div className="flex items-center gap-2">
            <Badge variant="info">{selectedIds.length} selected</Badge>
            {selectedIds.length < 5 && (
              <Badge variant="default">max 5</Badge>
            )}
          </div>
        )}
      </div>

      {/* Strategy Selector */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <GitCompare className="h-4 w-4 text-primary" />
            Select Strategies
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Selected strategy cards */}
            {selectedIds.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {selectedIds.map((id, index) => {
                  const strategy = realStrategies.find((s) => s.id === id);
                  return (
                    <div
                      key={id}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg border"
                      style={{
                        borderColor: CHART_COLORS[index % CHART_COLORS.length],
                        backgroundColor: `${CHART_COLORS[index % CHART_COLORS.length]}15`,
                      }}
                    >
                      <div
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                      />
                      <span className="text-sm font-medium text-text-primary">
                        {strategy?.name || id}
                      </span>
                      <button
                        onClick={() => removeStrategy(id)}
                        className="ml-1 rounded p-0.5 hover:bg-border text-text-muted hover:text-text-primary transition-colors"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Dropdown selector */}
            {selectedIds.length < 5 && (
              <div className="relative">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Search strategies..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setDropdownOpen(true);
                    }}
                    onFocus={() => setDropdownOpen(true)}
                    className="flex h-10 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>

                {dropdownOpen && (
                  <div className="absolute z-50 mt-1 w-full rounded-lg border border-border bg-card shadow-xl max-h-64 overflow-y-auto">
                    {availableStrategies.length === 0 ? (
                      <div className="px-4 py-3 text-sm text-text-muted">
                        {searchQuery ? "No matching strategies" : "All strategies selected"}
                      </div>
                    ) : (
                      availableStrategies.map((strategy) => (
                        <button
                          key={strategy.id}
                          onClick={() => addStrategy(strategy.id)}
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-border text-text-primary transition-colors"
                        >
                          <div className="h-2 w-2 rounded-full bg-primary opacity-60" />
                          {strategy.name}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}

            {selectedIds.length === 0 && (
              <div className="flex items-center gap-2 text-sm text-text-muted py-2">
                <Info className="h-4 w-4" />
                Select at least one strategy to begin comparison
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {selectedIds.length > 0 && (
        <>
          {/* Equity Curve Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-primary" />
                Equity Curve Overlay
                <span className="text-xs text-text-muted font-normal ml-2">
                  (normalized % returns)
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div
                ref={chartContainerRef}
                className="h-72 w-full rounded-lg overflow-hidden"
              />
              {/* Legend */}
              <div className="flex flex-wrap gap-4 mt-3">
                {normalizedCurves.map((curve, i) => (
                  <div key={curve.id} className="flex items-center gap-1.5">
                    <div
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                    />
                    <span className="text-xs text-text-secondary">{curve.name}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Metrics Comparison Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-primary" />
                Performance Metrics
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide w-44">
                        Metric
                      </th>
                      {selectedIds.map((id, i) => {
                        const strategy = realStrategies.find((s) => s.id === id);
                        return (
                          <th key={id} className="px-4 py-3 text-center">
                            <div className="flex items-center justify-center gap-2">
                              <div
                                className="h-2 w-2 rounded-full"
                                style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                              />
                              <span className="text-xs font-medium text-text-primary">
                                {strategy?.name || id}
                              </span>
                            </div>
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {METRICS.map((metric) => {
                      const { best, worst } = getBestWorst(metric.key, metric.higherBetter);
                      return (
                        <tr key={metric.key} className="border-b border-border/50 hover:bg-card/50 transition-colors">
                          <td className="px-4 py-3 text-sm text-text-secondary">
                            {metric.label}
                          </td>
                          {selectedIds.map((id) => {
                            const result = selectedResults.data?.find((r) => r.strategy_id === id);
                            const value = result
                              ? (result[metric.key as keyof StrategyResult] as number)
                              : 0;
                            return (
                              <MetricCell
                                key={id}
                                value={value}
                                best={best === id}
                                worst={worst === id}
                              />
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Trade Distribution */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-primary" />
                Trade PnL Distribution
              </CardTitle>
            </CardHeader>
            <CardContent>
              {tradeDistributionData.length > 0 ? (
                <div className="space-y-6">
                  {/* Simplified histogram visualization */}
                  <div className="overflow-x-auto">
                    <div className="flex items-end gap-3 min-w-max">
                      {tradeDistributionData.map((strategy, idx) => (
                        <div key={strategy.id} className="flex flex-col items-center gap-2">
                          <div className="flex items-end gap-0.5 h-24">
                            {strategy.buckets.map((count, bucketIdx) => {
                              const maxCount = Math.max(...tradeDistributionData.map((s) => Math.max(...s.buckets)));
                              const height = maxCount > 0 ? (count / maxCount) * 96 : 0;
                              return (
                                <div
                                  key={bucketIdx}
                                  className="w-4 rounded-sm transition-all"
                                  style={{
                                    height: `${Math.max(height, 2)}%`,
                                    backgroundColor: CHART_COLORS[idx % CHART_COLORS.length],
                                    opacity: 0.5 + (bucketIdx / 10) * 0.5,
                                  }}
                                  title={`${((bucketIdx - 5) * 1).toFixed(0)}% to ${((bucketIdx - 4) * 1).toFixed(0)}%: ${count} trades`}
                                />
                              );
                            })}
                          </div>
                          <span className="text-xs text-text-muted">{strategy.name.split(" ")[0]}</span>
                        </div>
                      ))}
                    </div>
                    {/* X-axis labels */}
                    <div className="flex justify-between mt-2 text-xs text-text-muted">
                      <span>-5%</span>
                      <span>0%</span>
                      <span>+5%</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-text-muted text-sm">
                  Loading trade distribution...
                </div>
              )}
            </CardContent>
          </Card>

          {/* Correlation Heatmap */}
          {selectedIds.length >= 2 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <GitCompare className="h-4 w-4 text-primary" />
                  Equity Curve Correlation
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr>
                        <th className="px-2 py-2" />
                        {normalizedCurves.map((curve, i) => (
                          <th key={curve.id} className="px-2 py-2 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <div
                                className="h-2 w-2 rounded-full"
                                style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                              />
                              <span className="text-xs text-text-secondary truncate max-w-[60px]">
                                {curve.name.split(" ")[0]}
                              </span>
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {correlationMatrix.map((row, i) => (
                        <tr key={i}>
                          <td className="px-2 py-2">
                            <div className="flex items-center gap-1.5">
                              <div
                                className="h-2 w-2 rounded-full"
                                style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                              />
                              <span className="text-xs text-text-secondary">
                                {normalizedCurves[i]?.name.split(" ")[0] || ""}
                              </span>
                            </div>
                          </td>
                          {row.map((value, j) => (
                            <CorrelationCell key={j} value={value} />
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center gap-4 mt-3 text-xs text-text-muted">
                  <div className="flex items-center gap-1.5">
                    <div className="h-3 w-3 rounded-sm" style={{ backgroundColor: "rgba(16, 185, 129, 0.6)" }} />
                    <span>Positive correlation</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="h-3 w-3 rounded-sm" style={{ backgroundColor: "rgba(239, 68, 68, 0.6)" }} />
                    <span>Negative correlation</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Best Total Return */}
            {(() => {
              const { best } = getBestWorst("total_return", true);
              const result = selectedResults.data?.find((r) => r.strategy_id === best);
              return (
                <Card className="border-accent/30">
                  <CardContent className="pt-4">
                    <p className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      Best Total Return
                    </p>
                    <p className="text-2xl font-bold font-mono text-accent mt-1">
                      {result ? formatPercent(result.total_return) : "—"}
                    </p>
                    <p className="text-xs text-text-secondary mt-1">
                      {result?.strategy_name || ""}
                    </p>
                  </CardContent>
                </Card>
              );
            })()}

            {/* Lowest Max Drawdown */}
            {(() => {
              const { best } = getBestWorst("max_drawdown", false);
              const result = selectedResults.data?.find((r) => r.strategy_id === best);
              return (
                <Card className="border-accent/30">
                  <CardContent className="pt-4">
                    <p className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      Lowest Drawdown
                    </p>
                    <p className="text-2xl font-bold font-mono text-accent mt-1">
                      {result ? formatPercent(result.max_drawdown) : "—"}
                    </p>
                    <p className="text-xs text-text-secondary mt-1">
                      {result?.strategy_name || ""}
                    </p>
                  </CardContent>
                </Card>
              );
            })()}

            {/* Best Sharpe */}
            {(() => {
              const { best } = getBestWorst("sharpe_ratio", true);
              const result = selectedResults.data?.find((r) => r.strategy_id === best);
              return (
                <Card className="border-primary/30">
                  <CardContent className="pt-4">
                    <p className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      Best Risk-Adj Return
                    </p>
                    <p className="text-2xl font-bold font-mono text-primary mt-1">
                      {result ? formatNumber(result.sharpe_ratio, 2) : "—"}
                    </p>
                    <p className="text-xs text-text-secondary mt-1">
                      {result?.strategy_name || ""}
                    </p>
                  </CardContent>
                </Card>
              );
            })()}

            {/* Best Win Rate */}
            {(() => {
              const { best } = getBestWorst("win_rate", true);
              const result = selectedResults.data?.find((r) => r.strategy_id === best);
              return (
                <Card className="border-warning/30">
                  <CardContent className="pt-4">
                    <p className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      Highest Win Rate
                    </p>
                    <p className="text-2xl font-bold font-mono text-warning mt-1">
                      {result ? formatPercent(result.win_rate) : "—"}
                    </p>
                    <p className="text-xs text-text-secondary mt-1">
                      {result?.strategy_name || ""}
                    </p>
                  </CardContent>
                </Card>
              );
            })()}
          </div>
        </>
      )}

      {/* Empty State */}
      {selectedIds.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="h-16 w-16 rounded-full bg-card border border-border flex items-center justify-center mb-4">
            <GitCompare className="h-8 w-8 text-text-muted" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary mb-1">
            No Strategies Selected
          </h3>
          <p className="text-sm text-text-muted max-w-sm">
            Select strategies from the dropdown above to compare their performance,
            equity curves, and risk metrics side-by-side.
          </p>
        </div>
      )}
    </div>
  );
}