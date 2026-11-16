import csv
import io
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.crypto import decrypt, encrypt
from ..db.models import Diagnosis, DietPlan, HealthAlert, LabCheckup, Medication, User
from . import interactions
from .biomarkers import BY_KEY, CATALOGUE, range_for, status_of
from .trends import analyse, trend_alert

OVERDUE_DAYS = 90
MAX_CSV_BYTES = 2_000_000
MAX_CSV_ROWS = 500
STATUS_WORDS = {"critical_low": "critically low", "critical_high": "critically high", "low": "below its typical range", "high": "above its typical range"}


def now():
    return datetime.now(timezone.utc)


def sex_of(patient: User) -> Optional[str]:
    return patient.profile.sex if patient.profile else None


def clean_values(values: Dict[str, float], context: str = "") -> Dict[str, float]:
    problems, cleaned = [], {}
    prefix = f"{context}: " if context else ""
    for key, raw in values.items():
        marker = BY_KEY.get(key)
        if marker is None:
            problems.append(f"{prefix}unknown measurement '{key}'")
            continue
        low, high = marker.plausible
        if raw != raw or not low <= float(raw) <= high:
            problems.append(f"{prefix}{marker.label} must be between {low:g} and {high:g} {marker.unit}")
            continue
        cleaned[key] = float(raw)
    if problems:
        raise HTTPException(422, "; ".join(problems[:6]))
    if not cleaned:
        raise HTTPException(422, "Enter at least one measurement.")
    return cleaned


def check_date(when: date):
    if when > date.today():
        raise HTTPException(422, "The check-up date cannot be in the future.")
    if when.year < 1950:
        raise HTTPException(422, "The check-up date is too far in the past.")


def series_map(db: Session, patient_id: int) -> Dict[str, list]:
    rows = db.scalars(select(LabCheckup).where(LabCheckup.patient_id == patient_id).order_by(LabCheckup.checkup_date, LabCheckup.id)).all()
    out: Dict[str, list] = {}
    for row in rows:
        for key, value in row.values.items():
            out.setdefault(key, []).append((row.checkup_date, float(value)))
    return out


def value_alert(marker, value: float, sex: Optional[str]):
    status = status_of(marker, value, sex)
    if status == "normal":
        return None
    low, high = range_for(marker, sex)
    width = (high - low) or max(abs(high), 1.0)
    distance = (low - value) / width if value < low else (value - high) / width
    critical = status.startswith("critical")
    severity = "critical" if critical else "warning" if distance > 0.2 else "info"
    message = f"{marker.label} {value:g} {marker.unit} is {STATUS_WORDS[status]} (typical {low:g} to {high:g})."
    if critical:
        message += " Contact a doctor promptly. If the value was a typing mistake, delete the check-up."
    return severity, message


def refresh_alerts(db: Session, patient: User, keys: List[str], checkup: Optional[LabCheckup]):
    sex = sex_of(patient)
    points = series_map(db, patient.id)
    stamp = now()
    open_alerts = db.scalars(select(HealthAlert).where(HealthAlert.patient_id == patient.id, HealthAlert.resolved_at.is_(None),
                                                       HealthAlert.biomarker.in_(keys))).all()
    for alert in open_alerts:
        alert.resolved_at = stamp
    for key in keys:
        marker = BY_KEY[key]
        history = points.get(key, [])
        if not history:
            continue
        latest = history[-1][1]
        found = value_alert(marker, latest, sex)
        if found:
            db.add(HealthAlert(patient_id=patient.id, severity=found[0], kind="value", biomarker=key, message=found[1],
                               checkup_id=checkup.id if checkup else None))
        trend = trend_alert(marker, history, sex)
        if trend:
            db.add(HealthAlert(patient_id=patient.id, severity="warning" if trend["level"] == "warning" else "info", kind="trend",
                               biomarker=key, message=trend["message"], checkup_id=checkup.id if checkup else None))


