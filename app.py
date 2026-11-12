
import streamlit as st
from supabase import create_client
import random

# PAGE CONFIG
st.set_page_config(
    page_title="Online Quiz System",
    page_icon="📝",
    layout="centered"
)

# CLOUD DATABASE CONNECTION
@st.cache_resource
def connect_db():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

try:
    db = connect_db()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

# HEADER
st.title("📝 Online Quiz System")
st.write("Welcome! Attend your online examination.")
st.divider()

# MENU
menu = st.sidebar.selectbox(
    "Choose Menu",
    ["Student Quiz", "My Results", "Admin Dashboard"]
)

# STUDENT QUIZ
if menu == "Student Quiz":

    st.subheader("👨‍🎓 Student Details")

    name = st.text_input("Enter Student Name")

    if st.button("Start Quiz"):
        if name.strip():
            st.session_state.student = name.strip()
            st.session_state.started = True
            st.session_state.submitted = False

            response = db.table(
                "quiz_questions"
            ).select("*").execute()

            questions = response.data

            if questions:
                random.shuffle(questions)
                st.session_state.questions = questions
            else:
                st.error("No questions available.")
                st.session_state.started = False
        else:
            st.warning("Please enter your name.")

    if st.session_state.get("started", False):

        if not st.session_state.get("submitted", False):

            st.success(
                f"Welcome {st.session_state.student}!"
            )

            questions = st.session_state.questions

            with st.form("quiz_form"):

                answers = []

                for i, q in enumerate(questions):

                    st.markdown(
                        f"### Q{i+1}. {q['question']}"
                    )

                    options = q["options"]

                    selected = st.radio(
                        "Select your answer:",
                        options,
                        key=f"question_{q['id']}"
                    )

                    answers.append(selected)

                submit = st.form_submit_button(
                    "Submit Quiz"
                )

            if submit:

                score = 0

                for q, answer in zip(questions, answers):
                    if answer == q["answer"]:
                        score += 1

                total = len(questions)
                percentage = (score / total) * 100

                # SAVE RESULT TO CLOUD DATABASE
                try:
                    db.table("quiz_results").insert({
                        "student_name": st.session_state.student,
                        "score": score,
                        "total_questions": total,
                        "percentage": percentage
                    }).execute()

                    st.session_state.submitted = True
                    st.session_state.score = score
                    st.session_state.total = total
                    st.session_state.percentage = percentage

                    st.rerun()

                except Exception as e:
                    st.error(f"Could not save result: {e}")

        else:

            st.success("🎉 Quiz Submitted Successfully!")

            st.metric(
                "Your Score",
                f"{st.session_state.score}/{st.session_state.total}"
            )

            st.metric(
                "Percentage",
                f"{st.session_state.percentage:.2f}%"
            )

            if st.button("Take Another Quiz"):
                st.session_state.started = False
                st.session_state.submitted = False
                st.rerun()

# MY RESULTS
elif menu == "My Results":

    st.subheader("📊 Student Results")

    student = st.text_input("Enter your registered name")

    if st.button("View My Results"):

        if student.strip():

            try:
                result = db.table(
                    "quiz_results"
                ).select("*").eq(
                    "student_name", student.strip()
                ).order(
                    "submitted_at", desc=True
                ).execute()

                if result.data:
                    st.dataframe(
                        result.data,
                        use_container_width=True
                    )
                else:
                    st.info("No results found.")

            except Exception as e:
                st.error(str(e))

# ADMIN DASHBOARD
elif menu == "Admin Dashboard":

    st.subheader("🔐 Admin Dashboard")

    password = st.text_input(
        "Admin Password",
        type="password"
    )

    if st.button("Login"):

        if password == st.secrets["ADMIN_PASSWORD"]:

            try:
                results = db.table(
                    "quiz_results"
                ).select("*").order(
                    "submitted_at", desc=True
                ).execute()

                st.success("Admin Login Successful!")

                if results.data:

                    st.metric(
                        "Total Attempts",
                        len(results.data)
                    )

                    st.dataframe(
                        results.data,
                        use_container_width=True
                    )

                else:
                    st.info("No student results yet.")

            except Exception as e:
                st.error(str(e))

        else:
            st.error("Invalid Admin Password")

st.divider()
st.caption("Online Quiz System | Streamlit + Supabase Cloud")
