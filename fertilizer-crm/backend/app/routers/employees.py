from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.employees import Employee, RoleEnum

router = APIRouter(prefix="/api/employees", tags=["employees"])


class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    role: RoleEnum
    phone: Optional[str] = None
    email: Optional[str] = None


def _emp_dict(e):
    return {
        "employee_id": e.employee_id,
        "employee_code": e.employee_code,
        "full_name": e.full_name,
        "role": e.role,
        "phone": e.phone,
        "email": e.email,
        "is_active": e.is_active,
    }


@router.get("")
def list_employees(role: str = None, active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(Employee)
    if active_only:
        q = q.filter_by(is_active=True)
    if role:
        q = q.filter(Employee.role == role.upper())
    return [_emp_dict(e) for e in q.order_by(Employee.role, Employee.full_name).all()]


@router.post("", status_code=201)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    if db.query(Employee).filter_by(employee_code=payload.employee_code).first():
        raise HTTPException(400, f"รหัสพนักงาน {payload.employee_code} มีอยู่แล้ว")
    emp = Employee(**payload.model_dump())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return _emp_dict(emp)
