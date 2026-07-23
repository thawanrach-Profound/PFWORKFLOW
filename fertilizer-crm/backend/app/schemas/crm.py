from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict
from app.models.crm import CreditTerm, OrderStatus, ProductionStatus, PaymentStatus, RmEntryTypeEnum, PoStatusEnum, RmSale, Promotion, PromotionGift, OrderPromotion, ShopMaster


# ── Customer ──────────────────────────────────────────────────
class CustomerCreate(BaseModel):
    customer_code: str
    company_name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    credit_term: CreditTerm = CreditTerm.D30
    credit_limit: Decimal = Decimal("0")
    notes: Optional[str] = None

class CustomerUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    credit_term: Optional[CreditTerm] = None
    credit_limit: Optional[Decimal] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    customer_id: int
    customer_code: str
    company_name: str
    contact_name: Optional[str]
    phone: Optional[str]
    credit_term: CreditTerm
    credit_limit: Decimal
    outstanding_balance: Decimal
    is_active: bool


# ── Formula ───────────────────────────────────────────────────
class BOMItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bom_id: int
    material_name: str
    qty_per_100kg: Decimal
    unit: str
    cost_per_unit: Decimal

class BOMItemCreate(BaseModel):
    material_name: str
    qty_per_100kg: Decimal
    unit: str = "kg"
    cost_per_unit: Decimal = Decimal("0")

class FormulaCreate(BaseModel):
    formula_code: str
    product_code: Optional[str] = None
    formula_name: str
    description: Optional[str] = None
    base_price_per_kg: Decimal = Decimal("0")
    bom_items: list[BOMItemCreate] = []

class FormulaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    formula_id: int
    formula_code: str
    product_code: Optional[str] = None
    formula_name: str
    base_price_per_kg: Decimal
    is_active: bool
    bom_items: list[BOMItemOut] = []


# ── Raw Material ──────────────────────────────────────────────
class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    material_id: int
    material_name: str
    unit: str
    stock_qty: Decimal
    minimum_qty: Decimal
    cost_per_unit: Decimal
    low_stock: bool = False   # computed field

    @classmethod
    def from_orm_with_alert(cls, obj):
        d = cls.model_validate(obj)
        d.low_stock = obj.stock_qty < obj.minimum_qty
        return d

class MaterialUpdate(BaseModel):
    stock_qty: Optional[Decimal] = None
    minimum_qty: Optional[Decimal] = None
    cost_per_unit: Optional[Decimal] = None


# ── Order / Sales ─────────────────────────────────────────────
class OrderItemIn(BaseModel):
    seq: int = 1
    product_code: Optional[str] = None
    product_name: str
    quantity_ton: Decimal = Decimal("0")
    unit: str = "ตัน"
    unit_price: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    salesperson: Optional[str] = None
    sale_support_name: Optional[str] = None
    team_zone: Optional[str] = None
    so_ref: Optional[str] = None
    notes: Optional[str] = None

class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_id: int
    seq: int
    product_code: Optional[str]
    product_name: str
    quantity_ton: Decimal
    unit: str
    unit_price: Decimal
    discount: Decimal
    line_amount: Optional[Decimal]
    salesperson: Optional[str]
    sale_support_name: Optional[str]
    team_zone: Optional[str]
    so_ref: Optional[str]
    notes: Optional[str]

class OrderCreate(BaseModel):
    order_id: Optional[str] = None
    customer_id: int
    salesperson: str
    sale_support_name: Optional[str] = None
    dept: Optional[str] = None
    items: list[OrderItemIn] = []
    initial_status: Optional[str] = "DRAFT"
    delivery_due_date: Optional[date] = None
    line_note: Optional[str] = None
    notes: Optional[str] = None

class OrderApprove(BaseModel):
    approved_by: str

class OrderReject(BaseModel):
    rejected_reason: str

