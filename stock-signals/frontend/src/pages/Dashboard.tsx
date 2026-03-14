import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  DashboardSummary,
  SignalData,
} from "../api";
import {
  Activity,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";

function getSignalBadgeClass(signalType: string): string {
  switch (signalType) {
    case "STRONG_BUY":
      return "bg-green-500/20 text-green-400 border-green-500/40";
    case "BUY":
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";
    case "HOLD":
      return "bg-amber-500/20 text-amber-400 border-amber-500/40";
    case "EXIT":
      return "bg-red-500/20 text-red-400 border-red-500/40";
    default:
      return "bg-gray-500/20 text-gray-400 border-gray-500/40";
  }
}

function getSignalIcon(signalType: string) {
  switch (signalType) {
    case "STRONG_BUY":
    case "BUY":
      return TrendingUp;
    case "EXIT":
      return TrendingDown;
    default:
      return Minus;
  }
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [signals, setSignals] = useState<SignalData[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [dash, sigs] = await Promise.all([
          api.dashboard(),
          api.signals(),
        ]);
        setSummary(dash);
        setSignals(
          [...sigs].sort(
            (a, b) =>
              (b.composite_score ?? 0) - (a.composite_score ?? 0)
          )
        );
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleTriggerScan() {
    setScanning(true);
    try {
      await api.triggerScan();
      const [dash, sigs] = await Promise.all([
        api.dashboard(),
        api.signals(),
      ]);
      setSummary(dash);
      setSignals(
        [...sigs].sort(
          (a, b) =>
            (b.composite_score ?? 0) - (a.composite_score ?? 0)
        )
      );
    } finally {
      setScanning(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <RefreshCw className="w-10 h-10 text-gray-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 p-4 md:p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 md:gap-4">
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-700/50 shadow-lg">
            <p className="text-gray-400 text-sm">Total Universe</p>
            <p className="text-2xl font-semibold text-gray-100">
              {summary?.total_universe ?? 0}
            </p>
          </div>
          <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30 shadow-lg">
            <p className="text-green-400/80 text-sm">Strong Buys</p>
            <p className="text-2xl font-semibold text-green-400">
              {summary?.strong_buys ?? 0}
            </p>
          </div>
          <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-500/30 shadow-lg">
            <p className="text-emerald-400/80 text-sm">Buys</p>
            <p className="text-2xl font-semibold text-emerald-400">
              {summary?.buys ?? 0}
            </p>
          </div>
          <div className="bg-amber-500/10 rounded-xl p-4 border border-amber-500/30 shadow-lg">
            <p className="text-amber-400/80 text-sm">Holds</p>
            <p className="text-2xl font-semibold text-amber-400">
              {summary?.holds ?? 0}
            </p>
          </div>
          <div className="bg-red-500/10 rounded-xl p-4 border border-red-500/30 shadow-lg">
            <p className="text-red-400/80 text-sm">Exits</p>
            <p className="text-2xl font-semibold text-red-400">
              {summary?.exits ?? 0}
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-2 text-gray-400">
            <Activity className="w-4 h-4" />
            <span className="text-sm">
              Last scan:{" "}
              {summary?.last_scan
                ? new Date(summary.last_scan).toLocaleString()
                : "Never"}
            </span>
          </div>
          <button
            onClick={handleTriggerScan}
            disabled={scanning}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded-xl text-gray-100 transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={`w-4 h-4 ${scanning ? "animate-spin" : ""}`}
            />
            {scanning ? "Scanning…" : "Trigger Scan"}
          </button>
        </div>

        <div>
          <h2 className="text-lg font-semibold text-gray-100 mb-4">
            Latest Signals
          </h2>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {signals.map((s) => {
              const Icon = getSignalIcon(s.signal_type);
              return (
                <button
                  key={`${s.symbol}-${s.generated_at}`}
                  onClick={() => navigate(`/stock/${s.symbol}`)}
                  className="text-left bg-gray-900 rounded-xl p-4 border border-gray-700/50 hover:border-gray-600 transition-colors shadow"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xl font-bold text-gray-100">
                      {s.symbol}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs font-medium border ${getSignalBadgeClass(
                        s.signal_type
                      )}`}
                    >
                      <Icon className="w-3 h-3" />
                      {s.signal_type}
                    </span>
                  </div>
                  <div className="mt-2 text-gray-400 text-sm">
                    Score:{" "}
                    <span className="text-gray-100 font-medium">
                      {s.composite_score ?? "—"}
                    </span>
                  </div>
                  {s.reasoning && (
                    <p className="mt-2 text-gray-400 text-sm line-clamp-2">
                      {s.reasoning}
                    </p>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
