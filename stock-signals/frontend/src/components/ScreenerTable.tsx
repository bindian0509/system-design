import { useState, useMemo } from "react";

interface ScreenerRow {
  symbol: string;
  name: string;
  sector: string | null;
  market_cap_cr: number | null;
  pe_ratio: number | null;
  roe: number | null;
  composite_score: number | null;
  signal_type: string | null;
}

interface ScreenerTableProps {
  data: ScreenerRow[];
  onRowClick: (symbol: string) => void;
}

type SortKey = keyof ScreenerRow;
type SortDir = "asc" | "desc";

function getSignalBadgeClass(signalType: string | null): string {
  if (!signalType) return "bg-gray-500/20 text-gray-400 border-gray-500/40";
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

function formatMarketCap(cr: number | null): string {
  if (cr == null) return "—";
  return `₹${cr.toLocaleString()} Cr`;
}

function sortValue(a: unknown, b: unknown, dir: SortDir): number {
  const aVal = a ?? -Infinity;
  const bVal = b ?? -Infinity;
  if (typeof aVal === "string" && typeof bVal === "string") {
    return dir === "asc"
      ? aVal.localeCompare(bVal)
      : bVal.localeCompare(aVal);
  }
  const numA = Number(aVal);
  const numB = Number(bVal);
  return dir === "asc" ? numA - numB : numB - numA;
}

export default function ScreenerTable({ data, onRowClick }: ScreenerTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("symbol");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      return sortValue(aVal, bVal, sortDir);
    });
  }, [data, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const headers: { key: SortKey; label: string }[] = [
    { key: "symbol", label: "Symbol" },
    { key: "name", label: "Name" },
    { key: "sector", label: "Sector" },
    { key: "market_cap_cr", label: "Market Cap" },
    { key: "pe_ratio", label: "P/E" },
    { key: "roe", label: "ROE %" },
    { key: "composite_score", label: "Score" },
    { key: "signal_type", label: "Signal" },
  ];

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-700/50">
      <table className="w-full min-w-[800px] text-sm">
        <thead>
          <tr className="bg-gray-800 border-b border-gray-700">
            {headers.map(({ key, label }) => (
              <th
                key={key}
                onClick={() => handleSort(key)}
                className="px-4 py-3 text-left font-medium text-gray-300 cursor-pointer hover:text-gray-100 select-none"
              >
                <span className="inline-flex items-center gap-1">
                  {label}
                  {sortKey === key && (
                    <span className="text-gray-500">{sortDir === "asc" ? "↑" : "↓"}</span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row, i) => (
            <tr
              key={row.symbol}
              onClick={() => onRowClick(row.symbol)}
              className={`
                border-b border-gray-800 cursor-pointer transition-colors
                hover:bg-gray-700/50
                ${i % 2 === 0 ? "bg-gray-900" : "bg-gray-850"}
              `}
            >
              <td className="px-4 py-3 font-semibold text-gray-100">{row.symbol}</td>
              <td className="px-4 py-3 text-gray-300 max-w-[180px] truncate">{row.name}</td>
              <td className="px-4 py-3 text-gray-400">{row.sector ?? "—"}</td>
              <td className="px-4 py-3 text-gray-300">{formatMarketCap(row.market_cap_cr)}</td>
              <td className="px-4 py-3 text-gray-300">{row.pe_ratio ?? "—"}</td>
              <td className="px-4 py-3 text-gray-300">{row.roe != null ? `${row.roe}%` : "—"}</td>
              <td className="px-4 py-3 text-gray-300">{row.composite_score ?? "—"}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex px-2 py-0.5 rounded-lg text-xs font-medium border ${getSignalBadgeClass(
                    row.signal_type
                  )}`}
                >
                  {row.signal_type ?? "—"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
