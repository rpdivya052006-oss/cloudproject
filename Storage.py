"""FoodBridge data layer: AWS (DynamoDB + S3 via boto3) with a local-JSON demo fallback, plus business rules."""
import hashlib, hmac, json, logging, os, random, re, threading, uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from recommender import LOCATIONS

log = logging.getLogger("foodbridge")
KEYS = {"users": "username", "donations": "donation_id", "ngos": "ngo_id"}
DEFAULT_TABLES = {"users": "FoodBridge_Users", "donations": "FoodBridge_Donations", "ngos": "FoodBridge_NGOs"}
CATEGORIES = ["Cooked Meals", "Bakery", "Fruits & Vegetables", "Packaged Food", "Dairy", "Beverages", "Other"]
STATUSES = ["Available", "Claimed", "Completed"]
MAGIC = {"png": b"\x89PNG\r\n\x1a\n", "jpg": b"\xff\xd8\xff", "jpeg": b"\xff\xd8\xff", "pdf": b"%PDF"}


def table_name(t): return os.getenv(f"DDB_{t.upper()}_TABLE", DEFAULT_TABLES[t])
def now_iso(): return datetime.now().isoformat(timespec="minutes")
def _to_ddb(o): return json.loads(json.dumps(o), parse_float=Decimal)  # DynamoDB has no float type


def _from_ddb(o):
    if isinstance(o, Decimal): return int(o) if o == o.to_integral_value() else float(o)
    if isinstance(o, list): return [_from_ddb(i) for i in o]
    if isinstance(o, dict): return {k: _from_ddb(v) for k, v in o.items()}
    return o


# ───────────────────────── Stores ─────────────────────────
class LocalStore:
    """Demo mode: JSON file + local folder. Data persists across restarts."""
    mode = "Local demo mode"

    def __init__(self):
        self.dir = Path(os.getenv("FOODBRIDGE_DATA_DIR", "data"))
        (self.dir / "uploads").mkdir(parents=True, exist_ok=True)
        self.db, self.lock = self.dir / "local_db.json", threading.RLock()
        if not self.db.exists():
            self._save({"users": {}, "donations": {}, "ngos": {}})

    def _load(self): return json.loads(self.db.read_text(encoding="utf-8"))

    def _save(self, d):
        tmp = self.db.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
        os.replace(tmp, self.db)

    def get(self, t, k):
        with self.lock: return self._load()[t].get(k)

    def put(self, t, item):
        with self.lock:
            d = self._load(); d[t][item[KEYS[t]]] = item; self._save(d)

    def all(self, t):
        with self.lock: return list(self._load()[t].values())

    def claim(self, did, ngo_id, ngo_name) -> bool:
        with self.lock:
            d = self._load(); r = d["donations"].get(did)
            if not r or r["status"] != "Available": return False
            r.update(status="Claimed", claimed_by=ngo_id, claimed_by_name=ngo_name, claimed_at=now_iso())
            self._save(d); return True

    def put_file(self, key, data):
        p = self.dir / "uploads" / key; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)

    def get_file(self, key):
        base, p = (self.dir / "uploads").resolve(), (self.dir / "uploads" / key).resolve()
        return p.read_bytes() if base in p.parents and p.exists() else None


