from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from app.schemas.common import Number


PayrollStatus = Literal["open", "processed", "paid"]


class PayrollPeriodCreate(BaseModel):
    period_name: str = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date
    pay_date: date | None = None


class PayrollPeriodUpdate(BaseModel):
    period_name: str | None = Field(None, min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    pay_date: date | None = None
    status: PayrollStatus | None = None


class PayrollPeriodOut(BaseModel):
    period_id: int
    period_name: str
    start_date: date
    end_date: date
    pay_date: date | None
    status: str


class PayslipOut(BaseModel):
    payslip_id: int
    employee_id: int
    employee_no: str
    employee_name: str
    department: str
    period_id: int
    period_name: str
    days_paid: float
    overtime_hours: float
    basic_pay: Number
    overtime_pay: Number
    gross_pay: Number
    total_deductions: Number
    net_pay: Number
    generated_at: date


class DeductionTypeOut(BaseModel):
    deduction_type_id: int
    name: str
    calc_method: str
    rate: Number
    max_amount: Number | None
    is_active: bool


class GeneratePayrollRequest(BaseModel):
    period_id: int


class DeductionTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    calc_method: Literal["percent", "fixed"]
    rate: Decimal = Field(ge=0, max_digits=10, decimal_places=4)
    max_amount: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    is_active: bool = True


class DeductionTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    calc_method: Literal["percent", "fixed"] | None = None
    rate: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=4)
    max_amount: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    is_active: bool | None = None