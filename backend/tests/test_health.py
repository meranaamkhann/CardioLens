from datetime import date, timedelta

import pytest

from app.health import interactions
from app.health.biomarkers import BY_KEY, CATALOGUE, CATEGORIES, range_for, status_of
from app.health.trends import analyse, slope_per_month, trend_alert
from conftest import headers, register_patient

H = "/api/me/health"


def day(offset):
    return (date.today() - timedelta(days=offset)).isoformat()


def add(client, token, when, values, base=H):
    return client.post(f"{base}/checkups", headers=headers(token), json={"checkup_date": when, "values": values})


def test_catalogue_is_complete_and_consistent():
    assert len(CATALOGUE) == 46
    assert len({b.key for b in CATALOGUE}) == 46
    for b in CATALOGUE:
        assert b.category in CATEGORIES
        assert b.plausible[0] < b.plausible[1]
        if b.concern != "none":
            assert b.low <= b.high
            assert b.plausible[0] <= b.low and b.high <= b.plausible[1]
        if b.critical_low is not None:
            assert b.critical_low < b.low
        if b.critical_high is not None:
            assert b.critical_high > b.high


def test_sex_specific_ranges_and_status():
    hb = BY_KEY["hemoglobin"]
    assert range_for(hb, "male") == (13.5, 17.5)
    assert range_for(hb, "female") == (12.0, 15.5)
    assert status_of(hb, 12.5, "male") == "low"
    assert status_of(hb, 12.5, "female") == "normal"
    assert status_of(hb, 6.5, "female") == "critical_low"
    assert status_of(BY_KEY["crp"], 0.2, None) == "normal"
    assert status_of(BY_KEY["weight_kg"], 400, None) == "normal"


def test_biomarker_catalogue_endpoint(client, patient):
    body = client.get(f"{H}/biomarkers", headers=headers(patient["access_token"])).json()
    assert len(body["biomarkers"]) == 46 and "note" in body
    hb = next(b for b in body["biomarkers"] if b["key"] == "hemoglobin")
    assert hb["low"] == 13.5


@pytest.mark.parametrize("values, when, fragment", [
    ({"nonsense": 5}, None, "unknown measurement"),
    ({"hemoglobin": 99}, None, "Haemoglobin must be between"),
    ({"hemoglobin": 14}, (date.today() + timedelta(days=2)).isoformat(), "future"),
    ({}, None, None)])
def test_checkup_validation(client, patient, values, when, fragment):
    r = add(client, patient["access_token"], when or day(1), values)
    assert r.status_code == 422
    if fragment:
        assert fragment in r.text


def test_critical_value_creates_alert_and_normal_value_resolves_it(client, patient):
    t = patient["access_token"]
    assert add(client, t, day(30), {"hemoglobin": 6.5, "ldl": 90}).status_code == 201
    alerts = client.get(f"{H}/alerts", headers=headers(t)).json()
    critical = [a for a in alerts if a["severity"] == "critical"]
    assert len(critical) == 1 and critical[0]["biomarker"] == "hemoglobin" and "critically low" in critical[0]["message"]
    assert not any(a["biomarker"] == "ldl" for a in alerts)
    assert add(client, t, day(2), {"hemoglobin": 14.8}).status_code == 201
    assert not any(a["biomarker"] == "hemoglobin" for a in client.get(f"{H}/alerts", headers=headers(t)).json())
    assert any(a["biomarker"] == "hemoglobin" and a["resolved"] for a in client.get(f"{H}/alerts?include=all", headers=headers(t)).json())


def test_checkup_list_flags_and_delete(client, patient):
    t = patient["access_token"]
    created = add(client, t, day(10), {"ldl": 160, "hdl": 55}).json()
    assert created["flags"]["ldl"] == "high" and created["flags"]["hdl"] == "normal" and created["source"] == "patient"
    assert client.get(f"{H}/checkups", headers=headers(t)).json()[0]["id"] == created["id"]
    assert client.delete(f"{H}/checkups/{created['id']}", headers=headers(t)).status_code == 204
    assert client.get(f"{H}/checkups", headers=headers(t)).json() == []
    assert client.delete(f"{H}/checkups/{created['id']}", headers=headers(t)).status_code == 404
    assert not [a for a in client.get(f"{H}/alerts", headers=headers(t)).json() if a["biomarker"] == "ldl"]