def create_checkup(db: Session, patient: User, actor: User, source: str, when: date, values: Dict[str, float],
                   notes: Optional[str]) -> LabCheckup:
    check_date(when)
    cleaned = clean_values(values)
    row = LabCheckup(patient_id=patient.id, checkup_date=when, values=cleaned, source=source, created_by=actor.id,
                     notes_encrypted=encrypt(notes.strip()) if notes and notes.strip() else None)
    db.add(row)
    db.flush()
    refresh_alerts(db, patient, list(cleaned), row)
    return row


def delete_checkup(db: Session, patient: User, row: LabCheckup):
    keys = list(row.values)
    for alert in db.scalars(select(HealthAlert).where(HealthAlert.checkup_id == row.id)):
        alert.checkup_id = None
        alert.resolved_at = alert.resolved_at or now()
    db.delete(row)
    db.flush()
    refresh_alerts(db, patient, keys, None)


def checkup_out(row: LabCheckup, sex: Optional[str]) -> dict:
    flags = {k: status_of(BY_KEY[k], v, sex) for k, v in row.values.items() if k in BY_KEY}
    return {"id": row.id, "date": row.checkup_date.isoformat(), "values": row.values, "flags": flags,
            "notes": decrypt(row.notes_encrypted) if row.notes_encrypted else None, "source": row.source,
            "created_at": row.created_at.isoformat()}


def trend_report(db: Session, patient: User, keys: Optional[List[str]] = None) -> List[dict]:
    sex = sex_of(patient)
    points = series_map(db, patient.id)
    wanted = [k for k in (keys or [b.key for b in CATALOGUE]) if k in points and k in BY_KEY]
    return [analyse(BY_KEY[k], points[k], sex) for k in wanted]


def overdue_info(db: Session, patient: User, today: Optional[date] = None) -> dict:
    today = today or date.today()
    last = db.scalar(select(LabCheckup.checkup_date).where(LabCheckup.patient_id == patient.id).order_by(LabCheckup.checkup_date.desc()))
    if last is None:
        created = patient.created_at.date() if patient.created_at else today
        age = (today - created).days
        status = "overdue" if age >= 14 else "none"
        message = "No check-up results have been recorded yet. Add your latest lab results to start tracking trends."
        return {"status": status, "last_checkup": None, "days_since": None, "overdue": status == "overdue", "message": message}
    days = (today - last).days
    overdue = days >= OVERDUE_DAYS
    message = (f"Your last recorded check-up was {days} days ago. Consider booking a routine blood test." if overdue
               else f"Your last recorded check-up was {days} days ago.")
    return {"status": "overdue" if overdue else "ok", "last_checkup": last.isoformat(), "days_since": days, "overdue": overdue, "message": message}


def active_medicines(db: Session, patient_id: int) -> List[str]:
    return [m.name for m in db.scalars(select(Medication).where(Medication.patient_id == patient_id, Medication.is_active.is_(True)))]


def health_summary(db: Session, patient: User) -> dict:
    alerts = db.scalars(select(HealthAlert).where(HealthAlert.patient_id == patient.id, HealthAlert.resolved_at.is_(None),
                                                  HealthAlert.acknowledged_at.is_(None))).all()
    names = active_medicines(db, patient.id)
    found = interactions.check(names)["interactions"] if len(names) > 1 else []
    return {"open_alerts": len(alerts), "critical_alerts": sum(1 for a in alerts if a.severity == "critical"),
            "overdue": overdue_info(db, patient), "interaction_count": len(found),
            "serious_interactions": sum(1 for f in found if f["severity"] in ("major", "contraindicated"))}


def alert_out(a: HealthAlert, patient_name: Optional[str] = None) -> dict:
    marker = BY_KEY.get(a.biomarker) if a.biomarker else None
    return {"id": a.id, "patient_id": a.patient_id, "patient_name": patient_name, "severity": a.severity, "kind": a.kind,
            "biomarker": a.biomarker, "label": marker.label if marker else None, "message": a.message,
            "created_at": a.created_at.isoformat(), "resolved": a.resolved_at is not None,
            "acknowledged": a.acknowledged_at is not None}


