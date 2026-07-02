from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.routers import customers, formulas, orders, production, inventory, reports, imports, employees, bag_stock, rm_stock, promotions


@asynccontextmanager
async def lifespan(app: FastAPI):
    # สร้าง tables อัตโนมัติถ้ายังไม่มี (Railway fresh deploy)
    Base.metadata.create_all(bind=engine)
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
