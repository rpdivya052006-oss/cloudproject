"""FoodBridge recommendation engine."""
import math
from datetime import datetime

LOCATIONS = {
    "Adyar": (13.0067, 80.2570), "Anna Nagar": (13.0850, 80.2101),
    "Chromepet": (12.9516, 80.1462), "Egmore": (13.0732, 80.2609),
    "Guindy": (13.0067, 80.2206), "Kilpauk": (13.0827, 80.2420),
    "Mylapore": (13.0368, 80.2676), "Perambur": (13.1186, 80.2328),
    "Porur": (13.0382, 80.1565), "Sholinganallur": (12.9010, 80.2279),
    "T. Nagar": (13.0418, 80.2341), "Tambaram": (12.9249, 80.1000),
    "Vandalur": (12.8920, 80.0810), "Velachery": (12.9815, 80.2180),
}

def distance_km(a: str, b: str) -> float:
    if a not in LOCATIONS or b not in LOCATIONS:
        raise ValueError(f"Unsupported location: {a} or {b}")
    (lat1, lon1), (lat2, lon2) = LOCATIONS[a], LOCATIONS[b]
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (math.sin((p2-p1)/2)**2
         + math.cos(p1)*math.cos(p2)
         * math.sin(math.radians(lon2-lon1)/2)**2)
    return 2 * 6371 * math.asin(math.sqrt(h))

def _hours_left(expiry_iso: str, now=None) -> float:
    expiry = datetime.fromisoformat(expiry_iso)
    current = now or datetime.now()
    # Keep both timestamps comparable if one has timezone data and the other doesn't.
    if expiry.tzinfo and current.tzinfo is None:
        current = current.replace(tzinfo=expiry.tzinfo)
    elif current.tzinfo and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=current.tzinfo)
    return (expiry - current).total_seconds() / 3600

def urgency_score(hours: float) -> float:
    return 0.0 if hours <= 0 else 1 / (1 + hours / 4)

def urgency_label(hours: float) -> str:
    if hours <= 0: return "Expired"
    if hours <= 3: return "Critical"
    if hours <= 8: return "High"
    if hours <= 24: return "Medium"
    return "Low"

def qty_match(quantity: float, need: float) -> float:
    return min(quantity, need) / max(quantity, need, 1)

def recommend_donations(ngo: dict, donations: list[dict], now=None) -> list[dict]:
    results = []
    for donation in donations:
        if donation.get("status") != "Available":
            continue
        hours = _hours_left(donation["expiry_time"], now)
        if hours <= 0:
            continue
        try:
            km = distance_km(ngo["location"], donation["location"])
        except ValueError:
            continue
        urgency = urgency_score(hours)
        proximity = 1 / (1 + km / 5)
        match = qty_match(float(donation["quantity"]), float(ngo["daily_need"]))
        score = 0.45 * urgency + 0.30 * proximity + 0.25 * match
        results.append({
            "donation_id": donation["donation_id"],
            "food_name": donation["food_name"],
            "quantity": donation["quantity"],
            "location": donation["location"],
            "km": round(km, 1),
            "hours_left": round(hours, 1),
            "urgency": urgency_label(hours),
            "match": round(match, 2),
            "score": round(score, 3),
        })
    return sorted(results, key=lambda row: row["score"], reverse=True)

def recommend_ngos(donation: dict, ngos: list[dict], now=None) -> list[dict]:
    hours = _hours_left(donation["expiry_time"], now)
    results = []
    if hours <= 0:
        return results
    for ngo in ngos:
        try:
            km = distance_km(ngo["location"], donation["location"])
        except ValueError:
            continue
        eta_hours = km / 20 + 0.25
        reachable = eta_hours < hours
        proximity = 1 / (1 + km / 5)
        match = qty_match(float(donation["quantity"]), float(ngo["daily_need"]))
        score = 0.55 * proximity + 0.45 * match
        if not reachable:
            score *= 0.3
        results.append({
            "ngo_id": ngo["ngo_id"], "ngo": ngo["name"],
            "location": ngo["location"], "km": round(km, 1),
            "daily_need": ngo["daily_need"],
            "eta_min": round(eta_hours * 60),
            "reachable": reachable, "score": round(score, 3),
        })
    return sorted(results, key=lambda row: row["score"], reverse=True)
