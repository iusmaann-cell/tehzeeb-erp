import { useEffect, useState } from "react";

const NAV_SECTIONS = [
  {
    label: "Analytics",
    items: [
      { key: "bi-dashboard", label: "BI Dashboards", icon: "📈" },
    ],
  },
  {
    label: "Procurement",
    items: [
      { key: "vendors", label: "Vendors", icon: "🤝" },
      { key: "items", label: "Items", icon: "◈" },
      { key: "warehouses", label: "Warehouses", icon: "▦" },
      { key: "purchase-orders", label: "Purchase Orders", icon: "📋" },
      { key: "grn", label: "Goods Received", icon: "🚚" },
      { key: "stock", label: "Stock", icon: "🛢" },
      { key: "stock-adjustments", label: "Stock Adjustments", icon: "⚖" },
    ],
  },
  {
    label: "Production",
    items: [
      { key: "boms", label: "BOMs / Recipes", icon: "🧪" },
      { key: "production-orders", label: "Production Orders", icon: "⚙" },
    ],
  },
  {
    label: "Toll / Job-Work",
    items: [
      { key: "customers", label: "Toll Customers", icon: "🧑‍🤝‍🧑" },
      { key: "toll-intake", label: "Toll Intake", icon: "📥" },
      { key: "toll-delivery", label: "Toll Delivery", icon: "📤" },
      { key: "commission-invoices", label: "Commission Invoices", icon: "🧾" },
    ],
  },
  {
    label: "Sales",
    items: [
      { key: "distributors", label: "Distributors", icon: "🏪" },
      { key: "sales-orders", label: "Sales Orders", icon: "🛒" },
      { key: "sales-dispatch", label: "Dispatch", icon: "🚛" },
      { key: "sales-invoices", label: "Sales Invoices", icon: "💵" },
    ],
  },
  {
    label: "Finance",
    items: [
      { key: "expenses", label: "Expenses", icon: "📉" },
      { key: "reports", label: "Reports", icon: "📊" },
    ],
  },
  {
    label: "HR & Payroll",
    items: [
      { key: "employees", label: "Employees", icon: "👷" },
      { key: "attendance", label: "Attendance", icon: "🗓" },
      { key: "payroll", label: "Payroll", icon: "💰" },
    ],
  },
  {
    label: "Settings",
    items: [
      { key: "invoice-settings", label: "Invoice Printing", icon: "🖨" },
    ],
  },
];

function sectionForKey(key) {
  return NAV_SECTIONS.find((s) => s.items.some((i) => i.key === key))?.label;
}

export default function Sidebar({ active, onNavigate, mobileOpen, onCloseMobile }) {
  // Open the section containing whichever page is active, on top of anything
  // the person has already expanded themselves.
  const [openSections, setOpenSections] = useState(() => {
    const initial = new Set();
    const activeSection = sectionForKey(active);
    if (activeSection) initial.add(activeSection);
    return initial;
  });

  useEffect(() => {
    const activeSection = sectionForKey(active);
    if (activeSection && !openSections.has(activeSection)) {
      setOpenSections((prev) => new Set(prev).add(activeSection));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  function toggleSection(label) {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  }

  function handleNavigate(key) {
    onNavigate(key);
    onCloseMobile?.();   // tapping a link closes the drawer on mobile; no-op on desktop
  }

  return (
    <>
      {/* Backdrop — mobile only, shown behind the drawer while it's open */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={onCloseMobile} />
      )}

      <aside
        className={`w-64 sm:w-60 shrink-0 bg-surface border-r border-border flex flex-col h-screen
          fixed top-0 left-0 z-50 transition-transform duration-200 ease-out
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0 md:static md:sticky md:z-auto`}
      >
        <div className="px-5 py-6 border-b border-border shrink-0 flex items-center justify-between">
          <div>
            <div className="text-amber stencil text-xs tracking-widest uppercase mb-1">Tehzeeb ERP</div>
            <div className="font-display font-semibold text-lg leading-tight">Bahawalpur Mill</div>
          </div>
          <button
            type="button"
            onClick={onCloseMobile}
            className="md:hidden text-text-muted hover:text-text text-xl leading-none px-2"
            aria-label="Close menu"
          >
            ✕
          </button>
        </div>

        <nav className="flex-1 min-h-0 overflow-y-auto py-4 px-2">
          <button
            onClick={() => handleNavigate("dashboard")}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm mb-3 transition-colors
              ${active === "dashboard"
                ? "bg-amber/10 text-amber-soft border border-amber/30"
                : "text-text-muted hover:text-text hover:bg-surface-2 border border-transparent"}`}
          >
            <span>⛁</span>
            Dashboard
          </button>

          {NAV_SECTIONS.map((section) => {
            const isOpen = openSections.has(section.label);
            const sectionHasActive = section.items.some((i) => i.key === active);
            return (
              <div key={section.label} className="mb-1">
                <button
                  onClick={() => toggleSection(section.label)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-[11px] uppercase tracking-widest transition-colors
                    ${sectionHasActive ? "text-amber-soft" : "text-text-muted/80 hover:text-text-muted"}`}
                >
                  {section.label}
                  <span className={`text-[9px] transition-transform ${isOpen ? "rotate-90" : ""}`}>▶</span>
                </button>
                {isOpen && (
                  <div className="mb-2">
                    {section.items.map((item) => (
                      <button
                        key={item.key}
                        onClick={() => handleNavigate(item.key)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm mb-1 transition-colors
                          ${active === item.key
                            ? "bg-amber/10 text-amber-soft border border-amber/30"
                            : "text-text-muted hover:text-text hover:bg-surface-2 border border-transparent"}`}
                      >
                        <span>{item.icon}</span>
                        {item.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        <div className="px-5 py-4 border-t border-border text-xs text-text-muted shrink-0">
          Improvement Phase 7
        </div>
      </aside>
    </>
  );
}
