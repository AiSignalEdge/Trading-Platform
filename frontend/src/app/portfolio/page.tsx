"use client";

import { useState } from "react";
import { Briefcase, Plus, Layers, TrendingUp, TrendingDown, MoreHorizontal, Pencil, Trash2, X } from "lucide-react";

interface Portfolio {
  id: string;
  name: string;
  strategies: number;
  equity: number;
  pnl_pct: number;
  status: "active" | "paused" | "inactive";
}

const MOCK_PORTFOLIOS: Portfolio[] = [
  { id: "1", name: "Momentum Portfolio", strategies: 3, equity: 125000, pnl_pct: 15.2, status: "active" },
  { id: "2", name: "Market Neutral", strategies: 5, equity: 85000, pnl_pct: -3.8, status: "paused" },
  { id: "3", name: "Trend Following", strategies: 2, equity: 156000, pnl_pct: 22.1, status: "active" },
  { id: "4", name: "Mean Reversion", strategies: 4, equity: 67000, pnl_pct: 5.4, status: "inactive" },
];

const STRATEGIES = [
  { id: "ma_cross", label: "MA Cross" },
  { id: "rsi", label: "RSI" },
  { id: "bollinger", label: "Bollinger" },
  { id: "macd", label: "MACD" },
];

function SummaryCard({ label, value, sub, trend }: { label: string; value: string; sub?: string; trend?: "up" | "down" }) {
  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-lg p-4">
      <div className="text-slate-400 text-xs mb-1">{label}</div>
      <div className={`text-xl font-bold ${trend === "up" ? "text-emerald-400" : trend === "down" ? "text-red-400" : "text-white"}`}>
        {value}
      </div>
      {sub && <div className="text-slate-500 text-xs mt-1">{sub}</div>}
    </div>
  );
}

function StatusBadge({ status }: { status: Portfolio["status"] }) {
  const styles = {
    active: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
    paused: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
    inactive: "bg-slate-500/10 text-slate-400 border border-slate-500/20",
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function CreatePortfolioModal({ onClose, onCreate }: { onClose: () => void; onCreate: (name: string, strategies: string[]) => void }) {
  const [name, setName] = useState("");
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim() && selectedStrategies.length > 0) {
      onCreate(name.trim(), selectedStrategies);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">Create New Portfolio</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-slate-300 text-sm mb-2 block">Portfolio Name</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g., Momentum Strategy Pool"
              className="w-full bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg p-3 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
              autoFocus
            />
          </div>

          <div>
            <label className="text-slate-300 text-sm mb-2 block">Select Strategies</label>
            <div className="grid grid-cols-2 gap-2">
              {STRATEGIES.map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => {
                    setSelectedStrategies(prev =>
                      prev.includes(s.id) ? prev.filter(id => id !== s.id) : [...prev, s.id]
                    );
                  }}
                  className={`p-3 rounded-lg border text-left text-sm transition-all ${
                    selectedStrategies.includes(s.id)
                      ? "border-blue-500 bg-blue-500/10 text-white"
                      : "border-[#1e1e2e] text-slate-400 hover:border-blue-500/50"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 rounded-lg border border-[#1e1e2e] text-slate-400 hover:text-white hover:border-slate-500 transition-all text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || selectedStrategies.length === 0}
              className="flex-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Create Portfolio
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>(MOCK_PORTFOLIOS);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const totalEquity = portfolios.reduce((sum, p) => sum + p.equity, 0);
  const totalPnL = portfolios.reduce((sum, p) => sum + (p.equity * p.pnl_pct / 100), 0);
  const activePortfolios = portfolios.filter(p => p.status === "active").length;

  const handleCreatePortfolio = (name: string, strategies: string[]) => {
    const newPortfolio: Portfolio = {
      id: Date.now().toString(),
      name,
      strategies: strategies.length,
      equity: 10000,
      pnl_pct: 0,
      status: "active",
    };
    setPortfolios(prev => [newPortfolio, ...prev]);
    setShowCreateModal(false);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Layers size={24} className="text-blue-400" />
            Portfolio Manager
          </h1>
          <p className="text-slate-400 text-sm mt-1">Manage your trading portfolios and strategies</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors text-sm"
        >
          <Plus size={16} />
          New Portfolio
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <SummaryCard label="Total Portfolios" value={portfolios.length.toString()} sub={`${activePortfolios} active`} />
        <SummaryCard label="Total Strategies" value={portfolios.reduce((sum, p) => sum + p.strategies, 0).toString()} sub="across all portfolios" />
        <SummaryCard label="Total Equity" value={`$${(totalEquity / 1000).toFixed(1)}K`} trend={totalEquity >= 0 ? "up" : "down"} />
        <SummaryCard label="Total PnL" value={`${totalPnL >= 0 ? "+" : ""}${(totalPnL / 1000).toFixed(1)}K`} trend={totalPnL >= 0 ? "up" : "down"} />
      </div>

      {/* Portfolio List */}
      <div className="bg-[#0f0f1a] border border-[#1e1e2e] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#1e1e2e]">
              <th className="text-left px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">Name</th>
              <th className="text-left px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">Strategies</th>
              <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">Equity</th>
              <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">PnL %</th>
              <th className="text-left px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">Status</th>
              <th className="text-right px-4 py-3 text-slate-400 text-xs font-medium uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            {portfolios.map(portfolio => (
              <tr key={portfolio.id} className="border-b border-[#1e1e2e]/50 hover:bg-[#1a1a2e]/50 transition-colors">
                <td className="px-4 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                      <Briefcase size={16} className="text-blue-400" />
                    </div>
                    <span className="text-white font-medium">{portfolio.name}</span>
                  </div>
                </td>
                <td className="px-4 py-4 text-slate-300 text-sm">{portfolio.strategies}</td>
                <td className="px-4 py-4 text-slate-300 text-sm text-right">${portfolio.equity.toLocaleString()}</td>
                <td className="px-4 py-4 text-right">
                  <div className={`flex items-center justify-end gap-1 text-sm ${portfolio.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {portfolio.pnl_pct >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    {portfolio.pnl_pct >= 0 ? "+" : ""}{portfolio.pnl_pct.toFixed(1)}%
                  </div>
                </td>
                <td className="px-4 py-4">
                  <StatusBadge status={portfolio.status} />
                </td>
                <td className="px-4 py-4 text-right">
                  <div className="relative">
                    <button
                      onClick={() => setMenuOpen(menuOpen === portfolio.id ? null : portfolio.id)}
                      className="p-1.5 rounded-lg hover:bg-[#1e1e2e] text-slate-400 hover:text-white transition-colors"
                    >
                      <MoreHorizontal size={16} />
                    </button>
                    {menuOpen === portfolio.id && (
                      <div className="absolute right-0 top-full mt-1 bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg shadow-xl z-10 min-w-[140px]">
                        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:text-white hover:bg-[#2a2a3e] transition-colors">
                          <Pencil size={14} />
                          Edit
                        </button>
                        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-[#2a2a3e] transition-colors">
                          <Trash2 size={14} />
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {portfolios.length === 0 && (
          <div className="py-12 text-center text-slate-500">
            <Briefcase size={32} className="mx-auto mb-3 opacity-50" />
            <p>No portfolios yet</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="mt-3 text-blue-400 hover:text-blue-300 text-sm"
            >
              Create your first portfolio
            </button>
          </div>
        )}
      </div>

      {showCreateModal && (
        <CreatePortfolioModal
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreatePortfolio}
        />
      )}
    </div>
  );
}