class AwsStore:
    """Real AWS: DynamoDB tables + private S3 bucket. Credentials come from env vars / AWS profile / IAM role."""
    mode = "AWS (S3 + DynamoDB)"

    def __init__(self, region, bucket):
        import boto3
        s = boto3.session.Session(region_name=region)
        self.s3, self.bucket = s.client("s3"), bucket
        self.tables = {t: s.resource("dynamodb").Table(table_name(t)) for t in KEYS}
        for tb in self.tables.values(): tb.load()  # raises if table is missing / no permission
        self.s3.head_bucket(Bucket=bucket)

    def get(self, t, k):
        r = self.tables[t].get_item(Key={KEYS[t]: k}).get("Item")
        return _from_ddb(r) if r else None

    def put(self, t, item): self.tables[t].put_item(Item=_to_ddb(item))

    def all(self, t):
        items, kw = [], {}
        while True:
            r = self.tables[t].scan(**kw); items += r["Items"]
            if "LastEvaluatedKey" not in r: return _from_ddb(items)
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def claim(self, did, ngo_id, ngo_name) -> bool:
        from botocore.exceptions import ClientError
        try:  # conditional write → two NGOs can never claim the same donation
            self.tables["donations"].update_item(
                Key={"donation_id": did}, ConditionExpression="#s = :a",
                UpdateExpression="SET #s=:c, claimed_by=:i, claimed_by_name=:n, claimed_at=:t",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":a": "Available", ":c": "Claimed", ":i": ngo_id, ":n": ngo_name, ":t": now_iso()})
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException": return False
            raise

    def put_file(self, key, data):  # bucket stays private; encrypted at rest
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")

    def get_file(self, key):
        try: return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception: log.warning("S3 read failed for %s", key); return None


def get_store():
    """Returns (store, warning). Falls back to local demo mode if AWS is off or unreachable."""
    if os.getenv("USE_AWS", "false").lower() == "true":
        try:
            return AwsStore(os.getenv("AWS_REGION", "ap-south-1"), os.environ["S3_BUCKET_NAME"]), None
        except Exception as e:
            log.exception("AWS init failed")
            return LocalStore(), f"AWS not reachable ({type(e).__name__}) – running in local demo mode."
    return LocalStore(), None


# ───────────────────────── Auth ─────────────────────────
def hash_pw(pw, salt=None):
    salt = salt or os.urandom(16)
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000).hex()


def check_pw(pw, stored):
    salt, h = stored.split("$")
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex(), h)


def register(store, username, password, role, display_name, location="", daily_need=50, org_type=""):
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,20}", username): raise ValueError("Username: 3–20 chars, lowercase letters, digits or _.")
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password needs 8+ characters with letters and digits.")
    if role not in ("Donor", "NGO"): raise ValueError("Invalid role.")
    if not display_name.strip(): raise ValueError("Name is required.")
    if store.get("users", username): raise ValueError("That username is already taken.")
    user = {"username": username, "password_hash": hash_pw(password), "role": role,
            "display_name": display_name.strip()[:80], "created_at": now_iso()}
    if role == "NGO":
        if location not in LOCATIONS: raise ValueError("Select a valid location.")
        user["ngo_id"] = f"NGO-{username}"
        store.put("ngos", {"ngo_id": user["ngo_id"], "name": user["display_name"], "location": location,
                           "daily_need": int(daily_need), "owner": username, "created_at": now_iso()})
    else:
        user["org_type"] = org_type
    store.put("users", user)
    return user


def login(store, username, password):
    u = store.get("users", username.strip().lower())
    ok = check_pw(password, u["password_hash"]) if u else check_pw(password, hash_pw("x"))  # constant-ish time
    return {k: v for k, v in u.items() if k != "password_hash"} if (u and ok) else None


# ───────────────────────── Donations ─────────────────────────
def validate_upload(name, data, allowed, max_mb=5):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in allowed: raise ValueError(f"'{name}': only {', '.join(allowed)} files are allowed.")
    if len(data) > max_mb * 1024 * 1024: raise ValueError(f"'{name}' is larger than {max_mb} MB.")
    if not data.startswith(MAGIC[ext]): raise ValueError(f"'{name}' content does not match its file type.")
    return ext


