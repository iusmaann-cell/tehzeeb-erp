import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db
from ..security import user_has_action, current_user

router = APIRouter(prefix="/payroll", tags=["Payroll"])


def _compute_payslip(db: Session, employee: models.Employee, period_start, period_end):
    records = db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.employee_id == employee.id,
        models.AttendanceRecord.attendance_date >= period_start,
        models.AttendanceRecord.attendance_date <= period_end,
    ).all()

    days_present = sum(1 for r in records if r.status == models.AttendanceStatus.present)
    days_absent = sum(1 for r in records if r.status == models.AttendanceStatus.absent)
    days_leave = sum(1 for r in records if r.status == models.AttendanceStatus.leave)
    days_half = sum(1 for r in records if r.status == models.AttendanceStatus.half_day)
    overtime_hours = sum(r.overtime_hours or 0 for r in records)

    if employee.employment_type == models.EmploymentType.daily_wage:
        rate = employee.daily_wage_rate or 0.0
        # daily-wage workers are paid for days actually worked — leave/absence unpaid,
        # a half day pays half
        basic_pay = rate * (days_present + 0.5 * days_half)
    else:
        # permanent/contract: full monthly salary, minus a per-day deduction for
        # unpaid absence (leave is paid, a half day counts as half an unpaid absence)
        salary = employee.basic_salary or 0.0
        per_day_rate = salary / 30.0
        unpaid_absence_days = days_absent + 0.5 * days_half
        basic_pay = max(0.0, salary - per_day_rate * unpaid_absence_days)

    overtime_pay = overtime_hours * (employee.overtime_rate_per_hour or 0.0)

    return {
        "days_present": days_present, "days_absent": days_absent,
        "days_leave": days_leave, "days_half": days_half,
        "overtime_hours": overtime_hours, "basic_pay": basic_pay, "overtime_pay": overtime_pay,
    }


