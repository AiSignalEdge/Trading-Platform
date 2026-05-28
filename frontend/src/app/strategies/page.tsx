"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Plus, Filter, ArrowUpDown, TrendingUp, TrendingDown } from "lucide-react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { authFetch } from "@/lib/authFetch";

// ─── API Types ────────────────────────────────────────────────────────────────

interface Strategy {
  id: string;
  name: string;
  description: string;
  author: string;
  strategy_type: string;
  asset_class: string;
  pairs: string[];
  timeframes: string[];
  tags: string[];
  rating: number;
  backtest_count: number;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

interface StrategyListResponse {
  items: Strategy[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface StrategyCreate {
  name: string;
  description?: string;
  strategy_type: string;
  pairs?: string[];
  timeframes?: string[];
  is_public?: boolean;
}

// ─── API Helpers ──────────────────────────────────────────────────────────────

async function fetchStrategies(): Promise<StrategyListResponse> {
  const res = await authFetch("/api/v1/strategies?page=1&page_size=50");
  if (!res.ok) throw new Error("Failed to fetch strategies");
  return res.json();
}

async function createStrategy(data: StrategyCreate): Promise<Strategy> {
  const res = await authFetch("/api/v1/strategies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Sparkline Component ──────────────────────────────────────────────────────

function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data || data.length === 0) {
    return <div className="h-8 w-20 bg-background rounded" />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * 80;
      const y = 30 - ((value - min) / range) * 26;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width="80" height="32" className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={positive ? "#10b981" : "#ef4444"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─── Strategy Type Badge ──────────────────────────────────────────────────────

function StrategyTypeBadge({ type }: { type: string }) {
  const variants: Record<string, string> = {
    momentum: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    mean_reversion: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    trend_following: "bg-green-500/10 text-green-400 border-green-500/20",
    breakout: "bg-orange-500/10 text-orange-400 border-orange-500/20",
    grid: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    statistical: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
    ml: "bg-pink-500/10 text-pink-400 border-pink-500/20",
  };
  const cls = variants[type] ?? "bg-slate-500/10 text-slate-400 border-slate-500/20";
  return <Badge className={cn("text-xs", cls)}>{type.replace("_", " ")}</Badge>;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function StrategiesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [filter, setFilter] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("all");
  const [sortBy, setSortBy] = React.useState<"created" | "rating" | "name">("created");
  const [editingStrategy, setEditingStrategy] = React.useState<Strategy | null>(null);
  const [creatingStrategy, setCreatingStrategy] = React.useState(false);

  // Create form state
  const [formName, setFormName] = React.useState("");
  const [formDescription, setFormDescription] = React.useState("");
  const [formType, setFormType] = React.useState("momentum");
  const [formPairs, setFormPairs] = React.useState("BTC/USDT, ETH/USDT");
  const [formTimeframes, setFormTimeframes] = React.useState("1h, 4h");
  const [formError, setFormError] = React.useState<string | null>(null);
  const [formLoading, setFormLoading] = React.useState(false);

  // Fetch strategies
  const { data: strategiesData, isLoading } = useQuery({
    queryKey: ["strategies"],
    queryFn: fetchStrategies,
    staleTime: 30000,
  });

  // Create strategy mutation
  const createMutation = useMutation({
    mutationFn: createStrategy,
    onSuccess: (newStrategy) => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] });
      setCreatingStrategy(false);
      setFormName("");
      setFormDescription("");
      setFormType("momentum");
      setFormPairs("BTC/USDT, ETH/USDT");
      setFormTimeframes("1h, 4h");
      setFormError(null);
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  // Handle create submit
  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!formName.trim()) {
      setFormError("Strategy name is required");
      return;
    }
    setFormLoading(true);
    createMutation.mutate({
      name: formName.trim(),
      description: formDescription.trim(),
      strategy_type: formType,
      pairs: formPairs.split(",").map((p) => p.trim()).filter(Boolean),
      timeframes: formTimeframes.split(",").map((t) => t.trim()).filter(Boolean),
      is_public: true,
    });
  };

  const strategies = strategiesData?.items ?? [];

  const filteredStrategies = strategies
    .filter((s) => {
      const matchesSearch = s.name.toLowerCase().includes(filter.toLowerCase()) ||
        s.description.toLowerCase().includes(filter.toLowerCase());
      const matchesType = typeFilter === "all" || s.strategy_type === typeFilter;
      return matchesSearch && matchesType;
    })
    .sort((a, b) => {
      if (sortBy === "created") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      if (sortBy === "rating") return b.rating - a.rating;
      return a.name.localeCompare(b.name);
    });

  const types = ["all", ...Array.from(new Set(strategies.map((s) => s.strategy_type)))];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Strategy Library</h1>
          <p className="text-text-secondary">
            {isLoading ? "Loading..." : `${strategiesData?.total ?? 0} strategies configured`}
          </p>
        </div>
        <Button size="sm" onClick={() => setCreatingStrategy(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Strategy
        </Button>
      </div>

      {/* Filter Bar */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-text-secondary" />
              <span className="text-sm text-text-secondary">Filter:</span>
              {types.map((type) => (
                <button
                  key={type}
                  onClick={() => setTypeFilter(type)}
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                    typeFilter === type
                      ? "bg-primary text-white"
                      : "bg-border text-text-secondary hover:bg-border/80"
                  )}
                >
                  {type === "all" ? "All Types" : type.replace("_", " ")}
                </button>
              ))}
            </div>

            <div className="flex-1" />

            <div className="flex items-center gap-2">
              <span className="text-sm text-text-secondary">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-text-primary"
              >
                <option value="created">Created</option>
                <option value="rating">Rating</option>
                <option value="name">Name</option>
              </select>
            </div>

            <Input
              placeholder="Search strategies..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-48"
            />
          </div>
        </CardContent>
      </Card>

      {/* Strategy Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="pt-4 space-y-3">
                <div className="h-4 bg-background rounded w-3/4" />
                <div className="h-3 bg-background rounded w-1/2" />
                <div className="h-8 bg-background rounded" />
                <div className="grid grid-cols-4 gap-2 border-t border-border pt-3">
                  {[1, 2, 3, 4].map((j) => (
                    <div key={j} className="h-8 bg-background rounded" />
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredStrategies.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredStrategies.map((strategy) => (
            <Card key={strategy.id} className="hover:border-primary/30 transition-colors">
              <CardContent className="pt-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-text-primary">{strategy.name}</h3>
                    <p className="text-xs text-text-muted">
                      {strategy.pairs?.join(", ") || "—"} · {strategy.timeframes?.join(", ") || "—"}
                    </p>
                  </div>
                  <Badge
                    variant={strategy.is_public ? "success" : "warning"}
                  >
                    {strategy.is_public ? "public" : "private"}
                  </Badge>
                </div>

                <StrategyTypeBadge type={strategy.strategy_type} />

                {strategy.description && (
                  <p className="text-xs text-text-secondary mt-3 line-clamp-2">
                    {strategy.description}
                  </p>
                )}

                <div className="mt-4 pt-3 border-t border-border space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-muted">
                      by {strategy.author || "unknown"}
                    </span>
                    <span className="text-text-muted">
                      {strategy.backtest_count ?? 0} backtests
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">
                      {strategy.tags?.length ? strategy.tags.slice(0, 3).join(", ") : "No tags"}
                    </span>
                    <div className="flex gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setEditingStrategy(strategy)}>
                        Edit
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => router.push(`/automation?strategy=${strategy.id}`)}>
                        Run
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <p className="text-text-secondary">No strategies match your filters</p>
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={() => {
              setFilter("");
              setTypeFilter("all");
            }}
          >
            Clear Filters
          </Button>
        </div>
      )}

      {/* Edit Strategy Modal */}
      {editingStrategy && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditingStrategy(null)}>
          <div className="bg-card rounded-xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-text-primary mb-4">Edit Strategy</h2>
            <p className="text-text-secondary mb-4">Editing: <span className="font-medium text-text-primary">{editingStrategy.name}</span></p>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-text-secondary">Name</label>
                <Input defaultValue={editingStrategy.name} />
              </div>
              <div>
                <label className="text-sm text-text-secondary">Type</label>
                <Input defaultValue={editingStrategy.strategy_type} />
              </div>
              <div>
                <label className="text-sm text-text-secondary">Pairs</label>
                <Input defaultValue={editingStrategy.pairs?.join(", ")} />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <Button variant="outline" onClick={() => setEditingStrategy(null)}>Cancel</Button>
              <Button onClick={() => { alert(`Strategy "${editingStrategy.name}" updated! (read-only demo)`); setEditingStrategy(null); }}>Save Changes</Button>
            </div>
          </div>
        </div>
      )}

      {/* Create Strategy Modal */}
      {creatingStrategy && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => !formLoading && setCreatingStrategy(false)}>
          <div className="bg-card rounded-xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-text-primary mb-4">Create New Strategy</h2>
            <form onSubmit={handleCreateSubmit} className="space-y-3">
              <div>
                <label className="text-sm text-text-secondary">Strategy Name *</label>
                <Input
                  placeholder="e.g., MA Crossover BTC"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  disabled={formLoading}
                />
              </div>
              <div>
                <label className="text-sm text-text-secondary">Description</label>
                <Input
                  placeholder="Brief description of your strategy"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  disabled={formLoading}
                />
              </div>
              <div>
                <label className="text-sm text-text-secondary">Type</label>
                <select
                  value={formType}
                  onChange={(e) => setFormType(e.target.value)}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-text-primary"
                  disabled={formLoading}
                >
                  <option value="momentum">Momentum</option>
                  <option value="mean_reversion">Mean Reversion</option>
                  <option value="trend_following">Trend Following</option>
                  <option value="breakout">Breakout</option>
                  <option value="grid">Grid</option>
                  <option value="statistical">Statistical</option>
                  <option value="ml">ML-based</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-text-secondary">Trading Pairs (comma-separated)</label>
                <Input
                  placeholder="BTC/USDT, ETH/USDT"
                  value={formPairs}
                  onChange={(e) => setFormPairs(e.target.value)}
                  disabled={formLoading}
                />
              </div>
              <div>
                <label className="text-sm text-text-secondary">Timeframes (comma-separated)</label>
                <Input
                  placeholder="1h, 4h, 1d"
                  value={formTimeframes}
                  onChange={(e) => setFormTimeframes(e.target.value)}
                  disabled={formLoading}
                />
              </div>
              {formError && (
                <p className="text-xs text-red-400 bg-red-500/10 rounded px-3 py-2">{formError}</p>
              )}
              <div className="flex gap-2 mt-6">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => !formLoading && setCreatingStrategy(false)}
                  disabled={formLoading}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={formLoading}>
                  {formLoading ? "Creating..." : "Create Strategy"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}