class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    order_id: str
    customer_id: int
    salesperson: str
    sale_support_name: Optional[str]
    dept: Optional[str]
    total_amount: Optional[Decimal]
    order_status: OrderStatus
    credit_alert: bool
    credit_limit_snapshot: Optional[Decimal]
    outstanding_snapshot: Optional[Decimal]
    line_note: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejected_reason: Optional[str]
    order_date: datetime
    delivery_due_date: Optional[date]
    notes: Optional[str]
    items: list[OrderItemOut] = []
    promotions: list["OrderPromotionOut"] = []


# ── Production ────────────────────────────────────────────────
class ProductionUpdate(BaseModel):
    production_status: Optional[ProductionStatus] = None
    bom_actual: Optional[list[dict[str, Any]]] = None   # [{material_name, qty_used, unit}]
    raw_material_cost: Optional[Decimal] = None
    labor_cost: Optional[Decimal] = None
    packaging_cost: Optional[Decimal] = None
    produced_by: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    qc_passed: Optional[bool] = None
    notes: Optional[str] = None

class ProductionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    production_id: int
    order_id: str
    production_status: ProductionStatus
    bom_actual: Optional[list]
    raw_material_cost: Decimal
    labor_cost: Decimal
    packaging_cost: Decimal
    production_cost_total: Optional[Decimal]
    produced_by: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    qc_passed: bool


# ── Accounting ────────────────────────────────────────────────
class AccountingUpdate(BaseModel):
    payment_status: Optional[PaymentStatus] = None
    invoice_number: Optional[str] = None
    paid_amount: Optional[Decimal] = None
    due_date: Optional[date] = None
    paid_date: Optional[datetime] = None
    notes: Optional[str] = None

class AccountingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    order_id: str
    total_sales_amount: Decimal
    total_cost_amount: Decimal
    gross_profit: Decimal
    gross_margin_pct: Optional[Decimal]
    payment_status: PaymentStatus
    invoice_number: Optional[str]
    paid_amount: Decimal
    due_date: Optional[date]


# ── Bag Items (master) ────────────────────────────────────────
class BagItemCreate(BaseModel):
    item_code: str
    item_name: str
    item_type: Optional[str] = None

class BagItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_id: int
    item_code: str
    item_name: str
    item_type: Optional[str]
    is_active: bool


# ── Bag Stock Session ─────────────────────────────────────────
class BagStockEntryIn(BaseModel):
    item_id: Optional[int] = None
    item_code: str
    item_name: str
    bag_count: Decimal
    bag_price_unit: Decimal
    notes: Optional[str] = None

class BagStockSessionCreate(BaseModel):
    stock_date: date
    session_note: Optional[str] = None
    created_by: Optional[str] = None
    entries: list[BagStockEntryIn] = []

class BagStockEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entry_id: int
    item_id: Optional[int]
    item_code: str
    item_name: str
    bag_count: Decimal
    bag_price_unit: Decimal
    total_bag_cost: Optional[Decimal]
    notes: Optional[str]

class BagStockSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: int
    stock_date: date
    session_note: Optional[str]
    created_by: Optional[str]
    created_at: Optional[datetime]
    entries: list[BagStockEntryOut] = []
    total_bags: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None


# ── Raw Material Stock ────────────────────────────────────────
class RmStockEntryIn(BaseModel):
    entry_type: RmEntryTypeEnum = RmEntryTypeEnum.RAW
    material_name: str
    stock_qty_ton: Optional[Decimal] = None
    price_per_ton: Optional[Decimal] = None
    po_ref: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int = 0

class RmSessionCreate(BaseModel):
    stock_date: date
    notes: Optional[str] = None
    created_by: Optional[str] = None
    rm_entries: list[RmStockEntryIn] = []
    fg_entries: list[RmStockEntryIn] = []

class ProductionMaterialUsage(BaseModel):
    name: str
    qty_kg: float

