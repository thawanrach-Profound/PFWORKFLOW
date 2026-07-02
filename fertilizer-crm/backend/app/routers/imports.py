"""
Import routes — รับไฟล์ Excel แล้ว bulk-insert เข้าฐานข้อมูล
รองรับ 3 ประเภท:
  POST /api/import/products   — สินค้า/สูตรปุ๋ย + BOM
  POST /api/import/employees  — พนักงาน
  POST /api/import/customers  — ลูกค้า
  GET  /api/import/template/{type} — ดาวน์โหลด template Excel
"""
import io
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crm import FertilizerFormula, FormulaBOM, Customer, CreditTerm
from app.models.employees import Employee, RoleEnum

router = APIRouter(prefix="/api/import", tags=["import"])


# ──────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────
def _read_excel(file: UploadFile) -> pd.DataFrame:
    content = file.file.read()
    try:
        return pd.read_excel(io.BytesIO(content), dtype=str).fillna("")
    except Exception as e:
        raise HTTPException(400, f"อ่านไฟล์ Excel ไม่ได้: {e}")


def _excel_response(df: pd.DataFrame, filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ──────────────────────────────────────────────────────────────
# TEMPLATE DOWNLOAD
# ──────────────────────────────────────────────────────────────
@router.get("/template/{type}")
def download_template(type: Literal["products", "employees", "customers"]):
    if type == "products":
        df = pd.DataFrame(columns=[
            "formula_code", "formula_name", "base_price_per_kg", "description",
            "material_name", "qty_per_100kg", "unit", "cost_per_unit",
        ])
        df.loc[0] = ["16-20-0", "สูตรข้าวนาปี", "12.50", "สูตรมาตรฐาน",
                     "แอมโมเนียมซัลเฟต", "40", "kg", "8.00"]
        df.loc[1] = ["16-20-0", "", "", "", "ไดแอมโมเนียมฟอสเฟต", "60", "kg", "9.50"]
        return _excel_response(df, "template_products.xlsx")

    if type == "employees":
        df = pd.DataFrame(columns=[
            "employee_code", "full_name", "role", "phone", "email", "is_active",
        ])
        df.loc[0] = ["EMP-001", "สมชาย ใจดี", "SALE", "081-111-1111", "somchai@example.com", "TRUE"]
        df.loc[1] = ["EMP-002", "วิไล ทองใบ", "SALE_SUPPORT", "082-222-2222", "", "TRUE"]
        note = pd.DataFrame([{"NOTE": "role ที่ใช้ได้: SALE, SALE_SUPPORT, WAREHOUSE, PRODUCTION, ADMIN"}])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="employees")
            note.to_excel(w, index=False, sheet_name="คำอธิบาย")
        buf.seek(0)
        return StreamingResponse(buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=template_employees.xlsx"})

    if type == "customers":
        df = pd.DataFrame(columns=[
            "customer_code", "company_name", "contact_name", "phone",
            "address", "credit_term", "credit_limit", "notes",
        ])
        df.loc[0] = ["CUST-010", "บริษัท เกษตรดี จำกัด", "สมชาย ใจดี",
                     "081-111-1111", "123 ถ.พหลโยธิน กรุงเทพ", "30", "500000", ""]
        note = pd.DataFrame([{"NOTE": "credit_term ที่ใช้ได้: 30, 45, 60, 90, 120, OTHER"}])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="customers")
            note.to_excel(w, index=False, sheet_name="คำอธิบาย")
        buf.seek(0)
        return StreamingResponse(buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=template_customers.xlsx"})


# ──────────────────────────────────────────────────────────────
# IMPORT PRODUCTS (สูตรปุ๋ย + BOM)
# ──────────────────────────────────────────────────────────────
@router.post("/products")
async def import_products(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    คอลัมน์ที่ต้องมี:
      formula_code, formula_name, base_price_per_kg, description (optional)
      material_name, qty_per_100kg, unit, cost_per_unit
    หลายแถวที่มี formula_code เดียวกัน = BOM หลายรายการของสูตรเดียว
    """
    df = _read_excel(file)
    required = {"formula_code", "formula_name", "material_name", "qty_per_100kg"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"คอลัมน์ที่ขาด: {', '.join(missing)}")

    created, updated, skipped = 0, 0, 0
    errors = []
    formula_map: dict[str, FertilizerFormula] = {}

    for i, row in df.iterrows():
        code = row.get("formula_code", "").strip()
        if not code:
            continue
        try:
            if code not in formula_map:
                f = db.query(FertilizerFormula).filter_by(formula_code=code).first()
                if not f:
                    f = FertilizerFormula(
                        formula_code=code,
                        formula_name=row.get("formula_name", code).strip(),
                        base_price_per_kg=float(row.get("base_price_per_kg") or 0),
                        description=row.get("description", "").strip() or None,
                    )
                    db.add(f)
                    db.flush()
                    created += 1
                else:
                    # อัปเดตชื่อ/ราคาถ้ามีการระบุมา
                    if row.get("formula_name"):
                        f.formula_name = row["formula_name"].strip()
                    if row.get("base_price_per_kg"):
                        f.base_price_per_kg = float(row["base_price_per_kg"])
                    updated += 1
                formula_map[code] = f

            f = formula_map[code]
            mat = row.get("material_name", "").strip()
            if mat:
                exists = db.query(FormulaBOM).filter_by(
                    formula_id=f.formula_id, material_name=mat
                ).first()
                if not exists:
                    db.add(FormulaBOM(
                        formula_id=f.formula_id,
                        material_name=mat,
                        qty_per_100kg=float(row.get("qty_per_100kg") or 0),
                        unit=row.get("unit", "kg").strip() or "kg",
                        cost_per_unit=float(row.get("cost_per_unit") or 0),
                    ))
        except Exception as e:
            errors.append(f"แถว {i+2}: {e}")

    db.commit()
    return {
        "success": True,
        "created_formulas": created,
        "updated_formulas": updated,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────
# IMPORT EMPLOYEES
# ──────────────────────────────────────────────────────────────
@router.post("/employees")
async def import_employees(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    คอลัมน์ที่ต้องมี: employee_code, full_name, role
    role: SALE | SALE_SUPPORT | WAREHOUSE | PRODUCTION | ADMIN
    """
    df = _read_excel(file)
    required = {"employee_code", "full_name", "role"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"คอลัมน์ที่ขาด: {', '.join(missing)}")

    valid_roles = {r.value for r in RoleEnum}
    created, updated, errors = 0, 0, []

    for i, row in df.iterrows():
        code = row.get("employee_code", "").strip()
        name = row.get("full_name", "").strip()
        role = row.get("role", "").strip().upper()
        if not code or not name:
            continue
        if role not in valid_roles:
            errors.append(f"แถว {i+2}: role '{role}' ไม่ถูกต้อง (ใช้ได้: {', '.join(valid_roles)})")
            continue
        try:
            emp = db.query(Employee).filter_by(employee_code=code).first()
            if emp:
                emp.full_name = name
                emp.role = role
                emp.phone = row.get("phone", "").strip() or emp.phone
                emp.email = row.get("email", "").strip() or emp.email
                is_active = row.get("is_active", "TRUE").strip().upper()
                emp.is_active = is_active != "FALSE"
                updated += 1
            else:
                is_active = row.get("is_active", "TRUE").strip().upper()
                db.add(Employee(
                    employee_code=code,
                    full_name=name,
                    role=role,
                    phone=row.get("phone", "").strip() or None,
                    email=row.get("email", "").strip() or None,
                    is_active=is_active != "FALSE",
                ))
                created += 1
        except Exception as e:
            errors.append(f"แถว {i+2}: {e}")

    db.commit()
    return {"success": True, "created": created, "updated": updated, "errors": errors}


# ──────────────────────────────────────────────────────────────
# IMPORT CUSTOMERS
# ──────────────────────────────────────────────────────────────
@router.post("/customers")
async def import_customers(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    คอลัมน์ที่ต้องมี: customer_code, company_name
    credit_term: 30 | 45 | 60 | 90 | 120 | OTHER
    """
    df = _read_excel(file)
    required = {"customer_code", "company_name"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"คอลัมน์ที่ขาด: {', '.join(missing)}")

    valid_terms = {t.value for t in CreditTerm}
    created, updated, errors = 0, 0, []

    for i, row in df.iterrows():
        code = row.get("customer_code", "").strip()
        name = row.get("company_name", "").strip()
        if not code or not name:
            continue

        term_raw = row.get("credit_term", "30").strip()
        if term_raw not in valid_terms:
            term_raw = "30"

        try:
            cust = db.query(Customer).filter_by(customer_code=code).first()
            if cust:
                cust.company_name = name
                cust.contact_name = row.get("contact_name", "").strip() or cust.contact_name
                cust.phone = row.get("phone", "").strip() or cust.phone
                cust.address = row.get("address", "").strip() or cust.address
                cust.credit_term = term_raw
                if row.get("credit_limit"):
                    cust.credit_limit = float(row["credit_limit"])
                cust.notes = row.get("notes", "").strip() or cust.notes
                updated += 1
            else:
                db.add(Customer(
                    customer_code=code,
                    company_name=name,
                    contact_name=row.get("contact_name", "").strip() or None,
                    phone=row.get("phone", "").strip() or None,
                    address=row.get("address", "").strip() or None,
                    credit_term=term_raw,
                    credit_limit=float(row.get("credit_limit") or 0),
                    notes=row.get("notes", "").strip() or None,
                ))
                created += 1
        except Exception as e:
            errors.append(f"แถว {i+2}: {e}")

    db.commit()
    return {"success": True, "created": created, "updated": updated, "errors": errors}
