
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="FoodRescue AI",
    page_icon="🥗",
    layout="wide"
)

# ---------------- SESSION STATE ----------------
if "food_data" not in st.session_state:
    st.session_state.food_data = []

# ---------------- CUSTOM DESIGN ----------------
st.markdown("""
<style>
.stApp {
    background-color: #f5f8f5;
}
h1 {
    color: #176B45;
}
h2, h3 {
    color: #245C40;
}
div[data-testid="stMetric"] {
    background-color: white;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #e0e8e0;
}
</style>
""", unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------
st.sidebar.title("🥗 FoodRescue AI")
st.sidebar.caption("Smart Food Rescue Platform")

menu = st.sidebar.radio(
    "MAIN MENU",
    [
        "Dashboard",
        "Food Prediction",
        "Add Surplus Food",
        "Food Donations",
        "NGO Dashboard",
        "Analytics",
        "About Project"
    ]
)

st.sidebar.divider()
st.sidebar.success("Reducing Food Waste 🌱")

# ---------------- DASHBOARD ----------------
if menu == "Dashboard":

    st.title("🥗 FoodRescue AI")
    st.subheader("AI-Powered Food Waste Management System")

    st.write(
        "Predict food demand, identify surplus food "
        "and connect food providers with NGOs."
    )

    total_food = sum(
        item["Quantity (kg)"]
        for item in st.session_state.food_data
    )

    total_listings = len(st.session_state.food_data)

    available = sum(
        1 for item in st.session_state.food_data
        if item["Status"] == "Available"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Food Listed", f"{total_food:.1f} kg")
    col2.metric("Total Listings", total_listings)
    col3.metric("Available Donations", available)

    st.divider()

    st.subheader("Welcome to FoodRescue AI")

    st.info(
        "Our mission is to prevent food wastage "
        "through Artificial Intelligence and Cloud Computing."
    )

    st.subheader("How the system works")

    c1, c2, c3 = st.columns(3)

    c1.write("🍲 **Food Providers**")
    c1.caption("Add and track surplus food.")

    c2.write("🤖 **AI Prediction**")
    c2.caption("Estimate food requirements.")

    c3.write("🤝 **NGO Connection**")
    c3.caption("Connect surplus food with NGOs.")

# ---------------- FOOD PREDICTION ----------------
elif menu == "Food Prediction":

    st.title("🤖 AI Food Demand Prediction")

    st.write(
        "Estimate the amount of food required "
        "based on expected attendance."
    )

    people = st.number_input(
        "Expected number of people",
        min_value=1,
        max_value=10000,
        value=100
    )

    portion = st.number_input(
        "Food quantity per person (kg)",
        min_value=0.05,
        max_value=2.0,
        value=0.35
    )

    buffer = st.slider(
        "Additional safety buffer (%)",
        0, 30, 10
    )

    if st.button("Predict Food Requirement"):

        prediction = people * portion * (1 + buffer / 100)

        st.success(
            f"Recommended food preparation: "
            f"{prediction:.2f} kg"
        )

        st.caption(
            "This is a baseline estimate. "
            "A trained ML prediction model will be integrated later."
        )

# ---------------- ADD SURPLUS FOOD ----------------
elif menu == "Add Surplus Food":

    st.title("🍲 Add Surplus Food")

    with st.form("food_form"):

        food_name = st.text_input("Food Name")

        quantity = st.number_input(
            "Quantity (kg)",
            min_value=0.1,
            value=1.0
        )

        servings = st.number_input(
            "Number of Servings",
            min_value=1,
            value=10
        )

        location = st.text_input("Pickup Location")

        expiry = st.date_input("Available Until")

        description = st.text_area(
            "Food Description / Allergen Information"
        )

        image = st.file_uploader(
            "Upload Food Image",
            type=["jpg", "jpeg", "png"]
        )

        submit = st.form_submit_button(
            "Submit Food Donation"
        )

        if submit:

            if food_name.strip() and location.strip():

                st.session_state.food_data.append({
                    "Food Name": food_name,
                    "Quantity (kg)": quantity,
                    "Servings": servings,
                    "Location": location,
                    "Available Until": str(expiry),
                    "Description": description,
                    "Status": "Available",
                    "Image": image.getvalue() if image else None,
                    "Date": str(datetime.now())
                })

                st.success("Food listing added successfully!")

            else:
                st.error("Please enter food name and location.")

# ---------------- FOOD DONATIONS ----------------
elif menu == "Food Donations":

    st.title("🤝 Food Donation Marketplace")

    if not st.session_state.food_data:

        st.info("No food donations available yet.")

    for index, item in enumerate(st.session_state.food_data):

        with st.container(border=True):

            st.subheader(item["Food Name"])

            col1, col2 = st.columns(2)

            col1.write(
                f"**Quantity:** {item['Quantity (kg)']} kg"
            )

            col2.write(
                f"**Servings:** {item['Servings']}"
            )

            st.write(
                f"📍 Location: {item['Location']}"
            )

            st.write(
                f"📅 Available until: {item['Available Until']}"
            )

            st.write(
                f"Status: {item['Status']}"
            )

            if item["Image"]:
                st.image(item["Image"], width=250)

            if item["Description"]:
                st.caption(item["Description"])

            if item["Status"] == "Available":

                if st.button(
                    "Accept Donation",
                    key=f"accept_{index}"
                ):

                    st.session_state.food_data[index]["Status"] = "Accepted"

                    st.success("Donation accepted!")

                    st.rerun()

# ---------------- NGO DASHBOARD ----------------
elif menu == "NGO Dashboard":

    st.title("🏥 NGO Dashboard")

    accepted = [
        item for item in st.session_state.food_data
        if item["Status"] == "Accepted"
    ]

    st.metric("Accepted Donations", len(accepted))

    if accepted:

        for item in accepted:

            st.write(
                f"🍱 {item['Food Name']} - "
                f"{item['Quantity (kg)']} kg"
            )

    else:
        st.info("No donations have been accepted yet.")

# ---------------- ANALYTICS ----------------
elif menu == "Analytics":

    st.title("📊 Food Waste Analytics")

    if st.session_state.food_data:

        df = pd.DataFrame(
            st.session_state.food_data
        )

        st.subheader("Food Listing Details")

        st.dataframe(
            df.drop(columns=["Image"]),
            use_container_width=True
        )

        chart = px.bar(
            df,
            x="Food Name",
            y="Quantity (kg)",
            color="Status",
            title="Food Quantity Overview"
        )

        st.plotly_chart(
            chart,
            use_container_width=True
        )

        total = df["Quantity (kg)"].sum()

        st.metric(
            "Total Food Listed",
            f"{total:.2f} kg"
        )

    else:

        st.info("Add food listings to view analytics.")

# ---------------- ABOUT PROJECT ----------------
elif menu == "About Project":

    st.title("About FoodRescue AI")

    st.write("""
    FoodRescue AI is an intelligent food waste
    prediction and redistribution platform.

    **Technologies:**

    - Python
    - Streamlit
    - Artificial Intelligence
    - Machine Learning
    - AWS Cloud Computing

    **AWS Integration Planned:**

    - Amazon EC2 – Application hosting
    - Amazon RDS – Database
    - Amazon S3 – Food image storage
    - Amazon SNS – Donation notifications

    **Objective:**

    Reduce food waste and connect surplus food
    with people who need it.
    """)

    st.success("Save Food. Share Hope. Reduce Waste. 🌱")
