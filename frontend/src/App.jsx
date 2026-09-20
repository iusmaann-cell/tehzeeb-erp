import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Vendors from "./pages/Vendors";
import Items from "./pages/Items";
import Warehouses from "./pages/Warehouses";
import PurchaseOrders from "./pages/PurchaseOrders";
import GRN from "./pages/GRN";
import Stock from "./pages/Stock";
import StockAdjustments from "./pages/StockAdjustments";
import BOMs from "./pages/BOMs";
import ProductionOrders from "./pages/ProductionOrders";
import Customers from "./pages/Customers";
import TollIntake from "./pages/TollIntake";
import TollDelivery from "./pages/TollDelivery";
import CommissionInvoices from "./pages/CommissionInvoices";
import Distributors from "./pages/Distributors";
import SalesOrders from "./pages/SalesOrders";
import SalesDispatch from "./pages/SalesDispatch";
import SalesInvoices from "./pages/SalesInvoices";
import Expenses from "./pages/Expenses";
import Reports from "./pages/Reports";
import Employees from "./pages/Employees";
import Attendance from "./pages/Attendance";
import Payroll from "./pages/Payroll";
import BIDashboard from "./pages/BIDashboard";
import InvoiceSettings from "./pages/InvoiceSettings";

const PAGES = {
  dashboard: Dashboard,
  vendors: Vendors,
  items: Items,
  warehouses: Warehouses,
  "purchase-orders": PurchaseOrders,
  grn: GRN,
  stock: Stock,
  "stock-adjustments": StockAdjustments,
  boms: BOMs,
  "production-orders": ProductionOrders,
  customers: Customers,
  "toll-intake": TollIntake,
  "toll-delivery": TollDelivery,
  "commission-invoices": CommissionInvoices,
  distributors: Distributors,
  "sales-orders": SalesOrders,
  "sales-dispatch": SalesDispatch,
  "sales-invoices": SalesInvoices,
  expenses: Expenses,
  reports: Reports,
  employees: Employees,
  attendance: Attendance,
  payroll: Payroll,
  "bi-dashboard": BIDashboard,
  "invoice-settings": InvoiceSettings,
};

export default function App() {
  const [active, setActive] = useState("dashboard");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const Page = PAGES[active];

  function handleNavigate(key) {
    setActive(key);
    setMobileNavOpen(false);
  }

  return (
    <div className="flex min-h-screen bg-bg font-body">
      <Sidebar
        active={active}
        onNavigate={handleNavigate}
        mobileOpen={mobileNavOpen}
        onCloseMobile={() => setMobileNavOpen(false)}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        {/* Mobile-only top bar — hidden on md+ where the sidebar is always visible */}
        <header className="md:hidden sticky top-0 z-30 flex items-center gap-3 bg-surface border-b border-border px-4 py-3">
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            className="text-text-muted hover:text-text text-2xl leading-none px-1"
            aria-label="Open menu"
          >
            ☰
          </button>
          <div className="font-display font-semibold text-base">Tehzeeb ERP</div>
        </header>

        <main className="flex-1 p-4 sm:p-6 md:p-8 max-w-6xl w-full">
          <Page />
        </main>
      </div>
    </div>
  );
}
