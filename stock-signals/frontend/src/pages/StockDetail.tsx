import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, StockDetail as StockDetailType, PricePoint, SignalData } from "../api";
import SignalCard from "../components/SignalCard";
import StockChart from "../components/StockChart";
import { RefreshCw, ArrowLeft, Plus, Check } from "lucide-react";

function getSignalBadgeClass(signalType: string): string {
  switch (signalType) {
    case "STRONG_BUY":
      return "bg-green-500/20 text-green-400";
    case "BUY":
      return "bg-emerald-500/20 text-emerald-400";
    case "HOLD":
      return "bg-amber-500/20 text-amber-400";
    case "EXIT":
      return "bg-red-500/20 text-red-400";
    default:
      return "bg-gray-500/20 text-gray-400";
  }
}

function MetricCard({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <p className="text-gray-400 text-xs">{label}</p>
      <p className="text-gray-100 font-semibold mt-1">{value ?? "—"}</p>
    </div>
  );
}

export default function StockDetail() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<StockDetailType | null>(null);
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [signalHistory, setSignalHistory] = useState<SignalData[]>([]);
  const [loading, setLoading] = useState(true);
  const [watchlisted, setWatchlisted] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    Promise.all([
      api.stockDetail(symbol),
      api.stockPrices(symbol).catch(() => []),
      api.stockSignals(symbol).catch(() => []),
    ])
      .then(([d, p, s]) => {
        setDetail(d);
        setPrices(p);
        setSignalHistory(s);
      })
      .finally(() => setLoading(false));
  }, [symbol]);

  async function handleWatchlist() {
    if (!symbol) return;
    await api.addWatchlist(symbol);
    setWatchlisted(true);
  }

  if (loading || !symbol) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="w-10 h-10 text-gray-500 animate-spin" />
      </div>
    );
  }

  const sig = detail?.latest_signal;
  const fund = detail?.fundamentals;
  const chartData = prices.map((p) => ({
    trade_date: p.trade_date,
    close: p.close,
    volume: p.volume,
  }));

  return (
    <div className="space-y-6 max-w-5xl">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-100 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </button>

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            {detail?.stock.name ?? symbol}
          </h1>
          <p className="text-gray-400 mt-1">
            {symbol} &middot; {detail?.stock.sector ?? "—"} &middot;{" "}
            {detail?.stock.market_cap_cr
              ? `₹${detail.stock.market_cap_cr.toLocaleString()} Cr`
              : "—"}
          </p>
        </div>
        <button
          onClick={handleWatchlist}
          disabled={watchlisted}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded-xl text-sm text-gray-100 transition-colors disabled:opacity-60"
        >
          {watchlisted ? (
            <>
              <Check className="w-4 h-4 text-green-400" />
              Watchlisted
            </>
          ) : (
            <>
              <Plus className="w-4 h-4" />
              Add to Watchlist
            </>
          )}
        </button>
      </div>

      {sig && (
        <SignalCard
          symbol={symbol}
          signalType={sig.signal_type}
          compositeScore={sig.composite_score}
          reasoning={sig.reasoning}
        />
      )}

      {fund && (
        <div>
          <h2 className="text-lg font-semibold text-gray-100 mb-3">Fundamentals</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            <MetricCard label="P/E Ratio" value={fund.pe_ratio?.toFixed(1)} />
            <MetricCard label="P/B Ratio" value={fund.pb_ratio?.toFixed(1)} />
            <MetricCard label="ROE %" value={fund.roe?.toFixed(1)} />
            <MetricCard label="ROCE %" value={fund.roce?.toFixed(1)} />
            <MetricCard label="Debt/Equity" value={fund.debt_equity?.toFixed(2)} />
            <MetricCard label="Promoter %" value={fund.promoter_holding?.toFixed(1)} />
            <MetricCard label="Rev Growth (3Y)" value={fund.revenue_growth_3yr ? `${fund.revenue_growth_3yr.toFixed(1)}%` : null} />
            <MetricCard label="Profit Growth (3Y)" value={fund.profit_growth_3yr ? `${fund.profit_growth_3yr.toFixed(1)}%` : null} />
            <MetricCard label="PEG Ratio" value={fund.peg_ratio?.toFixed(2)} />
          </div>
        </div>
      )}

      {chartData.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-100 mb-3">Price Chart</h2>
          <StockChart data={chartData} />
        </div>
      )}

      {sig && (
        <div>
          <h2 className="text-lg font-semibold text-gray-100 mb-3">Technical Indicators</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <MetricCard label="RSI (14)" value={sig.rsi?.toFixed(1)} />
            <MetricCard label="MACD" value={sig.macd_signal ?? "—"} />
            <MetricCard label="MA Crossover" value={sig.ma_crossover ?? "—"} />
            <MetricCard
              label="Volume Spike"
              value={sig.volume_spike ? "Yes" : "No"}
            />
            <MetricCard label="Rel Strength (6M)" value={sig.relative_strength_6m?.toFixed(1)} />
            <MetricCard label="Near 52W High" value={sig.near_52w_high ? "Yes" : "No"} />
            <MetricCard label="Near 52W Low" value={sig.near_52w_low ? "Yes" : "No"} />
          </div>
        </div>
      )}

      {sig && (
        <div>
          <h2 className="text-lg font-semibold text-gray-100 mb-3">Score Breakdown</h2>
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-700/50">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: "Fundamental", score: sig.fundamental_score, weight: "30%" },
                { label: "Technical", score: sig.technical_score, weight: "25%" },
                { label: "Momentum", score: sig.momentum_score, weight: "20%" },
                { label: "Valuation", score: sig.valuation_score, weight: "25%" },
              ].map((item) => (
                <div key={item.label}>
                  <p className="text-gray-400 text-xs">
                    {item.label}{" "}
                    <span className="text-gray-500">({item.weight})</span>
                  </p>
                  <p className="text-gray-100 text-xl font-bold mt-1">
                    {item.score?.toFixed(0) ?? "—"}
                  </p>
                  <div className="h-1.5 bg-gray-700 rounded-full mt-2">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all"
                      style={{ width: `${Math.min(item.score ?? 0, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-gray-700">
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">Composite Score</span>
                <span className="text-2xl font-bold text-gray-100">
                  {sig.composite_score?.toFixed(1) ?? "—"}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {signalHistory.length > 1 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-100 mb-3">Signal History</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 text-left border-b border-gray-700">
                  <th className="pb-2 pr-4">Date</th>
                  <th className="pb-2 pr-4">Signal</th>
                  <th className="pb-2 pr-4">Score</th>
                  <th className="pb-2">Reasoning</th>
                </tr>
              </thead>
              <tbody>
                {signalHistory.map((s, i) => (
                  <tr
                    key={i}
                    className="border-b border-gray-800 hover:bg-gray-800/50"
                  >
                    <td className="py-2 pr-4 text-gray-300">
                      {new Date(s.generated_at).toLocaleDateString()}
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${getSignalBadgeClass(s.signal_type)}`}
                      >
                        {s.signal_type}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-gray-100 font-medium">
                      {s.composite_score?.toFixed(1)}
                    </td>
                    <td className="py-2 text-gray-400 truncate max-w-xs">
                      {s.reasoning}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
