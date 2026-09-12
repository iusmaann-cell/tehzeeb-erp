import { useEffect, useState } from "react";
import { api } from "../api";
import { generateDocNumber } from "../docNumbers";
import { Card, SectionTitle, Button, Input, Select, Table, Badge, RowActions, formatPKR } from "../components/ui";
import PaymentStatusModal from "../components/PaymentStatusModal";

const STATUS_TONES = { draft: "neutral", approved: "amber", partially_received: "amber", completed: "green", cancelled: "red" };
const STATUSES = ["draft", "approved", "partially_received", "completed", "cancelled"];
const PAYMENT_TONES = { paid: "green", unpaid: "red" };

function emptyLine() {
  return { item_id: "", quantity: "", rate: "" };
}

export default function PurchaseOrders() {
  const [pos, setPos] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [items, setItems] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [poNumber, setPoNumber] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState([emptyLine()]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [paymentModalPo, setPaymentModalPo] = useState(null);

  async function load() {
    const [poData, vendorData, itemData] = await Promise.all([
      api.getPurchaseOrders(),
      api.getVendors(),
      api.getItems(),
    ]);
    setPos(poData.sort((a, b) => b.id - a.id));
    setVendors(vendorData);
    setItems(itemData);
  }

  useEffect(() => { load(); }, []);

  function hasReceipts(po) {
    return po.lines.some((l) => l.received_quantity > 0);
  }

  function resetForm() {
    setPoNumber(generateDocNumber("PO")); setNotes(""); setLines([emptyLine()]);
    setVendorId(vendors[0]?.id || "");
  }

  function startCreate() {
    setEditingId(null);
    resetForm();
    setShowForm(true);
  }

  function startEdit(po) {
    setEditingId(po.id);
    setPoNumber(po.po_number);
    setVendorId(po.vendor_id);
    setNotes(po.notes || "");
    setLines(po.lines.map((l) => ({ item_id: l.item_id, quantity: l.quantity, rate: l.rate })));
    setShowForm(true);
  }

  function updateLine(i, field, value) {
    const next = [...lines];
    next[i] = { ...next[i], [field]: value };
    setLines(next);
  }

  function addLine() { setLines([...lines, emptyLine()]); }
  function removeLine(i) { setLines(lines.filter((_, idx) => idx !== i)); }

  const total = lines.reduce((sum, l) => sum + (Number(l.quantity) || 0) * (Number(l.rate) || 0), 0);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        po_number: poNumber,
        vendor_id: Number(vendorId),
        notes,
        lines: lines
          .filter((l) => l.item_id && l.quantity && l.rate)
          .map((l) => ({ item_id: Number(l.item_id), quantity: Number(l.quantity), rate: Number(l.rate) })),
      };
      if (editingId) {
        await api.updatePurchaseOrder(editingId, payload);
      } else {
        await api.createPurchaseOrder(payload);
      }
      setEditingId(null);
      resetForm();
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(po) {
    try {
      await api.deletePurchaseOrder(po.id);
      load();
    } catch (err) {
      alert(err.message);
    }
  }

  async function handleCancel(po) {
    await api.cancelPurchaseOrder(po.id);
    load();
  }

  async function markUnpaid(po) {
    if (!window.confirm(`Mark ${po.po_number} as unpaid? This reverses the recorded payment in the vendor's ledger.`)) return;
    await api.updatePOPaymentStatus(po.id, { payment_status: "unpaid" });
    load();
  }

  async function confirmPaid(detail) {
    await api.updatePOPaymentStatus(paymentModalPo.id, { payment_status: "paid", ...detail });
    load();
  }

  const vendorLookup = Object.fromEntries(vendors.map((v) => [v.id, v.name]));

  const filteredPos = pos.filter((po) => {
    const q = search.trim().toLowerCase();
    const matchesSearch = !q || po.po_number.toLowerCase().includes(q) || (vendorLookup[po.vendor_id] || "").toLowerCase().includes(q);
    const matchesStatus = statusFilter === "all" || po.status === statusFilter;
    const orderDate = new Date(po.order_date);
    const matchesFrom = !dateFrom || orderDate >= new Date(dateFrom);
    const matchesTo = !dateTo || orderDate <= new Date(`${dateTo}T23:59:59`);
    return matchesSearch && matchesStatus && matchesFrom && matchesTo;
  });

  return (
    <div>
      <SectionTitle
        eyebrow="Procurement"
        title="Purchase Orders"
        action={<Button onClick={() => (showForm ? setShowForm(false) : startCreate())}>{showForm ? "Cancel" : "+ New Purchase Order"}</Button>}
      />

      {showForm && (
        <Card className="mb-6">
          {vendors.length === 0 || items.length === 0 ? (
            <div className="text-text-muted text-sm">Add at least one vendor and one item before creating a purchase order.</div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <Input label="PO number" placeholder="PO-2026-0001" required value={poNumber} onChange={(e) => setPoNumber(e.target.value)} />
                <Select label="Vendor" value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
                  {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                </Select>
                <Input label="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>

              <div>
                <div className="text-xs text-text-muted mb-2">Line items</div>
                <div className="space-y-2">
                  {lines.map((line, i) => (
                    <div key={i} className="grid grid-cols-1 sm:grid-cols-[2fr_1fr_1fr_auto] gap-3 items-end">
                      <Select label={i === 0 ? "Item" : undefined} value={line.item_id} onChange={(e) => updateLine(i, "item_id", e.target.value)}>
                        <option value="">Select item&hellip;</option>
                        {items.map((it) => <option key={it.id} value={it.id}>{it.name} ({it.code})</option>)}
                      </Select>
                      <Input label={i === 0 ? "Quantity" : undefined} type="number" placeholder="Qty" value={line.quantity} onChange={(e) => updateLine(i, "quantity", e.target.value)} />
                      <Input label={i === 0 ? "Rate (Rs.)" : undefined} type="number" placeholder="Rate" value={line.rate} onChange={(e) => updateLine(i, "rate", e.target.value)} />
                      <Button type="button" variant="ghost" onClick={() => removeLine(i)} disabled={lines.length === 1}>✕</Button>
                    </div>
                  ))}
                </div>
                <Button type="button" variant="secondary" className="mt-3" onClick={addLine}>+ Add line</Button>
              </div>

              <div className="flex items-center justify-between border-t border-border pt-4">
                <div className="stencil text-sm text-text-muted">
                  Total: <span className="text-amber-soft">Rs. {formatPKR(total)}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Button type="submit">{editingId ? "Save Changes" : "Save Purchase Order"}</Button>
                  {error && <span className="text-red text-sm">{error}</span>}
                </div>
              </div>
            </form>
          )}
        </Card>
      )}

      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <Input label="Search" placeholder="PO number or vendor…" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
        <Select label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="max-w-xs">
          <option value="all">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </Select>
        <Input label="From date" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <Input label="To date" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        {(search || statusFilter !== "all" || dateFrom || dateTo) && (
          <Button variant="ghost" onClick={() => { setSearch(""); setStatusFilter("all"); setDateFrom(""); setDateTo(""); }}>
            Clear filters
          </Button>
        )}
      </div>

      <Card>
        <Table
          emptyLabel={pos.length === 0 ? "No purchase orders yet." : "No purchase orders match your search/filter."}
          columns={[
            { key: "po_number", label: "PO Number", mono: true },
            { key: "vendor", label: "Vendor", render: (row) => vendorLookup[row.vendor_id] || "—" },
            { key: "order_date", label: "Date", render: (row) => new Date(row.order_date).toLocaleDateString() },
            {
              key: "value",
              label: "Value",
              mono: true,
              render: (row) => `Rs. ${formatPKR(row.lines.reduce((s, l) => s + l.quantity * l.rate, 0))}`,
            },
            { key: "status", label: "Status", render: (row) => <Badge tone={STATUS_TONES[row.status]}>{row.status.replace(/_/g, " ")}</Badge> },
            {
              key: "payment_status", label: "Payment",
              render: (row) => (
                <button
                  type="button"
                  onClick={() => row.payment_status === "paid" ? markUnpaid(row) : setPaymentModalPo(row)}
                  title="Click to change payment status"
                >
                  <Badge tone={PAYMENT_TONES[row.payment_status]}>{row.payment_status}</Badge>
                </button>
              ),
            },
            {
              key: "actions",
              label: "",
              render: (row) => {
                const blocked = hasReceipts(row);
                if (blocked) {
                  return row.status === "cancelled"
                    ? <span className="text-text-muted text-xs">—</span>
                    : (
                      <button
                        type="button"
                        className="text-xs text-amber-soft hover:underline"
                        onClick={() => { if (window.confirm(`Cancel ${row.po_number}? It already has goods received, so it can't be deleted, but cancelling marks it closed.`)) handleCancel(row); }}
                      >
                        Cancel
                      </button>
                    );
                }
                return (
                  <RowActions
                    onEdit={() => startEdit(row)}
                    onDelete={() => handleDelete(row)}
                    deleteConfirm={`Delete ${row.po_number}? This can't be undone.`}
                  />
                );
              },
            },
          ]}
          rows={filteredPos}
        />
      </Card>

      {paymentModalPo && (
        <PaymentStatusModal
          title={`Mark ${paymentModalPo.po_number} as Paid`}
          amountLabel="PO total"
          amount={formatPKR(paymentModalPo.lines.reduce((s, l) => s + l.quantity * l.rate, 0))}
          direction="outgoing"
          onClose={() => setPaymentModalPo(null)}
          onSubmit={confirmPaid}
        />
      )}
    </div>
  );
}