def test_slope_and_direction_math():
    points = [(date(2026, 1, 1), 10.0), (date(2026, 3, 2), 12.0), (date(2026, 5, 1), 14.0)]
    assert slope_per_month(points) == pytest.approx(1.0, abs=0.05)
    assert slope_per_month(points[:1]) is None
    stable = [(date(2026, 1, 1) + timedelta(days=60 * i), v) for i, v in enumerate([14.0, 14.1, 13.9, 14.0])]
    assert analyse(BY_KEY["hemoglobin"], stable, "male")["direction"] == "stable"
    assert trend_alert(BY_KEY["hemoglobin"], stable, "male") is None


def test_single_outlier_does_not_create_a_trend():
    values = [14.2, 14.0, 6.5, 14.1, 14.0]
    points = [(date(2026, 1, 1) + timedelta(days=60 * i), v) for i, v in enumerate(values)]
    assert analyse(BY_KEY["hemoglobin"], points, "male")["direction"] == "stable"
    assert trend_alert(BY_KEY["hemoglobin"], points, "male") is None


def test_rising_ldl_inside_range_triggers_trend_watch():
    points = [(date(2026, 1, 1) + timedelta(days=90 * i), v) for i, v in enumerate([70.0, 78.0, 86.0, 94.0])]
    alert = trend_alert(BY_KEY["ldl"], points, "male")
    assert alert and alert["level"] == "watch" and "within its typical range" in alert["message"]


def test_steadily_rising_tumour_marker_is_flagged_without_diagnosing():
    points = [(date(2026, 1, 1) + timedelta(days=90 * i), v) for i, v in enumerate([1.0, 1.3, 1.6, 2.0])]
    alert = trend_alert(BY_KEY["cea"], points, None)
    assert alert and alert["level"] == "warning" and "not a diagnosis" in alert["message"]


def test_trend_alerts_need_enough_points_and_time():
    assert trend_alert(BY_KEY["ldl"], [(date(2026, 1, 1), 70.0), (date(2026, 6, 1), 96.0)], None) is None
    quick = [(date(2026, 1, 1) + timedelta(days=5 * i), v) for i, v in enumerate([70.0, 85.0, 99.0])]
    assert trend_alert(BY_KEY["ldl"], quick, None) is None


def test_trends_endpoint_end_to_end(client, patient):
    t = patient["access_token"]
    for offset, value in ((270, 70), (180, 78), (90, 86), (5, 94)):
        assert add(client, t, day(offset), {"ldl": value, "hdl": 52}).status_code == 201
    trends = client.get(f"{H}/trends", headers=headers(t)).json()
    ldl = next(x for x in trends if x["key"] == "ldl")
    assert len(ldl["points"]) == 4 and ldl["direction"] == "rising" and ldl["alert"]["level"] == "watch"
    only = client.get(f"{H}/trends?keys=hdl", headers=headers(t)).json()
    assert [x["key"] for x in only] == ["hdl"]
    assert any(a["kind"] == "trend" and a["biomarker"] == "ldl" for a in client.get(f"{H}/alerts", headers=headers(t)).json())


def test_acknowledge_alert_and_isolation(client, clinic):
    first, second = register_patient(client, clinic["code"]), register_patient(client, clinic["code"])
    add(client, first["access_token"], day(3), {"glucose_fasting": 300})
    alert = client.get(f"{H}/alerts", headers=headers(first["access_token"])).json()[0]
    assert alert["severity"] == "critical"
    assert client.post(f"{H}/alerts/{alert['id']}/acknowledge", headers=headers(second["access_token"])).status_code == 404
    done = client.post(f"{H}/alerts/{alert['id']}/acknowledge", headers=headers(first["access_token"])).json()
    assert done["acknowledged"] is True
    assert client.get(f"{H}/summary", headers=headers(first["access_token"])).json()["open_alerts"] == 0


