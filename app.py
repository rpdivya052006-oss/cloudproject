

import streamlit as st
import sqlite3
import hashlib
import secrets
import pandas as pd
from datetime import datetime

# ---------------- CONFIG ----------------

st.set_page_config(
    page_title="Online Quiz System",
    page_icon="📝",
    layout="wide"
)

DB = "quiz_system.db"

# ---------------- DATABASE ----------------

def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    with connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            active INTEGER DEFAULT 0,
            created_at TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            question TEXT,
            option1 TEXT,
            option2 TEXT,
            option3 TEXT,
            option4 TEXT,
            answer INTEGER
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            quiz_id INTEGER,
            score INTEGER,
            total INTEGER,
            percentage REAL,
            submitted_at TEXT
        )
        """)

        # Add default admin if not already present
        admin = conn.execute(
            "SELECT id FROM users WHERE email=?",
            ("admin@quiz.com",)
        ).fetchone()

        if not admin:
            conn.execute("""
            INSERT INTO users(full_name,email,password,role)
            VALUES(?,?,?,?)
            """, (
                "Administrator",
                "admin@quiz.com",
                hash_password("admin123"),
                "admin"
            ))


# ---------------- PASSWORD ----------------

def hash_password(password):
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000
    )
    return salt.hex() + ":" + hashed.hex()


def verify_password(password, stored_password):
    try:
        salt_hex, hash_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000
        )

        return secrets.compare_digest(
            new_hash.hex(),
            hash_hex
        )
    except Exception:
        return False


# ---------------- USER FUNCTIONS ----------------

def register_user(name, email, password):
    try:
        with connect() as conn:
            conn.execute("""
            INSERT INTO users(full_name,email,password,role)
            VALUES(?,?,?,?)
            """, (
                name.strip(),
                email.strip().lower(),
                hash_password(password),
                "student"
            ))
        return True
    except sqlite3.IntegrityError:
        return False


def login_user(email, password, role):
    with connect() as conn:
        user = conn.execute("""
        SELECT * FROM users
        WHERE email=? AND role=?
        """, (email.strip().lower(), role)).fetchone()

    if user and verify_password(password, user["password"]):
        return dict(user)

    return None


# ---------------- SESSION ----------------

if "user" not in st.session_state:
    st.session_state.user = None

if "quiz_attempt" not in st.session_state:
    st.session_state.quiz_attempt = None

create_tables()

# ---------------- LOGIN PAGE ----------------

def login_page():

    st.title("📝 Online Quiz System")
    st.write("Welcome! Login or register to continue.")

    login_tab, register_tab, admin_tab = st.tabs([
        "Student Login",
        "Student Registration",
        "Admin Login"
    ])

    with login_tab:
        st.subheader("Student Login")

        email = st.text_input(
            "Email",
            key="student_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="student_password"
        )

        if st.button("Login", key="student_login"):
            if not email or not password:
                st.warning("Enter email and password.")
            else:
                user = login_user(email, password, "student")

                if user:
                    st.session_state.user = user
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

    with register_tab:
        st.subheader("Create Student Account")

        name = st.text_input("Full Name", key="reg_name")
        email = st.text_input("Email Address", key="reg_email")
        password = st.text_input(
            "Create Password",
            type="password",
            key="reg_password"
        )
        confirm = st.text_input(
            "Confirm Password",
            type="password",
            key="reg_confirm"
        )

        if st.button("Register", key="register_button"):
            if not name.strip() or not email.strip() or not password:
                st.warning("Please fill all fields.")
            elif "@" not in email or "." not in email:
                st.warning("Enter a valid email address.")
            elif len(password) < 6:
                st.warning("Password must contain at least 6 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            elif register_user(name, email, password):
                st.success("Registration successful! Now login.")
            else:
                st.error("This email is already registered.")

    with admin_tab:
        st.subheader("Admin Login")

        email = st.text_input("Admin Email", key="admin_email")
        password = st.text_input(
            "Admin Password",
            type="password",
            key="admin_password"
        )

        if st.button("Admin Login"):
            user = login_user(email, password, "admin")

            if user:
                st.session_state.user = user
                st.success("Admin login successful!")
                st.rerun()
            else:
                st.error("Invalid admin credentials.")


# ---------------- STUDENT DASHBOARD ----------------

def student_dashboard():

    user = st.session_state.user

    st.title("🎓 Student Dashboard")
    st.write("Welcome,", user["full_name"])

    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.quiz_attempt = None
        st.rerun()

    tab1, tab2, tab3 = st.tabs([
        "Available Quizzes",
        "My Scores",
        "My Profile"
    ])

    with tab1:
        st.subheader("Available Quizzes")

        with connect() as conn:
            quizzes = conn.execute("""
            SELECT * FROM quizzes WHERE active=1
            ORDER BY id DESC
            """).fetchall()

        if not quizzes:
            st.info("No quizzes are available currently.")

        for quiz in quizzes:
            with st.container(border=True):
                st.subheader(quiz["title"])
                st.write(quiz["description"])

                if st.button(
                    "Start Quiz",
                    key=f"start_{quiz['id']}"
                ):
                    st.session_state.quiz_attempt = quiz["id"]
                    st.rerun()

    with tab2:
        st.subheader("My Quiz Results")

        with connect() as conn:
            results = conn.execute("""
            SELECT q.title, r.score, r.total,
                   r.percentage, r.submitted_at
            FROM results r
            JOIN quizzes q ON q.id=r.quiz_id
            WHERE r.user_id=?
            ORDER BY r.id DESC
            """, (user["id"],)).fetchall()

        if results:
            st.dataframe(
                pd.DataFrame([dict(r) for r in results]),
                use_container_width=True
            )
        else:
            st.info("You have not completed any quizzes.")

    with tab3:
        st.subheader("Student Profile")
        st.write("Name:", user["full_name"])
        st.write("Email:", user["email"])
        st.write("Role:", user["role"])


# ---------------- QUIZ ATTEMPT ----------------

def take_quiz():

    user = st.session_state.user
    quiz_id = st.session_state.quiz_attempt

    with connect() as conn:
        quiz = conn.execute(
            "SELECT * FROM quizzes WHERE id=? AND active=1",
            (quiz_id,)
        ).fetchone()

        questions = conn.execute(
            "SELECT * FROM questions WHERE quiz_id=?",
            (quiz_id,)
        ).fetchall()

    if not quiz or not questions:
        st.error("Quiz is unavailable.")
        if st.button("Back to Dashboard"):
            st.session_state.quiz_attempt = None
            st.rerun()
        return

    st.title("📝 " + quiz["title"])
    st.write(quiz["description"])
    st.write("Total Questions:", len(questions))

    answers = []

    for i, q in enumerate(questions):
        st.markdown(f"### Q{i+1}. {q['question']}")

        options = [
            q["option1"],
            q["option2"],
            q["option3"],
            q["option4"]
        ]

        selected = st.radio(
            "Select your answer",
            options,
            key=f"question_{q['id']}",
            index=None
        )

        answers.append((q, selected))

    if st.button("Submit Quiz"):
        if any(selected is None for q, selected in answers):
            st.warning("Please answer all questions before submitting.")
            return

        score = 0

        for q, selected in answers:
            correct = q["answer"]
            options = [
                q["option1"],
                q["option2"],
                q["option3"],
                q["option4"]
            ]

            if selected == options[correct - 1]:
                score += 1

        total = len(questions)
        percentage = (score / total) * 100

        with connect() as conn:
            conn.execute("""
            INSERT INTO results
            (user_id,quiz_id,score,total,percentage,submitted_at)
            VALUES(?,?,?,?,?,?)
            """, (
                user["id"],
                quiz_id,
                score,
                total,
                percentage,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        st.session_state.quiz_attempt = None
        st.session_state.last_result = {
            "score": score,
            "total": total,
            "percentage": percentage
        }
        st.rerun()


# ---------------- ADMIN DASHBOARD ----------------

def admin_dashboard():

    st.title("⚙️ Admin Dashboard")
    st.write("Welcome Administrator!")

    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard",
        "Create Quiz",
        "Add Questions",
        "Manage Quizzes",
        "Student Results"
    ])

    with tab1:
        with connect() as conn:
            students = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role='student'"
            ).fetchone()[0]

            quizzes = conn.execute(
                "SELECT COUNT(*) FROM quizzes"
            ).fetchone()[0]

            questions = conn.execute(
                "SELECT COUNT(*) FROM questions"
            ).fetchone()[0]

            attempts = conn.execute(
                "SELECT COUNT(*) FROM results"
            ).fetchone()[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Students", students)
        c2.metric("Quizzes", quizzes)
        c3.metric("Questions", questions)
        c4.metric("Attempts", attempts)

    with tab2:
        st.subheader("Create New Quiz")

        title = st.text_input("Quiz Title")
        description = st.text_area("Quiz Description")

        if st.button("Create Quiz"):
            if not title.strip():
                st.warning("Enter quiz title.")
            else:
                with connect() as conn:
                    conn.execute("""
                    INSERT INTO quizzes(title,description,active,created_at)
                    VALUES(?,?,0,?)
                    """, (
                        title.strip(),
                        description,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                st.success("Quiz created successfully!")

    with tab3:
        st.subheader("Add Questions")

        with connect() as conn:
            quizzes = conn.execute(
                "SELECT * FROM quizzes ORDER BY id DESC"
            ).fetchall()

        if quizzes:
            quiz_map = {
                f"{q['title']} (ID: {q['id']})": q["id"]
                for q in quizzes
            }

            selected_quiz = st.selectbox(
                "Select Quiz",
                list(quiz_map.keys())
            )

            quiz_id = quiz_map[selected_quiz]

            question = st.text_area("Enter Question")

            options = [
                st.text_input("Option 1"),
                st.text_input("Option 2"),
                st.text_input("Option 3"),
                st.text_input("Option 4")
            ]

            correct = st.selectbox(
                "Correct Answer",
                [1, 2, 3, 4]
            )

            if st.button("Add Question"):
                if not question.strip() or any(
                    not option.strip() for option in options
                ):
                    st.warning("Fill the question and all four options.")
                else:
                    with connect() as conn:
                        conn.execute("""
                        INSERT INTO questions
                        (quiz_id,question,option1,option2,option3,option4,answer)
                        VALUES(?,?,?,?,?,?,?)
                        """, (
                            quiz_id,
                            question.strip(),
                            *options,
                            correct
                        ))

                    st.success("Question added successfully!")
        else:
            st.info("Create a quiz first.")

    with tab4:
        st.subheader("Manage Quizzes")

        with connect() as conn:
            quizzes = conn.execute(
                "SELECT * FROM quizzes ORDER BY id DESC"
            ).fetchall()

        for q in quizzes:
            with st.container(border=True):
                st.write("**" + q["title"] + "**")
                st.write(q["description"])
                st.write(
                    "Status:",
                    "Published" if q["active"] else "Unpublished"
                )

                col1, col2 = st.columns(2)

                with col1:
                    if q["active"]:
                        if st.button(
                            "Unpublish",
                            key=f"unpublish_{q['id']}"
                        ):
                            with connect() as conn:
                                conn.execute(
                                    "UPDATE quizzes SET active=0 WHERE id=?",
                                    (q["id"],)
                                )
                            st.rerun()
                    else:
                        if st.button(
                            "Publish",
                            key=f"publish_{q['id']}"
                        ):
                            with connect() as conn:
                                conn.execute(
                                    "UPDATE quizzes SET active=1 WHERE id=?",
                                    (q["id"],)
                                )
                            st.rerun()

                with col2:
                    if st.button(
                        "Delete",
                        key=f"delete_{q['id']}"
                    ):
                        with connect() as conn:
                            conn.execute(
                                "DELETE FROM results WHERE quiz_id=?",
                                (q["id"],)
                            )
                            conn.execute(
                                "DELETE FROM questions WHERE quiz_id=?",
                                (q["id"],)
                            )
                            conn.execute(
                                "DELETE FROM quizzes WHERE id=?",
                                (q["id"],)
                            )
                        st.rerun()

    with tab5:
        st.subheader("Student Results")

        with connect() as conn:
            results = conn.execute("""
            SELECT u.full_name, u.email, q.title,
                   r.score, r.total, r.percentage, r.submitted_at
            FROM results r
            JOIN users u ON u.id=r.user_id
            JOIN quizzes q ON q.id=r.quiz_id
            ORDER BY r.id DESC
            """).fetchall()

        if results:
            st.dataframe(
                pd.DataFrame([dict(r) for r in results]),
                use_container_width=True
            )
        else:
            st.info("No student results yet.")


# ---------------- MAIN APP ----------------

if st.session_state.user is None:
    login_page()

elif st.session_state.quiz_attempt is not None:
    take_quiz()

elif st.session_state.user["role"] == "admin":
    admin_dashboard()

else:
    student_dashboard()


