
import streamlit as st
import sqlite3
import hashlib
import os
import pandas as pd
from datetime import datetime

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Online Quiz Portal",
    page_icon="📝",
    layout="wide"
)

DB = "quiz.db"

# ---------------- DATABASE ----------------
def connect():
    return sqlite3.connect(DB)

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, 200000
    )
    return salt.hex() + ":" + hashed.hex()

def verify_password(password, stored):
    try:
        salt, old_hash = stored.split(":")
        return hash_password(password, bytes.fromhex(salt)).split(":")[1] == old_hash
    except Exception:
        return False

def setup_database():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'student'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quizzes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        active INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER,
        question TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        answer TEXT NOT NULL,
        FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS results(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        quiz_id INTEGER,
        score INTEGER,
        total INTEGER,
        percentage REAL,
        submitted_at TEXT
    )
    """)

    # Create default admin
    admin = cur.execute(
        "SELECT id FROM users WHERE email=?",
        ("admin@quiz.com",)
    ).fetchone()

    if not admin:
        cur.execute("""
        INSERT INTO users(full_name,email,password,role)
        VALUES(?,?,?,?)
        """, (
            "Administrator",
            "admin@quiz.com",
            hash_password("admin123"),
            "admin"
        ))

    conn.commit()
    conn.close()

setup_database()

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

if "role" not in st.session_state:
    st.session_state.role = None

if "quiz_attempt" not in st.session_state:
    st.session_state.quiz_attempt = None

# ---------------- COMMON ----------------
def logout():
    st.session_state.user = None
    st.session_state.role = None
    st.session_state.quiz_attempt = None
    st.rerun()

def get_quizzes(active_only=False):
    conn = connect()
    if active_only:
        data = conn.execute(
            "SELECT * FROM quizzes WHERE active=1 ORDER BY id DESC"
        ).fetchall()
    else:
        data = conn.execute(
            "SELECT * FROM quizzes ORDER BY id DESC"
        ).fetchall()
    conn.close()
    return data

# ---------------- LOGIN PAGE ----------------
if st.session_state.user is None:

    st.title("📝 Online Examination Portal")
    st.write("Welcome! Login or register to continue.")
    st.divider()

    login_tab, register_tab, admin_tab = st.tabs([
        "Student Login",
        "Student Registration",
        "Admin Login"
    ])

    # STUDENT LOGIN
    with login_tab:
        st.subheader("Student Login")

        email = st.text_input("Email Address", key="login_email")
        password = st.text_input(
            "Password", type="password", key="login_password"
        )

        if st.button("Login", key="student_login"):
            conn = connect()
            user = conn.execute(
                "SELECT * FROM users WHERE email=? AND role='student'",
                (email.strip().lower(),)
            ).fetchone()
            conn.close()

            if user and verify_password(password, user[3]):
                st.session_state.user = user[0]
                st.session_state.role = "student"
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid email or password.")

    # STUDENT REGISTRATION
    with register_tab:
        st.subheader("Create Student Account")

        full_name = st.text_input("Full Name", key="reg_name")
        reg_email = st.text_input("Email Address", key="reg_email")
        reg_password = st.text_input(
            "Create Password", type="password", key="reg_password"
        )
        confirm_password = st.text_input(
            "Confirm Password", type="password", key="confirm_password"
        )

        if st.button("Register", key="register"):
            if not full_name.strip() or not reg_email.strip() or not reg_password:
                st.warning("Please fill all fields.")
            elif "@" not in reg_email or "." not in reg_email:
                st.warning("Enter a valid email address.")
            elif len(reg_password) < 6:
                st.warning("Password must have at least 6 characters.")
            elif reg_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                try:
                    conn = connect()
                    conn.execute("""
                    INSERT INTO users(full_name,email,password,role)
                    VALUES(?,?,?,'student')
                    """, (
                        full_name.strip(),
                        reg_email.strip().lower(),
                        hash_password(reg_password)
                    ))
                    conn.commit()
                    conn.close()
                    st.success("Registration successful! Now login.")
                except sqlite3.IntegrityError:
                    st.error("This email is already registered.")

    # ADMIN LOGIN
    with admin_tab:
        st.subheader("Administrator Login")

        admin_email = st.text_input(
            "Admin Email", key="admin_email"
        )
        admin_password = st.text_input(
            "Admin Password", type="password", key="admin_password"
        )

        if st.button("Admin Login"):
            conn = connect()
            admin = conn.execute(
                "SELECT * FROM users WHERE email=? AND role='admin'",
                (admin_email.strip().lower(),)
            ).fetchone()
            conn.close()

            if admin and verify_password(admin_password, admin[3]):
                st.session_state.user = admin[0]
                st.session_state.role = "admin"
                st.success("Admin login successful!")
                st.rerun()
            else:
                st.error("Invalid admin credentials.")

    st.stop()

# ---------------- USER DETAILS ----------------
conn = connect()
current_user = conn.execute(
    "SELECT * FROM users WHERE id=?",
    (st.session_state.user,)
).fetchone()
conn.close()

if not current_user:
    logout()

st.sidebar.title("📝 Quiz Portal")
st.sidebar.write(f"Welcome, {current_user[1]}")
st.sidebar.caption(current_user[4].upper())

if st.sidebar.button("Logout"):
    logout()

# =================================================
#                 STUDENT DASHBOARD
# =================================================
if st.session_state.role == "student":

    menu = st.sidebar.radio(
        "Student Menu",
        ["Dashboard", "Available Quizzes", "My Scores", "My Profile"]
    )

    if menu == "Dashboard":

        st.title("🎓 Student Dashboard")
        st.write(f"Hello, {current_user[1]}!")

        conn = connect()

        total_attempts = conn.execute(
            "SELECT COUNT(*) FROM results WHERE user_id=?",
            (current_user[0],)
        ).fetchone()[0]

        avg_score = conn.execute(
            "SELECT AVG(percentage) FROM results WHERE user_id=?",
            (current_user[0],)
        ).fetchone()[0]

        best_score = conn.execute(
            "SELECT MAX(percentage) FROM results WHERE user_id=?",
            (current_user[0],)
        ).fetchone()[0]

        available = conn.execute(
            "SELECT COUNT(*) FROM quizzes WHERE active=1"
        ).fetchone()[0]

        conn.close()

        c1, c2, c3 = st.columns(3)
        c1.metric("Quiz Attempts", total_attempts)
        c2.metric("Average Score", f"{avg_score or 0:.1f}%")
        c3.metric("Best Score", f"{best_score or 0:.1f}%")

        st.divider()
        st.subheader("Available Quizzes")
        st.info(f"You have {available} published quizzes available.")

    # AVAILABLE QUIZZES
    elif menu == "Available Quizzes":

        st.title("📚 Available Quizzes")

        quizzes = get_quizzes(active_only=True)

        if not quizzes:
            st.info("No quizzes are published yet.")

        for quiz in quizzes:

            conn = connect()
            count = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE quiz_id=?",
                (quiz[0],)
            ).fetchone()[0]
            conn.close()

            with st.expander(quiz[1]):

                st.write(quiz[2])
                st.write(f"Total Questions: {count}")

                if count == 0:
                    st.warning("Questions are not available.")
                elif st.button(
                    "Start Quiz",
                    key=f"start_{quiz[0]}"
                ):
                    st.session_state.quiz_attempt = quiz[0]
                    st.rerun()

        # QUIZ ATTEMPT
        quiz_id = st.session_state.quiz_attempt

        if quiz_id:

            st.divider()
            st.subheader("✍️ Attend Examination")

            conn = connect()
            questions = conn.execute(
                "SELECT * FROM questions WHERE quiz_id=?",
                (quiz_id,)
            ).fetchall()
            conn.close()

            if not questions:
                st.warning("No questions available.")
                st.session_state.quiz_attempt = None
            else:

                with st.form("student_quiz_form"):

                    answers = []

                    for i, q in enumerate(questions):
                        st.markdown(f"### Q{i+1}. {q[2]}")

                        selected = st.radio(
                            "Select your answer",
                            [q[3], q[4], q[5], q[6]],
                            key=f"student_answer_{q[0]}"
                        )

                        answers.append(selected)

                    submitted = st.form_submit_button(
                        "Submit Examination"
                    )

                if submitted:

                    score = sum(
                        1 for q, answer in zip(questions, answers)
                        if answer == q[7]
                    )

                    total = len(questions)
                    percentage = score / total * 100

                    conn = connect()
                    conn.execute("""
                    INSERT INTO results(
                        user_id,quiz_id,score,total,percentage,submitted_at
                    ) VALUES(?,?,?,?,?,?)
                    """, (
                        current_user[0],
                        quiz_id,
                        score,
                        total,
                        percentage,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    conn.commit()
                    conn.close()

                    st.session_state.last_result = (
                        score, total, percentage
                    )
                    st.session_state.quiz_attempt = None
                    st.success("Examination submitted successfully!")
                    st.rerun()

    # STUDENT RESULTS
    elif menu == "My Scores":

        st.title("🏆 My Scores")

        conn = connect()
        results = conn.execute("""
        SELECT quizzes.title, results.score, results.total,
        results.percentage, results.submitted_at
        FROM results
        JOIN quizzes ON results.quiz_id=quizzes.id
        WHERE results.user_id=?
        ORDER BY results.id DESC
        """, (current_user[0],)).fetchall()
        conn.close()

        if results:
            df = pd.DataFrame(results, columns=[
                "Quiz", "Score", "Total Questions",
                "Percentage", "Date"
            ])
            st.dataframe(df, use_container_width=True)

            for r in results:
                st.write(f"**{r[0]}**")
                st.progress(min(r[3] / 100, 1.0))
                st.write(f"Score: {r[1]}/{r[2]} | {r[3]:.2f}%")
                st.divider()
        else:
            st.info("You have not attempted any quiz yet.")

    # PROFILE
    elif menu == "My Profile":

        st.title("👤 My Profile")
        st.write("Full Name:", current_user[1])
        st.write("Email:", current_user[2])
        st.write("Account Type: Student")

# =================================================
#                  ADMIN DASHBOARD
# =================================================
elif st.session_state.role == "admin":

    menu = st.sidebar.radio(
        "Admin Menu",
        [
            "Dashboard",
            "Create Quiz",
            "Add Questions",
            "Manage Quizzes",
            "Student Results",
            "Student Details"
        ]
    )

    # ADMIN DASHBOARD
    if menu == "Dashboard":

        st.title("⚙️ Admin Dashboard")
        st.write("Manage your online examination system.")

        conn = connect()

        students = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='student'"
        ).fetchone()[0]

        quizzes = conn.execute(
            "SELECT COUNT(*) FROM quizzes"
        ).fetchone()[0]

        attempts = conn.execute(
            "SELECT COUNT(*) FROM results"
        ).fetchone()[0]

        conn.close()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Students", students)
        c2.metric("Total Quizzes", quizzes)
        c3.metric("Total Attempts", attempts)

        st.divider()
        st.info("Use the Admin Menu to create quizzes and manage questions.")

    # CREATE QUIZ
    elif menu == "Create Quiz":

        st.title("➕ Create New Quiz")

        with st.form("create_quiz_form"):

            title = st.text_input("Quiz Title")
            description = st.text_area("Quiz Description")

            create = st.form_submit_button("Create Quiz")

        if create:

            if title.strip():

                conn = connect()
                conn.execute("""
                INSERT INTO quizzes(title,description,active,created_at)
                VALUES(?,?,0,?)
                """, (
                    title.strip(),
                    description.strip(),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
                conn.commit()
                conn.close()

                st.success("Quiz created successfully! Add questions next.")

            else:
                st.warning("Enter a quiz title.")

    # ADD QUESTIONS
    elif menu == "Add Questions":

        st.title("📝 Add Quiz Questions")

        quizzes = get_quizzes()

        if quizzes:

            quiz_options = {
                f"{q[1]} (ID: {q[0]})": q[0]
                for q in quizzes
            }

            selected_quiz = st.selectbox(
                "Select Quiz",
                list(quiz_options.keys())
            )

            quiz_id = quiz_options[selected_quiz]

            with st.form("add_question_form"):

                question = st.text_area("Enter Question")

                a = st.text_input("Option A")
                b = st.text_input("Option B")
                c = st.text_input("Option C")
                d = st.text_input("Option D")

                answer = st.selectbox(
                    "Select Correct Answer",
                    ["A", "B", "C", "D"]
                )

                add = st.form_submit_button("Add Question")

            if add:

                if all(x.strip() for x in [question, a, b, c, d]):

                    correct = {
                        "A": a, "B": b, "C": c, "D": d
                    }[answer]

                    conn = connect()
                    conn.execute("""
                    INSERT INTO questions(
                        quiz_id,question,option_a,option_b,
                        option_c,option_d,answer
                    ) VALUES(?,?,?,?,?,?,?)
                    """, (
                        quiz_id, question.strip(),
                        a.strip(), b.strip(), c.strip(), d.strip(),
                        correct
                    ))
                    conn.commit()
                    conn.close()

                    st.success("Question added successfully!")

                else:
                    st.warning("Fill all question and option fields.")

            conn = connect()
            count = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE quiz_id=?",
                (quiz_id,)
            ).fetchone()[0]
            conn.close()

            st.info(f"Questions added to this quiz: {count}")

        else:
            st.warning("First create a quiz.")

    # MANAGE QUIZZES
    elif menu == "Manage Quizzes":

        st.title("⚙️ Manage Quizzes")

        quizzes = get_quizzes()

        for q in quizzes:

            with st.expander(q[1]):

                st.write(q[2])

                st.write(
                    "Status:",
                    "Published" if q[3] == 1 else "Draft"
                )

                new_status = st.checkbox(
                    "Publish this quiz",
                    value=bool(q[3]),
                    key=f"publish_{q[0]}"
                )

                if st.button(
                    "Update Status",
                    key=f"update_{q[0]}"
                ):

                    conn = connect()
                    conn.execute(
                        "UPDATE quizzes SET active=? WHERE id=?",
                        (int(new_status), q[0])
                    )
                    conn.commit()
                    conn.close()

                    st.success("Quiz status updated!")
                    st.rerun()

                if st.button(
                    "Delete Quiz",
                    key=f"delete_{q[0]}"
                ):

                    conn = connect()
                    conn.execute(
                        "DELETE FROM results WHERE quiz_id=?",
                        (q[0],)
                    )
                    conn.execute(
                        "DELETE FROM questions WHERE quiz_id=?",
                        (q[0],)
                    )
                    conn.execute(
                        "DELETE FROM quizzes WHERE id=?",
                        (q[0],)
                    )
                    conn.commit()
                    conn.close()

                    st.success("Quiz deleted.")
                    st.rerun()

    # STUDENT RESULTS
    elif menu == "Student Results":

        st.title("📊 Student Examination Results")

        conn = connect()

        results = conn.execute("""
        SELECT users.full_name, users.email, quizzes.title,
        results.score, results.total, results.percentage,
        results.submitted_at
        FROM results
        JOIN users ON results.user_id=users.id
        JOIN quizzes ON results.quiz_id=quizzes.id
        ORDER BY results.id DESC
        """).fetchall()

        conn.close()

        if results:

            df = pd.DataFrame(results, columns=[
                "Student Name", "Email", "Quiz",
                "Score", "Total", "Percentage", "Date"
            ])

            st.dataframe(df, use_container_width=True)

            st.subheader("Score Analysis")
            st.bar_chart(
                df.set_index("Student Name")["percentage"]
            )

        else:
            st.info("No student results available.")

    # STUDENT DETAILS
    elif menu == "Student Details":

        st.title("👨‍🎓 Registered Students")

        conn = connect()
        students = conn.execute("""
        SELECT id,full_name,email
        FROM users WHERE role='student'
        ORDER BY id DESC
        """).fetchall()
        conn.close()

        if students:

            df = pd.DataFrame(
                students,
                columns=["Student ID", "Full Name", "Email"]
            )

            st.dataframe(df, use_container_width=True)

            st.metric("Registered Students", len(students))

        else:
            st.info("No students registered yet.")

st.divider()
st.caption("Online Quiz Portal | Python | Streamlit | SQLite")

