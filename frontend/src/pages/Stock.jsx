import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, SectionTitle, Table, Badge, Button, Input, formatPKR } from "../components/ui";

function WarehouseCard({ wh, onClick }) {
  return (
    <button
      onClick={onClick}
      className="text-left bg-surface border border-border rounded-lg p-5 hover:border-amber/50 transition-colors"
    >
      <div className="text-xs text-amber stencil uppercase tracking-widest mb-1">{wh.warehouse_type.replace(/_/g, " ")}</div>
      <div className="font-display text-lg font-semibold mb-3">{wh.warehouse_name}</div>
      <div className="flex justify-between text-sm text-text-muted">
        <span>{wh.distinct_item_count} item{wh.distinct_item_count === 1 ? "" : "s"}</span>
        <span>{wh.batch_count} batch{wh.batch_count === 1 ? "" : "es"}</span>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="stencil text-sm text-amber-soft">Rs. {formatPKR(wh.owned_stock_value)}</span>
        {wh.has_toll_stock && <Badge tone="red">has toll stock</Badge>}
      </div>
    </button>
  );
}

function StockTable({ rows, emptyLabel }) {
  return (
    <Table
      emptyLabel={emptyLabel}
      columns={[
        { key: "item_name", label: "Item" },
        { key: "warehouse_name", label: "Warehouse" },
        { key: "batch_no", label: "Batch", mono: true, render: (row) => row.batch_no || "—" },
        { key: "quantity", label: "Quantity", mono: true },
        {
          key: "owner",
          label: "Ownership",
          render: (row) => row.is_toll_stock
            ? <Badge tone="red">{row.toll_customer_name || "Toll customer"}</Badge>
            : <Badge tone="green">Owned</Badge>,
        },
      ]}
      rows={rows}
    />
  );
}

export default function Stock() {
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedWarehouse, setSelectedWarehouse] = useState(null);
  const [warehouseStock, setWarehouseStock] = useState([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);

  async function loadWarehouses() {
    setLoading(true);
    setWarehouses(await api.getWarehouseStockSummary());
    setLoading(false);
  }
  useEffect(() => { loadWarehouses(); }, []);

  async function openWarehouse(wh) {
    setSelectedWarehouse(wh);
    setLoadingDetail(true);
    setWarehouseStock(await api.getStockBalance({ warehouse_id: wh.warehouse_id }));
    setLoadingDetail(false);
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    setSearching(true);
    try {
      setSearchResults(await api.searchStock(searchQuery.trim()));
    } finally {
      setSearching(false);
    }
  }

  function clearSearch() {
    setSearchQuery("");
    setSearchResults(null);
  }

  return (
    <div>
      <SectionTitle eyebrow="Inventory" title="Stock" />

      <Card className="mb-6">
        <form onSubmit={handleSearch} className="flex items-end gap-3">
          <Input
            label="Search by GRN number, toll intake number, toll customer name, or batch number"
            placeholder="e.g. GRN-2026-0004, or a customer's name"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-md"
          />
          <Button type="submit" disabled={searching}>{searching ? "Searching…" : "Search"}</Button>
          {searchResults !== null && <Button type="button" variant="ghost" onClick={clearSearch}>Clear</Button>}
        </form>
      </Card>

      {searchResults !== null ? (
        <Card>
          <div className="text-sm text-text-muted mb-3">
            {searchResults.length} result{searchResults.length === 1 ? "" : "s"} for &ldquo;{searchQuery}&rdquo;
          </div>
          <StockTable rows={searchResults} emptyLabel="No stock matches that search." />
        </Card>
      ) : selectedWarehouse ? (
        <div>
          <button
            type="button"
            className="text-sm text-amber-soft hover:underline mb-4"
            onClick={() => setSelectedWarehouse(null)}
          >
            &larr; All warehouses
          </button>
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-xs text-amber stencil uppercase tracking-widest">{selectedWarehouse.warehouse_type.replace(/_/g, " ")}</div>
                <div className="font-display text-lg font-semibold">{selectedWarehouse.warehouse_name}</div>
              </div>
            </div>
            {loadingDetail ? (
              <div className="text-text-muted text-sm">Loading&hellip;</div>
            ) : (
              <StockTable rows={warehouseStock} emptyLabel="No stock in this warehouse yet." />
            )}
          </Card>
        </div>
      ) : loading ? (
        <div className="text-text-muted text-sm">Loading warehouses&hellip;</div>
      ) : warehouses.length === 0 ? (
        <Card>
          <div className="text-text-muted text-sm text-center py-8">
            No warehouses yet. Add one under Warehouses to start tracking stock.
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {warehouses.map((wh) => (
            <WarehouseCard key={wh.warehouse_id} wh={wh} onClick={() => openWarehouse(wh)} />
          ))}
        </div>
      )}
    </div>
  );
}
