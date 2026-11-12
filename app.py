"""CloudQuiz - cloud-based online quiz system (Streamlit + Firebase Firestore).

Features: student/admin login, cloud DB, timed scoring, leaderboard,
study-PDF -> AI question generator, face detection (OpenCV) + ID photo check.
"""
import hashlib, json, os, time
import cv2, numpy as np, pandas as pd, streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
from pypdf import PdfReader

st.set_page_config(page_title="CloudQuiz", page_icon="☁️")
TIME_LIMIT = 20  # seconds per question (used for the speed bonus)


# ---------------------------------------------------------------- cloud DB
@st.cache_resource
def get_db():
    info = dict(st.secrets["firebase"])
    # clean the private key: strip stray quotes/spaces and convert literal "\n" to real newlines
    key = str(info["private_key"]).strip().strip('"').replace("\\n", "\n").strip()
    info["private_key"] = key + "\n"
    creds = service_account.Credentials.from_service_account_info(info)
    return firestore.Client(credentials=creds, project=info["project_id"])


db = get_db()


def hash_pw(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()


def load_questions():
    docs = db.collection("questions").order_by("order").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]


def load_attempts():
    docs = db.collection("attempts").stream()
    rows = [d.to_dict() for d in docs]
    return sorted(rows, key=lambda r: r.get("score", 0), reverse=True)


# ---------------------------------------------------------------- face check
_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def count_faces(file) -> int:
    img = cv2.imdecode(np.frombuffer(file.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return len(_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60)))


# ---------------------------------------------------------------- auth
def auth_page():
    st.title("☁️ CloudQuiz")
    st.caption("Online tests with instant evaluation, stored in the cloud.")
    tab_login, tab_reg = st.tabs(["Login", "Register"])

    with tab_login:
        roll = st.text_input("Roll number / User ID", key="l_roll").strip().lower()
        pw = st.text_input("Password", type="password", key="l_pw")
        if st.button("Login"):
            snap = db.collection("users").document(roll).get() if roll else None
            if not snap or not snap.exists:
                st.error("No account found. Please register first.")
            else:
                u = snap.to_dict()
                if hash_pw(pw, u["salt"]) != u["hash"]:
                    st.error("Incorrect ID or password.")
                else:
                    st.session_state.user = {"roll": roll, "name": u["name"], "role": u["role"]}
                    st.rerun()

    with tab_reg:
        role = st.radio("I am a", ["student", "admin"], horizontal=True)
        name = st.text_input("Full name")
        roll = st.text_input("Roll number / User ID", key="r_roll").strip().lower()
        pw = st.text_input("Password (min 6 chars)", type="password", key="r_pw")
        code = st.text_input("Admin code", type="password") if role == "admin" else ""
        if st.button("Create account"):
            if not (name.strip() and roll and len(pw) >= 6):
                st.error("Fill all fields (password min 6 characters).")
            elif role == "admin" and code != st.secrets.get("ADMIN_CODE", ""):
                st.error("Wrong admin code.")
            elif db.collection("users").document(roll).get().exists:
                st.error("This ID is already registered.")
            else:
                salt = os.urandom(16).hex()
                db.collection("users").document(roll).set(
                    {"name": name.strip(), "role": role, "salt": salt, "hash": hash_pw(pw, salt)}
                )
                st.success("Account created. Now log in from the Login tab.")


# ---------------------------------------------------------------- student pages
def home_page():
    qs, at = load_questions(), load_attempts()
    st.subheader(f"Hello, {st.session_state.user['name']}")
    st.write(f"**{len(qs)}** questions in the cloud · **{len(at)}** submissions so far")
    st.markdown(
        "**Why an online test system?**\n"
        "- Paper tests are slow to evaluate → scoring here is automatic and instant.\n"
        "- Paper is hard to store → results are saved digitally in a cloud database.\n"
        "- Paper tests are limited to one place and time → students can attend from anywhere.\n\n"
        "**Why the cloud?** No servers to buy or maintain; the college uses, and pays for, "
        "only the computing it consumes."
    )


