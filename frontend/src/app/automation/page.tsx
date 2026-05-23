"use client";

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Clock,
  Plus,
  Play,
  Pause,
  Trash2,
  X,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Calendar,
  Zap,
  BarChart3,
  Briefcase,
  GitBranch,
  TrendingUp,
  RefreshCw,
  Bell,
  Webhook,
  RotateCcw,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface SchedulerJob {
  job_id: string;
  name: string;
  job_type: string;
  payload: Record<string, any>;
  trigger_type: string;
  trigger_config: Record<string, any>;
  enabled: boolean;
  created_at: string;
  next_run: string | null;
  last_run: string | null;
  last_status: string | null;
  run_count: number;
  description: string;
  status: string;
}

interface JobHistory {
  execution_id: string;
  job_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  result_summary: string;
  error?: string;
}

// ─── API helpers ─────────────────────────────────────────────────────────────

async function fetchJobs(): Promise<{ items: SchedulerJob[]; total: number }> {
  const res = await fetch("/api/v1/scheduler/jobs");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchJobHistory(): Promise<{ items: JobHistory[]; total: number }> {
  const res = await fetch("/api/v1/scheduler/jobs/history");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function createJob(payload: any): Promise<any> {
  const res = await fetch("/api/v1/scheduler/jobs", {
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

async function updateJob(jobId: string, payload: any): Promise<any> {
  const res = await fetch(`/api/v1/scheduler/jobs/${jobId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function deleteJob(jobId: string): Promise<void> {
  const res = await fetch(`/api/v1/scheduler/jobs/${jobId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

async function runJob(jobId: string): Promise<any> {
  const res = await fetch(`/api/v1/scheduler/jobs/${jobId}/run`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ─── Constants ───────────────────────────────────────────────────────────────

const JOB_TYPES = [
  { id: "backtest", label: "Backtest", desc: "Single strategy backtest", icon: BarChart3 },
  { id: "walk-forward", label: "Walk-Forward", desc: "Train/test window optimization", icon: Zap },
  { id: "portfolio", label: "Portfolio", desc: "Multi-strategy portfolio", icon: Briefcase },
  { id: "portfolio-walk-forward", label: "Portfolio WF", desc: "Portfolio with walk-forward", icon: GitBranch },
  { id: "monte-carlo", label: "Monte Carlo", desc: "Monte Carlo simulation", icon: TrendingUp },
];

const PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT", "MATIC/USDT", "LINK/USDT", "DOT/USDT"];
const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];
const STRATEGIES = [
  { id: "ma_cross", label: "MA Cross" },
  { id: "rsi", label: "RSI" },
  { id: "bollinger", label: "Bollinger" },
  { id: "macd", label: "MACD" },
];

const INTERVAL_PRESETS: { label: string; hours: number; minutes?: number; seconds?: number }[] = [
  { label: "Every hour", hours: 1, minutes: 0 },
  { label: "Every 6 hours", hours: 6, minutes: 0 },
  { label: "Daily", hours: 24, minutes: 0 },
  { label: "Weekly", hours: 168, minutes: 0 },
];

const CRON_PRESETS = [
  { label: "Daily at 2AM", cron: "0 2 * * *" },
  { label: "Weekly (Monday)", cron: "0 0 * * 1" },
  { label: "Monthly", cron: "0 0 1 * *" },
  { label: "Every weekday", cron: "0 0 * * 1-5" },
];

// ─── Step Indicator ───────────────────────────────────────────────────────────

function StepIndicator({ current, total, labels }: { current: number; total: number; labels: string[] }) {
  return (
    <div className="flex items-center gap-2 mb-6 overflow-x-auto">
      {Array.from({ length: total }, (_, i) => {
        const num = i + 1;
        const done = num < current;
        const active = num === current;
        return (
          <div key={num} className="flex items-center gap-2 shrink-0">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors shrink-0 ${
                done ? "bg-emerald-500 text-white" : active ? "bg-primary text-white" : "bg-[#1e1e2e] text-slate-400"
              }`}
            >
              {done ? <CheckCircle2 size={16} /> : num}
            </div>
            <span className={`text-xs hidden sm:block ${active ? "text-text-primary" : "text-text-muted"}`}>
              {labels[i]}
            </span>
            {i < total - 1 && (
              <div className={`w-6 sm:w-12 h-0.5 ${done ? "bg-emerald-500" : "bg-[#1e1e2e]"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── New Job Modal ─────────────────────────────────────────────────────────────

interface NewJobModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

function NewJobModal({ open, onClose, onCreated }: NewJobModalProps) {
  const [step, setStep] = useState(1);
  const TOTAL_STEPS = 5;
  const STEP_LABELS = ["Job Type", "Config", "Schedule", "Notify", "Review"];

  // Step 1: Job Type
  const [jobType, setJobType] = useState<string>("backtest");

  // Step 2: Config
  const [pairs, setPairs] = useState<string[]>(["BTC/USDT"]);
  const [timeframes, setTimeframes] = useState<string[]>(["4h"]);
  const [strategy, setStrategy] = useState<string>("ma_cross");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 60);
    return d.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [commissionPct, setCommissionPct] = useState(0.0002);
  const [slippagePct, setSlippagePct] = useState(0.0005);
  const [leverage, setLeverage] = useState(1);
  const [maxPositions, setMaxPositions] = useState(1);
  const [exchange] = useState("binance");
  // Walk-forward params
  const [trainDays, setTrainDays] = useState(14);
  const [testDays, setTestDays] = useState(5);
  const [skipDays, setSkipDays] = useState(0);
  // Portfolio
  const [portfolioStrategies, setPortfolioStrategies] = useState([
    { id: 1, strategy: "ma_cross", symbols: ["BTC/USDT"] },
  ]);

  // Step 3: Schedule
  const [triggerType, setTriggerType] = useState<"interval" | "cron">("interval");
  const [intervalHours, setIntervalHours] = useState(24);
  const [intervalMinutes, setIntervalMinutes] = useState(0);
  const [intervalSeconds, setIntervalSeconds] = useState(0);
  const [cronExpr, setCronExpr] = useState("0 2 * * *");

  // Step 4: Notifications
  const [webhookUrl, setWebhookUrl] = useState("");
  const [notifyOnFailure, setNotifyOnFailure] = useState(false);
  const [notifyOnCompletion, setNotifyOnCompletion] = useState(false);

  // Step 5: Name/description
  const [jobName, setJobName] = useState("");
  const [jobDescription, setJobDescription] = useState("");

  const [createError, setCreateError] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: createJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scheduler-jobs"] });
      onCreated();
      handleClose();
    },
    onError: (err: Error) => setCreateError(err.message),
  });

  const handleClose = () => {
    setStep(1);
    setJobType("backtest");
    setPairs(["BTC/USDT"]);
    setTimeframes(["4h"]);
    setStrategy("ma_cross");
    setTriggerType("interval");
    setIntervalHours(24);
    setCronExpr("0 2 * * *");
    setWebhookUrl("");
    setNotifyOnFailure(false);
    setNotifyOnCompletion(false);
    setJobName("");
    setJobDescription("");
    setCreateError(null);
    onClose();
  };

  const buildPayload = () => {
    const isWalkForward = jobType === "walk-forward" || jobType === "portfolio-walk-forward";
    const isPortfolio = jobType === "portfolio" || jobType === "portfolio-walk-forward";

    let payload: any;
    if (isPortfolio) {
      payload = {
        name: jobName || "Portfolio Job",
        strategies: portfolioStrategies.map((s) => ({
          strategy: s.strategy,
          symbols: s.symbols,
          weight: 1 / portfolioStrategies.length,
        })),
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        commission_pct: commissionPct,
        slippage_pct: slippagePct,
        leverage,
        max_positions: maxPositions,
        exchange,
        timeframe: timeframes[0] || "4h",
        max_sector_exposure: 0.3,
        correlation_threshold: 0.8,
        correlation_reduction: 0.5,
        max_drawdown_pct: 20,
        ...(isWalkForward ? { train_days: trainDays, test_days: testDays, skip_days: skipDays } : {}),
      };
    } else {
      payload = {
        pairs,
        timeframes,
        strategy,
        start_date: startDate,
        end_date: endDate,
        ...(isWalkForward ? { train_days: trainDays, test_days: testDays, skip_days: skipDays } : {}),
        initial_capital: initialCapital,
        commission_pct: commissionPct,
        slippage_pct: slippagePct,
        leverage,
        max_positions: maxPositions,
        exchange,
      };
    }

    const triggerConfig: Record<string, any> =
      triggerType === "interval"
        ? {
            ...(intervalHours > 0 ? { hours: intervalHours } : {}),
            ...(intervalMinutes > 0 ? { minutes: intervalMinutes } : {}),
            ...(intervalSeconds > 0 ? { seconds: intervalSeconds } : {}),
          }
        : { cron: cronExpr };

    return {
      name: jobName || `${jobType} job`,
      job_type: jobType,
      payload,
      trigger_type: triggerType,
      trigger_config: Object.keys(triggerConfig).length === 0 ? { hours: 24 } : triggerConfig,
      enabled: true,
      description: jobDescription,
    };
  };

  const handleCreate = () => {
    setCreateError(null);
    createMutation.mutate(buildPayload());
  };

  if (!open) return null;

  // ─── Step 1: Job Type ─────────────────────────────────────────────────────

  const Step1 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
        <Zap size={18} className="text-primary" />
        Select Job Type
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {JOB_TYPES.map((jt) => (
          <button
            key={jt.id}
            type="button"
            onClick={() => setJobType(jt.id)}
            className={`p-4 rounded-lg border text-left transition-all ${
              jobType === jt.id
                ? "border-primary bg-primary/10"
                : "border-border bg-card hover:border-primary/50"
            }`}
          >
            <jt.icon className={`h-6 w-6 mb-2 ${jobType === jt.id ? "text-primary" : "text-text-secondary"}`} />
            <div className="font-semibold text-text-primary">{jt.label}</div>
            <div className="text-text-muted text-xs mt-1">{jt.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );

  // ─── Step 2: Config ────────────────────────────────────────────────────────

  const Step2 = () => {
    const isPortfolio = jobType === "portfolio" || jobType === "portfolio-walk-forward";
    const isWalkForward = jobType === "walk-forward" || jobType === "portfolio-walk-forward";

    return (
      <div className="space-y-5">
        <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
          <BarChart3 size={18} className="text-primary" />
          {isPortfolio ? "Portfolio Configuration" : "Strategy Configuration"}
        </h3>

        {!isPortfolio && (
          <>
            {/* Strategy */}
            <div>
              <label className="text-text-secondary text-sm mb-2 block">Strategy</label>
              <div className="flex flex-wrap gap-2">
                {STRATEGIES.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setStrategy(s.id)}
                    className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                      strategy === s.id ? "border-primary bg-primary/10 text-primary" : "border-border text-text-secondary hover:border-primary/50"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Pairs */}
            <div>
              <label className="text-text-secondary text-sm mb-2 block">Pairs</label>
              <div className="flex flex-wrap gap-2">
                {PAIRS.map((pair) => (
                  <button
                    key={pair}
                    type="button"
                    onClick={() =>
                      setPairs((p) => (p.includes(pair) ? p.filter((x) => x !== pair) : [...p, pair]))
                    }
                    className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                      pairs.includes(pair) ? "border-blue-500 bg-blue-500/10 text-blue-300" : "border-border text-text-secondary hover:border-blue-500/50"
                    }`}
                  >
                    {pair}
                  </button>
                ))}
              </div>
            </div>

            {/* Timeframes */}
            <div>
              <label className="text-text-secondary text-sm mb-2 block">Timeframes</label>
              <div className="flex flex-wrap gap-2">
                {TIMEFRAMES.map((tf) => (
                  <button
                    key={tf}
                    type="button"
                    onClick={() =>
                      setTimeframes((t) => (t.includes(tf) ? t.filter((x) => x !== tf) : [...t, tf]))
                    }
                    className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                      timeframes.includes(tf) ? "border-emerald-500 bg-emerald-500/10 text-emerald-300" : "border-border text-text-secondary hover:border-emerald-500/50"
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {isPortfolio && (
          <div>
            <label className="text-text-secondary text-sm mb-2 block">Strategies</label>
            <div className="space-y-2">
              {portfolioStrategies.map((ps, i) => (
                <div key={ps.id} className="flex gap-2 items-center">
                  <select
                    value={ps.strategy}
                    onChange={(e) => {
                      const updated = [...portfolioStrategies];
                      updated[i].strategy = e.target.value;
                      setPortfolioStrategies(updated);
                    }}
                    className="flex-1 bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
                  >
                    {STRATEGIES.map((s) => (
                      <option key={s.id} value={s.id}>{s.label}</option>
                    ))}
                  </select>
                  <div className="flex-1 flex flex-wrap gap-1">
                    {PAIRS.slice(0, 5).map((pair) => (
                      <button
                        key={pair}
                        type="button"
                        onClick={() => {
                          const updated = [...portfolioStrategies];
                          const syms = updated[i].symbols;
                          updated[i].symbols = syms.includes(pair)
                            ? syms.filter((x: string) => x !== pair)
                            : [...syms, pair];
                          setPortfolioStrategies(updated);
                        }}
                        className={`px-2 py-0.5 rounded text-xs border transition-all ${
                          ps.symbols.includes(pair) ? "border-blue-500 bg-blue-500/10 text-blue-300" : "border-border text-text-muted"
                        }`}
                      >
                        {pair}
                      </button>
                    ))}
                  </div>
                  {portfolioStrategies.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setPortfolioStrategies((p) => p.filter((_, idx) => idx !== i))}
                      className="text-danger hover:text-red-400"
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setPortfolioStrategies((p) => [
                    ...p,
                    { id: Date.now(), strategy: "ma_cross", symbols: ["BTC/USDT"] },
                  ])
                }
                className="flex items-center gap-1 text-primary text-sm hover:text-primary-hover"
              >
                <Plus size={14} /> Add Strategy
              </button>
            </div>
          </div>
        )}

        {/* Date range */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-text-secondary text-sm mb-2 block">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={endDate}
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-3 text-sm text-text-primary focus:border-primary focus:outline-none"
            />
          </div>
          <div>
            <label className="text-text-secondary text-sm mb-2 block">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              min={startDate}
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-3 text-sm text-text-primary focus:border-primary focus:outline-none"
            />
          </div>
        </div>

        {/* Walk-forward params */}
        {isWalkForward && (
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-text-secondary text-xs mb-1 block">Train Days</label>
              <input
                type="number"
                value={trainDays}
                onChange={(e) => setTrainDays(Number(e.target.value))}
                min={7}
                className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="text-text-secondary text-xs mb-1 block">Test Days</label>
              <input
                type="number"
                value={testDays}
                onChange={(e) => setTestDays(Number(e.target.value))}
                min={1}
                className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="text-text-secondary text-xs mb-1 block">Skip Days</label>
              <input
                type="number"
                value={skipDays}
                onChange={(e) => setSkipDays(Number(e.target.value))}
                min={0}
                className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Capital & Risk */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-text-secondary text-sm mb-1 block">Initial Capital ($)</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              min={100}
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
            />
          </div>
          <div>
            <label className="text-text-secondary text-sm mb-1 block">Leverage</label>
            <input
              type="number"
              value={leverage}
              onChange={(e) => setLeverage(Number(e.target.value))}
              min={1}
              max={100}
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
            />
          </div>
          <div>
            <label className="text-text-secondary text-sm mb-1 block">Max Positions</label>
            <input
              type="number"
              value={maxPositions}
              onChange={(e) => setMaxPositions(Number(e.target.value))}
              min={1}
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
            />
          </div>
          <div>
            <label className="text-text-secondary text-sm mb-1 block">Commission (%)</label>
            <input
              type="number"
              value={commissionPct * 100}
              onChange={(e) => setCommissionPct(Number(e.target.value) / 100)}
              step={0.01}
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
            />
          </div>
        </div>
      </div>
    );
  };

  // ─── Step 3: Schedule ─────────────────────────────────────────────────────

  const Step3 = () => (
    <div className="space-y-5">
      <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
        <Clock size={18} className="text-primary" />
        Schedule
      </h3>

      {/* Trigger type toggle */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setTriggerType("interval")}
          className={`flex-1 py-2.5 rounded-lg border text-sm font-medium transition-all ${
            triggerType === "interval"
              ? "border-primary bg-primary/10 text-primary"
              : "border-border text-text-secondary hover:border-primary/50"
          }`}
        >
          Interval
        </button>
        <button
          type="button"
          onClick={() => setTriggerType("cron")}
          className={`flex-1 py-2.5 rounded-lg border text-sm font-medium transition-all ${
            triggerType === "cron"
              ? "border-primary bg-primary/10 text-primary"
              : "border-border text-text-secondary hover:border-primary/50"
          }`}
        >
          Cron Schedule
        </button>
      </div>

      {triggerType === "interval" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {INTERVAL_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => {
                  setIntervalHours(p.hours);
                  setIntervalMinutes(p.minutes ?? 0);
                  setIntervalSeconds(p.seconds ?? 0);
                }}
                className="px-3 py-1.5 rounded-lg border border-border text-xs text-text-secondary hover:border-primary/50 hover:text-primary transition-all"
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-text-secondary text-xs mb-1 block">Hours</label>
              <input
                type="number"
                value={intervalHours}
                onChange={(e) => setIntervalHours(Number(e.target.value))}
                min={0}
                className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="text-text-secondary text-xs mb-1 block">Minutes</label>
              <input
                type="number"
                value={intervalMinutes}
                onChange={(e) => setIntervalMinutes(Number(e.target.value))}
                min={0}
                max={59}
                className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="text-text-secondary text-xs mb-1 block">Seconds</label>
              <input
                type="number"
                value={intervalSeconds}
                onChange={(e) => setIntervalSeconds(Number(e.target.value))}
                min={0}
                max={59}
                className="w-full bg-[#0f0f1a] border border-border rounded-lg p-2.5 text-sm text-text-primary focus:border-primary focus:outline-none"
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {CRON_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => setCronExpr(p.cron)}
                className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                  cronExpr === p.cron
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-text-secondary hover:border-primary/50"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div>
            <label className="text-text-secondary text-sm mb-2 block">Cron Expression</label>
            <input
              type="text"
              value={cronExpr}
              onChange={(e) => setCronExpr(e.target.value)}
              placeholder="0 2 * * *"
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-3 text-sm text-text-primary font-mono focus:border-primary focus:outline-none"
            />
            <p className="text-text-muted text-xs mt-1">Format: minute hour day month weekday</p>
          </div>
        </div>
      )}
    </div>
  );

  // ─── Step 4: Notifications ────────────────────────────────────────────────

  const Step4 = () => (
    <div className="space-y-5">
      <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
        <Bell size={18} className="text-primary" />
        Notifications
      </h3>

      <div>
        <label className="text-text-secondary text-sm mb-2 block">Webhook URL (optional)</label>
        <input
          type="url"
          value={webhookUrl}
          onChange={(e) => setWebhookUrl(e.target.value)}
          placeholder="https://your-server.com/webhook"
          className="w-full bg-[#0f0f1a] border border-border rounded-lg p-3 text-sm text-text-primary focus:border-primary focus:outline-none"
        />
      </div>

      <div className="space-y-3">
        <label className="flex items-center gap-3 cursor-pointer">
          <div
            onClick={() => setNotifyOnFailure(!notifyOnFailure)}
            className={`w-10 h-6 rounded-full transition-colors relative ${
              notifyOnFailure ? "bg-danger" : "bg-[#1e1e2e]"
            }`}
          >
            <div
              className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                notifyOnFailure ? "translate-x-5" : "translate-x-1"
              }`}
            />
          </div>
          <span className="text-text-secondary text-sm">Notify on failure</span>
        </label>

        <label className="flex items-center gap-3 cursor-pointer">
          <div
            onClick={() => setNotifyOnCompletion(!notifyOnCompletion)}
            className={`w-10 h-6 rounded-full transition-colors relative ${
              notifyOnCompletion ? "bg-emerald-500" : "bg-[#1e1e2e]"
            }`}
          >
            <div
              className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                notifyOnCompletion ? "translate-x-5" : "translate-x-1"
              }`}
            />
          </div>
          <span className="text-text-secondary text-sm">Notify on completion</span>
        </label>
      </div>
    </div>
  );

  // ─── Step 5: Review ────────────────────────────────────────────────────────

  const Step5 = () => {
    const isWalkForward = jobType === "walk-forward" || jobType === "portfolio-walk-forward";
    const isPortfolio = jobType === "portfolio" || jobType === "portfolio-walk-forward";
    const payload = buildPayload();

    return (
      <div className="space-y-5">
        <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
          <CheckCircle2 size={18} className="text-primary" />
          Review & Create
        </h3>

        <div className="space-y-3">
          <div>
            <label className="text-text-secondary text-xs mb-1 block">Job Name</label>
            <input
              type="text"
              value={jobName}
              onChange={(e) => setJobName(e.target.value)}
              placeholder="My scheduled job"
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-3 text-sm text-text-primary focus:border-primary focus:outline-none"
            />
          </div>
          <div>
            <label className="text-text-secondary text-xs mb-1 block">Description (optional)</label>
            <input
              type="text"
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="What does this job do?"
              className="w-full bg-[#0f0f1a] border border-border rounded-lg p-3 text-sm text-text-primary focus:border-primary focus:outline-none"
            />
          </div>
        </div>

        <div className="bg-[#0f0f1a] border border-border rounded-lg p-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-text-muted">Type</span>
            <span className="text-text-primary font-medium">{JOB_TYPES.find((j) => j.id === jobType)?.label}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">Trigger</span>
            <span className="text-text-primary font-medium">
              {triggerType === "interval"
                ? `Every ${intervalHours}h ${intervalMinutes}m`
                : `Cron: ${cronExpr}`}
            </span>
          </div>
          {!isPortfolio && (
            <div className="flex justify-between">
              <span className="text-text-muted">Strategy</span>
              <span className="text-text-primary font-medium">{STRATEGIES.find((s) => s.id === strategy)?.label}</span>
            </div>
          )}
          {!isPortfolio && (
            <div className="flex justify-between">
              <span className="text-text-muted">Pairs</span>
              <span className="text-text-primary font-medium">{pairs.join(", ")}</span>
            </div>
          )}
          {isWalkForward && (
            <div className="flex justify-between">
              <span className="text-text-muted">Walk-Forward</span>
              <span className="text-text-primary font-medium">
                {trainDays}d train / {testDays}d test / {skipDays}d skip
              </span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-text-muted">Capital</span>
            <span className="text-text-primary font-medium">${initialCapital.toLocaleString()}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={handleClose} />
      <div className="relative bg-card border border-border rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
          <h2 className="text-lg font-semibold text-text-primary">New Scheduled Job</h2>
          <button
            onClick={handleClose}
            className="text-text-muted hover:text-text-primary rounded-lg p-1.5 hover:bg-border transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Step indicator */}
        <div className="px-6 pt-4 shrink-0">
          <StepIndicator current={step} total={TOTAL_STEPS} labels={STEP_LABELS} />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 pb-4">
          {step === 1 && <Step1 />}
          {step === 2 && <Step2 />}
          {step === 3 && <Step3 />}
          {step === 4 && <Step4 />}
          {step === 5 && <Step5 />}

          {createError && (
            <div className="mt-4 p-3 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-2 text-danger text-sm">
              <AlertCircle size={16} />
              {createError}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border shrink-0">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1}
            className="px-4 py-2 rounded-lg border border-border text-text-secondary text-sm disabled:opacity-40 hover:border-primary/50 hover:text-primary transition-all"
          >
            Back
          </button>

          {step < TOTAL_STEPS ? (
            <button
              type="button"
              onClick={() => setStep((s) => s + 1)}
              className="flex items-center gap-2 px-6 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition-colors"
            >
              Next <ChevronRight size={16} />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleCreate}
              disabled={createMutation.isPending || !jobName.trim()}
              className="flex items-center gap-2 px-6 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500 disabled:opacity-50 transition-colors"
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Creating...
                </>
              ) : (
                <>
                  <Play size={16} /> Create Job
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Jobs Table ───────────────────────────────────────────────────────────────

function JobsTable() {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["scheduler-jobs"],
    queryFn: fetchJobs,
    refetchInterval: 30000,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduler-jobs"] }),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ jobId, enabled }: { jobId: string; enabled: boolean }) =>
      updateJob(jobId, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduler-jobs"] }),
  });

  const runMutation = useMutation({
    mutationFn: runJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduler-jobs"] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="animate-spin text-primary" size={32} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-center py-16">
        <AlertCircle className="mx-auto text-danger mb-2" size={32} />
        <p className="text-text-secondary">{String(error)}</p>
      </div>
    );
  }

  const jobs = data?.items ?? [];

  if (jobs.length === 0) {
    return (
      <div className="text-center py-16">
        <Calendar className="mx-auto text-text-muted mb-3" size={40} />
        <p className="text-text-secondary">No scheduled jobs yet</p>
        <p className="text-text-muted text-sm mt-1">Create your first job with the button above</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left py-3 px-4 text-text-muted font-medium">Name</th>
            <th className="text-left py-3 px-4 text-text-muted font-medium">Type</th>
            <th className="text-left py-3 px-4 text-text-muted font-medium">Trigger</th>
            <th className="text-left py-3 px-4 text-text-muted font-medium">Next Run</th>
            <th className="text-left py-3 px-4 text-text-muted font-medium">Status</th>
            <th className="text-right py-3 px-4 text-text-muted font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.job_id} className="border-b border-border/50 hover:bg-card/50 transition-colors">
              <td className="py-3 px-4">
                <div className="font-medium text-text-primary">{job.name}</div>
                <div className="text-text-muted text-xs">{job.description}</div>
              </td>
              <td className="py-3 px-4">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary">
                  {job.job_type}
                </span>
              </td>
              <td className="py-3 px-4 text-text-secondary">
                <div>{job.trigger_type === "interval" ? "⏱ Interval" : "⏰ Cron"}</div>
                <div className="text-xs text-text-muted">
                  {job.trigger_type === "interval"
                    ? `${job.trigger_config.hours ?? 0}h`
                    : job.trigger_config.cron}
                </div>
              </td>
              <td className="py-3 px-4 text-text-secondary">
                {job.next_run ? (
                  <div>{new Date(job.next_run).toLocaleString()}</div>
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </td>
              <td className="py-3 px-4">
                <button
                  onClick={() => toggleMutation.mutate({ jobId: job.job_id, enabled: !job.enabled })}
                  disabled={toggleMutation.isPending}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                    job.enabled
                      ? "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                      : "bg-[#1e1e2e] text-text-muted hover:bg-[#2e2e4e]"
                  }`}
                >
                  {job.enabled ? (
                    <><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Enabled</>
                  ) : (
                    <><span className="w-1.5 h-1.5 rounded-full bg-slate-500" /> Disabled</>
                  )}
                </button>
              </td>
              <td className="py-3 px-4">
                <div className="flex items-center justify-end gap-1">
                  <button
                    onClick={() => runMutation.mutate(job.job_id)}
                    disabled={runMutation.isPending}
                    title="Run now"
                    className="p-1.5 rounded-lg text-text-muted hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-50"
                  >
                    <Play size={15} />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Delete job "${job.name}"?`)) deleteMutation.mutate(job.job_id);
                    }}
                    disabled={deleteMutation.isPending}
                    title="Delete job"
                    className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-50"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Run History ──────────────────────────────────────────────────────────────

function RunHistory() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["scheduler-history"],
    queryFn: fetchJobHistory,
    refetchInterval: 15000,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="animate-spin text-primary" size={32} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-center py-16">
        <AlertCircle className="mx-auto text-danger mb-2" size={32} />
        <p className="text-text-secondary">{String(error)}</p>
      </div>
    );
  }

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <div className="text-center py-16">
        <RefreshCw className="mx-auto text-text-muted mb-3" size={40} />
        <p className="text-text-secondary">No run history yet</p>
        <p className="text-text-muted text-sm mt-1">Jobs will appear here after they execute</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-text-muted hover:text-primary text-xs transition-colors"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>
      {items.map((item) => (
        <div key={item.execution_id} className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                {item.status === "success" ? (
                  <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
                ) : item.status === "failed" ? (
                  <AlertCircle size={15} className="text-danger shrink-0" />
                ) : (
                  <Loader2 size={15} className="text-primary animate-spin shrink-0" />
                )}
                <span className={`text-sm font-medium ${
                  item.status === "success" ? "text-emerald-400" : item.status === "failed" ? "text-danger" : "text-primary"
                }`}>
                  {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
                </span>
                <span className="text-text-muted text-xs">·</span>
                <span className="text-text-muted text-xs">{item.job_id}</span>
              </div>
              <p className="text-text-secondary text-sm">{item.result_summary}</p>
              {item.error && (
                <p className="text-danger text-xs mt-1 font-mono truncate">{item.error.split("\n")[0]}</p>
              )}
            </div>
            <div className="text-right shrink-0">
              <div className="text-text-primary text-sm font-mono">
                {item.started_at ? (
                  item.finished_at ? (
                    <>
                      {Math.round(
                        (new Date(item.finished_at).getTime() - new Date(item.started_at).getTime()) / 1000
                      )}s
                    </>
                  ) : (
                    <span className="text-primary">running...</span>
                  )
                ) : (
                  "—"
                )}
              </div>
              <div className="text-text-muted text-xs mt-0.5">
                {item.started_at ? new Date(item.started_at).toLocaleString() : "—"}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AutomationPage() {
  const [activeTab, setActiveTab] = useState<"jobs" | "history">("jobs");
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
            <Clock size={24} className="text-primary" />
            Automation
          </h1>
          <p className="text-text-muted text-sm mt-1">Schedule and manage recurring backtests</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition-colors shrink-0"
        >
          <Plus size={18} />
          New Job
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {(["jobs", "history"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-primary text-primary"
                : "border-transparent text-text-muted hover:text-text-primary"
            }`}
          >
            {tab === "jobs" ? "Scheduled Jobs" : "Run History"}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "jobs" ? <JobsTable /> : <RunHistory />}

      {/* New Job Modal */}
      <NewJobModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={() => {
          setActiveTab("jobs");
        }}
      />
    </div>
  );
}
