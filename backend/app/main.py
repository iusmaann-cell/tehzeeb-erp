from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import models
from .database import engine, run_lightweight_migrations
from .routers import vendors, items, warehouses, purchase_orders, grn, stock, production, customers, toll, distributors, sales, expenses, finance, employees, attendance, payroll, bi, settings, stock_adjustments, admin

models.Base.metadata.create_all(bind=engine)
run_lightweight_migrations()

app = FastAPI(
    title="Tehzeeb ERP",
    description="ERP for Tehzeeb oil refining, ghee, soap and toll processing business",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your frontend domain before going live
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vendors.router)
app.include_router(items.router)
app.include_router(warehouses.router)
app.include_router(purchase_orders.router)
app.include_router(grn.router)
app.include_router(stock.router)
app.include_router(production.router)
app.include_router(customers.router)
app.include_router(toll.router)
app.include_router(distributors.router)
app.include_router(sales.router)
app.include_router(expenses.router)
app.include_router(finance.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(payroll.router)
app.include_router(bi.router)
app.include_router(settings.router)
app.include_router(stock_adjustments.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"message": "Tehzeeb ERP API — Phase 1: Procurement + Inventory, Phase 2: Production, Phase 3: Toll Processing, Phase 4: Packaging, Phase 5: Sales & Distribution, Phase 6: Finance, Phase 7: HR & Payroll, Phase 8: BI Dashboards"}
