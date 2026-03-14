import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  TooltipProps,
} from "recharts";

interface ChartDataPoint {
  trade_date: string;
  close: number;
  volume: number;
}

interface StockChartProps {
  data: ChartDataPoint[];
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

function PriceTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length || !label) return null;
  const d = payload[0]?.payload as ChartDataPoint;
  return (
    <div className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm shadow-xl">
      <p className="text-gray-300 font-medium">{new Date(d.trade_date).toLocaleDateString()}</p>
      <p className="text-gray-100">Price: ₹{d.close.toLocaleString()}</p>
      <p className="text-gray-400">Volume: {d.volume.toLocaleString()}</p>
    </div>
  );
}

export default function StockChart({ data }: StockChartProps) {
  const sortedData = [...data].sort(
    (a, b) => new Date(a.trade_date).getTime() - new Date(b.trade_date).getTime()
  );

  return (
    <div className="space-y-2">
      <div className="bg-gray-800 rounded-xl p-4">
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={sortedData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
            <defs>
              <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22c55e" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="trade_date"
              tickFormatter={formatDate}
              stroke="#9ca3af"
              fontSize={11}
              tickLine={false}
            />
            <YAxis
              dataKey="close"
              stroke="#9ca3af"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `₹${v}`}
            />
            <Tooltip content={<PriceTooltip />} />
            <Area
              type="monotone"
              dataKey="close"
              stroke="#22c55e"
              strokeWidth={2}
              fill="url(#priceGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="bg-gray-800 rounded-xl p-4" style={{ height: 60 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={sortedData} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
            <XAxis
              dataKey="trade_date"
              tickFormatter={formatDate}
              stroke="#9ca3af"
              fontSize={10}
              tickLine={false}
              hide
            />
            <YAxis stroke="#9ca3af" fontSize={10} tickLine={false} width={40} hide />
            <Bar dataKey="volume" fill="#4b5563" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
