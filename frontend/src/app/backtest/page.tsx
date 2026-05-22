"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useForm, Controller } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useMutation } from "@tanstack/react-query";
import { BarChart3, Play, ChevronRight, ChevronLeft, ArrowRight, TrendingUp, DollarSign, Settings2, Zap, CheckCircle2, X, AlertCircle, Plus, Trash2, PieChart } from "lucide-react";

// ─── Schema ────────────────────────────────────────────────────────────────

const formSchema = z.object({
  // Step 1: Strategy
  strategy: z.string().min(1, "Select a strategy"),
  strategy_params: z.record(z.union([z.string(), z.number()])).optional(),
  // Step 2: Universe
  pairs: z.array(z.string()).min(1, "Select at least one pair"),
  timeframes: z.array(z.string()).min(1, "Select at least one timeframe"),
  start_date: z.string().min(1, "Required"),
  end_date: z.string().min(1, "Required"),
  // Step 3: Capital & Risk
  initial_capital: z.number().min(100).max(10000000),
  leverage: z.number().min(1).max(100),
  position_sizing: z.string(),
  max_positions: z.number().int().min(1).max(20),
  direction: z.string(),
  // Step 4: Costs
  maker_fee: z.number().min(0).max(1),
  taker_fee: z.number().min(0).max(1),
  slippage_model: z.string(),
  slippage_bps: z.number().min(0).max(100).optional(),
  // Step 5: Advanced
  walk_forward: z.string(),
  walk_forward_train_days: z.number().int().min(7).optional(),
  walk_forward_test_days: z.number().int().min(1).optional(),
  walk_forward_skip_days: z.number().int().min(0).optional(),
  monte_carlo: z.string(),
  monte_carlo_runs: z.number().int().min(10).max(2000).optional(),
});

type FormValues = z.infer<typeof formSchema>;

// ─── Defaults ──────────────────────────────────────────────────────────────

const DEFAULT_VALUES: FormValues = {
  strategy: "ma_cross",
  pairs: ["BTC/USDT"],
  timeframes: ["4h"],
  start_date: (() => {
    const d = new Date();
    d.setDate(d.getDate() - 60);
    return d.toISOString().split("T")[0];
  })(),
  end_date: (() => new Date().toISOString().split("T")[0])(),
  initial_capital: 10000,
  leverage: 1,
  position_sizing: "pct_equal",
  max_positions: 5,
  direction: "both",
  maker_fee: 0.0002,
  taker_fee: 0.0004,
  slippage_model: "dynamic",
  slippage_bps: 5,
  walk_forward: "off",
  walk_forward_train_days: 60,
  walk_forward_test_days: 14,
  walk_forward_skip_days: 0,
  monte_carlo: "off",
  monte_carlo_runs: 500,
};

const STRATEGIES = [
  { id: "ma_cross", label: "MA Cross", desc: "Fast/slow SMA crossover" },
  { id: "rsi", label: "RSI", desc: "RSI mean-reversion" },
  { id: "bollinger", label: "Bollinger", desc: "Bollinger Bands breakout" },
  { id: "macd", label: "MACD", desc: "MACD momentum" },
];

const PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT", "MATIC/USDT", "LINK/USDT", "DOT/USDT", "AAVE/USDT", "UNI/USDT"];
const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];
const POSITION_SIZING = [
  { id: "pct_equal", label: "Equal %" },
  { id: "pct_ranked", label: "Ranked %" },
  { id: "fixed_lot", label: "Fixed $ per trade" },
  { id: "atr", label: "ATR-based" },
  { id: "kelly", label: "Kelly Criterion" },
];
const DIRECTION_OPTIONS = [
  { id: "both", label: "Long & Short" },
  { id: "long_only", label: "Long Only" },
  { id: "short_only", label: "Short Only" },
];

// ─── Fetch helpers ─────────────────────────────────────────────────────────