def test_medications_interactions_and_stop(client, patient):
    t = patient["access_token"]
    for name in ("Coumadin 5 mg", "Ecosprin 75"):
        assert client.post(f"{H}/medications", headers=headers(t), json={"name": name, "dose": "once daily"}).status_code == 201
    body = client.get(f"{H}/medications", headers=headers(t)).json()
    assert len(body["medications"]) == 2
    assert body["interactions"]["interactions"][0]["severity"] == "major"
    med = next(m for m in body["medications"] if "Ecosprin" in m["name"])
    stopped = client.patch(f"{H}/medications/{med['id']}", headers=headers(t), json={"is_active": False}).json()
    assert stopped["is_active"] is False and stopped["end_date"]
    assert client.get(f"{H}/medications", headers=headers(t)).json()["interactions"]["interactions"] == []
    assert client.get(f"{H}/summary", headers=headers(t)).json()["interaction_count"] == 0


def test_medication_date_validation(client, patient):
    r = client.post(f"{H}/medications", headers=headers(patient["access_token"]), json={"name": "Drug", "start_date": "2026-05-01", "end_date": "2026-04-01"})
    assert r.status_code == 422


def test_interaction_checker_rules():
    assert interactions.check(["sildenafil", "isosorbide mononitrate"])["interactions"][0]["severity"] == "contraindicated"
    assert interactions.check(["Brufen 400mg", "Coumadin"])["interactions"][0]["severity"] == "major"
    assert interactions.check(["metformin", "paracetamol"])["interactions"] == []
    assert interactions.check(["paracetamol", "warfarin"])["not_covered"] == ["paracetamol"]
    assert interactions.normalise("Glycomet 500 mg tablets") == "metformin"
    duplicate = interactions.check(["aspirin", "Aspirin 75mg", "warfarin"])
    assert len(duplicate["interactions"]) == 1


def test_interaction_endpoint(client, patient):
    r = client.post(f"{H}/interactions/check", headers=headers(patient["access_token"]), json={"medicines": ["lisinopril", "potassium chloride"]})
    assert r.status_code == 200 and r.json()["interactions"][0]["severity"] == "major"
    assert client.post(f"{H}/interactions/check", headers=headers(patient["access_token"]), json={"medicines": ["one"]}).status_code == 422


def test_diagnoses_validate_icd10(client, patient):
    t = patient["access_token"]
    ok = client.post(f"{H}/diagnoses", headers=headers(t), json={"icd10": "i10", "description": "Essential hypertension", "severity": "mild"})
    assert ok.status_code == 201 and ok.json()["icd10"] == "I10" and ok.json()["source"] == "patient"
    assert client.post(f"{H}/diagnoses", headers=headers(t), json={"icd10": "E11.9", "description": "Type 2 diabetes"}).status_code == 201
    for bad in ("12", "U", "ABCD", "I10.123456"):
        assert client.post(f"{H}/diagnoses", headers=headers(t), json={"icd10": bad, "description": "Invalid code"}).status_code == 422
    assert len(client.get(f"{H}/diagnoses", headers=headers(t)).json()) == 2


def test_diet_plans(client, patient):
    t = patient["access_token"]
    made = client.post(f"{H}/diet-plans", headers=headers(t), json={"name": "Heart-friendly", "diet_type": "Mediterranean", "calories": 1900,
                                                                     "protein_g": 80, "restrictions": ["low salt", " ", "no fried food"]})
    assert made.status_code == 201 and made.json()["restrictions"] == ["low salt", "no fried food"]
    assert client.post(f"{H}/diet-plans", headers=headers(t), json={"name": "Starvation", "calories": 100}).status_code == 422
    assert client.delete(f"{H}/diet-plans/{made.json()['id']}", headers=headers(t)).status_code == 204
    assert client.get(f"{H}/diet-plans", headers=headers(t)).json() == []


def test_csv_import_export_roundtrip(client, patient):
    t = patient["access_token"]
    template = client.get(f"{H}/import/template", headers=headers(t))
    assert template.status_code == 200 and template.text.startswith("date,weight_kg")
    body = f"date,hemoglobin,LDL\n{day(60)},13.9,98\n{day(30)},14.2,104\n"
    ok = client.post(f"{H}/import/checkups-csv", headers=headers(t), files={"file": ("labs.csv", body, "text/csv")})
    assert ok.status_code == 201 and ok.json()["imported"] == 2
    exported = client.get(f"{H}/export/checkups.csv", headers=headers(t)).text.splitlines()
    assert exported[0] == "date,hemoglobin,ldl" and len(exported) == 3
    assert any(a["biomarker"] == "ldl" for a in client.get(f"{H}/alerts", headers=headers(t)).json())