def create_donation(store, user, f, images=(), doc=None):
    """f: dict with food_name, category, quantity, prep_time, expiry_time (datetime), location, address, notes."""
    if user["role"] != "Donor": raise PermissionError("Only donors can submit donations.")
    name = f["food_name"].strip()
    if not 2 <= len(name) <= 80: raise ValueError("Food name must be 2–80 characters.")
    if f["category"] not in CATEGORIES: raise ValueError("Select a valid category.")
    qty = int(f["quantity"])
    if not 1 <= qty <= 5000: raise ValueError("Quantity must be between 1 and 5000 packets.")
    if f["location"] not in LOCATIONS: raise ValueError("Select a pickup location.")
    prep, exp, now = f["prep_time"], f["expiry_time"], datetime.now()
    if exp <= prep: raise ValueError("Expiry must be after the preparation time.")
    if exp <= now: raise ValueError("Expiry time is already in the past.")
    if prep > now + timedelta(minutes=5): raise ValueError("Preparation time cannot be in the future.")
    if len(images) > 3: raise ValueError("Upload at most 3 images.")
    checked = [(n, d, validate_upload(n, d, ("png", "jpg", "jpeg"))) for n, d in images]
    if doc: doc = (doc[0], doc[1], validate_upload(doc[0], doc[1], ("pdf",)))
    did = f"DON-{uuid.uuid4().hex[:8].upper()}"
    image_keys = []
    for _, data, ext in checked:
        k = f"images/{did}/{uuid.uuid4().hex}.{ext}"; store.put_file(k, data); image_keys.append(k)
    doc_key = ""
    if doc: doc_key = f"documents/{did}/{uuid.uuid4().hex}.pdf"; store.put_file(doc_key, doc[1])
    rec = {"donation_id": did, "donor_username": user["username"], "donor_name": user["display_name"],
           "food_name": name, "category": f["category"], "quantity": qty, "location": f["location"],
           "address": f.get("address", "").strip()[:200], "notes": f.get("notes", "").strip()[:300],
           "prep_time": prep.isoformat(timespec="minutes"), "expiry_time": exp.isoformat(timespec="minutes"),
           "image_keys": image_keys, "doc_key": doc_key, "status": "Available", "created_at": now_iso(),
           "claimed_by": "", "claimed_by_name": "", "claimed_at": "", "completed_at": ""}
    store.put("donations", rec)
    return rec


def claim_donation(store, user, did):
    if user["role"] != "NGO": raise PermissionError("Only NGOs can claim food.")
    d = store.get("donations", did)
    if not d: raise ValueError("Donation not found.")
    if datetime.fromisoformat(d["expiry_time"]) <= datetime.now(): raise ValueError("This food has expired and cannot be claimed.")
    ngo = store.get("ngos", user["ngo_id"])
    if not store.claim(did, ngo["ngo_id"], ngo["name"]): raise ValueError("Sorry – this donation was just claimed by someone else.")


def complete_donation(store, user, did):
    d = store.get("donations", did)
    if not d or d["status"] != "Claimed": raise ValueError("Only claimed donations can be completed.")
    if user["role"] == "NGO" and d["claimed_by"] != user.get("ngo_id"): raise PermissionError("This donation was claimed by another NGO.")
    if user["role"] == "Donor": raise PermissionError("Not allowed.")
    d.update(status="Completed", completed_at=now_iso()); store.put("donations", d)


def admin_set_status(store, user, did, status):
    if user["role"] != "Admin": raise PermissionError("Admins only.")
    if status not in STATUSES: raise ValueError("Invalid status.")
    d = store.get("donations", did)
    if not d: raise ValueError("Donation not found.")
    d["status"] = status
    if status == "Available": d.update(claimed_by="", claimed_by_name="", claimed_at="", completed_at="")
    if status == "Completed": d["completed_at"] = now_iso()
    store.put("donations", d)


