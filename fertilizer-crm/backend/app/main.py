import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine
from app.routers import customers, formulas, orders, production, inventory, reports, imports, employees, bag_stock, rm_stock, promotions

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        logger.warning(f"DB init skipped: {e}")
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


@app.get("/")
def health():
    return {"status": "ok", "system": "Fertilizer CRM"}


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