def parse_csv(raw: bytes) -> List[dict]:
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(422, "The file is larger than 2 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "The file must be UTF-8 text.")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(422, "The file is empty.")
    columns = {c.strip().lower(): c for c in reader.fieldnames if c}
    if "date" not in columns:
        raise HTTPException(422, "The file needs a 'date' column (YYYY-MM-DD).")
    unknown = [c for c in columns if c != "date" and c not in BY_KEY]
    if unknown:
        raise HTTPException(422, "Unknown columns: " + ", ".join(unknown[:8]))
    rows, problems = [], []
    for number, record in enumerate(reader, start=2):
        if number - 1 > MAX_CSV_ROWS:
            raise HTTPException(422, f"The file has more than {MAX_CSV_ROWS} rows.")
        try:
            when = date.fromisoformat((record[columns["date"]] or "").strip())
        except ValueError:
            problems.append(f"row {number}: date must look like 2026-03-15")
            continue
        values = {}
        for key in (c for c in columns if c != "date"):
            cell = (record.get(columns[key]) or "").strip()
            if cell:
                try:
                    values[key] = float(cell)
                except ValueError:
                    problems.append(f"row {number}: '{cell}' is not a number for {key}")
        if not values:
            problems.append(f"row {number}: no measurements")
            continue
        try:
            check_date(when)
            values = clean_values(values, f"row {number}")
        except HTTPException as error:
            problems.append(str(error.detail))
            continue
        rows.append({"date": when, "values": values})
    if problems:
        raise HTTPException(422, "; ".join(problems[:12]) + (f" (and {len(problems) - 12} more)" if len(problems) > 12 else ""))
    if not rows:
        raise HTTPException(422, "The file has no data rows.")
    return rows


def template_csv() -> str:
    keys = [b.key for b in CATALOGUE]
    sample = {"date": "2026-01-15", "weight_kg": "72.5", "bp_systolic": "128", "bp_diastolic": "82", "hemoglobin": "14.1",
              "glucose_fasting": "96", "total_cholesterol": "188", "ldl": "112", "hdl": "48", "triglycerides": "140"}
    header = ["date"] + keys
    return ",".join(header) + "\n" + ",".join(sample.get(c, "") for c in header) + "\n"


def export_csv(rows: List[LabCheckup]) -> str:
    present = [b.key for b in CATALOGUE if any(b.key in r.values for r in rows)]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date"] + present)
    for row in sorted(rows, key=lambda r: (r.checkup_date, r.id)):
        writer.writerow([row.checkup_date.isoformat()] + [row.values.get(k, "") for k in present])
    return buffer.getvalue()


def health_export(db: Session, patient: User) -> dict:
    sex = sex_of(patient)
    checkups = db.scalars(select(LabCheckup).where(LabCheckup.patient_id == patient.id).order_by(LabCheckup.checkup_date)).all()
    medicines = db.scalars(select(Medication).where(Medication.patient_id == patient.id)).all()
    diagnoses = db.scalars(select(Diagnosis).where(Diagnosis.patient_id == patient.id)).all()
    plans = db.scalars(select(DietPlan).where(DietPlan.patient_id == patient.id)).all()
    return {
        "checkups": [checkup_out(c, sex) for c in checkups],
        "medications": [{"name": m.name, "dose": m.dose, "frequency": m.frequency, "reason": m.reason, "active": m.is_active} for m in medicines],
        "diagnoses": [{"icd10": d.icd10, "description": d.description, "status": d.status} for d in diagnoses],
        "diet_plans": [{"name": p.name, "diet_type": p.diet_type, "calories": p.calories, "restrictions": p.restrictions} for p in plans],
    }
