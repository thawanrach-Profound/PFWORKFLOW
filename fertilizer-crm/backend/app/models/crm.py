import enum
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, DateTime,
    Text, ForeignKey, Date, Enum, func, Computed, SmallInteger, FetchedValue
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class CreditTerm(str, enum.Enum):
    D30 = "30"; D45 = "45"; D60 = "60"; D90 = "90"; D120 = "120"; OTHER = "OTHER"


class OrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IN_PRODUCTION = "IN_PRODUCTION"
    READY_TO_SHIP = "READY_TO_SHIP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class ProductionStatus(str, enum.Enum):
    WAITING = "WAITING"
    IN_PROGRESS = "IN_PROGRESS"
    DISPATCHED = "DISPATCHED"


class PaymentStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


# ── Customer ──────────────────────────────────────────────────
class Customer(Base):
    __tablename__ = "customers"
    customer_id         = Column(Integer, primary_key=True, autoincrement=True)
    customer_code       = Column(String(20), unique=True, nullable=False)
    company_name        = Column(String(255), nullable=False)
    contact_name        = Column(String(100))
    phone               = Column(String(20))
    address             = Column(Text)
    credit_term         = Column(Enum(CreditTerm, name="credit_term", values_callable=lambda x: [e.value for e in x]), default=CreditTerm.D30)
    credit_limit        = Column(Numeric(14, 2), default=0)
    outstanding_balance = Column(Numeric(14, 2), default=0)
    is_active           = Column(Boolean, default=True)
    notes               = Column(Text)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now())

    orders = relationship("Sales", back_populates="customer")


# ── Formula ───────────────────────────────────────────────────
class FertilizerFormula(Base):
    __tablename__ = "fertilizer_formulas"
    formula_id          = Column(Integer, primary_key=True, autoincrement=True)
    formula_code        = Column(String(30), unique=True, nullable=False)
    product_code        = Column(String(50))
    formula_name        = Column(String(255), nullable=False)
    description         = Column(Text)
    base_price_per_kg   = Column(Numeric(10, 4), default=0)
    is_active           = Column(Boolean, default=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now())

    bom_items = relationship("FormulaBOM", back_populates="formula", cascade="all, delete-orphan")


# ── Formula BOM ───────────────────────────────────────────────
class FormulaBOM(Base):
    __tablename__ = "formula_bom"
    bom_id          = Column(Integer, primary_key=True, autoincrement=True)
    formula_id      = Column(Integer, ForeignKey("fertilizer_formulas.formula_id", ondelete="CASCADE"))
    material_name   = Column(String(100), nullable=False)
    qty_per_100kg   = Column(Numeric(10, 4), nullable=False)
    unit            = Column(String(20), default="kg")
    cost_per_unit   = Column(Numeric(10, 4), default=0)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    formula = relationship("FertilizerFormula", back_populates="bom_items")


# ── Order Item ────────────────────────────────────────────────
class OrderItem(Base):
    __tablename__ = "order_items"
    item_id      = Column(Integer, primary_key=True, autoincrement=True)
    order_id     = Column(String(20), ForeignKey("sales.order_id", ondelete="CASCADE"), nullable=False)
    seq          = Column(SmallInteger, default=1)
    product_code = Column(String(100))
    product_name = Column(String(200), nullable=False)
    quantity_ton = Column(Numeric(12, 4), default=0)
    unit         = Column(String(20), default="ตัน")
    unit_price   = Column(Numeric(12, 2), default=0)
    discount     = Column(Numeric(12, 2), default=0)
    line_amount       = Column(Numeric(14, 2), Computed("quantity_ton * unit_price - discount", persisted=True))
    salesperson       = Column(String(100))
    sale_support_name = Column(String(100))
    team_zone         = Column(String(50))
    so_ref            = Column(String(50))
    notes             = Column(Text)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Sales", back_populates="items")


