import { useEffect, useState } from "react";
import { api } from "../api";
import { generateDocNumber } from "../docNumbers";
import { Card, SectionTitle, Button, Input, Select, Table, Badge, formatPKR } from "../components/ui";

const STATUS_TONES = { pending: "amber", approved: "green" };

export default function StockAdjustments() {
  const [adjustments, setAdjustments] = useState([]);
  const [items, setItems] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [stock, setStock] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [adjustmentNumber, setAdjustmentNumber] = useState("");
  const [itemId, setItemId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [direction, setDirection] = useState("decrease");
  const [quantity, setQuantity] = useState("");
  const [rate, setRate] = useState("");
  const [batchNo, setBatchNo] = useState("");
  const [reasonComment, setReasonComment] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [approvingId, setApprovingId] = useState(null);
  const [approverName, setApproverName] = useState("");

  async function load() {
    const [adjData, itemData, whData, stockData] = await Promise.all([
      api.getStockAdjustments(), api.getItems(), api.getWarehouses(), api.getStockBalance(),
    ]);
    setAdjustments(adjData);
    setItems(itemData);
    setWarehouses(whData);
    setStock(stockData.filter((s) => !s.is_toll_stock));
  }
  useEffect(() => { load(); }, []);

  const itemLookup = Object.fromEntries(items.map((i) => [i.id, i.name]));
  const warehouseLookup = Object.fromEntries(warehouses.map((w) => [w.id, w.name]));

  function openForm() {
    setAdjustmentNumber(generateDocNumber("ADJ"));
    setItemId(""); setWarehouseId(""); setDirection("decrease");
    setQuantity(""); setRate(""); setBatchNo(""); setReasonComment("");
    setError("");
    setShowForm(true);
  }

  const relevantStock = itemId && warehouseId
    ? stock.filter((s) => s.item_id === Number(itemId) && s.warehouse_id === Number(warehouseId))
    : [];
  const availableTotal = relevantStock.reduce((s, r) => s + r.quantity, 0);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!reasonComment.trim()) {
      setError("A reason comment is required.");
      return;
    }
    if (direction === "increase" && (!batchNo || !rate)) {
      setError("Increasing stock needs a new batch label and a value (rate).");
      return;
    }
    try {
      setSaving(true);
      await api.createStockAdjustment({
        adjustment_number: adjustmentNumber,
        item_id: Number(itemId),
        warehouse_id: Number(warehouseId),
        direction,
        quantity: Number(quantity),
        rate: rate ? Number(rate) : null,
        batch_no: batchNo || null,
        reason_comment: reasonComment,
      });
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove(id) {
    if (!approverName.trim()) {
      alert("Enter your name to approve this adjustment.");
      return;
    }
    await api.approveStockAdjustment(id, approverName);
    setApprovingId(null);
    load();
  }

  return (
    <div>
      <SectionTitle
        eyebrow="Inventory"
        title="Stock Adjustments"
        action={<Button onClick={() => (showForm ? setShowForm(false) : openForm())}>{showForm ? "Cancel" : "+ New Adjustment"}</Button>}
      />

      <Card className="mb-6 border-amber/30">
        <div className="text-xs text-text-muted">
          Use this to correct the book quantity when a physical check (e.g. a tank dip reading) disagrees
          with what the system shows — not for normal purchases, production, or sales. Every adjustment
          needs a reason and is posted to the stock ledger immediately; the pending/approved status is an
          audit-review flag only, since there's no login system yet to restrict who can approve.
        </div>
      </Card>

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Input label="Adjustment number" required value={adjustmentNumber} onChange={(e) => setAdjustmentNumber(e.target.value)} />
              <Select label="Item" value={itemId} onChange={(e) => setItemId(e.target.value)}>
                <option value="">Select item&hellip;</option>
                {items.map((it) => <option key={it.id} value={it.id}>{it.name}</option>)}
              </Select>
              <Select label="Warehouse" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                <option value="">Select warehouse&hellip;</option>
                {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </div>

            {itemId && warehouseId && (
              <div className="text-xs text-text-muted bg-surface-2 rounded-md p-2">
                Current book balance here: <span className="stencil text-amber-soft">{availableTotal}</span>
                {relevantStock.length > 0 && (
                  <span> across batches: {relevantStock.map((r) => `${r.batch_no} (${r.quantity})`).join(", ")}</span>
                )}
              </div>
            )}

            <div className="flex gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input type="radio" checked={direction === "decrease"} onChange={() => setDirection("decrease")} />
                Decrease (physical count found LESS)
              </label>
              <label className="flex items-center gap-2">
                <input type="radio" checked={direction === "increase"} onChange={() => setDirection("increase")} />
                Increase (physical count found MORE)
              </label>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Input label="Quantity" type="number" required value={quantity} onChange={(e) => setQuantity(e.target.value)} />
              {direction === "increase" ? (
                <>
                  <Input label="New batch label" required value={batchNo} onChange={(e) => setBatchNo(e.target.value)} />
                  <Input label="Value (Rs. per unit)" type="number" required value={rate} onChange={(e) => setRate(e.target.value)} />
                </>
              ) : (
                <Input label="Specific batch (optional — FIFO if blank)" value={batchNo} onChange={(e) => setBatchNo(e.target.value)} />
              )}
            </div>

            <div>
              <label className="block text-xs text-text-muted mb-1">Reason (required)</label>
              <textarea
                className="w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-amber focus:border-amber"
                rows={2}
                required
                value={reasonComment}
                onChange={(e) => setReasonComment(e.target.value)}
                placeholder="e.g. Monthly tank dip reading came in lower than book balance — evaporation loss"
              />
            </div>

            <div className="flex items-center gap-3 border-t border-border pt-4">
              <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save Adjustment"}</Button>
              {error && <span className="text-red text-sm">{error}</span>}
            </div>
          </form>
        </Card>
      )}

      <Card>
        <Table
          emptyLabel="No stock adjustments yet."
          columns={[
            { key: "adjustment_number", label: "Number", mono: true },
            { key: "item", label: "Item", render: (row) => itemLookup[row.item_id] || "—" },
            { key: "warehouse", label: "Warehouse", render: (row) => warehouseLookup[row.warehouse_id] || "—" },
            { key: "direction", label: "Direction", render: (row) => <Badge tone={row.direction === "increase" ? "green" : "red"}>{row.direction}</Badge> },
            { key: "quantity", label: "Qty", mono: true },
            { key: "value", label: "Value", mono: true, render: (row) => `Rs. ${formatPKR(row.quantity * row.rate)}` },
            { key: "reason", label: "Reason", render: (row) => <span className="text-xs">{row.reason_comment}</span> },
            { key: "date", label: "Date", render: (row) => new Date(row.adjustment_date).toLocaleDateString() },
            {
              key: "status", label: "Status",
              render: (row) => row.status === "approved"
                ? <div><Badge tone="green">approved</Badge><div className="text-[10px] text-text-muted mt-0.5">by {row.approved_by}</div></div>
                : approvingId === row.id
                  ? (
                    <div className="flex items-center gap-1">
                      <input
                        className="w-24 bg-surface-2 border border-border rounded px-1.5 py-0.5 text-xs"
                        placeholder="Your name"
                        value={approverName}
                        onChange={(e) => setApproverName(e.target.value)}
                      />
                      <button type="button" className="text-xs text-amber-soft hover:underline" onClick={() => handleApprove(row.id)}>Confirm</button>
                    </div>
                  )
                  : (
                    <button type="button" onClick={() => { setApprovingId(row.id); setApproverName(""); }}>
                      <Badge tone="amber">pending</Badge>
                    </button>
                  ),
            },
          ]}
          rows={adjustments}
        />
      </Card>
    </div>
  );
}