@router.post("/runs/", response_model=schemas.PayrollRunOut)
def create_payroll_run(run: schemas.PayrollRunCreate, db: Session = Depends(get_db)):
    """Computes a draft payslip for every active employee from their attendance in
    the period. Still editable (allowances/deductions) until finalized."""
    existing = db.query(models.PayrollRun).filter(models.PayrollRun.run_number == run.run_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Run number already exists")

    db_run = models.PayrollRun(
        run_number=run.run_number, period_start=run.period_start,
        period_end=run.period_end, notes=run.notes,
    )
    db.add(db_run)
    db.flush()

    employees = db.query(models.Employee).filter(models.Employee.is_active == 1).all()
    for emp in employees:
        calc = _compute_payslip(db, emp, run.period_start, run.period_end)
        net_pay = calc["basic_pay"] + calc["overtime_pay"]
        db.add(models.PayslipLine(
            payroll_run_id=db_run.id, employee_id=emp.id,
            allowances=0.0, deductions=0.0, net_pay=net_pay, **calc,
        ))

    db.commit()
    db.refresh(db_run)
    return db_run


@router.get("/runs/", response_model=List[schemas.PayrollRunOut])
def list_payroll_runs(db: Session = Depends(get_db)):
    return db.query(models.PayrollRun).order_by(models.PayrollRun.id.desc()).all()


@router.get("/runs/{run_id}", response_model=schemas.PayrollRunOut)
def get_payroll_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.PayrollRun).filter(models.PayrollRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return run


@router.put("/runs/{run_id}/lines/{line_id}", response_model=schemas.PayslipLineOut)
def update_payslip_line(run_id: int, line_id: int, update: schemas.PayslipLineUpdate, db: Session = Depends(get_db)):
    """Adjust allowances/deductions on a draft payslip before finalizing."""
    line = db.query(models.PayslipLine).filter(
        models.PayslipLine.id == line_id, models.PayslipLine.payroll_run_id == run_id
    ).first()
    if not line:
        raise HTTPException(status_code=404, detail="Payslip line not found")

    run = db.query(models.PayrollRun).filter(models.PayrollRun.id == run_id).first()
    if run.status == models.PayrollRunStatus.finalized:
        raise HTTPException(status_code=400, detail="This payroll run is already finalized and can't be edited")

    data = update.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(line, field, value)
    line.net_pay = line.basic_pay + line.overtime_pay + line.allowances - line.deductions

    db.commit()
    db.refresh(line)
    return line


@router.patch("/runs/{run_id}/finalize", response_model=schemas.PayrollRunOut)
def finalize_payroll_run(run_id: int, db: Session = Depends(get_db)):
    """
    Locks the run and posts salary cost to Expenses — one Expense entry per plant
    (cost center), so it flows straight into Phase 6's P&L without manual re-entry.
    """
    run = db.query(models.PayrollRun).filter(models.PayrollRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status == models.PayrollRunStatus.finalized:
        raise HTTPException(status_code=400, detail="This payroll run is already finalized")

    by_plant = {}
    for line in run.lines:
        line.net_pay = line.basic_pay + line.overtime_pay + line.allowances - line.deductions
        plant_key = line.employee.plant  # may be None (general/admin)
        by_plant[plant_key] = by_plant.get(plant_key, 0.0) + line.net_pay

    period_label = f"{run.period_start.date()} to {run.period_end.date()}"
    for plant_key, total in by_plant.items():
        if total <= 0:
            continue
        db.add(models.Expense(
            category=models.ExpenseCategory.salaries,
            payroll_run_id=run.id,
            plant=plant_key,
            amount=total,
            description=f"Payroll {run.run_number} ({period_label})",
        ))

    run.status = models.PayrollRunStatus.finalized
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------- edit / reopen / delete
def _require_finalized_permission(request: Request):
    if not user_has_action(current_user(request), "manage_finalized_payroll"):
        raise HTTPException(
            status_code=403,
            detail="Your role doesn't include permission to: Reopen or delete finalized payroll runs",
        )


def _posted_expenses(db: Session, run: models.PayrollRun):
    """The salary expenses this run posted when it was finalized. Runs finalized before the
    link existed are found by their description ("Payroll <run no.> (…)")."""
    rows = db.query(models.Expense).filter(
        models.Expense.category == models.ExpenseCategory.salaries,
    ).all()
    prefix = f"Payroll {run.run_number} ("
    return [e for e in rows if e.payroll_run_id == run.id or (e.payroll_run_id is None and (e.description or "").startswith(prefix))]


@router.put("/runs/{run_id}", response_model=schemas.PayrollRunOut)
def update_payroll_run(run_id: int, update: schemas.PayrollRunUpdate, db: Session = Depends(get_db)):
    """Edit a draft run: number, period, notes. Changing the period (or asking to recompute)
    rebuilds each payslip from attendance and adds anyone who became active since."""
    run = db.query(models.PayrollRun).filter(models.PayrollRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status == models.PayrollRunStatus.finalized:
        raise HTTPException(status_code=400, detail="This run is finalized. Reopen it first to edit it.")

    data = update.dict(exclude_unset=True)
    recompute = data.pop("recompute", False)

    if data.get("run_number") and data["run_number"] != run.run_number:
        if db.query(models.PayrollRun).filter(models.PayrollRun.run_number == data["run_number"]).first():
            raise HTTPException(status_code=400, detail="Run number already exists")

    new_start = data.get("period_start", run.period_start)
    new_end = data.get("period_end", run.period_end)
    if new_end < new_start:
        raise HTTPException(status_code=400, detail="Period end can't be before period start")
    if new_start != run.period_start or new_end != run.period_end:
        recompute = True

    for field, value in data.items():
        setattr(run, field, value)

    if recompute:
        by_emp = {l.employee_id: l for l in run.lines}
        for emp in db.query(models.Employee).filter(models.Employee.is_active == 1).all():
            calc = _compute_payslip(db, emp, new_start, new_end)
            line = by_emp.get(emp.id)
            if line is None:
                db.add(models.PayslipLine(payroll_run_id=run.id, employee_id=emp.id, allowances=0.0, deductions=0.0,
                                          net_pay=calc["basic_pay"] + calc["overtime_pay"], **calc))
            else:
                for k, v in calc.items():
                    setattr(line, k, v)
                line.net_pay = line.basic_pay + line.overtime_pay + (line.allowances or 0) - (line.deductions or 0)

    db.commit()
    db.refresh(run)
    return run


@router.patch("/runs/{run_id}/reopen", response_model=schemas.PayrollRunOut)
def reopen_payroll_run(run_id: int, request: Request, db: Session = Depends(get_db)):
    """Turns a finalized run back into a draft and removes the salary expenses it posted, so it
    can be corrected and finalized again (which posts fresh expenses)."""
    _require_finalized_permission(request)
    run = db.query(models.PayrollRun).filter(models.PayrollRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status != models.PayrollRunStatus.finalized:
        raise HTTPException(status_code=400, detail="This run is already a draft")
    for e in _posted_expenses(db, run):
        db.delete(e)
    run.status = models.PayrollRunStatus.draft
    db.commit()
    db.refresh(run)
    return run


@router.delete("/runs/{run_id}")
def delete_payroll_run(run_id: int, request: Request, db: Session = Depends(get_db)):
    """Deletes a run and its payslips. A finalized run also needs the 'finalized payroll'
    permission, and its posted salary expenses are removed too so reports stay correct."""
    run = db.query(models.PayrollRun).filter(models.PayrollRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    removed = 0
    if run.status == models.PayrollRunStatus.finalized:
        _require_finalized_permission(request)
        for e in _posted_expenses(db, run):
            db.delete(e)
            removed += 1
    db.delete(run)
    db.commit()
    return {"message": "Payroll run deleted", "run_id": run_id, "expenses_removed": removed}
