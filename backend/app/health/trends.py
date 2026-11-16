from datetime import date
from typing import List, Optional, Tuple

import numpy as np

from .biomarkers import TUMOUR_MARKERS, Biomarker, range_for, status_of

MIN_POINTS = 3
MIN_SPAN_DAYS = 60
DIRECTION_THRESHOLD = 0.10
TUMOUR_RISE = 0.30


def slope_per_month(points: List[Tuple[date, float]]) -> Optional[float]:
    if len(points) < 2:
        return None
    days = np.array([(d - points[0][0]).days for d, _ in points], dtype=float)
    values = np.array([v for _, v in points], dtype=float)
    first, second = np.triu_indices(len(points), k=1)
    gaps = days[second] - days[first]
    usable = gaps > 0
    if not usable.any():
        return None
    slopes = (values[second][usable] - values[first][usable]) / gaps[usable]
    return float(np.median(slopes) * 30.4375)


def direction_of(marker: Biomarker, slope: Optional[float], sex: Optional[str]) -> str:
    if slope is None:
        return "unknown"
    low, high = range_for(marker, sex)
    width = (high - low) or max(abs(high), 1.0)
    relative_per_year = slope * 12 / width
    if relative_per_year > DIRECTION_THRESHOLD:
        return "rising"
    if relative_per_year < -DIRECTION_THRESHOLD:
        return "falling"
    return "stable"


def trend_alert(marker: Biomarker, points: List[Tuple[date, float]], sex: Optional[str]) -> Optional[dict]:
    if marker.concern == "none" or not marker.watch_trend or len(points) < MIN_POINTS:
        return None
    if (points[-1][0] - points[0][0]).days < MIN_SPAN_DAYS:
        return None
    slope = slope_per_month(points)
    direction = direction_of(marker, slope, sex)
    if direction in ("unknown", "stable"):
        return None
    worsening = (direction == "rising" and marker.concern in ("high", "both")) or \
                (direction == "falling" and marker.concern in ("low", "both"))
    if not worsening:
        return None
    low, high = range_for(marker, sex)
    latest = points[-1][1]
    status = status_of(marker, latest, sex)
    months = (points[-1][0] - points[0][0]).days / 30.4375
    verb = "rising" if direction == "rising" else "falling"
    if status != "normal":
        return {"level": "warning", "message": f"{marker.label} is outside its typical range and still {verb} across {len(points)} results over {months:.0f} months."}
    projected = latest + slope * 12
    crosses = projected > high if direction == "rising" else projected < low
    consecutive = all(points[i + 1][1] > points[i][1] for i in range(len(points) - 1)) if direction == "rising" else \
        all(points[i + 1][1] < points[i][1] for i in range(len(points) - 1))
    if marker.key in TUMOUR_MARKERS and direction == "rising" and consecutive and points[0][1] > 0 and \
            (latest - points[0][1]) / points[0][1] >= TUMOUR_RISE:
        return {"level": "warning", "message": f"{marker.label} has risen at every one of the last {len(points)} checks (up {round((latest / points[0][1] - 1) * 100)}%). It is still within its typical range, but a steady rise is worth discussing with a doctor. This is not a diagnosis."}
    if crosses:
        return {"level": "watch", "message": f"{marker.label} is within its typical range but {verb} steadily over {months:.0f} months. If the trend continues it would leave the range within a year."}
    return None


def analyse(marker: Biomarker, points: List[Tuple[date, float]], sex: Optional[str]) -> dict:
    points = sorted(points)
    slope = slope_per_month(points)
    latest = points[-1][1] if points else None
    low, high = range_for(marker, sex)
    return {
        "key": marker.key, "label": marker.label, "unit": marker.unit, "category": marker.category,
        "low": None if marker.concern == "none" else low, "high": None if marker.concern == "none" else high,
        "points": [{"date": d.isoformat(), "value": v} for d, v in points],
        "latest": latest, "latest_date": points[-1][0].isoformat() if points else None,
        "status": status_of(marker, latest, sex) if latest is not None else "unknown",
        "slope_per_month": None if slope is None else round(slope, 4),
        "direction": direction_of(marker, slope, sex) if len(points) >= 2 else "unknown",
        "alert": trend_alert(marker, points, sex),
    }
