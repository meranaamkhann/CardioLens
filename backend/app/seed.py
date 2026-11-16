import sys
from datetime import date, datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select

from .config import get_settings
from .core.security import hash_password
from .db.base import Base, SessionLocal, engine
from .db.models import Appointment, Assessment, Clinic, Diagnosis, DietPlan, Measurement, Medication, PatientProfile, User
from .engine import Engine
from .schemas import SymptomAssessment
from .health import service as health
from .services import assessments as svc

PASSWORD = "DemoPass123"
CODE = "DEMO01"


def build_user(db, email, name, role, clinic, profile=None):
    user = User(email=email, password_hash=hash_password(PASSWORD), full_name=name, role=role, clinic_id=clinic.id)
    if profile:
        user.profile = PatientProfile(**profile)
    db.add(user)
    db.flush()
    return user


def seed_health(db, patient, clinician, index, rng):
    today = date.today()
    for step in range(5):
        when = today - timedelta(days=300 - step * 70)
        values = {
            "hemoglobin": round(float(14.2 + rng.normal(0, 0.25)), 1), "glucose_fasting": round(float(92 + index * 14 + step * 2 + rng.normal(0, 3)), 0),
            "ldl": round(float(78 + index * 22 + step * 6 + rng.normal(0, 2)), 0), "hdl": round(float(52 - index * 4 + rng.normal(0, 1.5)), 0),
            "total_cholesterol": round(float(165 + index * 25 + step * 5), 0), "bp_systolic": round(float(122 + index * 6 + step * 2)), "bp_diastolic": round(float(78 + index * 2)),
        }
        health.create_checkup(db, patient, clinician, "clinician", when, values, None)
    medicines = [[("Atorvastatin", "20 mg", "once daily", "Cholesterol")], [("Metformin", "500 mg", "twice daily", "Blood sugar")],
                 [("Coumadin", "5 mg", "once daily", "Anticoagulation"), ("Brufen", "400 mg", "when needed", "Joint pain")]][index]
    for name, dose, frequency, reason in medicines:
        db.add(Medication(patient_id=patient.id, name=name, dose=dose, frequency=frequency, reason=reason, source="clinician", created_by=clinician.id))
    codes = [("I10", "Essential hypertension"), ("E11.9", "Type 2 diabetes mellitus without complications"), ("I48.91", "Atrial fibrillation, unspecified")][index]
    db.add(Diagnosis(patient_id=patient.id, icd10=codes[0], description=codes[1], severity="mild", status="active", source="clinician", created_by=clinician.id))
    db.add(DietPlan(patient_id=patient.id, name="Heart-healthy plan", diet_type="Mediterranean", calories=1900, restrictions=["low salt", "limit fried food"],
                    source="clinician", created_by=clinician.id))


def seed():
    settings = get_settings()
    if settings.environment == "production":
        sys.exit("Demo data must not be seeded in production.")
    if settings.is_sqlite:
        Base.metadata.create_all(engine)
    rng = np.random.default_rng(42)
    with SessionLocal() as db:
        if db.scalar(select(Clinic).where(Clinic.code == CODE)):
            print("Demo data already present.")
            return
        clinic = Clinic(name="CardioLens Demo Clinic (synthetic data)", code=CODE)
        db.add(clinic)
        db.flush()
        build_user(db, "admin@demo.cardiolens.test", "Dana Admin", "clinic_admin", clinic)
        clinician = build_user(db, "clinician@demo.cardiolens.test", "Dr. Rao", "clinician", clinic)
        build_user(db, "researcher@demo.cardiolens.test", "Riya Researcher", "researcher", clinic)
        engine_ = Engine(settings.artifact_dir)
        people = [("Aarav Mehta", "male", 1966, "former", "typical", True), ("Meera Nair", "female", 1979, "never", "non_anginal", False),
                  ("Kabir Singh", "male", 1958, "current", "atypical", True)]
        for index, (name, sex, year, smoking, pain, effort) in enumerate(people):
            patient = build_user(db, f"patient{index + 1}@demo.cardiolens.test", name, "patient", clinic,
                                 {"sex": sex, "birth_year": year, "height_cm": 160 + 6 * index, "smoking": smoking, "activity_minutes": 60 * index})
            now = datetime.now(timezone.utc)
            for week in range(8):
                when = now - timedelta(weeks=7 - week)
                for kind, base, spread in (("systolic", 136 + 4 * index, 7), ("diastolic", 84, 5), ("weight", 70 + 6 * index, 1.2)):
                    db.add(Measurement(patient_id=patient.id, kind=kind, value=round(float(base + rng.normal(0, spread)), 1), measured_at=when))
            db.add(Measurement(patient_id=patient.id, kind="cholesterol", value=float(200 + 25 * index), measured_at=now - timedelta(weeks=3)))
            db.flush()
            db.refresh(patient)
            payload = SymptomAssessment(chest_discomfort=pain, discomfort_with_effort=effort, breathlessness="on_exertion" if effort else "none",
                                        duration="weeks", severity=4 + index, conditions=["hypertension"] if index != 1 else [])
            inputs, result, level, version = svc.run_symptom(db, engine_, patient, payload)
            db.add(Assessment(patient_id=patient.id, kind="symptom", urgency=level, inputs=inputs, result=result, model_version=version))
            seed_health(db, patient, clinician, index, rng)
            db.add(Appointment(patient_id=patient.id, clinician_id=clinician.id, scheduled_at=now + timedelta(days=5 + index),
                               reason="Follow-up review", status="confirmed", created_by=clinician.id))
        db.commit()
    print(f"Seeded demo clinic. Clinic code {CODE}; accounts use password {PASSWORD}.")


if __name__ == "__main__":
    seed()
