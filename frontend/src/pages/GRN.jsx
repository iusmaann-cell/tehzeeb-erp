import { useEffect, useState } from "react";
import { api } from "../api";
import { generateDocNumber } from "../docNumbers";
import { Card, SectionTitle, Button, Input, Select, Table, formatPKR } from "../components/ui";
import BillPhotoUpload from "../components/BillPhotoUpload";

export default function GRN() {
  const [grns, setGrns] = useState([]);
  const [pos, setPos] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [selectedPoId, setSelectedPoId] = useState("");
  const [grnNumber, setGrnNumber] = useState("");
  const [vehicleNo, setVehicleNo] = useState("");
  const [receiveLines, setReceiveLines] = useState([]); // one per PO line still open
  const [billPhoto, setBillPhoto] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    const [grnData, poData, whData] = await Promise.all([api.getGRNs(), api.getPurchaseOrders(), api.getWarehouses()]);
    setGrns(grnData.sort((a, b) => b.id - a.id));
    setPos(poData.filter((p) => p.status === "approved" || p.status === "partially_received"));
    setWarehouses(whData);
  }

  useEffect(() => { load(); }, []);

  function selectPo(poId) {
    setSelectedPoId(poId);
    const po = pos.find((p) => p.id === Number(poId));
    if (!po) { setReceiveLines([]); return; }
    setReceiveLines(
      po.lines
        .filter((l) => l.received_quantity < l.quantity - 1e-6)
        .map((l) => ({
          po_line_id: l.id,
          item_id: l.item_id,
          remaining: l.quantity - l.received_quantity,
          quantity: l.quantity - l.received_quantity,
          rate: l.rate,
          warehouse_id: "",
          batch_no: "",
        }))
    );
  }

  function updateLine(i, field, value) {
    const next = [...receiveLines];
    next[i] = { ...next[i], [field]: value };
    setReceiveLines(next);
  }

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    if (!billPhoto) {
      setError("A photo of the vendor's bill is required.");
      return;
    }
    try {
      const lines = receiveLines
        .filter((l) => l.quantity && l.warehouse_id && l.batch_no)
        .map((l) => ({
          po_line_id: l.po_line_id,
          item_id: l.item_id,
          warehouse_id: Number(l.warehouse_id),
          batch_no: l.batch_no,
          quantity: Number(l.quantity),
          rate: Number(l.rate),
        }));
      if (lines.length === 0) {
        setError("Fill in warehouse and batch number for at least one line.");
        return;
      }
      setSaving(true);
      await api.createGRN({
        grn_number: grnNumber,
        purchase_order_id: Number(selectedPoId),
        vehicle_no: vehicleNo,
        lines,
      }, billPhoto);
      setGrnNumber("");
      setVehicleNo("");
      setSelectedPoId("");
      setReceiveLines([]);
      setBillPhoto(null);
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <SectionTitle
        eyebrow="Procurement"
        title="Goods Received (GRN)"
        action={<Button onClick={() => { if (!showForm) setGrnNumber(generateDocNumber("GRN")); setShowForm((s) => !s); }}>{showForm ? "Cancel" : "+ Receive Goods"}</Button>}
      />

      {showForm && (
        <Card className="mb-6">
          {pos.length === 0 ? (
            <div className="text-text-muted text-sm">No open purchase orders to receive against. Create one first.</div>
          ) : (
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <Select label="Purchase order" value={selectedPoId} onChange={(e) => selectPo(e.target.value)}>
                  <option value="">Select PO&hellip;</option>
                  {pos.map((p) => <option key={p.id} value={p.id}>{p.po_number}</option>)}
                </Select>
                <Input label="GRN number" placeholder="GRN-2026-0001" required value={grnNumber} onChange={(e) => setGrnNumber(e.target.value)} />
                <Input label="Vehicle no. (optional)" placeholder="BWP-1234" value={vehicleNo} onChange={(e) => setVehicleNo(e.target.value)} />
              </div>

              {receiveLines.length > 0 && (
                <div>
                  <div className="text-xs text-text-muted mb-2">Receiving lines &mdash; enter batch number and destination warehouse</div>
                  <div className="space-y-3">
                    {receiveLines.map((line, i) => (
                      <div key={line.po_line_id} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_1fr_1fr] gap-3 items-end bg-surface-2 rounded-md p-3">
                        <div className="text-sm stencil text-text-muted col-span-4 -mb-1">
                          Remaining: {line.remaining} &middot; Rate Rs. {formatPKR(line.rate)}
                        </div>
                        <Input label="Quantity received" type="number" max={line.remaining} value={line.quantity} onChange={(e) => updateLine(i, "quantity", e.target.value)} />
                        <Input label="Batch / lot no." placeholder="BATCH-001" value={line.batch_no} onChange={(e) => updateLine(i, "batch_no", e.target.value)} />
                        <Select label="Warehouse" value={line.warehouse_id} onChange={(e) => updateLine(i, "warehouse_id", e.target.value)}>
                          <option value="">Select&hellip;</option>
                          {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                        </Select>
                        <Input label="Rate (Rs.)" type="number" value={line.rate} onChange={(e) => updateLine(i, "rate", e.target.value)} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <BillPhotoUpload file={billPhoto} onChange={setBillPhoto} />

              <div className="flex items-center gap-3 border-t border-border pt-4">
                <Button type="submit" disabled={!selectedPoId || saving}>{saving ? "Uploading & Saving…" : "Save GRN"}</Button>
                {error && <span className="text-red text-sm">{error}</span>}
              </div>
            </form>
          )}
        </Card>
      )}

      <Card>
        <Table
          emptyLabel="No goods received yet."
          columns={[
            { key: "grn_number", label: "GRN Number", mono: true },
            { key: "vehicle_no", label: "Vehicle", render: (row) => row.vehicle_no || "—" },
            { key: "received_date", label: "Date", render: (row) => new Date(row.received_date).toLocaleDateString() },
            { key: "batches", label: "Batches", mono: true, render: (row) => row.lines.map((l) => l.batch_no).join(", ") },
            {
              key: "qty",
              label: "Total quantity",
              render: (row) => row.lines.reduce((s, l) => s + l.quantity, 0),
            },
            {
              key: "bill", label: "Bill photo",
              render: (row) => row.bill_photo_url
                ? <a href={row.bill_photo_url} target="_blank" rel="noreferrer" className="text-xs text-amber-soft hover:underline">View</a>
                : <span className="text-xs text-text-muted">—</span>,
            },
          ]}
          rows={grns}
        />
      </Card>
    </div>
  );
}
