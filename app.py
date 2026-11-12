import os
import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, date, time

# PAGE CONFIG
st.set_page_config(
    page_title="FoodBridge AI",
    page_icon="🍱",
    layout="wide"
)

# SESSION STORAGE (DEMO MODE)
if "donations" not in st.session_state:
    st.session_state.donations = []

# LOCATIONS
locations = [
    "Adyar",
    "Anna Nagar",
    "Tambaram",
    "Velachery",
    "T Nagar",
    "Porur",
    "Guindy",
    "Chennai Central"
]

# FUNCTIONS
def active_donations():
    now = datetime.now()
    return [
        d for d in st.session_state.donations
        if d["status"] == "Available"
        and datetime.fromisoformat(d["expiry_time"]) > now
    ]

def add_donation(item):
    st.session_state.donations.append(item)

def update_status(donation_id, status, claimed_by=""):
    for donation in st.session_state.donations:
        if donation["donation_id"] == donation_id:
            if donation["status"] == "Available":
                donation["status"] = status
                donation["claimed_by"] = claimed_by
                return True
    return False

# HEADER
st.title("🍱 FoodBridge AI")
st.caption("Connecting Restaurants, NGOs and Communities")
st.divider()

# SIDEBAR
menu = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "Add Donation",
        "Available Donations",
        "NGO Recommendations",
        "Admin / Records"
    ]
)

