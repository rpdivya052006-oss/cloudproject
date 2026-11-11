"""FoodBridge AI recommendation engine (transparent weighted scoring, no external services)."""
import math
from datetime import datetime

# Approximate coordinates of Chennai areas (used for distance-based matching)
LOCATIONS = {
    "Adyar": (13.0067, 80.2570), "Anna Nagar": (13.0850, 80.2101), "Chromepet": (12.9516, 80.1462),
    "Egmore": (13.0732, 80.2609), "Guindy": (13.0067, 80.2206), "Kilpauk": (13.0827, 80.2420),
    "Mylapore": (13.0368, 80.2676), "Perambur": (13.1186, 80.2328), "Porur": (13.0382, 80.1565),
    "Sholinganallur": (12.9010, 80.2279), "T. Nagar": (13.0418, 80.2341), "Tambaram": (12.9249, 80.1000),
    "Vandalur": (12.8920, 80.0810), "Velachery": (12.9815, 80.2180),
}


def distance_km(a: str, b: str) -> float:
    """Haversine distance between two named locations."""
    (la1, lo1), (la2, lo2) = LOCATIONS[a], LOCATIONS[b]
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def hours_left(expiry_iso: str, now: datetime | None = None) -> float:
    return (datetime.fromisoformat(expiry_iso) - (now or datetime.now())).total_seconds() / 3600


def urgency_score(h: float) -> float:
    """1.0 = about to expire, decays smoothly; 0 once expired."""
    return 0.0 if h <= 0 else 1 / (1 + h / 4)


def urgency_label(h: float) -> str:
    if h <= 0: return "⚫ Expired"
    if h <= 3: return "🔴 Critical"
    if h <= 8: return "🟠 High"
    if h <= 24: return "🟡 Medium"
    return "🟢 Low"


def fmt_left(h: float) -> str:
    if h <= 0: return "Expired"
    return f"{int(h)}h {int((h % 1) * 60)}m" if h < 48 else f"{int(h // 24)}d"


def qty_match(qty: float, need: float) -> float:
    """1.0 when the donation exactly fits the NGO's daily requirement."""
    return min(qty, need) / max(qty, need, 1)


def recommend_donations(ngo: dict, donations: list[dict], now: datetime | None = None) -> list[dict]:
    """Rank available donations for an NGO: 45% urgency + 30% proximity + 25% quantity match."""
    rows = []
    for d in donations:
        if d["status"] != "Available":
            continue
        h = hours_left(d["expiry_time"], now)
        if h <= 0:
            continue
        km = distance_km(ngo["location"], d["location"])
        u, p, m = urgency_score(h), 1 / (1 + km / 5), qty_match(d["quantity"], ngo["daily_need"])
        rows.append({"donation_id": d["donation_id"], "food_name": d["food_name"], "quantity": d["quantity"],
                     "location": d["location"], "km": round(km, 1), "hours_left": h, "urgency": urgency_label(h),
                     "match": round(m, 2), "score": round(0.45 * u + 0.30 * p + 0.25 * m, 3)})
    return sorted(rows, key=lambda r: -r["score"])


def recommend_ngos(donation: dict, ngos: list[dict], now: datetime | None = None) -> list[dict]:
    """Rank NGOs for a donation: 55% proximity + 45% quantity match; NGOs that cannot arrive before expiry are penalised."""
    h = hours_left(donation["expiry_time"], now)
    rows = []
    for n in ngos:
        km = distance_km(n["location"], donation["location"])
        eta_h = km / 20 + 0.25  # ~20 km/h city speed + 15 min handling
        reachable = eta_h < h
        score = 0.55 * (1 / (1 + km / 5)) + 0.45 * qty_match(donation["quantity"], n["daily_need"])
        rows.append({"ngo_id": n["ngo_id"], "ngo": n["name"], "location": n["location"], "km": round(km, 1),
                     "daily_need": n["daily_need"], "eta_min": round(eta_h * 60), "reachable": reachable,
                     "score": round(score if reachable else score * 0.3, 3)})
    return sorted(rows, key=lambda r: -r["score"])