# ───────────────────────── Sample data ─────────────────────────
_SAMPLE = [("Veg Biryani", "Cooked Meals", 60, "Adyar", "Green Leaf Restaurant"),
           ("Sambar Rice", "Cooked Meals", 120, "T. Nagar", "Hotel Marina Palace"),
           ("Bread Loaves", "Bakery", 40, "Anna Nagar", "Sunrise Bakery"),
           ("Mixed Vegetables", "Fruits & Vegetables", 35, "Velachery", "FreshMart Supermarket"),
           ("Fruit Boxes", "Fruits & Vegetables", 50, "Mylapore", "FreshMart Supermarket"),
           ("Curd Rice Packs", "Cooked Meals", 80, "Guindy", "Hotel Marina Palace"),
           ("Biscuit Cartons", "Packaged Food", 100, "Porur", "FreshMart Supermarket"),
           ("Milk Packets", "Dairy", 45, "Perambur", "Dairy Fresh Store"),
           ("Chapati & Kurma", "Cooked Meals", 90, "Tambaram", "Green Leaf Restaurant"),
           ("Buns & Cakes", "Bakery", 30, "Egmore", "Sunrise Bakery"),
           ("Juice Bottles", "Beverages", 70, "Sholinganallur", "FreshMart Supermarket"),
           ("Lemon Rice", "Cooked Meals", 55, "Chromepet", "Hotel Marina Palace")]
_NGOS = [("NGO-hope-kitchen", "Hope Community Kitchen", "Tambaram", 200), ("NGO-seva-trust", "Seva Food Trust", "Anna Nagar", 80),
         ("NGO-asha-home", "Asha Children's Home", "Adyar", 60), ("NGO-annadhanam", "Annadhanam Foundation", "Velachery", 150),
         ("NGO-care-shelter", "Care Night Shelter", "Egmore", 90)]


def seed_sample(store):
    """Idempotent demo data: 3 demo logins, 6 NGOs, 22 donations (8 available, rest claimed/completed over 6 days)."""
    if not store.get("users", "admin"):
        store.put("users", {"username": "admin", "password_hash": hash_pw("Admin@123"), "role": "Admin",
                            "display_name": "FoodBridge Admin", "created_at": now_iso()})
    if not store.get("users", "demo_donor"): register(store, "demo_donor", "Donor@123", "Donor", "Demo Donor", org_type="Restaurant")
    if not store.get("users", "demo_ngo"): register(store, "demo_ngo", "Ngo@1234", "NGO", "Anbu Illam Trust", "Guindy", 120)
    for i, n, loc, need in _NGOS:
        if not store.get("ngos", i): store.put("ngos", {"ngo_id": i, "name": n, "location": loc, "daily_need": need, "owner": "", "created_at": now_iso()})
    if store.all("donations"): return
    rnd, now, ngos = random.Random(7), datetime.now(), store.all("ngos")
    for i in range(22):
        food, cat, qty, loc, donor = _SAMPLE[i % 12]
        mine = i % 4 == 0
        avail = i < 8
        created = now - timedelta(hours=rnd.uniform(0.5, 5)) if avail else now - timedelta(days=1 + i % 6, hours=rnd.uniform(0, 6))
        exp = now + timedelta(hours=rnd.uniform(1.5, 20)) if avail else created + timedelta(hours=5)
        status = "Available" if avail else ("Completed" if i % 3 else "Claimed")
        n = rnd.choice(ngos)
        store.put("donations", {
            "donation_id": f"DON-SAMPLE{i:02d}", "donor_username": "demo_donor" if mine else "seed_donor",
            "donor_name": "Demo Donor" if mine else donor, "food_name": food, "category": cat, "quantity": qty + rnd.randint(-5, 10),
            "location": loc, "address": "", "notes": "Sample record", "prep_time": (created - timedelta(hours=1)).isoformat(timespec="minutes"),
            "expiry_time": exp.isoformat(timespec="minutes"), "image_keys": [], "doc_key": "", "status": status,
            "created_at": created.isoformat(timespec="minutes"),
            "claimed_by": "" if avail else n["ngo_id"], "claimed_by_name": "" if avail else n["name"],
            "claimed_at": "" if avail else (created + timedelta(hours=1)).isoformat(timespec="minutes"),
            "completed_at": (created + timedelta(hours=2)).isoformat(timespec="minutes") if status == "Completed" else ""})
