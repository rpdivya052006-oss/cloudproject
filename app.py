
import streamlit as st

# PAGE CONFIGURATION
st.set_page_config(
    page_title="FoodRescue AI",
    page_icon="🥗",
    layout="wide"
)

# SESSION STATE
if "foods" not in st.session_state:
    st.session_state.foods = []

# CUSTOM CSS
st.markdown("""
<style>
.stApp {
    background-color: #F1F8F2;
}
h1 {
    color: #176B45;
    font-weight: bold;
}
h2, h3 {
    color: #28734D;
}
div[data-testid="stMetric"] {
    background-color: white;
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #D5E8D8;
}
.stButton button {
    background-color: #218653;
    color: white;
    border-radius: 10px;
    border: none;
}
</style>
""", unsafe_allow_html=True)

# SIDEBAR
st.sidebar.title("🥗 FoodRescue AI")
st.sidebar.caption("Save Food • Share Hope")

menu = st.sidebar.radio(
    "MAIN MENU",
    ["Home", "Food Prediction", "Food Donation"]
)

st.sidebar.success("🌱 Reduce Food Waste")

# HOME PAGE
if menu == "Home":

    st.title("🥗 FoodRescue AI")

    st.subheader("Save Food. Share Hope. Reduce Waste.")

    st.write(
        "Welcome to FoodRescue AI! "
        "A smart platform to reduce food waste "
        "through food prediction and food donation."
    )

    st.image(
        "https://images.unsplash.com/photo-1547592180-85f173990554?w=1200",
        use_container_width=True
    )

    st.divider()

    st.header("🌍 Our Mission")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("🍲 **Save Food**\n\nPrevent food wastage.")

    with col2:
        st.success("🤖 **Predict Food**\n\nEstimate food requirements.")

    with col3:
        st.warning("🤝 **Share Food**\n\nDonate surplus food.")

    st.divider()

    st.header("📊 Project Overview")

    total = sum(
        food["Quantity"] for food in st.session_state.foods
    )

    col1, col2 = st.columns(2)

    col1.metric("Total Food Donated", f"{total:.1f} kg")
    col2.metric("Total Donations", len(st.session_state.foods))


# FOOD PREDICTION
elif menu == "Food Prediction":

    st.title("🤖 Food Requirement Prediction")

    st.write("Calculate the estimated food quantity.")

    people = st.number_input(
        "Expected Number of People",
        min_value=1,
        value=100
    )

    quantity = st.number_input(
        "Food per Person (kg)",
        min_value=0.05,
        max_value=2.0,
        value=0.35
    )

    if st.button("🔍 Predict Food Requirement"):

        result = people * quantity

        st.success(
            f"🍱 Required Food Quantity: {result:.2f} kg"
        )

        st.balloons()

        st.info(
            "Prepare the estimated food quantity "
            "to help reduce food wastage."
        )


# FOOD DONATION
elif menu == "Food Donation":

    st.title("🍲 Surplus Food Donation")

    st.write("Donate extra food and help people in need.")

    with st.form("donation_form"):

        food_name = st.text_input("Food Name")

        quantity = st.number_input(
            "Food Quantity (kg)",
            min_value=0.1,
            value=1.0
        )

        location = st.text_input("Pickup Location")

        description = st.text_area("Food Description")

        submit = st.form_submit_button("❤️ Donate Food")

        if submit:

            if food_name.strip() and location.strip():

                st.session_state.foods.append({
                    "Food": food_name,
                    "Quantity": quantity,
                    "Location": location,
                    "Description": description
                })

                st.success("Donation Added Successfully!")

            else:
                st.error("Please enter Food Name and Location.")

    st.divider()

    st.header("🤝 Available Food Donations")

    if st.session_state.foods:

        for food in st.session_state.foods:

            with st.container(border=True):

                st.subheader("🍱 " + food["Food"])

                st.write(
                    f"Quantity: {food['Quantity']} kg"
                )

                st.write(
                    f"📍 Location: {food['Location']}"
                )

                st.write(
                    f"Description: {food['Description']}"
                )

    else:

        st.info("No donations available yet.")

