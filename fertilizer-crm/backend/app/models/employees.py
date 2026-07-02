import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, func
from app.core.database import Base


class RoleEnum(str, enum.Enum):
    SALE = "SALE"
    SALE_SUPPORT = "SALE_SUPPORT"
    WAREHOUSE = "WAREHOUSE"
    PRODUCTION = "PRODUCTION"
    ADMIN = "ADMIN"


class Employee(Base):
    __tablename__ = "employees"

    employee_id   = Column(Integer, primary_key=True, autoincrement=True)
    employee_code = Column(String(20), unique=True, nullable=False)
    full_name     = Column(String(100), nullable=False)
    role          = Column(Enum(RoleEnum, name="employee_role"), nullable=False)
    phone         = Column(String(20))
    email         = Column(String(100))
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now())
