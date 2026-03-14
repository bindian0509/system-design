import { useEffect, useState } from "react";
import { api, AlertItem } from "../api";
import AlertHistory from "../components/AlertHistory";
import { RefreshCw } from "lucide-react";

export default function Alerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.alerts().then(setAlerts).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="w-10 h-10 text-gray-500 animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-gray-100 mb-4">Alert History</h1>
      <AlertHistory alerts={alerts} />
    </div>
  );
}