class ProductionUsageIn(BaseModel):
    usage_date: date
    notes: Optional[str] = None
    machine_nos: list[str] = []
    materials: list[ProductionMaterialUsage]

class RmStockEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entry_id: int
    entry_type: RmEntryTypeEnum
    material_name: str
    stock_qty_ton: Optional[Decimal]
    price_per_ton: Optional[Decimal]
    total_value: Optional[Decimal]
    po_ref: Optional[str]
    notes: Optional[str]
    sort_order: int

class RmSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: int
    stock_date: date
    notes: Optional[str]
    created_by: Optional[str]
    total_rm_value: Optional[Decimal]
    total_fg_value: Optional[Decimal]
    total_paid_po: Optional[Decimal]
    total_pending_po: Optional[Decimal]
    created_at: Optional[datetime]
    entries: list[RmStockEntryOut] = []
    pos: list["PoOut"] = []
    rm_sales: list["RmSaleOut"] = []


# ── Purchase Orders ───────────────────────────────────────────
class PoCreate(BaseModel):
    session_id: Optional[int] = None
    po_date: Optional[date] = None
    supplier_name: str
    po_number: Optional[str] = None
    material_name: str
    qty_ton: Optional[Decimal] = None
    price_per_ton: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    freight_cost: Optional[Decimal] = Decimal("0")
    payment_date: Optional[date] = None
    po_status: PoStatusEnum = PoStatusEnum.PAID
    conditions: Optional[str] = None
    notes: Optional[str] = None

class PoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    po_id: int
    session_id: Optional[int]
    po_date: Optional[date]
    supplier_name: str
    po_number: Optional[str]
    material_name: str
    qty_ton: Optional[Decimal]
    price_per_ton: Optional[Decimal]
    amount: Optional[Decimal]
    freight_cost: Optional[Decimal]
    payment_date: Optional[date]
    po_status: PoStatusEnum
    conditions: Optional[str]
    notes: Optional[str]


# ── RM Sales (ขายวัตถุดิบออก) ────────────────────────────────
class RmSaleCreate(BaseModel):
    session_id: Optional[int] = None
    sale_date: date
    buyer_name: str
    material_name: str
    qty_ton: Optional[Decimal] = None
    price_per_ton: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    payment_date: Optional[date] = None
    conditions: Optional[str] = None
    notes: Optional[str] = None

class RmSaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rm_sale_id: int
    session_id: Optional[int]
    sale_date: date
    buyer_name: str
    material_name: str
    qty_ton: Optional[Decimal]
    price_per_ton: Optional[Decimal]
    amount: Optional[Decimal]
    payment_date: Optional[date]
    conditions: Optional[str]
    notes: Optional[str]
    created_at: Optional[datetime]


# ── Shop Master ───────────────────────────────────────────────
class ShopMasterCreate(BaseModel):
    shop_name: str
    region: Optional[str] = None
    zone: Optional[str] = None
    employee_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True

class ShopMasterUpdate(BaseModel):
    shop_name: Optional[str] = None
    region: Optional[str] = None
    zone: Optional[str] = None
    employee_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class ShopMasterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    shop_id: int
    shop_name: str
    region: Optional[str]
    zone: Optional[str]
    employee_name: Optional[str]
    phone: Optional[str]
    is_active: bool


# ── Promotions (รายการส่งเสริมการขาย) ───────────────────────
class PromotionGiftCreate(BaseModel):
    gift_name: str
    unit: str = "ชิ้น"
    stock_qty: Decimal = Decimal("0")
    qty_per_ton: Decimal = Decimal("0")
    dead_stock_qty: Decimal = Decimal("0")
    gift_image_url: Optional[str] = None
    notes: Optional[str] = None

class PromotionGiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gift_id: int
    gift_name: str
    unit: str
    stock_qty: Decimal
    qty_per_ton: Decimal
    dead_stock_qty: Decimal
    gift_image_url: Optional[str]
    notes: Optional[str]