@pytest.mark.parametrize("content, fragment", [
    ("hemoglobin\n14\n", "'date' column"),
    (f"date,bogus\n{day(5)},1\n", "Unknown columns"),
    ("date,hemoglobin\nyesterday,14\n", "date must look like"),
    (f"date,hemoglobin\n{day(5)},abc\n", "not a number"),
    (f"date,hemoglobin\n{day(5)},900\n", "Haemoglobin must be between"),
    (f"date,hemoglobin\n{day(5)},\n", "no measurements"),
    ("date,hemoglobin\n", "no data rows")])
def test_csv_import_rejects_bad_files_atomically(client, patient, content, fragment):
    t = patient["access_token"]
    r = client.post(f"{H}/import/checkups-csv", headers=headers(t), files={"file": ("x.csv", content, "text/csv")})
    assert r.status_code == 422 and fragment in r.text
    assert client.get(f"{H}/checkups", headers=headers(t)).json() == []


def test_csv_import_row_limit_and_atomicity(client, patient):
    t = patient["access_token"]
    rows = "\n".join(f"{day(1)},14" for _ in range(501))
    assert client.post(f"{H}/import/checkups-csv", headers=headers(t), files={"file": ("big.csv", "date,hemoglobin\n" + rows, "text/csv")}).status_code == 422
    mixed = f"date,hemoglobin\n{day(9)},14\n{day(8)},999\n"
    assert client.post(f"{H}/import/checkups-csv", headers=headers(t), files={"file": ("m.csv", mixed, "text/csv")}).status_code == 422
    assert client.get(f"{H}/checkups", headers=headers(t)).json() == []


def test_checkup_values_feed_symptom_assessment(client, patient):
    t = patient["access_token"]
    add(client, t, day(4), {"bp_systolic": 152, "total_cholesterol": 245})
    payload = {"chest_discomfort": "atypical", "discomfort_with_effort": False, "breathlessness": "none", "palpitations": False, "dizziness": False,
               "fatigue": False, "duration": "weeks", "severity": 4, "emergency": [], "conditions": []}
    body = client.post("/api/me/assessments/symptom", headers=headers(t), json=payload).json()
    assert set(body["inputs"]["autofilled_from_history"]) >= {"systolic", "cholesterol"}


def test_dashboard_health_summary_and_reminders(client, patient):
    t = patient["access_token"]
    dash = client.get("/api/me/dashboard", headers=headers(t)).json()
    assert dash["health"]["open_alerts"] == 0 and dash["health"]["overdue"]["status"] == "none"
    add(client, t, day(120), {"hemoglobin": 14})
    reminder = client.get(f"{H}/reminders", headers=headers(t)).json()
    assert reminder["overdue"] is True and reminder["days_since"] == 120
    add(client, t, day(5), {"hemoglobin": 14})
    assert client.get(f"{H}/reminders", headers=headers(t)).json()["overdue"] is False


def test_clinician_manages_patient_health_record(client, clinic, patient):
    c, p = headers(clinic["clinician"]["access_token"]), headers(patient["access_token"])
    base = f"/api/clinic/patients/{patient['user']['id']}/health"
    made = client.post(f"{base}/checkups", headers=c, json={"checkup_date": day(7), "values": {"hba1c": 8.2, "glucose_fasting": 160}})
    assert made.status_code == 201 and made.json()["source"] == "clinician"
    assert client.get(f"{H}/checkups", headers=p).json()[0]["id"] == made.json()["id"]
    assert client.delete(f"{H}/checkups/{made.json()['id']}", headers=p).status_code == 403
    diag = client.post(f"{base}/diagnoses", headers=c, json={"icd10": "E11.9", "description": "Type 2 diabetes mellitus", "severity": "moderate"}).json()
    assert diag["source"] == "clinician"
    assert client.delete(f"{H}/diagnoses/{diag['id']}", headers=p).status_code == 403
    assert client.delete(f"{base}/diagnoses/{diag['id']}", headers=c).status_code == 204
    med = client.post(f"{base}/medications", headers=c, json={"name": "Metformin", "dose": "500 mg", "frequency": "twice daily"})
    assert med.status_code == 201 and client.delete(f"{H}/medications/{med.json()['id']}", headers=p).status_code == 403
    listing = client.get(f"{base}/checkups", headers=c).json()
    assert len(listing) == 1
    audit = {e["action"] for e in client.get("/api/admin/audit", headers=headers(clinic["admin"]["access_token"])).json()}
    assert {"checkup_created", "patient_health_viewed", "medication_added"} <= audit


