import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ScreenerRow } from "../api";
import ScreenerTable from "../components/ScreenerTable";
import { RefreshCw } from "lucide-react";

export default function Screener() {
  const navigate = useNavigate();
  const [data, setData] = useState<ScreenerRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.screener().then(setData).finally(() => setLoading(false));
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
      <h1 className="text-xl font-semibold text-gray-100 mb-4">Screener</h1>
      <ScreenerTable data={data} onRowClick={(s) => navigate(`/stock/${s}`)} />
    </div>
  );
}