def test_page():
    ss, user = st.session_state, st.session_state.user
    qs = load_questions()
    if not qs:
        st.info("No questions yet. Please check back later.")
        return

    # ---- before the test: identity + face check
    if ss.get("quiz") is None:
        st.subheader("🛡️ Identity & face check")
        st.caption("Checks that exactly one face is visible and that your ID card has a photo. "
                   "It detects faces only; it does not identify or match people. Images are not stored.")
        selfie = st.camera_input("Take a selfie")
        id_img = st.file_uploader("Upload a photo of your ID card", type=["png", "jpg", "jpeg"])
        if st.button("Verify"):
            if not selfie or not id_img:
                st.warning("Provide both the selfie and the ID card photo.")
            else:
                n_self, n_id = count_faces(selfie), count_faces(id_img)
                ss.verified = (n_self == 1 and n_id >= 1)
                if ss.verified:
                    st.success("Identity check passed ✔")
                else:
                    st.error(f"Failed: selfie faces = {n_self} (need exactly 1), ID card faces = {n_id} (need ≥ 1).")
        skip = st.checkbox("Skip verification (demo only)")
        if st.button("Start test", disabled=not (ss.get("verified") or skip), type="primary"):
            ss.quiz = {"i": 0, "score": 0, "right": 0, "flags": 0, "phase": "ask",
                       "t0": time.time(), "skipped": bool(skip and not ss.get("verified"))}
            st.rerun()
        return

    qz = ss.quiz
    # ---- finished
    if qz["i"] >= len(qs):
        ref = db.collection("attempts").document(user["roll"])
        if not qz.get("saved"):
            old = ref.get()
            tries = (old.to_dict().get("tries", 1) if old.exists else 0) + 1
            if old.exists and old.to_dict()["score"] >= qz["score"]:
                ref.update({"tries": tries})
            else:
                ref.set({"name": user["name"], "roll": user["roll"], "score": qz["score"],
                         "right": qz["right"], "total": len(qs), "tries": tries,
                         "flags": qz["flags"], "skipped": qz["skipped"], "at": time.time()})
            qz["saved"] = True
        st.balloons()
        st.metric("Final score", qz["score"])
        st.write(f"{qz['right']} of {len(qs)} correct · proctor flags: {qz['flags']}")
        if st.button("Back"):
            ss.quiz, ss.verified = None, False
            st.rerun()
        return

    # ---- a question
    q = qs[qz["i"]]
    st.caption(f"Question {qz['i'] + 1} of {len(qs)} · Score {qz['score']}")
    st.subheader(q["text"])
    if qz["phase"] == "ask":
        choice = st.radio("Choose one", q["options"], index=None, key=f"c{qz['i']}")
        snap = st.camera_input("Proctor snapshot (optional)", key=f"p{qz['i']}")
        if st.button("Submit answer", disabled=choice is None):
            if snap is not None and count_faces(snap) != 1:
                qz["flags"] += 1
                st.warning("⚠ Proctor alert: exactly one face must be visible. Recorded.")
            elapsed = time.time() - qz["t0"]
            correct = q["options"].index(choice) == q["answer"]
            if correct:
                qz["right"] += 1
                qz["score"] += 10 + max(0, int(TIME_LIMIT - elapsed))
            qz.update(phase="rev", last=choice, correct=correct)
            st.rerun()
    else:
        (st.success if qz["correct"] else st.error)(
            "Correct! ✔" if qz["correct"] else f"Wrong. Correct answer: {q['options'][q['answer']]}")
        if st.button("Next →"):
            qz.update(i=qz["i"] + 1, phase="ask", t0=time.time())
            st.rerun()


def my_result_page():
    snap = db.collection("attempts").document(st.session_state.user["roll"]).get()
    if not snap.exists:
        st.info("You haven't taken the test yet.")
        return
    m = snap.to_dict()
    st.metric("Best score", m["score"])
    st.write(f"{m['right']}/{m['total']} correct ({round(100 * m['right'] / m['total'])}%) · "
             f"{m.get('tries', 1)} attempt(s)")


def leaderboard_page():
    st.subheader("🏆 Leaderboard")
    rows = load_attempts()[:20]
    if not rows:
        st.info("No scores yet.")
        return
    st.dataframe(pd.DataFrame(rows)[["name", "score", "right", "total"]].rename(
        columns={"name": "Name", "score": "Score", "right": "Correct", "total": "Total"}),
        hide_index=True, use_container_width=True)


