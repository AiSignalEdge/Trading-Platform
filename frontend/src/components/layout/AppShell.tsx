"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  LayoutDashboard,
  GitBranch,
  BarChart3,
  Briefcase,
  Zap,
  GitCompare,
  Shield,
  Download,
  Settings,
  ChevronLeft,
  ChevronRight,
  User,
  X,
  Menu,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 60 * 1000,
    },
  },
});

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/strategies", label: "Strategies", icon: GitBranch },
  { href: "/backtest", label: "Backtest", icon: BarChart3 },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/automation", label: "Automation", icon: Clock },
  { href: "/automate", label: "Automate", icon: Zap },
  { href: "/compare", label: "Compare", icon: GitCompare },
  { href: "/risk", label: "Risk", icon: Shield },
  { href: "/export", label: "Export", icon: Download },
  { href: "/settings", label: "Settings", icon: Settings },
];

const STATIC_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "BNB/USDT"];

function useMarketTicker() {
  const [ticks, setTicks] = React.useState<
    Record<string, { price: number; symbol: string }>
  >({});

  React.useEffect(() => {
    async function fetchTicks() {
      try {
        const syms = STATIC_SYMBOLS.join(",");
        const res = await fetch(
          `/api/v1/data/tickers?exchange=binance&symbols=${encodeURIComponent(syms)}`,
          { headers: { "X-API-Key": "hermes-secret-api-key-2025" }, signal: AbortSignal.timeout(4000) }
        );
        if (!res.ok) return;
        const data = await res.json();
        const map: Record<string, { price: number; symbol: string }> = {};
        for (const t of data) {
          map[t.symbol] = t;
        }
        setTicks(map);
      } catch {
        // keep last known prices on error
      }
    }
    fetchTicks();
    const id = setInterval(fetchTicks, 5000);
    return () => clearInterval(id);
  }, []);

  return ticks;
}

function formatPrice(price: number | undefined, decimals = 2): string {
  if (price === undefined || price === null) return "—";
  return price.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const [collapsed, setCollapsed] = React.useState(false);
  const pathname = usePathname();
  const ticks = useMarketTicker();

  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen overflow-hidden bg-background">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col border-r border-border bg-card transition-all duration-300 ease-in-out lg:relative lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          collapsed ? "w-16" : "w-56"
        )}
      >
        {/* Logo */}
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 shrink-0 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-white font-bold text-sm">H</span>
            </div>
            {!collapsed && (
              <span className="font-semibold text-text-primary">Hermes</span>
            )}
          </div>
          {/* Mobile close */}
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden rounded-lg p-1.5 text-text-secondary hover:bg-border hover:text-text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-text-secondary hover:bg-border hover:text-text-primary"
                )}
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Collapse Button (desktop only) */}
        <div className="hidden lg:block border-t border-border p-2">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex w-full items-center justify-center rounded-lg p-2 text-text-secondary hover:bg-border hover:text-text-primary"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Topbar */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4 gap-3">
          {/* Mobile hamburger */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden rounded-lg p-2 text-text-secondary hover:bg-border hover:text-text-primary"
          >
            <Menu className="h-5 w-5" />
          </button>

          <h1 className="text-base font-semibold text-text-primary lg:text-lg">
            Trading Dashboard
          </h1>

          {/* Market ticker — horizontal scroll on mobile */}
          <div className="hidden sm:flex items-center gap-3 lg:gap-4">
            {STATIC_SYMBOLS.map((pair) => {
              const sym = pair.replace("/USDT", "");
              const tick = ticks[pair.replace("/", "")];
              return (
                <div key={sym} className="flex items-center gap-1.5">
                  <span className="text-xs font-medium text-text-secondary">
                    {sym}
                  </span>
                  <span className="text-sm font-mono text-text-primary">
                    {tick ? formatPrice(tick.price, sym === "BTC" ? 2 : 2) : "—"}
                  </span>
                  {tick && (
                    <span className="text-xs font-medium text-text-muted">—</span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Mobile market — just BTC price */}
          <div className="flex sm:hidden items-center gap-1.5">
            <span className="text-xs font-medium text-text-secondary">BTC</span>
            <span className="text-sm font-mono text-text-primary">
              {ticks["BTCUSDT"]
                ? formatPrice(ticks["BTCUSDT"].price)
                : "—"}
            </span>
          </div>

          <button className="rounded-full bg-border p-2">
            <User className="h-4 w-4 text-text-secondary" />
          </button>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
    </QueryClientProvider>
  );
}