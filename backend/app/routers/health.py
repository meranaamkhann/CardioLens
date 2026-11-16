from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import audit
from ..core.deps import require
from ..db.base import get_db
from ..db.models import Diagnosis, DietPlan, HealthAlert, LabCheckup, Medication, User
from ..health import interactions, service
from ..health.biomarkers import catalogue_for
from ..schemas import DiagnosisCreate, DietPlanCreate, InteractionCheck, LabCheckupCreate, MedicationCreate, MedicationUpdate
from .clinician import clinic_patient
from .patient import UNITS


@dataclass
class Context:
    patient: User
    actor: User
    source: str


def patient_context(user: User = Depends(require("patient"))) -> Context:
    return Context(user, user, "patient")


def clinic_context(patient_id: int, user: User = Depends(require("clinician")), db: Session = Depends(get_db)) -> Context:
    return Context(clinic_patient(db, user, patient_id), user, "clinician")


def may_delete(ctx: Context, row) -> bool:
    if row.created_by == ctx.actor.id:
        return True
    return ctx.source == "patient" and row.source == "patient"


def medication_out(m: Medication) -> dict:
    return {"id": m.id, "name": m.name, "dose": m.dose, "frequency": m.frequency, "reason": m.reason,
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None, "is_active": m.is_active, "source": m.source}


def diagnosis_out(d: Diagnosis) -> dict:
    return {"id": d.id, "icd10": d.icd10, "description": d.description, "severity": d.severity, "status": d.status,
            "diagnosed_on": d.diagnosed_on.isoformat() if d.diagnosed_on else None, "source": d.source}


def diet_out(d: DietPlan) -> dict:
    return {"id": d.id, "name": d.name, "diet_type": d.diet_type, "calories": d.calories, "protein_g": d.protein_g,
            "carbs_g": d.carbs_g, "fat_g": d.fat_g, "restrictions": d.restrictions or [],
            "start_date": d.start_date.isoformat() if d.start_date else None,
            "end_date": d.end_date.isoformat() if d.end_date else None, "notes": d.notes, "source": d.source}


