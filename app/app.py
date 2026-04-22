from flask import Flask, render_template, request, redirect, session
import pickle
import numpy as np
import sqlite3
import hashlib
from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
app.secret_key = "secret123"

# =========================
# LOAD MODELS
# =========================
model_t = pickle.load(open(r"D:\MachineLearning_Project\Uplift Marketing Project\app\models\model_t.pkl","rb"))
model_c = pickle.load(open(r"D:\MachineLearning_Project\Uplift Marketing Project\app\models\model_c.pkl","rb"))

# =========================
# DATABASE SETUP
# =========================
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # history table
    c.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        score REAL,
        segment TEXT,
        decision TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# PASSWORD HASHING
# =========================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =========================
# UPLIFT PREDICTION
# =========================
def predict_uplift(data):
    arr = np.array(data).reshape(1, -1)

    p_t = model_t.predict_proba(arr)[:, 1][0]
    p_c = model_c.predict_proba(arr)[:, 1][0]

    uplift = p_t - p_c

    if uplift > 0.10:
        segment = "Persuadable"
        decision = "Send Email"
    elif uplift > 0:
        segment = "Sure Thing"
        decision = "Skip"
    elif uplift > -0.10:
        segment = "Lost Cause"
        decision = "Skip"
    else:
        segment = "Do Not Disturb"
        decision = "Avoid"

    # NEW: confidence logic
    if abs(uplift) > 0.08:
        confidence = "High"
    elif abs(uplift) > 0.03:
        confidence = "Medium"
    else:
        confidence = "Low"

    return uplift, segment, decision, p_t, p_c, confidence

# =========================
# ROUTES
# =========================

# Home
@app.route("/")
def home():
    return render_template("index.html")

# -------------------------
# AUTH SYSTEM
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = hash_password(request.form["password"])

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["user"] = username
            return redirect("/dashboard")
        else:
            return "Invalid credentials"

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = hash_password(request.form["password"])

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users(username,password) VALUES(?,?)", (username, password))
            conn.commit()
        except:
            return "User already exists"

        conn.close()
        return redirect("/login")

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    return render_template("logout.html")  # 👈 logout page show hoga


#----------------------------
# A/B Testing
#---------------------------
@app.route('/abtest')
@login_required
def abtest():
    import pandas as pd

    # ✅ Step 1: Load data properly (important)
    df = pd.read_csv(r"D:\MachineLearning_Project\Uplift\app\Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv")

    # ✅ Step 2: Create treatment column safely
    df['treatment'] = df['segment'].apply(
        lambda x: 0 if str(x).strip().lower() == 'no e-mail' else 1
    )

    # ✅ Step 3: Calculate conversion rate
    conv = (df.groupby('treatment')['conversion'].mean() * 100).to_dict()

    # ✅ Step 4: Calculate average revenue
    rev = df.groupby('treatment')['spend'].mean().to_dict()

    # ✅ Step 5: Default values (avoid key error in HTML)
    conv.setdefault(0, 0)
    conv.setdefault(1, 0)
    rev.setdefault(0, 0)
    rev.setdefault(1, 0)

    return render_template("abtest.html", conv=conv, rev=rev)

# -------------------------
# DASHBOARD
# -------------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    return render_template("dashboard.html", user=session["user"])


# -------------------------
# PREDICTION
# -------------------------
@app.route("/predict_page")
def predict_page():
    if "user" not in session:
        return redirect("/login")

    return render_template("predict.html")


@app.route("/predict", methods=["POST"])
def predict():
    if "user" not in session:
        return redirect("/login")

    recency = float(request.form["recency"])
    history = float(request.form["history"])
    mens = int(request.form["mens"])
    womens = int(request.form["womens"])

    score, segment, decision, p_t, p_c, confidence = predict_uplift(
        [recency, history, mens, womens]
    )

    # save history
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO history(username, score, segment, decision) VALUES(?,?,?,?)",
        (session["user"], float(score), segment, decision)
    )
    conn.commit()
    conn.close()

    return render_template(
        "dashboard.html",
        user=session["user"],
        score=round(score, 4),
        segment=segment,
        decision=decision,
        treatment=round(p_t, 3),
        control=round(p_c, 3),
        confidence=confidence
    )


# -------------------------
# HISTORY PAGE
# -------------------------
@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT score, segment, decision FROM history WHERE username=?", (session["user"],))
    data = c.fetchall()

    conn.close()

    return render_template("history.html", data=data)


# -------------------------
# ABOUT PAGE
# -------------------------
@app.route("/about")
def about():
    if "user" not in session:
        return redirect("/login")

    return render_template("about.html")


# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    app.run(debug=True)