class PromotionGiftStockUpdate(BaseModel):
    stock_qty: Decimal

class PromoShopCreate(BaseModel):
    shop_name: str
    region: Optional[str] = None
    qty_ton: Decimal = Decimal("0")
    qty_allocated: Decimal = Decimal("0")
    notes: Optional[str] = None

class PromoShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    shop_id: int
    promotion_id: int
    shop_name: str
    region: Optional[str]
    qty_ton: Decimal
    qty_allocated: Decimal
    qty_dispatched: Decimal
    notes: Optional[str]

class PromotionCreate(BaseModel):
    promo_name: str
    description: Optional[str] = None
    product_filter: Optional[str] = None
    multiplier: Decimal = Decimal("0")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool = True
    notes: Optional[str] = None
    gifts: list[PromotionGiftCreate] = []
    shops: list[PromoShopCreate] = []

class PromotionUpdate(BaseModel):
    promo_name: Optional[str] = None
    description: Optional[str] = None
    product_filter: Optional[str] = None
    multiplier: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    gifts: Optional[list[PromotionGiftCreate]] = None
    shops: Optional[list[PromoShopCreate]] = None

class PromotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    promotion_id: int
    promo_name: str
    description: Optional[str]
    product_filter: Optional[str]
    multiplier: Optional[Decimal]
    start_date: Optional[date]
    end_date: Optional[date]
    is_active: bool
    notes: Optional[str]
    gifts: list[PromotionGiftOut] = []
    shops: list[PromoShopOut] = []

class OrderPromotionIn(BaseModel):
    promotion_id: int
    gift_id: int
    qty_given: Decimal = Decimal("1")
    notes: Optional[str] = None

class GiftDispatchCreate(BaseModel):
    dispatch_date: date
    qty_dispatched: Decimal
    dispatched_by: Optional[str] = None
    shop_name: Optional[str] = None
    region: Optional[str] = None
    notes: Optional[str] = None

class DirectDispatchCreate(BaseModel):
    """แจกของแจกโดยตรงจากโปรโมชัน → ร้าน → ของแจก (ไม่ผ่าน order)"""
    promo_shop_id: int
    gift_id: int
    dispatch_date: date
    qty_dispatched: Decimal
    dispatch_type: str = "dispatch"           # 'dispatch' | 'trip_withdrawal'
    dispatched_by: Optional[str] = None
    salesperson_name: Optional[str] = None   # สำหรับ trip_withdrawal
    notes: Optional[str] = None

class GiftDispatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dispatch_id: int
    op_id: Optional[int]
    dispatch_date: date
    qty_dispatched: Decimal
    dispatched_by: Optional[str]
    shop_name: Optional[str]
    region: Optional[str]
    notes: Optional[str]
    created_at: Optional[datetime]

class OrderPromotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    op_id: int
    promotion_id: int
    gift_id: int
    gift_name: str
    qty_given: Decimal
    unit: str
    notes: Optional[str]
    dispatches: list[GiftDispatchOut] = []


# ── Dashboard ─────────────────────────────────────────────────
class DashboardRow(BaseModel):
    order_id: str
    order_date: Optional[datetime]
    delivery_due_date: Optional[date]
    customer_code: Optional[str]
    customer_name: Optional[str]
    credit_limit: Optional[Decimal]
    outstanding_balance: Optional[Decimal]
    credit_exceeded: Optional[bool]
    salesperson: Optional[str]
    sale_support_name: Optional[str]
    dept: Optional[str]
    total_amount: Optional[Decimal]
    order_status: Optional[str]
    credit_alert: Optional[bool]
    approved_by: Optional[str]
    production_status: Optional[str]
    production_cost_total: Optional[Decimal]
    qc_passed: Optional[bool]
    payment_status: Optional[str]
    gross_profit: Optional[Decimal]
    gross_margin_pct: Optional[Decimal]
    paid_amount: Optional[Decimal]
    due_date: Optional[date]
