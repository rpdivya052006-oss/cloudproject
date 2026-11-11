
"""FoodBridge – AI-based food donation & redistribution platform (Streamlit)."""
import logging
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
import recommender as rec  # noqa: E402
import storage as sv  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("foodbridge")
st.set_page_config(page_title="FoodBridge", page_icon="🍲", layout="wide")

GREEN, ORANGE, DARK = "#1B8A4B", "#F58220", "#0F5132"
PALETTE = [GREEN, ORANGE, "#6CC48B", "#FFB36B", DARK, "#C25E00", "#9AD7B0"]
STATUS_COLORS = {"Available": GREEN, "Claimed": ORANGE, "Completed": DARK}
KG_PER_PACKET, CO2_PER_KG = 0.4, 2.5  # assumptions for the waste-reduction estimate

CSS = """<style>
.stApp{background:#F7FBF8}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#14733D,#1B8A4B)}
[data-testid="stSidebar"] *{color:#fff!important}
[data-testid="stSidebar"] .stButton button{background:#fff;border:0;font-weight:600}
[data-testid="stSidebar"] .stButton button *{color:#14733D!important}
.fb-hero{display:flex;justify-content:space-between;align-items:center;gap:1rem;color:#fff;padding:1.4rem 1.8rem;
 border-radius:18px;margin-bottom:1.2rem;background:linear-gradient(120deg,#1B8A4B 0%,#2FA862 62%,#F58220 150%)}
.fb-hero h1{color:#fff;margin:0;font-size:2rem}.fb-hero p{margin:.3rem 0 0;opacity:.95}
.fb-card{background:#fff;border-radius:14px;padding:1rem 1.2rem;border-left:6px solid #1B8A4B;box-shadow:0 2px 8px rgba(0,0,0,.06);margin-bottom:.6rem}
.fb-card.o{border-left-color:#F58220}.fb-card .v{font-size:1.8rem;font-weight:700;color:#14733D}
.fb-card.o .v{color:#D96A0B}.fb-card .l{font-size:.85rem;color:#5b6b61}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:#F58220;border:0;color:#fff;font-weight:600}
@media(max-width:768px){.fb-hero{flex-direction:column;text-align:center}.fb-hero h1{font-size:1.4rem}.fb-card .v{font-size:1.4rem}}
</style>"""
SVG = """<svg width="110" height="110" viewBox="0 0 120 120"><circle cx="60" cy="60" r="56" fill="#fff" opacity=".15"/>
<circle cx="60" cy="64" r="34" fill="#fff"/><circle cx="60" cy="64" r="24" fill="#F58220"/>
<path d="M60 78C38 62 46 48 60 58C74 48 82 62 60 78Z" fill="#fff"/>
<path d="M22 28v28M16 28v10a6 6 0 0 0 12 0V28M100 28c-8 8-8 22 0 28V28z" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round"/></svg>"""


@st.cache_resource
def init_store():
    store, warn = sv.get_store()
    if store.mode.startswith("Local") and not store.all("users"):
        sv.seed_sample(store)  # first run in demo mode → ready-to-test data
    return store, warn


STORE, WARN = init_store()


# ───────────── helpers ─────────────
def flash(kind, msg): st.session_state["_flash"] = (kind, msg)


def show_flash():
    f = st.session_state.pop("_flash", None)
    if f: getattr(st, f[0])(f[1])


def hero(title, sub): st.markdown(f'<div class="fb-hero"><div><h1>{title}</h1><p>{sub}</p></div>{SVG}</div>', unsafe_allow_html=True)


def card(label, value, orange=False):
    st.markdown(f'<div class="fb-card {"o" if orange else ""}"><div class="l">{label}</div><div class="v">{value}</div></div>', unsafe_allow_html=True)


COLS = ["donation_id", "donor_username", "donor_name", "food_name", "category", "quantity", "location", "address", "notes", "prep_time",
        "expiry_time", "image_keys", "doc_key", "status", "created_at", "claimed_by", "claimed_by_name", "claimed_at", "completed_at"]


def load_df():
    df = pd.DataFrame(STORE.all("donations")).reindex(columns=COLS)
    df["quantity"] = pd.to_numeric(df["quantity"]).fillna(0).astype(int)
    return df.sort_values("created_at", ascending=False).reset_index(drop=True)