# ── Raw Material ──────────────────────────────────────────────
class RawMaterial(Base):
    __tablename__ = "raw_materials"
    material_id     = Column(Integer, primary_key=True, autoincrement=True)
    material_name   = Column(String(100), unique=True, nullable=False)
    unit            = Column(String(20), default="kg")
    stock_qty       = Column(Numeric(14, 4), default=0)
    minimum_qty     = Column(Numeric(14, 4), default=0)
    cost_per_unit   = Column(Numeric(10, 4), default=0)
    updated_at      = Column(DateTime(timezone=True), server_default=func.now())


# ── Sales / Order ─────────────────────────────────────────────
class Sales(Base):
    __tablename__ = "sales"
    order_id                = Column(String(20), primary_key=True)
    customer_id             = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    salesperson             = Column(String(100), nullable=False)   # รหัสพนักงานขาย
    sale_support_name       = Column(String(100))                   # Sale Support ผู้คีย์ข้อมูล
    dept                    = Column(String(20))                    # แผนก S1/S2/.../T001
    total_amount            = Column(Numeric(14, 2), default=0)     # รวมทั้งสิ้น (sum of line items)
    order_status            = Column(Enum(OrderStatus, name="order_status"), default=OrderStatus.DRAFT)
    credit_limit_snapshot   = Column(Numeric(14, 2))
    outstanding_snapshot    = Column(Numeric(14, 2))
    credit_alert            = Column(Boolean, default=False)
    line_note               = Column(Text)
    approved_by             = Column(String(100))
    approved_at             = Column(DateTime(timezone=True))
    rejected_reason         = Column(Text)
    order_date              = Column(DateTime(timezone=True), server_default=func.now())
    delivery_due_date       = Column(Date)
    notes                   = Column(Text)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())
    updated_at              = Column(DateTime(timezone=True), server_default=func.now())

    customer    = relationship("Customer", back_populates="orders")
    items       = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.seq")
    promotions  = relationship("OrderPromotion", back_populates="order", cascade="all, delete-orphan")
    production  = relationship("Production", back_populates="sales", uselist=False)
    accounting  = relationship("Accounting", back_populates="sales", uselist=False)


# ── Production ────────────────────────────────────────────────
class Production(Base):
    __tablename__ = "production"
    production_id           = Column(Integer, primary_key=True, autoincrement=True)
    order_id                = Column(String(20), ForeignKey("sales.order_id", ondelete="CASCADE"), unique=True)
    production_status       = Column(Enum(ProductionStatus, name="production_status"), default=ProductionStatus.WAITING)
    bom_actual              = Column(JSONB)   # [{material_name, qty_used, unit}]
    raw_material_cost       = Column(Numeric(14, 2), default=0)
    labor_cost              = Column(Numeric(14, 2), default=0)
    packaging_cost          = Column(Numeric(14, 2), default=0)
    production_cost_total   = Column(Numeric(14, 2), server_default=FetchedValue())   # GENERATED ALWAYS AS in DB
    produced_by             = Column(String(100))
    start_date              = Column(DateTime(timezone=True))
    end_date                = Column(DateTime(timezone=True))
    qc_passed               = Column(Boolean, default=False)
    notes                   = Column(Text)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())
    updated_at              = Column(DateTime(timezone=True), server_default=func.now())

    sales = relationship("Sales", back_populates="production")


# ── Accounting ────────────────────────────────────────────────
class Accounting(Base):
    __tablename__ = "accounting"
    accounting_id       = Column(Integer, primary_key=True, autoincrement=True)
    order_id            = Column(String(20), ForeignKey("sales.order_id", ondelete="CASCADE"), unique=True)
    total_sales_amount  = Column(Numeric(14, 2), default=0)
    total_cost_amount   = Column(Numeric(14, 2), default=0)
    gross_profit        = Column(Numeric(14, 2), default=0)
    gross_margin_pct    = Column(Numeric(6, 2))
    payment_status      = Column(Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.UNPAID)
    invoice_number      = Column(String(50))
    paid_amount         = Column(Numeric(14, 2), default=0)
    due_date            = Column(Date)
    paid_date           = Column(DateTime(timezone=True))
    notes               = Column(Text)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now())

    sales = relationship("Sales", back_populates="accounting")


