from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Biomarker:
    key: str
    label: str
    unit: str
    category: str
    low: float
    high: float
    plausible: Tuple[float, float]
    concern: str
    about: str
    critical_low: Optional[float] = None
    critical_high: Optional[float] = None
    by_sex: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    watch_trend: bool = True


CATEGORIES = {
    "vitals": "Vitals",
    "cbc": "Blood count",
    "metabolic": "Metabolic and organ function",
    "lipids": "Cholesterol",
    "hormones": "Hormones and vitamins",
    "tumour": "Tumour markers",
    "inflammation": "Inflammation",
}

_B = Biomarker

CATALOGUE = [
    _B("weight_kg", "Weight", "kg", "vitals", 0, 0, (25, 350), "none", "Body weight. Sudden unintended changes are worth mentioning to a doctor.", watch_trend=False),
    _B("bmi", "Body mass index", "kg/m²", "vitals", 18.5, 24.9, (10, 70), "both", "Weight relative to height. Ranges differ for some ethnic groups, for example South Asians."),
    _B("bp_systolic", "Systolic blood pressure", "mmHg", "vitals", 90, 119, (60, 260), "high", "The top blood pressure number, measured while the heart pumps.", 80, 180),
    _B("bp_diastolic", "Diastolic blood pressure", "mmHg", "vitals", 60, 79, (30, 160), "high", "The bottom blood pressure number, measured between beats.", 50, 120),
    _B("heart_rate", "Resting heart rate", "bpm", "vitals", 60, 100, (25, 230), "both", "Heartbeats per minute at rest.", 40, 140),
    _B("spo2", "Oxygen saturation", "%", "vitals", 95, 100, (50, 100), "low", "How much oxygen your blood carries.", 90, None),
    _B("temperature_c", "Body temperature", "°C", "vitals", 36.1, 37.2, (30, 43), "both", "Core body temperature.", 35.0, 39.5, watch_trend=False),

    _B("wbc", "White blood cells", "10³/µL", "cbc", 4.0, 11.0, (0.2, 200), "both", "Immune cells. High counts can mean infection or inflammation, low counts can reduce defences.", 2.0, 30.0),
    _B("rbc", "Red blood cells", "10⁶/µL", "cbc", 4.1, 5.9, (1.0, 9.0), "both", "Cells that carry oxygen.", by_sex={"male": (4.5, 5.9), "female": (4.1, 5.1)}),
    _B("hemoglobin", "Haemoglobin", "g/dL", "cbc", 12.0, 17.5, (3, 25), "low", "The oxygen-carrying protein in red cells. Low levels mean anaemia.", 7.0, 20.0, by_sex={"male": (13.5, 17.5), "female": (12.0, 15.5)}),
    _B("hematocrit", "Haematocrit", "%", "cbc", 36, 53, (10, 70), "both", "The share of your blood made of red cells.", by_sex={"male": (41, 53), "female": (36, 46)}),
    _B("platelets", "Platelets", "10³/µL", "cbc", 150, 450, (5, 2000), "both", "Cells that help blood clot.", 50, 1000),
    _B("lymphocytes_pct", "Lymphocytes", "%", "cbc", 20, 40, (1, 90), "both", "A type of white cell involved in immunity."),
    _B("neutrophils_pct", "Neutrophils", "%", "cbc", 40, 70, (5, 99), "both", "White cells that fight bacterial infection."),
    _B("monocytes_pct", "Monocytes", "%", "cbc", 2, 10, (0, 40), "high", "White cells that clear debris and fight infection."),
    _B("eosinophils_pct", "Eosinophils", "%", "cbc", 1, 6, (0, 50), "high", "White cells linked to allergy and parasites."),
    _B("mcv", "Mean cell volume", "fL", "cbc", 80, 100, (40, 150), "both", "The average size of red cells."),
    _B("mch", "Mean cell haemoglobin", "pg", "cbc", 27, 33, (10, 50), "both", "The average haemoglobin in each red cell."),

    _B("glucose_fasting", "Fasting glucose", "mg/dL", "metabolic", 70, 99, (20, 800), "high", "Blood sugar after at least 8 hours without food. 100 to 125 is the prediabetes range.", 54, 250),
    _B("hba1c", "HbA1c", "%", "metabolic", 4.0, 5.6, (3, 20), "high", "Average blood sugar over about 3 months. 5.7 to 6.4 is prediabetes and 6.5 or more is the diabetes range.", None, 10.0),
    _B("creatinine", "Creatinine", "mg/dL", "metabolic", 0.59, 1.35, (0.2, 15), "high", "A waste product the kidneys clear.", None, 4.0, by_sex={"male": (0.74, 1.35), "female": (0.59, 1.04)}),
    _B("egfr", "eGFR", "mL/min/1.73m²", "metabolic", 90, 150, (3, 200), "low", "An estimate of kidney filtering. Below 60 for 3 months suggests reduced kidney function.", 15, None),
    _B("bun", "Blood urea nitrogen", "mg/dL", "metabolic", 7, 20, (1, 200), "high", "A waste product linked to kidney function and hydration."),
    _B("alt", "ALT", "U/L", "metabolic", 7, 56, (1, 3000), "high", "A liver enzyme that rises when liver cells are stressed."),
    _B("ast", "AST", "U/L", "metabolic", 8, 48, (1, 3000), "high", "An enzyme found in the liver and muscle."),
    _B("albumin", "Albumin", "g/dL", "metabolic", 3.5, 5.0, (1, 7), "low", "A protein made by the liver."),
    _B("bilirubin", "Total bilirubin", "mg/dL", "metabolic", 0.1, 1.2, (0, 30), "high", "A pigment cleared by the liver. High levels cause jaundice."),
    _B("ggt", "GGT", "U/L", "metabolic", 5, 61, (1, 2000), "high", "A liver enzyme sensitive to alcohol and bile duct problems.", by_sex={"male": (8, 61), "female": (5, 36)}),
    _B("uric_acid", "Uric acid", "mg/dL", "metabolic", 2.4, 7.0, (0.5, 20), "high", "High levels can cause gout and kidney stones.", by_sex={"male": (3.4, 7.0), "female": (2.4, 6.0)}),

    _B("total_cholesterol", "Total cholesterol", "mg/dL", "lipids", 100, 199, (50, 600), "high", "All the cholesterol in your blood. Under 200 is desirable."),
    _B("ldl", "LDL cholesterol", "mg/dL", "lipids", 40, 99, (10, 500), "high", "The 'bad' cholesterol. Lower is better for the heart; targets depend on your risk."),
    _B("hdl", "HDL cholesterol", "mg/dL", "lipids", 40, 100, (10, 150), "low", "The 'good' cholesterol. Higher is better. Women are advised to stay above 50.", by_sex={"male": (40, 100), "female": (50, 100)}),
    _B("triglycerides", "Triglycerides", "mg/dL", "lipids", 30, 149, (20, 3000), "high", "Blood fats that rise with sugar, alcohol and weight."),

    _B("tsh", "TSH", "mIU/L", "hormones", 0.4, 4.0, (0.01, 150), "both", "Thyroid stimulating hormone, the main thyroid screening test."),
    _B("t3", "Total T3", "ng/dL", "hormones", 80, 200, (20, 600), "both", "An active thyroid hormone."),
    _B("t4", "Total T4", "µg/dL", "hormones", 5.0, 12.0, (1, 30), "both", "The main thyroid hormone."),
    _B("vitamin_d", "Vitamin D", "ng/mL", "hormones", 30, 100, (2, 250), "low", "Needed for bones and immunity. Below 20 is deficient."),
    _B("vitamin_b12", "Vitamin B12", "pg/mL", "hormones", 200, 900, (50, 3000), "low", "Needed for nerves and blood cells."),
    _B("ferritin", "Ferritin", "ng/mL", "hormones", 11, 336, (1, 3000), "both", "A measure of the body's iron stores.", by_sex={"male": (24, 336), "female": (11, 307)}),

    _B("cea", "CEA", "ng/mL", "tumour", 0, 3.0, (0, 1000), "high", "A tumour marker. Smoking and some benign conditions also raise it. It cannot diagnose cancer."),
    _B("ca125", "CA-125", "U/mL", "tumour", 0, 35, (0, 5000), "high", "A tumour marker used to follow certain ovarian conditions. It has many benign causes."),
    _B("ca199", "CA 19-9", "U/mL", "tumour", 0, 37, (0, 100000), "high", "A tumour marker used to follow certain digestive conditions. Many benign conditions raise it."),
    _B("psa", "PSA", "ng/mL", "tumour", 0, 4.0, (0, 1000), "high", "Prostate-specific antigen. It rises with age and benign prostate conditions as well as cancer."),
    _B("afp", "AFP", "ng/mL", "tumour", 0, 10, (0, 100000), "high", "A protein used to follow certain liver conditions."),

    _B("crp", "C-reactive protein", "mg/L", "inflammation", 0, 3.0, (0, 500), "high", "A general marker of inflammation."),
    _B("esr", "ESR", "mm/hr", "inflammation", 0, 20, (0, 150), "high", "A general marker of inflammation that rises with age.", by_sex={"male": (0, 15), "female": (0, 20)}),
]

