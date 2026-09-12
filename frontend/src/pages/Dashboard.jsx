import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, SectionTitle, Input, Button, formatPKR } from "../components/ui";

function Stat({ label, value, sub }) {
  return (
    <Card>
      <div className="text-xs text-text-muted uppercase tracking-wide mb-2">{label}</div>
      <div className="font-display text-3xl font-semibold text-text stencil">{value}</div>
      {sub && <div className="text-xs text-text-muted mt-1">{sub}</div>}
    </Card>
  );
}

function todayStr() { return new Date().toISOString().slice(0, 10); }
function daysAgoStr(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const [dateFrom, setDateFrom] = useState(daysAgoStr(30));
  const [dateTo, setDateTo] = useState(todayStr());

  async function load() {
    try {
      const rangeParams = { start_date: `${dateFrom}T00:00:00`, end_date: `${dateTo}T23:59:59` };
      const inRange = (dateStr) => {
        const d = new Date(dateStr);
        return d >= new Date(rangeParams.start_date) && d <= new Date(rangeParams.end_date);
      };

      const [vendors, items, pos, grns, stock, productionOrders, customers, distributors, salesOrders, employees] = await Promise.all([
        api.getVendors(),
        api.getItems(),
        api.getPurchaseOrders(),
        api.getGRNs(),
        api.getStockBalance(),
        api.getProductionOrders(),
        api.getCustomers(),
        api.getDistributors(),
        api.getSalesOrders(),
        api.getEmployees(),
      ]);

      // current-state figures — a balance is "as of now", not bound to a date range,
      // so these stay unfiltered but are labeled "current" to avoid confusion
      const balances = await Promise.all(vendors.map((v) => api.getVendorBalance(v.id)));
      const totalOwed = balances.reduce((s, b) => s + b.balance, 0);
      const customerBalances = await Promise.all(customers.map((c) => api.getCustomerBalance(c.id)));
      const totalOwedByCustomers = customerBalances.reduce((s, b) => s + b.balance, 0);
      const distributorBalances = await Promise.all(distributors.map((d) => api.getDistributorBalance(d.id)));
      const totalOwedByDistributors = distributorBalances.reduce((s, b) => s + b.balance, 0);
      const ownedStockBatches = stock.filter((s) => !s.is_toll_stock).length;

      // date-scoped figures — everything below only counts activity within the
      // selected range
      const posInRange = pos.filter((p) => inRange(p.order_date));
      const openPOs = posInRange.filter((p) => p.status === "approved" || p.status === "partially_received").length;

      const grnsInRange = grns.filter((g) => inRange(g.received_date));

      const productionOrdersInRange = productionOrders.filter((o) => inRange(o.order_date));
      const yieldOrders = productionOrdersInRange.filter((o) => o.yield_percent != null);
      const avgYield = yieldOrders.length ? yieldOrders.reduce((s, o) => s + o.yield_percent, 0) / yieldOrders.length : null;

      const salesOrdersInRange = salesOrders.filter((s) => inRange(s.order_date));
      const openSalesOrders = salesOrdersInRange.filter((s) => s.status === "approved" || s.status === "partially_dispatched").length;

      let pnl = null;
      try {
        pnl = await api.getPnL(rangeParams);
      } catch (e) { /* ignore — not critical for the rest of the dashboard */ }

      setStats({
        vendorCount: vendors.length,
        itemCount: items.length,
        openPOs,
        grnCount: grnsInRange.length,
        totalOwed,
        ownedStockBatches,
        productionOrderCount: productionOrdersInRange.length,
        avgYield,
        customerCount: customers.length,
        totalOwedByCustomers,
        totalCommissionRevenue: pnl?.commission_revenue ?? null,
        distributorCount: distributors.length,
        totalOwedByDistributors,
        totalSalesRevenue: pnl?.sales_revenue ?? null,
        openSalesOrders,
        netProfit: pnl?.net_profit ?? null,
        employeeCount: employees.length,
      });
    } catch (err) {
      setError(err.message || "Something went wrong loading the dashboard.");
    }
  }

  useEffect(() => { load(); }, [dateFrom, dateTo]);

  function setQuickRange(days) {
    setDateFrom(daysAgoStr(days));
    setDateTo(todayStr());
  }

  return (
    <div>
      <SectionTitle
        eyebrow="Overview"
        title="Mill Dashboard"
        action={
          <div className="flex items-end gap-2 flex-wrap">
            <Input label="From" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <Input label="To" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            <Button variant="secondary" onClick={() => setQuickRange(7)}>7d</Button>
            <Button variant="secondary" onClick={() => setQuickRange(30)}>30d</Button>
            <Button variant="secondary" onClick={() => setQuickRange(365)}>1y</Button>
          </div>
        }
      />

      {error ? (
        <div className="text-red text-sm border border-red/30 bg-red/10 rounded-md p-4">
          Couldn't load the dashboard: {error}
        </div>
      ) : !stats ? (
        <div className="text-text-muted text-sm">Loading&hellip;</div>
      ) : (
        <>
          <div className="text-xs text-text-muted mb-4">
            Transactional figures below reflect <span className="text-amber-soft">{dateFrom}</span> to <span className="text-amber-soft">{dateTo}</span>.
            Balances owed are always as of today (a balance isn't bound to a date range).
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <Stat label="Active vendors" value={stats.vendorCount} sub="all time" />
            <Stat label="Items in master" value={stats.itemCount} sub="all time" />
            <Stat label="Open purchase orders" value={stats.openPOs} sub="in selected range" />
            <Stat label="GRNs recorded" value={stats.grnCount} sub="in selected range" />
            <Stat label="Total owed to vendors" value={`Rs. ${formatPKR(stats.totalOwed)}`} sub="current" />
            <Stat label="Stock batches on hand" value={stats.ownedStockBatches} sub="current, owned inventory" />
            <Stat label="Production batches run" value={stats.productionOrderCount} sub="in selected range" />
            <Stat label="Average yield" value={stats.avgYield ? `${stats.avgYield.toFixed(1)}%` : "—"} sub="in selected range" />
            <Stat label="Toll customers" value={stats.customerCount} sub="all time" />
            <Stat label="Owed by toll customers" value={`Rs. ${formatPKR(stats.totalOwedByCustomers)}`} sub="current" />
            <Stat label="Commission revenue" value={stats.totalCommissionRevenue != null ? `Rs. ${formatPKR(stats.totalCommissionRevenue)}` : "—"} sub="in selected range" />
            <Stat label="Distributors" value={stats.distributorCount} sub="all time" />
            <Stat label="Open sales orders" value={stats.openSalesOrders} sub="in selected range" />
            <Stat label="Owed by distributors" value={`Rs. ${formatPKR(stats.totalOwedByDistributors)}`} sub="current" />
            <Stat label="Sales revenue" value={stats.totalSalesRevenue != null ? `Rs. ${formatPKR(stats.totalSalesRevenue)}` : "—"} sub="in selected range" />
            <Stat label="Net profit" value={stats.netProfit != null ? `Rs. ${formatPKR(stats.netProfit)}` : "—"} sub="in selected range — see Reports for detail" />
            <Stat label="Employees" value={stats.employeeCount} sub="all time" />
          </div>
        </>
      )}
    </div>
  );
}