def test_clinician_cannot_reach_outsiders_or_wrong_roles(client, clinic):
    outsider = register_patient(client)
    c = headers(clinic["clinician"]["access_token"])
    base = f"/api/clinic/patients/{outsider['user']['id']}/health"
    assert client.get(f"{base}/checkups", headers=c).status_code == 404
    assert client.post(f"{base}/checkups", headers=c, json={"checkup_date": day(1), "values": {"hemoglobin": 14}}).status_code == 404
    member = register_patient(client, clinic["code"])
    mbase = f"/api/clinic/patients/{member['user']['id']}/health"
    assert client.get(f"{mbase}/checkups", headers=headers(member["access_token"])).status_code == 403
    assert client.get(f"{mbase}/checkups", headers=headers(clinic["researcher"]["access_token"])).status_code == 403
    assert client.get(f"{H}/checkups", headers=c).status_code == 403
    assert client.get(f"{H}/checkups").status_code == 401


def test_clinic_wide_alerts_and_overdue(client, clinic):
    sick, quiet = register_patient(client, clinic["code"]), register_patient(client, clinic["code"])
    add(client, sick["access_token"], day(2), {"hemoglobin": 6.0})
    add(client, quiet["access_token"], day(200), {"hemoglobin": 14.0})
    c = headers(clinic["clinician"]["access_token"])
    alerts = client.get("/api/clinic/health/alerts", headers=c).json()
    assert alerts[0]["severity"] == "critical" and alerts[0]["patient_id"] == sick["user"]["id"] and alerts[0]["patient_name"]
    overdue = {o["patient_id"]: o for o in client.get("/api/clinic/health/overdue", headers=c).json()}
    assert overdue[quiet["user"]["id"]]["days_since"] == 200 and sick["user"]["id"] not in overdue
    assert client.get("/api/clinic/health/alerts", headers=headers(sick["access_token"])).status_code == 403
    outsider = register_patient(client)
    add(client, outsider["access_token"], day(1), {"hemoglobin": 5.0})
    assert all(a["patient_id"] != outsider["user"]["id"] for a in client.get("/api/clinic/health/alerts", headers=c).json())


def test_health_data_is_exported_and_deleted_with_the_account(client, clinic):
    auth = register_patient(client, clinic["code"])
    t = auth["access_token"]
    add(client, t, day(5), {"hemoglobin": 6.0, "ldl": 150})
    client.post(f"{H}/medications", headers=headers(t), json={"name": "Aspirin"})
    client.post(f"{H}/diagnoses", headers=headers(t), json={"icd10": "I10", "description": "Hypertension"})
    client.post(f"{H}/diet-plans", headers=headers(t), json={"name": "Low salt"})
    export = client.get("/api/me/export.json", headers=headers(t)).json()
    record = export["health_record"]
    assert len(record["checkups"]) == 1 and record["medications"][0]["name"] == "Aspirin" and record["diagnoses"] and record["diet_plans"]
    assert client.post("/api/me/delete-account", headers=headers(t), json={"password": "Str0ngPassw0rd"}).status_code == 204
    from app.db.base import SessionLocal
    from app.db.models import Diagnosis, DietPlan, HealthAlert, LabCheckup, Medication
    with SessionLocal() as db:
        for model in (LabCheckup, Medication, Diagnosis, DietPlan, HealthAlert):
            assert db.query(model).filter(model.patient_id == auth["user"]["id"]).count() == 0
