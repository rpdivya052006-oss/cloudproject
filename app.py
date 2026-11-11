
import os
import uuid
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import recommender as rec
from storage import get_storage

st.set_page_config(page_title="FoodBridge", page_icon="🍱", layout="wide")

st.markdown("""
<style>
.main {background-color: #f7faf7;}
.block-container {padding-top: 1.5rem; max-width: 1200px;}
.hero {padding: 1.5rem; border-radius: 16px; background: linear-gradient(120deg,#14532d,#16a34a); color: white;}
div[data-testid="stMetric"] {background: white; padding: 14px; border-radius: 12px; border: 1px solid #e5e7eb;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🍱 FoodBridge</h1><p>AI-assisted food donation and redistribution</p></div>', unsafe_allow_html=True)

@st.cache_resource
def load_storage():
    return get_storage()

try:
    store = load_storage()
    donations = store.list_donations()
except Exception as exc:
    st.error(str(exc))
    st.info("For a local demo, set FOODBRIDGE_STORAGE=local. For AWS, configure the AWS settings and permissions first.")
    st.stop()

locations = list(rec.LOCATIONS.keys())
menu = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Add Donation", "Available Donations", "NGO Recommendations", "Admin / Records"]
)
st.sidebar.caption(f"Storage: {store.mode}")
st.sidebar.caption("Demo project — verify food safety and pickup details before redistribution.")

def refresh_data():
    st.cache_resource.clear()
    st.rerun()

def active_donations():
    return [d for d in store.list_donations() if d.get("status") == "Available"]

if menu == "Dashboard":
    st.subheader("Project Dashboard")
    all_rows = store.list_donations()
    total = len(all_rows)
    available = sum(d.get("status") == "Available" for d in all_rows)
    claimed = sum(d.get("status") == "Claimed" for d in all_rows)
    completed = sum(d.get("status") == "Completed" for d in all_rows)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total donations", total)
    c2.metric("Available", available)
    c3.metric("Claimed", claimed)
    c4.metric("Completed", completed)

    if all_rows:
        df = pd.DataFrame(all_rows)
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
        left, right = st.columns(2)
        with left:
            st.markdown("**Donations by food category**")
            st.bar_chart(df.groupby("category")["quantity"].sum())
        with right:
            st.markdown("**Donation status**")
            st.bar_chart(df["status"].value_counts())
        st.markdown("**Recent donations**")
        st.dataframe(df[["donation_id", "food_name", "quantity", "location", "expiry_time", "status"]].head(10),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No donations yet. Add the first donation from the sidebar.")

elif menu == "Add Donation":
    st.subheader("Add a food donation")
    with st.form("donation_form", clear_on_submit=True):
        donor = st.text_input("Donor / restaurant name")
        food = st.text_input("Food name")
        category = st.selectbox("Food category", ["Cooked meals", "Fruits", "Vegetables", "Bakery", "Packaged food", "Other"])
        quantity = st.number_input("Quantity (servings / packets)", min_value=1, max_value=100000, value=10)
        location = st.selectbox("Pickup area", locations)
        expiry_date = st.date_input("Expiry date", value=datetime.now().date())
        expiry_time = st.time_input("Expiry time", value=(datetime.now() + timedelta(hours=8)).time().replace(second=0, microsecond=0))
        notes = st.text_area("Notes (allergens, storage, pickup instructions)")
        image_file = st.file_uploader("Food image (optional)", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("Submit donation", type="primary")

    if submitted:
        if not donor.strip() or not food.strip():
            st.error("Please enter the donor name and food name.")

