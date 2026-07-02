from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crm import FertilizerFormula, FormulaBOM
from app.schemas.crm import FormulaCreate, FormulaOut, BOMItemCreate, BOMItemOut

router = APIRouter(prefix="/api/formulas", tags=["formulas"])


@router.post("", response_model=FormulaOut, status_code=201)
def create_formula(payload: FormulaCreate, db: Session = Depends(get_db)):
    f = FertilizerFormula(
        formula_code=payload.formula_code,
        formula_name=payload.formula_name,
        description=payload.description,
        base_price_per_kg=payload.base_price_per_kg,
    )
    db.add(f); db.flush()
    for item in payload.bom_items:
        db.add(FormulaBOM(formula_id=f.formula_id, **item.model_dump()))
    db.commit(); db.refresh(f)
    return f


@router.get("", response_model=list[FormulaOut])
def list_formulas(db: Session = Depends(get_db)):
    return db.query(FertilizerFormula).filter_by(is_active=True).order_by(FertilizerFormula.formula_code).all()


@router.get("/{formula_id}", response_model=FormulaOut)
def get_formula(formula_id: int, db: Session = Depends(get_db)):
    f = db.get(FertilizerFormula, formula_id)
    if not f:
        raise HTTPException(404, "ไม่พบสูตรปุ๋ย")
    return f


@router.put("/{formula_id}/bom", response_model=FormulaOut)
def replace_bom(formula_id: int, items: list[BOMItemCreate], db: Session = Depends(get_db)):
    """แทนที่ BOM template ทั้งหมดของสูตรนี้ (ปรับสูตรได้)"""
    f = db.get(FertilizerFormula, formula_id)
    if not f:
        raise HTTPException(404, "ไม่พบสูตรปุ๋ย")
    db.query(FormulaBOM).filter_by(formula_id=formula_id).delete()
    for item in items:
        db.add(FormulaBOM(formula_id=formula_id, **item.model_dump()))
    db.commit(); db.refresh(f)
    return f
