-- ============================================================
-- ระบบ CRM บริษัทขายปุ๋ย
-- PostgreSQL
-- ============================================================

-- ============================================================
-- 0. EMPLOYEES (พนักงาน)
-- ============================================================
-- (สร้างก่อน ENUM อื่น)

-- ENUM Types
CREATE TYPE employee_role AS ENUM ('SALE','SALE_SUPPORT','WAREHOUSE','PRODUCTION','ADMIN');

CREATE TABLE IF NOT EXISTS employees (
    employee_id   SERIAL          PRIMARY KEY,
    employee_code VARCHAR(20)     UNIQUE NOT NULL,
    full_name     VARCHAR(100)    NOT NULL,
    role          employee_role   NOT NULL,
    phone         VARCHAR(20),
    email         VARCHAR(100),
    is_active     BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE TYPE credit_term AS ENUM ('30','45','60','90','120','OTHER');
CREATE TYPE order_status AS ENUM ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','IN_PRODUCTION','READY_TO_SHIP','DELIVERED','CANCELLED');
CREATE TYPE production_status AS ENUM ('WAITING','IN_PROGRESS','DISPATCHED');
CREATE TYPE payment_status AS ENUM ('UNPAID','PARTIAL','PAID','OVERDUE');

-- ============================================================
-- 1. CUSTOMERS
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    customer_id     SERIAL          PRIMARY KEY,
    customer_code   VARCHAR(20)     UNIQUE NOT NULL,           -- รหัสลูกค้า เช่น CUST-001
    company_name    VARCHAR(255)    NOT NULL,
    contact_name    VARCHAR(100),
    phone           VARCHAR(20),
    address         TEXT,
    credit_term     credit_term     NOT NULL DEFAULT '30',     -- ระยะเวลาเครดิต (วัน)
    credit_limit    NUMERIC(14,2)   NOT NULL DEFAULT 0,        -- วงเงินเครดิตสูงสุด
    outstanding_balance NUMERIC(14,2) NOT NULL DEFAULT 0,      -- ยอดค้างชำระปัจจุบัน (อัปเดตจาก accounting)
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. FERTILIZER FORMULAS (ทะเบียนสูตรปุ๋ย — template)
-- ============================================================
CREATE TABLE IF NOT EXISTS fertilizer_formulas (
    formula_id      SERIAL          PRIMARY KEY,
    formula_code    VARCHAR(30)     UNIQUE NOT NULL,           -- เช่น 16-20-0
    formula_name    VARCHAR(255)    NOT NULL,
    description     TEXT,
    base_price_per_kg NUMERIC(10,4) NOT NULL DEFAULT 0,       -- ราคาขายต่อ kg (default)
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 3. FORMULA BOM (วัตถุดิบต่อสูตร — template, ปรับได้ต่อ Order)
-- ============================================================
CREATE TABLE IF NOT EXISTS formula_bom (
    bom_id          SERIAL          PRIMARY KEY,
    formula_id      INT             NOT NULL REFERENCES fertilizer_formulas(formula_id) ON DELETE CASCADE,
    material_name   VARCHAR(100)    NOT NULL,                  -- ชื่อวัตถุดิบ
    qty_per_100kg   NUMERIC(10,4)   NOT NULL,                  -- ปริมาณต่อปุ๋ย 100 kg
    unit            VARCHAR(20)     NOT NULL DEFAULT 'kg',
    cost_per_unit   NUMERIC(10,4)   NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 4. RAW MATERIALS (สต็อกวัตถุดิบ)
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_materials (
    material_id     SERIAL          PRIMARY KEY,
    material_name   VARCHAR(100)    UNIQUE NOT NULL,
    unit            VARCHAR(20)     NOT NULL DEFAULT 'kg',
    stock_qty       NUMERIC(14,4)   NOT NULL DEFAULT 0,
    minimum_qty     NUMERIC(14,4)   NOT NULL DEFAULT 0,        -- ปริมาณขั้นต่ำ — alert เมื่อต่ำกว่านี้
    cost_per_unit   NUMERIC(10,4)   NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 5. SALES / ORDERS (หัว Order — 1 invoice = หลาย line items)
-- ============================================================
CREATE TABLE IF NOT EXISTS sales (
    order_id        VARCHAR(20)     PRIMARY KEY,               -- เช่น I16904082 หรือ ORD-2026-0001
    customer_id     INT             NOT NULL REFERENCES customers(customer_id),
    salesperson     VARCHAR(100)    NOT NULL,                  -- รหัสพนักงานขาย เช่น X640101
    sale_support_name   VARCHAR(100),                          -- ชื่อ Sale Support ที่คีย์ข้อมูล
    dept            VARCHAR(20),                               -- แผนก เช่น S1, S2, T001
    total_amount    NUMERIC(14,2)   NOT NULL DEFAULT 0,        -- รวมทั้งสิ้น (อัปเดตจาก order_items)
    order_status    order_status    NOT NULL DEFAULT 'DRAFT',
    -- Credit snapshot ณ เวลาสั่ง
    credit_limit_snapshot   NUMERIC(14,2),
    outstanding_snapshot    NUMERIC(14,2),
    credit_alert            BOOLEAN NOT NULL DEFAULT FALSE,
    -- เนื้อหา Order จาก LINE
    line_note       TEXT,
    approved_by     VARCHAR(100),
    approved_at     TIMESTAMPTZ,
    rejected_reason TEXT,
    order_date      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    delivery_due_date DATE,
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 5b. ORDER ITEMS (รายการสินค้าต่อ Order)
-- ============================================================
CREATE TABLE IF NOT EXISTS order_items (
    item_id         SERIAL          PRIMARY KEY,
    order_id        VARCHAR(20)     NOT NULL REFERENCES sales(order_id) ON DELETE CASCADE,
    seq             SMALLINT        NOT NULL DEFAULT 1,         -- ลำดับรายการ
    product_code    VARCHAR(100),                              -- รหัสสินค้า เช่น 01-02-0300-200404-LD
    product_name    VARCHAR(200)    NOT NULL,                  -- ชื่อสินค้า เช่น คนเขียว 20-4-4 OX
    quantity_ton    NUMERIC(12,4)   NOT NULL DEFAULT 0,        -- จำนวน (ตัน)
    unit            VARCHAR(20)     NOT NULL DEFAULT 'ตัน',
    unit_price      NUMERIC(12,2)   NOT NULL DEFAULT 0,        -- ราคาต่อหน่วย (บาท/ตัน)
    discount        NUMERIC(12,2)   NOT NULL DEFAULT 0,
    line_amount     NUMERIC(14,2)   GENERATED ALWAYS AS (quantity_ton * unit_price - discount) STORED,
    salesperson         VARCHAR(100),                          -- พนักงานขาย (Sale) ต่อ line item
    sale_support_name   VARCHAR(100),                          -- ผู้ช่วยขาย (Support) ต่อ line item
    team_zone           VARCHAR(50),                           -- ทีม/เขต เช่น S1, S2, T001
    so_ref          VARCHAR(50),                               -- เลขที่ใบสั่งผลิต SO...
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 6. PRODUCTION
-- ============================================================
CREATE TABLE IF NOT EXISTS production (
    production_id   SERIAL          PRIMARY KEY,
    order_id        VARCHAR(20)     NOT NULL UNIQUE REFERENCES sales(order_id) ON DELETE CASCADE,
    production_status production_status NOT NULL DEFAULT 'WAITING',
    -- BOM จริงที่ใช้ผลิต (JSON เก็บ list วัตถุดิบ+ปริมาณจริง)
    bom_actual      JSONB,
    -- ต้นทุนจริง
    raw_material_cost NUMERIC(14,2) NOT NULL DEFAULT 0,
    labor_cost        NUMERIC(14,2) NOT NULL DEFAULT 0,
    packaging_cost    NUMERIC(14,2) NOT NULL DEFAULT 0,
    production_cost_total NUMERIC(14,2)
        GENERATED ALWAYS AS (raw_material_cost + labor_cost + packaging_cost) STORED,
    produced_by     VARCHAR(100),
    start_date      TIMESTAMPTZ,
    end_date        TIMESTAMPTZ,
    qc_passed       BOOLEAN         DEFAULT FALSE,
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 7. ACCOUNTING (ต้นทุน / กำไร / การชำระเงิน)
-- ============================================================
CREATE TABLE IF NOT EXISTS accounting (
    accounting_id   SERIAL          PRIMARY KEY,
    order_id        VARCHAR(20)     NOT NULL UNIQUE REFERENCES sales(order_id) ON DELETE CASCADE,
    total_sales_amount  NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cost_amount   NUMERIC(14,2) NOT NULL DEFAULT 0,
    gross_profit        NUMERIC(14,2) NOT NULL DEFAULT 0,
    gross_margin_pct    NUMERIC(6,2),
    payment_status  payment_status  NOT NULL DEFAULT 'UNPAID',
    invoice_number  VARCHAR(50),
    paid_amount     NUMERIC(14,2)   NOT NULL DEFAULT 0,
    due_date        DATE,
    paid_date       TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 8. BAG ITEMS (ทะเบียนกระสอบ/ถุงบรรจุ — master)
-- ============================================================
CREATE TABLE IF NOT EXISTS bag_items (
    item_id     SERIAL          PRIMARY KEY,
    item_code   VARCHAR(30)     UNIQUE NOT NULL,        -- รหัสสินค้า เช่น 15-02-0000-120420-00
    item_name   VARCHAR(200)    NOT NULL,               -- ชื่อ เช่น กระสอบ คนเขียว 12-4-20
    item_type   VARCHAR(50),                            -- ถุงใน / ไก่งวง / คนเขียว
    is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 9. BAG STOCK SESSIONS (แต่ละรอบตรวจนับ)
-- ============================================================
CREATE TABLE IF NOT EXISTS bag_stock_sessions (
    session_id   SERIAL          PRIMARY KEY,
    stock_date   DATE            NOT NULL,              -- วันที่ตรวจนับ
    session_note TEXT,                                  -- เช่น "เช้าก่อนผลิต"
    created_by   VARCHAR(100),
    created_at   TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 10. BAG STOCK ENTRIES (รายการกระสอบต่อรอบตรวจนับ)
-- ============================================================
CREATE TABLE IF NOT EXISTS bag_stock_entries (
    entry_id        SERIAL          PRIMARY KEY,
    session_id      INT             NOT NULL REFERENCES bag_stock_sessions(session_id) ON DELETE CASCADE,
    item_id         INT             REFERENCES bag_items(item_id),
    item_code       VARCHAR(30)     NOT NULL,           -- denormalized
    item_name       VARCHAR(200)    NOT NULL,
    bag_count       NUMERIC(12,2)   NOT NULL DEFAULT 0,
    bag_price_unit  NUMERIC(10,4)   NOT NULL DEFAULT 0,
    total_bag_cost  NUMERIC(14,2)   GENERATED ALWAYS AS (bag_count * bag_price_unit) STORED,
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_bag_sessions_date  ON bag_stock_sessions(stock_date DESC);
CREATE INDEX idx_bag_entries_sess   ON bag_stock_entries(session_id);
CREATE INDEX idx_bag_entries_item   ON bag_stock_entries(item_id);

-- ============================================================
-- 11. RAW MATERIAL STOCK SESSIONS (แต่ละรอบ snapshot วัตถุดิบ)
-- ============================================================
CREATE TABLE IF NOT EXISTS rm_stock_sessions (
    session_id          SERIAL          PRIMARY KEY,
    stock_date          DATE            NOT NULL,
    notes               TEXT,
    created_by          VARCHAR(100),
    total_rm_value      NUMERIC(16,2),   -- มูลค่าวัตถุดิบรวม
    total_fg_value      NUMERIC(16,2),   -- มูลค่า FG รวม
    total_paid_po       NUMERIC(16,2),   -- ยอด PO จ่ายแล้ว
    total_pending_po    NUMERIC(16,2),   -- ยอด PO รอขน
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 12. RM STOCK ENTRIES (สต็อกวัตถุดิบ + FG ต่อรอบ)
-- ============================================================
CREATE TYPE rm_entry_type AS ENUM ('RAW','FG');

CREATE TABLE IF NOT EXISTS rm_stock_entries (
    entry_id        SERIAL          PRIMARY KEY,
    session_id      INT             NOT NULL REFERENCES rm_stock_sessions(session_id) ON DELETE CASCADE,
    entry_type      rm_entry_type   NOT NULL DEFAULT 'RAW',  -- RAW=วัตถุดิบ, FG=สำเร็จรูป
    material_name   VARCHAR(100)    NOT NULL,
    stock_qty_ton   NUMERIC(14,4),                          -- จำนวน (ตัน)
    price_per_ton   NUMERIC(12,2),                          -- ราคา/ตัน
    total_value     NUMERIC(16,2)   GENERATED ALWAYS AS (stock_qty_ton * price_per_ton) STORED,
    po_ref          VARCHAR(50),
    notes           TEXT,
    sort_order      INT             DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 13. PURCHASE ORDERS (PO ซื้อวัตถุดิบ)
-- ============================================================
CREATE TYPE po_status AS ENUM ('PAID','PENDING','PARTIAL');

CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id           SERIAL          PRIMARY KEY,
    session_id      INT             REFERENCES rm_stock_sessions(session_id) ON DELETE SET NULL,
    po_date         DATE,
    supplier_name   VARCHAR(100)    NOT NULL,
    po_number       VARCHAR(50),
    material_name   VARCHAR(100)    NOT NULL,
    qty_ton         NUMERIC(14,4),
    price_per_ton   NUMERIC(12,2),
    amount          NUMERIC(16,2),
    freight_cost    NUMERIC(14,2)   DEFAULT 0,   -- ค่าขนส่งแยก
    payment_date    DATE,
    po_status       po_status       NOT NULL DEFAULT 'PAID',
    conditions      VARCHAR(200),   -- เงื่อนไข เช่น "13700", "ทยอยจ่าย"
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 14. RM SALES (รายการขายวัตถุดิบออกให้บริษัทอื่น)
-- ============================================================
CREATE TABLE IF NOT EXISTS rm_sales (
    rm_sale_id      SERIAL          PRIMARY KEY,
    session_id      INT             REFERENCES rm_stock_sessions(session_id) ON DELETE SET NULL,
    sale_date       DATE            NOT NULL DEFAULT CURRENT_DATE,
    buyer_name      VARCHAR(100)    NOT NULL,   -- ชื่อบริษัทผู้ซื้อ
    material_name   VARCHAR(100)    NOT NULL,   -- สินค้าที่ขาย
    qty_ton         NUMERIC(14,4),
    price_per_ton   NUMERIC(12,2),
    amount          NUMERIC(16,2),
    payment_date    DATE,
    conditions      VARCHAR(200),
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 15. PROMOTIONS (รายการส่งเสริมการขาย)
-- ============================================================
CREATE TABLE IF NOT EXISTS promotions (
    promotion_id    SERIAL          PRIMARY KEY,
    promo_name      VARCHAR(200)    NOT NULL,           -- ชื่อรายการส่งเสริมการขาย
    description     TEXT,
    start_date      DATE,
    end_date        DATE,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 16. PROMOTION GIFTS (ของแจกในรายการส่งเสริมการขาย)
-- ============================================================
CREATE TABLE IF NOT EXISTS promotion_gifts (
    gift_id         SERIAL          PRIMARY KEY,
    promotion_id    INT             NOT NULL REFERENCES promotions(promotion_id) ON DELETE CASCADE,
    gift_name       VARCHAR(200)    NOT NULL,           -- ชื่อของแจก เช่น เสื้อ, หมวก
    unit            VARCHAR(30)     NOT NULL DEFAULT 'ชิ้น',
    stock_qty       NUMERIC(12,2)   NOT NULL DEFAULT 0, -- stock คงเหลือ
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 17. ORDER PROMOTIONS (โปรโมชันที่ใช้ใน Order + ตัด stock)
-- ============================================================
CREATE TABLE IF NOT EXISTS order_promotions (
    op_id           SERIAL          PRIMARY KEY,
    order_id        VARCHAR(20)     NOT NULL REFERENCES sales(order_id) ON DELETE CASCADE,
    promotion_id    INT             NOT NULL REFERENCES promotions(promotion_id),
    gift_id         INT             NOT NULL REFERENCES promotion_gifts(gift_id),
    gift_name       VARCHAR(200)    NOT NULL,           -- snapshot ณ เวลาสั่ง
    qty_given       NUMERIC(12,2)   NOT NULL DEFAULT 1, -- จำนวนที่แจก
    unit            VARCHAR(30)     NOT NULL DEFAULT 'ชิ้น',
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ============================================================
-- 18. GIFT DISPATCHES (บันทึกการแจกของจริงแต่ละครั้ง)
-- ============================================================
CREATE TABLE IF NOT EXISTS gift_dispatches (
    dispatch_id     SERIAL          PRIMARY KEY,
    op_id           INT             NOT NULL REFERENCES order_promotions(op_id) ON DELETE CASCADE,
    dispatch_date   DATE            NOT NULL DEFAULT CURRENT_DATE,
    qty_dispatched  NUMERIC(12,2)   NOT NULL CHECK (qty_dispatched > 0),
    dispatched_by   VARCHAR(100),   -- ชื่อผู้แจก
    shop_name       VARCHAR(200),   -- ชื่อร้านค้า
    region          VARCHAR(50),    -- ภาค
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- migration: add shop_name/region if not exists
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='gift_dispatches' AND column_name='shop_name') THEN
    ALTER TABLE gift_dispatches ADD COLUMN shop_name VARCHAR(200);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='gift_dispatches' AND column_name='region') THEN
    ALTER TABLE gift_dispatches ADD COLUMN region VARCHAR(50);
  END IF;
END $$;

CREATE INDEX idx_gift_dispatches_op    ON gift_dispatches(op_id);
CREATE INDEX idx_gift_dispatches_date  ON gift_dispatches(dispatch_date DESC);

CREATE INDEX idx_promotions_active     ON promotions(is_active);
CREATE INDEX idx_promo_gifts_promo     ON promotion_gifts(promotion_id);
CREATE INDEX idx_order_promos_order    ON order_promotions(order_id);
CREATE INDEX idx_order_promos_promo    ON order_promotions(promotion_id);

CREATE TRIGGER trg_promotions_upd BEFORE UPDATE ON promotions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_rm_sessions_date   ON rm_stock_sessions(stock_date DESC);
CREATE INDEX idx_rm_entries_sess    ON rm_stock_entries(session_id);
CREATE INDEX idx_rm_entries_type    ON rm_stock_entries(entry_type);
CREATE INDEX idx_po_session         ON purchase_orders(session_id);
CREATE INDEX idx_po_status          ON purchase_orders(po_status);
CREATE INDEX idx_po_supplier        ON purchase_orders(supplier_name);
CREATE INDEX idx_rm_sales_session   ON rm_sales(session_id);
CREATE INDEX idx_rm_sales_date      ON rm_sales(sale_date DESC);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_sales_customer    ON sales(customer_id);
CREATE INDEX idx_sales_status      ON sales(order_status);
CREATE INDEX idx_sales_date        ON sales(order_date);
CREATE INDEX idx_production_status ON production(production_status);
CREATE INDEX idx_accounting_pay    ON accounting(payment_status);
CREATE INDEX idx_customers_code    ON customers(customer_code);

-- ============================================================
-- Trigger: auto updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_upd    BEFORE UPDATE ON customers    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_formulas_upd     BEFORE UPDATE ON fertilizer_formulas FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_sales_upd        BEFORE UPDATE ON sales        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_production_upd   BEFORE UPDATE ON production   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_accounting_upd   BEFORE UPDATE ON accounting   FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Trigger: อัปเดต outstanding_balance ของลูกค้า อัตโนมัติ
-- เมื่อ accounting เปลี่ยน payment_status
-- ============================================================
CREATE OR REPLACE FUNCTION sync_customer_outstanding()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE customers c
    SET outstanding_balance = (
        SELECT COALESCE(SUM(a.total_sales_amount - a.paid_amount), 0)
        FROM accounting a
        JOIN sales s ON s.order_id = a.order_id
        WHERE s.customer_id = c.customer_id
          AND a.payment_status IN ('UNPAID','PARTIAL','OVERDUE')
    )
    WHERE customer_id = (
        SELECT customer_id FROM sales WHERE order_id = NEW.order_id
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_outstanding
    AFTER INSERT OR UPDATE ON accounting
    FOR EACH ROW EXECUTE FUNCTION sync_customer_outstanding();

-- ============================================================
-- View: Dashboard รวมทุกตาราง
-- ============================================================
CREATE OR REPLACE VIEW v_order_dashboard AS
SELECT
    s.order_id,
    s.order_date,
    s.delivery_due_date,
    c.customer_code,
    c.company_name      AS customer_name,
    c.credit_limit,
    c.outstanding_balance,
    CASE WHEN c.outstanding_balance >= c.credit_limit THEN TRUE ELSE FALSE END AS credit_exceeded,
    s.salesperson,
    s.sale_support_name,
    s.dept,
    s.total_amount,
    s.order_status,
    s.credit_alert,
    s.approved_by,
    p.production_status,
    p.production_cost_total,
    p.qc_passed,
    p.start_date        AS production_start,
    p.end_date          AS production_end,
    a.payment_status,
    a.gross_profit,
    a.gross_margin_pct,
    a.paid_amount,
    a.due_date
FROM sales s
JOIN customers c           ON c.customer_id = s.customer_id
LEFT JOIN production p     ON p.order_id    = s.order_id
LEFT JOIN accounting a     ON a.order_id    = s.order_id;

-- ============================================================
-- Seed Data ตัวอย่าง
-- ============================================================
INSERT INTO customers (customer_code, company_name, contact_name, phone, credit_term, credit_limit)
VALUES
  ('CUST-001', 'บริษัท เกษตรดี จำกัด',      'สมชาย ใจดี',   '081-111-1111', '30',  500000),
  ('CUST-002', 'ห้างหุ้นส่วน ฟาร์มทอง',       'วิไล ทองใบ',   '082-222-2222', '45',  300000),
  ('CUST-003', 'ร้าน พืชผลไร่นา',             'ประเสริฐ นาดี', '083-333-3333', '60', 1000000);

INSERT INTO fertilizer_formulas (formula_code, formula_name, base_price_per_kg)
VALUES
  ('16-20-0',  'สูตรข้าวนาปี',       12.50),
  ('15-15-15', 'สูตรพืชไร่ทั่วไป',   14.00),
  ('46-0-0',   'ยูเรียบริสุทธิ์',    18.00),
  ('0-0-60',   'โพแทสเซียมคลอไรด์', 22.00);

INSERT INTO formula_bom (formula_id, material_name, qty_per_100kg, unit, cost_per_unit)
VALUES
  (1, 'แอมโมเนียมซัลเฟต',  40, 'kg', 8.00),
  (1, 'ไดแอมโมเนียมฟอสเฟต', 60, 'kg', 9.50),
  (2, 'แอมโมเนียมซัลเฟต',  30, 'kg', 8.00),
  (2, 'ไดแอมโมเนียมฟอสเฟต', 35, 'kg', 9.50),
  (2, 'โพแทสเซียมคลอไรด์', 35, 'kg', 11.00);

INSERT INTO raw_materials (material_name, unit, stock_qty, minimum_qty, cost_per_unit)
VALUES
  ('แอมโมเนียมซัลเฟต',   'kg', 50000, 5000,  8.00),
  ('ไดแอมโมเนียมฟอสเฟต', 'kg', 30000, 3000,  9.50),
  ('โพแทสเซียมคลอไรด์',  'kg', 20000, 2000, 11.00),
  ('ยูเรีย',             'kg', 15000, 1500, 12.00);