def table(df):
    if df.empty: st.info("No donations to show."); return
    st.dataframe(pd.DataFrame({
        "Donation ID": df.donation_id, "Donor": df.donor_name, "Food": df.food_name, "Quantity": df.quantity, "Location": df.location,
        "Expiry": pd.to_datetime(df.expiry_time).dt.strftime("%d %b %Y, %I:%M %p"), "Status": df.status}), hide_index=True)


def my_ngo(): return STORE.get("ngos", st.session_state.user.get("ngo_id", ""))


def show_media(d):
    keys = d.get("image_keys") or []
    if keys:
        for c, k in zip(st.columns(len(keys)), keys):
            data = STORE.get_file(k)
            if data: c.image(data, width=200)
    if d.get("doc_key"):
        data = STORE.get_file(d["doc_key"])
        if data: st.download_button("📄 Supporting document", data, file_name=f"{d['donation_id']}.pdf", key=f"doc_{d['donation_id']}")


def safe(action, ok_msg=None):
    """Run an action with uniform success / failure notifications."""
    try:
        action()
        if ok_msg: flash("success", ok_msg)
    except (ValueError, PermissionError) as e:
        flash("error", f"⚠️ {e}")
    except Exception:
        log.exception("Unexpected error"); flash("error", "Something went wrong on the server. Please try again.")
    st.rerun()


# ───────────── pages ─────────────
def page_home():
    hero("FoodBridge", "Connecting surplus food with the people who need it – reducing waste, one packet at a time.")
    df = load_df()
    packets = int(df.loc[df.status.isin(["Claimed", "Completed"]), "quantity"].sum())
    c = st.columns(5)
    with c[0]: card("Total donations", len(df))
    with c[1]: card("Available food", int((df.status == "Available").sum()))
    with c[2]: card("Claimed donations", int((df.status == "Claimed").sum()), True)
    with c[3]: card("Packets redistributed", packets)
    with c[4]: card("Completed pickups", int((df.status == "Completed").sum()), True)
    kg = packets * KG_PER_PACKET
    st.subheader("🌱 Food waste reduction")
    w = st.columns(3)
    with w[0]: card("Food saved from waste", f"{kg:,.0f} kg")
    with w[1]: card("Meals provided", f"{packets:,}", True)
    with w[2]: card("CO₂e avoided (est.)", f"{kg * CO2_PER_KG:,.0f} kg")
    st.caption(f"Estimates assume 1 packet ≈ {KG_PER_PACKET} kg of food and ≈ {CO2_PER_KG} kg CO₂e per kg of food wasted.")
    live = [d for d in df.to_dict("records") if d["status"] == "Available" and rec.hours_left(d["expiry_time"]) > 0]
    live.sort(key=lambda d: rec.hours_left(d["expiry_time"]))
    st.subheader("⏰ Expiring soonest")
    if live:
        table(pd.DataFrame(live[:5]))
    else:
        st.info("No available donations right now.")
    if "user" not in st.session_state: st.info("👉 Open **Login / Register** in the sidebar to donate or claim food.")


def page_login():
    hero("Welcome to FoodBridge", "Log in or create an account as a Donor or an NGO.")
    t1, t2 = st.tabs(["🔐 Login", "📝 Register"])
    with t1, st.form("login"):
        u, p = st.text_input("Username"), st.text_input("Password", type="password")
        if st.form_submit_button("Login", type="primary"):
            if st.session_state.get("fails", 0) >= 5:
                st.error("Too many failed attempts in this session. Please refresh the page and try again.")
            elif (user := sv.login(STORE, u, p)):
                st.session_state.update(user=user, fails=0); st.session_state.pop("nav", None)
                flash("success", f"Welcome back, {user['display_name']}!"); st.rerun()
            else:
                st.session_state.fails = st.session_state.get("fails", 0) + 1; st.error("Invalid username or password.")
    with t2:
        role = st.radio("I am a…", ["Donor", "NGO"], horizontal=True)
        with st.form("register"):
            name = st.text_input("Organisation / full name")
            user = st.text_input("Username (lowercase letters, digits, _)")
            pw = st.text_input("Password (8+ chars, letters & digits)", type="password")
            loc, need, org = "", 50, ""
            if role == "NGO":
                loc = st.selectbox("Your location", list(rec.LOCATIONS))
                need = st.number_input("Packets you can use per day", 1, 5000, 100)
            else:
                org = st.selectbox("Donor type", ["Restaurant", "Hotel", "Supermarket", "Individual", "Other"])
            if st.form_submit_button("Create account", type="primary"):
                try:
                    sv.register(STORE, user, pw, role, name, loc, need, org)
                    st.success("Account created! Switch to the Login tab.")
                except ValueError as e:
                    st.error(f"⚠️ {e}")
                except Exception:
                    log.exception("register"); st.error("Could not create the account. Try again.")


