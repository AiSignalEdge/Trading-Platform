type FetchOptions = RequestInit & {
  params?: Record<string, string | number | boolean>;
};

async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

  let url = endpoint;
  if (params) {
    const searchParams = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    );
    url += `?${searchParams.toString()}`;
  }

  const res = await fetch(url, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export const api = {
  get: <T>(endpoint: string, params?: Record<string, string | number | boolean>) =>
    fetchApi<T>(endpoint, { method: "GET", params }),

  post: <T>(endpoint: string, body?: unknown) =>
    fetchApi<T>(endpoint, { method: "POST", body: JSON.stringify(body) }),

  put: <T>(endpoint: string, body?: unknown) =>
    fetchApi<T>(endpoint, { method: "PUT", body: JSON.stringify(body) }),

  delete: <T>(endpoint: string) =>
    fetchApi<T>(endpoint, { method: "DELETE" }),
};

export interface Strategy {
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
}

export interface Backtest {
  id: string;
  strategyId: string;
  strategyName: string;
  pair: string;
  startedAt: string;
  duration: string;
  returnPct: number;
  status: "running" | "completed" | "failed";
}

export interface Portfolio {
  totalValue: number;
  pnlDay: number;
  pnlDayPct: number;
  positions: Position[];
}

export interface Position {
  symbol: string;
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
  pnlPct: number;
}

export const strategiesApi = {
  list: () => api.get<Strategy[]>("/api/strategies"),
  get: (id: string) => api.get<Strategy>(`/api/strategies/${id}`),
  create: (data: Partial<Strategy>) => api.post<Strategy>("/api/strategies", data),
  update: (id: string, data: Partial<Strategy>) =>
    api.put<Strategy>(`/api/strategies/${id}`, data),
  delete: (id: string) => api.delete(`/api/strategies/${id}`),
};

export const backtestApi = {
  list: () => api.get<Backtest[]>("/api/backtest"),
  get: (id: string) => api.get<Backtest>(`/api/backtest/${id}`),
  create: (data: { strategyId: string; pair: string; timeframe: string }) =>
    api.post<Backtest>("/api/backtest", data),
  run: (id: string) => api.post<Backtest>(`/api/backtest/${id}/run`, {}),
};

export const portfolioApi = {
  get: () => api.get<Portfolio>("/api/portfolio"),
};