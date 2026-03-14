const BASE = "/api";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export interface DashboardSummary {
  total_universe: number;
  strong_buys: number;
  buys: number;
  holds: number;
  exits: number;
  last_scan: string | null;
}

export interface SignalData {
  symbol: string;
  generated_at: string;
  fundamental_score: number | null;
  technical_score: number | null;
  momentum_score: number | null;
  valuation_score: number | null;
  composite_score: number | null;
  signal_type: string;
  reasoning: string | null;
  rsi: number | null;
  macd_signal: string | null;
  ma_crossover: string | null;
  volume_spike: boolean | null;
  relative_strength_6m: number | null;
  near_52w_high: boolean | null;
  near_52w_low: boolean | null;
}

export interface StockDetail {
  stock: {
    symbol: string;
    name: string;
    sector: string | null;
    industry: string | null;
    market_cap_cr: number | null;
    is_in_universe: boolean;
  };
  fundamentals: {
    pe_ratio: number | null;
    pb_ratio: number | null;
    roe: number | null;
    roce: number | null;
    debt_equity: number | null;
    promoter_holding: number | null;
    revenue_growth_3yr: number | null;
    profit_growth_3yr: number | null;
    peg_ratio: number | null;
  } | null;
  latest_signal: SignalData | null;
}

export interface PricePoint {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ScreenerRow {
  symbol: string;
  name: string;
  sector: string | null;
  market_cap_cr: number | null;
  pe_ratio: number | null;
  roe: number | null;
  composite_score: number | null;
  signal_type: string | null;
}

export interface AlertItem {
  symbol: string;
  signal_type: string;
  channel: string | null;
  message: string | null;
  sent_at: string;
  success: boolean;
}

export const api = {
  dashboard: () => fetchJson<DashboardSummary>("/dashboard"),
  signals: (type?: string) =>
    fetchJson<SignalData[]>(`/signals${type ? `?signal_type=${type}` : ""}`),
  stockSignals: (symbol: string) =>
    fetchJson<SignalData[]>(`/signals/${symbol}`),
  stockDetail: (symbol: string) =>
    fetchJson<StockDetail>(`/stocks/${symbol}`),
  stockPrices: (symbol: string, limit = 365) =>
    fetchJson<PricePoint[]>(`/stocks/${symbol}/prices?limit=${limit}`),
  screener: () => fetchJson<ScreenerRow[]>("/screener"),
  alerts: () => fetchJson<AlertItem[]>("/alerts"),
  watchlist: () => fetchJson<any[]>("/watchlist"),
  addWatchlist: (symbol: string) =>
    fetch(`${BASE}/watchlist/${symbol}`, { method: "POST" }),
  removeWatchlist: (symbol: string) =>
    fetch(`${BASE}/watchlist/${symbol}`, { method: "DELETE" }),
  triggerScan: () => fetch(`${BASE}/scan/trigger`, { method: "POST" }),
};
