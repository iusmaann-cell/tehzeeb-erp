import datetime
from typing import Optional, List
from pydantic import BaseModel
from .models import ItemType, WarehouseType, POStatus, LedgerDirection, Plant, ProductionOrderStatus, SalesOrderStatus, ExpenseCategory, EmploymentType, AttendanceStatus, PayrollRunStatus, PaymentMethod, PaymentStatus, AdjustmentDirection, AdjustmentStatus


# ---------- UOM ----------
class UOMBase(BaseModel):
    name: str
    symbol: str


class UOMCreate(UOMBase):
    pass


class UOMOut(UOMBase):
    id: int
    class Config:
        from_attributes = True


# ---------- Vendor ----------
class VendorBase(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    payment_terms: Optional[str] = None
    opening_balance: float = 0.0


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    payment_terms: Optional[str] = None
    opening_balance: Optional[float] = None


class VendorOut(VendorBase):
    id: int
    created_at: datetime.datetime
    class Config:
        from_attributes = True


class VendorBalanceOut(BaseModel):
    vendor_id: int
    vendor_name: str
    balance: float  # positive = we owe the vendor


# ---------- Customer (Phase 3 - toll) ----------
class CustomerBase(BaseModel):
    customer_number: Optional[str] = None
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    customer_number: Optional[str] = None
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class CustomerOut(CustomerBase):
    id: int
    created_at: datetime.datetime
    class Config:
        from_attributes = True


class CustomerBalanceOut(BaseModel):
    customer_id: int
    customer_name: str
    balance: float  # positive = customer owes us


# ---------- Warehouse ----------
class WarehouseBase(BaseModel):
    name: str
    warehouse_type: WarehouseType
    capacity: Optional[float] = None


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    warehouse_type: Optional[WarehouseType] = None
    capacity: Optional[float] = None


class WarehouseOut(WarehouseBase):
    id: int
    class Config:
        from_attributes = True


# ---------- Item ----------
class ItemBase(BaseModel):
    code: str
    name: str
    item_type: ItemType
    uom_id: int
    reorder_level: Optional[float] = None
    pack_size: Optional[str] = None
    units_per_case: Optional[float] = None
    density_kg_per_liter: Optional[float] = None


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    item_type: Optional[ItemType] = None
    uom_id: Optional[int] = None
    reorder_level: Optional[float] = None
    pack_size: Optional[str] = None
    units_per_case: Optional[float] = None
    density_kg_per_liter: Optional[float] = None


class ItemOut(ItemBase):
    id: int
    class Config:
        from_attributes = True


# ---------- Purchase Order ----------
class POLineBase(BaseModel):
    item_id: int
    quantity: float
    rate: float


class POLineCreate(POLineBase):
    pass


class POLineOut(POLineBase):
    id: int
    received_quantity: float
    class Config:
        from_attributes = True


class PurchaseOrderCreate(BaseModel):
    po_number: str
    vendor_id: int
    notes: Optional[str] = None
    lines: List[POLineCreate]


class PurchaseOrderUpdate(BaseModel):
    po_number: Optional[str] = None
    vendor_id: Optional[int] = None
    notes: Optional[str] = None
    lines: Optional[List[POLineCreate]] = None   # if provided, replaces all lines


class PurchaseOrderOut(BaseModel):
    id: int
    po_number: str
    vendor_id: int
    order_date: datetime.datetime
    status: POStatus
    payment_status: PaymentStatus
    notes: Optional[str] = None
    lines: List[POLineOut]
    class Config:
        from_attributes = True


class PaymentStatusUpdate(BaseModel):
    """Used to mark a PO / commission invoice / sales invoice paid or unpaid.
    Payment method fields are required when payment_status is 'paid' (validated
    in the endpoint, since requirements differ by method)."""
    payment_status: PaymentStatus
    payment_date: Optional[datetime.datetime] = None
    payment_method: Optional[PaymentMethod] = None
    cheque_number: Optional[str] = None
    cheque_bank: Optional[str] = None
    our_bank: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_bank: Optional[str] = None
    notes: Optional[str] = None


class VendorLedgerEntryOut(BaseModel):
    id: int
    direction: LedgerDirection
    amount: float
    ref_type: str
    ref_id: Optional[int] = None
    entry_date: datetime.datetime
    notes: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    cheque_number: Optional[str] = None
    cheque_bank: Optional[str] = None
    our_bank: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_bank: Optional[str] = None
    class Config:
        from_attributes = True


class CustomerLedgerEntryOut(BaseModel):
    id: int
    direction: LedgerDirection
    amount: float
    ref_type: str
    ref_id: Optional[int] = None
    entry_date: datetime.datetime
    notes: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    cheque_number: Optional[str] = None
    cheque_bank: Optional[str] = None
    our_bank: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_bank: Optional[str] = None
    class Config:
        from_attributes = True


class DistributorLedgerEntryOut(BaseModel):
    id: int
    direction: LedgerDirection
    amount: float
    ref_type: str
    ref_id: Optional[int] = None
    entry_date: datetime.datetime
    notes: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    cheque_number: Optional[str] = None
    cheque_bank: Optional[str] = None
    our_bank: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_bank: Optional[str] = None
    class Config:
        from_attributes = True


class VendorLedgerDetailOut(BaseModel):
    entries: List[VendorLedgerEntryOut]
    period_debit: float     # billed in this range
    period_credit: float    # paid in this range
    balance_as_of_end: float  # total owed as of the end of the range (or now)


class CustomerLedgerDetailOut(BaseModel):
    entries: List[CustomerLedgerEntryOut]
    period_debit: float
    period_credit: float
    balance_as_of_end: float


class DistributorLedgerDetailOut(BaseModel):
    entries: List[DistributorLedgerEntryOut]
    period_debit: float
    period_credit: float
    balance_as_of_end: float


# ---------- GRN ----------
class GRNLineCreate(BaseModel):
    po_line_id: int
    item_id: int
    warehouse_id: int
    batch_no: str
    quantity: float
    rate: float


class GRNCreate(BaseModel):
    grn_number: str
    purchase_order_id: int
    vehicle_no: Optional[str] = None
    notes: Optional[str] = None
    lines: List[GRNLineCreate]


class GRNLineOut(GRNLineCreate):
    id: int
    class Config:
        from_attributes = True


class GRNOut(BaseModel):
    id: int
    grn_number: str
    purchase_order_id: int
    received_date: datetime.datetime
    vehicle_no: Optional[str] = None
    notes: Optional[str] = None
    bill_photo_url: Optional[str] = None
    lines: List[GRNLineOut]
    class Config:
        from_attributes = True


# ---------- BOM / Recipe ----------
class BOMInputLineCreate(BaseModel):
    item_id: int
    quantity: float


class BOMOutputLineCreate(BaseModel):
    item_id: int
    quantity: float
    is_primary: bool = True


class BOMCreate(BaseModel):
    name: str
    plant: Plant
    reference_batch_size: float
    notes: Optional[str] = None
    input_lines: List[BOMInputLineCreate]
    output_lines: List[BOMOutputLineCreate]


class BOMUpdate(BaseModel):
    name: Optional[str] = None
    plant: Optional[Plant] = None
    reference_batch_size: Optional[float] = None
    notes: Optional[str] = None
    input_lines: Optional[List[BOMInputLineCreate]] = None    # if provided, replaces all lines
    output_lines: Optional[List[BOMOutputLineCreate]] = None  # if provided, replaces all lines


class BOMInputLineOut(BOMInputLineCreate):
    id: int
    class Config:
        from_attributes = True


class BOMOutputLineOut(BaseModel):
    id: int
    item_id: int
    quantity: float
    is_primary: bool
    class Config:
        from_attributes = True


class BOMOut(BaseModel):
    id: int
    name: str
    plant: Plant
    reference_batch_size: float
    notes: Optional[str] = None
    input_lines: List[BOMInputLineOut]
    output_lines: List[BOMOutputLineOut]
    class Config:
        from_attributes = True


# ---------- Production Orders ----------
class ProductionInputLineCreate(BaseModel):
    item_id: int
    warehouse_id: int
    quantity: float
    batch_no: Optional[str] = None   # omit for automatic FIFO consumption (recommended);
                                       # set to consume from one specific batch instead
    use_own_stock: bool = False   # only meaningful on a toll order — set True for lines that
    # should draw from YOUR OWN stock instead of the toll customer's (e.g. packaging materials
    # when packing a customer's oil into your bottles)


class ProductionOutputLineCreate(BaseModel):
    item_id: int
    warehouse_id: int
    batch_no: str       # new batch number for the output
    quantity: float
    is_primary: bool = True
    is_loss: bool = False   # pure process loss (evaporation, spillage) — no rate, no stock created
    rate: Optional[float] = None   # required for byproducts (is_primary=False and is_loss=False)


class ProductionOrderCreate(BaseModel):
    order_number: str
    plant: Plant
    bom_id: Optional[int] = None
    customer_id: Optional[int] = None   # set = this is a TOLL processing run for this customer
    notes: Optional[str] = None
    input_lines: List[ProductionInputLineCreate]
    output_lines: List[ProductionOutputLineCreate]


class ProductionInputLineOut(BaseModel):
    id: int
    item_id: int
    warehouse_id: int
    batch_no: str
    quantity: float
    rate: float
    is_toll_stock: Optional[bool] = False   # Optional: historical rows from before this column
    # existed land as NULL after the migration adds it, not False — must not be a hard requirement
    toll_customer_id: Optional[int] = None
    class Config:
        from_attributes = True


class ProductionOutputLineOut(BaseModel):
    id: int
    item_id: int
    warehouse_id: int
    batch_no: str
    quantity: float
    is_primary: bool
    is_loss: bool = False
    rate: Optional[float] = None
    class Config:
        from_attributes = True


class ProductionOrderOut(BaseModel):
    id: int
    order_number: str
    plant: Plant
    bom_id: Optional[int] = None
    customer_id: Optional[int] = None
    status: ProductionOrderStatus
    order_date: datetime.datetime
    notes: Optional[str] = None
    total_input_cost: Optional[float] = None
    total_input_quantity: Optional[float] = None
    total_primary_output_quantity: Optional[float] = None
    yield_percent: Optional[float] = None
    input_lines: List[ProductionInputLineOut]
    output_lines: List[ProductionOutputLineOut]
    class Config:
        from_attributes = True


# ---------- Toll / Job-Work Processing ----------
class TollIntakeLineCreate(BaseModel):
    item_id: int
    warehouse_id: int
    batch_no: str
    quantity: float
    declared_value: Optional[float] = None


class TollIntakeCreate(BaseModel):
    intake_number: str
    customer_id: int
    vehicle_no: Optional[str] = None
    notes: Optional[str] = None
    lines: List[TollIntakeLineCreate]


class TollIntakeLineOut(TollIntakeLineCreate):
    id: int
    class Config:
        from_attributes = True


class TollIntakeOut(BaseModel):
    id: int
    intake_number: str
    customer_id: int
    received_date: datetime.datetime
    vehicle_no: Optional[str] = None
    notes: Optional[str] = None
    lines: List[TollIntakeLineOut]
    class Config:
        from_attributes = True


class TollDeliveryLineCreate(BaseModel):
    item_id: int
    warehouse_id: int
    quantity: float
    batch_no: Optional[str] = None   # omit for automatic FIFO consumption of that customer's stock


class TollDeliveryCreate(BaseModel):
    delivery_number: str
    customer_id: int
    vehicle_no: Optional[str] = None
    notes: Optional[str] = None
    lines: List[TollDeliveryLineCreate]


class TollDeliveryLineOut(BaseModel):
    id: int
    item_id: int
    warehouse_id: int
    batch_no: str
    quantity: float
    class Config:
        from_attributes = True


class TollDeliveryOut(BaseModel):
    id: int
    delivery_number: str
    customer_id: int
    delivery_date: datetime.datetime
    vehicle_no: Optional[str] = None
    notes: Optional[str] = None
    lines: List[TollDeliveryLineOut]
    class Config:
        from_attributes = True


class CommissionInvoiceCreate(BaseModel):
    invoice_number: str
    customer_id: int
    production_order_id: Optional[int] = None
    quantity_processed: Optional[float] = None
    rate_per_unit: Optional[float] = None
    amount: Optional[float] = None   # if omitted, computed as quantity_processed * rate_per_unit
    notes: Optional[str] = None


class CommissionInvoiceOut(BaseModel):
    id: int
    invoice_number: str
    customer_id: int
    production_order_id: Optional[int] = None
    invoice_date: datetime.datetime
    quantity_processed: Optional[float] = None
    rate_per_unit: Optional[float] = None
    amount: float
    payment_status: PaymentStatus
    notes: Optional[str] = None
    class Config:
        from_attributes = True


# ---------- Sales & Distribution (Phase 5) ----------
class DistributorBase(BaseModel):
    distributor_number: Optional[str] = None
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    payment_terms: Optional[str] = None
    credit_limit: Optional[float] = None
    opening_balance: float = 0.0


class DistributorCreate(DistributorBase):
    pass


class DistributorUpdate(BaseModel):
    distributor_number: Optional[str] = None
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    payment_terms: Optional[str] = None
    credit_limit: Optional[float] = None
    opening_balance: Optional[float] = None


class DistributorOut(DistributorBase):
    id: int
    created_at: datetime.datetime
    class Config:
        from_attributes = True


class DistributorBalanceOut(BaseModel):
    distributor_id: int
    distributor_name: str
    balance: float   # positive = they owe us


class SOLineCreate(BaseModel):
    item_id: int
    quantity: float
    rate: float


class SOLineOut(SOLineCreate):
    id: int
    dispatched_quantity: float
    class Config:
        from_attributes = True


class SalesOrderCreate(BaseModel):
    so_number: str
    distributor_id: int
    notes: Optional[str] = None
    lines: List[SOLineCreate]


class SalesOrderUpdate(BaseModel):
    so_number: Optional[str] = None
    distributor_id: Optional[int] = None
    notes: Optional[str] = None
    lines: Optional[List[SOLineCreate]] = None


class SalesOrderOut(BaseModel):
    id: int
    so_number: str
    distributor_id: int
    order_date: datetime.datetime
    status: SalesOrderStatus
    notes: Optional[str] = None
    lines: List[SOLineOut]
    class Config:
        from_attributes = True


class DispatchLineCreate(BaseModel):
    sales_order_line_id: int
    item_id: int
    warehouse_id: int
    quantity: float
    batch_no: Optional[str] = None   # omit for automatic FIFO consumption


class SalesDispatchCreate(BaseModel):
    dispatch_number: str
    sales_order_id: int
    vehicle_no: Optional[str] = None
    notes: Optional[str] = None
    lines: List[DispatchLineCreate]


class DispatchLineOut(BaseModel):
    id: int
    sales_order_line_id: int
    item_id: int
    warehouse_id: int
    batch_no: str
    quantity: float
    cogs_rate: Optional[float] = None
    class Config:
        from_attributes = True


class SalesDispatchOut(BaseModel):
    id: int
    dispatch_number: str
    sales_order_id: int
    dispatch_date: datetime.datetime
    vehicle_no: Optional[str] = None
    notes: Optional[str] = None
    lines: List[DispatchLineOut]
    class Config:
        from_attributes = True


class SalesInvoiceCreate(BaseModel):
    invoice_number: str
    distributor_id: int
    sales_order_id: Optional[int] = None
    tax_rate: float = 0.0
    notes: Optional[str] = None
    lines: List[SOLineCreate]   # item_id, quantity, rate — invoice its own line items directly


class SalesInvoiceLineOut(BaseModel):
    id: int
    item_id: int
    quantity: float
    rate: float
    amount: float
    class Config:
        from_attributes = True


class SalesInvoiceOut(BaseModel):
    id: int
    invoice_number: str
    distributor_id: int
    sales_order_id: Optional[int] = None
    invoice_date: datetime.datetime
    subtotal: float
    tax_rate: float
    tax_amount: float
    total_amount: float
    payment_status: PaymentStatus
    notes: Optional[str] = None
    lines: List[SalesInvoiceLineOut]
    class Config:
        from_attributes = True


# ---------- Stock ----------
class StockBalanceOut(BaseModel):
    item_id: int
    item_name: str
    warehouse_id: int
    warehouse_name: str
    batch_no: Optional[str] = None
    quantity: float
    is_toll_stock: bool
    toll_customer_id: Optional[int] = None
    toll_customer_name: Optional[str] = None


# ---------- Finance (Phase 6) ----------
class ExpenseCreate(BaseModel):
    expense_date: Optional[datetime.datetime] = None
    category: ExpenseCategory
    plant: Optional[Plant] = None
    amount: float
    description: Optional[str] = None
    notes: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    cheque_number: Optional[str] = None
    cheque_bank: Optional[str] = None
    our_bank: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_bank: Optional[str] = None


class ExpenseUpdate(BaseModel):
    expense_date: Optional[datetime.datetime] = None
    category: Optional[ExpenseCategory] = None
    plant: Optional[Plant] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    cheque_number: Optional[str] = None
    cheque_bank: Optional[str] = None
    our_bank: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_bank: Optional[str] = None


class ExpenseOut(BaseModel):
    id: int
    expense_date: datetime.datetime
    category: ExpenseCategory
    plant: Optional[Plant] = None
    amount: float
    description: Optional[str] = None
    notes: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    cheque_number: Optional[str] = None
    cheque_bank: Optional[str] = None
    our_bank: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_bank: Optional[str] = None
    bill_photo_url: Optional[str] = None
    bill_photo_drive_file_id: Optional[str] = None
    class Config:
        from_attributes = True


class PnLOut(BaseModel):
    start_date: datetime.datetime
    end_date: datetime.datetime
    plant: Optional[str] = None
    sales_revenue: float
    commission_revenue: float
    total_revenue: float
    cogs: float
    gross_profit: float
    total_expenses: float
    net_profit: float


class AgingBucketOut(BaseModel):
    party_id: int
    party_name: str
    current: float       # 0-30 days
    days_31_60: float
    days_61_90: float
    over_90: float
    total_outstanding: float


class SalesTaxSummaryOut(BaseModel):
    start_date: datetime.datetime
    end_date: datetime.datetime
    taxable_sales: float
    output_tax_collected: float
    invoice_count: int


class FinancialSnapshotOut(BaseModel):
    as_of: datetime.datetime
    total_accounts_payable: float
    total_accounts_receivable_distributors: float
    total_accounts_receivable_toll: float
    total_inventory_value: float
    total_sales_revenue_to_date: float
    total_commission_revenue_to_date: float
    total_cogs_to_date: float
    total_expenses_to_date: float


# ---------- HR & Payroll (Phase 7) ----------
class EmployeeBase(BaseModel):
    name: str
    father_name: Optional[str] = None
    cnic: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    designation: Optional[str] = None
    plant: Optional[Plant] = None
    employment_type: EmploymentType
    basic_salary: Optional[float] = None
    daily_wage_rate: Optional[float] = None
    overtime_rate_per_hour: Optional[float] = None
    bank_account: Optional[str] = None
    joining_date: Optional[datetime.datetime] = None
    emergency_contact: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    father_name: Optional[str] = None
    cnic: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    designation: Optional[str] = None
    plant: Optional[Plant] = None
    employment_type: Optional[EmploymentType] = None
    basic_salary: Optional[float] = None
    daily_wage_rate: Optional[float] = None
    overtime_rate_per_hour: Optional[float] = None
    bank_account: Optional[str] = None
    joining_date: Optional[datetime.datetime] = None
    emergency_contact: Optional[str] = None


class EmployeeOut(EmployeeBase):
    id: int
    created_at: datetime.datetime
    class Config:
        from_attributes = True


class AttendanceMarkLine(BaseModel):
    employee_id: int
    status: AttendanceStatus
    overtime_hours: float = 0.0
    notes: Optional[str] = None


class AttendanceMarkRequest(BaseModel):
    attendance_date: datetime.datetime
    lines: List[AttendanceMarkLine]


class AttendanceRecordOut(BaseModel):
    id: int
    employee_id: int
    attendance_date: datetime.datetime
    status: AttendanceStatus
    overtime_hours: float
    notes: Optional[str] = None
    class Config:
        from_attributes = True


class PayrollRunCreate(BaseModel):
    run_number: str
    period_start: datetime.datetime
    period_end: datetime.datetime
    notes: Optional[str] = None


class PayslipLineUpdate(BaseModel):
    allowances: Optional[float] = None
    deductions: Optional[float] = None


class PayslipLineOut(BaseModel):
    id: int
    employee_id: int
    days_present: float
    days_absent: float
    days_leave: float
    days_half: float
    overtime_hours: float
    basic_pay: float
    overtime_pay: float
    allowances: float
    deductions: float
    net_pay: float
    class Config:
        from_attributes = True


class PayrollRunOut(BaseModel):
    id: int
    run_number: str
    period_start: datetime.datetime
    period_end: datetime.datetime
    run_date: datetime.datetime
    status: PayrollRunStatus
    notes: Optional[str] = None
    lines: List[PayslipLineOut]
    class Config:
        from_attributes = True


# ---------- Invoice Print Settings ----------
class InvoiceSettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    ntn_number: Optional[str] = None
    logo_base64: Optional[str] = None
    logo_width_mm: Optional[float] = None
    logo_height_mm: Optional[float] = None
    footer_text: Optional[str] = None
    show_logo: Optional[bool] = None
    accent_color: Optional[str] = None


class InvoiceSettingsOut(BaseModel):
    company_name: str
    company_address: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    ntn_number: Optional[str] = None
    logo_base64: Optional[str] = None
    logo_width_mm: float
    logo_height_mm: float
    footer_text: Optional[str] = None
    show_logo: bool
    accent_color: str
    class Config:
        from_attributes = True


# ---------- Stock Adjustments (Improvement Phase 6) ----------
class StockAdjustmentCreate(BaseModel):
    adjustment_number: str
    item_id: int
    warehouse_id: int
    direction: AdjustmentDirection
    quantity: float
    rate: Optional[float] = None   # required for "increase" (no purchase cost to derive it from)
    batch_no: Optional[str] = None  # required for "increase" (new batch label); optional override for "decrease"
    reason_comment: str


class StockAdjustmentOut(BaseModel):
    id: int
    adjustment_number: str
    item_id: int
    warehouse_id: int
    direction: AdjustmentDirection
    quantity: float
    rate: float
    batch_no: Optional[str] = None
    reason_comment: str
    status: AdjustmentStatus
    adjustment_date: datetime.datetime
    approved_at: Optional[datetime.datetime] = None
    approved_by: Optional[str] = None
    class Config:
        from_attributes = True


class StockAdjustmentApprove(BaseModel):
    approved_by: str