def page_donate():
    hero("Donate Food", "Share surplus food – nearby NGOs will be notified instantly.")
    now = datetime.now()
    with st.form("donate", clear_on_submit=True):
        c1, c2 = st.columns(2)
        food = c1.text_input("Food name *")
        cat = c2.selectbox("Category *", sv.CATEGORIES)
        qty = c1.number_input("Quantity (packets) *", 1, 5000, 20)
        loc = c2.selectbox("Pickup area *", list(rec.LOCATIONS))
        pd_, pt = c1.date_input("Preparation date", now.date()), c1.time_input("Preparation time", (now - timedelta(minutes=30)).time())
        ed, et = c2.date_input("Expiry date", (now + timedelta(hours=4)).date()), c2.time_input("Expiry time", (now + timedelta(hours=4)).time())
        addr = st.text_input("Street address / landmark")
        notes = st.text_area("Notes (optional)", max_chars=300)
        imgs = st.file_uploader("Food images (PNG/JPG, ≤5 MB, max 3)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        doc = st.file_uploader("Supporting document (PDF, optional)", type=["pdf"])
        if st.form_submit_button("Submit donation", type="primary"):
            try:
                d = sv.create_donation(STORE, st.session_state.user, {
                    "food_name": food, "category": cat, "quantity": qty, "location": loc, "address": addr, "notes": notes,
                    "prep_time": datetime.combine(pd_, pt), "expiry_time": datetime.combine(ed, et)},
                    [(f.name, f.getvalue()) for f in imgs], (doc.name, doc.getvalue()) if doc else None)
                st.success(f"✅ Donation {d['donation_id']} saved. Top NGO matches:")
                top = rec.recommend_ngos(d, STORE.all("ngos"))[:3]
                st.dataframe(pd.DataFrame(top)[["ngo", "location", "km", "eta_min", "score"]], hide_index=True)
            except (ValueError, PermissionError) as e:
                st.error(f"⚠️ {e}")
            except Exception:
                log.exception("donate"); st.error("Could not save the donation. Please try again.")


def page_my_donations():
    hero("My Donations", "Track the status of everything you have shared.")
    df = load_df(); df = df[df.donor_username == st.session_state.user["username"]]
    table(df)
    for d in df.to_dict("records"):
        with st.expander(f"{d['donation_id']} · {d['food_name']} · {d['status']}"):
            st.write(f"📍 {d['location']} {d['address']}  |  🍱 {d['quantity']} packets  |  ⏳ {rec.fmt_left(rec.hours_left(d['expiry_time']))}")
            if d["claimed_by_name"]: st.write(f"🤝 Claimed by **{d['claimed_by_name']}**")
            show_media(d)


def page_available():
    hero("Available Food", "AI-ranked donations near you. Claim before they expire.")
    ngo = my_ngo()
    if not ngo: st.error("NGO profile not found."); return
    don = {d["donation_id"]: d for d in STORE.all("donations")}
    ranked = rec.recommend_donations(ngo, list(don.values()))
    c1, c2, c3 = st.columns([2, 2, 2])
    q = c1.text_input("🔎 Search by location / food").strip().lower()
    cats = c2.multiselect("Category", sv.CATEGORIES)
    sort = c3.selectbox("Sort by", ["AI priority", "Soonest expiry", "Nearest"])
    ranked = [r for r in ranked if (not q or q in (r["location"] + don[r["donation_id"]]["address"] + r["food_name"]).lower())
              and (not cats or don[r["donation_id"]]["category"] in cats)]
    if sort == "Soonest expiry": ranked.sort(key=lambda r: r["hours_left"])
    if sort == "Nearest": ranked.sort(key=lambda r: r["km"])
    if not ranked: st.info("No matching donations right now."); return
    for r in ranked[:30]:
        d = don[r["donation_id"]]
        with st.container(border=True):
            a, b = st.columns([4, 1])
            a.markdown(f"**{d['food_name']}** · {d['category']} · 🍱 {d['quantity']} packets  \n"
                       f"📍 {d['location']} ({r['km']} km) · ⏳ {rec.fmt_left(r['hours_left'])} left · {r['urgency']} · AI score {r['score']}")
            if b.button("Claim", key=f"claim_{d['donation_id']}", type="primary"):
                safe(lambda: sv.claim_donation(STORE, st.session_state.user, d["donation_id"]),
                     f"✅ Claimed {d['food_name']} – please collect before {d['expiry_time'].replace('T', ' ')}.")
            if d["address"] or d["notes"] or d["image_keys"] or d["doc_key"]:
                with st.expander("Details & photos"):
                    st.write(f"Donor: {d['donor_name']}  \nAddress: {d['address'] or '—'}  \nNotes: {d['notes'] or '—'}"); show_media(d)


def page_history():
    hero("Claim History", "Everything your NGO has claimed.")
    df = load_df(); df = df[df.claimed_by == st.session_state.user.get("ngo_id")]
    table(df)
    for d in df[df.status == "Claimed"].to_dict("records"):
        if st.button(f"✔ Mark {d['donation_id']} ({d['food_name']}) as collected", key=f"done_{d['donation_id']}"):
            safe(lambda: sv.complete_donation(STORE, st.session_state.user, d["donation_id"]), "✅ Marked as completed.")


def page_ai():
    hero("AI Recommendations", "Transparent scoring: urgency, distance and quantity match.")
    u = st.session_state.user
    if u["role"] == "NGO":
        ngo = my_ngo()
        rows = rec.recommend_donations(ngo, STORE.all("donations"))
        st.subheader(f"Best donations for {ngo['name']} ({ngo['location']}, needs ~{ngo['daily_need']} packets/day)")
        if rows:
            df = pd.DataFrame(rows).assign(**{"time left": [rec.fmt_left(r["hours_left"]) for r in rows]})
            st.dataframe(df[["food_name", "quantity", "location", "km", "time left", "urgency", "match", "score"]], hide_index=True,
                         column_config={"score": st.column_config.ProgressColumn("AI score", min_value=0, max_value=1)})
        else:
            st.info("No available donations to rank.")
    else:
        df = load_df(); df = df[df.status == "Available"]
        if u["role"] == "Donor": df = df[df.donor_username == u["username"]]
        recs = {d["donation_id"]: d for d in df.to_dict("records") if rec.hours_left(d["expiry_time"]) > 0}
        if not recs: st.info("No available donations to match."); return
        pick = st.selectbox("Donation", list(recs), format_func=lambda i: f"{i} · {recs[i]['food_name']} ({recs[i]['quantity']} packets, {recs[i]['location']})")
        rows = rec.recommend_ngos(recs[pick], STORE.all("ngos"))
        out = pd.DataFrame(rows)
        st.dataframe(out[["ngo", "location", "km", "daily_need", "eta_min", "reachable", "score"]], hide_index=True,
                     column_config={"score": st.column_config.ProgressColumn("AI score", min_value=0, max_value=1)})
        st.plotly_chart(px.bar(out.head(6), x="ngo", y="score", color_discrete_sequence=[GREEN], title="Top NGO matches"))
    with st.expander("How the algorithm works"):
        st.markdown("""* **Urgency** = `1 / (1 + hours_left / 4)` → food about to expire scores highest; expired food is excluded.
* **Proximity** = `1 / (1 + km / 5)` using Haversine distance between areas.
* **Quantity match** = `min(qty, need) / max(qty, need)` against the NGO's daily requirement.
* **Donations for an NGO:** `0.45·urgency + 0.30·proximity + 0.25·match`.
* **NGOs for a donation:** `0.55·proximity + 0.45·match`; NGOs that cannot arrive before expiry (≈20 km/h + 15 min) get ×0.3.""")


def page_admin_donations():
    hero("Donation Management", "All donations across the platform.")
    df = load_df()
    s = st.multiselect("Filter by status", sv.STATUSES, default=sv.STATUSES)
    df = df[df.status.isin(s)]
    table(df)
    st.download_button("⬇ Export CSV", df.drop(columns=["image_keys"]).to_csv(index=False), "donations.csv", "text/csv")
    if not df.empty:
        with st.form("status"):
            c1, c2 = st.columns(2)
            did, new = c1.selectbox("Donation", df.donation_id), c2.selectbox("New status", sv.STATUSES)
            if st.form_submit_button("Update status", type="primary"):
                safe(lambda: sv.admin_set_status(STORE, st.session_state.user, did, new), f"✅ {did} → {new}")


def page_users():
    hero("Users & NGOs", "Registered accounts and NGO profiles.")
    users = pd.DataFrame(STORE.all("users"))
    if not users.empty: st.dataframe(users.drop(columns=["password_hash"], errors="ignore"), hide_index=True)
    st.subheader("NGOs"); st.dataframe(pd.DataFrame(STORE.all("ngos")), hide_index=True)
    if st.button("Load sample data (demo accounts, NGOs & donations)"):
        safe(lambda: sv.seed_sample(STORE), "✅ Sample data loaded. Demo logins: admin/Admin@123, demo_donor/Donor@123, demo_ngo/Ngo@1234 – change or remove these before real use.")


def page_analytics():
    hero("Analytics", "Interactive insights into donations and redistribution.")
    df = load_df()
    if df.empty: st.info("No data yet."); return
    redistributed = int(df.loc[df.status.isin(["Claimed", "Completed"]), "quantity"].sum())
    c = st.columns(4)
    with c[0]: card("Total donations", len(df))
    with c[1]: card("Packets donated", int(df.quantity.sum()), True)
    with c[2]: card("Total redistributed", redistributed)
    with c[3]: card("Claim rate", f"{100 * (df.status != 'Available').mean():.0f}%", True)
    a, b = st.columns(2)
    cat = df.groupby("category", as_index=False).quantity.sum()
    a.plotly_chart(px.pie(cat, names="category", values="quantity", hole=.5, color_discrete_sequence=PALETTE, title="Food category distribution (packets)"))
    sc = df.groupby("status", as_index=False).agg(donations=("donation_id", "count"))
    b.plotly_chart(px.bar(sc, x="status", y="donations", color="status", color_discrete_map=STATUS_COLORS, title="Available vs claimed vs completed"))
    day = df.assign(day=pd.to_datetime(df.created_at).dt.date).groupby("day", as_index=False).agg(donations=("donation_id", "count"), packets=("quantity", "sum"))
    st.plotly_chart(px.line(day, x="day", y=["donations", "packets"], markers=True, color_discrete_sequence=[GREEN, ORANGE], title="Daily donation trend"))
    top = df.groupby("donor_name", as_index=False).quantity.sum().nlargest(8, "quantity")
    st.plotly_chart(px.bar(top, x="quantity", y="donor_name", orientation="h", color_discrete_sequence=[GREEN], title="Top donors (packets)"))


# ───────────── navigation ─────────────
PAGES = {"🏠 Home": page_home, "🔐 Login / Register": page_login, "➕ Donate Food": page_donate, "📦 My Donations": page_my_donations,
         "🍽️ Available Food": page_available, "📜 Claim History": page_history, "🤖 AI Recommendations": page_ai,
         "📊 Analytics": page_analytics, "🗂️ All Donations": page_admin_donations, "👥 Users & NGOs": page_users}
MENU = {"Donor": ["🏠 Home", "➕ Donate Food", "📦 My Donations", "🤖 AI Recommendations", "📊 Analytics"],
        "NGO": ["🏠 Home", "🍽️ Available Food", "📜 Claim History", "🤖 AI Recommendations", "📊 Analytics"],
        "Admin": ["🏠 Home", "🗂️ All Donations", "🤖 AI Recommendations", "📊 Analytics", "👥 Users & NGOs"],
        None: ["🏠 Home", "🔐 Login / Register"]}


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    user = st.session_state.get("user")
    with st.sidebar:
        st.markdown("## 🍲 FoodBridge")
        st.caption(("☁️ " if STORE.mode.startswith("AWS") else "💻 ") + STORE.mode)
        if user: st.markdown(f"**{user['display_name']}**  \n`{user['role']}`")
        page = st.radio("Navigate", MENU[user["role"] if user else None], key="nav", label_visibility="collapsed")
        if user and st.button("Logout"):
            st.session_state.pop("user"); st.session_state.pop("nav", None); st.rerun()
    if WARN: st.warning(WARN)
    show_flash()
    PAGES[page]()


main()