BY_KEY: Dict[str, Biomarker] = {b.key: b for b in CATALOGUE}
TUMOUR_MARKERS = {b.key for b in CATALOGUE if b.category == "tumour"}

CHECKUP_TO_MEASUREMENT = {
    "bp_systolic": "systolic", "bp_diastolic": "diastolic", "total_cholesterol": "cholesterol",
    "glucose_fasting": "glucose", "weight_kg": "weight", "heart_rate": "resting_hr",
}


def range_for(marker: Biomarker, sex: Optional[str]) -> Tuple[float, float]:
    if sex in marker.by_sex:
        return marker.by_sex[sex]
    if marker.by_sex and sex is None:
        values = list(marker.by_sex.values())
        return min(v[0] for v in values), max(v[1] for v in values)
    return marker.low, marker.high


def status_of(marker: Biomarker, value: float, sex: Optional[str]) -> str:
    if marker.concern == "none":
        return "normal"
    low, high = range_for(marker, sex)
    if marker.critical_low is not None and value < marker.critical_low:
        return "critical_low"
    if marker.critical_high is not None and value > marker.critical_high:
        return "critical_high"
    if value < low and marker.concern in ("low", "both"):
        return "low"
    if value > high and marker.concern in ("high", "both"):
        return "high"
    return "normal"


def describe(marker: Biomarker, sex: Optional[str]) -> dict:
    low, high = range_for(marker, sex)
    return {"key": marker.key, "label": marker.label, "unit": marker.unit, "category": marker.category,
            "low": None if marker.concern == "none" else low, "high": None if marker.concern == "none" else high,
            "concern": marker.concern, "about": marker.about, "plausible": list(marker.plausible)}


def catalogue_for(sex: Optional[str]) -> dict:
    return {"categories": CATEGORIES, "biomarkers": [describe(b, sex) for b in CATALOGUE],
            "note": "Typical adult reference ranges. Laboratories differ, so always use the range printed on your own report."}
