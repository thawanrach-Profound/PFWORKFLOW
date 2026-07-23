import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine
from app.routers import customers, formulas, orders, production, inventory, reports, imports, employees, bag_stock, rm_stock, promotions, shops

logger = logging.getLogger("crm.startup")


def init_db():
    """Run schema.sql on first deploy — idempotent (CREATE IF NOT EXISTS)."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    if not os.path.exists(schema_path):
        logger.warning("schema.sql not found — skipping DB init")
        return
    sql = open(schema_path).read()
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    logger.info("DB schema initialized")


MIGRATIONS = [
    # 2026-07: add shop_name and region to gift_dispatches
    "ALTER TABLE gift_dispatches ADD COLUMN IF NOT EXISTS shop_name VARCHAR(200)",
    "ALTER TABLE gift_dispatches ADD COLUMN IF NOT EXISTS region VARCHAR(50)",
    # 2026-07: add qty_per_ton to promotion_gifts
    "ALTER TABLE promotion_gifts ADD COLUMN IF NOT EXISTS qty_per_ton NUMERIC(10,2) DEFAULT 0",
    # 2026-07: add product_filter and multiplier to promotions
    "ALTER TABLE promotions ADD COLUMN IF NOT EXISTS product_filter TEXT",
    "ALTER TABLE promotions ADD COLUMN IF NOT EXISTS multiplier NUMERIC(10,2) DEFAULT 0",
    # 2026-07: create promo_shops table
    """CREATE TABLE IF NOT EXISTS promo_shops (
        shop_id         SERIAL          PRIMARY KEY,
        promotion_id    INT             NOT NULL REFERENCES promotions(promotion_id) ON DELETE CASCADE,
        shop_name       VARCHAR(200)    NOT NULL,
        region          VARCHAR(50),
        qty_ton         NUMERIC(12,2)   NOT NULL DEFAULT 0,
        qty_allocated   NUMERIC(12,2)   NOT NULL DEFAULT 0,
        qty_dispatched  NUMERIC(12,2)   NOT NULL DEFAULT 0,
        notes           TEXT,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_promo_shops_promo ON promo_shops(promotion_id)",
    # 2026-07: add promo_shop_id and gift_id FK to gift_dispatches
    "ALTER TABLE gift_dispatches ADD COLUMN IF NOT EXISTS promo_shop_id INT REFERENCES promo_shops(shop_id) ON DELETE SET NULL",
    "ALTER TABLE gift_dispatches ADD COLUMN IF NOT EXISTS gift_id INT REFERENCES promotion_gifts(gift_id) ON DELETE SET NULL",
    # 2026-07: make op_id nullable in gift_dispatches
    "ALTER TABLE gift_dispatches ALTER COLUMN op_id DROP NOT NULL",
    # 2026-07: shop_master table
    """CREATE TABLE IF NOT EXISTS shop_master (
        shop_id       SERIAL          PRIMARY KEY,
        shop_name     VARCHAR(200)    NOT NULL,
        region        VARCHAR(50),
        zone          VARCHAR(50),
        employee_name VARCHAR(100),
        phone         VARCHAR(20),
        is_active     BOOLEAN         NOT NULL DEFAULT TRUE,
        created_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
        updated_at    TIMESTAMPTZ     NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_shop_master_region ON shop_master(region)",
    # 2026-07: gift dead stock + image
    "ALTER TABLE promotion_gifts ADD COLUMN IF NOT EXISTS dead_stock_qty NUMERIC(12,2) DEFAULT 0",
    "ALTER TABLE promotion_gifts ADD COLUMN IF NOT EXISTS gift_image_url TEXT",
    # 2026-07: dispatch type for trip withdrawal
    "ALTER TABLE gift_dispatches ADD COLUMN IF NOT EXISTS dispatch_type VARCHAR(30) DEFAULT 'dispatch'",
    "ALTER TABLE gift_dispatches ADD COLUMN IF NOT EXISTS salesperson_name VARCHAR(100)",
    # 2026-07: team responsible for each gift
    "ALTER TABLE promotion_gifts ADD COLUMN IF NOT EXISTS team VARCHAR(100)",
]

def run_migrations():
    """Run incremental ALTER TABLE migrations — safe to run multiple times."""
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
                logger.info(f"Migration OK: {sql[:60]}")
            except Exception as e:
                logger.warning(f"Migration skip: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        logger.error(f"DB init failed: {e}")
    try:
        run_migrations()
    except Exception as e:
        logger.error(f"Migrations failed: {e}")
    yield


app = FastAPI(
    title="Fertilizer CRM API",
    description="ระบบบริหารจัดการบริษัทขายปุ๋ย — Phase 1",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(formulas.router)
app.include_router(orders.router)
app.include_router(production.router)
app.include_router(inventory.router)
app.include_router(reports.router)
app.include_router(imports.router)
app.include_router(employees.router)
app.include_router(bag_stock.router)
app.include_router(rm_stock.router)
app.include_router(promotions.router)
app.include_router(shops.router)


@app.get("/")
def health():
    return {"status": "ok", "system": "Fertilizer CRM"}


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/init-db")
def run_init_db():
    try:
        init_db()
        return {"status": "ok", "message": "DB schema initialized"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/run-migrations")
def trigger_migrations():
    try:
        run_migrations()
        return {"status": "ok", "message": "Migrations applied"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
