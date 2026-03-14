import { NavLink, Outlet, Routes, Route } from "react-router-dom";
import { LayoutDashboard, Filter, Bell, BarChart3 } from "lucide-react";
import Dashboard from "./pages/Dashboard";
import Screener from "./pages/Screener";
import Alerts from "./pages/Alerts";
import StockDetail from "./pages/StockDetail";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/screener", icon: Filter, label: "Screener" },
  { to: "/alerts", icon: Bell, label: "Alerts" },
];

function NavItem({
  to,
  icon: Icon,
  label,
  end,
}: {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  end?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
          isActive
            ? "bg-gray-800 text-gray-100 border-l-2 border-l-gray-500 -ml-[2px] pl-[14px]"
            : "text-gray-400 hover:text-gray-100 hover:bg-gray-800/50"
        }`
      }
    >
      <Icon className="w-5 h-5 shrink-0" />
      <span className="hidden lg:inline">{label}</span>
    </NavLink>
  );
}

function Layout() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex">
      <aside className="fixed left-0 top-0 bottom-0 w-16 lg:w-60 flex flex-col bg-gray-900 border-r border-gray-800 z-10">
        <div className="p-4 border-b border-gray-800 shrink-0">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-gray-100 shrink-0" />
            <span className="font-semibold text-gray-100 hidden lg:inline truncate">
              StockSignals
            </span>
          </div>
        </div>
        <nav className="p-2 flex-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavItem
              key={item.to}
              to={item.to}
              icon={item.icon}
              label={item.label}
              end={item.to === "/"}
            />
          ))}
        </nav>
      </aside>
      <main className="flex-1 lg:ml-60 ml-16 p-4 md:p-6 min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="screener" element={<Screener />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="stock/:symbol" element={<StockDetail />} />
      </Route>
    </Routes>
  );
}
