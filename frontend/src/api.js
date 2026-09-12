const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export { BASE_URL };

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Vendors
  getVendors: () => request("/vendors/"),
  createVendor: (data) => request("/vendors/", { method: "POST", body: JSON.stringify(data) }),
  updateVendor: (id, data) => request(`/vendors/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteVendor: (id) => request(`/vendors/${id}`, { method: "DELETE" }),
  getVendorBalance: (id) => request(`/vendors/${id}/balance`),
  recordPayment: (id, amount, notes) =>
    request(`/vendors/${id}/payment?amount=${amount}&notes=${encodeURIComponent(notes || "")}`, { method: "POST" }),

  // UOM
  getUOMs: () => request("/uom/"),
  createUOM: (data) => request("/uom/", { method: "POST", body: JSON.stringify(data) }),

  // Items
  getItems: (itemType) => request(`/items/${itemType ? `?item_type=${itemType}` : ""}`),
  createItem: (data) => request("/items/", { method: "POST", body: JSON.stringify(data) }),
  bulkUploadItems: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/items/bulk-upload`, { method: "POST", body: formData });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = body.detail;
      const err = new Error(typeof detail === "string" ? detail : detail?.message || "Upload failed");
      err.rowErrors = typeof detail === "object" ? detail?.errors : null;
      throw err;
    }
    return body;
  },
  updateItem: (id, data) => request(`/items/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteItem: (id) => request(`/items/${id}`, { method: "DELETE" }),

  // Warehouses
  getWarehouses: () => request("/warehouses/"),
  createWarehouse: (data) => request("/warehouses/", { method: "POST", body: JSON.stringify(data) }),
  updateWarehouse: (id, data) => request(`/warehouses/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteWarehouse: (id) => request(`/warehouses/${id}`, { method: "DELETE" }),

  // Purchase Orders
  getPurchaseOrders: () => request("/purchase-orders/"),
  createPurchaseOrder: (data) => request("/purchase-orders/", { method: "POST", body: JSON.stringify(data) }),
  updatePurchaseOrder: (id, data) => request(`/purchase-orders/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePurchaseOrder: (id) => request(`/purchase-orders/${id}`, { method: "DELETE" }),
  cancelPurchaseOrder: (id) => request(`/purchase-orders/${id}/cancel`, { method: "PATCH" }),
  getPurchaseOrder: (id) => request(`/purchase-orders/${id}`),

  // GRN
  getGRNs: () => request("/grn/"),
  createGRN: async (data, billPhotoFile) => {
    const formData = new FormData();
    formData.append("data", JSON.stringify(data));
    formData.append("bill_photo", billPhotoFile);
    const res = await fetch(`${BASE_URL}/grn/`, { method: "POST", body: formData });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Failed to save GRN");
    return body;
  },

  // Stock
  getStockBalance: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/stock/balance${qs ? `?${qs}` : ""}`);
  },
  getWarehouseStockSummary: () => request("/stock/warehouse-summary"),
  searchStock: (q) => request(`/stock/search?q=${encodeURIComponent(q)}`),

  // BOMs
  getBOMs: (plant) => request(`/boms/${plant ? `?plant=${plant}` : ""}`),
  createBOM: (data) => request("/boms/", { method: "POST", body: JSON.stringify(data) }),
  updateBOM: (id, data) => request(`/boms/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteBOM: (id) => request(`/boms/${id}`, { method: "DELETE" }),
  getBOM: (id) => request(`/boms/${id}`),

  // Production Orders
  getProductionOrders: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/production-orders/${qs ? `?${qs}` : ""}`);
  },
  createProductionOrder: (data) => request("/production-orders/", { method: "POST", body: JSON.stringify(data) }),
  getProductionOrder: (id) => request(`/production-orders/${id}`),

  // Customers (toll)
  getCustomers: () => request("/customers/"),
  createCustomer: (data) => request("/customers/", { method: "POST", body: JSON.stringify(data) }),
  updateCustomer: (id, data) => request(`/customers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteCustomer: (id) => request(`/customers/${id}`, { method: "DELETE" }),
  getCustomerBalance: (id) => request(`/customers/${id}/balance`),
  recordCustomerPayment: (id, amount, notes) =>
    request(`/customers/${id}/payment?amount=${amount}&notes=${encodeURIComponent(notes || "")}`, { method: "POST" }),

  // Toll Intake
  getTollIntakes: (customerId) => request(`/toll-intakes/${customerId ? `?customer_id=${customerId}` : ""}`),
  createTollIntake: (data) => request("/toll-intakes/", { method: "POST", body: JSON.stringify(data) }),

  // Toll Delivery
  getTollDeliveries: (customerId) => request(`/toll-deliveries/${customerId ? `?customer_id=${customerId}` : ""}`),
  createTollDelivery: (data) => request("/toll-deliveries/", { method: "POST", body: JSON.stringify(data) }),

  // Commission Invoices
  getCommissionInvoices: (customerId) => request(`/commission-invoices/${customerId ? `?customer_id=${customerId}` : ""}`),
  createCommissionInvoice: (data) => request("/commission-invoices/", { method: "POST", body: JSON.stringify(data) }),

  // Distributors
  getDistributors: () => request("/distributors/"),
  createDistributor: (data) => request("/distributors/", { method: "POST", body: JSON.stringify(data) }),
  updateDistributor: (id, data) => request(`/distributors/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteDistributor: (id) => request(`/distributors/${id}`, { method: "DELETE" }),
  getDistributorBalance: (id) => request(`/distributors/${id}/balance`),
  recordDistributorPayment: (id, amount, notes) =>
    request(`/distributors/${id}/payment?amount=${amount}&notes=${encodeURIComponent(notes || "")}`, { method: "POST" }),

  // Sales Orders
  getSalesOrders: () => request("/sales-orders/"),
  createSalesOrder: (data) => request("/sales-orders/", { method: "POST", body: JSON.stringify(data) }),
  updateSalesOrder: (id, data) => request(`/sales-orders/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteSalesOrder: (id) => request(`/sales-orders/${id}`, { method: "DELETE" }),
  cancelSalesOrder: (id) => request(`/sales-orders/${id}/cancel`, { method: "PATCH" }),
  getSalesOrder: (id) => request(`/sales-orders/${id}`),

  // Sales Dispatch
  getSalesDispatches: () => request("/sales-dispatches/"),
  createSalesDispatch: (data) => request("/sales-dispatches/", { method: "POST", body: JSON.stringify(data) }),

  // Sales Invoices
  getSalesInvoices: (distributorId) => request(`/sales-invoices/${distributorId ? `?distributor_id=${distributorId}` : ""}`),
  createSalesInvoice: (data) => request("/sales-invoices/", { method: "POST", body: JSON.stringify(data) }),

  // Expenses
  getExpenses: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/expenses/${qs ? `?${qs}` : ""}`);
  },
  createExpense: async (data, billPhotoFile) => {
    const formData = new FormData();
    formData.append("data", JSON.stringify(data));
    formData.append("bill_photo", billPhotoFile);
    const res = await fetch(`${BASE_URL}/expenses/`, { method: "POST", body: formData });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Failed to save expense");
    return body;
  },
  updateExpense: (id, data) => request(`/expenses/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteExpense: (id) => request(`/expenses/${id}`, { method: "DELETE" }),

  // Finance Reports
  getPnL: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/reports/pnl${qs ? `?${qs}` : ""}`);
  },
  getPnLByItem: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/reports/pnl-by-item${qs ? `?${qs}` : ""}`);
  },
  getExpensesByPlant: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/reports/expenses-by-plant${qs ? `?${qs}` : ""}`);
  },
  getAPAging: () => request("/reports/ap-aging"),
  getARAgingDistributors: () => request("/reports/ar-aging-distributors"),
  getARAgingTollCustomers: () => request("/reports/ar-aging-toll-customers"),
  getSalesTaxSummary: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/reports/sales-tax-summary${qs ? `?${qs}` : ""}`);
  },
  getFinancialSnapshot: () => request("/reports/financial-snapshot"),

  // Employees
  getEmployees: (plant) => request(`/employees/${plant ? `?plant=${plant}` : ""}`),
  createEmployee: (data) => request("/employees/", { method: "POST", body: JSON.stringify(data) }),
  updateEmployee: (id, data) => request(`/employees/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteEmployee: (id) => request(`/employees/${id}`, { method: "DELETE" }),

  // Attendance
  markAttendance: (data) => request("/attendance/mark", { method: "POST", body: JSON.stringify(data) }),
  getAttendance: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/attendance/${qs ? `?${qs}` : ""}`);
  },

  // Payroll
  getPayrollRuns: () => request("/payroll/runs/"),
  createPayrollRun: (data) => request("/payroll/runs/", { method: "POST", body: JSON.stringify(data) }),
  getPayrollRun: (id) => request(`/payroll/runs/${id}`),
  updatePayslipLine: (runId, lineId, data) => request(`/payroll/runs/${runId}/lines/${lineId}`, { method: "PUT", body: JSON.stringify(data) }),
  finalizePayrollRun: (id) => request(`/payroll/runs/${id}/finalize`, { method: "PATCH" }),

  // BI Dashboards
  getRevenueTrend: (months = 6) => request(`/bi/revenue-trend?months=${months}`),
  getProductionYieldTrend: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/bi/production-yield-trend${qs ? `?${qs}` : ""}`);
  },
  getInventoryValueByType: () => request("/bi/inventory-value-by-type"),
  getSalesByDistributor: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/bi/sales-by-distributor${qs ? `?${qs}` : ""}`);
  },
  getExpenseBreakdown: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/bi/expense-breakdown${qs ? `?${qs}` : ""}`);
  },

  // Payment status (POs, commission invoices, sales invoices)
  updatePOPaymentStatus: (id, data) => request(`/purchase-orders/${id}/payment-status`, { method: "PATCH", body: JSON.stringify(data) }),
  updateCommissionInvoicePaymentStatus: (id, data) => request(`/commission-invoices/${id}/payment-status`, { method: "PATCH", body: JSON.stringify(data) }),
  updateSalesInvoicePaymentStatus: (id, data) => request(`/sales-invoices/${id}/payment-status`, { method: "PATCH", body: JSON.stringify(data) }),

  // Ledgers (with payment detail)
  getVendorLedger: (id, params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/vendors/${id}/ledger${qs ? `?${qs}` : ""}`);
  },
  getCustomerLedger: (id, params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/customers/${id}/ledger${qs ? `?${qs}` : ""}`);
  },
  getDistributorLedger: (id, params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/distributors/${id}/ledger${qs ? `?${qs}` : ""}`);
  },

  // Invoice print settings
  getInvoiceSettings: () => request("/settings/invoice"),
  updateInvoiceSettings: (data) => request("/settings/invoice", { method: "PUT", body: JSON.stringify(data) }),
  uploadInvoiceLogo: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/settings/invoice/logo`, { method: "POST", body: formData });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || "Logo upload failed");
    return body;
  },

  // Stock Adjustments
  getStockAdjustments: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/stock-adjustments/${qs ? `?${qs}` : ""}`);
  },
  createStockAdjustment: (data) => request("/stock-adjustments/", { method: "POST", body: JSON.stringify(data) }),
  approveStockAdjustment: (id, approvedBy) => request(`/stock-adjustments/${id}/approve`, { method: "PATCH", body: JSON.stringify({ approved_by: approvedBy }) }),
};
