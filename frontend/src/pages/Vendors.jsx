import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, SectionTitle, Button, Input, Select, Table, RowActions, formatPKR } from "../components/ui";
import LedgerDetail from "../components/LedgerDetail";

const emptyForm = { name: "", contact_person: "", phone: "", payment_terms: "", opening_balance: 0 };
const BALANCE_FILTERS = [
  { value: "all", label: "All vendors" },
  { value: "owing", label: "Balance owed" },
  { value: "settled", label: "Settled" },
];

export default function Vendors() {
  const [vendors, setVendors] = useState([]);
  const [balances, setBalances] = useState({});
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [balanceFilter, setBalanceFilter] = useState("all");
  const [selectedVendor, setSelectedVendor] = useState(null);

  async function load() {
    setLoading(true);
    const data = await api.getVendors();
    setVendors(data);
    const balMap = {};
    await Promise.all(
      data.map(async (v) => {
        const b = await api.getVendorBalance(v.id);
        balMap[v.id] = b.balance;
      })
    );
    setBalances(balMap);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function startCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
  }

  function startEdit(vendor) {
    setEditingId(vendor.id);
    setForm({
      name: vendor.name,
      contact_person: vendor.contact_person || "",
      phone: vendor.phone || "",
      payment_terms: vendor.payment_terms || "",
      opening_balance: vendor.opening_balance,
    });
    setShowForm(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = { ...form, opening_balance: Number(form.opening_balance) || 0 };
      if (editingId) {
        await api.updateVendor(editingId, payload);
      } else {
        await api.createVendor(payload);
      }
      setForm(emptyForm);
      setEditingId(null);
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    await api.deleteVendor(id);
    load();
  }

  const filteredVendors = vendors.filter((v) => {
    const q = search.trim().toLowerCase();
    const matchesSearch = !q || v.name.toLowerCase().includes(q) || (v.phone || "").toLowerCase().includes(q);
    const bal = balances[v.id] ?? 0;
    const matchesBalance = balanceFilter === "all" || (balanceFilter === "owing" ? bal > 0 : bal <= 0);
    return matchesSearch && matchesBalance;
  });

  return (
    <div>
      {selectedVendor ? (
        <LedgerDetail
          partyName={selectedVendor.name}
          fetchLedger={(params) => api.getVendorLedger(selectedVendor.id, params)}
          debitLabel="Billed"
          creditLabel="Paid"
          balanceLabel="Owed to vendor"
          onBack={() => setSelectedVendor(null)}
        />
      ) : (
      <>
      <SectionTitle
        eyebrow="Procurement"
        title="Vendors"
        action={<Button onClick={() => (showForm ? setShowForm(false) : startCreate())}>{showForm ? "Cancel" : "+ New Vendor"}</Button>}
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="Vendor name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Input label="Contact person" value={form.contact_person} onChange={(e) => setForm({ ...form, contact_person: e.target.value })} />
            <Input label="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            <Input label="Payment terms" placeholder="e.g. Net 15" value={form.payment_terms} onChange={(e) => setForm({ ...form, payment_terms: e.target.value })} />
            <Input label="Opening balance (Rs.)" type="number" value={form.opening_balance} onChange={(e) => setForm({ ...form, opening_balance: e.target.value })} />
            <div className="col-span-2 flex items-center gap-3">
              <Button type="submit">{editingId ? "Save Changes" : "Save Vendor"}</Button>
              {error && <span className="text-red text-sm">{error}</span>}
            </div>
          </form>
        </Card>
      )}

      <div className="flex gap-3 mb-4">
        <Input placeholder="Search by name or phone…" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
        <Select value={balanceFilter} onChange={(e) => setBalanceFilter(e.target.value)} className="max-w-xs">
          {BALANCE_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
        </Select>
      </div>

      <Card>
        {loading ? (
          <div className="text-text-muted text-sm">Loading vendors&hellip;</div>
        ) : (
          <Table
            emptyLabel={vendors.length === 0 ? "No vendors yet. Add your first crude oil supplier above." : "No vendors match your search/filter."}
            columns={[
              {
                key: "name", label: "Vendor",
                render: (row) => (
                  <button type="button" className="text-amber-soft hover:underline text-left" onClick={() => setSelectedVendor(row)}>
                    {row.name}
                  </button>
                ),
              },
              { key: "contact_person", label: "Contact" },
              { key: "phone", label: "Phone" },
              { key: "payment_terms", label: "Terms" },
              {
                key: "balance",
                label: "Balance owed",
                mono: true,
                render: (row) => (
                  <span className={balances[row.id] > 0 ? "text-amber-soft" : "text-text-muted"}>
                    Rs. {formatPKR(balances[row.id] ?? 0)}
                  </span>
                ),
              },
              {
                key: "actions",
                label: "",
                render: (row) => (
                  <RowActions
                    onEdit={() => startEdit(row)}
                    onDelete={() => handleDelete(row.id)}
                    deleteConfirm={`Remove ${row.name} from active vendors? Past purchase orders and ledger history are kept.`}
                  />
                ),
              },
            ]}
            rows={filteredVendors}
          />
        )}
      </Card>
      </>
      )}
    </div>
  );
}