# ── Bag Items (ทะเบียนกระสอบ/ถุง — master) ───────────────────
class BagItem(Base):
    __tablename__ = "bag_items"
    item_id     = Column(Integer, primary_key=True, autoincrement=True)
    item_code   = Column(String(30), unique=True, nullable=False)
    item_name   = Column(String(200), nullable=False)
    item_type   = Column(String(50))   # ถุงใน / ไก่งวง / คนเขียว
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    entries = relationship("BagStockEntry", back_populates="item")


# ── Bag Stock Sessions (แต่ละรอบตรวจนับ) ─────────────────────
class BagStockSession(Base):
    __tablename__ = "bag_stock_sessions"
    session_id   = Column(Integer, primary_key=True, autoincrement=True)
    stock_date   = Column(Date, nullable=False)
    session_note = Column(Text)
    created_by   = Column(String(100))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    entries = relationship("BagStockEntry", back_populates="session", cascade="all, delete-orphan")


# ── Bag Stock Entries (รายการกระสอบต่อรอบ) ───────────────────
class BagStockEntry(Base):
    __tablename__ = "bag_stock_entries"
    entry_id        = Column(Integer, primary_key=True, autoincrement=True)
    session_id      = Column(Integer, ForeignKey("bag_stock_sessions.session_id", ondelete="CASCADE"), nullable=False)
    item_id         = Column(Integer, ForeignKey("bag_items.item_id"))
    item_code       = Column(String(30), nullable=False)
    item_name       = Column(String(200), nullable=False)
    bag_count       = Column(Numeric(12, 2), nullable=False, default=0)
    bag_price_unit  = Column(Numeric(10, 4), nullable=False, default=0)
    total_bag_cost  = Column(Numeric(14, 2), Computed("bag_count * bag_price_unit", persisted=True))
    notes           = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("BagStockSession", back_populates="entries")
    item    = relationship("BagItem", back_populates="entries")


# ── RM Stock Sessions ─────────────────────────────────────────
class RmStockSession(Base):
    __tablename__ = "rm_stock_sessions"
    session_id       = Column(Integer, primary_key=True, autoincrement=True)
    stock_date       = Column(Date, nullable=False)
    notes            = Column(Text)
    created_by       = Column(String(100))
    total_rm_value   = Column(Numeric(16, 2))
    total_fg_value   = Column(Numeric(16, 2))
    total_paid_po    = Column(Numeric(16, 2))
    total_pending_po = Column(Numeric(16, 2))
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    entries   = relationship("RmStockEntry", back_populates="session", cascade="all, delete-orphan")
    pos       = relationship("PurchaseOrder", back_populates="session")
    rm_sales  = relationship("RmSale", back_populates="session")


class RmEntryTypeEnum(str, enum.Enum):
    RAW = "RAW"
    FG  = "FG"


# ── RM Stock Entries (วัตถุดิบ + FG ต่อรอบ) ──────────────────
class RmStockEntry(Base):
    __tablename__ = "rm_stock_entries"
    entry_id      = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(Integer, ForeignKey("rm_stock_sessions.session_id", ondelete="CASCADE"), nullable=False)
    entry_type    = Column(Enum(RmEntryTypeEnum, name="rm_entry_type"), nullable=False, default=RmEntryTypeEnum.RAW)
    material_name = Column(String(100), nullable=False)
    stock_qty_ton = Column(Numeric(14, 4))
    price_per_ton = Column(Numeric(12, 2))
    total_value   = Column(Numeric(16, 2), Computed("stock_qty_ton * price_per_ton", persisted=True))
    po_ref        = Column(String(50))
    notes         = Column(Text)
    sort_order    = Column(Integer, default=0)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("RmStockSession", back_populates="entries")


class PoStatusEnum(str, enum.Enum):
    PAID    = "PAID"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"