async function fetchMarkets(exchange: string): Promise<Record<string, { base: string; quote: string }>> {
  const res = await fetch(`/api/v1/data/markets?exchange=${exchange}&quote=USDT`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.markets ?? {};
}

async function fetchStrategies(): Promise<{ strategies: Array<{ name: string; description: string }> }> {
  const res = await fetch(`/api/v1/signals`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function runBacktest(payload: FormValues): Promise<any> {
  const res = await fetch(`/api/v1/backtest/quick-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

async function runPortfolioBacktest(payload: {
  name: string;
  strategies: Array<{ strategy: string; symbols: string[]; weight?: number; strategy_params?: object }>;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission_pct: number;
  slippage_pct: number;
  leverage: number;
  max_positions: number;
  exchange: "binance";
  timeframe: string;
  max_sector_exposure: number;
  correlation_threshold: number;
  correlation_reduction: number;
  max_drawdown_pct: number;
}): Promise<any> {
  const res = await fetch(`/api/v1/backtest/portfolio`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

async function runPortfolioWalkForward(payload: {
  name: string;
  strategies: Array<{ strategy: string; symbols: string[]; weight?: number; strategy_params?: object }>;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission_pct: number;
  slippage_pct: number;
  leverage: number;
  max_positions: number;
  exchange: "binance";
  timeframe: string;
  max_sector_exposure: number;
  correlation_threshold: number;
  correlation_reduction: number;
  max_drawdown_pct: number;
  train_days: number;
  test_days: number;
  skip_days: number;
}): Promise<any> {
  const res = await fetch(`/api/v1/backtest/portfolio-walk-forward`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Step components ───────────────────────────────────────────────────────

function StepIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {Array.from({ length: total }, (_, i) => {
        const num = i + 1;
        const done = num < current;
        const active = num === current;
        return (
          <div key={num} className="flex items-center gap-2">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                done ? "bg-emerald-500 text-white" : active ? "bg-blue-500 text-white" : "bg-[#1e1e2e] text-slate-400"
              }`}
            >
              {done ? <CheckCircle2 size={16} /> : num}
            </div>
            {i < total - 1 && (
              <div className={`w-12 h-0.5 ${done ? "bg-emerald-500" : "bg-[#1e1e2e]"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Metric Card ────────────────────────────────────────────────────────────

function MetricCard({ label, value, sub, up }: { label: string; value: string; sub?: string; up?: boolean }) {
  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
      <div className="text-slate-400 text-xs mb-1">{label}</div>
      <div className={`text-xl font-bold ${up === undefined ? "text-white" : up ? "text-emerald-400" : "text-red-400"}`}>
        {value}
      </div>
      {sub && <div className="text-slate-500 text-xs mt-1">{sub}</div>}
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────

export default function BacktestPage() {
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<"single" | "portfolio">("single");
  const [portfolioStrategies, setPortfolioStrategies] = useState([
    { id: 1, strategy: "ma_cross", symbols: ["BTC/USDT"], weight: 1, params: {} },
  ]);
  const [result, setResult] = useState<any>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [selectedPair, setSelectedPair] = useState<string>("BTC/USDT");

  // Restore focus after step changes so keyboard navigation isn't interrupted
  const [prevStep, setPrevStep] = useState(1);
  const headingRef = useRef<HTMLHeadingElement>(null);

  const { control, handleSubmit, watch, formState: { errors }, setValue, trigger } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const watchedValues = watch();

  // Move focus to heading after step change so screen reader + keyboard stay in the form
  useEffect(() => {
    if (step !== prevStep) {
      setPrevStep(step);
      // Small tick to let DOM settle, then move focus
      const id = requestAnimationFrame(() => {
        headingRef.current?.focus();
      });
      return () => cancelAnimationFrame(id);
    }
  }, [step, prevStep]);

  // Fetch markets for pair selector
  const { data: marketsData } = useQuery({
    queryKey: ["markets", "binance"],
    queryFn: () => fetchMarkets("binance"),
    staleTime: 5 * 60 * 1000,
  });

  // Fetch strategies
  const { data: signalsData } = useQuery({
    queryKey: ["signals"],
    queryFn: fetchStrategies,
    staleTime: 5 * 60 * 1000,
  });

  // Run backtest mutation
  const runMutation = useMutation({
    mutationFn: runBacktest,
    onSuccess: (data) => {
      setResult(data);
      setStep(6); // results step
    },
    onError: (err: Error) => {
      setRunError(err.message);
    },
  });

  // Portfolio run mutation
  const portfolioRunMutation = useMutation({
    mutationFn: runPortfolioBacktest,
    onSuccess: (data) => {
      setResult(data);
      setStep(6);
    },
    onError: (err: Error) => {
      setRunError(err.message);
    },
  });

  // Portfolio walk-forward mutation
  const portfolioWalkForwardMutation = useMutation({
    mutationFn: runPortfolioWalkForward,
    onSuccess: (data) => {
      setResult(data);
      setStep(6);
    },
    onError: (err: Error) => {
      setRunError(err.message);
    },
  });

  const onSubmit = handleSubmit((data) => {
    setRunError(null);
    runMutation.mutate(data);
  });

  // ─── Step 1: Strategy ───────────────────────────────────────────────────

  const StrategyStep = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <Zap size={18} className="text-blue-400" />
        Select Strategy
      </h2>
      <Controller
        control={control}
        name="strategy"
        render={({ field }) => (
          <div className="grid grid-cols-2 gap-3">
            {STRATEGIES.map(s => (
              <button
                key={s.id}
                type="button"
                onClick={() => field.onChange(s.id)}
                className={`p-4 rounded-lg border text-left transition-all ${
                  field.value === s.id
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-[#1e1e2e] bg-[#0f0f1a] hover:border-blue-500/50"
                }`}
              >
                <div className="font-semibold text-white">{s.label}</div>
                <div className="text-slate-400 text-sm mt-1">{s.desc}</div>
              </button>
            ))}
          </div>
        )}
      />

      <div className="mt-4">
        <label className="text-slate-300 text-sm mb-2 block">Strategy parameters (optional JSON)</label>
        <Controller
          control={control}
          name="strategy_params"
          render={({ field }) => (
            <textarea
              {...field}
              value={field.value ? JSON.stringify(field.value, null, 2) : ""}
              onChange={e => {
                try { field.onChange(JSON.parse(e.target.value)); }
                catch { field.onChange({}); }
              }}
              placeholder='{"fast_period": 10, "slow_period": 30}'
              className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 font-mono h-24 resize-none focus:border-blue-500 focus:outline-none"
            />
          )}
        />
      </div>
    </div>
  );

  // ─── Step 2: Universe ───────────────────────────────────────────────────

  const UniverseStep = () => (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <BarChart3 size={18} className="text-blue-400" />
        Trading Universe
      </h2>

      {/* Pairs */}
      <div>
        <label className="text-slate-300 text-sm mb-2 block">Pairs</label>
        <Controller
          control={control}
          name="pairs"
          render={({ field }) => (
            <div className="flex flex-wrap gap-2">
              {PAIRS.map(pair => (
                <button
                  key={pair}
                  type="button"
                  onClick={() => {
                    const cur = (field.value as string[]) ?? [];
                    field.onChange(cur.includes(pair) ? cur.filter(p => p !== pair) : [...cur, pair]);
                  }}
                  className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                    ((field.value as string[]) ?? []).includes(pair)
                      ? "border-blue-500 bg-blue-500/10 text-blue-300"
                      : "border-[#1e1e2e] text-slate-400 hover:border-blue-500/50"
                  }`}
                >
                  {pair}
                </button>
              ))}
            </div>
          )}
        />
        {errors.pairs && <p className="text-red-400 text-xs mt-1">{errors.pairs.message}</p>}
      </div>

      {/* Timeframes */}
      <div>
        <label className="text-slate-300 text-sm mb-2 block">Timeframes</label>
        <Controller
          control={control}
          name="timeframes"
          render={({ field }) => (
            <div className="flex flex-wrap gap-2">
              {TIMEFRAMES.map(tf => (
                <button
                  key={tf}
                  type="button"
                  onClick={() => {
                    const cur = (field.value as string[]) ?? [];
                    field.onChange(cur.includes(tf) ? cur.filter(t => t !== tf) : [...cur, tf]);
                  }}
                  className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                    ((field.value as string[]) ?? []).includes(tf)
                      ? "border-emerald-500 bg-emerald-500/10 text-emerald-300"
                      : "border-[#1e1e2e] text-slate-400 hover:border-emerald-500/50"
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          )}
        />
        {errors.timeframes && <p className="text-red-400 text-xs mt-1">{errors.timeframes.message}</p>}
      </div>

      {/* Date range */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-slate-300 text-sm mb-2 block">Start Date</label>
          <Controller
            control={control}
            name="start_date"
            render={({ field }) => (
              <input
                type="date"
                {...field}
                max={watchedValues.end_date}
                className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
              />
            )}
          />
          {errors.start_date && <p className="text-red-400 text-xs mt-1">{errors.start_date.message}</p>}
        </div>
        <div>
          <label className="text-slate-300 text-sm mb-2 block">End Date</label>
          <Controller
            control={control}
            name="end_date"
            render={({ field }) => (
              <input
                type="date"
                {...field}
                min={watchedValues.start_date}
                className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
              />
            )}
          />
          {errors.end_date && <p className="text-red-400 text-xs mt-1">{errors.end_date.message}</p>}
        </div>
      </div>
    </div>
  );

  // ─── Step 3: Capital & Risk ────────────────────────────────────────────

  const CapitalStep = () => (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <DollarSign size={18} className="text-blue-400" />
        Capital & Risk
      </h2>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-slate-300 text-sm mb-2 block">Initial Capital ($)</label>
          <Controller
            control={control}
            name="initial_capital"
            render={({ field }) => (
              <input
                type="number"
                {...field}
                onChange={e => field.onChange(Number(e.target.value))}
                className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
              />
            )}
          />
        </div>
        <div>
          <label className="text-slate-300 text-sm mb-2 block">Leverage</label>
          <Controller
            control={control}
            name="leverage"
            render={({ field }) => (
              <input
                type="number"
                {...field}
                min={1}
                max={100}
                step={1}
                onChange={e => field.onChange(Number(e.target.value))}
                className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
              />
            )}
          />
        </div>
      </div>

      <div>
        <label className="text-slate-300 text-sm mb-2 block">Position Sizing</label>
        <Controller
          control={control}
          name="position_sizing"
          render={({ field }) => (
            <div className="grid grid-cols-3 gap-2">
              {POSITION_SIZING.map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => field.onChange(s.id)}
                  className={`px-3 py-2 rounded-lg border text-sm text-center transition-all ${
                    field.value === s.id
                      ? "border-blue-500 bg-blue-500/10 text-blue-300"
                      : "border-[#1e1e2e] text-slate-400 hover:border-blue-500/50"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-slate-300 text-sm mb-2 block">Max Positions</label>
          <Controller
            control={control}
            name="max_positions"
            render={({ field }) => (
              <input
                type="number"
                {...field}
                min={1}
                max={20}
                step={1}
                onChange={e => field.onChange(Number(e.target.value))}
                className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
              />
            )}
          />
        </div>
        <div>
          <label className="text-slate-300 text-sm mb-2 block">Direction</label>
          <Controller
            control={control}
            name="direction"
            render={({ field }) => (
              <div className="flex gap-2">
                {DIRECTION_OPTIONS.map(d => (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => field.onChange(d.id)}
                    className={`flex-1 px-3 py-2 rounded-lg border text-sm text-center transition-all ${
                      field.value === d.id
                        ? "border-blue-500 bg-blue-500/10 text-blue-300"
                        : "border-[#1e1e2e] text-slate-400 hover:border-blue-500/50"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            )}
          />
        </div>
      </div>
    </div>
  );

  // ─── Step 4: Costs ────────────────────────────────────────────────────

  const CostsStep = () => (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <Settings2 size={18} className="text-blue-400" />
        Execution Costs
      </h2>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-slate-300 text-sm mb-2 block">Maker Fee (%)</label>
          <Controller
            control={control}
            name="maker_fee"
            render={({ field }) => (
              <input
                type="number"
                {...field}
                step={0.0001}
                min={0}
                max={0.01}
                onChange={e => field.onChange(Number(e.target.value))}
                className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
              />
            )}
          />
        </div>
        <div>
          <label className="text-slate-300 text-sm mb-2 block">Taker Fee (%)</label>
          <Controller
            control={control}
            name="taker_fee"
            render={({ field }) => (
              <input
                type="number"
                {...field}
                step={0.0001}
                min={0}
                max={0.01}
                onChange={e => field.onChange(Number(e.target.value))}
                className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
              />
            )}
          />
        </div>
      </div>

      <div>
        <label className="text-slate-300 text-sm mb-2 block">Slippage Model</label>
        <Controller
          control={control}
          name="slippage_model"
          render={({ field }) => (
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "none", label: "None" },
                { id: "fixed", label: "Fixed BPS" },
                { id: "dynamic", label: "Dynamic" },
              ].map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => field.onChange(s.id)}
                  className={`px-3 py-2 rounded-lg border text-sm text-center transition-all ${
                    field.value === s.id
                      ? "border-blue-500 bg-blue-500/10 text-blue-300"
                      : "border-[#1e1e2e] text-slate-400 hover:border-blue-500/50"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        />
      </div>
    </div>
  );

  // ─── Step 5: Advanced ─────────────────────────────────────────────────

  const AdvancedStep = () => (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <TrendingUp size={18} className="text-blue-400" />
        Advanced Options
      </h2>

      {/* Walk-forward */}
      <div>
        <label className="text-slate-300 text-sm mb-2 block">Walk-Forward Analysis</label>
        <Controller
          control={control}
          name="walk_forward"
          render={({ field }) => (
            <div className="grid grid-cols-3 gap-2 mb-3">
              {[
                { id: "off", label: "Off" },
                { id: "expanding", label: "Expanding" },
                { id: "rolling", label: "Rolling" },
              ].map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => field.onChange(s.id)}
                  className={`px-3 py-2 rounded-lg border text-sm text-center transition-all ${
                    field.value === s.id
                      ? "border-purple-500 bg-purple-500/10 text-purple-300"
                      : "border-[#1e1e2e] text-slate-400 hover:border-purple-500/50"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        />
        {watchedValues.walk_forward !== "off" && (
          <div className="grid grid-cols-3 gap-3 pl-2 border-l-2 border-purple-500/30">
            <div>
              <label className="text-slate-400 text-xs mb-1 block">Train (days)</label>
              <Controller
                control={control}
                name="walk_forward_train_days"
                render={({ field }) => (
                  <input
                    type="number"
                    {...field}
                    onChange={e => field.onChange(Number(e.target.value))}
                    className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-sm text-slate-200 focus:border-purple-500 focus:outline-none"
                  />
                )}
              />
            </div>
            <div>
              <label className="text-slate-400 text-xs mb-1 block">Test (days)</label>
              <Controller
                control={control}
                name="walk_forward_test_days"
                render={({ field }) => (
                  <input
                    type="number"
                    {...field}
                    onChange={e => field.onChange(Number(e.target.value))}
                    className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-sm text-slate-200 focus:border-purple-500 focus:outline-none"
                  />
                )}
              />
            </div>
            <div>
              <label className="text-slate-400 text-xs mb-1 block">Skip (days)</label>
              <Controller
                control={control}
                name="walk_forward_skip_days"
                render={({ field }) => (
                  <input
                    type="number"
                    {...field}
                    onChange={e => field.onChange(Number(e.target.value))}
                    className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-sm text-slate-200 focus:border-purple-500 focus:outline-none"
                  />
                )}
              />
            </div>
          </div>
        )}
      </div>

      {/* Monte Carlo */}
      <div>
        <label className="text-slate-300 text-sm mb-2 block">Monte Carlo Simulation</label>
        <Controller
          control={control}
          name="monte_carlo"
          render={({ field }) => (
            <div className="grid grid-cols-4 gap-2 mb-3">
              {[
                { id: "off", label: "Off" },
                { id: "100", label: "100 runs" },
                { id: "500", label: "500 runs" },
                { id: "1000", label: "1000 runs" },
              ].map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => field.onChange(s.id)}
                  className={`px-3 py-2 rounded-lg border text-sm text-center transition-all ${
                    field.value === s.id
                      ? "border-amber-500 bg-amber-500/10 text-amber-300"
                      : "border-[#1e1e2e] text-slate-400 hover:border-amber-500/50"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        />
      </div>
    </div>
  );

  // ─── Portfolio Builder Step ─────────────────────────────────────────────────

  const PortfolioBuilderStep = () => {
    const addStrategy = () => {
      if (portfolioStrategies.length >= 10) return;
      setPortfolioStrategies(prev => [
        ...prev,
        { id: Date.now(), strategy: "ma_cross", symbols: ["BTC/USDT"], weight: 1, params: {} },
      ]);
    };

    const removeStrategy = (id: number) => {
      setPortfolioStrategies(prev => prev.filter(s => s.id !== id));
    };

    const updateStrategy = (id: number, field: string, value: any) => {
      setPortfolioStrategies(prev =>
        prev.map(s => s.id === id ? { ...s, [field]: value } : s)
      );
    };

    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <PieChart size={18} className="text-blue-400" />
          Portfolio Builder
        </h2>
        <div className="text-slate-400 text-sm">Add up to 10 strategies to combine in a portfolio</div>

        <div className="space-y-3">
          {portfolioStrategies.map((s, idx) => (
            <div key={s.id} className="bg-[#0a0a14] border border-[#1e1e2e] rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 text-xs font-medium">Strategy {idx + 1}</span>
                {portfolioStrategies.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeStrategy(s.id)}
                    className="text-slate-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>

              {/* Strategy selector */}
              <div>
                <label className="text-slate-300 text-xs mb-1 block">Strategy</label>
                <select
                  value={s.strategy}
                  onChange={e => updateStrategy(s.id, "strategy", e.target.value)}
                  className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
                >
                  {STRATEGIES.map(strat => (
                    <option key={strat.id} value={strat.id}>{strat.label}</option>
                  ))}
                </select>
              </div>

              {/* Symbols multi-select */}
              <div>
                <label className="text-slate-300 text-xs mb-1 block">Symbols</label>
                <div className="flex flex-wrap gap-1">
                  {PAIRS.map(pair => (
                    <button
                      key={pair}
                      type="button"
                      onClick={() => {
                        const symbols = s.symbols.includes(pair)
                          ? s.symbols.filter(p => p !== pair)
                          : [...s.symbols, pair];
                        updateStrategy(s.id, "symbols", symbols);
                      }}
                      className={`px-2 py-1 rounded text-xs transition-all ${
                        s.symbols.includes(pair)
                          ? "border-blue-500 bg-blue-500/10 text-blue-300 border"
                          : "border border-[#1e1e2e] text-slate-400 hover:border-blue-500/50"
                      }`}
                    >
                      {pair}
                    </button>
                  ))}
                </div>
              </div>

              {/* Weight */}
              <div>
                <label className="text-slate-300 text-xs mb-1 block">Weight (%)</label>
                <input
                  type="number"
                  value={s.weight}
                  onChange={e => updateStrategy(s.id, "weight", Number(e.target.value))}
                  min={1}
                  max={100}
                  className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
                />
              </div>

              {/* Params JSON */}
              <div>
                <label className="text-slate-300 text-xs mb-1 block">Parameters (JSON)</label>
                <textarea
                  value={JSON.stringify(s.params, null, 2)}
                  onChange={e => {
                    try { updateStrategy(s.id, "params", JSON.parse(e.target.value)); }
                    catch { }
                  }}
                  placeholder='{}'
                  className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-xs text-slate-200 font-mono h-16 resize-none focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
          ))}
        </div>

        {portfolioStrategies.length < 10 && (
          <button
            type="button"
            onClick={addStrategy}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-[#1e1e2e] text-slate-400 hover:border-blue-500/50 hover:text-blue-300 transition-all text-sm w-full justify-center"
          >
            <Plus size={16} /> Add Strategy
          </button>
        )}
      </div>
    );
  };

  // ─── Portfolio Settings Step ───────────────────────────────────────────────

  const PortfolioSettingsStep = ({ capital, setCapital, leverage, setLeverage, maxPos, setMaxPos, makerFee, setMakerFee, slippageBps, setSlippageBps, walkForward, setWalkForward, trainDays, setTrainDays, testDays, setTestDays, skipDays, setSkipDays }: {
    capital: number; setCapital: (v: number) => void;
    leverage: number; setLeverage: (v: number) => void;
    maxPos: number; setMaxPos: (v: number) => void;
    makerFee: number; setMakerFee: (v: number) => void;
    slippageBps: number; setSlippageBps: (v: number) => void;
    walkForward: boolean; setWalkForward: (v: boolean) => void;
    trainDays: number; setTrainDays: (v: number) => void;
    testDays: number; setTestDays: (v: number) => void;
    skipDays: number; setSkipDays: (v: number) => void;
  }) => {
    return (
      <div className="space-y-5">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Settings2 size={18} className="text-blue-400" />
          Portfolio Settings
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-slate-300 text-sm mb-2 block">Initial Capital ($)</label>
            <input
              type="number"
              value={capital}
              onChange={e => setCapital(Number(e.target.value))}
              className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-slate-300 text-sm mb-2 block">Leverage</label>
            <input
              type="number"
              value={leverage}
              onChange={e => setLeverage(Number(e.target.value))}
              min={1}
              max={100}
              className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-slate-300 text-sm mb-2 block">Max Positions</label>
            <input
              type="number"
              value={maxPos}
              onChange={e => setMaxPos(Number(e.target.value))}
              min={1}
              max={20}
              className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-slate-300 text-sm mb-2 block">Maker Fee (%)</label>
            <input
              type="number"
              value={makerFee}
              onChange={e => setMakerFee(Number(e.target.value))}
              step={0.0001}
              min={0}
              className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label className="text-slate-300 text-sm mb-2 block">Slippage (bps)</label>
          <input
            type="number"
            value={slippageBps}
            onChange={e => setSlippageBps(Number(e.target.value))}
            min={0}
            className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Walk-Forward Analysis Toggle */}
        <div className="border border-[#1e1e2e] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-slate-300 text-sm font-medium">Walk-Forward Analysis</div>
              <div className="text-slate-500 text-xs">Split into train/test windows for out-of-sample validation</div>
            </div>
            <button
              type="button"
              onClick={() => setWalkForward(!walkForward)}
              className={`w-12 h-6 rounded-full transition-colors relative ${
                walkForward ? "bg-purple-500" : "bg-[#1e1e2e]"
              }`}
            >
              <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                walkForward ? "translate-x-7" : "translate-x-1"
              }`} />
            </button>
          </div>

          {walkForward && (
            <div className="grid grid-cols-3 gap-3 pl-2 border-l-2 border-purple-500/30 mt-3">
              <div>
                <label className="text-slate-400 text-xs mb-1 block">Train (days)</label>
                <input
                  type="number"
                  value={trainDays}
                  onChange={e => setTrainDays(Number(e.target.value))}
                  min={7}
                  max={180}
                  className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-sm text-slate-200 focus:border-purple-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-slate-400 text-xs mb-1 block">Test (days)</label>
                <input
                  type="number"
                  value={testDays}
                  onChange={e => setTestDays(Number(e.target.value))}
                  min={1}
                  max={30}
                  className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-sm text-slate-200 focus:border-purple-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-slate-400 text-xs mb-1 block">Skip (days)</label>
                <input
                  type="number"
                  value={skipDays}
                  onChange={e => setSkipDays(Number(e.target.value))}
                  min={0}
                  max={14}
                  className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-2 text-sm text-slate-200 focus:border-purple-500 focus:outline-none"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  // ─── Mode Step ─────────────────────────────────────────────────────────────

  const ModeStep = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <PieChart size={18} className="text-blue-400" />
        Backtest Mode
      </h2>
      <div className="text-slate-400 text-sm">Choose how to run your backtest</div>

      <div className="grid grid-cols-2 gap-4">
        <button
          type="button"
          onClick={() => { setMode("single"); setStep(1); }}
          className={`p-5 rounded-lg border text-left transition-all ${
            mode === "single"
              ? "border-blue-500 bg-blue-500/10"
              : "border-[#1e1e2e] bg-[#0f0f1a] hover:border-blue-500/50"
          }`}
        >
          <Zap size={24} className={mode === "single" ? "text-blue-400 mb-2" : "text-slate-400 mb-2"} />
          <div className="font-semibold text-white">Single Strategy</div>
          <div className="text-slate-400 text-sm mt-1">Run a single strategy with full configuration</div>
        </button>

        <button
          type="button"
          onClick={() => { setMode("portfolio"); setStep(1); }}
          className={`p-5 rounded-lg border text-left transition-all ${
            mode === "portfolio"
              ? "border-blue-500 bg-blue-500/10"
              : "border-[#1e1e2e] bg-[#0f0f1a] hover:border-blue-500/50"
          }`}
        >
          <PieChart size={24} className={mode === "portfolio" ? "text-blue-400 mb-2" : "text-slate-400 mb-2"} />
          <div className="font-semibold text-white">Portfolio</div>
          <div className="text-slate-400 text-sm mt-1">Combine multiple strategies with correlation risk</div>
        </button>
      </div>
    </div>
  );

  // ─── Results Step ──────────────────────────────────────────────────────

  const ResultsStep = () => {
    if (runMutation.isPending) {
      return (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <div className="text-slate-300 font-medium">Running backtest...</div>
          <div className="text-slate-500 text-sm">This may take up to 60 seconds</div>
        </div>
      );
    }

    if (runError) {
      return (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <AlertCircle size={48} className="text-red-400" />
          <div className="text-red-400 font-semibold">Backtest Failed</div>
          <div className="text-slate-400 text-sm bg-[#0f0f1a] border border-red-500/30 rounded-lg p-4 max-w-lg text-center">{runError}</div>
          <button
            onClick={() => { setStep(1); setResult(null); setRunError(null); }}
            className="px-4 py-2 bg-[#1e1e2e] hover:bg-[#2e2e4e] rounded-lg text-sm text-slate-300 transition-colors"
          >
            Start Over
          </button>
        </div>
      );
    }

    if (!result) return null;

    // Handle both direct result and wrapped result formats
    const metrics = result.metrics ?? result;
    const trades = result.trade_log ?? result.trades ?? [];
    const equityCurve = result.equity_curve ?? [];
    const regime = result.regime ?? null;

    const formatPct = (v: number | null | undefined) => {
      if (v == null) return "—";
      return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;
    };
    // max_drawdown_pct is stored as a percentage (e.g. 8.0 = 8%), not a fraction
    const formatDrawdown = (v: number | null | undefined) => {
      if (v == null) return "—";
      return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
    };
    const formatNum = (v: number | null | undefined, dec = 2) => {
      if (v == null) return "—";
      return v.toFixed(dec);
    };

    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Backtest Results</h2>
            <p className="text-slate-400 text-sm mt-1">
              {result.strategy_name ?? watchedValues.strategy} · {result.symbol ?? watchedValues.pairs?.[0]} · {result.timeframe ?? watchedValues.timeframes?.[0]}
            </p>
          </div>
          <button
            onClick={() => { setStep(1); setResult(null); setRunError(null); }}
            className="flex items-center gap-2 px-3 py-1.5 bg-[#1e1e2e] hover:bg-[#2e2e4e] rounded-lg text-sm text-slate-300 transition-colors"
          >
            <Play size={14} /> New Run
          </button>
        </div>

        {/* Regime badge */}
        {regime && (
          <div className="flex items-center gap-3 bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
            <span className="text-slate-400 text-sm">Regime:</span>
            <span className={`px-2 py-0.5 rounded text-sm font-semibold ${
              regime.regime === "trending_up" ? "bg-emerald-500/20 text-emerald-400" :
              regime.regime === "trending_down" ? "bg-red-500/20 text-red-400" :
              regime.regime === "volatile" ? "bg-amber-500/20 text-amber-400" :
              "bg-slate-500/20 text-slate-400"
            }`}>{regime.regime}</span>
            <span className="text-slate-500 text-xs">trend={regime.trend_strength} | vol={regime.volatility_rank}</span>
          </div>
        )}

        {/* Metrics grid */}
        <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
          <MetricCard label="Total Return" value={formatPct(metrics.total_return)} up={metrics.total_return >= 0} />
          <MetricCard label="Annualized" value={formatPct(metrics.annualized_return)} up={metrics.annualized_return >= 0} />
          <MetricCard label="Max Drawdown" value={formatDrawdown(metrics.max_drawdown_pct)} up={false} />
          <MetricCard label="Sharpe" value={formatNum(metrics.sharpe_ratio)} />
          <MetricCard label="Sortino" value={formatNum(metrics.sortino_ratio)} />
          <MetricCard label="Calmar" value={formatNum(metrics.calmar_ratio)} />
          <MetricCard label="Win Rate" value={formatPct(metrics.win_rate)} up={(metrics.win_rate ?? 0) >= 0.5} />
          <MetricCard label="Profit Factor" value={formatNum(metrics.profit_factor)} />
          <MetricCard label="Expectancy" value={formatPct(metrics.expectancy)} up={(metrics.expectancy ?? 0) >= 0} />
          <MetricCard label="Trades" value={String(metrics.total_trades ?? 0)} />
          <MetricCard label="W/L" value={`${metrics.winning_trades ?? 0}/${metrics.losing_trades ?? 0}`} />
          <MetricCard label="Avg Trade" value={formatPct(metrics.avg_trade_duration_hours ? metrics.avg_trade_duration_hours / 24 : null)} />
        </div>

        {/* Equity curve placeholder */}
        <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
          <div className="text-slate-300 text-sm mb-3">Equity Curve</div>
          <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
            {equityCurve.length > 0
              ? <span className="text-emerald-400">{equityCurve.length} data points</span>
              : "Run with actual engine to render chart"}
          </div>
        </div>

        {/* Trade log */}
        <div>
          <div className="text-slate-300 text-sm mb-3">Trade Log ({trades.length} trades)</div>
          {trades.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-500 border-b border-[#1e1e2e]">
                    <th className="text-left py-2 px-3">#</th>
                    <th className="text-left py-2 px-3">Side</th>
                    <th className="text-left py-2 px-3">Entry</th>
                    <th className="text-left py-2 px-3">Exit</th>
                    <th className="text-right py-2 px-3">P&L</th>
                    <th className="text-right py-2 px-3">P&L%</th>
                    <th className="text-right py-2 px-3">MAE</th>
                    <th className="text-right py-2 px-3">MFE</th>
                  </tr>
                </thead>
                <tbody>
                  {(trades as any[]).slice(0, 20).map((t: any, i: number) => (
                    <tr key={i} className="border-b border-[#1e1e2e]/50 hover:bg-[#0f0f1a]">
                      <td className="py-2 px-3 text-slate-400">{i + 1}</td>
                      <td className={`py-2 px-3 font-medium ${t.side === "long" ? "text-emerald-400" : "text-red-400"}`}>{t.side}</td>
                      <td className="py-2 px-3 text-slate-200">{t.entry_price?.toFixed(2)}</td>
                      <td className="py-2 px-3 text-slate-200">{t.exit_price?.toFixed(2) ?? "—"}</td>
                      <td className={`py-2 px-3 text-right font-medium ${(t.pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {(t.pnl ?? 0) >= 0 ? "+" : ""}{t.pnl?.toFixed(2)}
                      </td>
                      <td className={`py-2 px-3 text-right ${(t.pnl_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {formatPct(t.pnl_pct)}
                      </td>
                      <td className="py-2 px-3 text-right text-slate-400">{t.mae?.toFixed(4) ?? "—"}</td>
                      <td className="py-2 px-3 text-right text-slate-400">{t.mfe?.toFixed(4) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-slate-500 text-sm text-center py-8">No trades in result yet</div>
          )}
        </div>
      </div>
    );
  };

// Portfolio state refs (hoisted for form submit)
  const portfolioSettingsRef = useRef({ capital: 10000, leverage: 1, maxPos: 5, makerFee: 0.0002, slippageBps: 5, startDate: "", endDate: "" });

  // Portfolio settings state (lifted so we can reference in submit)
  const [portfolioCapital, setPortfolioCapital] = useState(10000);
  const [portfolioLeverage, setPortfolioLeverage] = useState(1);
  const [portfolioMaxPos, setPortfolioMaxPos] = useState(5);
  const [portfolioMakerFee, setPortfolioMakerFee] = useState(0.0002);
  const [portfolioSlippageBps, setPortfolioSlippageBps] = useState(5);
  const [portfolioStartDate, setPortfolioStartDate] = useState(DEFAULT_VALUES.start_date);
  const [portfolioEndDate, setPortfolioEndDate] = useState(DEFAULT_VALUES.end_date);

  // Walk-forward state
  const [portfolioWalkForward, setPortfolioWalkForward] = useState(false);
  const [portfolioTrainDays, setPortfolioTrainDays] = useState(30);
  const [portfolioTestDays, setPortfolioTestDays] = useState(7);
  const [portfolioSkipDays, setPortfolioSkipDays] = useState(0);

  // Portfolio run handler
  const handlePortfolioRun = () => {
    const basePayload = {
      name: "Portfolio Backtest",
      strategies: portfolioStrategies.map(s => ({
        strategy: s.strategy,
        symbols: s.symbols,
        weight: s.weight,
        strategy_params: s.params,
      })),
      start_date: portfolioStartDate,
      end_date: portfolioEndDate,
      initial_capital: portfolioCapital,
      commission_pct: portfolioMakerFee,
      slippage_pct: portfolioSlippageBps / 10000,
      leverage: portfolioLeverage,
      max_positions: portfolioMaxPos,
      exchange: "binance" as const,
      timeframe: "4h",
      max_sector_exposure: 0.3,
      correlation_threshold: 0.7,
      correlation_reduction: 0.5,
      max_drawdown_pct: 0.2,
    };
    setRunError(null);
    if (portfolioWalkForward) {
      portfolioWalkForwardMutation.mutate({
        ...basePayload,
        train_days: portfolioTrainDays,
        test_days: portfolioTestDays,
        skip_days: portfolioSkipDays,
      });
    } else {
      portfolioRunMutation.mutate(basePayload);
    }
  };

  // ─── Navigation ────────────────────────────────────────────────────────────

  const StepNav = () => (
    <div className="flex items-center justify-between mt-4">
      <button
        type="button"
        onClick={back}
        disabled={step === 0}
        className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#1e1e2e] text-slate-400 hover:text-white hover:border-slate-500 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <ChevronLeft size={16} /> Back
      </button>
      <div className="text-slate-500 text-sm">{STEP_LABELS[step]}</div>
      {step < 5 ? (
        <button
          type="submit"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors"
        >
          Next <ChevronRight size={16} />
        </button>
      ) : (
        <button
          type="submit"
          disabled={runMutation.isPending}
          className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors disabled:opacity-50"
        >
          <Play size={16} />
          {runMutation.isPending ? "Running..." : "Run Backtest"}
        </button>
      )}
    </div>
  );

  const next = () => {
    if (mode === "portfolio") {
      setStep(s => Math.min(s + 1, 2)); // portfolio has steps 0,1,2
    } else {
      setStep(s => Math.min(s + 1, 5)); // single has steps 0,1,2,3,4,5
    }
  };
  const back = () => {
    if (mode === "portfolio") {
      setStep(s => Math.max(s - 1, 0));
    } else {
      setStep(s => Math.max(s - 1, 0));
    }
  };

  // ─── Step label ─────────────────────────────────────────────────────────
  const STEP_LABELS_SINGLE = ["Mode", "Strategy", "Universe", "Capital & Risk", "Costs", "Advanced"];
  const STEP_LABELS_PORTFOLIO = ["Mode", "Portfolio Builder", "Portfolio Settings"];
  const STEP_LABELS = mode === "portfolio" ? STEP_LABELS_PORTFOLIO : STEP_LABELS_SINGLE;
  const TOTAL_STEPS = mode === "portfolio" ? 2 : 5;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-bold text-white flex items-center gap-3 outline-none">
          <BarChart3 size={24} className="text-blue-400" />
          Backtest Runner
        </h1>
        <p className="text-slate-400 text-sm mt-1">Configure and run event-driven backtests with full metrics</p>
      </div>

      {step < 6 && (
        <>
          <StepIndicator current={step} total={mode === "portfolio" ? 3 : (step === 0 ? 1 : step + 1)} />

          {/* Step 0: Mode Selection - always visible first */}
          {step === 0 && (
            <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
              <ModeStep />
            </div>
          )}

          {/* Single Strategy Flow */}
          {mode === "single" && step === 1 && (
            <form onSubmit={async (e) => { e.preventDefault(); const ok = await trigger(['strategy']); if (ok) next(); }}>
              <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
                <StrategyStep />
              </div>
              <StepNav />
            </form>
          )}
          {mode === "single" && step === 2 && (
            <form onSubmit={async (e) => { e.preventDefault(); const ok = await trigger(['pairs', 'timeframes', 'start_date', 'end_date']); if (ok) next(); }}>
              <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
                <UniverseStep />
              </div>
              <StepNav />
            </form>
          )}
          {mode === "single" && step === 3 && (
            <form onSubmit={async (e) => { e.preventDefault(); const ok = await trigger(['initial_capital', 'leverage', 'position_sizing', 'max_positions', 'direction']); if (ok) next(); }}>
              <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
                <CapitalStep />
              </div>
              <StepNav />
            </form>
          )}
          {mode === "single" && step === 4 && (
            <form onSubmit={async (e) => { e.preventDefault(); const ok = await trigger(['maker_fee', 'taker_fee', 'slippage_model']); if (ok) next(); }}>
              <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
                <CostsStep />
              </div>
              <StepNav />
            </form>
          )}
          {mode === "single" && step === 5 && (
            <form onSubmit={onSubmit}>
              <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
                <AdvancedStep />
              </div>
              <div className="flex items-center justify-between mt-4">
                <button
                  type="button"
                  onClick={back}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#1e1e2e] text-slate-400 hover:text-white hover:border-slate-500 transition-all"
                >
                  <ChevronLeft size={16} /> Back
                </button>
                <div className="text-slate-500 text-sm">{STEP_LABELS[step]}</div>
                <button
                  type="submit"
                  disabled={runMutation.isPending}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors disabled:opacity-50"
                >
                  <Play size={16} />
                  {runMutation.isPending ? "Running..." : "Run Backtest"}
                </button>
              </div>
            </form>
          )}

          {/* Portfolio Flow */}
          {mode === "portfolio" && step === 1 && (
            <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
              <PortfolioBuilderStep />
              <div className="flex items-center justify-between mt-4">
                <button
                  type="button"
                  onClick={back}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#1e1e2e] text-slate-400 hover:text-white hover:border-slate-500 transition-all"
                >
                  <ChevronLeft size={16} /> Back
                </button>
                <div className="text-slate-500 text-sm">Portfolio Builder</div>
                <button
                  type="button"
                  onClick={next}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors"
                >
                  Next <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}

          {mode === "portfolio" && step === 2 && (
            <div className="space-y-4">
              <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
                <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
                  <BarChart3 size={18} className="text-blue-400" />
                  Date Range
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-slate-300 text-sm mb-2 block">Start Date</label>
                    <input
                      type="date"
                      value={portfolioStartDate}
                      onChange={e => setPortfolioStartDate(e.target.value)}
                      max={portfolioEndDate}
                      className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-300 text-sm mb-2 block">End Date</label>
                    <input
                      type="date"
                      value={portfolioEndDate}
                      onChange={e => setPortfolioEndDate(e.target.value)}
                      min={portfolioStartDate}
                      className="w-full bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
                <PortfolioSettingsStep
                  capital={portfolioCapital} setCapital={setPortfolioCapital}
                  leverage={portfolioLeverage} setLeverage={setPortfolioLeverage}
                  maxPos={portfolioMaxPos} setMaxPos={setPortfolioMaxPos}
                  makerFee={portfolioMakerFee} setMakerFee={setPortfolioMakerFee}
                  slippageBps={portfolioSlippageBps} setSlippageBps={setPortfolioSlippageBps}
                  walkForward={portfolioWalkForward} setWalkForward={setPortfolioWalkForward}
                  trainDays={portfolioTrainDays} setTrainDays={setPortfolioTrainDays}
                  testDays={portfolioTestDays} setTestDays={setPortfolioTestDays}
                  skipDays={portfolioSkipDays} setSkipDays={setPortfolioSkipDays}
                />
                <div className="flex items-center justify-between mt-4">
                  <button
                    type="button"
                    onClick={back}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#1e1e2e] text-slate-400 hover:text-white hover:border-slate-500 transition-all"
                  >
                    <ChevronLeft size={16} /> Back
                  </button>
                  <div className="text-slate-500 text-sm">Portfolio Settings</div>
                  <button
                    type="button"
                    onClick={handlePortfolioRun}
                    disabled={portfolioWalkForward ? portfolioWalkForwardMutation.isPending : portfolioRunMutation.isPending}
                    className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors disabled:opacity-50"
                  >
                    <Play size={16} />
                    {portfolioWalkForward ? (portfolioWalkForwardMutation.isPending ? "Running..." : "Run Walk-Forward") : (portfolioRunMutation.isPending ? "Running..." : "Run Portfolio")}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {step === 6 && (
        <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl p-6">
          <ResultsStep />
        </div>
      )}
    </div>
  );
}