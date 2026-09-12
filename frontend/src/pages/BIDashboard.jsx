import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, SectionTitle, Select, formatPKR } from "../components/ui";
import {
  ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  BarChart, PieChart, Pie, Cell,
} from "recharts";

const COLORS = {
  amber: "#c98a2c",
  amberSoft: "#e0a94d",
  green: "#4caf7d",
  red: "#d9615c",
  blue: "#5b8dc9",
  purple: "#9b7fd4",
  border: "#2c3341",
  textMuted: "#8a93a3",
};
const PIE_COLORS = [COLORS.amber, COLORS.green, COLORS.blue, COLORS.red, COLORS.purple, COLORS.amberSoft];

const PLANTS = ["refining", "hydrogenation", "soap", "packaging"];

function tooltipStyle() {
  return { background: "#1b212b", border: "1px solid #2c3341", borderRadius: 8, fontSize: 12 };
}

function ChartCard({ title, children, action }) {
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm font-medium text-text">{title}</div>
        {action}
      </div>
      {children}
    </Card>
  );
}

export default function BIDashboard() {
  const [months, setMonths] = useState(6);
  const [plant, setPlant] = useState("");
  const [revenueTrend, setRevenueTrend] = useState([]);
  const [yieldTrend, setYieldTrend] = useState([]);
  const [salesByDistributor, setSalesByDistributor] = useState([]);
  const [expenseBreakdown, setExpenseBreakdown] = useState([]);
  const [inventoryByType, setInventoryByType] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [rt, yt, sbd, eb, ivt] = await Promise.all([
        api.getRevenueTrend(months),
        api.getProductionYieldTrend({ months, ...(plant ? { plant } : {}) }),
        api.getSalesByDistributor(),
        api.getExpenseBreakdown(),
        api.getInventoryValueByType(),
      ]);
      setRevenueTrend(rt);
      setYieldTrend(yt);
      setSalesByDistributor(sbd.slice(0, 8));
      setExpenseBreakdown(eb);
      setInventoryByType(ivt);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, [months, plant]);

  return (
    <div>
      <SectionTitle
        eyebrow="BI Dashboards"
        title="Analytics"
        action={
          <Select value={months} onChange={(e) => setMonths(Number(e.target.value))} className="w-40">
            <option value={3}>Last 3 months</option>
            <option value={6}>Last 6 months</option>
            <option value={12}>Last 12 months</option>
          </Select>
        }
      />

      {loading && <div className="text-text-muted text-sm mb-4">Loading&hellip;</div>}

      <div className="space-y-6">
        <ChartCard title="Revenue &amp; Net Profit Trend">
          {revenueTrend.length === 0 ? (
            <div className="text-text-muted text-sm py-8 text-center">No revenue data in this range yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={revenueTrend}>
                <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" />
                <XAxis dataKey="month" stroke={COLORS.textMuted} fontSize={12} />
                <YAxis stroke={COLORS.textMuted} fontSize={12} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip contentStyle={tooltipStyle()} formatter={(v) => `Rs. ${formatPKR(v)}`} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="sales_revenue" name="Sales Revenue" stackId="rev" fill={COLORS.amber} radius={[0, 0, 0, 0]} />
                <Bar dataKey="commission_revenue" name="Commission Revenue" stackId="rev" fill={COLORS.amberSoft} radius={[4, 4, 0, 0]} />
                <Bar dataKey="expenses" name="Expenses" fill={COLORS.red} opacity={0.6} />
                <Line type="monotone" dataKey="net_profit" name="Net Profit" stroke={COLORS.green} strokeWidth={2.5} dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <ChartCard title="Sales by Distributor (last 90 days)">
            {salesByDistributor.length === 0 ? (
              <div className="text-text-muted text-sm py-8 text-center">No sales invoices yet.</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={salesByDistributor} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" stroke={COLORS.textMuted} fontSize={12} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <YAxis type="category" dataKey="distributor_name" stroke={COLORS.textMuted} fontSize={12} width={110} />
                  <Tooltip contentStyle={tooltipStyle()} formatter={(v) => `Rs. ${formatPKR(v)}`} />
                  <Bar dataKey="revenue" fill={COLORS.amber} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="Expense Breakdown (last 90 days)">
            {expenseBreakdown.length === 0 ? (
              <div className="text-text-muted text-sm py-8 text-center">No expenses logged yet.</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={expenseBreakdown} dataKey="total" nameKey="category" cx="50%" cy="50%" outerRadius={90} label={(d) => d.category}>
                    {expenseBreakdown.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle()} formatter={(v) => `Rs. ${formatPKR(v)}`} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <ChartCard
            title="Production Yield Trend"
            action={
              <Select value={plant} onChange={(e) => setPlant(e.target.value)} className="w-36">
                <option value="">All plants</option>
                {PLANTS.map((p) => <option key={p} value={p}>{p}</option>)}
              </Select>
            }
          >
            {yieldTrend.length === 0 ? (
              <div className="text-text-muted text-sm py-8 text-center">No completed production batches in this range yet.</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={yieldTrend}>
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" />
                  <XAxis dataKey="month" stroke={COLORS.textMuted} fontSize={12} />
                  <YAxis stroke={COLORS.textMuted} fontSize={12} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                  <Tooltip contentStyle={tooltipStyle()} formatter={(v, name) => name === "avg_yield_percent" ? `${v.toFixed(1)}%` : v} />
                  <Line type="monotone" dataKey="avg_yield_percent" name="Avg Yield %" stroke={COLORS.amber} strokeWidth={2.5} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="Inventory Value by Type">
            {inventoryByType.length === 0 ? (
              <div className="text-text-muted text-sm py-8 text-center">No owned stock on hand.</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={inventoryByType} dataKey="value" nameKey="item_type" cx="50%" cy="50%" outerRadius={90} label={(d) => d.item_type.replace("_", " ")}>
                    {inventoryByType.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle()} formatter={(v) => `Rs. ${formatPKR(v)}`} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>
      </div>
    </div>
  );
}