# ── Purchase Orders (PO ซื้อวัตถุดิบ) ────────────────────────
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(Integer, ForeignKey("rm_stock_sessions.session_id", ondelete="SET NULL"))
    po_date       = Column(Date)
    supplier_name = Column(String(100), nullable=False)
    po_number     = Column(String(50))
    material_name = Column(String(100), nullable=False)
    qty_ton       = Column(Numeric(14, 4))
    price_per_ton = Column(Numeric(12, 2))
    amount        = Column(Numeric(16, 2))
    freight_cost  = Column(Numeric(14, 2), default=0)
    payment_date  = Column(Date)
    po_status     = Column(Enum(PoStatusEnum, name="po_status"), nullable=False, default=PoStatusEnum.PAID)
    conditions    = Column(String(200))
    notes         = Column(Text)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("RmStockSession", back_populates="pos")


# ── RM Sales (ขายวัตถุดิบออกให้บริษัทอื่น) ──────────────────
class RmSale(Base):
    __tablename__ = "rm_sales"
    rm_sale_id    = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(Integer, ForeignKey("rm_stock_sessions.session_id", ondelete="SET NULL"))
    sale_date     = Column(Date, nullable=False, server_default=func.current_date())
    buyer_name    = Column(String(100), nullable=False)
    material_name = Column(String(100), nullable=False)
    qty_ton       = Column(Numeric(14, 4))
    price_per_ton = Column(Numeric(12, 2))
    amount        = Column(Numeric(16, 2))
    payment_date  = Column(Date)
    conditions    = Column(String(200))
    notes         = Column(Text)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("RmStockSession", back_populates="rm_sales")


# ── Promotions (รายการส่งเสริมการขาย) ───────────────────────
class Promotion(Base):
    __tablename__ = "promotions"
    promotion_id = Column(Integer, primary_key=True, autoincrement=True)
    promo_name   = Column(String(200), nullable=False)
    description  = Column(Text)
    start_date   = Column(Date)
    end_date     = Column(Date)
    is_active    = Column(Boolean, default=True)
    notes        = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), server_default=func.now())

    gifts = relationship("PromotionGift", back_populates="promotion", cascade="all, delete-orphan")


class PromotionGift(Base):
    __tablename__ = "promotion_gifts"
    gift_id      = Column(Integer, primary_key=True, autoincrement=True)
    promotion_id = Column(Integer, ForeignKey("promotions.promotion_id", ondelete="CASCADE"), nullable=False)
    gift_name    = Column(String(200), nullable=False)
    unit         = Column(String(30), default="ชิ้น")
    stock_qty    = Column(Numeric(12, 2), default=0)
    notes        = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    promotion = relationship("Promotion", back_populates="gifts")
    order_uses = relationship("OrderPromotion", back_populates="gift")


class OrderPromotion(Base):
    __tablename__ = "order_promotions"
    op_id        = Column(Integer, primary_key=True, autoincrement=True)
    order_id     = Column(String(20), ForeignKey("sales.order_id", ondelete="CASCADE"), nullable=False)
    promotion_id = Column(Integer, ForeignKey("promotions.promotion_id"), nullable=False)
    gift_id      = Column(Integer, ForeignKey("promotion_gifts.gift_id"), nullable=False)
    gift_name    = Column(String(200), nullable=False)
    qty_given    = Column(Numeric(12, 2), default=1)
    unit         = Column(String(30), default="ชิ้น")
    notes        = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    order      = relationship("Sales", back_populates="promotions")
    promotion  = relationship("Promotion")
    gift       = relationship("PromotionGift", back_populates="order_uses")
    dispatches = relationship("GiftDispatch", back_populates="order_promotion", cascade="all, delete-orphan")


class GiftDispatch(Base):
    __tablename__ = "gift_dispatches"
    dispatch_id    = Column(Integer, primary_key=True, autoincrement=True)
    op_id          = Column(Integer, ForeignKey("order_promotions.op_id", ondelete="CASCADE"), nullable=False)
    dispatch_date  = Column(Date, nullable=False, server_default=func.current_date())
    qty_dispatched = Column(Numeric(12, 2), nullable=False)
    dispatched_by  = Column(String(100))
    shop_name      = Column(String(200))
    region         = Column(String(50))
    notes          = Column(Text)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    order_promotion = relationship("OrderPromotion", back_populates="dispatches")
