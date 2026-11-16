import re
from typing import Dict, List, Set

GROUPS: Dict[str, Set[str]] = {
    "nsaid": {"ibuprofen", "naproxen", "diclofenac", "ketorolac", "indomethacin", "celecoxib", "etoricoxib", "nimesulide", "mefenamic acid"},
    "ace_inhibitor": {"lisinopril", "enalapril", "ramipril", "captopril", "perindopril", "benazepril"},
    "arb": {"losartan", "telmisartan", "valsartan", "olmesartan", "candesartan", "irbesartan"},
    "ssri": {"sertraline", "fluoxetine", "escitalopram", "citalopram", "paroxetine", "fluvoxamine"},
    "beta_blocker": {"metoprolol", "atenolol", "bisoprolol", "propranolol", "carvedilol", "nebivolol"},
    "nitrate": {"nitroglycerin", "glyceryl trinitrate", "isosorbide mononitrate", "isosorbide dinitrate"},
    "pde5": {"sildenafil", "tadalafil", "vardenafil"},
    "macrolide": {"clarithromycin", "erythromycin"},
    "azole": {"itraconazole", "ketoconazole", "fluconazole", "voriconazole"},
    "thiazide": {"hydrochlorothiazide", "chlorthalidone", "indapamide"},
    "ppi": {"omeprazole", "esomeprazole", "pantoprazole", "lansoprazole"},
    "k_sparing": {"spironolactone", "eplerenone", "amiloride", "triamterene"},
    "potassium": {"potassium chloride", "potassium"},
}

ALIASES = {
    "coumadin": "warfarin", "warf": "warfarin", "ecosprin": "aspirin", "disprin": "aspirin", "acetylsalicylic acid": "aspirin",
    "brufen": "ibuprofen", "advil": "ibuprofen", "motrin": "ibuprofen", "aleve": "naproxen", "voveran": "diclofenac", "voltaren": "diclofenac",
    "plavix": "clopidogrel", "lipitor": "atorvastatin", "zocor": "simvastatin", "crestor": "rosuvastatin", "lasix": "furosemide",
    "viagra": "sildenafil", "cialis": "tadalafil", "lanoxin": "digoxin", "cordarone": "amiodarone", "norvasc": "amlodipine",
    "zoloft": "sertraline", "prozac": "fluoxetine", "lexapro": "escitalopram", "ultram": "tramadol", "prilosec": "omeprazole",
    "nexium": "esomeprazole", "glucophage": "metformin", "glycomet": "metformin", "betaloc": "metoprolol", "tenormin": "atenolol",
    "aldactone": "spironolactone", "sorbitrate": "isosorbide dinitrate", "nitroglycerine": "nitroglycerin",
}

