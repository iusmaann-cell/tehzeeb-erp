import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, SectionTitle, Button, Input, Select, Table, Badge, RowActions, Modal, formatPKR } from "../components/ui";
import PaymentMethodFields, { emptyPaymentDetail, paymentMethodLabel } from "../components/PaymentMethodFields";
import BillPhotoUpload from "../components/BillPhotoUpload";

const CATEGORIES = ["salaries", "utilities", "rent", "maintenance", "transport", "fuel", "admin", "other"];
const PLANTS = ["refining", "hydrogenation", "soap", "packaging"];

const emptyForm = { category: "salaries", plant: "", amount: "", description: "", notes: "", ...emptyPaymentDetail() };

function receiptPreviewUrl(driveFileId) {
  // Google's documented embeddable-thumbnail endpoint — works for any file shared
  // as "anyone with the link can view" (which is how we upload every bill photo).
  return `https://drive.google.com/thumbnail?id=${driveFileId}&sz=w1200`;
}

export default function Expenses() {
  const [expenses, setExpenses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [billPhoto, setBillPhoto] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [previewExpense, setPreviewExpense] = useState(null);
  const [previewFailed, setPreviewFailed] = useState(false);

  async function load() {
    setExpenses(await api.getExpenses());
  }
  useEffect(() => { load(); }, []);

  function startCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setBillPhoto(null);
    setShowForm(true);
  }

  function startEdit(exp) {
    setEditingId(exp.id);
    setForm({
      category: exp.category, plant: exp.plant || "", amount: exp.amount, description: exp.description || "", notes: exp.notes || "",
      payment_method: exp.payment_method || "cash", cheque_number: exp.cheque_number || "", cheque_bank: exp.cheque_bank || "",
      our_bank: exp.our_bank || "", other_party_name: exp.other_party_name || "", other_party_bank: exp.other_party_bank || "",
    });
    setShowForm(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!editingId && !billPhoto) {
      setError("A photo of the bill/receipt is required.");
      return;
    }
    try {
      const payload = { ...form, plant: form.plant || null, amount: Number(form.amount) };
      setSaving(true);
      if (editingId) {
        await api.updateExpense(editingId, payload);
      } else {
        await api.createExpense(payload, billPhoto);
      }
      setForm(emptyForm);
      setBillPhoto(null);
      setEditingId(null);
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    await api.deleteExpense(id);
    load();
  }

  function openPreview(exp) {
    setPreviewFailed(false);
    setPreviewExpense(exp);
  }

  const filteredExpenses = expenses.filter((row) => {
    const rowDate = new Date(row.expense_date);
    const matchesFrom = !dateFrom || rowDate >= new Date(`${dateFrom}T00:00:00`);
    const matchesTo = !dateTo || rowDate <= new Date(`${dateTo}T23:59:59`);
    return matchesFrom && matchesTo;
  });

  return (
    <div>
      <SectionTitle
        eyebrow="Finance"
        title="Expenses"
        action={<Button onClick={() => (showForm ? setShowForm(false) : startCreate())}>{showForm ? "Cancel" : "+ New Expense"}</Button>}
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select label="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <Select label="Plant (optional — leave blank for general/admin)" value={form.plant} onChange={(e) => setForm({ ...form, plant: e.target.value })}>
              <option value="">General / Admin</option>
              {PLANTS.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
            <Input label="Amount (Rs.)" type="number" required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            <Input label="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <div className="col-span-1 sm:col-span-2">
              <div className="text-xs text-text-muted mb-2">Payment method (how this expense was paid)</div>
              <PaymentMethodFields value={form} onChange={(v) => setForm({ ...form, ...v })} direction="outgoing" />
            </div>
            {!editingId && (
              <div className="col-span-1 sm:col-span-2">
                <BillPhotoUpload file={billPhoto} onChange={setBillPhoto} />
              </div>
            )}
            <div className="col-span-1 sm:col-span-2 flex items-center gap-3">
              <Button type="submit" disabled={saving}>{saving ? "Uploading & Saving…" : editingId ? "Save Changes" : "Save Expense"}</Button>
              {error && <span className="text-red text-sm">{error}</span>}
            </div>
          </form>
        </Card>
      )}

      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <Input label="From date" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <Input label="To date" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        {(dateFrom || dateTo) && (
          <Button variant="ghost" onClick={() => { setDateFrom(""); setDateTo(""); }}>Clear filter</Button>
        )}
      </div>

      <Card>
        <Table
          emptyLabel={expenses.length === 0 ? "No expenses logged yet. Add salaries, utilities, rent, etc. to see real profitability, not just gross margin." : "No expenses match this date range."}
          columns={[
            { key: "date", label: "Date", render: (row) => new Date(row.expense_date).toLocaleDateString() },
            { key: "category", label: "Category", render: (row) => <Badge tone="amber">{row.category}</Badge> },
            { key: "plant", label: "Cost center", render: (row) => row.plant || "General/Admin" },
            { key: "description", label: "Description", render: (row) => row.description || "—" },
            { key: "amount", label: "Amount", mono: true, render: (row) => `Rs. ${formatPKR(row.amount)}` },
            { key: "payment", label: "Paid via", render: (row) => paymentMethodLabel(row) },
            {
              key: "bill", label: "Bill photo",
              render: (row) => row.bill_photo_url
                ? (
                  <div className="flex items-center gap-2">
                    <button type="button" className="text-xs text-amber-soft hover:underline" onClick={() => openPreview(row)}>Preview</button>
                    <a href={row.bill_photo_url} target="_blank" rel="noreferrer" className="text-xs text-text-muted hover:underline">Open</a>
                  </div>
                )
                : <span className="text-xs text-text-muted">—</span>,
            },
            {
              key: "actions", label: "",
              render: (row) => (
                <RowActions
                  onEdit={() => startEdit(row)}
                  onDelete={() => handleDelete(row.id)}
                  deleteConfirm="Delete this expense entry?"
                />
              ),
            },
          ]}
          rows={filteredExpenses}
        />
      </Card>

      {previewExpense && (
        <Modal title={`Receipt — ${previewExpense.description || previewExpense.category}`} onClose={() => setPreviewExpense(null)} wide>
          {previewFailed ? (
            <div className="text-sm text-text-muted py-8 text-center">
              Couldn't load a preview here — Drive sometimes blocks inline previews for certain file types.
              <br />
              <a href={previewExpense.bill_photo_url} target="_blank" rel="noreferrer" className="text-amber-soft hover:underline">
                Open it directly in Google Drive instead
              </a>
            </div>
          ) : (
            <img
              src={receiptPreviewUrl(previewExpense.bill_photo_drive_file_id)}
              alt="Receipt"
              className="w-full h-auto rounded-md border border-border"
              onError={() => setPreviewFailed(true)}
            />
          )}
        </Modal>
      )}
    </div>
  );
}
