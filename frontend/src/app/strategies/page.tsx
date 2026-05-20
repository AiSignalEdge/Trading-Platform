"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Plus, Filter, ArrowUpDown, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface Strategy {
  id: string;
  name: string;
  type: string;
  pair: string;
  timeframe: string;
  returnPct: number;
  maxDrawdown: number;
  sharpe: number;
  winRate: number;
  trades: number;
  status: "active" | "paused" | "archived";
  sparkline: number[];
}

const mockStrategies: Strategy[] = [
  {
    id: "1",
    name: "MA Crossover BTC",
    type: "Trend Following",
    pair: "BTC/USDT",
    timeframe: "1h",
    returnPct: 24.5,
    maxDrawdown: -8.2,
    sharpe: 1.87,
    winRate: 62.3,
    trades: 156,
    status: "active",
    sparkline: [10, 15, 12, 18, 22, 19, 25, 28, 24, 30],
  },
  {
    id: "2",
    name: "Bollinger RSI ETH",
    type: "Mean Reversion",
    pair: "ETH/USDT",
    timeframe: "4h",
    returnPct: 18.3,
    maxDrawdown: -5.4,
    sharpe: 2.14,
    winRate: 71.8,
    trades: 89,
    status: "active",
    sparkline: [20, 22, 18, 24, 21, 26, 23, 28, 25, 30],
  },
  {
    id: "3",
    name: "MACD Momentum SOL",
    type: "Momentum",
    pair: "SOL/USDT",
    timeframe: "15m",
    returnPct: 42.1,
    maxDrawdown: -12.6,
    sharpe: 1.54,
    winRate: 58.9,
    trades: 234,
    status: "active",
    sparkline: [5, 8, 12, 15, 18, 22, 20, 28, 32, 38],
  },
  {
    id: "4",
    name: "Grid Trading AVAX",
    type: "Grid",
    pair: "AVAX/USDT",
    timeframe: "1h",
    returnPct: 15.7,
    maxDrawdown: -3.2,
    sharpe: 2.45,
    winRate: 78.4,
    trades: 412,
    status: "paused",
    sparkline: [15, 17, 16, 18, 19, 17, 20, 19, 21, 22],
  },
  {
    id: "5",
    name: "Donchian Breakout",
    type: "Breakout",
    pair: "BNB/USDT",
    timeframe: "4h",
    returnPct: 31.2,
    maxDrawdown: -9.8,
    sharpe: 1.92,
    winRate: 55.2,
    trades: 67,
    status: "active",
    sparkline: [8, 12, 10, 15, 18, 22, 20, 28, 26, 35],
  },
  {
    id: "6",
    name: "Moon Phase BTC",
    type: "Seasonal",
    pair: "BTC/USDT",
    timeframe: "1d",
    returnPct: 28.9,
    maxDrawdown: -6.4,
    sharpe: 2.01,
    winRate: 64.7,
    trades: 45,
    status: "paused",
    sparkline: [12, 14, 16, 15, 18, 20, 19, 24, 26, 28],
  },
];

function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
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

function MetricBadge({ label, value, positive }: { label: string; value: string; positive: boolean }) {
  return (
    <div className="text-center">
      <p className="text-xs text-text-muted">{label}</p>
      <p className={cn("text-sm font-mono font-medium", positive ? "text-accent" : "text-danger")}>
        {value}
      </p>
    </div>
  );
}

export default function StrategiesPage() {
  const [filter, setFilter] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("all");
  const [sortBy, setSortBy] = React.useState<"return" | "sharpe" | "winRate">("return");

  const filteredStrategies = mockStrategies
    .filter((s) => {
      const matchesSearch = s.name.toLowerCase().includes(filter.toLowerCase());
      const matchesType = typeFilter === "all" || s.type === typeFilter;
      return matchesSearch && matchesType;
    })
    .sort((a, b) => {
      if (sortBy === "return") return b.returnPct - a.returnPct;
      if (sortBy === "sharpe") return b.sharpe - a.sharpe;
      return b.winRate - a.winRate;
    });

  const types = ["all", ...Array.from(new Set(mockStrategies.map((s) => s.type)))];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Strategy Library</h1>
          <p className="text-text-secondary">{mockStrategies.length} strategies configured</p>
        </div>
        <Button size="sm">
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
                  {type === "all" ? "All Types" : type}
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
                <option value="return">Return</option>
                <option value="sharpe">Sharpe</option>
                <option value="winRate">Win Rate</option>
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
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredStrategies.map((strategy) => (
          <Card key={strategy.id} className="hover:border-primary/30 transition-colors">
            <CardContent className="pt-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-text-primary">{strategy.name}</h3>
                  <p className="text-sm text-text-secondary">
                    {strategy.pair} • {strategy.timeframe}
                  </p>
                </div>
                <Badge
                  variant={
                    strategy.status === "active"
                      ? "success"
                      : strategy.status === "paused"
                      ? "warning"
                      : "default"
                  }
                >
                  {strategy.status}
                </Badge>
              </div>

              <Badge variant="info" className="mb-4">
                {strategy.type}
              </Badge>

              {/* Sparkline */}
              <div className="flex items-center justify-center h-12 mb-4 bg-background rounded-lg">
                <Sparkline data={strategy.sparkline} positive={strategy.returnPct > 0} />
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-4 gap-2 border-t border-border pt-3">
                <MetricBadge
                  label="Return"
                  value={`${strategy.returnPct > 0 ? "+" : ""}${strategy.returnPct.toFixed(1)}%`}
                  positive={strategy.returnPct > 0}
                />
                <MetricBadge
                  label="MaxDD"
                  value={`${strategy.maxDrawdown.toFixed(1)}%`}
                  positive={false}
                />
                <MetricBadge
                  label="Sharpe"
                  value={strategy.sharpe.toFixed(2)}
                  positive={strategy.sharpe > 1}
                />
                <MetricBadge
                  label="Win%"
                  value={`${strategy.winRate.toFixed(1)}%`}
                  positive={strategy.winRate > 50}
                />
              </div>

              <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
                <span className="text-xs text-text-muted">{strategy.trades} trades</span>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm">
                    Edit
                  </Button>
                  <Button variant="ghost" size="sm">
                    Run
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredStrategies.length === 0 && (
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
    </div>
  );
}