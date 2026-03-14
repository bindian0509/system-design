interface SignalCardProps {
  symbol: string;
  signalType: string;
  compositeScore: number | null;
  reasoning: string | null;
  onClick?: () => void;
}

function getBorderClass(signalType: string): string {
  switch (signalType) {
    case "STRONG_BUY":
      return "border-l-green-500";
    case "BUY":
      return "border-l-emerald-500";
    case "HOLD":
      return "border-l-amber-500";
    case "EXIT":
      return "border-l-red-500";
    default:
      return "border-l-gray-500";
  }
}

function getProgressBarClass(signalType: string): string {
  switch (signalType) {
    case "STRONG_BUY":
      return "bg-green-500";
    case "BUY":
      return "bg-emerald-500";
    case "HOLD":
      return "bg-amber-500";
    case "EXIT":
      return "bg-red-500";
    default:
      return "bg-gray-500";
  }
}

function getBadgeClass(signalType: string): string {
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

export default function SignalCard({
  symbol,
  signalType,
  compositeScore,
  reasoning,
  onClick,
}: SignalCardProps) {
  const score = compositeScore ?? 0;
  const maxScore = 100;

  return (
    <div
      role={onClick ? "button" : undefined}
      onClick={onClick}
      className={`
        bg-gray-900 rounded-xl p-4 border border-gray-700/50 border-l-4
        ${getBorderClass(signalType)}
        transition-colors
        ${onClick ? "cursor-pointer hover:bg-gray-800/80 hover:border-gray-600" : ""}
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-lg font-bold text-gray-100">{symbol}</span>
        <span
          className={`inline-flex px-2 py-0.5 rounded-lg text-xs font-medium border ${getBadgeClass(
            signalType
          )}`}
        >
          {signalType}
        </span>
      </div>
      <div className="mt-2">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-gray-400">Score</span>
          <span className="text-gray-100 font-medium">
            {compositeScore != null ? compositeScore : "—"}
          </span>
        </div>
        <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${getProgressBarClass(signalType)}`}
            style={{ width: `${Math.min(100, (score / maxScore) * 100)}%` }}
          />
        </div>
      </div>
      {reasoning && (
        <p className="mt-2 text-gray-400 text-sm line-clamp-2">{reasoning}</p>
      )}
    </div>
  );
}
