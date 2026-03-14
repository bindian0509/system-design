import { Mail, MessageSquare, Send } from "lucide-react";

interface AlertItem {
  symbol: string;
  signal_type: string;
  channel: string | null;
  message: string | null;
  sent_at: string;
  success: boolean;
}

interface AlertHistoryProps {
  alerts: AlertItem[];
}

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

function getChannelIcon(channel: string | null) {
  if (!channel) return null;
  const c = channel.toLowerCase();
  if (c.includes("email") || c === "mail") return Mail;
  if (c.includes("slack") || c.includes("chat")) return MessageSquare;
  return Send;
}

function timeAgo(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString();
}

function getDateGroup(sentAt: string): "today" | "yesterday" | "older" {
  const d = new Date(sentAt);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const alertDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());

  if (alertDate.getTime() === today.getTime()) return "today";
  if (alertDate.getTime() === yesterday.getTime()) return "yesterday";
  return "older";
}

export default function AlertHistory({ alerts }: AlertHistoryProps) {
  const grouped = alerts.reduce(
    (acc, a) => {
      const g = getDateGroup(a.sent_at);
      if (!acc[g]) acc[g] = [];
      acc[g].push(a);
      return acc;
    },
    {} as Record<"today" | "yesterday" | "older", AlertItem[]>
  );

  const order: ("today" | "yesterday" | "older")[] = ["today", "yesterday", "older"];
  const labels: Record<string, string> = {
    today: "Today",
    yesterday: "Yesterday",
    older: "Older",
  };

  return (
    <div className="space-y-6">
      {order.map((key) => {
        const items = grouped[key] ?? [];
        if (items.length === 0) return null;

        return (
          <div key={key}>
            <h3 className="text-sm font-medium text-gray-400 mb-3">{labels[key]}</h3>
            <ul className="space-y-2">
              {items.map((a, i) => {
                const Icon = getChannelIcon(a.channel);
                return (
                  <li
                    key={`${a.symbol}-${a.sent_at}-${i}`}
                    className="flex items-start gap-3 bg-gray-900 rounded-xl p-4 border border-gray-700/50"
                  >
                    <span
                      className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${
                        a.success ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-gray-100">{a.symbol}</span>
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-lg text-xs font-medium border ${getSignalBadgeClass(
                            a.signal_type
                          )}`}
                        >
                          {a.signal_type}
                        </span>
                        {Icon && (
                          <span className="text-gray-500" title={a.channel ?? undefined}>
                            <Icon className="w-4 h-4" />
                          </span>
                        )}
                        <span className="text-gray-500 text-xs ml-auto shrink-0">
                          {timeAgo(a.sent_at)}
                        </span>
                      </div>
                      {a.message && (
                        <p className="mt-1 text-gray-400 text-sm line-clamp-2">{a.message}</p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