# HOME
if menu == "Home":
    st.title("Welcome to FoodBridge AI")
    st.write(
        "A smart food donation platform that connects "
        "restaurants with NGOs to reduce food wastage."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Donations", len(st.session_state.donations))

    with col2:
        st.metric("Available Donations", len(active_donations()))

    with col3:
        st.metric(
            "Claimed Donations",
            sum(d["status"] == "Claimed"
                for d in st.session_state.donations)
        )

# ADD DONATION
elif menu == "Add Donation":

    st.header("🍽️ Add Food Donation")
    st.write("Enter restaurant and food donation details.")

    with st.form("donation_form"):

        donor = st.text_input(
            "Donor / Restaurant Name",
            placeholder="Enter restaurant name",
            max_chars=100
        )

        food = st.text_input(
            "Food Name",
            placeholder="Example: Vegetable Rice"
        )

        category = st.selectbox(
            "Food Category",
            [
                "Cooked Food",
                "Fruits",
                "Vegetables",
                "Bakery",
                "Packaged Food"
            ]
        )

        quantity = st.number_input(
            "Quantity (servings / packets)",
            min_value=1,
            value=10,
            step=1
        )

        location = st.selectbox(
            "Pickup Location",
            locations
        )

        expiry_date = st.date_input(
            "Expiry Date",
            value=date.today()
        )

        expiry_time = st.time_input(
            "Expiry Time",
            value=time(23, 59)
        )

        notes = st.text_area(
            "Additional Notes",
            placeholder="Enter food details..."
        )

        image_file = st.file_uploader(
            "Upload Food Image",
            type=["jpg", "jpeg", "png"]
        )

        submitted = st.form_submit_button(
            "Submit Donation",
            type="primary",
            use_container_width=True
        )

    if submitted:

        if not donor.strip():
            st.error("Please enter the Restaurant Name.")

        elif not food.strip():
            st.error("Please enter the Food Name.")

        else:
            expiry = datetime.combine(
                expiry_date,
                expiry_time
            )

            if expiry <= datetime.now():
                st.error("Expiry time must be in the future.")

            else:
                try:
                    image_url = ""

                    if image_file:
                        os.makedirs("food_images", exist_ok=True)

                        image_path = os.path.join(
                            "food_images",
                            str(uuid.uuid4()) + "_" + image_file.name
                        )

                        with open(image_path, "wb") as f:
                            f.write(image_file.getbuffer())

                        image_url = image_path

                    item = {
                        "donation_id": str(uuid.uuid4())[:8].upper(),
                        "donor_name": donor.strip(),
                        "food_name": food.strip(),
                        "category": category,
                        "quantity": int(quantity),
                        "location": location,
                        "expiry_time": expiry.isoformat(timespec="minutes"),
                        "notes": notes.strip(),
                        "image_url": image_url,
                        "status": "Available",
                        "claimed_by": "",
                        "created_at": datetime.now().isoformat(timespec="seconds")
                    }

                    add_donation(item)

                    st.success(
                        f"Donation from {donor} saved successfully!"
                    )

                except Exception as exc:
                    st.error(f"Could not save donation: {exc}")

# AVAILABLE DONATIONS
elif menu == "Available Donations":

    st.header("🥗 Available Food Donations")

    rows = active_donations()

    if not rows:
        st.info("There are no available donations right now.")

    else:
        df = pd.DataFrame(rows)

        st.dataframe(
            df[
                [
                    "donation_id",
                    "donor_name",
                    "food_name",
                    "category",
                    "quantity",
                    "location",
                    "expiry_time",
                    "notes"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        selected = st.selectbox(
            "Select Donation",
            [d["donation_id"] for d in rows],
            format_func=lambda x: (
                f"{x} - "
                + next(d["food_name"] for d in rows
                       if d["donation_id"] == x)
            )
        )

        ngo_name = st.text_input("NGO Name")

        if st.button("Claim Donation", type="primary"):

            if not ngo_name.strip():
                st.warning("Enter NGO name.")

            elif update_status(selected, "Claimed", ngo_name.strip()):
                st.success("Donation claimed successfully!")

                st.rerun()

# NGO RECOMMENDATIONS
elif menu == "NGO Recommendations":

    st.header("🤝 NGO Recommendations")

    ngo_name = st.text_input(
        "NGO Name",
        value="Community NGO"
    )

    ngo_location = st.selectbox(
        "NGO Location",
        locations
    )

    daily_need = st.number_input(
        "Daily Food Requirement",
        min_value=1,
        value=50
    )

    rows = active_donations()

    if rows:

        recommendations = []

        for donation in rows:

            distance_score = (
                100 if donation["location"] == ngo_location else 50
            )

            quantity_score = max(
                0,
                100 - abs(donation["quantity"] - daily_need)
                / daily_need * 100
            )

            expiry = datetime.fromisoformat(
                donation["expiry_time"]
            )

            remaining_hours = (
                expiry - datetime.now()
            ).total_seconds() / 3600

            urgency_score = max(
                0,
                100 - remaining_hours * 2
            )

            score = (
                0.45 * urgency_score
                + 0.30 * distance_score
                + 0.25 * quantity_score
            )

            recommendations.append({
                "Restaurant": donation["donor_name"],
                "Food": donation["food_name"],
                "Location": donation["location"],
                "Quantity": donation["quantity"],
                "Match Score": round(score, 2)
            })

        recommendations.sort(
            key=lambda x: x["Match Score"],
            reverse=True
        )

        st.caption(
            "Ranking: 45% expiry urgency + "
            "30% location match + 25% quantity match."
        )

        st.dataframe(
            pd.DataFrame(recommendations),
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No available donations for recommendations.")

# ADMIN RECORDS
elif menu == "Admin / Records":

    st.header("📊 Admin Dashboard")

    rows = st.session_state.donations

    if rows:

        df = pd.DataFrame(rows)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Download Donation Records CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="foodbridge_donations.csv",
            mime="text/csv"
        )

        available = [
            d for d in rows
            if d["status"] == "Available"
        ]

        if available:

            selected = st.selectbox(
                "Select Donation to Complete",
                [d["donation_id"] for d in available]
            )

            if st.button("Mark as Completed"):

                update_status(
                    selected,
                    "Completed",
                    "Pickup completed"
                )

                st.success("Donation marked as completed!")

                st.rerun()

    else:
        st.info("No donation records available.")

# FOOTER
st.divider()
st.caption("FoodBridge AI | Smart Food Donation Management System")