RULES = [
    ("warfarin", "aspirin", "major", "Higher risk of serious bleeding.", "Do not combine unless a doctor has prescribed both and is monitoring you."),
    ("warfarin", "nsaid", "major", "Higher risk of serious bleeding.", "Avoid anti-inflammatory painkillers with warfarin. Ask a pharmacist about safer pain relief."),
    ("warfarin", "amiodarone", "major", "Amiodarone raises warfarin levels and the INR.", "Warfarin doses usually need reducing and closer INR checks."),
    ("warfarin", "azole", "major", "Antifungal azoles raise warfarin levels and the INR.", "Needs closer INR monitoring and often a dose change."),
    ("warfarin", "macrolide", "moderate", "These antibiotics can raise warfarin levels and the INR.", "Tell the prescriber you take warfarin and check the INR."),
    ("aspirin", "ibuprofen", "moderate", "Ibuprofen can blunt aspirin's heart protection and adds stomach bleeding risk.", "Take aspirin first, at least 30 minutes before ibuprofen, or ask about alternatives."),
    ("aspirin", "naproxen", "moderate", "Adds stomach bleeding risk and may reduce aspirin's heart protection.", "Ask your doctor or pharmacist before combining."),
    ("aspirin", "clopidogrel", "moderate", "Together they raise bleeding risk. They are often prescribed together deliberately.", "Follow your cardiologist's plan and do not stop either on your own."),
    ("clopidogrel", "omeprazole", "moderate", "Omeprazole can reduce how well clopidogrel works.", "Ask about pantoprazole, which has less effect."),
    ("clopidogrel", "esomeprazole", "moderate", "Esomeprazole can reduce how well clopidogrel works.", "Ask about pantoprazole, which has less effect."),
    ("simvastatin", "macrolide", "major", "Strongly raises simvastatin levels and the risk of muscle damage.", "Usually avoided. Simvastatin is normally paused during the antibiotic course."),
    ("simvastatin", "azole", "major", "Strongly raises simvastatin levels and the risk of muscle damage.", "Usually avoided."),
    ("simvastatin", "amiodarone", "moderate", "Raises simvastatin levels. The simvastatin dose is usually capped.", "Ask the prescriber about the dose."),
    ("simvastatin", "amlodipine", "moderate", "Raises simvastatin levels. The simvastatin dose is usually capped.", "Ask the prescriber about the dose."),
    ("simvastatin", "diltiazem", "moderate", "Raises simvastatin levels. The simvastatin dose is usually capped.", "Ask the prescriber about the dose."),
    ("simvastatin", "verapamil", "moderate", "Raises simvastatin levels. The simvastatin dose is usually capped.", "Ask the prescriber about the dose."),
    ("atorvastatin", "clarithromycin", "moderate", "Raises atorvastatin levels and the risk of muscle problems.", "Ask the prescriber whether to pause atorvastatin."),
    ("ace_inhibitor", "k_sparing", "major", "Risk of dangerously high potassium.", "Needs regular blood potassium checks."),
    ("arb", "k_sparing", "major", "Risk of dangerously high potassium.", "Needs regular blood potassium checks."),
    ("ace_inhibitor", "potassium", "major", "Risk of dangerously high potassium.", "Do not take potassium supplements unless prescribed."),
    ("arb", "potassium", "major", "Risk of dangerously high potassium.", "Do not take potassium supplements unless prescribed."),
    ("potassium", "k_sparing", "major", "Risk of dangerously high potassium.", "Avoid unless a doctor is monitoring your potassium."),
    ("ace_inhibitor", "arb", "moderate", "Using both increases the risk of kidney problems and high potassium.", "This combination is usually avoided."),
    ("ace_inhibitor", "nsaid", "moderate", "Anti-inflammatory painkillers can harm the kidneys and weaken the blood pressure medicine.", "Limit use and stay hydrated. Ask about alternatives."),
    ("arb", "nsaid", "moderate", "Anti-inflammatory painkillers can harm the kidneys and weaken the blood pressure medicine.", "Limit use and stay hydrated. Ask about alternatives."),
    ("pde5", "nitrate", "contraindicated", "Can cause a sudden, dangerous drop in blood pressure.", "Never take together. Seek urgent medical advice if both were taken."),
    ("digoxin", "amiodarone", "major", "Raises digoxin levels, which can cause toxicity.", "Digoxin doses usually need reducing and levels monitoring."),
    ("digoxin", "verapamil", "major", "Raises digoxin levels and can slow the heart too much.", "Needs close monitoring."),
    ("digoxin", "clarithromycin", "major", "Raises digoxin levels, which can cause toxicity.", "Tell the prescriber you take digoxin."),
    ("beta_blocker", "verapamil", "major", "Risk of a very slow heartbeat or heart block.", "Usually avoided. Only used under specialist care."),
    ("beta_blocker", "diltiazem", "major", "Risk of a very slow heartbeat or heart block.", "Usually avoided. Only used under specialist care."),
    ("lithium", "nsaid", "major", "Raises lithium levels and the risk of toxicity.", "Avoid anti-inflammatory painkillers or monitor lithium levels."),
    ("lithium", "ace_inhibitor", "major", "Raises lithium levels and the risk of toxicity.", "Needs lithium level monitoring."),
    ("lithium", "arb", "major", "Raises lithium levels and the risk of toxicity.", "Needs lithium level monitoring."),
    ("lithium", "thiazide", "major", "Raises lithium levels and the risk of toxicity.", "Needs lithium level monitoring."),
    ("ssri", "tramadol", "major", "Risk of serotonin syndrome, a dangerous reaction.", "Avoid unless a doctor directs otherwise."),
    ("ssri", "nsaid", "moderate", "Raises the risk of stomach and other bleeding.", "Ask about stomach protection or alternatives."),
    ("ssri", "aspirin", "moderate", "Raises the risk of bleeding.", "Ask your doctor about stomach protection."),
    ("ssri", "warfarin", "moderate", "Raises the risk of bleeding.", "Needs closer monitoring."),
    ("methotrexate", "nsaid", "major", "Can raise methotrexate levels and cause toxicity.", "Check with the prescriber before using painkillers."),
]


def normalise(name: str) -> str:
    text = re.sub(r"\b\d+(\.\d+)?\s*(mg|mcg|µg|g|ml|iu|units?)\b", " ", name.lower())
    text = re.sub(r"\b(tablets?|tabs?|capsules?|caps?|syrup|injection|er|sr|xl|cr|od|bd)\b", " ", text)
    text = re.sub(r"[^a-z ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return ALIASES.get(text, text)


def tags_for(name: str) -> Set[str]:
    tags = {name}
    for group, members in GROUPS.items():
        if name in members:
            tags.add(group)
    return tags


def known(name: str) -> bool:
    if tags_for(name) != {name}:
        return True
    return any(name in (a, b) for a, b, *_ in RULES)


def check(names: List[str]) -> dict:
    cleaned = []
    for original in names:
        normal = normalise(original)
        if normal and all(normal != c[1] for c in cleaned):
            cleaned.append((original, normal))
    findings, seen = [], set()
    for i in range(len(cleaned)):
        for j in range(i + 1, len(cleaned)):
            (oa, a), (ob, b) = cleaned[i], cleaned[j]
            ta, tb = tags_for(a), tags_for(b)
            for left, right, severity, effect, advice in RULES:
                if (left in ta and right in tb) or (left in tb and right in ta):
                    key = (a, b, left, right)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append({"medicines": [oa, ob], "severity": severity, "effect": effect, "advice": advice})
    order = {"contraindicated": 0, "major": 1, "moderate": 2}
    findings.sort(key=lambda f: order[f["severity"]])
    return {"interactions": findings, "not_covered": [o for o, n in cleaned if not known(n)],
            "note": "This list covers well-known interactions only and is not exhaustive. Always confirm with a pharmacist or doctor."}
