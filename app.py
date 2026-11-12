

import streamlit as st
import sqlite3
import random
from datetime import datetime

# PAGE CONFIG
st.set_page_config(
    page_title="Online Quiz System",
    page_icon="📝",
    layout="wide"
)

# DATABASE CONNECTION
def connect_db():
    return sqlite3.connect("quiz.db")

# CREATE TABLES
def create_tables():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options TEXT,
            answer TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS results(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            score INTEGER,
            total INTEGER,
            percentage REAL,
            date TEXT
        )
    """)

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM questions")

    if cur.fetchone()[0] == 0:
        sample_questions = [
            ("What does CPU stand for?",
             "Central Processing Unit|Computer Personal Unit|Central Program Utility|Control Processing User",
             "Central Processing Unit"),

            ("Which language is used with Streamlit?",
             "C|Java|Python|PHP",
             "Python"),

            ("What is DBMS?",
             "Database Management System|Data Backup System|Digital Base System|Database Memory System",
             "Database Management System"),

            ("Which is a cloud platform?",
             "Notepad|AWS|Paint|MS Word",
             "AWS"),

            ("Which language is used for web page structure?",
             "Python|HTML|C++|SQL",
             "HTML"),

            ("What does RAM stand for?",
             "Read Access Memory|Random Access Memory|Run Active Memory|Real Application Memory",
             "Random Access Memory"),

            ("Which database uses SQL?",
             "PostgreSQL|HTML|CSS|JavaScript",
             "PostgreSQL"),

            ("What is the full form of URL?",
             "Uniform Resource Locator|Universal Read Link|User Resource Login|Unified Reference Link",
             "Uniform Resource Locator")
        ]

        cur.executemany(
            "INSERT INTO questions(question, options, answer) VALUES(?,?,?)",
            sample_questions
        )

    conn.commit()
    conn.close()


create_tables()

# TITLE
st.title("📝 Cloud Based Online Quiz System")
st.write("Welcome to the Online Examination Portal")

# SIDEBAR
menu = st.sidebar.radio(
    "Navigation",
    ["Home", "Student Quiz", "My Results", "Admin Dashboard"]
)

# HOME
if menu == "Home":

    st.header("Welcome to Online Quiz")

    st.markdown("""
    ### Features
    - Student Registration
    - Multiple Choice Questions
    - Automatic Evaluation
    - Instant Results
    - Student Result History
    - Admin Dashboard
    """)

    st.info("Start your online examination using Student Quiz.")

# STUDENT QUIZ
elif menu == "Student Quiz":

    st.header("👨‍🎓 Student Examination")

    name = st.text_input("Enter Student Name")

    if st.button("Start Quiz"):

        if name.strip():

            conn = connect_db()
            questions = conn.execute(
                "SELECT * FROM questions"
            ).fetchall()
            conn.close()

            random.shuffle(questions)

            st.session_state.questions = questions
            st.session_state.student = name.strip()
            st.session_state.started = True
            st.session_state.submitted = False

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

                    st.subheader(f"Question {i+1}")
                    st.write(q[1])

                    options = q[2].split("|")

                    selected = st.radio(
                        "Choose your answer",
                        options,
                        key=f"answer_{i}"
                    )

                    answers.append(selected)

                submit = st.form_submit_button("Submit Quiz")

            if submit:

                score = sum(
                    1 for q, ans in zip(questions, answers)
                    if q[3] == ans
                )

                total = len(questions)
                percentage = (score / total) * 100

                conn = connect_db()

                conn.execute("""
                    INSERT INTO results
                    (student_name, score, total, percentage, date)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    st.session_state.student,
                    score,
                    total,
                    percentage,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

                conn.commit()
                conn.close()

                st.session_state.score = score
                st.session_state.total = total
                st.session_state.percentage = percentage
                st.session_state.submitted = True

                st.rerun()

        else:

            st.success("Quiz Submitted Successfully!")

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

    st.header("📊 My Quiz Results")

    student = st.text_input("Enter Student Name")

    if st.button("View Results"):

        conn = connect_db()

        data = conn.execute("""
            SELECT score, total, percentage, date
            FROM results
            WHERE student_name = ?
            ORDER BY id DESC
        """, (student.strip(),)).fetchall()

        conn.close()

        if data:

            for result in data:

                st.write(f"Date: {result[3]}")
                st.write(f"Score: {result[0]}/{result[1]}")
                st.write(f"Percentage: {result[2]:.2f}%")
                st.divider()

        else:
            st.warning("No results found.")

# ADMIN DASHBOARD
elif menu == "Admin Dashboard":

    st.header("🔐 Admin Dashboard")

    password = st.text_input(
        "Enter Admin Password",
        type="password"
    )

    if st.button("Login"):

        if password == "admin123":

            st.success("Admin Login Successful!")

            conn = connect_db()

            data = conn.execute("""
                SELECT student_name, score, total,
                percentage, date
                FROM results
                ORDER BY id DESC
            """).fetchall()

            conn.close()

            st.metric("Total Quiz Attempts", len(data))

            if data:

                st.dataframe(
                    data,
                    use_container_width=True
                )

            else:
                st.info("No student results available.")

        else:
            st.error("Invalid Password")

st.divider()
st.caption("Online Quiz System | Python + Streamlit + SQLite")