def build(prefix: str, resolver: Callable, tag: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("/biomarkers")
    def biomarkers(ctx: Context = Depends(resolver)):
        return catalogue_for(service.sex_of(ctx.patient))

    @router.post("/checkups", status_code=201)
    def add_checkup(payload: LabCheckupCreate, request: Request, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = service.create_checkup(db, ctx.patient, ctx.actor, ctx.source, payload.checkup_date, payload.values, payload.notes)
        audit.record(db, ctx.actor, "checkup_created", "checkup", row.id, request, {"patient_id": ctx.patient.id})
        db.commit()
        return service.checkup_out(row, service.sex_of(ctx.patient))

    @router.get("/checkups")
    def list_checkups(request: Request, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        rows = db.scalars(select(LabCheckup).where(LabCheckup.patient_id == ctx.patient.id)
                          .order_by(LabCheckup.checkup_date.desc(), LabCheckup.id.desc()).limit(500)).all()
        if ctx.source == "clinician":
            audit.record(db, ctx.actor, "patient_health_viewed", "patient", ctx.patient.id, request)
            db.commit()
        sex = service.sex_of(ctx.patient)
        return [service.checkup_out(r, sex) for r in rows]

    @router.delete("/checkups/{checkup_id}", status_code=204)
    def delete_checkup(checkup_id: int, request: Request, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = db.scalar(select(LabCheckup).where(LabCheckup.id == checkup_id, LabCheckup.patient_id == ctx.patient.id))
        if row is None:
            raise HTTPException(404, "Check-up not found")
        if not may_delete(ctx, row):
            raise HTTPException(403, "Only the person who entered this check-up can delete it.")
        service.delete_checkup(db, ctx.patient, row)
        audit.record(db, ctx.actor, "checkup_deleted", "checkup", checkup_id, request)
        db.commit()

    @router.get("/trends")
    def trends(keys: Optional[str] = Query(default=None, max_length=600), ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        wanted = [k.strip() for k in keys.split(",") if k.strip()] if keys else None
        return service.trend_report(db, ctx.patient, wanted)

    @router.get("/alerts")
    def alerts(include: str = Query(default="open", pattern="^(open|all)$"), ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        query = select(HealthAlert).where(HealthAlert.patient_id == ctx.patient.id)
        if include == "open":
            query = query.where(HealthAlert.resolved_at.is_(None))
        rows = db.scalars(query.order_by(HealthAlert.created_at.desc()).limit(200)).all()
        order = {"critical": 0, "warning": 1, "info": 2}
        return sorted((service.alert_out(a) for a in rows), key=lambda a: (a["resolved"], a["acknowledged"], order[a["severity"]]))

    @router.post("/alerts/{alert_id}/acknowledge")
    def acknowledge(alert_id: int, request: Request, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = db.scalar(select(HealthAlert).where(HealthAlert.id == alert_id, HealthAlert.patient_id == ctx.patient.id))
        if row is None:
            raise HTTPException(404, "Alert not found")
        row.acknowledged_by, row.acknowledged_at = ctx.actor.id, service.now()
        audit.record(db, ctx.actor, "alert_acknowledged", "alert", alert_id, request)
        db.commit()
        return service.alert_out(row)

    @router.get("/reminders")
    def reminders(ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        return service.overdue_info(db, ctx.patient)

    @router.get("/summary")
    def summary(ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        return service.health_summary(db, ctx.patient)

    @router.get("/medications")
    def list_medications(ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        rows = db.scalars(select(Medication).where(Medication.patient_id == ctx.patient.id).order_by(Medication.is_active.desc(), Medication.created_at.desc())).all()
        names = [m.name for m in rows if m.is_active]
        return {"medications": [medication_out(m) for m in rows],
                "interactions": interactions.check(names) if len(names) > 1 else {"interactions": [], "not_covered": [], "note": interactions.check(["a", "b"])["note"]}}

    @router.post("/medications", status_code=201)
    def add_medication(payload: MedicationCreate, request: Request, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
            raise HTTPException(422, "The end date cannot be before the start date.")
        row = Medication(patient_id=ctx.patient.id, name=payload.name.strip(), dose=payload.dose, frequency=payload.frequency,
                         reason=payload.reason, start_date=payload.start_date, end_date=payload.end_date,
                         is_active=not (payload.end_date and payload.end_date < date.today()), source=ctx.source, created_by=ctx.actor.id)
        db.add(row)
        db.flush()
        audit.record(db, ctx.actor, "medication_added", "medication", row.id, request, {"patient_id": ctx.patient.id})
        db.commit()
        return medication_out(row)

    @router.patch("/medications/{medication_id}")
    def update_medication(medication_id: int, payload: MedicationUpdate, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = db.scalar(select(Medication).where(Medication.id == medication_id, Medication.patient_id == ctx.patient.id))
        if row is None:
            raise HTTPException(404, "Medication not found")
        row.is_active = payload.is_active
        row.end_date = None if payload.is_active else (payload.end_date or date.today())
        db.commit()
        return medication_out(row)

    @router.delete("/medications/{medication_id}", status_code=204)
    def delete_medication(medication_id: int, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = db.scalar(select(Medication).where(Medication.id == medication_id, Medication.patient_id == ctx.patient.id))
        if row is None:
            raise HTTPException(404, "Medication not found")
        if not may_delete(ctx, row):
            raise HTTPException(403, "Only the person who added this medication can delete it.")
        db.delete(row)
        db.commit()

    @router.post("/interactions/check")
    def check_interactions(payload: InteractionCheck, ctx: Context = Depends(resolver)):
        return interactions.check(payload.medicines)

    @router.get("/diagnoses")
    def list_diagnoses(ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        rows = db.scalars(select(Diagnosis).where(Diagnosis.patient_id == ctx.patient.id).order_by(Diagnosis.created_at.desc())).all()
        return [diagnosis_out(d) for d in rows]

    @router.post("/diagnoses", status_code=201)
    def add_diagnosis(payload: DiagnosisCreate, request: Request, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = Diagnosis(patient_id=ctx.patient.id, icd10=payload.icd10.upper(), description=payload.description.strip(), severity=payload.severity,
                        status=payload.status, diagnosed_on=payload.diagnosed_on, source=ctx.source, created_by=ctx.actor.id)
        db.add(row)
        db.flush()
        audit.record(db, ctx.actor, "diagnosis_added", "diagnosis", row.id, request, {"patient_id": ctx.patient.id})
        db.commit()
        return diagnosis_out(row)

    @router.delete("/diagnoses/{diagnosis_id}", status_code=204)
    def delete_diagnosis(diagnosis_id: int, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = db.scalar(select(Diagnosis).where(Diagnosis.id == diagnosis_id, Diagnosis.patient_id == ctx.patient.id))
        if row is None:
            raise HTTPException(404, "Diagnosis not found")
        if not may_delete(ctx, row):
            raise HTTPException(403, "Only the person who added this diagnosis can delete it.")
        db.delete(row)
        db.commit()

    @router.get("/diet-plans")
    def list_diets(ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        rows = db.scalars(select(DietPlan).where(DietPlan.patient_id == ctx.patient.id).order_by(DietPlan.created_at.desc())).all()
        return [diet_out(d) for d in rows]

    @router.post("/diet-plans", status_code=201)
    def add_diet(payload: DietPlanCreate, request: Request, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = DietPlan(patient_id=ctx.patient.id, name=payload.name.strip(), diet_type=payload.diet_type, calories=payload.calories,
                       protein_g=payload.protein_g, carbs_g=payload.carbs_g, fat_g=payload.fat_g,
                       restrictions=[r.strip() for r in payload.restrictions if r.strip()], start_date=payload.start_date,
                       end_date=payload.end_date, notes=payload.notes, source=ctx.source, created_by=ctx.actor.id)
        db.add(row)
        db.flush()
        audit.record(db, ctx.actor, "diet_plan_added", "diet_plan", row.id, request, {"patient_id": ctx.patient.id})
        db.commit()
        return diet_out(row)

    @router.delete("/diet-plans/{plan_id}", status_code=204)
    def delete_diet(plan_id: int, ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        row = db.scalar(select(DietPlan).where(DietPlan.id == plan_id, DietPlan.patient_id == ctx.patient.id))
        if row is None:
            raise HTTPException(404, "Diet plan not found")
        if not may_delete(ctx, row):
            raise HTTPException(403, "Only the person who added this plan can delete it.")
        db.delete(row)
        db.commit()

    @router.get("/import/template", response_class=Response)
    def csv_template(ctx: Context = Depends(resolver)):
        return Response(service.template_csv(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="checkups-template.csv"'})

    @router.post("/import/checkups-csv", status_code=201)
    async def import_csv(request: Request, file: UploadFile = File(...), ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        raw = await file.read(service.MAX_CSV_BYTES + 1)
        rows = service.parse_csv(raw)
        created = [service.create_checkup(db, ctx.patient, ctx.actor, ctx.source, r["date"], r["values"], None) for r in rows]
        audit.record(db, ctx.actor, "checkups_imported", "patient", ctx.patient.id, request, {"rows": len(created)})
        db.commit()
        return {"imported": len(created)}

    @router.get("/export/checkups.csv")
    def export_csv(ctx: Context = Depends(resolver), db: Session = Depends(get_db)):
        rows = db.scalars(select(LabCheckup).where(LabCheckup.patient_id == ctx.patient.id)).all()
        return Response(service.export_csv(rows), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="checkups.csv"'})

    return router


patient_router = build("/me/health", patient_context, "patient-health")
clinic_router = build("/clinic/patients/{patient_id}/health", clinic_context, "clinic-health")
overview_router = APIRouter(prefix="/clinic/health", tags=["clinic-health"])


@overview_router.get("/alerts")
def clinic_alerts(user: User = Depends(require("clinician")), db: Session = Depends(get_db)):
    rows = db.execute(select(HealthAlert, User).join(User, HealthAlert.patient_id == User.id)
                      .where(User.clinic_id == user.clinic_id, HealthAlert.resolved_at.is_(None), HealthAlert.acknowledged_at.is_(None))
                      .order_by(HealthAlert.created_at.desc()).limit(300)).all()
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted((service.alert_out(a, p.full_name) for a, p in rows), key=lambda a: order[a["severity"]])


@overview_router.get("/overdue")
def clinic_overdue(user: User = Depends(require("clinician")), db: Session = Depends(get_db)):
    patients = db.scalars(select(User).where(User.clinic_id == user.clinic_id, User.role == "patient", User.is_active.is_(True))).all()
    out = []
    for p in patients:
        info = service.overdue_info(db, p)
        if info["overdue"]:
            out.append({"patient_id": p.id, "patient_name": p.full_name, **info})
    return sorted(out, key=lambda r: -(r["days_since"] if r["days_since"] is not None else 10_000))