# ---------------------------------------------------------------- admin pages
def questions_page():
    st.subheader("Add a question")
    with st.form("addq", clear_on_submit=True):
        text = st.text_input("Question")
        opts = [st.text_input(f"Option {i + 1}") for i in range(4)]
        ans = st.selectbox("Correct option", [1, 2, 3, 4])
        if st.form_submit_button("Add question"):
            if text.strip() and all(o.strip() for o in opts):
                db.collection("questions").add({"text": text.strip(), "options": [o.strip() for o in opts],
                                                "answer": ans - 1, "order": time.time()})
                st.success("Added ✔")
            else:
                st.error("Fill the question and all 4 options.")
    st.subheader("Questions in cloud")
    for q in load_questions():
        c1, c2 = st.columns([6, 1])
        c1.write(q["text"])
        if c2.button("Delete", key=f"d{q['id']}"):
            db.collection("questions").document(q["id"]).delete()
            st.rerun()


def import_pdf_page():
    st.subheader("📄 Import study PDF")
    f = st.file_uploader("Study material (text PDF)", type="pdf")
    n = st.selectbox("How many questions?", [5, 10, 15])
    if f and st.button("Generate questions"):
        text = "\n".join((p.extract_text() or "") for p in PdfReader(f).pages)[:14000]
        if len(text.strip()) < 80:
            st.error("No readable text found (is it a scanned PDF?).")
            return
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
            prompt = (f"From the study material below, write {n} multiple-choice questions for a college quiz. "
                      'Return ONLY a JSON array of objects {"text": str, "options": [exactly 4 strings], '
                      '"answer": index 0-3 of the correct option}. Use only facts from the material.\n\n'
                      f"MATERIAL:\n{text}")
            with st.spinner("AI is writing questions..."):
                msg = client.messages.create(model="claude-sonnet-5-5", max_tokens=3000,
                                             messages=[{"role": "user", "content": prompt}])
            raw = msg.content[0].text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
            qs = [x for x in json.loads(raw) if len(x.get("options", [])) == 4 and x.get("answer") in range(4)]
            st.session_state.drafts = qs
        except Exception as e:
            st.error(f"Generation failed: {e}")
    drafts = st.session_state.get("drafts", [])
    for i, x in enumerate(drafts, 1):
        st.markdown(f"**{i}. {x['text']}**")
        st.write("  \n".join(("✔ " if k == x["answer"] else "• ") + o for k, o in enumerate(x["options"])))
    if drafts and st.button("Save all to cloud", type="primary"):
        for i, x in enumerate(drafts):
            db.collection("questions").add({"text": x["text"], "options": x["options"],
                                            "answer": x["answer"], "order": time.time() + i})
        st.session_state.drafts = []
        st.success(f"Saved {len(drafts)} questions ✔")


def results_page():
    rows = load_attempts()
    st.subheader("Results dashboard")
    if not rows:
        st.info("No submissions yet.")
        return
    df = pd.DataFrame(rows)
    df["percent"] = (100 * df["right"] / df["total"]).round()
    st.write(f"{len(df)} student(s) submitted · class average {int(df['percent'].mean())}%")
    st.dataframe(df[["roll", "name", "score", "right", "percent", "tries", "flags", "skipped"]],
                 hide_index=True, use_container_width=True)
    st.download_button("Download CSV", df.to_csv(index=False), "results.csv")


# ---------------------------------------------------------------- main
if "user" not in st.session_state:
    auth_page()
    st.stop()

user = st.session_state.user
st.sidebar.write(f"👤 **{user['name']}** ({user['role']})")
pages = {"Home": home_page}
if user["role"] == "student":
    pages |= {"Take test": test_page, "My result": my_result_page}
pages["Leaderboard"] = leaderboard_page
if user["role"] == "admin":
    pages |= {"Questions": questions_page, "Import study PDF": import_pdf_page, "Results": results_page}
choice = st.sidebar.radio("Menu", list(pages))
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
pages[choice]()
